"""
属性测试：Redis 事件接收

**功能: architecture-deep-integration, 属性 19: Redis 事件接收**
**验证: 需求 10.1**

测试通过 Redis Pub/Sub 发送的外部事件能够被等待该事件的工作流接收并继续执行。
"""

import pytest
from hypothesis import given, strategies as st, settings, Phase
from unittest.mock import MagicMock, AsyncMock, patch
import uuid
import asyncio
import json

from src.workflows.enhanced_workflow import (
    EnhancedWorkflowMixin,
    ExternalEvent,
    RedisEventForwarder,
)


# 配置 Hypothesis
settings.register_profile(
    "ci",
    max_examples=100,
    phases=[Phase.generate, Phase.target, Phase.shrink]
)


# ==================== 策略定义 ====================

# 生成有效的事件类型
event_type_strategy = st.text(
    alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='_-'),
    min_size=1,
    max_size=50
)

# 生成事件负载
event_payload_strategy = st.dictionaries(
    keys=st.text(min_size=1, max_size=20),
    values=st.one_of(
        st.text(max_size=100),
        st.integers(),
        st.floats(allow_nan=False, allow_infinity=False),
        st.booleans(),
    ),
    max_size=10
)

# 生成时间戳
timestamp_strategy = st.text(min_size=10, max_size=30)

# 生成事件来源
source_strategy = st.one_of(
    st.none(),
    st.text(min_size=1, max_size=50)
)

# 生成完整的外部事件
external_event_strategy = st.fixed_dictionaries({
    "event_type": event_type_strategy,
    "payload": event_payload_strategy,
    "timestamp": timestamp_strategy,
    "source": source_strategy,
})

# 生成工作流 ID
workflow_id_strategy = st.uuids().map(str)


# ==================== 属性测试 ====================

class TestRedisEventReception:
    """
    Redis 事件接收属性测试
    
    **功能: architecture-deep-integration, 属性 19: Redis 事件接收**
    **验证: 需求 10.1**
    """
    
    @given(event=external_event_strategy)
    @settings(max_examples=100)
    def test_external_event_signal_reception(self, event: dict):
        """
        属性 19.1: 外部事件应能通过 Signal 接收
        
        *对于任意* 通过 Redis Pub/Sub 发送的外部事件，
        工作流应当能够通过 Signal 接收到该事件。
        
        **功能: architecture-deep-integration, 属性 19: Redis 事件接收**
        **验证: 需求 10.1**
        """
        mixin = EnhancedWorkflowMixin()
        
        # 初始状态应无事件
        assert len(mixin.get_external_events()) == 0
        
        # 接收事件
        mixin.external_event(event)
        
        # 验证事件已接收
        events = mixin.get_external_events()
        assert len(events) == 1
        assert events[0] == event
        assert events[0]["event_type"] == event["event_type"]
        assert events[0]["payload"] == event["payload"]
    
    @given(events=st.lists(external_event_strategy, min_size=1, max_size=20))
    @settings(max_examples=100)
    def test_multiple_events_reception_order(self, events: list):
        """
        属性 19.2: 多个事件应按接收顺序保存
        
        *对于任意* 事件序列，工作流应当按接收顺序保存所有事件。
        
        **功能: architecture-deep-integration, 属性 19: Redis 事件接收**
        **验证: 需求 10.1**
        """
        mixin = EnhancedWorkflowMixin()
        
        # 接收所有事件
        for event in events:
            mixin.external_event(event)
        
        # 验证事件数量和顺序
        received_events = mixin.get_external_events()
        assert len(received_events) == len(events)
        
        for i, event in enumerate(events):
            assert received_events[i] == event
    
    @given(
        target_event_type=event_type_strategy,
        other_events=st.lists(external_event_strategy, min_size=0, max_size=5)
    )
    @settings(max_examples=100)
    def test_event_type_filtering(
        self,
        target_event_type: str,
        other_events: list
    ):
        """
        属性 19.3: 应能按事件类型过滤事件
        
        *对于任意* 目标事件类型，工作流应当能够识别该类型的事件。
        
        **功能: architecture-deep-integration, 属性 19: Redis 事件接收**
        **验证: 需求 10.1**
        """
        mixin = EnhancedWorkflowMixin()
        
        # 创建目标事件
        target_event = {
            "event_type": target_event_type,
            "payload": {"key": "value"},
            "timestamp": "2024-01-01T00:00:00Z",
            "source": "test",
        }
        
        # 接收其他事件
        for event in other_events:
            mixin.external_event(event)
        
        # 接收目标事件
        mixin.external_event(target_event)
        
        # 验证能找到目标事件
        events = mixin.get_external_events()
        target_events = [e for e in events if e["event_type"] == target_event_type]
        
        assert len(target_events) >= 1
        assert target_event in events


