"""流式事件推送及时性的属性测试

**功能: self-evolving-grading, 属性 31: 流式事件推送及时性**
**验证: 需求 1.2**

属性定义：
对于任意页面批改完成事件，应在 500ms 内推送到客户端。
"""

import pytest
import asyncio
import time
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from src.services.streaming import StreamingService, StreamEvent, EventType


# ============================================================================
# 策略定义
# ============================================================================

@st.composite
def stream_event_strategy(draw):
    """
    生成随机的 StreamEvent 对象
    
    Args:
        draw: Hypothesis draw 函数
        
    Returns:
        StreamEvent 对象
    """
    event_type = draw(st.sampled_from(list(EventType)))
    batch_id = draw(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'N'))))
    sequence_number = draw(st.integers(min_value=0, max_value=1000))
    
    # 根据事件类型生成不同的数据
    if event_type == EventType.PAGE_COMPLETE:
        data = {
            "page_index": draw(st.integers(min_value=0, max_value=100)),
            "score": draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)),
            "confidence": draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))
        }
    elif event_type == EventType.BATCH_START:
        data = {
            "batch_index": draw(st.integers(min_value=0, max_value=100)),
            "total_pages": draw(st.integers(min_value=1, max_value=10))
        }
    elif event_type == EventType.BATCH_COMPLETE:
        data = {
            "batch_index": draw(st.integers(min_value=0, max_value=100)),
            "success_count": draw(st.integers(min_value=0, max_value=10)),
            "failure_count": draw(st.integers(min_value=0, max_value=10))
        }
    elif event_type == EventType.ERROR:
        data = {
            "error": draw(st.text(min_size=1, max_size=50)),
            "message": draw(st.text(min_size=1, max_size=200)),
            "retry_suggestion": draw(st.text(min_size=1, max_size=100))
        }
    else:
        data = {}
    
    return StreamEvent(
        event_type=event_type,
        batch_id=batch_id,
        sequence_number=sequence_number,
        data=data
    )


# ============================================================================
# 属性测试
# ============================================================================

