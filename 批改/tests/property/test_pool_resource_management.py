"""连接池资源管理属性测试

使用 Hypothesis 验证连接池资源管理的正确性

**功能: architecture-deep-integration, 属性 15: 连接池资源管理**
**验证: 需求 8.2, 8.4**
"""

import asyncio
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck, assume
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List

from src.utils.pool_manager import (
    UnifiedPoolManager,
    PoolConfig,
    PoolError,
    ConnectionTimeoutError,
    PoolExhaustedError,
    PoolNotInitializedError,
)


# 策略定义
pool_size_strategy = st.integers(min_value=1, max_value=10)
timeout_strategy = st.floats(min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False)
connection_count_strategy = st.integers(min_value=1, max_value=5)


class TestPoolConfigProperties:
    """连接池配置属性测试
    
    **功能: architecture-deep-integration, 属性 15: 连接池资源管理**
    **验证: 需求 8.2, 8.4**
    """
    
    @given(
        pg_min_size=pool_size_strategy,
        pg_max_size=pool_size_strategy,
        redis_max_connections=pool_size_strategy,
    )
    def test_pool_config_preserves_values(
        self, pg_min_size, pg_max_size, redis_max_connections
    ):
        """
        **功能: architecture-deep-integration, 属性 15: 连接池资源管理**
        **验证: 需求 8.2, 8.4**
        
        对于任意有效的配置值，PoolConfig 应该正确保存这些值
        """
        # 确保 min <= max
        if pg_min_size > pg_max_size:
            pg_min_size, pg_max_size = pg_max_size, pg_min_size
        
        config = PoolConfig(
            pg_dsn="postgresql://test:test@localhost/test",
            pg_min_size=pg_min_size,
            pg_max_size=pg_max_size,
            redis_url="redis://localhost:6379/0",
            redis_max_connections=redis_max_connections,
        )
        
        assert config.pg_min_size == pg_min_size
        assert config.pg_max_size == pg_max_size
        assert config.redis_max_connections == redis_max_connections
    
    @given(
        timeout=timeout_strategy
    )
    def test_pool_config_timeout_values(self, timeout):
        """
        **功能: architecture-deep-integration, 属性 15: 连接池资源管理**
        **验证: 需求 8.4**
        
        对于任意有效的超时值，PoolConfig 应该正确保存
        """
        config = PoolConfig(
            pg_dsn="postgresql://test:test@localhost/test",
            pg_connection_timeout=timeout,
            redis_url="redis://localhost:6379/0",
            redis_connection_timeout=timeout,
            shutdown_timeout=timeout,
        )
        
        assert config.pg_connection_timeout == timeout
        assert config.redis_connection_timeout == timeout
        assert config.shutdown_timeout == timeout


class TestPoolManagerSingletonProperties:
    """连接池管理器单例属性测试
    
    **功能: architecture-deep-integration, 属性 15: 连接池资源管理**
    **验证: 需求 8.2, 8.4**
    """
    
    def setup_method(self):
        """每个测试前重置单例"""
        UnifiedPoolManager.reset_instance()
    
    def teardown_method(self):
        """每个测试后重置单例"""
        UnifiedPoolManager.reset_instance()
    
    @given(
        call_count=st.integers(min_value=2, max_value=10)
    )
    def test_singleton_returns_same_instance(self, call_count):
        """
        **功能: architecture-deep-integration, 属性 15: 连接池资源管理**
        **验证: 需求 8.2**
        
        对于任意次数的 get_instance_sync 调用，应该返回相同的实例
        """
        instances = [
            UnifiedPoolManager.get_instance_sync()
            for _ in range(call_count)
        ]
        
        # 所有实例应该是同一个对象
        first_instance = instances[0]
        for instance in instances[1:]:
            assert instance is first_instance
    
    @pytest.mark.asyncio
    @given(
        call_count=st.integers(min_value=2, max_value=5)
    )
    @settings(max_examples=10)
    async def test_async_singleton_returns_same_instance(self, call_count):
        """
        **功能: architecture-deep-integration, 属性 15: 连接池资源管理**
        **验证: 需求 8.2**
        
        对于任意次数的异步 get_instance 调用，应该返回相同的实例
        """
        # 重置单例
        UnifiedPoolManager.reset_instance()
        
        instances = []
        for _ in range(call_count):
            instance = await UnifiedPoolManager.get_instance()
            instances.append(instance)
        
        # 所有实例应该是同一个对象
        first_instance = instances[0]
        for instance in instances[1:]:
            assert instance is first_instance



