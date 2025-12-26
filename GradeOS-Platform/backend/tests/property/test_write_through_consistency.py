"""
属性测试：写入同步一致性

**功能: architecture-deep-integration, 属性 5: 写入同步一致性**
**验证: 需求 3.1, 3.4**

测试 Write-Through 策略下 Redis 和 PostgreSQL 数据的一致性。
"""

import asyncio
import json
import pytest
from hypothesis import given, strategies as st, settings, Phase
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any, Dict

from src.services.multi_layer_cache import (
    MultiLayerCacheService,
    CacheConfig,
)
from src.utils.pool_manager import UnifiedPoolManager


# 配置 Hypothesis
settings.register_profile(
    "ci",
    max_examples=100,
    phases=[Phase.generate, Phase.target, Phase.shrink]
)


# 测试数据生成策略
cache_keys = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
    min_size=1,
    max_size=50
)

cache_values = st.dictionaries(
    keys=st.text(min_size=1, max_size=20),
    values=st.one_of(
        st.text(max_size=100),
        st.integers(),
        st.floats(allow_nan=False, allow_infinity=False),
        st.booleans(),
        st.none(),
    ),
    min_size=1,
    max_size=10
)


class MockRedisClient:
    """模拟 Redis 客户端"""
    
    def __init__(self):
        self._data: Dict[str, bytes] = {}
        self._ttls: Dict[str, int] = {}
        self._fail_on_write = False
        self._fail_on_read = False
    
    async def get(self, key: str) -> bytes | None:
        if self._fail_on_read:
            from redis.exceptions import ConnectionError
            raise ConnectionError("Mock Redis read failure")
        return self._data.get(key)
    
    async def setex(self, key: str, ttl: int, value: str) -> None:
        if self._fail_on_write:
            from redis.exceptions import ConnectionError
            raise ConnectionError("Mock Redis write failure")
        self._data[key] = value.encode() if isinstance(value, str) else value
        self._ttls[key] = ttl
    
    async def delete(self, *keys: str) -> int:
        count = 0
        for key in keys:
            if key in self._data:
                del self._data[key]
                count += 1
        return count
    
    async def scan(self, cursor: int, match: str, count: int):
        # 简单实现：返回所有匹配的键
        import fnmatch
        matched = [k for k in self._data.keys() if fnmatch.fnmatch(k, match)]
        return (0, matched)
    
    async def publish(self, channel: str, message: str) -> int:
        return 1
    
    async def ping(self) -> bool:
        return True
    
    def pubsub(self):
        return MockPubSub()


class MockPubSub:
    """模拟 Pub/Sub"""
    
    async def subscribe(self, channel: str) -> None:
        pass
    
    async def unsubscribe(self) -> None:
        pass
    
    async def aclose(self) -> None:
        pass
    
    async def get_message(self, ignore_subscribe_messages: bool = True, timeout: float = 1.0):
        return None


class MockPoolManager:
    """模拟连接池管理器"""
    
    def __init__(self):
        self._redis_client = MockRedisClient()
        self._pg_data: Dict[str, Any] = {}
    
    def get_redis_client(self):
        return self._redis_client


@pytest.fixture
def mock_pool_manager():
    """创建模拟连接池管理器"""
    return MockPoolManager()


@pytest.fixture
def cache_service(mock_pool_manager):
    """创建缓存服务实例"""
    config = CacheConfig(enable_pubsub=False)
    return MultiLayerCacheService(mock_pool_manager, config)


