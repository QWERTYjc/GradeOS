"""
分布式事务集成测试

测试 Saga 模式的分布式事务执行和补偿操作。

验证：需求 4.1, 4.2
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from src.services.distributed_transaction import (
    DistributedTransactionCoordinator,
    SagaStep,
    SagaStepStatus,
    SagaTransactionStatus,
    SagaTransaction,
    ReviewOverrideSagaBuilder,
)
from src.utils.pool_manager import UnifiedPoolManager


class MockPoolManager:
    """模拟统一连接池管理器"""
    
    def __init__(self):
        self._pg_data = {}
        self._transactions = {}
    
    def pg_connection(self):
        return MockPgConnection(self._pg_data, self._transactions)
    
    def pg_transaction(self):
        return MockPgTransaction(self._pg_data)


class MockPgConnection:
    """模拟 PostgreSQL 连接"""
    
    def __init__(self, data: dict, transactions: dict):
        self._data = data
        self._transactions = transactions
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    
    async def execute(self, query: str, params=None):
        # 模拟事务日志记录
        if "INSERT INTO saga_transactions" in query or "UPDATE saga_transactions" in query:
            if params:
                saga_id = params[0]
                self._transactions[saga_id] = {
                    "saga_id": saga_id,
                    "steps": params[1] if len(params) > 1 else [],
                    "final_status": params[2] if len(params) > 2 else "started",
                }
        return MockPgResult(self._data)


class MockPgTransaction:
    """模拟 PostgreSQL 事务"""
    
    def __init__(self, data: dict):
        self._data = data
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    
    async def execute(self, query: str, params=None):
        return MockPgResult(self._data)


class MockPgResult:
    """模拟 PostgreSQL 查询结果"""
    
    def __init__(self, data: dict):
        self._data = data
    
    async def fetchone(self):
        return self._data.get("row")
    
    async def fetchall(self):
        return self._data.get("rows", [])


class TestSagaStepDataClass:
    """测试 Saga 步骤数据类"""
    
    def test_saga_step_initialization(self):
        """测试 Saga 步骤初始化"""
        async def action():
            return "result"
        
        async def compensation():
            pass
        
        step = SagaStep(
            name="测试步骤",
            action=action,
            compensation=compensation
        )
        
        assert step.name == "测试步骤"
        assert step.status == SagaStepStatus.PENDING
        assert step.result is None
        assert step.error is None
    
    def test_saga_step_to_dict(self):
        """测试 Saga 步骤转换为字典"""
        async def action():
            pass
        
        async def compensation():
            pass
        
        step = SagaStep(
            name="步骤1",
            action=action,
            compensation=compensation,
            status=SagaStepStatus.COMPLETED,
            started_at=datetime(2025, 12, 13, 10, 0, 0, tzinfo=timezone.utc),
            completed_at=datetime(2025, 12, 13, 10, 0, 5, tzinfo=timezone.utc)
        )
        
        result = step.to_dict()
        
        assert result["name"] == "步骤1"
        assert result["status"] == "completed"
        assert "started_at" in result
        assert "completed_at" in result


class TestSagaTransactionExecution:
    """
    测试 Saga 事务执行
    
    验证：需求 4.1
    """
    
    @pytest.mark.asyncio
    async def test_successful_saga_execution(self):
        """测试成功的 Saga 事务执行
        
        验证：需求 4.1
        """
        pool_manager = MockPoolManager()
        coordinator = DistributedTransactionCoordinator(
            pool_manager=pool_manager,
            enable_logging=False
        )
        
        execution_order = []
        
        async def step1_action():
            execution_order.append("step1")
            return "step1_result"
        
        async def step1_compensation():
            execution_order.append("step1_comp")
        
        async def step2_action():
            execution_order.append("step2")
            return "step2_result"
        
        async def step2_compensation():
            execution_order.append("step2_comp")
        
        async def step3_action():
            execution_order.append("step3")
            return "step3_result"
        
        async def step3_compensation():
            execution_order.append("step3_comp")
        
        steps = [
            SagaStep(name="步骤1", action=step1_action, compensation=step1_compensation),
            SagaStep(name="步骤2", action=step2_action, compensation=step2_compensation),
            SagaStep(name="步骤3", action=step3_action, compensation=step3_compensation),
        ]
        
        saga_id = coordinator.generate_saga_id()
        result = await coordinator.execute_saga(saga_id, steps)
        
        # 验证执行成功
        assert result is True
        
        # 验证执行顺序
        assert execution_order == ["step1", "step2", "step3"]
        
        # 验证所有步骤状态
        for step in steps:
            assert step.status == SagaStepStatus.COMPLETED
    
    @pytest.mark.asyncio
    async def test_saga_execution_with_step_failure(self):
        """测试步骤失败时的 Saga 事务执行
        
        验证：需求 4.1, 4.2
        """
        pool_manager = MockPoolManager()
        coordinator = DistributedTransactionCoordinator(
            pool_manager=pool_manager,
            enable_logging=False
        )
        
        execution_order = []
        
        async def step1_action():
            execution_order.append("step1")
            return "step1_result"
        
        async def step1_compensation():
            execution_order.append("step1_comp")
        
        async def step2_action():
            execution_order.append("step2")
            raise Exception("步骤2失败")
        
        async def step2_compensation():
            execution_order.append("step2_comp")
        
        steps = [
            SagaStep(name="步骤1", action=step1_action, compensation=step1_compensation),
            SagaStep(name="步骤2", action=step2_action, compensation=step2_compensation),
        ]
        
        saga_id = coordinator.generate_saga_id()
        result = await coordinator.execute_saga(saga_id, steps)
        
        # 验证执行失败
        assert result is False
        
        # 验证执行顺序（包括补偿）
        assert "step1" in execution_order
        assert "step2" in execution_order
        assert "step1_comp" in execution_order
        
        # 验证步骤状态
        assert steps[0].status == SagaStepStatus.COMPENSATED
        assert steps[1].status == SagaStepStatus.FAILED


class TestSagaCompensation:
    """
    测试 Saga 补偿操作
    
    验证：需求 4.2
    """
    
    @pytest.mark.asyncio
    async def test_compensation_reverse_order(self):
        """测试补偿操作按逆序执行
        
        验证：需求 4.2
        """
        pool_manager = MockPoolManager()
        coordinator = DistributedTransactionCoordinator(
            pool_manager=pool_manager,
            enable_logging=False
        )
        
        compensation_order = []
        
        async def step1_action():
            return "step1"
        
        async def step1_compensation():
            compensation_order.append("step1_comp")
        
        async def step2_action():
            return "step2"
        
        async def step2_compensation():
            compensation_order.append("step2_comp")
        
        async def step3_action():
            return "step3"
        
        async def step3_compensation():
            compensation_order.append("step3_comp")
        
        # 创建已完成的步骤
        steps = [
            SagaStep(name="步骤1", action=step1_action, compensation=step1_compensation, status=SagaStepStatus.COMPLETED),
            SagaStep(name="步骤2", action=step2_action, compensation=step2_compensation, status=SagaStepStatus.COMPLETED),
            SagaStep(name="步骤3", action=step3_action, compensation=step3_compensation, status=SagaStepStatus.COMPLETED),
        ]
        
        saga_id = coordinator.generate_saga_id()
        result = await coordinator.compensate(saga_id, steps)
        
        # 验证补偿成功
        assert result is True
        
        # 验证补偿按逆序执行
        assert compensation_order == ["step3_comp", "step2_comp", "step1_comp"]
    
    @pytest.mark.asyncio
    async def test_compensation_with_retry(self):
        """测试补偿操作重试
        
        验证：需求 4.2
        """
        pool_manager = MockPoolManager()
        coordinator = DistributedTransactionCoordinator(
            pool_manager=pool_manager,
            max_compensation_retries=3,
            enable_logging=False
        )
        
        attempt_count = 0
        
        async def step1_action():
            return "step1"
        
        async def step1_compensation():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise Exception(f"补偿失败，尝试 {attempt_count}")
            # 第三次成功
        
        steps = [
            SagaStep(name="步骤1", action=step1_action, compensation=step1_compensation, status=SagaStepStatus.COMPLETED),
        ]
        
        saga_id = coordinator.generate_saga_id()
        result = await coordinator.compensate(saga_id, steps)
        
        # 验证补偿最终成功
        assert result is True
        assert attempt_count == 3
        assert steps[0].status == SagaStepStatus.COMPENSATED
    
    @pytest.mark.asyncio
    async def test_compensation_failure_after_max_retries(self):
        """测试补偿操作超过最大重试次数后失败
        
        验证：需求 4.2
        """
        pool_manager = MockPoolManager()
        coordinator = DistributedTransactionCoordinator(
            pool_manager=pool_manager,
            max_compensation_retries=2,
            enable_logging=False
        )
        
        async def step1_action():
            return "step1"
        
        async def step1_compensation():
            raise Exception("补偿始终失败")
        
        steps = [
            SagaStep(name="步骤1", action=step1_action, compensation=step1_compensation, status=SagaStepStatus.COMPLETED),
        ]
        
        saga_id = coordinator.generate_saga_id()
        result = await coordinator.compensate(saga_id, steps)
        
        # 验证补偿失败
        assert result is False
        assert steps[0].status == SagaStepStatus.COMPENSATION_FAILED


class TestSagaTransactionLogging:
    """
    测试 Saga 事务日志记录
    
    验证：需求 4.5
    """
    
    @pytest.mark.asyncio
    async def test_transaction_logging_enabled(self):
        """测试启用事务日志记录"""
        pool_manager = MockPoolManager()
        coordinator = DistributedTransactionCoordinator(
            pool_manager=pool_manager,
            enable_logging=True
        )
        
        async def step1_action():
            return "result"
        
        async def step1_compensation():
            pass
        
        steps = [
            SagaStep(name="步骤1", action=step1_action, compensation=step1_compensation),
        ]
        
        saga_id = coordinator.generate_saga_id()
        await coordinator.execute_saga(saga_id, steps)
        
        # 验证事务已记录
        assert saga_id in pool_manager._transactions
    
    @pytest.mark.asyncio
    async def test_log_transaction_method(self):
        """测试日志记录方法"""
        pool_manager = MockPoolManager()
        coordinator = DistributedTransactionCoordinator(
            pool_manager=pool_manager,
            enable_logging=True
        )
        
        async def action():
            pass
        
        async def compensation():
            pass
        
        steps = [
            SagaStep(name="步骤1", action=action, compensation=compensation),
        ]
        
        saga_id = coordinator.generate_saga_id()
        started_at = datetime.now(timezone.utc)
        
        await coordinator.log_transaction(
            saga_id=saga_id,
            steps=steps,
            final_status=SagaTransactionStatus.COMPLETED,
            started_at=started_at
        )
        
        # 验证日志已记录
        assert saga_id in pool_manager._transactions


class TestPartialStateCleanup:
    """
    测试部分状态清理
    
    验证：需求 4.3
    """
    
    @pytest.mark.asyncio
    async def test_cleanup_partial_state(self):
        """测试清理部分写入状态
        
        验证：需求 4.3
        """
        pool_manager = MockPoolManager()
        coordinator = DistributedTransactionCoordinator(
            pool_manager=pool_manager,
            enable_logging=False
        )
        
        cleanup_executed = []
        
        async def cleanup1():
            cleanup_executed.append("cleanup1")
        
        async def cleanup2():
            cleanup_executed.append("cleanup2")
        
        saga_id = coordinator.generate_saga_id()
        result = await coordinator.cleanup_partial_state(
            saga_id=saga_id,
            cleanup_actions=[cleanup1, cleanup2]
        )
        
        # 验证清理成功
        assert result is True
        assert cleanup_executed == ["cleanup1", "cleanup2"]
    
    @pytest.mark.asyncio
    async def test_cleanup_partial_state_with_failure(self):
        """测试清理部分状态时部分失败"""
        pool_manager = MockPoolManager()
        coordinator = DistributedTransactionCoordinator(
            pool_manager=pool_manager,
            enable_logging=False
        )
        
        async def cleanup_success():
            pass
        
        async def cleanup_fail():
            raise Exception("清理失败")
        
        saga_id = coordinator.generate_saga_id()
        result = await coordinator.cleanup_partial_state(
            saga_id=saga_id,
            cleanup_actions=[cleanup_success, cleanup_fail]
        )
        
        # 验证清理部分失败
        assert result is False


class TestReviewOverrideSaga:
    """
    测试审核覆盖事务
    
    验证：需求 4.4
    """
    
    @pytest.mark.asyncio
    async def test_review_override_saga_success(self):
        """测试审核覆盖事务成功执行
        
        验证：需求 4.4
        """
        pool_manager = MockPoolManager()
        coordinator = DistributedTransactionCoordinator(
            pool_manager=pool_manager,
            enable_logging=False
        )
        
        # 设置原始数据
        pool_manager._pg_data["row"] = {
            "score": 70.0,
            "reviewed": False,
            "reviewer_id": None,
            "review_reason": None
        }
        
        builder = ReviewOverrideSagaBuilder(
            coordinator=coordinator,
            pool_manager=pool_manager
        )
        
        notify_called = False
        
        async def notify_callback():
            nonlocal notify_called
            notify_called = True
        
        # 创建模拟缓存服务
        mock_cache = MagicMock()
        mock_cache.invalidate_with_notification = AsyncMock(return_value=1)
        
        result = await builder.execute_review_override(
            submission_id="sub_001",
            question_id="q1",
            new_score=85.0,
            reviewer_id="reviewer_001",
            reason="答案部分正确",
            notify_callback=notify_callback,
            cache_service=mock_cache
        )
        
        # 验证执行成功
        assert result is True
        assert notify_called is True
        
        # 验证缓存失效被调用
        mock_cache.invalidate_with_notification.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_review_override_saga_without_optional_callbacks(self):
        """测试没有可选回调的审核覆盖事务"""
        pool_manager = MockPoolManager()
        coordinator = DistributedTransactionCoordinator(
            pool_manager=pool_manager,
            enable_logging=False
        )
        
        pool_manager._pg_data["row"] = {
            "score": 60.0,
            "reviewed": False,
            "reviewer_id": None,
            "review_reason": None
        }
        
        builder = ReviewOverrideSagaBuilder(
            coordinator=coordinator,
            pool_manager=pool_manager
        )
        
        result = await builder.execute_review_override(
            submission_id="sub_002",
            question_id="q2",
            new_score=75.0,
            reviewer_id="reviewer_002",
            reason="重新评估"
        )
        
        # 验证执行成功
        assert result is True


class TestSagaIdGeneration:
    """测试 Saga ID 生成"""
    
    def test_generate_unique_saga_ids(self):
        """测试生成唯一的 Saga ID"""
        pool_manager = MockPoolManager()
        coordinator = DistributedTransactionCoordinator(
            pool_manager=pool_manager,
            enable_logging=False
        )
        
        ids = set()
        for _ in range(100):
            saga_id = coordinator.generate_saga_id()
            ids.add(saga_id)
        
        # 验证所有 ID 都是唯一的
        assert len(ids) == 100
    
    def test_saga_id_format(self):
        """测试 Saga ID 格式"""
        pool_manager = MockPoolManager()
        coordinator = DistributedTransactionCoordinator(
            pool_manager=pool_manager,
            enable_logging=False
        )
        
        saga_id = coordinator.generate_saga_id()
        
        # 验证是有效的 UUID 格式
        assert len(saga_id) == 36
        assert saga_id.count("-") == 4


class TestSagaStepStatusTransitions:
    """测试 Saga 步骤状态转换"""
    
    @pytest.mark.asyncio
    async def test_step_status_transitions_on_success(self):
        """测试成功执行时的状态转换"""
        pool_manager = MockPoolManager()
        coordinator = DistributedTransactionCoordinator(
            pool_manager=pool_manager,
            enable_logging=False
        )
        
        async def action():
            return "result"
        
        async def compensation():
            pass
        
        step = SagaStep(name="测试", action=action, compensation=compensation)
        
        # 初始状态
        assert step.status == SagaStepStatus.PENDING
        
        steps = [step]
        saga_id = coordinator.generate_saga_id()
        await coordinator.execute_saga(saga_id, steps)
        
        # 最终状态
        assert step.status == SagaStepStatus.COMPLETED
        assert step.started_at is not None
        assert step.completed_at is not None
    
    @pytest.mark.asyncio
    async def test_step_status_transitions_on_failure(self):
        """测试失败时的状态转换"""
        pool_manager = MockPoolManager()
        coordinator = DistributedTransactionCoordinator(
            pool_manager=pool_manager,
            enable_logging=False
        )
        
        async def action():
            raise Exception("执行失败")
        
        async def compensation():
            pass
        
        step = SagaStep(name="测试", action=action, compensation=compensation)
        
        steps = [step]
        saga_id = coordinator.generate_saga_id()
        await coordinator.execute_saga(saga_id, steps)
        
        # 最终状态
        assert step.status == SagaStepStatus.FAILED
        assert step.error is not None
        assert "执行失败" in step.error
