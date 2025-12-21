"""流式推送服务的单元测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from src.services.streaming import StreamingService, StreamEvent, EventType


class TestStreamingService:
    """流式推送服务的单元测试"""

    @pytest.mark.asyncio
    async def test_create_stream(self):
        """测试创建流式连接"""
        # 创建 Mock Redis 客户端
        mock_redis = AsyncMock()
        mock_redis.set.return_value = True
        
        # 创建流式推送服务
        streaming_service = StreamingService(redis_client=mock_redis)
        
        # 创建流
        stream_id = await streaming_service.create_stream("task_123")
        
        # 验证
        assert stream_id == "task_123"
        mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_push_event(self):
        """测试推送事件"""
        # 创建 Mock Redis 客户端
        mock_redis = AsyncMock()
        mock_redis.rpush.return_value = 1
        mock_redis.incr.return_value = 1
        mock_redis.expire.return_value = True
        
        # 创建流式推送服务
        streaming_service = StreamingService(
            redis_client=mock_redis,
            enable_persistence=False
        )
        
        # 创建事件
        event = StreamEvent(
            event_type=EventType.PAGE_COMPLETE,
            batch_id="batch_1",
            sequence_number=0,
            data={"page_index": 0, "score": 85.0}
        )
        
        # 推送事件
        success = await streaming_service.push_event("stream_1", event)
        
        # 验证
        assert success is True
        assert mock_redis.rpush.called
        assert mock_redis.incr.called
        assert mock_redis.expire.called

    @pytest.mark.asyncio
    async def test_push_error_event(self):
        """测试推送错误事件"""
        # 创建 Mock Redis 客户端
        mock_redis = AsyncMock()
        mock_redis.get.return_value = "5"
        mock_redis.rpush.return_value = 1
        mock_redis.incr.return_value = 6
        mock_redis.expire.return_value = True
        
        # 创建流式推送服务
        streaming_service = StreamingService(
            redis_client=mock_redis,
            enable_persistence=False
        )
        
        # 推送错误事件
        success = await streaming_service.push_error_event(
            stream_id="stream_1",
            error_type="redis_error",
            error_message="Redis connection failed"
        )
        
        # 验证
        assert success is True
        assert mock_redis.rpush.called

    @pytest.mark.asyncio
    async def test_generate_retry_suggestion(self):
        """测试生成重试建议"""
        # 创建 Mock Redis 客户端
        mock_redis = AsyncMock()
        
        # 创建流式推送服务
        streaming_service = StreamingService(redis_client=mock_redis)
        
        # 测试不同错误类型的建议
        test_cases = [
            ("redis_error", "Redis connection failed", "Redis 连接失败"),
            ("database_error", "Database timeout", "数据库连接失败"),
            ("timeout_error", "Operation timeout", "操作超时"),
            ("network_error", "Network unreachable", "网络连接失败"),
            ("rate_limit_error", "Too many requests", "请求频率过高"),
            ("unknown_error", "Something went wrong", "请稍后重试")
        ]
        
        for error_type, error_message, expected_keyword in test_cases:
            suggestion = streaming_service._generate_retry_suggestion(
                error_type,
                error_message
            )
            assert expected_keyword in suggestion, \
                f"建议 '{suggestion}' 应包含关键词 '{expected_keyword}'"

    @pytest.mark.asyncio
    async def test_push_error_event_with_details(self):
        """测试推送带详情的错误事件"""
        # 创建 Mock Redis 客户端
        mock_redis = AsyncMock()
        mock_redis.get.return_value = "3"
        mock_redis.rpush.return_value = 1
        mock_redis.incr.return_value = 4
        mock_redis.expire.return_value = True
        
        # 创建流式推送服务
        streaming_service = StreamingService(
            redis_client=mock_redis,
            enable_persistence=False
        )
        
        # 推送带详情的错误事件
        error_details = {
            "batch_index": 2,
            "failed_pages": [5, 7, 9],
            "error_code": "BATCH_001"
        }
        
        success = await streaming_service.push_error_event(
            stream_id="stream_1",
            error_type="batch_processing_error",
            error_message="Batch processing failed",
            error_details=error_details
        )
        
        # 验证
        assert success is True
        assert mock_redis.rpush.called

    @pytest.mark.asyncio
    async def test_close_stream(self):
        """测试关闭流式连接"""
        # 创建 Mock Redis 客户端
        mock_redis = AsyncMock()
        mock_redis.delete.return_value = 2
        
        # 创建流式推送服务
        streaming_service = StreamingService(redis_client=mock_redis)
        
        # 关闭流
        await streaming_service.close_stream("stream_1")
        
        # 验证
        assert mock_redis.delete.called

    @pytest.mark.asyncio
    async def test_get_stream_status(self):
        """测试获取流状态"""
        # 创建 Mock Redis 客户端
        mock_redis = AsyncMock()
        mock_redis.llen.return_value = 10
        mock_redis.get.return_value = "10"
        mock_redis.ttl.return_value = 3600
        
        # 创建流式推送服务
        streaming_service = StreamingService(redis_client=mock_redis)
        
        # 获取流状态
        status = await streaming_service.get_stream_status("stream_1")
        
        # 验证
        assert status["stream_id"] == "stream_1"
        assert status["event_count"] == 10
        assert status["last_sequence"] == 10
        assert status["ttl_seconds"] == 3600
        assert status["exists"] is True
