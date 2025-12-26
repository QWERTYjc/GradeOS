"""
属性测试：补偿操作正确性

**功能: architecture-deep-integration, 属性 8: 补偿操作正确性**
**验证: 需求 4.2**

测试缓存写入成功但数据库写入失败时，系统执行补偿操作删除缓存条目，
最终状态与操作前一致。
"""

import asyncio
import pytest
from hypothesis import given, strategies as st, settings, Phase
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from src.services.distributed_transaction import (
    DistributedTransactionCoordinator,
    SagaStep,
    SagaStepStatus,
    SagaTransactionStatus,
)
from src.utils.pool_manager import UnifiedPoolManager, PoolNotInitializedError


# 配置 Hypothesis
settings.register_profile(
    "ci",
    max_examples=100,
    phases=[Phase.generate, Phase.target, Phase.shrink]
)


# 测试数据生成策略
step_names = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_- "),
    min_size=1,
    max_size=30
)

step_counts = st.integers(min_value=1, max_value=5)

fail_at_step = st.integers(min_value=0, max_value=4)


@dataclass
class MockState:
    """模拟状态，用于跟踪操作和补偿"""
    actions_executed: List[str]
    compensations_executed: List[str]
    values: Dict[str, Any]
    
    def __init__(self):
        self.actions_executed = []
        self.compensations_executed = []
        self.values = {}


class MockPoolManager:
    """模拟连接池管理器"""
    
    def __init__(self):
        self._initialized = True
        self._pg_data: Dict[str, Any] = {}
    
    async def pg_connection(self):
        """模拟 PostgreSQL 连接"""
        class MockConnection:
            def __init__(self, data):
                self._data = data
            
            async def execute(self, query: str, params=None):
                # 简单模拟：不实际执行 SQL
                return MockCursor()
            
            async def __aenter__(self):
                return self
            
            async def __aexit__(self, *args):
                pass
        
        class MockCursor:
            async def fetchone(self):
                return None
            
            async def fetchall(self):
                return []
        
        class MockContextManager:
            def __init__(self, data):
                self._data = data
            
            async def __aenter__(self):
                return MockConnection(self._data)
            
            async def __aexit__(self, *args):
                pass
        
        return MockContextManager(self._pg_data)


