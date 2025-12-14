"""
属性测试：缓存失效通知传播

**功能: architecture-deep-integration, 属性 7: 缓存失效通知传播**
**验证: 需求 3.3**

测试评分细则更新时，通过 Redis Pub/Sub 通知所有 Worker 节点失效本地缓存。
"""

import asyncio
import json
import pytest
from hypothesis import given, strategies as st, settings, Phase
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

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
cache_patterns = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-*"),
    min_size=1,
    max_size=50
)

cache_keys = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
    min_size=1,
    max_size=50
)


@dataclass
class PubSubMessage:
    """Pub/Sub 消息"""
    channel: str
    message: str


class MockPubSub:
    """模拟 Pub/Sub，支持消息追踪"""
    
    def __init__(self, message_queue: asyncio.Queue):
        self._subscribed_channels: List[str] = []
        self._message_queue = message_queue
    
    async def subscribe(self, channel: str) -> None:
        self._subscribed_channels.append(channel)
    
    async def unsubscribe(self) -> None:
        self._subscribed_channels.clear()
    
    async def aclose(self) -> None:
        pass
    
    async def get_message(
        self, 
        ignore_subscribe_messages: bool = True, 
        timeout: float = 1.0
    ) -> Optional[dict]:
        try:
            msg = await asyncio.wait_for(
                self._message_queue.get(),
                timeout=timeout
            )
            return msg
        except asyncio.TimeoutError:
            return None


class MockRedisClient:
    """模拟 Redis 客户端，支持 Pub/Sub 追踪"""
    
    def __init__(self):
        self._data: Dict[str, bytes] = {}
        self._published_messages: List[PubSubMessage] = []
        self._pubsub_queues: List[asyncio.Queue] = []
    
    async def get(self, key: str) -> bytes | None:
        return self._data.get(key)
    
    async def setex(self, key: str, ttl: int, value: str) -> None:
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
        self._published_messages.append(PubSubMessage(channel, message))
        # 广播到所有订阅者
        for queue in self._pubsub_queues:
            await queue.put({
                "type": "message",
                "channel": channel,
                "data": message.encode() if isinstance(message, str) else message
            })
        return len(self._pubsub_queues)
    
    async def ping(self) -> bool:
        return True
    
    def pubsub(self) -> MockPubSub:
        queue = asyncio.Queue()
        self._pubsub_queues.append(queue)
        return MockPubSub(queue)
    
    def set_data(self, key: str, value: Any) -> None:
        """直接设置数据（用于测试）"""
        self._data[key] = json.dumps(value, default=str).encode()


class MockPoolManager:
    """模拟连接池管理器"""
    
    def __init__(self):
        self._redis_client = MockRedisClient()
    
    def get_redis_client(self):
        return self._redis_client


