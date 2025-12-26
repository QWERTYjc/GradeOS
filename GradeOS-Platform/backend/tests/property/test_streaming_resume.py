"""断点续传正确性的属性测试

**功能: self-evolving-grading, 属性 32: 断点续传正确性**
**验证: 需求 1.4**

属性定义：
对于任意断开重连的客户端，应从上次断点（sequence_number）继续推送未接收的事件。
"""

import pytest
import asyncio
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import AsyncMock, MagicMock, call
from datetime import datetime

from src.services.streaming import StreamingService, StreamEvent, EventType


# ============================================================================
# 策略定义
# ============================================================================

@st.composite
def event_list_strategy(draw, min_size=1, max_size=20):
    """
    生成随机的事件列表
    
    Args:
        draw: Hypothesis draw 函数
        min_size: 最小事件数量
        max_size: 最大事件数量
        
    Returns:
        StreamEvent 对象列表
    """
    num_events = draw(st.integers(min_value=min_size, max_value=max_size))
    stream_id = draw(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'N'))))
    
    events = []
    for i in range(num_events):
        event_type = draw(st.sampled_from([
            EventType.BATCH_START,
            EventType.PAGE_COMPLETE,
            EventType.BATCH_COMPLETE
        ]))
        
        event = StreamEvent(
            event_type=event_type,
            batch_id=stream_id,
            sequence_number=i,
            data={
                "page_index": i,
                "score": draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False))
            }
        )
        events.append(event)
    
    return events


# ============================================================================
# 属性测试
# ============================================================================