class TestCompensationCorrectness:
    """
    **功能: architecture-deep-integration, 属性 8: 补偿操作正确性**
    **验证: 需求 4.2**
    
    测试补偿操作的正确性：
    - 失败时逆序执行补偿
    - 补偿后状态与操作前一致
    """
    
    @given(
        num_steps=step_counts,
        fail_step=fail_at_step
    )
    @settings(max_examples=100)
    def test_compensation_restores_initial_state(
        self, 
        num_steps: int, 
        fail_step: int
    ):
        """
        **功能: architecture-deep-integration, 属性 8: 补偿操作正确性**
        **验证: 需求 4.2**
        
        对于任意缓存写入成功但数据库写入失败的场景，
        系统应当执行补偿操作删除已写入的缓存条目，
        最终状态应当与操作前一致。
        """
        async def run_test():
            # 确保 fail_step 在有效范围内
            actual_fail_step = min(fail_step, num_steps - 1)
            
            # 设置
            pool_manager = MockPoolManager()
            coordinator = DistributedTransactionCoordinator(
                pool_manager, 
                enable_logging=False
            )
            
            # 跟踪状态
            state = MockState()
            initial_values = {}
            
            # 创建步骤
            steps = []
            for i in range(num_steps):
                step_name = f"step_{i}"
                
                # 创建动作闭包
                def make_action(idx: int, name: str):
                    async def action():
                        if idx == actual_fail_step:
                            raise Exception(f"Step {name} failed")
                        state.actions_executed.append(name)
                        state.values[name] = f"value_{idx}"
                        return f"result_{idx}"
                    return action
                
                # 创建补偿闭包
                def make_compensation(name: str):
                    async def compensation():
                        state.compensations_executed.append(name)
                        if name in state.values:
                            del state.values[name]
                    return compensation
                
                steps.append(SagaStep(
                    name=step_name,
                    action=make_action(i, step_name),
                    compensation=make_compensation(step_name),
                ))
            
            # 执行 Saga
            saga_id = coordinator.generate_saga_id()
            result = await coordinator.execute_saga(saga_id, steps)
            
            # 验证执行失败
            assert result is False, "Saga 应该失败"
            
            # 验证补偿操作逆序执行
            expected_compensations = list(reversed(state.actions_executed))
            assert state.compensations_executed == expected_compensations, \
                f"补偿应该逆序执行: 期望 {expected_compensations}, 实际 {state.compensations_executed}"
            
            # 验证最终状态与初始状态一致（所有值都被清理）
            assert state.values == initial_values, \
                f"最终状态应该与初始状态一致: 期望 {initial_values}, 实际 {state.values}"
        
        asyncio.get_event_loop().run_until_complete(run_test())
    
    @given(num_steps=step_counts)
    @settings(max_examples=100)
    def test_successful_saga_no_compensation(self, num_steps: int):
        """
        **功能: architecture-deep-integration, 属性 8: 补偿操作正确性**
        **验证: 需求 4.1**
        
        对于成功的 Saga 事务，不应执行任何补偿操作。
        """
        async def run_test():
            # 设置
            pool_manager = MockPoolManager()
            coordinator = DistributedTransactionCoordinator(
                pool_manager,
                enable_logging=False
            )
            
            # 跟踪状态
            state = MockState()
            
            # 创建步骤（全部成功）
            steps = []
            for i in range(num_steps):
                step_name = f"step_{i}"
                
                def make_action(name: str):
                    async def action():
                        state.actions_executed.append(name)
                        return f"result"
                    return action
                
                def make_compensation(name: str):
                    async def compensation():
                        state.compensations_executed.append(name)
                    return compensation
                
                steps.append(SagaStep(
                    name=step_name,
                    action=make_action(step_name),
                    compensation=make_compensation(step_name),
                ))
            
            # 执行 Saga
            saga_id = coordinator.generate_saga_id()
            result = await coordinator.execute_saga(saga_id, steps)
            
            # 验证执行成功
            assert result is True, "Saga 应该成功"
            
            # 验证所有步骤都执行了
            assert len(state.actions_executed) == num_steps, \
                f"应该执行 {num_steps} 个步骤"
            
            # 验证没有执行补偿
            assert len(state.compensations_executed) == 0, \
                "成功的 Saga 不应执行补偿"
        
        asyncio.get_event_loop().run_until_complete(run_test())
    
    @given(num_steps=step_counts)
    @settings(max_examples=100)
    def test_first_step_failure_no_compensation_needed(self, num_steps: int):
        """
        **功能: architecture-deep-integration, 属性 8: 补偿操作正确性**
        **验证: 需求 4.2**
        
        当第一个步骤就失败时，不需要执行任何补偿操作。
        """
        async def run_test():
            # 设置
            pool_manager = MockPoolManager()
            coordinator = DistributedTransactionCoordinator(
                pool_manager,
                enable_logging=False
            )
            
            # 跟踪状态
            state = MockState()
            
            # 创建步骤（第一个就失败）
            steps = []
            for i in range(num_steps):
                step_name = f"step_{i}"
                
                def make_action(idx: int, name: str):
                    async def action():
                        if idx == 0:
                            raise Exception("First step failed")
                        state.actions_executed.append(name)
                        return f"result"
                    return action
                
                def make_compensation(name: str):
                    async def compensation():
                        state.compensations_executed.append(name)
                    return compensation
                
                steps.append(SagaStep(
                    name=step_name,
                    action=make_action(i, step_name),
                    compensation=make_compensation(step_name),
                ))
            
            # 执行 Saga
            saga_id = coordinator.generate_saga_id()
            result = await coordinator.execute_saga(saga_id, steps)
            
            # 验证执行失败
            assert result is False, "Saga 应该失败"
            
            # 验证没有步骤成功执行
            assert len(state.actions_executed) == 0, \
                "第一步失败时不应有步骤成功执行"
            
            # 验证没有执行补偿（因为没有成功的步骤）
            assert len(state.compensations_executed) == 0, \
                "没有成功步骤时不需要补偿"
        
        asyncio.get_event_loop().run_until_complete(run_test())


