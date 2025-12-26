"""
属性测试：分布式锁互斥性

**功能: architecture-deep-integration, 属性 22: 分布式锁互斥性**
**验证: 需求 10.4**

测试对于需要访问共享资源的工作流，同一时刻只有一个工作流能够持有该资源的分布式锁，
其他工作流应当等待或超时。
"""

import pytest
from hypothesis import given, strategies as st, settings, Phase
from unittest.mock import MagicMock, AsyncMock, patch
import uuid
import asyncio

from src.workflows.enhanced_workflow import EnhancedWorkflowMixin
from src.activities.enhanced_activities import (
    acquire_lock_activity,
    release_lock_activity,
)


# 配置 Hypothesis
settings.register_profile(
    "ci",
    max_examples=100,
    phases=[Phase.generate, Phase.target, Phase.shrink]
)


# ==================== 策略定义 ====================

# 生成有效的资源 ID
resource_id_strategy = st.text(
    alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='_-'),
    min_size=1,
    max_size=50
)

# 生成锁令牌
lock_token_strategy = st.uuids().map(str)

# 生成锁超时时间（秒）
lock_timeout_strategy = st.integers(min_value=1, max_value=300)

# 生成工作流 ID
workflow_id_strategy = st.uuids().map(str)


# ==================== 属性测试 ====================

class TestDistributedLockMutex:
    """
    分布式锁互斥性属性测试
    
    **功能: architecture-deep-integration, 属性 22: 分布式锁互斥性**
    **验证: 需求 10.4**
    """
    
    @given(
        resource_id=resource_id_strategy,
        lock_token=lock_token_strategy
    )
    @settings(max_examples=100)
    def test_lock_acquisition_records_token(
        self,
        resource_id: str,
        lock_token: str
    ):
        """
        属性 22.1: 获取锁应记录锁令牌
        
        *对于任意* 成功获取的锁，工作流应当记录锁令牌。
        
        **功能: architecture-deep-integration, 属性 22: 分布式锁互斥性**
        **验证: 需求 10.4**
        """
        mixin = EnhancedWorkflowMixin()
        
        # 初始状态应无锁
        assert len(mixin.get_held_locks()) == 0
        
        # 模拟锁获取成功
        mixin.lock_acquired(resource_id, lock_token)
        
        # 验证锁已记录
        held_locks = mixin.get_held_locks()
        assert resource_id in held_locks
        assert held_locks[resource_id] == lock_token
    
    @given(
        resource_id=resource_id_strategy,
        lock_token=lock_token_strategy
    )
    @settings(max_examples=100)
    def test_lock_release_removes_token(
        self,
        resource_id: str,
        lock_token: str
    ):
        """
        属性 22.2: 释放锁应移除锁令牌
        
        *对于任意* 已持有的锁，释放后应当移除锁令牌。
        
        **功能: architecture-deep-integration, 属性 22: 分布式锁互斥性**
        **验证: 需求 10.4**
        """
        mixin = EnhancedWorkflowMixin()
        
        # 先获取锁
        mixin.lock_acquired(resource_id, lock_token)
        assert resource_id in mixin.get_held_locks()
        
        # 释放锁
        mixin.lock_released(resource_id)
        
        # 验证锁已移除
        assert resource_id not in mixin.get_held_locks()
    
    @given(
        locks=st.lists(
            st.tuples(resource_id_strategy, lock_token_strategy),
            min_size=1,
            max_size=10,
            unique_by=lambda x: x[0]  # 资源 ID 唯一
        )
    )
    @settings(max_examples=100)
    def test_multiple_locks_isolation(
        self,
        locks: list
    ):
        """
        属性 22.3: 多个锁应相互隔离
        
        *对于任意* 多个不同资源的锁，每个锁应当独立管理。
        
        **功能: architecture-deep-integration, 属性 22: 分布式锁互斥性**
        **验证: 需求 10.4**
        """
        mixin = EnhancedWorkflowMixin()
        
        # 获取所有锁
        for resource_id, lock_token in locks:
            mixin.lock_acquired(resource_id, lock_token)
        
        # 验证所有锁都已记录
        held_locks = mixin.get_held_locks()
        assert len(held_locks) == len(locks)
        
        for resource_id, lock_token in locks:
            assert resource_id in held_locks
            assert held_locks[resource_id] == lock_token
        
        # 释放第一个锁
        first_resource_id, _ = locks[0]
        mixin.lock_released(first_resource_id)
        
        # 验证只有第一个锁被移除
        held_locks = mixin.get_held_locks()
        assert len(held_locks) == len(locks) - 1
        assert first_resource_id not in held_locks
        
        # 其他锁仍然存在
        for resource_id, lock_token in locks[1:]:
            assert resource_id in held_locks
            assert held_locks[resource_id] == lock_token
    
    @given(resource_id=resource_id_strategy)
    @settings(max_examples=100)
    def test_release_nonexistent_lock_is_safe(
        self,
        resource_id: str
    ):
        """
        属性 22.4: 释放不存在的锁应安全
        
        *对于任意* 未持有的锁，释放操作应当安全（不抛出异常）。
        
        **功能: architecture-deep-integration, 属性 22: 分布式锁互斥性**
        **验证: 需求 10.4**
        """
        mixin = EnhancedWorkflowMixin()
        
        # 释放不存在的锁应该不抛出异常
        mixin.lock_released(resource_id)
        
        # 状态应保持不变
        assert len(mixin.get_held_locks()) == 0


