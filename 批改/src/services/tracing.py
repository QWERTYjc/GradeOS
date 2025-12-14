"""
端到端追踪服务

提供跨组件的分布式追踪能力，包括：
- 生成唯一 trace_id
- 跨组件传递追踪标识
- 结构化日志记录
- 性能告警

验证：需求 5.1, 5.2, 5.3, 5.4, 5.5
"""

import asyncio
import logging
import uuid
from typing import Optional, Dict, Any, List, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from contextlib import asynccontextmanager

from src.utils.pool_manager import UnifiedPoolManager, PoolNotInitializedError


logger = logging.getLogger(__name__)


class SpanKind(str, Enum):
    """
    追踪跨度类型枚举
    
    定义不同组件类型的跨度，用于区分追踪链路中的不同阶段。
    
    验证：需求 5.1, 5.2, 5.3
    """
    API = "api"
    TEMPORAL_WORKFLOW = "temporal_workflow"
    TEMPORAL_ACTIVITY = "temporal_activity"
    LANGGRAPH_NODE = "langgraph_node"
    DATABASE = "database"
    CACHE = "cache"
    EXTERNAL_SERVICE = "external_service"
    INTERNAL = "internal"


class SpanStatus(str, Enum):
    """跨度状态枚举"""
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class TraceSpan:
    """
    追踪跨度数据类
    
    表示追踪链路中的一个操作单元，包含：
    - 追踪标识（trace_id, span_id）
    - 父子关系（parent_span_id）
    - 类型和名称
    - 时间信息
    - 属性和状态
    
    验证：需求 5.1, 5.2, 5.3
    """
    trace_id: str
    span_id: str
    kind: SpanKind
    name: str
    start_time: datetime
    parent_span_id: Optional[str] = None
    end_time: Optional[datetime] = None
    duration_ms: Optional[int] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    status: SpanStatus = SpanStatus.OK
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "kind": self.kind.value,
            "name": self.name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "attributes": self.attributes,
            "status": self.status.value,
            "error_message": self.error_message,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TraceSpan":
        """从字典创建"""
        return cls(
            trace_id=data["trace_id"],
            span_id=data["span_id"],
            parent_span_id=data.get("parent_span_id"),
            kind=SpanKind(data["kind"]),
            name=data["name"],
            start_time=datetime.fromisoformat(data["start_time"]),
            end_time=datetime.fromisoformat(data["end_time"]) if data.get("end_time") else None,
            duration_ms=data.get("duration_ms"),
            attributes=data.get("attributes", {}),
            status=SpanStatus(data.get("status", "ok")),
            error_message=data.get("error_message"),
        )


@dataclass
class TracingConfig:
    """追踪服务配置"""
    alert_threshold_ms: int = 500  # 性能告警阈值（毫秒）
    enable_persistence: bool = True  # 是否持久化到数据库
    enable_alerts: bool = True  # 是否启用告警
    max_attributes_size: int = 10000  # 属性最大字节数
    batch_size: int = 100  # 批量持久化大小
    flush_interval_seconds: float = 5.0  # 刷新间隔（秒）


