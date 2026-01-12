"""
增强型 API 服务

提供 WebSocket 实时推送、分页查询、字段选择和慢查询监控功能。

验证：需求 7.1, 7.2, 7.3, 7.4, 7.5
"""

import asyncio
import json
import logging
import time
from typing import Optional, Dict, Any, List, Set, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from fastapi import WebSocket, WebSocketDisconnect, HTTPException, status
from pydantic import BaseModel, Field
import redis.asyncio as redis

from src.utils.pool_manager import UnifiedPoolManager, PoolNotInitializedError
from src.services.tracing import TracingService, SpanKind, SpanStatus


logger = logging.getLogger(__name__)


class SortOrder(str, Enum):
    """排序顺序枚举"""
    ASC = "asc"
    DESC = "desc"


class QueryParams(BaseModel):
    """
    查询参数模型
    
    支持分页、排序和过滤功能。
    
    验证：需求 7.2
    """
    page: int = Field(default=1, ge=1, description="页码（从 1 开始）")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")
    sort_by: Optional[str] = Field(default=None, description="排序字段")
    sort_order: SortOrder = Field(default=SortOrder.DESC, description="排序顺序")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="过滤条件")


class PaginatedResponse(BaseModel):
    """
    分页响应模型
    
    验证：需求 7.2
    """
    items: List[Dict[str, Any]] = Field(description="数据项列表")
    total: int = Field(description="总数量")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页数量")
    total_pages: int = Field(description="总页数")
    has_next: bool = Field(description="是否有下一页")
    has_prev: bool = Field(description="是否有上一页")


@dataclass
class SlowQueryRecord:
    """慢查询记录"""
    query_id: str
    table: str
    params: Dict[str, Any]
    duration_ms: int
    timestamp: datetime
    trace_id: Optional[str] = None


@dataclass
class EnhancedAPIConfig:
    """增强型 API 服务配置"""
    slow_query_threshold_ms: int = 500  # 慢查询阈值（毫秒）
    websocket_heartbeat_interval: float = 30.0  # WebSocket 心跳间隔（秒）
    max_websocket_connections: int = 1000  # 最大 WebSocket 连接数
    pubsub_channel_prefix: str = "state_changes"  # Pub/Sub 通道前缀
    enable_slow_query_logging: bool = True  # 是否启用慢查询日志
    allowed_sort_fields: Set[str] = field(default_factory=lambda: {
        "created_at", "updated_at", "score", "status", "id"
    })
    allowed_filter_fields: Set[str] = field(default_factory=lambda: {
        "status", "exam_id", "student_id", "question_id"
    })