class TestWriteThroughConsistency:
    """
    **功能: architecture-deep-integration, 属性 5: 写入同步一致性**
    **验证: 需求 3.1, 3.4**
    
    测试 Write-Through 策略下 Redis 和 PostgreSQL 数据的一致性。
    """
    
    @given(key=cache_keys, value=cache_values)
    @settings(max_examples=100)
    def test_write_through_data_consistency(self, key: str, value: dict):
        """
        **功能: architecture-deep-integration, 属性 5: 写入同步一致性**
        **验证: 需求 3.1, 3.4**
        
        对于任意采用 Write-Through 策略的写入操作，
        Redis 和 PostgreSQL 中的数据应当保持一致。
        """
        async def run_test():
            # 设置
            pool_manager = MockPoolManager()
            config = CacheConfig(enable_pubsub=False)
            service = MultiLayerCacheService(pool_manager, config)
            
            # 记录写入 PostgreSQL 的数据
            pg_written_value = None
            
            async def db_write(val: Any) -> None:
                nonlocal pg_written_value
                pg_written_value = val
            
            # 执行 Write-Through 写入
            result = await service.write_through(key, value, db_write)
            
            # 验证写入成功
            assert result is True, "Write-Through 应该成功"
            
            # 验证 PostgreSQL 数据
            assert pg_written_value == value, "PostgreSQL 应该收到正确的数据"
            
            # 验证 Redis 数据
            full_key = f"{config.hot_cache_prefix}:{key}"
            redis_data = await pool_manager._redis_client.get(full_key)
            assert redis_data is not None, "Redis 应该有缓存数据"
            
            # 解析 Redis 数据并比较
            redis_value = json.loads(redis_data)
            assert redis_value == value, "Redis 和 PostgreSQL 数据应该一致"
        
        asyncio.get_event_loop().run_until_complete(run_test())
    
    @given(key=cache_keys, value=cache_values)
    @settings(max_examples=100)
    def test_write_through_compensation_on_db_failure(self, key: str, value: dict):
        """
        **功能: architecture-deep-integration, 属性 5: 写入同步一致性**
        **验证: 需求 3.1, 4.2**
        
        当数据库写入失败时，应该执行补偿操作删除已写入的 Redis 缓存。
        """
        async def run_test():
            # 设置
            pool_manager = MockPoolManager()
            config = CacheConfig(enable_pubsub=False)
            service = MultiLayerCacheService(pool_manager, config)
            
            async def db_write_fail(val: Any) -> None:
                raise Exception("Database write failed")
            
            # 执行 Write-Through 写入（预期失败）
            result = await service.write_through(key, value, db_write_fail)
            
            # 验证写入失败
            assert result is False, "Write-Through 应该失败"
            
            # 验证 Redis 缓存已被补偿删除
            full_key = f"{config.hot_cache_prefix}:{key}"
            redis_data = await pool_manager._redis_client.get(full_key)
            assert redis_data is None, "补偿操作应该删除 Redis 缓存"
        
        asyncio.get_event_loop().run_until_complete(run_test())
    
    @given(key=cache_keys, value=cache_values)
    @settings(max_examples=100)
    def test_write_through_continues_on_redis_failure(self, key: str, value: dict):
        """
        **功能: architecture-deep-integration, 属性 5: 写入同步一致性**
        **验证: 需求 3.1, 3.5**
        
        当 Redis 写入失败时，应该继续写入 PostgreSQL 并进入降级模式。
        """
        async def run_test():
            # 设置
            pool_manager = MockPoolManager()
            pool_manager._redis_client._fail_on_write = True
            config = CacheConfig(enable_pubsub=False)
            service = MultiLayerCacheService(pool_manager, config)
            
            pg_written_value = None
            
            async def db_write(val: Any) -> None:
                nonlocal pg_written_value
                pg_written_value = val
            
            # 执行 Write-Through 写入
            result = await service.write_through(key, value, db_write)
            
            # 验证写入成功（PostgreSQL 写入成功即可）
            assert result is True, "即使 Redis 失败，PostgreSQL 写入成功也应返回 True"
            
            # 验证 PostgreSQL 数据
            assert pg_written_value == value, "PostgreSQL 应该收到正确的数据"
            
            # 验证进入降级模式
            assert service.is_fallback_mode is True, "应该进入降级模式"
        
        asyncio.get_event_loop().run_until_complete(run_test())


class TestWorkflowStateSync:
    """
    测试工作流状态同步
    
    **验证: 需求 3.4**
    """
    
    @given(
        workflow_id=st.uuids().map(str),
        state=st.dictionaries(
            keys=st.text(min_size=1, max_size=20),
            values=st.one_of(st.text(max_size=50), st.integers(), st.booleans()),
            min_size=1,
            max_size=5
        )
    )
    @settings(max_examples=100)
    def test_workflow_state_sync_consistency(self, workflow_id: str, state: dict):
        """
        **功能: architecture-deep-integration, 属性 5: 写入同步一致性**
        **验证: 需求 3.4**
        
        工作流状态同步后，应该能够正确读取。
        """
        async def run_test():
            # 设置
            pool_manager = MockPoolManager()
            config = CacheConfig(enable_pubsub=False)
            service = MultiLayerCacheService(pool_manager, config)
            
            # 同步状态
            await service.sync_workflow_state(workflow_id, state)
            
            # 读取状态
            retrieved_state = await service.get_workflow_state(workflow_id)
            
            # 验证状态一致性（忽略 _synced_at 字段）
            assert retrieved_state is not None, "应该能够读取状态"
            for key, value in state.items():
                assert retrieved_state.get(key) == value, f"字段 {key} 应该一致"
        
        asyncio.get_event_loop().run_until_complete(run_test())