class TestStreamingResume:
    """断点续传正确性的属性测试"""

    @settings(max_examples=100, deadline=None)
    @given(
        events=event_list_strategy(min_size=5, max_size=20),
        disconnect_point=st.integers(min_value=1, max_value=10)
    )
    @pytest.mark.asyncio
    async def test_resume_from_sequence_number(
        self,
        events: list,
        disconnect_point: int
    ):
        """
        **功能: self-evolving-grading, 属性 32: 断点续传正确性**
        **验证: 需求 1.4**
        
        验证：从指定序列号恢复时，应该从该序列号开始返回后续所有事件。
        """
        # 确保断点在有效范围内
        assume(disconnect_point < len(events))
        
        stream_id = events[0].batch_id
        
        # 创建 Mock Redis 客户端
        mock_redis = AsyncMock()
        
        # 模拟 Redis 中存储的事件（从断点开始）
        remaining_events = events[disconnect_point:]
        
        def lindex_side_effect(key, index):
            # 计算相对索引
            relative_index = index - disconnect_point
            if 0 <= relative_index < len(remaining_events):
                return remaining_events[relative_index].model_dump_json()
            return None
        
        mock_redis.lindex.side_effect = lindex_side_effect
        mock_redis.get.return_value = str(len(events))
        
        # 创建流式推送服务（不启用持久化）
        streaming_service = StreamingService(
            redis_client=mock_redis,
            enable_persistence=False
        )
        
        # 从断点恢复
        recovered_events = []
        async for event in streaming_service.get_events(stream_id, from_sequence=disconnect_point):
            recovered_events.append(event)
            # 限制恢复数量，避免无限循环
            if len(recovered_events) >= len(remaining_events):
                break
        
        # 验证：恢复的事件数量正确
        assert len(recovered_events) == len(remaining_events), \
            f"恢复的事件数量不正确: {len(recovered_events)} != {len(remaining_events)}"
        
        # 验证：恢复的事件序列号连续且正确
        for i, event in enumerate(recovered_events):
            expected_seq = disconnect_point + i
            assert event.sequence_number == expected_seq, \
                f"序列号不正确: {event.sequence_number} != {expected_seq}"
        
        # 验证：恢复的事件内容正确
        for i, event in enumerate(recovered_events):
            original_event = remaining_events[i]
            assert event.event_type == original_event.event_type
            assert event.batch_id == original_event.batch_id
            assert event.data == original_event.data

    @settings(max_examples=100, deadline=None)
    @given(
        events=event_list_strategy(min_size=3, max_size=15)
    )
    @pytest.mark.asyncio
    async def test_resume_from_zero_returns_all_events(
        self,
        events: list
    ):
        """
        **功能: self-evolving-grading, 属性 32: 断点续传正确性**
        **验证: 需求 1.4**
        
        验证：从序列号 0 开始恢复时，应该返回所有事件。
        """
        stream_id = events[0].batch_id
        
        # 创建 Mock Redis 客户端
        mock_redis = AsyncMock()
        
        def lindex_side_effect(key, index):
            if 0 <= index < len(events):
                return events[index].model_dump_json()
            return None
        
        mock_redis.lindex.side_effect = lindex_side_effect
        mock_redis.get.return_value = str(len(events))
        
        # 创建流式推送服务
        streaming_service = StreamingService(
            redis_client=mock_redis,
            enable_persistence=False
        )
        
        # 从序列号 0 开始
        recovered_events = []
        async for event in streaming_service.get_events(stream_id, from_sequence=0):
            recovered_events.append(event)
            if len(recovered_events) >= len(events):
                break
        
        # 验证：返回所有事件
        assert len(recovered_events) == len(events), \
            f"应该返回所有事件: {len(recovered_events)} != {len(events)}"
        
        # 验证：序列号从 0 开始连续
        for i, event in enumerate(recovered_events):
            assert event.sequence_number == i, \
                f"序列号应该从 0 开始连续: {event.sequence_number} != {i}"

    @settings(max_examples=50, deadline=None)
    @given(
        events=event_list_strategy(min_size=10, max_size=20),
        first_disconnect=st.integers(min_value=2, max_value=5),
        second_disconnect=st.integers(min_value=6, max_value=10)
    )
    @pytest.mark.asyncio
    async def test_multiple_disconnects_and_resumes(
        self,
        events: list,
        first_disconnect: int,
        second_disconnect: int
    ):
        """
        **功能: self-evolving-grading, 属性 32: 断点续传正确性**
        **验证: 需求 1.4**
        
        验证：多次断开和恢复时，每次都应该从正确的序列号继续。
        """
        # 确保断点在有效范围内且有序
        assume(first_disconnect < second_disconnect)
        assume(second_disconnect < len(events))
        
        stream_id = events[0].batch_id
        
        # 创建 Mock Redis 客户端
        mock_redis = AsyncMock()
        
        def lindex_side_effect(key, index):
            if 0 <= index < len(events):
                return events[index].model_dump_json()
            return None
        
        mock_redis.lindex.side_effect = lindex_side_effect
        mock_redis.get.return_value = str(len(events))
        
        # 创建流式推送服务
        streaming_service = StreamingService(
            redis_client=mock_redis,
            enable_persistence=False
        )
        
        # 第一次连接：接收到 first_disconnect 个事件
        first_batch = []
        async for event in streaming_service.get_events(stream_id, from_sequence=0):
            first_batch.append(event)
            if len(first_batch) >= first_disconnect:
                break
        
        # 验证第一批事件
        assert len(first_batch) == first_disconnect
        assert all(event.sequence_number == i for i, event in enumerate(first_batch))
        
        # 第二次连接：从 first_disconnect 恢复，接收到 second_disconnect
        second_batch = []
        async for event in streaming_service.get_events(stream_id, from_sequence=first_disconnect):
            second_batch.append(event)
            if len(second_batch) >= (second_disconnect - first_disconnect):
                break
        
        # 验证第二批事件
        expected_count = second_disconnect - first_disconnect
        assert len(second_batch) == expected_count
        assert all(
            event.sequence_number == first_disconnect + i 
            for i, event in enumerate(second_batch)
        )
        
        # 第三次连接：从 second_disconnect 恢复，接收剩余事件
        third_batch = []
        async for event in streaming_service.get_events(stream_id, from_sequence=second_disconnect):
            third_batch.append(event)
            if len(third_batch) >= (len(events) - second_disconnect):
                break
        
        # 验证第三批事件
        expected_count = len(events) - second_disconnect
        assert len(third_batch) == expected_count
        assert all(
            event.sequence_number == second_disconnect + i 
            for i, event in enumerate(third_batch)
        )
        
        # 验证：三批事件合并后等于所有事件
        all_recovered = first_batch + second_batch + third_batch
        assert len(all_recovered) == len(events)

    @settings(max_examples=100, deadline=None)
    @given(
        events=event_list_strategy(min_size=5, max_size=15),
        resume_point=st.integers(min_value=0, max_value=10)
    )
    @pytest.mark.asyncio
    async def test_resume_preserves_event_order(
        self,
        events: list,
        resume_point: int
    ):
        """
        **功能: self-evolving-grading, 属性 32: 断点续传正确性**
        **验证: 需求 1.4**
        
        验证：断点续传不应改变事件的顺序。
        """
        # 确保恢复点在有效范围内
        assume(resume_point < len(events))
        
        stream_id = events[0].batch_id
        
        # 创建 Mock Redis 客户端
        mock_redis = AsyncMock()
        
        def lindex_side_effect(key, index):
            if 0 <= index < len(events):
                return events[index].model_dump_json()
            return None
        
        mock_redis.lindex.side_effect = lindex_side_effect
        mock_redis.get.return_value = str(len(events))
        
        # 创建流式推送服务
        streaming_service = StreamingService(
            redis_client=mock_redis,
            enable_persistence=False
        )
        
        # 从恢复点开始
        recovered_events = []
        async for event in streaming_service.get_events(stream_id, from_sequence=resume_point):
            recovered_events.append(event)
            if len(recovered_events) >= (len(events) - resume_point):
                break
        
        # 验证：事件顺序正确（序列号严格递增）
        for i in range(len(recovered_events) - 1):
            current_seq = recovered_events[i].sequence_number
            next_seq = recovered_events[i + 1].sequence_number
            assert next_seq == current_seq + 1, \
                f"事件顺序不正确: {next_seq} != {current_seq + 1}"

    @settings(max_examples=100, deadline=None)
    @given(
        events=event_list_strategy(min_size=5, max_size=15),
        resume_point=st.integers(min_value=1, max_value=10)
    )
    @pytest.mark.asyncio
    async def test_resume_does_not_duplicate_events(
        self,
        events: list,
        resume_point: int
    ):
        """
        **功能: self-evolving-grading, 属性 32: 断点续传正确性**
        **验证: 需求 1.4**
        
        验证：断点续传不应重复发送已接收的事件。
        """
        # 确保恢复点在有效范围内
        assume(resume_point < len(events))
        
        stream_id = events[0].batch_id
        
        # 创建 Mock Redis 客户端
        mock_redis = AsyncMock()
        
        def lindex_side_effect(key, index):
            if 0 <= index < len(events):
                return events[index].model_dump_json()
            return None
        
        mock_redis.lindex.side_effect = lindex_side_effect
        mock_redis.get.return_value = str(len(events))
        
        # 创建流式推送服务
        streaming_service = StreamingService(
            redis_client=mock_redis,
            enable_persistence=False
        )
        
        # 从恢复点开始
        recovered_events = []
        async for event in streaming_service.get_events(stream_id, from_sequence=resume_point):
            recovered_events.append(event)
            if len(recovered_events) >= (len(events) - resume_point):
                break
        
        # 验证：没有重复的序列号
        sequence_numbers = [event.sequence_number for event in recovered_events]
        assert len(sequence_numbers) == len(set(sequence_numbers)), \
            "存在重复的序列号"
        
        # 验证：所有序列号都 >= resume_point
        assert all(seq >= resume_point for seq in sequence_numbers), \
            f"存在序列号 < {resume_point} 的事件"

    @settings(max_examples=50, deadline=None)
    @given(
        num_events=st.integers(min_value=10, max_value=30),
        resume_point=st.integers(min_value=5, max_value=15)
    )
    @pytest.mark.asyncio
    async def test_resume_with_complete_event(
        self,
        num_events: int,
        resume_point: int
    ):
        """
        **功能: self-evolving-grading, 属性 32: 断点续传正确性**
        **验证: 需求 1.4**
        
        验证：当流中包含 COMPLETE 事件时，断点续传应正确处理。
        """
        # 确保恢复点在有效范围内
        assume(resume_point < num_events - 1)
        
        stream_id = "test_stream"
        
        # 创建事件列表，最后一个是 COMPLETE 事件
        events = []
        for i in range(num_events - 1):
            events.append(StreamEvent(
                event_type=EventType.PAGE_COMPLETE,
                batch_id=stream_id,
                sequence_number=i,
                data={"page_index": i}
            ))
        
        # 添加 COMPLETE 事件
        events.append(StreamEvent(
            event_type=EventType.COMPLETE,
            batch_id=stream_id,
            sequence_number=num_events - 1,
            data={}
        ))
        
        # 创建 Mock Redis 客户端
        mock_redis = AsyncMock()
        
        def lindex_side_effect(key, index):
            if 0 <= index < len(events):
                return events[index].model_dump_json()
            return None
        
        mock_redis.lindex.side_effect = lindex_side_effect
        mock_redis.get.return_value = str(len(events))
        
        # 创建流式推送服务
        streaming_service = StreamingService(
            redis_client=mock_redis,
            enable_persistence=False
        )
        
        # 从恢复点开始
        recovered_events = []
        async for event in streaming_service.get_events(stream_id, from_sequence=resume_point):
            recovered_events.append(event)
        
        # 验证：应该接收到从恢复点到 COMPLETE 事件的所有事件
        expected_count = num_events - resume_point
        assert len(recovered_events) == expected_count, \
            f"应该接收 {expected_count} 个事件，实际接收 {len(recovered_events)} 个"
        
        # 验证：最后一个事件是 COMPLETE
        assert recovered_events[-1].event_type == EventType.COMPLETE, \
            "最后一个事件应该是 COMPLETE"