class TestPoolManagerInitializationProperties:
    """连接池管理器初始化属性测试
    
    **功能: architecture-deep-integration, 属性 15: 连接池资源管理**
    **验证: 需求 8.2, 8.4**
    """
    
    def setup_method(self):
        """每个测试前重置单例"""
        UnifiedPoolManager.reset_instance()
    
    def teardown_method(self):
        """每个测试后重置单例"""
        UnifiedPoolManager.reset_instance()
    
    def test_uninitialized_pool_raises_error(self):
        """
        **功能: architecture-deep-integration, 属性 15: 连接池资源管理**
        **验证: 需求 8.4**
        
        未初始化的连接池应该抛出明确的错误
        """
        manager = UnifiedPoolManager.get_instance_sync()
        
        assert manager.is_initialized is False
        
        with pytest.raises(PoolNotInitializedError):
            manager._check_initialized()
    
    @pytest.mark.asyncio
    async def test_uninitialized_pg_connection_raises_error(self):
        """
        **功能: architecture-deep-integration, 属性 15: 连接池资源管理**
        **验证: 需求 8.4**
        
        未初始化时获取 PostgreSQL 连接应该抛出明确的错误
        """
        manager = await UnifiedPoolManager.get_instance()
        
        with pytest.raises(PoolNotInitializedError) as exc_info:
            async with manager.pg_connection():
                pass
        
        assert "未初始化" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_uninitialized_redis_client_raises_error(self):
        """
        **功能: architecture-deep-integration, 属性 15: 连接池资源管理**
        **验证: 需求 8.4**
        
        未初始化时获取 Redis 客户端应该抛出明确的错误
        """
        manager = await UnifiedPoolManager.get_instance()
        
        with pytest.raises(PoolNotInitializedError) as exc_info:
            manager.get_redis_client()
        
        assert "未初始化" in str(exc_info.value)


class TestPoolManagerConnectionReturnProperties:
    """连接池连接归还属性测试
    
    **功能: architecture-deep-integration, 属性 15: 连接池资源管理**
    **验证: 需求 8.2, 8.4**
    """
    
    def setup_method(self):
        """每个测试前重置单例"""
        UnifiedPoolManager.reset_instance()
    
    def teardown_method(self):
        """每个测试后重置单例"""
        UnifiedPoolManager.reset_instance()
    
    @pytest.mark.asyncio
    @given(
        operation_count=connection_count_strategy
    )
    @settings(max_examples=10)
    async def test_active_operations_tracking(self, operation_count):
        """
        **功能: architecture-deep-integration, 属性 15: 连接池资源管理**
        **验证: 需求 8.2**
        
        对于任意数量的操作，活跃操作计数应该正确跟踪
        """
        # 重置单例
        UnifiedPoolManager.reset_instance()
        
        manager = await UnifiedPoolManager.get_instance()
        
        # 初始状态应该是 0
        assert manager._active_operations == 0
        
        # 模拟跟踪操作
        for _ in range(operation_count):
            await manager._track_operation()
        
        assert manager._active_operations == operation_count
        
        # 取消跟踪
        for _ in range(operation_count):
            await manager._untrack_operation()
        
        # 最终应该回到 0
        assert manager._active_operations == 0
    
    @pytest.mark.asyncio
    async def test_operations_tracking_with_exception(self):
        """
        **功能: architecture-deep-integration, 属性 15: 连接池资源管理**
        **验证: 需求 8.2**
        
        即使操作中发生异常，活跃操作计数也应该正确减少
        """
        UnifiedPoolManager.reset_instance()
        manager = await UnifiedPoolManager.get_instance()
        
        # 模拟初始化状态
        manager._initialized = True
        manager._shutting_down = False
        
        # 创建 mock Redis 客户端
        mock_redis = AsyncMock()
        manager._redis_client = mock_redis
        
        initial_count = manager._active_operations
        
        try:
            async with manager.redis_connection():
                # 模拟操作中的异常
                raise ValueError("测试异常")
        except ValueError:
            pass
        
        # 操作计数应该回到初始值
        assert manager._active_operations == initial_count


