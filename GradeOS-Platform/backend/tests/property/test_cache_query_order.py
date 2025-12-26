"""
属性测试：缓存查询顺序正确性

**功能: architecture-deep-integration, 属性 6: 缓存查询顺序正确性**
**验证: 需求 3.2**

测试缓存查询的顺序：先查 Redis，未命中查 PostgreSQL，结果回填 Redis。
"""

import asyncio
import json
import pytest
from hypothesis import given, strategies as st, settings, Phase
from typing import Any, Dict, Optional, List

from src.services.multi_layer_cache import (
    MultiLayerCacheService,
    CacheConfig,
)


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
    ),
    min_size=1,
    max_size=10
)


class QueryTracker:
    """查询追踪器，记录查询顺序"""
    
    def __init__(self):
        self.operations: List[str] = []
    
    def record(self, operation: str) -> None:
        self.operations.append(operation)
    
    def clear(self) -> None:
        self.operations.clear()


class MockRedisClient:
    """模拟 Redis 客户端，支持查询追踪"""
    
    def __init__(self, tracker: QueryTracker):
        self._data: Dict[str, bytes] = {}
        self._tracker = tracker
        self._fail_on_read = False
    
    async def get(self, key: str) -> bytes | None:
        self._tracker.record("redis_get")
        if self._fail_on_read:
            from redis.exceptions import ConnectionError
            raise ConnectionError("Mock Redis read failure")
        return self._data.get(key)
    
    async def setex(self, key: str, ttl: int, value: str) -> None:
        self._tracker.record("redis_setex")
        self._data[key] = value.encode() if isinstance(value, str) else value
    
    async def delete(self, *keys: str) -> int:
        count = 0
        for key in keys:
            if key in self._data:
                del self._data[key]
                count += 1
        return count
    
    async def scan(self, cursor: int, match: str, count: int):
        import fnmatch
        matched = [k for k in self._data.keys() if fnmatch.fnmatch(k, match)]
        return (0, matched)
    
    async def publish(self, channel: str, message: str) -> int:
        return 1
    
    async def ping(self) -> bool:
        return True
    
    def pubsub(self):
        return MockPubSub()
    
    def set_data(self, key: str, value: Any) -> None:
        """直接设置数据（用于测试）"""
        self._data[key] = json.dumps(value, default=str).encode()


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
    
    def __init__(self, tracker: QueryTracker):
        self._redis_client = MockRedisClient(tracker)
        self._tracker = tracker
    
    def get_redis_client(self):
        return self._redis_client