class TestStreamingTimeliness:
    """流式事件推送及时性的属性测试"""

    @settings(max_examples=100, deadline=None)
    @given(
        stream_id=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'N'))),
        event=stream_event_strategy()
    )
    @pytest.mark.asyncio
    async def test_event_push_within_500ms(
        self,
        stream_id: str,
        event: StreamEvent
    ):
        """
        **功能: self-evolving-grading, 属性 31: 流式事件推送及时性**
        **验证: 需求 1.2**
        
        验证：事件推送操作应在 500ms 内完成。
        """
        # 确保输入有效
        assume(len(stream_id.strip()) > 0)
        
        # 创建 Mock Redis 客户端
        mock_redis = AsyncMock()
        mock_redis.rpush.return_value = 1
        mock_redis.incr.return_value = event.sequence_number + 1
        mock_redis.expire.return_value = True
        
        # 创建流式推送服务
        streaming_service = StreamingService(redis_client=mock_redis)
        
        # 记录开始时间
        start_time = time.time()
        
        # 推送事件
        success = await streaming_service.push_event(stream_id, event)
        
        # 记录结束时间
        end_time = time.time()
        
        # 计算耗时（毫秒）
        elapsed_ms = (end_time - start_time) * 1000
        
        # 验证：推送成功
        assert success is True, "事件推送应该成功"
        
        # 验证：推送在 500ms 内完成
        assert elapsed_ms < 500, \
            f"事件推送耗时 {elapsed_ms:.2f}ms，超过 500ms 阈值"
        
        # 验证：Redis 被正确调用
        assert mock_redis.rpush.called, "应该调用 rpush 方法"
        assert mock_redis.incr.called, "应该调用 incr 方法"
        assert mock_redis.expire.called, "应该调用 expire 方法"

    @settings(max_examples=50, deadline=None)
    @given(
        stream_id=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'N'))),
        events=st.lists(stream_event_strategy(), min_size=1, max_size=10)
    )
    @pytest.mark.asyncio
    async def test_multiple_events_push_timeliness(
        self,
        stream_id: str,
        events: list
    ):
        """
        **功能: self-evolving-grading, 属性 31: 流式事件推送及时性**
        **验证: 需求 1.2**
        
        验证：连续推送多个事件时，每个事件的推送都应在 500ms 内完成。
        """
        # 确保输入有效
        assume(len(stream_id.strip()) > 0)
        assume(len(events) > 0)
        
        # 创建 Mock Redis 客户端
        mock_redis = AsyncMock()
        mock_redis.rpush.return_value = 1
        mock_redis.incr.return_value = 1
        mock_redis.expire.return_value = True
        
        # 创建流式推送服务
        streaming_service = StreamingService(redis_client=mock_redis)
        
        # 推送所有事件并记录每个事件的耗时
        push_times = []
        
        for event in events:
            start_time = time.time()
            success = await streaming_service.push_event(stream_id, event)
            end_time = time.time()
            
            elapsed_ms = (end_time - start_time) * 1000
            push_times.append(elapsed_ms)
            
            # 验证：每个事件推送成功
            assert success is True, f"事件 {event.event_type} 推送应该成功"
        
        # 验证：所有事件推送都在 500ms 内完成
        for i, elapsed_ms in enumerate(push_times):
            assert elapsed_ms < 500, \
                f"第 {i+1} 个事件推送耗时 {elapsed_ms:.2f}ms，超过 500ms 阈值"
        
        # 验证：平均推送时间也应该很快（< 200ms）
        avg_time = sum(push_times) / len(push_times)
        assert avg_time < 200, \
            f"平均推送时间 {avg_time:.2f}ms 过长"

    @settings(max_examples=100, deadline=None)
    @given(
        stream_id=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'N'))),
        page_index=st.integers(min_value=0, max_value=100),
        score=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        sequence_number=st.integers(min_value=0, max_value=1000)
    )
    @pytest.mark.asyncio
    async def test_page_complete_event_push_timeliness(
        self,
        stream_id: str,
        page_index: int,
        score: float,
        confidence: float,
        sequence_number: int
    ):
        """
        **功能: self-evolving-grading, 属性 31: 流式事件推送及时性**
        **验证: 需求 1.2**
        
        验证：页面批改完成事件的推送应在 500ms 内完成。
        这是最关键的事件类型，需要特别测试。
        """
        # 确保输入有效
        assume(len(stream_id.strip()) > 0)
        
        # 创建页面完成事件
        event = StreamEvent(
            event_type=EventType.PAGE_COMPLETE,
            batch_id=stream_id,
            sequence_number=sequence_number,
            data={
                "page_index": page_index,
                "score": score,
                "confidence": confidence
            }
        )
        
        # 创建 Mock Redis 客户端
        mock_redis = AsyncMock()
        mock_redis.rpush.return_value = 1
        mock_redis.incr.return_value = sequence_number + 1
        mock_redis.expire.return_value = True
        
        # 创建流式推送服务
        streaming_service = StreamingService(redis_client=mock_redis)
        
        # 记录开始时间
        start_time = time.time()
        
        # 推送事件
        success = await streaming_service.push_event(stream_id, event)
        
        # 记录结束时间
        end_time = time.time()
        
        # 计算耗时（毫秒）
        elapsed_ms = (end_time - start_time) * 1000
        
        # 验证：推送成功
        assert success is True, "页面完成事件推送应该成功"
        
        # 验证：推送在 500ms 内完成
        assert elapsed_ms < 500, \
            f"页面完成事件推送耗时 {elapsed_ms:.2f}ms，超过 500ms 阈值"

    @settings(max_examples=100, deadline=None)
    @given(
        stream_id=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'N'))),
        event=stream_event_strategy()
    )
    @pytest.mark.asyncio
    async def test_event_push_preserves_data(
        self,
        stream_id: str,
        event: StreamEvent
    ):
        """
        **功能: self-evolving-grading, 属性 31: 流式事件推送及时性**
        **验证: 需求 1.2**
        
        验证：快速推送不应影响数据完整性。
        """
        # 确保输入有效
        assume(len(stream_id.strip()) > 0)
        
        # 创建 Mock Redis 客户端
        mock_redis = AsyncMock()
        
        # 捕获推送的数据
        pushed_data = None
        
        async def capture_rpush(key, value):
            nonlocal pushed_data
            pushed_data = value
            return 1
        
        mock_redis.rpush.side_effect = capture_rpush
        mock_redis.incr.return_value = event.sequence_number + 1
        mock_redis.expire.return_value = True
        
        # 创建流式推送服务
        streaming_service = StreamingService(redis_client=mock_redis)
        
        # 推送事件
        success = await streaming_service.push_event(stream_id, event)
        
        # 验证：推送成功
        assert success is True, "事件推送应该成功"
        
        # 验证：数据完整性
        assert pushed_data is not None, "应该捕获到推送的数据"
        
        # 反序列化并验证
        deserialized_event = StreamEvent.model_validate_json(pushed_data)
        assert deserialized_event.event_type == event.event_type
        assert deserialized_event.batch_id == event.batch_id
        assert deserialized_event.sequence_number == event.sequence_number
        assert deserialized_event.data == event.data

    @settings(max_examples=50, deadline=None)
    @given(
        stream_id=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'N'))),
        num_concurrent=st.integers(min_value=2, max_value=10)
    )
    @pytest.mark.asyncio
    async def test_concurrent_push_timeliness(
        self,
        stream_id: str,
        num_concurrent: int
    ):
        """
        **功能: self-evolving-grading, 属性 31: 流式事件推送及时性**
        **验证: 需求 1.2**
        
        验证：并发推送多个事件时，每个事件的推送仍应在 500ms 内完成。
        """
        # 确保输入有效
        assume(len(stream_id.strip()) > 0)
        
        # 创建 Mock Redis 客户端
        mock_redis = AsyncMock()
        mock_redis.rpush.return_value = 1
        mock_redis.incr.return_value = 1
        mock_redis.expire.return_value = True
        
        # 创建流式推送服务
        streaming_service = StreamingService(redis_client=mock_redis)
        
        # 创建多个事件
        events = [
            StreamEvent(
                event_type=EventType.PAGE_COMPLETE,
                batch_id=stream_id,
                sequence_number=i,
                data={"page_index": i, "score": 80.0, "confidence": 0.9}
            )
            for i in range(num_concurrent)
        ]
        
        # 记录开始时间
        start_time = time.time()
        
        # 并发推送所有事件
        results = await asyncio.gather(
            *[streaming_service.push_event(stream_id, event) for event in events]
        )
        
        # 记录结束时间
        end_time = time.time()
        
        # 计算总耗时（毫秒）
        total_elapsed_ms = (end_time - start_time) * 1000
        
        # 验证：所有推送成功
        assert all(results), "所有事件推送应该成功"
        
        # 验证：并发推送的总时间应该合理（不应该是串行时间）
        # 假设串行时间是 num_concurrent * 100ms，并发应该快得多
        max_expected_time = num_concurrent * 100  # 串行时间的估计
        assert total_elapsed_ms < max_expected_time, \
            f"并发推送 {num_concurrent} 个事件耗时 {total_elapsed_ms:.2f}ms，" \
            f"超过预期的 {max_expected_time}ms"