class TestCompensationRetry:
    """
    测试补偿操作的重试机制
    """
    
    @given(
        num_steps=st.integers(min_value=2, max_value=4),
        compensation_fail_count=st.integers(min_value=1, max_value=2)
    )
    @settings(max_examples=100, deadline=None)
    def test_compensation_retry_on_failure(
        self, 
        num_steps: int, 
        compensation_fail_count: int
    ):
        """
        **功能: architecture-deep-integration, 属性 8: 补偿操作正确性**
        **验证: 需求 4.2**
        
        补偿操作失败时应该重试。
        """
        async def run_test():
            # 设置
            pool_manager = MockPoolManager()
            coordinator = DistributedTransactionCoordinator(
                pool_manager,
                max_compensation_retries=3,
                enable_logging=False
            )
            
            # 跟踪状态
            compensation_attempts: Dict[str, int] = {}
            
            # 创建步骤
            steps = []
            for i in range(num_steps):
                step_name = f"step_{i}"
                compensation_attempts[step_name] = 0
                
                def make_action(idx: int, name: str):
                    async def action():
                        if idx == num_steps - 1:
                            raise Exception("Last step failed")
                        return f"result_{idx}"
                    return action
                
                def make_compensation(name: str, fail_times: int):
                    async def compensation():
                        compensation_attempts[name] += 1
                        if compensation_attempts[name] <= fail_times:
                            raise Exception(f"Compensation {name} failed")
                    return compensation
                
                # 只有第一个步骤的补偿会失败几次
                fail_times = compensation_fail_count if i == 0 else 0
                
                steps.append(SagaStep(
                    name=step_name,
                    action=make_action(i, step_name),
                    compensation=make_compensation(step_name, fail_times),
                ))
            
            # 执行 Saga
            saga_id = coordinator.generate_saga_id()
            result = await coordinator.execute_saga(saga_id, steps)
            
            # 验证执行失败
            assert result is False, "Saga 应该失败"
            
            # 验证补偿重试了
            assert compensation_attempts["step_0"] == compensation_fail_count + 1, \
                f"补偿应该重试 {compensation_fail_count} 次后成功"
        
        asyncio.get_event_loop().run_until_complete(run_test())


class TestCacheCompensation:
    """
    测试缓存写入失败时的补偿
    
    模拟真实场景：缓存写入成功，数据库写入失败，需要删除缓存
    """
    
    @given(
        cache_key=st.text(min_size=1, max_size=20),
        cache_value=st.dictionaries(
            keys=st.text(min_size=1, max_size=10),
            values=st.text(max_size=20),
            min_size=1,
            max_size=3
        )
    )
    @settings(max_examples=100)
    def test_cache_compensation_on_db_failure(
        self, 
        cache_key: str, 
        cache_value: dict
    ):
        """
        **功能: architecture-deep-integration, 属性 8: 补偿操作正确性**
        **验证: 需求 4.2**
        
        对于任意缓存写入成功但数据库写入失败的场景，
        系统应当执行补偿操作删除已写入的缓存条目。
        """
        async def run_test():
            # 设置
            pool_manager = MockPoolManager()
            coordinator = DistributedTransactionCoordinator(
                pool_manager,
                enable_logging=False
            )
            
            # 模拟缓存
            cache: Dict[str, Any] = {}
            
            # 缓存写入动作
            async def cache_write():
                cache[cache_key] = cache_value
                return True
            
            # 缓存写入补偿
            async def cache_compensation():
                if cache_key in cache:
                    del cache[cache_key]
            
            # 数据库写入动作（失败）
            async def db_write():
                raise Exception("Database write failed")
            
            # 数据库写入补偿
            async def db_compensation():
                pass  # 数据库写入失败，无需补偿
            
            steps = [
                SagaStep(
                    name="cache_write",
                    action=cache_write,
                    compensation=cache_compensation,
                ),
                SagaStep(
                    name="db_write",
                    action=db_write,
                    compensation=db_compensation,
                ),
            ]
            
            # 验证初始状态
            assert cache_key not in cache, "初始缓存应该为空"
            
            # 执行 Saga
            saga_id = coordinator.generate_saga_id()
            result = await coordinator.execute_saga(saga_id, steps)
            
            # 验证执行失败
            assert result is False, "Saga 应该失败"
            
            # 验证缓存已被补偿删除
            assert cache_key not in cache, \
                "补偿操作应该删除缓存条目，恢复到初始状态"
        
        asyncio.get_event_loop().run_until_complete(run_test())