class EnhancedAPIService:
    """
    增强型 API 服务
    
    特性：
    - WebSocket 实时推送状态变更
    - 分页、排序、过滤查询
    - 字段选择查询
    - 慢查询监控和告警
    - 限流响应处理
    
    验证：需求 7.1, 7.2, 7.3, 7.4, 7.5
    """
    
    def __init__(
        self,
        pool_manager: UnifiedPoolManager,
        tracing_service: Optional[TracingService] = None,
        config: Optional[EnhancedAPIConfig] = None,
        alert_callback: Optional[Callable[[SlowQueryRecord], Awaitable[None]]] = None
    ):
        """
        初始化增强型 API 服务
        
        Args:
            pool_manager: 统一连接池管理器
            tracing_service: 追踪服务（可选）
            config: 服务配置
            alert_callback: 慢查询告警回调
        """
        self.pool_manager = pool_manager
        self.tracing_service = tracing_service
        self.config = config or EnhancedAPIConfig()
        self.alert_callback = alert_callback
        
        # WebSocket 连接管理
        self._websocket_connections: Dict[str, Set[WebSocket]] = {}
        self._connections_lock = asyncio.Lock()
        
        # Pub/Sub 订阅任务
        self._pubsub_task: Optional[asyncio.Task] = None
        self._running = False
        
        # 慢查询记录
        self._slow_queries: List[SlowQueryRecord] = []
        self._slow_queries_lock = asyncio.Lock()
        
        # 统计信息
        self._stats = {
            "queries_executed": 0,
            "slow_queries": 0,
            "websocket_connections": 0,
            "messages_broadcast": 0,
        }
    
    @property
    def stats(self) -> Dict[str, int]:
        """获取统计信息"""
        return self._stats.copy()
    
    async def start(self) -> None:
        """启动服务"""
        if self._running:
            return
        
        self._running = True
        
        # 启动 Pub/Sub 订阅
        self._pubsub_task = asyncio.create_task(self._pubsub_listener())
        
        logger.info("增强型 API 服务已启动")
    
    async def stop(self) -> None:
        """停止服务"""
        self._running = False
        
        # 停止 Pub/Sub 订阅
        if self._pubsub_task is not None:
            self._pubsub_task.cancel()
            try:
                await self._pubsub_task
            except asyncio.CancelledError:
                pass
            self._pubsub_task = None
        
        # 关闭所有 WebSocket 连接
        async with self._connections_lock:
            for submission_id, connections in self._websocket_connections.items():
                for ws in connections:
                    try:
                        await ws.close()
                    except Exception:
                        pass
            self._websocket_connections.clear()
        
        logger.info("增强型 API 服务已停止")


    # ==================== WebSocket 实时推送 ====================
    
    async def handle_websocket(
        self,
        websocket: WebSocket,
        submission_id: str
    ) -> None:
        """
        处理 WebSocket 连接，推送状态变更
        
        Args:
            websocket: WebSocket 连接
            submission_id: 提交 ID
            
        验证：需求 7.1
        """
        await websocket.accept()
        
        # 检查连接数限制
        total_connections = sum(
            len(conns) for conns in self._websocket_connections.values()
        )
        if total_connections >= self.config.max_websocket_connections:
            await websocket.close(code=1013, reason="服务器连接数已满")
            return
        
        # 注册连接
        async with self._connections_lock:
            if submission_id not in self._websocket_connections:
                self._websocket_connections[submission_id] = set()
            self._websocket_connections[submission_id].add(websocket)
            self._stats["websocket_connections"] += 1
        
        logger.info(f"WebSocket 连接已建立: submission_id={submission_id}")
        
        try:
            # 发送初始状态
            initial_state = await self._get_submission_state(submission_id)
            if initial_state:
                await websocket.send_json({
                    "type": "initial_state",
                    "data": initial_state
                })
            
            # 保持连接并处理心跳
            while self._running:
                try:
                    # 等待客户端消息（心跳或其他）
                    message = await asyncio.wait_for(
                        websocket.receive_text(),
                        timeout=self.config.websocket_heartbeat_interval
                    )
                    
                    # 处理心跳
                    if message == "ping":
                        await websocket.send_text("pong")
                    
                except asyncio.TimeoutError:
                    # 发送服务器心跳
                    try:
                        await websocket.send_json({"type": "heartbeat"})
                    except Exception:
                        break
                        
        except WebSocketDisconnect:
            logger.info(f"WebSocket 连接已断开: submission_id={submission_id}")
        except Exception as e:
            logger.warning(f"WebSocket 错误: {e}")
        finally:
            # 注销连接
            async with self._connections_lock:
                if submission_id in self._websocket_connections:
                    self._websocket_connections[submission_id].discard(websocket)
                    if not self._websocket_connections[submission_id]:
                        del self._websocket_connections[submission_id]
                self._stats["websocket_connections"] = max(
                    0, self._stats["websocket_connections"] - 1
                )
    
    async def broadcast_state_change(
        self,
        submission_id: str,
        state: Dict[str, Any]
    ) -> int:
        """
        广播状态变更到 WebSocket 客户端
        
        Args:
            submission_id: 提交 ID
            state: 状态数据
            
        Returns:
            成功发送的连接数
            
        验证：需求 7.1
        """
        sent_count = 0
        
        async with self._connections_lock:
            connections = self._websocket_connections.get(submission_id, set()).copy()
        
        if not connections:
            return 0
        
        message = {
            "type": "state_change",
            "data": state,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        dead_connections = []
        
        for ws in connections:
            try:
                await ws.send_json(message)
                sent_count += 1
            except Exception as e:
                logger.debug(f"发送 WebSocket 消息失败: {e}")
                dead_connections.append(ws)
        
        # 清理死连接
        if dead_connections:
            async with self._connections_lock:
                if submission_id in self._websocket_connections:
                    for ws in dead_connections:
                        self._websocket_connections[submission_id].discard(ws)
        
        self._stats["messages_broadcast"] += sent_count
        return sent_count
    
    async def _pubsub_listener(self) -> None:
        """
        Redis Pub/Sub 监听器
        
        订阅状态变更通道并转发到 WebSocket 客户端。
        
        验证：需求 7.1
        """
        while self._running:
            try:
                redis_client = self.pool_manager.get_redis_client()
                pubsub = redis_client.pubsub()
                
                # 订阅状态变更通道
                pattern = f"{self.config.pubsub_channel_prefix}:*"
                await pubsub.psubscribe(pattern)
                
                logger.info(f"已订阅 Redis Pub/Sub 通道: {pattern}")
                
                async for message in pubsub.listen():
                    if not self._running:
                        break
                    
                    if message["type"] == "pmessage":
                        try:
                            # 解析通道名获取 submission_id
                            channel = message["channel"]
                            if isinstance(channel, bytes):
                                channel = channel.decode("utf-8")
                            
                            parts = channel.split(":")
                            if len(parts) >= 2:
                                submission_id = parts[1]
                                
                                # 解析消息数据
                                data = message["data"]
                                if isinstance(data, bytes):
                                    data = data.decode("utf-8")
                                state = json.loads(data)
                                
                                # 广播到 WebSocket
                                await self.broadcast_state_change(submission_id, state)
                        except Exception as e:
                            logger.warning(f"处理 Pub/Sub 消息失败: {e}")
                
                await pubsub.punsubscribe(pattern)
                await pubsub.close()
                
            except PoolNotInitializedError:
                logger.debug("Redis连接不可用，将禁用实时状态推送功能")
                break
            except Exception as e:
                logger.warning(f"Pub/Sub 监听器错误: {e}")
                await asyncio.sleep(1)
    
    async def _get_submission_state(
        self,
        submission_id: str
    ) -> Optional[Dict[str, Any]]:
        """获取提交的当前状态"""
        try:
            # 先尝试从 Redis 获取
            redis_client = self.pool_manager.get_redis_client()
            cache_key = f"workflow_state:{submission_id}"
            cached = await redis_client.get(cache_key)
            
            if cached:
                return json.loads(cached)
            
            # 从数据库获取
            async with self.pool_manager.pg_connection() as conn:
                result = await conn.execute(
                    """
                    SELECT submission_id, exam_id, student_id, status,
                           total_score, max_total_score, created_at, updated_at
                    FROM submissions
                    WHERE submission_id = %s
                    """,
                    (submission_id,)
                )
                row = await result.fetchone()
                
                if row:
                    return {
                        "submission_id": row["submission_id"],
                        "exam_id": row["exam_id"],
                        "student_id": row["student_id"],
                        "status": row["status"],
                        "total_score": float(row["total_score"]) if row["total_score"] else None,
                        "max_total_score": float(row["max_total_score"]) if row["max_total_score"] else None,
                        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
                    }
                return None
                
        except Exception as e:
            logger.warning(f"获取提交状态失败: {e}")
            return None


    # ==================== 分页查询 ====================
    
    async def query_with_pagination(
        self,
        table: str,
        params: QueryParams,
        trace_id: Optional[str] = None
    ) -> PaginatedResponse:
        """
        分页查询
        
        支持分页、排序和过滤功能。
        
        Args:
            table: 表名
            params: 查询参数
            trace_id: 追踪 ID（可选）
            
        Returns:
            分页响应
            
        Raises:
            HTTPException: 查询参数无效或查询失败
            
        验证：需求 7.2
        """
        start_time = time.time()
        query_id = f"{table}_{int(start_time * 1000)}"
        
        # 验证排序字段
        if params.sort_by and params.sort_by not in self.config.allowed_sort_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的排序字段: {params.sort_by}"
            )
        
        # 验证过滤字段
        if params.filters:
            invalid_fields = set(params.filters.keys()) - self.config.allowed_filter_fields
            if invalid_fields:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"不支持的过滤字段: {invalid_fields}"
                )
        
        try:
            async with self.pool_manager.pg_connection() as conn:
                # 构建基础查询
                base_query = f"SELECT * FROM {table}"
                count_query = f"SELECT COUNT(*) as total FROM {table}"
                
                # 构建 WHERE 子句
                where_clauses = []
                query_params = []
                
                if params.filters:
                    for field_name, value in params.filters.items():
                        if value is not None:
                            where_clauses.append(f"{field_name} = %s")
                            query_params.append(value)
                
                if where_clauses:
                    where_sql = " WHERE " + " AND ".join(where_clauses)
                    base_query += where_sql
                    count_query += where_sql
                
                # 获取总数
                count_result = await conn.execute(count_query, query_params)
                count_row = await count_result.fetchone()
                total = count_row["total"] if count_row else 0
                
                # 添加排序
                sort_field = params.sort_by or "created_at"
                sort_order = params.sort_order.value.upper()
                base_query += f" ORDER BY {sort_field} {sort_order}"
                
                # 添加分页
                offset = (params.page - 1) * params.page_size
                base_query += f" LIMIT %s OFFSET %s"
                query_params.extend([params.page_size, offset])
                
                # 执行查询
                result = await conn.execute(base_query, query_params)
                rows = await result.fetchall()
                
                # 转换结果
                items = []
                for row in rows:
                    item = dict(row)
                    # 转换日期时间字段
                    for key, value in item.items():
                        if isinstance(value, datetime):
                            item[key] = value.isoformat()
                    items.append(item)
                
                # 计算分页信息
                total_pages = (total + params.page_size - 1) // params.page_size if total > 0 else 0
                
                self._stats["queries_executed"] += 1
                
                # 记录慢查询
                duration_ms = int((time.time() - start_time) * 1000)
                await self._record_slow_query(
                    query_id=query_id,
                    table=table,
                    params=params.model_dump(),
                    duration_ms=duration_ms,
                    trace_id=trace_id
                )
                
                return PaginatedResponse(
                    items=items,
                    total=total,
                    page=params.page,
                    page_size=params.page_size,
                    total_pages=total_pages,
                    has_next=params.page < total_pages,
                    has_prev=params.page > 1
                )
                
        except HTTPException:
            raise
        except PoolNotInitializedError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="数据库服务不可用"
            )
        except Exception as e:
            logger.error(f"分页查询失败: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"查询失败: {str(e)}"
            )
    
    # ==================== 字段选择查询 ====================
    
    async def query_with_field_selection(
        self,
        table: str,
        record_id: str,
        fields: Set[str],
        id_field: str = "id",
        trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        字段选择查询
        
        仅返回请求的字段，减少数据传输。
        
        Args:
            table: 表名
            record_id: 记录 ID
            fields: 要返回的字段集合
            id_field: ID 字段名
            trace_id: 追踪 ID（可选）
            
        Returns:
            包含请求字段的字典
            
        Raises:
            HTTPException: 记录不存在或查询失败
            
        验证：需求 7.3
        """
        start_time = time.time()
        query_id = f"{table}_{record_id}_{int(start_time * 1000)}"
        
        if not fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="必须指定至少一个字段"
            )
        
        try:
            async with self.pool_manager.pg_connection() as conn:
                # 构建字段列表
                field_list = ", ".join(fields)
                
                # 执行查询
                query = f"SELECT {field_list} FROM {table} WHERE {id_field} = %s"
                result = await conn.execute(query, (record_id,))
                row = await result.fetchone()
                
                if not row:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"记录不存在: {record_id}"
                    )
                
                # 转换结果，仅包含请求的字段
                item = {}
                for field_name in fields:
                    if field_name in row:
                        value = row[field_name]
                        if isinstance(value, datetime):
                            value = value.isoformat()
                        item[field_name] = value
                
                self._stats["queries_executed"] += 1
                
                # 记录慢查询
                duration_ms = int((time.time() - start_time) * 1000)
                await self._record_slow_query(
                    query_id=query_id,
                    table=table,
                    params={"id": record_id, "fields": list(fields)},
                    duration_ms=duration_ms,
                    trace_id=trace_id
                )
                
                return item
                
        except HTTPException:
            raise
        except PoolNotInitializedError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="数据库服务不可用"
            )
        except Exception as e:
            logger.error(f"字段选择查询失败: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"查询失败: {str(e)}"
            )


    # ==================== 慢查询监控 ====================
    
    async def _record_slow_query(
        self,
        query_id: str,
        table: str,
        params: Dict[str, Any],
        duration_ms: int,
        trace_id: Optional[str] = None
    ) -> None:
        """
        记录慢查询
        
        当查询时间超过阈值时记录并触发告警。
        
        Args:
            query_id: 查询 ID
            table: 表名
            params: 查询参数
            duration_ms: 查询耗时（毫秒）
            trace_id: 追踪 ID
            
        验证：需求 7.4
        """
        if duration_ms <= self.config.slow_query_threshold_ms:
            return
        
        if not self.config.enable_slow_query_logging:
            return
        
        self._stats["slow_queries"] += 1
        
        record = SlowQueryRecord(
            query_id=query_id,
            table=table,
            params=params,
            duration_ms=duration_ms,
            timestamp=datetime.now(timezone.utc),
            trace_id=trace_id
        )
        
        # 记录日志
        logger.warning(
            f"慢查询告警: query_id={query_id}, table={table}, "
            f"duration_ms={duration_ms}, threshold_ms={self.config.slow_query_threshold_ms}, "
            f"trace_id={trace_id}"
        )
        
        # 保存记录
        async with self._slow_queries_lock:
            self._slow_queries.append(record)
            # 保留最近 1000 条记录
            if len(self._slow_queries) > 1000:
                self._slow_queries = self._slow_queries[-1000:]
        
        # 触发告警回调
        if self.alert_callback is not None:
            try:
                await self.alert_callback(record)
            except Exception as e:
                logger.warning(f"执行慢查询告警回调失败: {e}")
        
        # 如果有追踪服务，记录追踪信息
        if self.tracing_service and trace_id:
            span = self.tracing_service.start_span(
                trace_id=trace_id,
                kind=SpanKind.DATABASE,
                name=f"slow_query:{table}",
                attributes={
                    "query_id": query_id,
                    "table": table,
                    "duration_ms": duration_ms,
                    "is_slow": True,
                }
            )
            await self.tracing_service.end_span(span, status=SpanStatus.OK)
    
    async def get_slow_queries(
        self,
        limit: int = 100,
        min_duration_ms: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        获取慢查询记录
        
        Args:
            limit: 返回数量限制
            min_duration_ms: 最小耗时过滤
            
        Returns:
            慢查询记录列表
            
        验证：需求 7.4
        """
        async with self._slow_queries_lock:
            records = self._slow_queries.copy()
        
        # 过滤
        if min_duration_ms is not None:
            records = [r for r in records if r.duration_ms >= min_duration_ms]
        
        # 按时间倒序排序
        records.sort(key=lambda r: r.timestamp, reverse=True)
        
        # 限制数量
        records = records[:limit]
        
        return [
            {
                "query_id": r.query_id,
                "table": r.table,
                "params": r.params,
                "duration_ms": r.duration_ms,
                "timestamp": r.timestamp.isoformat(),
                "trace_id": r.trace_id,
            }
            for r in records
        ]
    
    # ==================== 限流响应 ====================
    
    @staticmethod
    def create_rate_limit_response(
        retry_after: int,
        limit: int,
        window_seconds: int
    ) -> Dict[str, Any]:
        """
        创建限流响应
        
        当请求超过限流阈值时返回 429 响应。
        
        Args:
            retry_after: 重试等待时间（秒）
            limit: 限流阈值
            window_seconds: 时间窗口（秒）
            
        Returns:
            限流响应字典
            
        验证：需求 7.5
        """
        return {
            "error": "rate_limit_exceeded",
            "message": f"请求过于频繁，请在 {retry_after} 秒后重试",
            "limit": limit,
            "window_seconds": window_seconds,
            "retry_after": retry_after
        }
    
    @staticmethod
    def get_rate_limit_headers(
        retry_after: int,
        limit: int,
        remaining: int,
        reset_at: Optional[str] = None
    ) -> Dict[str, str]:
        """
        获取限流响应头
        
        Args:
            retry_after: 重试等待时间（秒）
            limit: 限流阈值
            remaining: 剩余配额
            reset_at: 重置时间
            
        Returns:
            响应头字典
            
        验证：需求 7.5
        """
        headers = {
            "Retry-After": str(retry_after),
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(remaining),
        }
        if reset_at:
            headers["X-RateLimit-Reset"] = reset_at
        return headers
    
    # ==================== 辅助方法 ====================
    
    def get_active_connections_count(self) -> int:
        """获取活跃 WebSocket 连接数"""
        return sum(len(conns) for conns in self._websocket_connections.values())
    
    def get_subscribed_submissions(self) -> List[str]:
        """获取有订阅的提交 ID 列表"""
        return list(self._websocket_connections.keys())


# 便捷函数
def create_enhanced_api_service(
    pool_manager: UnifiedPoolManager,
    tracing_service: Optional[TracingService] = None,
    slow_query_threshold_ms: int = 500
) -> EnhancedAPIService:
    """
    创建增强型 API 服务实例
    
    Args:
        pool_manager: 统一连接池管理器
        tracing_service: 追踪服务（可选）
        slow_query_threshold_ms: 慢查询阈值（毫秒）
        
    Returns:
        配置好的 EnhancedAPIService 实例
    """
    config = EnhancedAPIConfig(
        slow_query_threshold_ms=slow_query_threshold_ms
    )
    return EnhancedAPIService(
        pool_manager=pool_manager,
        tracing_service=tracing_service,
        config=config
    )