class TracingService:
    """
    端到端追踪服务
    
    特性：
    - 生成唯一 trace_id
    - 跨组件传递追踪标识
    - 结构化日志记录
    - 性能告警
    - 追踪链路查询
    
    验证：需求 5.1, 5.2, 5.3, 5.4, 5.5
    """
    
    def __init__(
        self,
        pool_manager: UnifiedPoolManager,
        config: Optional[TracingConfig] = None,
        alert_callback: Optional[Callable[[TraceSpan], Awaitable[None]]] = None
    ):
        """
        初始化追踪服务
        
        Args:
            pool_manager: 统一连接池管理器
            config: 追踪配置
            alert_callback: 告警回调函数
        """
        self.pool_manager = pool_manager
        self.config = config or TracingConfig()
        self.alert_callback = alert_callback
        
        # 待持久化的 span 缓冲区
        self._span_buffer: List[TraceSpan] = []
        self._buffer_lock = asyncio.Lock()
        
        # 后台刷新任务
        self._flush_task: Optional[asyncio.Task] = None
        self._running = False
        
        # 统计信息
        self._stats = {
            "spans_created": 0,
            "spans_persisted": 0,
            "alerts_triggered": 0,
            "persistence_errors": 0,
        }
    
    @property
    def stats(self) -> Dict[str, int]:
        """获取统计信息"""
        return self._stats.copy()
    
    async def start(self) -> None:
        """启动追踪服务"""
        if self._running:
            return
        
        self._running = True
        
        if self.config.enable_persistence:
            self._flush_task = asyncio.create_task(self._flush_loop())
        
        logger.info("追踪服务已启动")
    
    async def stop(self) -> None:
        """停止追踪服务"""
        self._running = False
        
        if self._flush_task is not None:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
            self._flush_task = None
        
        # 刷新剩余的 span
        await self._flush_buffer()
        
        logger.info("追踪服务已停止")
    
    async def _flush_loop(self) -> None:
        """后台刷新循环"""
        while self._running:
            try:
                await asyncio.sleep(self.config.flush_interval_seconds)
                await self._flush_buffer()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"刷新追踪数据时出错: {e}")
    
    async def _flush_buffer(self) -> None:
        """刷新缓冲区到数据库"""
        async with self._buffer_lock:
            if not self._span_buffer:
                return
            
            spans_to_persist = self._span_buffer.copy()
            self._span_buffer.clear()
        
        await self._persist_spans(spans_to_persist)
    
    def generate_trace_id(self) -> str:
        """
        生成唯一 trace_id
        
        Returns:
            唯一的 trace_id 字符串
            
        验证：需求 5.1
        """
        return str(uuid.uuid4())
    
    def generate_span_id(self) -> str:
        """
        生成唯一 span_id
        
        Returns:
            唯一的 span_id 字符串
        """
        return str(uuid.uuid4())
    
    def start_span(
        self,
        trace_id: str,
        kind: SpanKind,
        name: str,
        parent_span_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None
    ) -> TraceSpan:
        """
        开始一个跨度
        
        创建新的追踪跨度并记录开始时间。
        
        Args:
            trace_id: 追踪 ID
            kind: 跨度类型
            name: 跨度名称
            parent_span_id: 父跨度 ID（可选）
            attributes: 附加属性（可选）
            
        Returns:
            新创建的 TraceSpan 对象
            
        验证：需求 5.1, 5.2, 5.3
        """
        span = TraceSpan(
            trace_id=trace_id,
            span_id=self.generate_span_id(),
            kind=kind,
            name=name,
            parent_span_id=parent_span_id,
            start_time=datetime.now(timezone.utc),
            attributes=attributes or {},
        )
        
        self._stats["spans_created"] += 1
        
        logger.debug(
            f"开始跨度: trace_id={trace_id}, span_id={span.span_id}, "
            f"kind={kind.value}, name={name}"
        )
        
        return span
    
    async def end_span(
        self,
        span: TraceSpan,
        status: SpanStatus = SpanStatus.OK,
        error_message: Optional[str] = None,
        additional_attributes: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        结束跨度并记录
        
        设置结束时间、计算持续时间、检查性能告警并持久化。
        
        Args:
            span: 要结束的跨度
            status: 跨度状态
            error_message: 错误信息（可选）
            additional_attributes: 附加属性（可选）
            
        验证：需求 5.1, 5.5
        """
        span.end_time = datetime.now(timezone.utc)
        span.status = status
        span.error_message = error_message
        
        # 计算持续时间
        duration = span.end_time - span.start_time
        span.duration_ms = int(duration.total_seconds() * 1000)
        
        # 合并附加属性
        if additional_attributes:
            span.attributes.update(additional_attributes)
        
        logger.debug(
            f"结束跨度: trace_id={span.trace_id}, span_id={span.span_id}, "
            f"duration_ms={span.duration_ms}, status={status.value}"
        )
        
        # 检查性能告警
        if self.config.enable_alerts:
            await self.check_and_alert(span)
        
        # 添加到缓冲区
        if self.config.enable_persistence:
            async with self._buffer_lock:
                self._span_buffer.append(span)
                
                # 如果缓冲区满了，立即刷新
                if len(self._span_buffer) >= self.config.batch_size:
                    spans_to_persist = self._span_buffer.copy()
                    self._span_buffer.clear()
                    asyncio.create_task(self._persist_spans(spans_to_persist))
    
    @asynccontextmanager
    async def trace_span(
        self,
        trace_id: str,
        kind: SpanKind,
        name: str,
        parent_span_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None
    ):
        """
        跨度上下文管理器
        
        自动管理跨度的开始和结束。
        
        Args:
            trace_id: 追踪 ID
            kind: 跨度类型
            name: 跨度名称
            parent_span_id: 父跨度 ID（可选）
            attributes: 附加属性（可选）
            
        Yields:
            TraceSpan 对象
        """
        span = self.start_span(
            trace_id=trace_id,
            kind=kind,
            name=name,
            parent_span_id=parent_span_id,
            attributes=attributes,
        )
        
        try:
            yield span
            await self.end_span(span, status=SpanStatus.OK)
        except Exception as e:
            await self.end_span(
                span,
                status=SpanStatus.ERROR,
                error_message=str(e)
            )
            raise
    
    async def check_and_alert(self, span: TraceSpan) -> None:
        """
        检查性能并触发告警
        
        当跨度持续时间超过阈值时触发告警。
        
        Args:
            span: 要检查的跨度
            
        验证：需求 5.5
        """
        if span.duration_ms is None:
            return
        
        if span.duration_ms > self.config.alert_threshold_ms:
            self._stats["alerts_triggered"] += 1
            
            logger.warning(
                f"性能告警: trace_id={span.trace_id}, span_id={span.span_id}, "
                f"name={span.name}, duration_ms={span.duration_ms}, "
                f"threshold_ms={self.config.alert_threshold_ms}"
            )
            
            # 调用告警回调
            if self.alert_callback is not None:
                try:
                    await self.alert_callback(span)
                except Exception as e:
                    logger.warning(f"执行告警回调时出错: {e}")
    
    async def _persist_spans(self, spans: List[TraceSpan]) -> None:
        """
        持久化跨度到数据库
        
        Args:
            spans: 要持久化的跨度列表
        """
        if not spans:
            return
        
        try:
            async with self.pool_manager.pg_connection() as conn:
                # 批量插入
                for span in spans:
                    await conn.execute(
                        """
                        INSERT INTO trace_spans 
                        (trace_id, span_id, parent_span_id, kind, name,
                         start_time, end_time, duration_ms, attributes, 
                         status, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (trace_id, span_id) DO UPDATE SET
                            end_time = EXCLUDED.end_time,
                            duration_ms = EXCLUDED.duration_ms,
                            attributes = EXCLUDED.attributes,
                            status = EXCLUDED.status
                        """,
                        (
                            span.trace_id,
                            span.span_id,
                            span.parent_span_id,
                            span.kind.value,
                            span.name,
                            span.start_time,
                            span.end_time,
                            span.duration_ms,
                            span.attributes,
                            span.status.value,
                            datetime.now(timezone.utc),
                        )
                    )
            
            self._stats["spans_persisted"] += len(spans)
            logger.debug(f"已持久化 {len(spans)} 个跨度")
            
        except PoolNotInitializedError:
            logger.warning("数据库连接池未初始化，跳过跨度持久化")
            self._stats["persistence_errors"] += 1
        except Exception as e:
            logger.warning(f"持久化跨度失败: {e}")
            self._stats["persistence_errors"] += 1
    
    async def get_trace(self, trace_id: str) -> List[TraceSpan]:
        """
        获取完整追踪链路
        
        根据 trace_id 查询所有相关的跨度。
        
        Args:
            trace_id: 追踪 ID
            
        Returns:
            该追踪的所有跨度列表，按开始时间排序
            
        验证：需求 5.4
        """
        try:
            async with self.pool_manager.pg_connection() as conn:
                result = await conn.execute(
                    """
                    SELECT trace_id, span_id, parent_span_id, kind, name,
                           start_time, end_time, duration_ms, attributes, status
                    FROM trace_spans
                    WHERE trace_id = %s
                    ORDER BY start_time ASC
                    """,
                    (trace_id,)
                )
                rows = await result.fetchall()
                
                return [
                    TraceSpan(
                        trace_id=row["trace_id"],
                        span_id=row["span_id"],
                        parent_span_id=row["parent_span_id"],
                        kind=SpanKind(row["kind"]),
                        name=row["name"],
                        start_time=row["start_time"],
                        end_time=row["end_time"],
                        duration_ms=row["duration_ms"],
                        attributes=row["attributes"] or {},
                        status=SpanStatus(row["status"]) if row["status"] else SpanStatus.OK,
                    )
                    for row in rows
                ]
                
        except PoolNotInitializedError:
            logger.warning("数据库连接池未初始化")
            return []
        except Exception as e:
            logger.warning(f"查询追踪链路失败: {e}")
            return []
    
    async def get_span(
        self,
        trace_id: str,
        span_id: str
    ) -> Optional[TraceSpan]:
        """
        获取单个跨度
        
        Args:
            trace_id: 追踪 ID
            span_id: 跨度 ID
            
        Returns:
            跨度对象，未找到返回 None
        """
        try:
            async with self.pool_manager.pg_connection() as conn:
                result = await conn.execute(
                    """
                    SELECT trace_id, span_id, parent_span_id, kind, name,
                           start_time, end_time, duration_ms, attributes, status
                    FROM trace_spans
                    WHERE trace_id = %s AND span_id = %s
                    """,
                    (trace_id, span_id)
                )
                row = await result.fetchone()
                
                if row:
                    return TraceSpan(
                        trace_id=row["trace_id"],
                        span_id=row["span_id"],
                        parent_span_id=row["parent_span_id"],
                        kind=SpanKind(row["kind"]),
                        name=row["name"],
                        start_time=row["start_time"],
                        end_time=row["end_time"],
                        duration_ms=row["duration_ms"],
                        attributes=row["attributes"] or {},
                        status=SpanStatus(row["status"]) if row["status"] else SpanStatus.OK,
                    )
                return None
                
        except PoolNotInitializedError:
            logger.warning("数据库连接池未初始化")
            return None
        except Exception as e:
            logger.warning(f"查询跨度失败: {e}")
            return None
    
    async def list_slow_spans(
        self,
        threshold_ms: Optional[int] = None,
        limit: int = 100,
        since: Optional[datetime] = None
    ) -> List[TraceSpan]:
        """
        列出慢跨度
        
        查询持续时间超过阈值的跨度。
        
        Args:
            threshold_ms: 阈值（毫秒），默认使用配置值
            limit: 返回数量限制
            since: 起始时间（可选）
            
        Returns:
            慢跨度列表
            
        验证：需求 5.5
        """
        threshold = threshold_ms or self.config.alert_threshold_ms
        
        try:
            async with self.pool_manager.pg_connection() as conn:
                if since:
                    result = await conn.execute(
                        """
                        SELECT trace_id, span_id, parent_span_id, kind, name,
                               start_time, end_time, duration_ms, attributes, status
                        FROM trace_spans
                        WHERE duration_ms > %s AND start_time >= %s
                        ORDER BY duration_ms DESC
                        LIMIT %s
                        """,
                        (threshold, since, limit)
                    )
                else:
                    result = await conn.execute(
                        """
                        SELECT trace_id, span_id, parent_span_id, kind, name,
                               start_time, end_time, duration_ms, attributes, status
                        FROM trace_spans
                        WHERE duration_ms > %s
                        ORDER BY duration_ms DESC
                        LIMIT %s
                        """,
                        (threshold, limit)
                    )
                
                rows = await result.fetchall()
                
                return [
                    TraceSpan(
                        trace_id=row["trace_id"],
                        span_id=row["span_id"],
                        parent_span_id=row["parent_span_id"],
                        kind=SpanKind(row["kind"]),
                        name=row["name"],
                        start_time=row["start_time"],
                        end_time=row["end_time"],
                        duration_ms=row["duration_ms"],
                        attributes=row["attributes"] or {},
                        status=SpanStatus(row["status"]) if row["status"] else SpanStatus.OK,
                    )
                    for row in rows
                ]
                
        except PoolNotInitializedError:
            logger.warning("数据库连接池未初始化")
            return []
        except Exception as e:
            logger.warning(f"查询慢跨度失败: {e}")
            return []
    
    async def get_trace_summary(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """
        获取追踪摘要
        
        返回追踪的统计摘要信息。
        
        Args:
            trace_id: 追踪 ID
            
        Returns:
            追踪摘要字典，未找到返回 None
        """
        spans = await self.get_trace(trace_id)
        
        if not spans:
            return None
        
        # 计算统计信息
        total_duration = sum(s.duration_ms or 0 for s in spans)
        error_count = sum(1 for s in spans if s.status == SpanStatus.ERROR)
        
        # 按类型分组
        spans_by_kind: Dict[str, int] = {}
        for span in spans:
            kind = span.kind.value
            spans_by_kind[kind] = spans_by_kind.get(kind, 0) + 1
        
        # 找到根跨度
        root_span = next(
            (s for s in spans if s.parent_span_id is None),
            spans[0] if spans else None
        )
        
        return {
            "trace_id": trace_id,
            "total_spans": len(spans),
            "total_duration_ms": total_duration,
            "error_count": error_count,
            "spans_by_kind": spans_by_kind,
            "root_span_name": root_span.name if root_span else None,
            "start_time": spans[0].start_time.isoformat() if spans else None,
            "end_time": spans[-1].end_time.isoformat() if spans and spans[-1].end_time else None,
        }


class TraceContext:
    """
    追踪上下文
    
    用于在组件间传递追踪信息。
    
    验证：需求 5.1, 5.2, 5.3
    """
    
    def __init__(
        self,
        trace_id: str,
        span_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None
    ):
        """
        初始化追踪上下文
        
        Args:
            trace_id: 追踪 ID
            span_id: 当前跨度 ID（可选）
            attributes: 附加属性（可选）
        """
        self.trace_id = trace_id
        self.span_id = span_id
        self.attributes = attributes or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于序列化传递）"""
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "attributes": self.attributes,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TraceContext":
        """从字典创建"""
        return cls(
            trace_id=data["trace_id"],
            span_id=data.get("span_id"),
            attributes=data.get("attributes", {}),
        )
    
    def child_context(self, new_span_id: str) -> "TraceContext":
        """
        创建子上下文
        
        Args:
            new_span_id: 新的跨度 ID
            
        Returns:
            新的追踪上下文，继承 trace_id 和属性
        """
        return TraceContext(
            trace_id=self.trace_id,
            span_id=new_span_id,
            attributes=self.attributes.copy(),
        )