class TestCacheInvalidationPropagation:
    """
    **功能: architecture-deep-integration, 属性 7: 缓存失效通知传播**
    **验证: 需求 3.3**
    
    测试缓存失效通知的传播。
    """
    
    @given(pattern=cache_patterns)
    @settings(max_examples=100)
    def test_invalidation_publishes_notification(self, pattern: str):
        """
        **功能: architecture-deep-integration, 属性 7: 缓存失效通知传播**
        **验证: 需求 3.3**
        
        对于任意评分细则更新操作，系统应当通过 Redis Pub/Sub 发送失效通知。
        """
        async def run_test():
            # 设置
            pool_manager = MockPoolManager()
            config = CacheConfig(enable_pubsub=False)
            service = MultiLayerCacheService(pool_manager, config)
            
            # 执行失效操作
            await service.invalidate_with_notification(pattern)
            
            # 验证发布了通知
            messages = pool_manager._redis_client._published_messages
            assert len(messages) == 1, "应该发布一条失效通知"
            assert messages[0].channel == config.pubsub_channel, "应该发布到正确的通道"
            assert messages[0].message == pattern, "消息内容应该是失效模式"
            
            # 验证统计信息更新
            assert service.stats.invalidation_notifications_sent == 1, "发送计数应该增加"
        
        asyncio.get_event_loop().run_until_complete(run_test())
    
    @given(
        keys=st.lists(cache_keys, min_size=1, max_size=5, unique=True),
        value=st.dictionaries(
            keys=st.text(min_size=1, max_size=10),
            values=st.text(max_size=20),
            min_size=1,
            max_size=3
        )
    )
    @settings(max_examples=100)
    def test_invalidation_deletes_matching_keys(self, keys: List[str], value: dict):
        """
        **功能: architecture-deep-integration, 属性 7: 缓存失效通知传播**
        **验证: 需求 3.3**
        
        失效操作应该删除所有匹配的缓存键。
        """
        async def run_test():
            # 设置
            pool_manager = MockPoolManager()
            config = CacheConfig(enable_pubsub=False)
            service = MultiLayerCacheService(pool_manager, config)
            
            # 预先设置多个缓存键
            for key in keys:
                full_key = f"{config.hot_cache_prefix}:{key}"
                pool_manager._redis_client.set_data(full_key, value)
            
            # 使用通配符模式失效所有键
            deleted_count = await service.invalidate_with_notification("*")
            
            # 验证所有键都被删除
            assert deleted_count == len(keys), f"应该删除 {len(keys)} 个键"
            
            # 验证缓存中没有数据
            for key in keys:
                full_key = f"{config.hot_cache_prefix}:{key}"
                data = await pool_manager._redis_client.get(full_key)
                assert data is None, f"键 {key} 应该被删除"
        
        asyncio.get_event_loop().run_until_complete(run_test())
    
    @given(pattern=cache_patterns)
    @settings(max_examples=100)
    def test_callback_receives_notification(self, pattern: str):
        """
        **功能: architecture-deep-integration, 属性 7: 缓存失效通知传播**
        **验证: 需求 3.3**
        
        所有订阅的 Worker 节点应当收到通知并失效本地缓存。
        """
        async def run_test():
            # 设置
            pool_manager = MockPoolManager()
            config = CacheConfig(enable_pubsub=False)
            service = MultiLayerCacheService(pool_manager, config)
            
            # 记录收到的通知
            received_patterns: List[str] = []
            
            async def callback(p: str) -> None:
                received_patterns.append(p)
            
            # 注册回调
            service.register_invalidation_callback(callback)
            
            # 模拟收到失效消息
            await service._handle_invalidation_message(pattern.encode())
            
            # 验证回调被调用
            assert len(received_patterns) == 1, "回调应该被调用一次"
            assert received_patterns[0] == pattern, "回调应该收到正确的模式"
            
            # 验证统计信息更新
            assert service.stats.invalidation_notifications_received == 1, "接收计数应该增加"
        
        asyncio.get_event_loop().run_until_complete(run_test())
    
    @given(pattern=cache_patterns)
    @settings(max_examples=50)
    def test_multiple_callbacks_all_receive_notification(self, pattern: str):
        """
        **功能: architecture-deep-integration, 属性 7: 缓存失效通知传播**
        **验证: 需求 3.3**
        
        多个回调都应该收到失效通知。
        """
        async def run_test():
            # 设置
            pool_manager = MockPoolManager()
            config = CacheConfig(enable_pubsub=False)
            service = MultiLayerCacheService(pool_manager, config)
            
            # 记录收到的通知
            received_1: List[str] = []
            received_2: List[str] = []
            received_3: List[str] = []
            
            async def callback_1(p: str) -> None:
                received_1.append(p)
            
            async def callback_2(p: str) -> None:
                received_2.append(p)
            
            async def callback_3(p: str) -> None:
                received_3.append(p)
            
            # 注册多个回调
            service.register_invalidation_callback(callback_1)
            service.register_invalidation_callback(callback_2)
            service.register_invalidation_callback(callback_3)
            
            # 模拟收到失效消息
            await service._handle_invalidation_message(pattern.encode())
            
            # 验证所有回调都被调用
            assert len(received_1) == 1, "回调 1 应该被调用"
            assert len(received_2) == 1, "回调 2 应该被调用"
            assert len(received_3) == 1, "回调 3 应该被调用"
            assert received_1[0] == pattern, "回调 1 应该收到正确的模式"
            assert received_2[0] == pattern, "回调 2 应该收到正确的模式"
            assert received_3[0] == pattern, "回调 3 应该收到正确的模式"
        
        asyncio.get_event_loop().run_until_complete(run_test())
    
    @given(pattern=cache_patterns)
    @settings(max_examples=50)
    def test_unregister_callback_stops_notifications(self, pattern: str):
        """
        测试取消注册回调后不再收到通知。
        """
        async def run_test():
            # 设置
            pool_manager = MockPoolManager()
            config = CacheConfig(enable_pubsub=False)
            service = MultiLayerCacheService(pool_manager, config)
            
            received: List[str] = []
            
            async def callback(p: str) -> None:
                received.append(p)
            
            # 注册并取消注册回调
            service.register_invalidation_callback(callback)
            service.unregister_invalidation_callback(callback)
            
            # 模拟收到失效消息
            await service._handle_invalidation_message(pattern.encode())
            
            # 验证回调没有被调用
            assert len(received) == 0, "取消注册后回调不应该被调用"
        
        asyncio.get_event_loop().run_until_complete(run_test())
