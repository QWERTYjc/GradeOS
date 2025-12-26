"""
流式推送服务

提供基于 SSE (Server-Sent Events) 的实时批改进度推送功能。
支持断点续传、错误事件推送和 Redis 事件队列。

验证：需求 1.1, 1.2, 1.3, 1.4, 1.5
"""

import json
import logging
import asyncio
from typing import AsyncGenerator, Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field
import redis.asyncio as redis
from redis.exceptions import RedisError
from psycopg_pool import AsyncConnectionPool


logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """流式事件类型"""
    BATCH_START = "batch_start"
    PAGE_COMPLETE = "page_complete"
    BATCH_COMPLETE = "batch_complete"
    STUDENT_IDENTIFIED = "student_identified"
    ERROR = "error"
    COMPLETE = "complete"


class StreamEvent(BaseModel):
    """流式事件模型"""
    event_type: EventType = Field(..., description="事件类型")
    timestamp: datetime = Field(default_factory=datetime.now, description="事件时间戳")
    batch_id: str = Field(..., description="批次 ID")
    data: Dict[str, Any] = Field(default_factory=dict, description="事件数据")
    sequence_number: int = Field(..., description="序列号，用于断点续传")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class StreamingService:
    """
    流式推送服务
    
    通过 SSE 实时推送批改进度和结果。
    支持断点续传、错误事件推送和 Redis 事件队列。
    
    验证：需求 1.1, 1.2, 1.3, 1.4, 1.5
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        db_pool: Optional[AsyncConnectionPool] = None,
        event_ttl_seconds: int = 3600,  # 事件保留 1 小时
        enable_persistence: bool = True  # 是否启用事件持久化
    ):
        """
        初始化流式推送服务
        
        Args:
            redis_client: Redis 异步客户端实例
            db_pool: PostgreSQL 连接池（用于事件持久化）
            event_ttl_seconds: 事件在 Redis 中的保留时间（秒）
            enable_persistence: 是否启用事件持久化到数据库
        """
        self.redis_client = redis_client
        self.db_pool = db_pool
        self.event_ttl_seconds = event_ttl_seconds
        self.enable_persistence = enable_persistence and db_pool is not None
        
    def _get_stream_key(self, stream_id: str) -> str:
        """获取流的 Redis 键"""
        return f"stream:{stream_id}:events"
    
    def _get_sequence_key(self, stream_id: str) -> str:
        """获取序列号的 Redis 键"""
        return f"stream:{stream_id}:last_seq"
    
    async def create_stream(self, task_id: str) -> str:
        """
        创建流式连接
        
        Args:
            task_id: 任务 ID
            
        Returns:
            stream_id: 流 ID（与 task_id 相同）
            
        验证：需求 1.1
        """
        stream_id = task_id
        
        try:
            # 初始化序列号为 0
            await self.redis_client.set(
                self._get_sequence_key(stream_id),
                0,
                ex=self.event_ttl_seconds
            )
            
            logger.info(f"创建流式连接: stream_id={stream_id}")
            return stream_id
            
        except RedisError as e:
            logger.error(f"创建流式连接失败: {str(e)}")
            raise
    
    async def push_event(
        self,
        stream_id: str,
        event: StreamEvent
    ) -> bool:
        """
        推送事件到指定流
        
        事件会被存储到 Redis 列表中，并设置 TTL。
        如果启用持久化，事件也会被存储到 PostgreSQL。
        
        Args:
            stream_id: 流 ID
            event: 流式事件对象
            
        Returns:
            如果推送成功返回 True，失败返回 False
            
        验证：需求 1.2, 1.3, 1.4
        """
        try:
            stream_key = self._get_stream_key(stream_id)
            
            # 序列化事件
            event_json = event.model_dump_json()
            
            # 推送到 Redis 列表
            await self.redis_client.rpush(stream_key, event_json)
            
            # 更新序列号
            await self.redis_client.incr(self._get_sequence_key(stream_id))
            
            # 设置 TTL
            await self.redis_client.expire(stream_key, self.event_ttl_seconds)
            
            # 持久化到数据库（异步，不阻塞）
            if self.enable_persistence:
                asyncio.create_task(self._persist_event(stream_id, event))
            
            logger.debug(
                f"推送事件: stream_id={stream_id}, "
                f"event_type={event.event_type}, "
                f"sequence={event.sequence_number}"
            )
            
            return True
            
        except RedisError as e:
            logger.error(f"推送事件失败: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"推送事件发生未预期错误: {str(e)}", exc_info=True)
            return False
    
    async def _persist_event(
        self,
        stream_id: str,
        event: StreamEvent
    ) -> None:
        """
        持久化事件到数据库
        
        Args:
            stream_id: 流 ID
            event: 流式事件对象
            
        验证：需求 1.4
        """
        if not self.db_pool:
            return
        
        try:
            async with self.db_pool.connection() as conn:
                await conn.execute(
                    """
                    INSERT INTO stream_events (stream_id, sequence_number, event_type, event_data)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (stream_id, sequence_number) DO NOTHING
                    """,
                    (
                        stream_id,
                        event.sequence_number,
                        event.event_type.value,
                        json.dumps(event.data)
                    )
                )
                await conn.commit()
                
                logger.debug(
                    f"事件已持久化: stream_id={stream_id}, "
                    f"sequence={event.sequence_number}"
                )
                
        except Exception as e:
            logger.warning(f"事件持久化失败（不影响推送）: {str(e)}")
    
    async def get_events(
        self,
        stream_id: str,
        from_sequence: int = 0
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        获取事件流，支持断点续传
        
        从指定序列号开始获取事件。如果没有新事件，会等待新事件到达。
        如果 Redis 中没有事件，会尝试从数据库恢复。
        
        Args:
            stream_id: 流 ID
            from_sequence: 起始序列号（默认从 0 开始）
            
        Yields:
            StreamEvent: 流式事件对象
            
        验证：需求 1.4
        """
        stream_key = self._get_stream_key(stream_id)
        current_index = from_sequence
        
        try:
            # 如果从非零序列号开始，尝试从数据库恢复历史事件
            if from_sequence > 0 and self.enable_persistence:
                async for event in self._recover_events_from_db(stream_id, from_sequence):
                    yield event
                    current_index = event.sequence_number + 1
            
            while True:
                # 获取当前索引的事件
                event_data = await self.redis_client.lindex(stream_key, current_index)
                
                if event_data is None:
                    # Redis 中没有事件，尝试从数据库恢复
                    if self.enable_persistence:
                        recovered = False
                        async for event in self._recover_events_from_db(
                            stream_id, 
                            current_index, 
                            current_index
                        ):
                            yield event
                            current_index = event.sequence_number + 1
                            recovered = True
                        
                        if recovered:
                            continue
                    
                    # 没有更多事件，等待一段时间后重试
                    await asyncio.sleep(0.1)
                    
                    # 检查流是否已完成
                    last_seq = await self.redis_client.get(
                        self._get_sequence_key(stream_id)
                    )
                    
                    if last_seq is None:
                        # 流已过期或不存在，检查数据库
                        if self.enable_persistence:
                            has_more = await self._check_db_for_more_events(
                                stream_id, 
                                current_index
                            )
                            if not has_more:
                                logger.debug(f"流已结束: stream_id={stream_id}")
                                break
                        else:
                            logger.debug(f"流已结束: stream_id={stream_id}")
                            break
                    
                    # 检查是否有新事件
                    if current_index >= int(last_seq):
                        # 检查是否是完成事件
                        if current_index > 0:
                            last_event_data = await self.redis_client.lindex(
                                stream_key,
                                current_index - 1
                            )
                            if last_event_data:
                                last_event = StreamEvent.model_validate_json(last_event_data)
                                if last_event.event_type == EventType.COMPLETE:
                                    logger.debug(f"流已完成: stream_id={stream_id}")
                                    break
                        
                        # 继续等待
                        continue
                else:
                    # 解析并返回事件
                    event = StreamEvent.model_validate_json(event_data)
                    yield event
                    
                    current_index += 1
                    
                    # 如果是完成事件，结束流
                    if event.event_type == EventType.COMPLETE:
                        logger.debug(f"流已完成: stream_id={stream_id}")
                        break
                        
        except RedisError as e:
            logger.error(f"获取事件流失败: {str(e)}")
            # 推送错误事件
            error_event = StreamEvent(
                event_type=EventType.ERROR,
                batch_id=stream_id,
                sequence_number=current_index,
                data={
                    "error": "redis_error",
                    "message": str(e),
                    "retry_suggestion": "请稍后重试"
                }
            )
            yield error_event
            
        except Exception as e:
            logger.error(f"获取事件流发生未预期错误: {str(e)}", exc_info=True)
            # 推送错误事件
            error_event = StreamEvent(
                event_type=EventType.ERROR,
                batch_id=stream_id,
                sequence_number=current_index,
                data={
                    "error": "internal_error",
                    "message": str(e),
                    "retry_suggestion": "请联系技术支持"
                }
            )
            yield error_event
    
    async def _recover_events_from_db(
        self,
        stream_id: str,
        from_sequence: int,
        to_sequence: Optional[int] = None
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        从数据库恢复事件
        
        Args:
            stream_id: 流 ID
            from_sequence: 起始序列号
            to_sequence: 结束序列号（可选）
            
        Yields:
            StreamEvent: 恢复的事件对象
            
        验证：需求 1.4
        """
        if not self.db_pool:
            return
        
        try:
            async with self.db_pool.connection() as conn:
                if to_sequence is not None:
                    query = """
                        SELECT sequence_number, event_type, event_data, created_at
                        FROM stream_events
                        WHERE stream_id = %s 
                          AND sequence_number >= %s 
                          AND sequence_number <= %s
                        ORDER BY sequence_number
                    """
                    params = (stream_id, from_sequence, to_sequence)
                else:
                    query = """
                        SELECT sequence_number, event_type, event_data, created_at
                        FROM stream_events
                        WHERE stream_id = %s AND sequence_number >= %s
                        ORDER BY sequence_number
                    """
                    params = (stream_id, from_sequence)
                
                async with conn.cursor() as cur:
                    await cur.execute(query, params)
                    
                    async for row in cur:
                        sequence_number, event_type, event_data, created_at = row
                        
                        # 重建事件对象
                        event = StreamEvent(
                            event_type=EventType(event_type),
                            timestamp=created_at,
                            batch_id=stream_id,
                            sequence_number=sequence_number,
                            data=event_data
                        )
                        
                        logger.debug(
                            f"从数据库恢复事件: stream_id={stream_id}, "
                            f"sequence={sequence_number}"
                        )
                        
                        yield event
                        
        except Exception as e:
            logger.error(f"从数据库恢复事件失败: {str(e)}", exc_info=True)
    
    async def _check_db_for_more_events(
        self,
        stream_id: str,
        from_sequence: int
    ) -> bool:
        """
        检查数据库中是否还有更多事件
        
        Args:
            stream_id: 流 ID
            from_sequence: 起始序列号
            
        Returns:
            如果还有更多事件返回 True，否则返回 False
        """
        if not self.db_pool:
            return False
        
        try:
            async with self.db_pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        SELECT COUNT(*) 
                        FROM stream_events
                        WHERE stream_id = %s AND sequence_number >= %s
                        """,
                        (stream_id, from_sequence)
                    )
                    
                    row = await cur.fetchone()
                    return row[0] > 0 if row else False
                    
        except Exception as e:
            logger.error(f"检查数据库事件失败: {str(e)}")
            return False
    
    async def close_stream(self, stream_id: str) -> None:
        """
        关闭流式连接
        
        删除流相关的 Redis 键。
        
        Args:
            stream_id: 流 ID
            
        验证：需求 1.1
        """
        try:
            stream_key = self._get_stream_key(stream_id)
            sequence_key = self._get_sequence_key(stream_id)
            
            # 删除事件列表和序列号
            await self.redis_client.delete(stream_key, sequence_key)
            
            logger.info(f"关闭流式连接: stream_id={stream_id}")
            
        except RedisError as e:
            logger.warning(f"关闭流式连接失败: {str(e)}")
        except Exception as e:
            logger.error(f"关闭流式连接发生未预期错误: {str(e)}", exc_info=True)
    
    async def push_error_event(
        self,
        stream_id: str,
        error_type: str,
        error_message: str,
        retry_suggestion: Optional[str] = None,
        sequence_number: Optional[int] = None,
        error_details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        推送错误事件
        
        根据错误类型自动生成重试建议。
        
        Args:
            stream_id: 流 ID
            error_type: 错误类型
            error_message: 错误消息
            retry_suggestion: 重试建议（可选，如果不提供则自动生成）
            sequence_number: 序列号（可选，如果不提供则自动获取）
            error_details: 错误详情（可选）
            
        Returns:
            如果推送成功返回 True，失败返回 False
            
        验证：需求 1.5
        """
        try:
            # 获取当前序列号
            if sequence_number is None:
                last_seq = await self.redis_client.get(
                    self._get_sequence_key(stream_id)
                )
                sequence_number = int(last_seq) if last_seq else 0
            
            # 如果没有提供重试建议，根据错误类型生成
            if retry_suggestion is None:
                retry_suggestion = self._generate_retry_suggestion(error_type, error_message)
            
            # 构建错误数据
            error_data = {
                "error": error_type,
                "message": error_message,
                "retry_suggestion": retry_suggestion
            }
            
            # 添加错误详情
            if error_details:
                error_data["details"] = error_details
            
            # 构建错误事件
            error_event = StreamEvent(
                event_type=EventType.ERROR,
                batch_id=stream_id,
                sequence_number=sequence_number,
                data=error_data
            )
            
            # 推送事件
            return await self.push_event(stream_id, error_event)
            
        except Exception as e:
            logger.error(f"推送错误事件失败: {str(e)}", exc_info=True)
            return False
    
    def _generate_retry_suggestion(
        self,
        error_type: str,
        error_message: str
    ) -> str:
        """
        根据错误类型生成重试建议
        
        Args:
            error_type: 错误类型
            error_message: 错误消息
            
        Returns:
            重试建议字符串
            
        验证：需求 1.5
        """
        # 根据错误类型提供具体的重试建议
        suggestions = {
            "redis_error": "Redis 连接失败，请检查 Redis 服务状态后重试",
            "database_error": "数据库连接失败，请检查数据库服务状态后重试",
            "timeout_error": "操作超时，请稍后重试",
            "network_error": "网络连接失败，请检查网络连接后重试",
            "rate_limit_error": "请求频率过高，请等待一段时间后重试",
            "validation_error": "数据验证失败，请检查输入数据格式",
            "permission_error": "权限不足，请联系管理员",
            "resource_not_found": "资源不存在，请检查资源 ID",
            "internal_error": "服务器内部错误，请联系技术支持",
            "batch_processing_error": "批次处理失败，请检查批次数据后重试",
            "grading_error": "批改失败，请检查试卷图片质量后重试"
        }
        
        # 返回对应的建议，如果没有匹配则返回默认建议
        suggestion = suggestions.get(error_type, "请稍后重试")
        
        # 如果错误消息中包含特定关键词，提供更具体的建议
        if "connection" in error_message.lower():
            suggestion += "，建议检查网络连接"
        elif "timeout" in error_message.lower():
            suggestion += "，建议增加超时时间或稍后重试"
        elif "permission" in error_message.lower() or "denied" in error_message.lower():
            suggestion += "，建议检查访问权限"
        
        return suggestion
    
    async def get_stream_status(self, stream_id: str) -> Dict[str, Any]:
        """
        获取流的状态信息
        
        Args:
            stream_id: 流 ID
            
        Returns:
            包含流状态信息的字典
        """
        try:
            stream_key = self._get_stream_key(stream_id)
            sequence_key = self._get_sequence_key(stream_id)
            
            # 获取事件数量
            event_count = await self.redis_client.llen(stream_key)
            
            # 获取最后序列号
            last_seq = await self.redis_client.get(sequence_key)
            
            # 获取 TTL
            ttl = await self.redis_client.ttl(stream_key)
            
            return {
                "stream_id": stream_id,
                "event_count": event_count,
                "last_sequence": int(last_seq) if last_seq else 0,
                "ttl_seconds": ttl,
                "exists": event_count > 0 or last_seq is not None
            }
            
        except Exception as e:
            logger.error(f"获取流状态失败: {str(e)}", exc_info=True)
            return {
                "stream_id": stream_id,
                "error": str(e),
                "exists": False
            }
