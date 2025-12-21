"""流式推送相关 Activities

提供流式事件推送的 Activity 实现。
"""

import logging
from typing import Dict, Any
from datetime import datetime

from temporalio import activity
import redis.asyncio as redis

from src.services.streaming import StreamingService, StreamEvent, EventType
from src.utils.pool_manager import UnifiedPoolManager


logger = logging.getLogger(__name__)


@activity.defn
async def push_stream_event_activity(input_data: Dict[str, Any]) -> bool:
    """
    推送流式事件 Activity
    
    Args:
        input_data: {
            "stream_id": str,
            "event_type": str,
            "data": Dict[str, Any],
            "sequence_number": int
        }
        
    Returns:
        是否推送成功
    """
    stream_id = input_data["stream_id"]
    event_type = input_data["event_type"]
    data = input_data["data"]
    sequence_number = input_data["sequence_number"]
    
    try:
        # 初始化服务
        pool_manager = UnifiedPoolManager()
        redis_client = await redis.from_url(
            "redis://localhost:6379",
            encoding="utf-8",
            decode_responses=False
        )
        
        streaming_service = StreamingService(
            redis_client=redis_client,
            db_pool=None,  # 在 Activity 中不启用持久化
            enable_persistence=False
        )
        
        # 创建事件对象
        event = StreamEvent(
            event_type=EventType(event_type),
            timestamp=datetime.now(),
            batch_id=stream_id,
            data=data,
            sequence_number=sequence_number
        )
        
        # 推送事件
        success = await streaming_service.push_event(stream_id, event)
        
        # 清理资源
        await redis_client.close()
        
        return success
        
    except Exception as e:
        logger.error(f"推送流式事件失败: {e}")
        return False


@activity.defn
async def create_stream_activity(stream_id: str) -> str:
    """
    创建流式连接 Activity
    
    Args:
        stream_id: 流 ID
        
    Returns:
        创建的流 ID
    """
    try:
        # 初始化服务
        redis_client = await redis.from_url(
            "redis://localhost:6379",
            encoding="utf-8",
            decode_responses=False
        )
        
        streaming_service = StreamingService(redis_client=redis_client)
        
        # 创建流
        created_stream_id = await streaming_service.create_stream(stream_id)
        
        # 清理资源
        await redis_client.close()
        
        return created_stream_id
        
    except Exception as e:
        logger.error(f"创建流式连接失败: {e}")
        raise