class TestCacheQueryOrder:
    """
    **功能: architecture-deep-integration, 属性 6: 缓存查询顺序正确性**
    **验证: 需求 3.2**
    
    测试缓存查询的顺序正确性。
    """
    
    @given(key=cache_keys, value=cache_values)
    @settings(max_examples=100)
    def test_redis_hit_no_pg_query(self, key: str, value: dict):
        """
        **功能: architecture-deep-integration, 属性 6: 缓存查询顺序正确性**
        **验证: 需求 3.2**
        
        当 Redis 缓存命中时，不应该查询 PostgreSQL。
        """
        async def run_test():
            # 设置
            tracker = QueryTracker()
            pool_manager = MockPoolManager(tracker)
            config = CacheConfig(enable_pubsub=False)
            service = MultiLayerCacheService(pool_manager, config)
            
            # 预先在 Redis 中设置数据
            full_key = f"{config.hot_cache_prefix}:{key}"
            pool_manager._redis_client.set_data(full_key, value)
            
            pg_queried = False
            
            async def db_query() -> Optional[dict]:
                nonlocal pg_queried
                pg_queried = True
                tracker.record("pg_query")
                return {"from": "pg"}
            
            # 执行查询
            tracker.clear()
            result = await service.get_with_fallback(key, db_query)
            
            # 验证结果来自 Redis
            assert result == value, "结果应该来自 Redis 缓存"
            
            # 验证没有查询 PostgreSQL
            assert pg_queried is False, "Redis 命中时不应该查询 PostgreSQL"
            assert "pg_query" not in tracker.operations, "不应该有 PostgreSQL 查询操作"
            
            # 验证查询顺序
            assert tracker.operations[0] == "redis_get", "应该先查询 Redis"
        
        asyncio.get_event_loop().run_until_complete(run_test())
    
    @given(key=cache_keys, value=cache_values)
    @settings(max_examples=100)
    def test_redis_miss_then_pg_query_and_backfill(self, key: str, value: dict):
        """
        **功能: architecture-deep-integration, 属性 6: 缓存查询顺序正确性**
        **验证: 需求 3.2**
        
        当 Redis 缓存未命中时，应该查询 PostgreSQL 并回填缓存。
        """
        async def run_test():
            # 设置
            tracker = QueryTracker()
            pool_manager = MockPoolManager(tracker)
            config = CacheConfig(enable_pubsub=False)
            service = MultiLayerCacheService(pool_manager, config)
            
            async def db_query() -> Optional[dict]:
                tracker.record("pg_query")
                return value
            
            # 执行查询（Redis 中没有数据）
            tracker.clear()
            result = await service.get_with_fallback(key, db_query)
            
            # 验证结果来自 PostgreSQL
            assert result == value, "结果应该来自 PostgreSQL"
            
            # 验证查询顺序：Redis -> PostgreSQL -> Redis 回填
            assert len(tracker.operations) >= 3, "应该有至少 3 个操作"
            assert tracker.operations[0] == "redis_get", "第一步应该查询 Redis"
            assert tracker.operations[1] == "pg_query", "第二步应该查询 PostgreSQL"
            assert tracker.operations[2] == "redis_setex", "第三步应该回填 Redis"
            
            # 验证回填后 Redis 中有数据
            full_key = f"{config.hot_cache_prefix}:{key}"
            cached_data = await pool_manager._redis_client.get(full_key)
            assert cached_data is not None, "回填后 Redis 应该有数据"
        
        asyncio.get_event_loop().run_until_complete(run_test())
    
    @given(key=cache_keys)
    @settings(max_examples=100)
    def test_pg_miss_no_backfill(self, key: str):
        """
        **功能: architecture-deep-integration, 属性 6: 缓存查询顺序正确性**
        **验证: 需求 3.2**
        
        当 PostgreSQL 也没有数据时，不应该回填缓存。
        """
        async def run_test():
            # 设置
            tracker = QueryTracker()
            pool_manager = MockPoolManager(tracker)
            config = CacheConfig(enable_pubsub=False)
            service = MultiLayerCacheService(pool_manager, config)
            
            async def db_query() -> Optional[dict]:
                tracker.record("pg_query")
                return None  # PostgreSQL 也没有数据
            
            # 执行查询
            tracker.clear()
            result = await service.get_with_fallback(key, db_query)
            
            # 验证结果为 None
            assert result is None, "结果应该为 None"
            
            # 验证没有回填操作
            assert "redis_setex" not in tracker.operations, "不应该有回填操作"
        
        asyncio.get_event_loop().run_until_complete(run_test())
    
    @given(key=cache_keys, value=cache_values)
    @settings(max_examples=100)
    def test_redis_failure_fallback_to_pg(self, key: str, value: dict):
        """
        **功能: architecture-deep-integration, 属性 6: 缓存查询顺序正确性**
        **验证: 需求 3.2, 3.5**
        
        当 Redis 故障时，应该降级到直接查询 PostgreSQL。
        """
        async def run_test():
            # 设置
            tracker = QueryTracker()
            pool_manager = MockPoolManager(tracker)
            pool_manager._redis_client._fail_on_read = True
            config = CacheConfig(enable_pubsub=False)
            service = MultiLayerCacheService(pool_manager, config)
            
            async def db_query() -> Optional[dict]:
                tracker.record("pg_query")
                return value
            
            # 执行查询
            tracker.clear()
            result = await service.get_with_fallback(key, db_query)
            
            # 验证结果来自 PostgreSQL
            assert result == value, "结果应该来自 PostgreSQL"
            
            # 验证进入降级模式
            assert service.is_fallback_mode is True, "应该进入降级模式"
            
            # 验证查询了 PostgreSQL
            assert "pg_query" in tracker.operations, "应该查询 PostgreSQL"
        
        asyncio.get_event_loop().run_until_complete(run_test())


class TestCacheStatistics:
    """测试缓存统计信息"""
    
    @given(key=cache_keys, value=cache_values)
    @settings(max_examples=50)
    def test_stats_update_on_hit(self, key: str, value: dict):
        """
        测试缓存命中时统计信息更新。
        """
        async def run_test():
            tracker = QueryTracker()
            pool_manager = MockPoolManager(tracker)
            config = CacheConfig(enable_pubsub=False)
            service = MultiLayerCacheService(pool_manager, config)
            
            # 预先设置缓存
            full_key = f"{config.hot_cache_prefix}:{key}"
            pool_manager._redis_client.set_data(full_key, value)
            
            initial_hits = service.stats.redis_hits
            
            async def db_query():
                return None
            
            await service.get_with_fallback(key, db_query)
            
            assert service.stats.redis_hits == initial_hits + 1, "Redis 命中计数应该增加"
        
        asyncio.get_event_loop().run_until_complete(run_test())
    
    @given(key=cache_keys, value=cache_values)
    @settings(max_examples=50)
    def test_stats_update_on_miss(self, key: str, value: dict):
        """
        测试缓存未命中时统计信息更新。
        """
        async def run_test():
            tracker = QueryTracker()
            pool_manager = MockPoolManager(tracker)
            config = CacheConfig(enable_pubsub=False)
            service = MultiLayerCacheService(pool_manager, config)
            
            initial_misses = service.stats.redis_misses
            initial_pg_hits = service.stats.pg_hits
            
            async def db_query():
                return value
            
            await service.get_with_fallback(key, db_query)
            
            assert service.stats.redis_misses == initial_misses + 1, "Redis 未命中计数应该增加"
            assert service.stats.pg_hits == initial_pg_hits + 1, "PostgreSQL 命中计数应该增加"
        
        asyncio.get_event_loop().run_until_complete(run_test())