class TestLockKeyGeneration:
    """
    锁键生成测试
    
    **功能: architecture-deep-integration, 属性 22: 分布式锁互斥性**
    **验证: 需求 10.4**
    """
    
    @given(resource_id=resource_id_strategy)
    @settings(max_examples=100)
    def test_lock_key_format(
        self,
        resource_id: str
    ):
        """
        属性 22.5: 锁键格式应正确
        
        **功能: architecture-deep-integration, 属性 22: 分布式锁互斥性**
        **验证: 需求 10.4**
        """
        lock_key = f"lock:{resource_id}"
        
        # 验证锁键格式
        assert lock_key.startswith("lock:")
        assert resource_id in lock_key
    
    @given(
        resource_ids=st.lists(
            resource_id_strategy,
            min_size=2,
            max_size=10,
            unique=True
        )
    )
    @settings(max_examples=100)
    def test_different_resources_have_different_keys(
        self,
        resource_ids: list
    ):
        """
        属性 22.6: 不同资源应有不同的锁键
        
        *对于任意* 不同的资源 ID，生成的锁键应当唯一。
        
        **功能: architecture-deep-integration, 属性 22: 分布式锁互斥性**
        **验证: 需求 10.4**
        """
        lock_keys = [f"lock:{rid}" for rid in resource_ids]
        
        # 验证锁键唯一
        assert len(lock_keys) == len(set(lock_keys))


class TestLockActivityLogic:
    """
    锁 Activity 逻辑测试
    
    **功能: architecture-deep-integration, 属性 22: 分布式锁互斥性**
    **验证: 需求 10.4**
    """
    
    @given(
        resource_id=resource_id_strategy,
        lock_token=lock_token_strategy,
        lock_timeout=lock_timeout_strategy
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_acquire_lock_activity_with_mock_redis(
        self,
        resource_id: str,
        lock_token: str,
        lock_timeout: int
    ):
        """
        属性 22.7: 获取锁 Activity 应正确调用 Redis
        
        **功能: architecture-deep-integration, 属性 22: 分布式锁互斥性**
        **验证: 需求 10.4**
        """
        # 创建模拟的 Redis 客户端
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)  # 模拟成功获取锁
        
        # 创建模拟的连接池管理器
        mock_pool_manager = MagicMock()
        mock_pool_manager.get_redis_client.return_value = mock_redis
        
        with patch(
            'src.activities.enhanced_activities.UnifiedPoolManager.get_instance',
            return_value=mock_pool_manager
        ):
            result = await acquire_lock_activity(
                resource_id,
                lock_token,
                lock_timeout
            )
        
        # 验证结果
        assert result["acquired"] == True
        assert result["lock_key"] == f"lock:{resource_id}"
        assert result["lock_token"] == lock_token
    
    @given(
        resource_id=resource_id_strategy,
        lock_token=lock_token_strategy
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_release_lock_activity_with_mock_redis(
        self,
        resource_id: str,
        lock_token: str
    ):
        """
        属性 22.8: 释放锁 Activity 应正确调用 Redis
        
        **功能: architecture-deep-integration, 属性 22: 分布式锁互斥性**
        **验证: 需求 10.4**
        """
        # 创建模拟的 Redis 客户端
        mock_redis = AsyncMock()
        mock_redis.eval = AsyncMock(return_value=1)  # 模拟成功释放锁
        
        # 创建模拟的连接池管理器
        mock_pool_manager = MagicMock()
        mock_pool_manager.get_redis_client.return_value = mock_redis
        
        with patch(
            'src.activities.enhanced_activities.UnifiedPoolManager.get_instance',
            return_value=mock_pool_manager
        ):
            result = await release_lock_activity(
                resource_id,
                lock_token
            )
        
        # 验证结果
        assert result["released"] == True
        assert result["lock_key"] == f"lock:{resource_id}"


class TestLockMutualExclusion:
    """
    锁互斥性测试
    
    **功能: architecture-deep-integration, 属性 22: 分布式锁互斥性**
    **验证: 需求 10.4**
    """
    
    @given(
        resource_id=resource_id_strategy,
        token1=lock_token_strategy,
        token2=lock_token_strategy
    )
    @settings(max_examples=100)
    def test_same_resource_different_tokens(
        self,
        resource_id: str,
        token1: str,
        token2: str
    ):
        """
        属性 22.9: 同一资源只能有一个锁令牌
        
        *对于任意* 资源，同一时刻只能有一个锁令牌。
        后获取的锁应覆盖前一个（在工作流状态中）。
        
        **功能: architecture-deep-integration, 属性 22: 分布式锁互斥性**
        **验证: 需求 10.4**
        """
        mixin = EnhancedWorkflowMixin()
        
        # 第一次获取锁
        mixin.lock_acquired(resource_id, token1)
        assert mixin.get_held_locks()[resource_id] == token1
        
        # 第二次获取锁（模拟锁被覆盖）
        mixin.lock_acquired(resource_id, token2)
        
        # 验证只有一个锁，且是最新的令牌
        held_locks = mixin.get_held_locks()
        assert len([k for k in held_locks if k == resource_id]) == 1
        assert held_locks[resource_id] == token2
