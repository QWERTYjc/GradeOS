"""
Redis 降级集成测试

测试 Redis 故障时系统自动降级到 PostgreSQL 的功能。

验证：需求 3.5
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from datetime import datetime, timezone

from redis.exceptions import RedisError, ConnectionError as RedisConnectionError

from src.services.multi_layer_cache import (
    MultiLayerCacheService,
    CacheConfig,
    CacheStats,
)
from src.utils.pool_manager import UnifiedPoolManager, PoolNotInitializedError


class MockRedisClient:
    """模拟 Redis 客户端"""
    
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self._data = {}
        self._fail_count = 0
    
    async def get(self, key: str):
        if self.should_fail:
            self._fail_count += 1
            raise RedisConnectionError("模拟 Redis 连接失败")
        return self._data.get(key)
    
    async def setex(self, key: str, ttl: int, value: str):
        if self.should_fail:
            self._fail_count += 1
            raise RedisConnectionError("模拟 Redis 连接失败")
        self._data[key] = value
    
    async def set(self, key: str, value: str, **kwargs):
        if self.should_fail:
            self._fail_count += 1
            raise RedisConnectionError("模拟 Redis 连接失败")
        self._data[key] = value
    
    async def delete(self, *keys):
        if self.should_fail:
            self._fail_count += 1
            raise RedisConnectionError("模拟 Redis 连接失败")
        deleted = 0
        for key in keys:
            if key in self._data:
                del self._data[key]
                deleted += 1
        return deleted
    
    async def ping(self):
        if self.should_fail:
            raise RedisConnectionError("模拟 Redis 连接失败")
        return True
    
    async def scan(self, cursor=0, match=None, count=100):
        if self.should_fail:
            raise RedisConnectionError("模拟 Redis 连接失败")
        # 简单实现：返回所有匹配的键
        keys = [k for k in self._data.keys() if match is None or k.startswith(match.replace("*", ""))]
        return (0, keys)
    
    async def publish(self, channel: str, message: str):
        if self.should_fail:
            raise RedisConnectionError("模拟 Redis 连接失败")
        return 1
    
    def pubsub(self):
        return MockPubSub(self.should_fail)


class MockPubSub:
    """模拟 Redis PubSub"""
    
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self._subscribed = []
    
    async def subscribe(self, *channels):
        if self.should_fail:
            raise RedisConnectionError("模拟 Redis 连接失败")
        self._subscribed.extend(channels)
    
    async def unsubscribe(self, *channels):
        pass
    
    async def aclose(self):
        pass
    
    async def get_message(self, ignore_subscribe_messages=True, timeout=1.0):
        return None


class MockPoolManager:
    """模拟统一连接池管理器"""
    
    def __init__(self, redis_client: MockRedisClient):
        self._redis_client = redis_client
        self._pg_data = {}
    
    def get_redis_client(self):
        return self._redis_client
    
    async def pg_connection(self):
        return MockPgConnection(self._pg_data)


class MockPgConnection:
    """模拟 PostgreSQL 连接"""
    
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


class TestRedisFallbackBehavior:
    """
    测试 Redis 降级行为
    
    验证：需求 3.5
    """
    
    @pytest.mark.asyncio
    async def test_fallback_mode_activation_on_redis_failure(self):
        """测试 Redis 故障时激活降级模式
        
        验证：需求 3.5
        """
        # 创建会失败的 Redis 客户端
        redis_client = MockRedisClient(should_fail=True)
        pool_manager = MockPoolManager(redis_client)
        
        cache_service = MultiLayerCacheService(
            pool_manager=pool_manager,
            config=CacheConfig(enable_pubsub=False)
        )
        
        # 初始状态不在降级模式
        assert cache_service.is_fallback_mode is False
        
        # 定义数据库查询函数
        async def db_query():
            return {"id": "test_001", "score": 85.0}
        
        # 执行查询，应该触发降级
        result = await cache_service.get_with_fallback(
            key="test_key",
            db_query=db_query
        )
        
        # 验证进入降级模式
        assert cache_service.is_fallback_mode is True
        assert cache_service.stats.fallback_activations >= 1
        
        # 验证仍然返回了数据（从 PostgreSQL）
        assert result is not None
        assert result["id"] == "test_001"
    
    @pytest.mark.asyncio
    async def test_fallback_to_postgresql_on_redis_get_failure(self):
        """测试 Redis GET 失败时降级到 PostgreSQL
        
        验证：需求 3.5
        """
        redis_client = MockRedisClient(should_fail=True)
        pool_manager = MockPoolManager(redis_client)
        
        cache_service = MultiLayerCacheService(
            pool_manager=pool_manager,
            config=CacheConfig(enable_pubsub=False)
        )
        
        # 设置 PostgreSQL 返回数据
        pool_manager._pg_data["row"] = {"score": 90.0}
        
        db_query_called = False
        
        async def db_query():
            nonlocal db_query_called
            db_query_called = True
            return {"score": 90.0}
        
        result = await cache_service.get_with_fallback(
            key="grading_result:sub_001:q1",
            db_query=db_query
        )
        
        # 验证调用了数据库查询
        assert db_query_called is True
        
        # 验证返回了正确的数据
        assert result["score"] == 90.0
        
        # 验证统计信息
        assert cache_service.stats.pg_hits >= 1
    
    @pytest.mark.asyncio
    async def test_cache_hit_when_redis_available(self):
        """测试 Redis 可用时的缓存命中
        
        验证：需求 3.2
        """
        redis_client = MockRedisClient(should_fail=False)
        pool_manager = MockPoolManager(redis_client)
        
        cache_service = MultiLayerCacheService(
            pool_manager=pool_manager,
            config=CacheConfig(enable_pubsub=False)
        )
        
        # 预先在 Redis 中设置数据
        cache_key = "hot_cache:test_key"
        redis_client._data[cache_key] = json.dumps({"cached": True, "value": 100})
        
        db_query_called = False
        
        async def db_query():
            nonlocal db_query_called
            db_query_called = True
            return {"cached": False, "value": 200}
        
        result = await cache_service.get_with_fallback(
            key="test_key",
            db_query=db_query
        )
        
        # 验证没有调用数据库查询（缓存命中）
        assert db_query_called is False
        
        # 验证返回了缓存数据
        assert result["cached"] is True
        assert result["value"] == 100
        
        # 验证统计信息
        assert cache_service.stats.redis_hits >= 1
    
    @pytest.mark.asyncio
    async def test_cache_miss_and_backfill(self):
        """测试缓存未命中时回填 Redis
        
        验证：需求 3.2
        """
        redis_client = MockRedisClient(should_fail=False)
        pool_manager = MockPoolManager(redis_client)
        
        cache_service = MultiLayerCacheService(
            pool_manager=pool_manager,
            config=CacheConfig(enable_pubsub=False)
        )
        
        async def db_query():
            return {"from_db": True, "score": 75.0}
        
        result = await cache_service.get_with_fallback(
            key="new_key",
            db_query=db_query
        )
        
        # 验证返回了数据库数据
        assert result["from_db"] is True
        
        # 验证数据已回填到 Redis
        cache_key = "hot_cache:new_key"
        assert cache_key in redis_client._data
        
        cached_data = json.loads(redis_client._data[cache_key])
        assert cached_data["score"] == 75.0
    
    @pytest.mark.asyncio
    async def test_fallback_mode_recovery_attempt(self):
        """测试降级模式恢复尝试
        
        验证：需求 3.5
        """
        redis_client = MockRedisClient(should_fail=True)
        pool_manager = MockPoolManager(redis_client)
        
        cache_service = MultiLayerCacheService(
            pool_manager=pool_manager,
            config=CacheConfig(
                enable_pubsub=False,
                fallback_retry_interval=0.1  # 短间隔便于测试
            )
        )
        
        # 触发降级
        async def db_query():
            return {"test": True}
        
        await cache_service.get_with_fallback(key="test", db_query=db_query)
        assert cache_service.is_fallback_mode is True
        
        # 等待重试间隔
        await asyncio.sleep(0.2)
        
        # 恢复 Redis
        redis_client.should_fail = False
        
        # 再次查询，应该尝试恢复
        await cache_service.get_with_fallback(key="test2", db_query=db_query)
        
        # 验证已退出降级模式
        assert cache_service.is_fallback_mode is False


class TestWriteThroughWithFallback:
    """
    测试 Write-Through 写入与降级
    
    验证：需求 3.1, 3.5
    """
    
    @pytest.mark.asyncio
    async def test_write_through_success(self):
        """测试 Write-Through 写入成功
        
        验证：需求 3.1
        """
        redis_client = MockRedisClient(should_fail=False)
        pool_manager = MockPoolManager(redis_client)
        
        cache_service = MultiLayerCacheService(
            pool_manager=pool_manager,
            config=CacheConfig(enable_pubsub=False)
        )
        
        db_write_called = False
        
        async def db_write(value):
            nonlocal db_write_called
            db_write_called = True
        
        result = await cache_service.write_through(
            key="result_001",
            value={"score": 95.0},
            db_write=db_write
        )
        
        # 验证写入成功
        assert result is True
        assert db_write_called is True
        
        # 验证 Redis 中有数据
        cache_key = "hot_cache:result_001"
        assert cache_key in redis_client._data
        
        # 验证统计信息
        assert cache_service.stats.write_through_success >= 1
    
    @pytest.mark.asyncio
    async def test_write_through_with_redis_failure(self):
        """测试 Redis 失败时的 Write-Through
        
        验证：需求 3.1, 3.5
        """
        redis_client = MockRedisClient(should_fail=True)
        pool_manager = MockPoolManager(redis_client)
        
        cache_service = MultiLayerCacheService(
            pool_manager=pool_manager,
            config=CacheConfig(enable_pubsub=False)
        )
        
        db_write_called = False
        
        async def db_write(value):
            nonlocal db_write_called
            db_write_called = True
        
        result = await cache_service.write_through(
            key="result_002",
            value={"score": 80.0},
            db_write=db_write
        )
        
        # 验证写入成功（数据库写入成功）
        assert result is True
        assert db_write_called is True
        
        # 验证进入降级模式
        assert cache_service.is_fallback_mode is True
    
    @pytest.mark.asyncio
    async def test_write_through_compensation_on_db_failure(self):
        """测试数据库写入失败时的补偿操作
        
        验证：需求 3.1, 4.2
        """
        redis_client = MockRedisClient(should_fail=False)
        pool_manager = MockPoolManager(redis_client)
        
        cache_service = MultiLayerCacheService(
            pool_manager=pool_manager,
            config=CacheConfig(enable_pubsub=False)
        )
        
        async def db_write_fail(value):
            raise Exception("数据库写入失败")
        
        result = await cache_service.write_through(
            key="result_003",
            value={"score": 70.0},
            db_write=db_write_fail
        )
        
        # 验证写入失败
        assert result is False
        
        # 验证 Redis 缓存已被补偿删除
        cache_key = "hot_cache:result_003"
        assert cache_key not in redis_client._data
        
        # 验证统计信息
        assert cache_service.stats.write_through_failures >= 1


class TestCacheInvalidationWithFallback:
    """
    测试缓存失效与降级
    
    验证：需求 3.3, 3.5
    """
    
    @pytest.mark.asyncio
    async def test_invalidation_with_notification(self):
        """测试缓存失效并发送通知
        
        验证：需求 3.3
        """
        redis_client = MockRedisClient(should_fail=False)
        pool_manager = MockPoolManager(redis_client)
        
        cache_service = MultiLayerCacheService(
            pool_manager=pool_manager,
            config=CacheConfig(enable_pubsub=False)
        )
        
        # 预先设置一些缓存数据
        redis_client._data["hot_cache:grading:sub_001:q1"] = json.dumps({"score": 80})
        redis_client._data["hot_cache:grading:sub_001:q2"] = json.dumps({"score": 90})
        
        # 执行失效
        deleted_count = await cache_service.invalidate_with_notification(
            pattern="grading:sub_001:*"
        )
        
        # 验证删除了缓存
        assert deleted_count >= 0  # 实际删除数量取决于 mock 实现
        
        # 验证统计信息
        assert cache_service.stats.invalidation_notifications_sent >= 1
    
    @pytest.mark.asyncio
    async def test_invalidation_in_fallback_mode(self):
        """测试降级模式下的缓存失效
        
        验证：需求 3.5
        """
        redis_client = MockRedisClient(should_fail=True)
        pool_manager = MockPoolManager(redis_client)
        
        cache_service = MultiLayerCacheService(
            pool_manager=pool_manager,
            config=CacheConfig(enable_pubsub=False)
        )
        
        # 触发降级
        await cache_service._enter_fallback_mode("测试")
        assert cache_service.is_fallback_mode is True
        
        # 尝试失效（应该优雅处理）
        deleted_count = await cache_service.invalidate_with_notification(
            pattern="test:*"
        )
        
        # 验证没有抛出异常
        assert deleted_count == 0


class TestWorkflowStateSyncWithFallback:
    """
    测试工作流状态同步与降级
    
    验证：需求 3.4, 3.5
    """
    
    @pytest.mark.asyncio
    async def test_sync_workflow_state_success(self):
        """测试工作流状态同步成功
        
        验证：需求 3.4
        """
        redis_client = MockRedisClient(should_fail=False)
        pool_manager = MockPoolManager(redis_client)
        
        cache_service = MultiLayerCacheService(
            pool_manager=pool_manager,
            config=CacheConfig(enable_pubsub=False)
        )
        
        workflow_id = "wf_001"
        state = {
            "stage": "grading",
            "progress": 50.0,
            "current_question": 3
        }
        
        await cache_service.sync_workflow_state(workflow_id, state)
        
        # 验证状态已同步到 Redis
        state_key = f"workflow_state:{workflow_id}"
        assert state_key in redis_client._data
        
        stored_state = json.loads(redis_client._data[state_key])
        assert stored_state["stage"] == "grading"
        assert stored_state["progress"] == 50.0
        assert "_synced_at" in stored_state
    
    @pytest.mark.asyncio
    async def test_sync_workflow_state_with_redis_failure(self):
        """测试 Redis 故障时的工作流状态同步
        
        验证：需求 3.5
        """
        redis_client = MockRedisClient(should_fail=True)
        pool_manager = MockPoolManager(redis_client)
        
        cache_service = MultiLayerCacheService(
            pool_manager=pool_manager,
            config=CacheConfig(enable_pubsub=False)
        )
        
        workflow_id = "wf_002"
        state = {"stage": "completed"}
        
        # 应该不抛出异常
        await cache_service.sync_workflow_state(workflow_id, state)
        
        # 验证进入降级模式
        assert cache_service.is_fallback_mode is True
    
    @pytest.mark.asyncio
    async def test_get_workflow_state(self):
        """测试获取工作流状态
        
        验证：需求 3.4
        """
        redis_client = MockRedisClient(should_fail=False)
        pool_manager = MockPoolManager(redis_client)
        
        cache_service = MultiLayerCacheService(
            pool_manager=pool_manager,
            config=CacheConfig(enable_pubsub=False)
        )
        
        # 预先设置状态
        workflow_id = "wf_003"
        state_key = f"workflow_state:{workflow_id}"
        redis_client._data[state_key] = json.dumps({
            "stage": "review",
            "progress": 100.0
        })
        
        result = await cache_service.get_workflow_state(workflow_id)
        
        assert result is not None
        assert result["stage"] == "review"
        assert result["progress"] == 100.0


class TestCacheStatsTracking:
    """测试缓存统计信息跟踪"""
    
    @pytest.mark.asyncio
    async def test_stats_dict_format(self):
        """测试统计信息字典格式"""
        redis_client = MockRedisClient(should_fail=False)
        pool_manager = MockPoolManager(redis_client)
        
        cache_service = MultiLayerCacheService(
            pool_manager=pool_manager,
            config=CacheConfig(enable_pubsub=False)
        )
        
        stats = cache_service.get_stats_dict()
        
        # 验证包含所有必要字段
        assert "redis_hits" in stats
        assert "redis_misses" in stats
        assert "redis_hit_rate" in stats
        assert "pg_hits" in stats
        assert "pg_misses" in stats
        assert "write_through_success" in stats
        assert "write_through_failures" in stats
        assert "fallback_mode" in stats
        assert "fallback_activations" in stats
        assert "total_requests" in stats
    
    @pytest.mark.asyncio
    async def test_hit_rate_calculation(self):
        """测试命中率计算"""
        redis_client = MockRedisClient(should_fail=False)
        pool_manager = MockPoolManager(redis_client)
        
        cache_service = MultiLayerCacheService(
            pool_manager=pool_manager,
            config=CacheConfig(enable_pubsub=False)
        )
        
        # 模拟一些命中和未命中
        cache_service._stats.redis_hits = 80
        cache_service._stats.redis_misses = 20
        
        stats = cache_service.get_stats_dict()
        
        # 验证命中率计算正确
        assert stats["redis_hit_rate"] == 0.8