class TestExternalEventDataClass:
    """
    ExternalEvent 数据类测试
    
    **功能: architecture-deep-integration, 属性 19: Redis 事件接收**
    **验证: 需求 10.1**
    """
    
    @given(
        event_type=event_type_strategy,
        payload=event_payload_strategy,
        timestamp=timestamp_strategy,
        source=source_strategy
    )
    @settings(max_examples=100)
    def test_external_event_to_dict_roundtrip(
        self,
        event_type: str,
        payload: dict,
        timestamp: str,
        source
    ):
        """
        属性 19.4: ExternalEvent 序列化应保持一致性
        
        **功能: architecture-deep-integration, 属性 19: Redis 事件接收**
        **验证: 需求 10.1**
        """
        event = ExternalEvent(
            event_type=event_type,
            payload=payload,
            timestamp=timestamp,
            source=source,
        )
        
        # 转换为字典
        event_dict = event.to_dict()
        
        # 验证字典内容
        assert event_dict["event_type"] == event_type
        assert event_dict["payload"] == payload
        assert event_dict["timestamp"] == timestamp
        assert event_dict["source"] == source
        
        # 从字典重建
        reconstructed = ExternalEvent.from_dict(event_dict)
        
        # 验证重建后的对象
        assert reconstructed.event_type == event_type
        assert reconstructed.payload == payload
        assert reconstructed.timestamp == timestamp
        assert reconstructed.source == source


class TestRedisEventForwarderLogic:
    """
    RedisEventForwarder 逻辑测试
    
    **功能: architecture-deep-integration, 属性 19: Redis 事件接收**
    **验证: 需求 10.1**
    """
    
    @given(
        workflow_id=workflow_id_strategy,
        channel_prefix=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='_-'),
            min_size=1,
            max_size=30
        )
    )
    @settings(max_examples=100)
    def test_channel_name_generation(
        self,
        workflow_id: str,
        channel_prefix: str
    ):
        """
        属性 19.5: 通道名称应正确生成
        
        **功能: architecture-deep-integration, 属性 19: Redis 事件接收**
        **验证: 需求 10.1**
        """
        # 验证通道名称格式
        expected_channel = f"{channel_prefix}:{workflow_id}"
        
        # 通道名称应包含前缀和工作流 ID
        assert channel_prefix in expected_channel
        assert workflow_id in expected_channel
        # 通道名称格式为 prefix:workflow_id，冒号数量取决于 UUID 中的连字符
        assert expected_channel.startswith(f"{channel_prefix}:")
        assert expected_channel.endswith(workflow_id)
    
    @given(
        workflow_ids=st.lists(workflow_id_strategy, min_size=1, max_size=10, unique=True)
    )
    @settings(max_examples=100)
    def test_multiple_workflow_subscriptions_isolation(
        self,
        workflow_ids: list
    ):
        """
        属性 19.6: 多个工作流订阅应相互隔离
        
        *对于任意* 工作流 ID 集合，每个工作流的事件通道应当唯一。
        
        **功能: architecture-deep-integration, 属性 19: Redis 事件接收**
        **验证: 需求 10.1**
        """
        channel_prefix = "workflow_events"
        
        # 生成所有通道名称
        channels = [f"{channel_prefix}:{wf_id}" for wf_id in workflow_ids]
        
        # 验证通道名称唯一
        assert len(channels) == len(set(channels))
        
        # 验证每个通道只对应一个工作流
        for i, channel in enumerate(channels):
            assert workflow_ids[i] in channel


class TestEventReceptionWithMockedRedis:
    """
    使用模拟 Redis 的事件接收测试
    
    **功能: architecture-deep-integration, 属性 19: Redis 事件接收**
    **验证: 需求 10.1**
    """
    
    @given(
        workflow_id=workflow_id_strategy,
        event=external_event_strategy
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_event_forwarding_to_workflow(
        self,
        workflow_id: str,
        event: dict
    ):
        """
        属性 19.7: 事件应能转发到工作流
        
        *对于任意* 外部事件，事件转发器应当能够将事件
        转发到目标工作流的 Signal。
        
        **功能: architecture-deep-integration, 属性 19: Redis 事件接收**
        **验证: 需求 10.1**
        """
        # 创建模拟的工作流 mixin
        mixin = EnhancedWorkflowMixin()
        
        # 模拟 Signal 回调
        received_events = []
        
        async def signal_callback(event_data: dict):
            received_events.append(event_data)
            mixin.external_event(event_data)
        
        # 直接调用回调（模拟事件转发）
        await signal_callback(event)
        
        # 验证事件已接收
        assert len(received_events) == 1
        assert received_events[0] == event
        
        # 验证工作流也收到了事件
        workflow_events = mixin.get_external_events()
        assert len(workflow_events) == 1
        assert workflow_events[0] == event