class TestPoolManagerTimeoutProperties:
    """连接池超时属性测试
    
    **功能: architecture-deep-integration, 属性 15: 连接池资源管理**
    **验证: 需求 8.4**
    """
    
    def setup_method(self):
        """每个测试前重置单例"""
        UnifiedPoolManager.reset_instance()
    
    def teardown_method(self):
        """每个测试后重置单例"""
        UnifiedPoolManager.reset_instance()
    
    @given(
        timeout=timeout_strategy
    )
    def test_config_timeout_is_preserved(self, timeout):
        """
        **功能: architecture-deep-integration, 属性 15: 连接池资源管理**
        **验证: 需求 8.4**
        
        对于任意有效的超时配置，应该被正确保存
        """
        config = PoolConfig(
            pg_dsn="postgresql://test:test@localhost/test",
            pg_connection_timeout=timeout,
            redis_url="redis://localhost:6379/0",
            redis_connection_timeout=timeout,
        )
        
        manager = UnifiedPoolManager.get_instance_sync()
        manager._config = config
        
        assert manager.config.pg_connection_timeout == timeout
        assert manager.config.redis_connection_timeout == timeout


class TestPoolManagerHealthCheckProperties:
    """连接池健康检查属性测试
    
    **功能: architecture-deep-integration, 属性 15: 连接池资源管理**
    **验证: 需求 8.2, 8.4**
    """
    
    def setup_method(self):
        """每个测试前重置单例"""
        UnifiedPoolManager.reset_instance()
    
    def teardown_method(self):
        """每个测试后重置单例"""
        UnifiedPoolManager.reset_instance()
    
    @pytest.mark.asyncio
    async def test_health_check_returns_structured_result(self):
        """
        **功能: architecture-deep-integration, 属性 15: 连接池资源管理**
        **验证: 需求 8.2**
        
        健康检查应该返回结构化的结果
        """
        manager = await UnifiedPoolManager.get_instance()
        
        # 未初始化时的健康检查
        result = await manager.health_check()
        
        # 验证结果结构
        assert "healthy" in result
        assert "postgresql" in result
        assert "redis" in result
        assert "status" in result["postgresql"]
        assert "status" in result["redis"]
    
    @pytest.mark.asyncio
    async def test_pool_stats_returns_structured_result(self):
        """
        **功能: architecture-deep-integration, 属性 15: 连接池资源管理**
        **验证: 需求 8.2**
        
        连接池统计应该返回结构化的结果
        """
        manager = await UnifiedPoolManager.get_instance()
        
        stats = manager.get_pool_stats()
        
        # 验证结果结构
        assert "initialized" in stats
        assert "shutting_down" in stats
        assert "active_operations" in stats
        assert "postgresql" in stats
        assert "redis" in stats


class TestPoolManagerShutdownProperties:
    """连接池关闭属性测试
    
    **功能: architecture-deep-integration, 属性 15: 连接池资源管理**
    **验证: 需求 8.2, 8.4**
    """
    
    def setup_method(self):
        """每个测试前重置单例"""
        UnifiedPoolManager.reset_instance()
    
    def teardown_method(self):
        """每个测试后重置单例"""
        UnifiedPoolManager.reset_instance()
    
    @pytest.mark.asyncio
    async def test_shutdown_sets_flags_correctly(self):
        """
        **功能: architecture-deep-integration, 属性 15: 连接池资源管理**
        **验证: 需求 8.2**
        
        关闭操作应该正确设置标志
        """
        manager = await UnifiedPoolManager.get_instance()
        
        # 模拟已初始化状态
        manager._initialized = True
        
        # 执行关闭
        await manager.shutdown(timeout=1.0)
        
        # 验证状态
        assert manager._initialized is False
        assert manager._shutting_down is False
    
    @pytest.mark.asyncio
    async def test_shutdown_on_uninitialized_is_safe(self):
        """
        **功能: architecture-deep-integration, 属性 15: 连接池资源管理**
        **验证: 需求 8.2**
        
        对未初始化的连接池执行关闭应该是安全的
        """
        manager = await UnifiedPoolManager.get_instance()
        
        # 未初始化时关闭不应该抛出异常
        await manager.shutdown()
        
        assert manager._initialized is False
    
    @pytest.mark.asyncio
    async def test_shutting_down_prevents_new_connections(self):
        """
        **功能: architecture-deep-integration, 属性 15: 连接池资源管理**
        **验证: 需求 8.4**
        
        正在关闭时应该阻止新的连接请求
        """
        manager = await UnifiedPoolManager.get_instance()
        
        # 模拟正在关闭状态
        manager._initialized = True
        manager._shutting_down = True
        
        with pytest.raises(PoolError) as exc_info:
            manager._check_initialized()
        
        assert "正在关闭" in str(exc_info.value)
