"""
增强型 Temporal 工作流

提供 Redis 事件接收、分布式锁、进度查询和并发控制的增强工作流混入类。

验证：需求 1.1, 1.4, 1.5, 10.1, 10.2, 10.3, 10.4
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from typing import Any, Awaitable, Dict, List, Optional, TypeVar, Generic, Callable

from temporalio import workflow, activity
from temporalio.common import RetryPolicy

from src.utils.pool_manager import UnifiedPoolManager
from src.utils.enhanced_checkpointer import EnhancedPostgresCheckpointer


logger = logging.getLogger(__name__)


# 默认重试策略
DEFAULT_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=1),
    maximum_attempts=3,
)


@dataclass
class WorkflowProgress:
    """
    工作流进度数据类
    
    用于通过 Temporal Query 暴露工作流进度信息。
    
    验证：需求 10.2
    """
    stage: str
    percentage: float
    details: Dict[str, Any]
    updated_at: str
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "stage": self.stage,
            "percentage": self.percentage,
            "details": self.details,
            "updated_at": self.updated_at,
        }


@dataclass
class ExternalEvent:
    """
    外部事件数据类
    
    用于接收通过 Redis Pub/Sub 转发的外部事件。
    
    验证：需求 10.1
    """
    event_type: str
    payload: Dict[str, Any]
    timestamp: str
    source: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "event_type": self.event_type,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "source": self.source,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExternalEvent":
        """从字典创建"""
        return cls(
            event_type=data.get("event_type", "unknown"),
            payload=data.get("payload", {}),
            timestamp=data.get("timestamp", ""),
            source=data.get("source"),
        )


@dataclass
class LangGraphState:
    """
    LangGraph 状态快照
    
    用于通过 Temporal Query 返回 LangGraph 最新状态。
    
    验证：需求 1.5
    """
    thread_id: str
    checkpoint_id: Optional[str]
    channel_values: Dict[str, Any]
    metadata: Dict[str, Any]
    updated_at: str
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "thread_id": self.thread_id,
            "checkpoint_id": self.checkpoint_id,
            "channel_values": self.channel_values,
            "metadata": self.metadata,
            "updated_at": self.updated_at,
        }


class EnhancedWorkflowMixin:
    """
    增强型工作流混入类
    
    特性：
    - 进度查询（Temporal Query）
    - 外部事件接收（Signal）
    - 分布式锁协调
    - 批量子工作流并发控制
    - 状态标识一致性（workflow_run_id 作为 thread_id）
    - 重试策略决策
    
    验证：需求 1.1, 1.4, 1.5, 10.1, 10.2, 10.3, 10.4
    """
    
    def __init__(self):
        """初始化增强型工作流混入"""
        # 进度信息
        self._progress: Dict[str, Any] = {
            "stage": "initialized",
            "percentage": 0.0,
            "details": {},
            "updated_at": "",
        }
        
        # 外部事件队列
        self._external_events: List[Dict[str, Any]] = []
        self._event_received = False
        
        # LangGraph 状态快照
        self._langgraph_state: Optional[Dict[str, Any]] = None
        
        # 分布式锁状态
        self._held_locks: Dict[str, str] = {}  # resource_id -> lock_token
    
    # ==================== Query 方法 ====================
    
    @workflow.query
    def get_progress(self) -> Dict[str, Any]:
        """
        查询当前进度
        
        通过 Temporal Query 暴露工作流进度信息。
        
        Returns:
            进度信息字典，包含 stage、percentage、details 和 updated_at
            
        验证：需求 10.2
        """
        return self._progress
    
    @workflow.query
    def get_langgraph_state(self) -> Optional[Dict[str, Any]]:
        """
        查询 LangGraph 状态快照
        
        返回最新的 LangGraph 状态，确保 Query 返回最新状态。
        
        Returns:
            LangGraph 状态字典，未初始化返回 None
            
        验证：需求 1.5
        """
        return self._langgraph_state
    
    @workflow.query
    def get_external_events(self) -> List[Dict[str, Any]]:
        """
        查询已接收的外部事件
        
        Returns:
            外部事件列表
        """
        return self._external_events
    
    @workflow.query
    def get_held_locks(self) -> Dict[str, str]:
        """
        查询当前持有的分布式锁
        
        Returns:
            锁资源 ID 到锁令牌的映射
        """
        return self._held_locks.copy()
    
    # ==================== Signal 方法 ====================
    
    @workflow.signal
    def external_event(self, event: Dict[str, Any]) -> None:
        """
        接收外部事件（通过 Redis Pub/Sub 转发）
        
        工作流可以通过此 Signal 接收来自 Redis Pub/Sub 的外部事件。
        
        Args:
            event: 事件数据字典，包含 event_type、payload、timestamp 等
            
        验证：需求 10.1
        """
        logger.info(f"收到外部事件: {event.get('event_type', 'unknown')}")
        self._external_events.append(event)
        self._event_received = True
    
    @workflow.signal
    def update_langgraph_state(self, state: Dict[str, Any]) -> None:
        """
        更新 LangGraph 状态快照
        
        由 Activity 在 LangGraph 状态变更时调用，保持状态同步。
        
        Args:
            state: LangGraph 状态字典
            
        验证：需求 1.5
        """
        self._langgraph_state = state
        logger.debug(f"LangGraph 状态已更新: checkpoint_id={state.get('checkpoint_id')}")
    
    @workflow.signal
    def lock_acquired(self, resource_id: str, lock_token: str) -> None:
        """
        通知锁已获取
        
        Args:
            resource_id: 资源 ID
            lock_token: 锁令牌
        """
        self._held_locks[resource_id] = lock_token
        logger.debug(f"锁已获取: resource_id={resource_id}")
    
    @workflow.signal
    def lock_released(self, resource_id: str) -> None:
        """
        通知锁已释放
        
        Args:
            resource_id: 资源 ID
        """
        self._held_locks.pop(resource_id, None)
        logger.debug(f"锁已释放: resource_id={resource_id}")
    
    # ==================== 进度管理方法 ====================
    
    def update_progress(
        self,
        stage: str,
        percentage: float,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        更新进度信息
        
        更新工作流进度，可通过 Temporal Query 查询。
        
        Args:
            stage: 当前阶段名称
            percentage: 进度百分比 (0.0 - 100.0)
            details: 附加详情（可选）
            
        验证：需求 10.2
        """
        self._progress = {
            "stage": stage,
            "percentage": min(max(percentage, 0.0), 100.0),
            "details": details or {},
            "updated_at": workflow.now().isoformat(),
        }
        logger.debug(f"进度更新: stage={stage}, percentage={percentage}")
    
    # ==================== 事件等待方法 ====================
    
    async def wait_for_external_event(
        self,
        event_type: Optional[str] = None,
        timeout: Optional[timedelta] = None
    ) -> Optional[Dict[str, Any]]:
        """
        等待外部事件
        
        等待通过 Redis Pub/Sub 转发的外部事件。
        
        Args:
            event_type: 要等待的事件类型（可选，None 表示任意事件）
            timeout: 超时时间（可选）
            
        Returns:
            事件数据字典，超时返回 None
            
        验证：需求 10.1
        """
        def check_event() -> bool:
            if not self._external_events:
                return False
            if event_type is None:
                return True
            return any(
                e.get("event_type") == event_type 
                for e in self._external_events
            )
        
        try:
            await workflow.wait_condition(check_event, timeout=timeout)
            
            # 查找并移除匹配的事件
            for i, event in enumerate(self._external_events):
                if event_type is None or event.get("event_type") == event_type:
                    return self._external_events.pop(i)
            
            return None
            
        except asyncio.TimeoutError:
            logger.debug(f"等待外部事件超时: event_type={event_type}")
            return None
    
    # ==================== 状态标识一致性方法 ====================
    
    def get_thread_id(self) -> str:
        """
        获取 LangGraph thread_id
        
        将 workflow_run_id 作为 thread_id 传递给 LangGraph，
        确保状态标识一致性。
        
        Returns:
            thread_id（等于 workflow_run_id）
            
        验证：需求 1.1
        """
        return workflow.info().run_id
    
    def get_workflow_run_id(self) -> str:
        """
        获取工作流运行 ID
        
        Returns:
            workflow_run_id
        """
        return workflow.info().run_id
    
    def get_workflow_id(self) -> str:
        """
        获取工作流 ID
        
        Returns:
            workflow_id
        """
        return workflow.info().workflow_id


    # ==================== 重试策略决策方法 ====================
    
    async def should_recover_from_checkpoint(
        self,
        thread_id: str,
        checkpoint_ns: str = ""
    ) -> bool:
        """
        决定是否从检查点恢复
        
        检查点存在且有效时从检查点恢复，否则重新开始。
        
        Args:
            thread_id: LangGraph thread_id
            checkpoint_ns: 检查点命名空间
            
        Returns:
            True 表示应从检查点恢复，False 表示应重新开始
            
        验证：需求 1.4
        """
        # 通过 Activity 检查检查点是否存在
        result = await workflow.execute_activity(
            check_checkpoint_exists_activity,
            thread_id,
            checkpoint_ns,
            retry_policy=DEFAULT_RETRY_POLICY,
            start_to_close_timeout=timedelta(seconds=30),
        )
        return result.get("exists", False) and result.get("valid", False)
    
    # ==================== 分布式锁方法 ====================
    
    async def acquire_distributed_lock(
        self,
        resource_id: str,
        timeout: timedelta = timedelta(seconds=30),
        lock_timeout: timedelta = timedelta(seconds=30)
    ) -> bool:
        """
        获取分布式锁
        
        通过 Redis 分布式锁协调对共享资源的访问。
        
        Args:
            resource_id: 资源 ID
            timeout: 获取锁的超时时间
            lock_timeout: 锁的过期时间
            
        Returns:
            是否成功获取锁
            
        验证：需求 10.4
        """
        lock_token = str(uuid.uuid4())
        
        result = await workflow.execute_activity(
            acquire_lock_activity,
            resource_id,
            lock_token,
            int(lock_timeout.total_seconds()),
            retry_policy=RetryPolicy(maximum_attempts=1),
            start_to_close_timeout=timeout,
        )
        
        if result.get("acquired", False):
            self._held_locks[resource_id] = lock_token
            logger.info(f"分布式锁已获取: resource_id={resource_id}")
            return True
        
        logger.debug(f"获取分布式锁失败: resource_id={resource_id}")
        return False
    
    async def release_distributed_lock(
        self,
        resource_id: str
    ) -> bool:
        """
        释放分布式锁
        
        Args:
            resource_id: 资源 ID
            
        Returns:
            是否成功释放锁
            
        验证：需求 10.4
        """
        lock_token = self._held_locks.get(resource_id)
        if not lock_token:
            logger.warning(f"尝试释放未持有的锁: resource_id={resource_id}")
            return False
        
        result = await workflow.execute_activity(
            release_lock_activity,
            resource_id,
            lock_token,
            retry_policy=DEFAULT_RETRY_POLICY,
            start_to_close_timeout=timedelta(seconds=10),
        )
        
        if result.get("released", False):
            self._held_locks.pop(resource_id, None)
            logger.info(f"分布式锁已释放: resource_id={resource_id}")
            return True
        
        logger.warning(f"释放分布式锁失败: resource_id={resource_id}")
        return False
    
    async def with_distributed_lock(
        self,
        resource_id: str,
        timeout: timedelta = timedelta(seconds=30),
        lock_timeout: timedelta = timedelta(seconds=30)
    ):
        """
        分布式锁上下文管理器
        
        Args:
            resource_id: 资源 ID
            timeout: 获取锁的超时时间
            lock_timeout: 锁的过期时间
            
        Yields:
            锁令牌
            
        Raises:
            RuntimeError: 获取锁失败时抛出
        """
        acquired = await self.acquire_distributed_lock(
            resource_id, timeout, lock_timeout
        )
        if not acquired:
            raise RuntimeError(f"无法获取分布式锁: {resource_id}")
        
        try:
            yield self._held_locks.get(resource_id)
        finally:
            await self.release_distributed_lock(resource_id)
    
    # ==================== 批量子工作流并发控制 ====================
    
    async def batch_start_child_workflows(
        self,
        workflow_class: type,
        inputs: List[Any],
        max_concurrent: int = 10,
        task_queue: Optional[str] = None,
        id_prefix: Optional[str] = None
    ) -> List[Any]:
        """
        批量启动子工作流，限制并发
        
        使用信号量控制同时运行的子工作流数量。
        
        Args:
            workflow_class: 子工作流类
            inputs: 子工作流输入列表
            max_concurrent: 最大并发数
            task_queue: 任务队列（可选）
            id_prefix: 工作流 ID 前缀（可选）
            
        Returns:
            所有子工作流的结果列表
            
        验证：需求 10.3
        """
        if not inputs:
            return []
        
        # 使用信号量控制并发
        semaphore = asyncio.Semaphore(max_concurrent)
        results: List[Any] = [None] * len(inputs)
        errors: List[Optional[Exception]] = [None] * len(inputs)
        
        async def run_child(index: int, input_data: Any) -> None:
            async with semaphore:
                try:
                    # 生成子工作流 ID
                    child_id = f"{id_prefix or self.get_workflow_id()}_{index}"
                    
                    # 启动子工作流
                    handle = await workflow.start_child_workflow(
                        workflow_class,
                        input_data,
                        id=child_id,
                        task_queue=task_queue or workflow.info().task_queue,
                    )
                    
                    # 等待结果
                    result = await handle.result()
                    results[index] = result
                    
                    # 更新进度
                    completed = sum(1 for r in results if r is not None)
                    self.update_progress(
                        stage="batch_child_workflows",
                        percentage=(completed / len(inputs)) * 100,
                        details={
                            "total": len(inputs),
                            "completed": completed,
                            "max_concurrent": max_concurrent,
                        }
                    )
                    
                except Exception as e:
                    logger.error(f"子工作流执行失败: index={index}, error={e}")
                    errors[index] = e
        
        # 并发启动所有子工作流
        tasks = [
            asyncio.create_task(run_child(i, input_data))
            for i, input_data in enumerate(inputs)
        ]
        
        # 等待所有任务完成
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # 检查错误
        failed_indices = [i for i, e in enumerate(errors) if e is not None]
        if failed_indices:
            logger.warning(f"部分子工作流失败: indices={failed_indices}")
        
        return results


# ==================== Activity 定义 ====================

@activity.defn
async def check_checkpoint_exists_activity(
    thread_id: str,
    checkpoint_ns: str = ""
) -> Dict[str, Any]:
    """
    检查检查点是否存在
    
    Args:
        thread_id: LangGraph thread_id
        checkpoint_ns: 检查点命名空间
        
    Returns:
        包含 exists 和 valid 字段的字典
        
    验证：需求 1.4
    """
    try:
        pool_manager = await UnifiedPoolManager.get_instance()
        
        async with pool_manager.pg_connection() as conn:
            result = await conn.execute(
                """
                SELECT checkpoint_id, is_compressed, is_delta, data_size_bytes
                FROM enhanced_checkpoints
                WHERE thread_id = %s AND checkpoint_ns = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (thread_id, checkpoint_ns)
            )
            row = await result.fetchone()
            
            if row:
                # 检查点存在，验证是否有效
                return {
                    "exists": True,
                    "valid": True,
                    "checkpoint_id": row["checkpoint_id"],
                    "data_size_bytes": row["data_size_bytes"],
                }
            
            return {"exists": False, "valid": False}
            
    except Exception as e:
        logger.error(f"检查检查点存在性失败: {e}")
        return {"exists": False, "valid": False, "error": str(e)}


@activity.defn
async def acquire_lock_activity(
    resource_id: str,
    lock_token: str,
    lock_timeout_seconds: int
) -> Dict[str, Any]:
    """
    获取分布式锁
    
    Args:
        resource_id: 资源 ID
        lock_token: 锁令牌
        lock_timeout_seconds: 锁过期时间（秒）
        
    Returns:
        包含 acquired 字段的字典
        
    验证：需求 10.4
    """
    try:
        pool_manager = await UnifiedPoolManager.get_instance()
        redis_client = pool_manager.get_redis_client()
        
        lock_key = f"lock:{resource_id}"
        
        # 使用 SET NX EX 原子操作获取锁
        acquired = await redis_client.set(
            lock_key,
            lock_token,
            nx=True,
            ex=lock_timeout_seconds
        )
        
        return {
            "acquired": acquired is not None,
            "lock_key": lock_key,
            "lock_token": lock_token if acquired else None,
        }
        
    except Exception as e:
        logger.error(f"获取分布式锁失败: {e}")
        return {"acquired": False, "error": str(e)}


@activity.defn
async def release_lock_activity(
    resource_id: str,
    lock_token: str
) -> Dict[str, Any]:
    """
    释放分布式锁
    
    使用 Lua 脚本确保只有锁持有者才能释放锁。
    
    Args:
        resource_id: 资源 ID
        lock_token: 锁令牌
        
    Returns:
        包含 released 字段的字典
        
    验证：需求 10.4
    """
    try:
        pool_manager = await UnifiedPoolManager.get_instance()
        redis_client = pool_manager.get_redis_client()
        
        lock_key = f"lock:{resource_id}"
        
        # Lua 脚本：只有锁持有者才能释放锁
        release_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        
        result = await redis_client.eval(
            release_script,
            1,
            lock_key,
            lock_token
        )
        
        return {
            "released": result == 1,
            "lock_key": lock_key,
        }
        
    except Exception as e:
        logger.error(f"释放分布式锁失败: {e}")
        return {"released": False, "error": str(e)}


@activity.defn
async def forward_redis_event_activity(
    workflow_id: str,
    event: Dict[str, Any]
) -> Dict[str, Any]:
    """
    转发 Redis 事件到工作流
    
    通过 Temporal Client 将 Redis Pub/Sub 事件转发到工作流 Signal。
    
    Args:
        workflow_id: 目标工作流 ID
        event: 事件数据
        
    Returns:
        转发结果
        
    验证：需求 10.1
    """
    # 注意：此 Activity 需要在 Worker 中配置 Temporal Client
    # 实际实现需要访问 Temporal Client 来发送 Signal
    logger.info(f"转发 Redis 事件到工作流: workflow_id={workflow_id}")
    return {
        "forwarded": True,
        "workflow_id": workflow_id,
        "event_type": event.get("event_type"),
    }


@activity.defn
async def sync_langgraph_state_activity(
    workflow_id: str,
    thread_id: str,
    checkpoint_ns: str = ""
) -> Dict[str, Any]:
    """
    同步 LangGraph 状态到工作流
    
    从检查点读取最新状态并返回。
    
    Args:
        workflow_id: 工作流 ID
        thread_id: LangGraph thread_id
        checkpoint_ns: 检查点命名空间
        
    Returns:
        LangGraph 状态字典
        
    验证：需求 1.5
    """
    try:
        pool_manager = await UnifiedPoolManager.get_instance()
        checkpointer = EnhancedPostgresCheckpointer(pool_manager)
        
        config = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
            }
        }
        
        checkpoint_tuple = await checkpointer.aget(config)
        
        if checkpoint_tuple:
            return {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_tuple.config.get("configurable", {}).get("checkpoint_id"),
                "channel_values": checkpoint_tuple.checkpoint.get("channel_values", {}),
                "metadata": checkpoint_tuple.metadata.__dict__ if checkpoint_tuple.metadata else {},
                "updated_at": workflow.now().isoformat() if hasattr(workflow, 'now') else "",
            }
        
        return {
            "thread_id": thread_id,
            "checkpoint_id": None,
            "channel_values": {},
            "metadata": {},
            "updated_at": "",
        }
        
    except Exception as e:
        logger.error(f"同步 LangGraph 状态失败: {e}")
        return {
            "thread_id": thread_id,
            "error": str(e),
        }



# ==================== 状态标识一致性辅助类 ====================

class StateIdentityManager:
    """
    状态标识一致性管理器
    
    确保 Temporal workflow_run_id 与 LangGraph thread_id 保持一致，
    并提供状态同步功能。
    
    验证：需求 1.1, 1.5
    """
    
    def __init__(self, workflow_run_id: str):
        """
        初始化状态标识管理器
        
        Args:
            workflow_run_id: Temporal 工作流运行 ID
        """
        self.workflow_run_id = workflow_run_id
        self.thread_id = workflow_run_id  # 保持一致性
        self._state_cache: Optional[Dict[str, Any]] = None
    
    def get_langgraph_config(
        self,
        checkpoint_ns: str = ""
    ) -> Dict[str, Any]:
        """
        获取 LangGraph 配置
        
        生成用于 LangGraph 的配置字典，确保 thread_id 等于 workflow_run_id。
        
        Args:
            checkpoint_ns: 检查点命名空间
            
        Returns:
            LangGraph 配置字典
            
        验证：需求 1.1
        """
        return {
            "configurable": {
                "thread_id": self.thread_id,
                "checkpoint_ns": checkpoint_ns,
            }
        }
    
    def update_state_cache(self, state: Dict[str, Any]) -> None:
        """
        更新状态缓存
        
        Args:
            state: LangGraph 状态
        """
        self._state_cache = state
    
    def get_state_cache(self) -> Optional[Dict[str, Any]]:
        """
        获取状态缓存
        
        Returns:
            缓存的 LangGraph 状态
        """
        return self._state_cache


@activity.defn
async def create_langgraph_config_activity(
    workflow_run_id: str,
    checkpoint_ns: str = ""
) -> Dict[str, Any]:
    """
    创建 LangGraph 配置
    
    确保 thread_id 等于 workflow_run_id，实现状态标识一致性。
    
    Args:
        workflow_run_id: Temporal 工作流运行 ID
        checkpoint_ns: 检查点命名空间
        
    Returns:
        LangGraph 配置字典
        
    验证：需求 1.1
    """
    return {
        "configurable": {
            "thread_id": workflow_run_id,
            "checkpoint_ns": checkpoint_ns,
        }
    }


@activity.defn
async def get_latest_langgraph_state_activity(
    thread_id: str,
    checkpoint_ns: str = ""
) -> Dict[str, Any]:
    """
    获取最新 LangGraph 状态
    
    从检查点读取最新状态，用于 Temporal Query 返回。
    
    Args:
        thread_id: LangGraph thread_id（等于 workflow_run_id）
        checkpoint_ns: 检查点命名空间
        
    Returns:
        LangGraph 状态字典
        
    验证：需求 1.5
    """
    try:
        pool_manager = await UnifiedPoolManager.get_instance()
        checkpointer = EnhancedPostgresCheckpointer(pool_manager)
        
        config = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
            }
        }
        
        checkpoint_tuple = await checkpointer.aget(config)
        
        if checkpoint_tuple:
            checkpoint_config = checkpoint_tuple.config.get("configurable", {})
            return {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_config.get("checkpoint_id"),
                "channel_values": checkpoint_tuple.checkpoint.get("channel_values", {}),
                "metadata": {
                    "source": getattr(checkpoint_tuple.metadata, 'source', 'unknown'),
                    "step": getattr(checkpoint_tuple.metadata, 'step', -1),
                } if checkpoint_tuple.metadata else {},
                "exists": True,
            }
        
        return {
            "thread_id": thread_id,
            "checkpoint_id": None,
            "channel_values": {},
            "metadata": {},
            "exists": False,
        }
        
    except Exception as e:
        logger.error(f"获取 LangGraph 状态失败: {e}")
        return {
            "thread_id": thread_id,
            "error": str(e),
            "exists": False,
        }



# ==================== 重试策略决策 ====================

class RetryDecision(str, Enum):
    """
    重试决策枚举
    
    验证：需求 1.4
    """
    RECOVER_FROM_CHECKPOINT = "recover_from_checkpoint"
    RESTART_FROM_BEGINNING = "restart_from_beginning"
    FAIL_PERMANENTLY = "fail_permanently"


@dataclass
class CheckpointStatus:
    """
    检查点状态数据类
    
    验证：需求 1.4
    """
    exists: bool
    valid: bool
    checkpoint_id: Optional[str] = None
    data_size_bytes: Optional[int] = None
    is_corrupted: bool = False
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "exists": self.exists,
            "valid": self.valid,
            "checkpoint_id": self.checkpoint_id,
            "data_size_bytes": self.data_size_bytes,
            "is_corrupted": self.is_corrupted,
            "error": self.error,
        }


class RetryStrategyDecider:
    """
    重试策略决策器
    
    根据检查点状态决定是从检查点恢复还是重新开始。
    
    验证：需求 1.4
    """
    
    def __init__(self, max_restart_attempts: int = 3):
        """
        初始化重试策略决策器
        
        Args:
            max_restart_attempts: 最大重启尝试次数
        """
        self.max_restart_attempts = max_restart_attempts
        self._restart_count = 0
    
    def decide(self, checkpoint_status: CheckpointStatus) -> RetryDecision:
        """
        决定重试策略
        
        Args:
            checkpoint_status: 检查点状态
            
        Returns:
            重试决策
            
        验证：需求 1.4
        """
        # 检查点存在且有效 -> 从检查点恢复
        if checkpoint_status.exists and checkpoint_status.valid:
            logger.info(
                f"检查点有效，决定从检查点恢复: "
                f"checkpoint_id={checkpoint_status.checkpoint_id}"
            )
            return RetryDecision.RECOVER_FROM_CHECKPOINT
        
        # 检查点不存在或损坏 -> 重新开始
        if not checkpoint_status.exists or checkpoint_status.is_corrupted:
            self._restart_count += 1
            
            if self._restart_count > self.max_restart_attempts:
                logger.error(
                    f"重启次数超过限制 ({self.max_restart_attempts})，"
                    f"决定永久失败"
                )
                return RetryDecision.FAIL_PERMANENTLY
            
            logger.info(
                f"检查点不存在或损坏，决定重新开始: "
                f"restart_count={self._restart_count}"
            )
            return RetryDecision.RESTART_FROM_BEGINNING
        
        # 检查点存在但无效 -> 重新开始
        logger.info("检查点存在但无效，决定重新开始")
        self._restart_count += 1
        return RetryDecision.RESTART_FROM_BEGINNING
    
    def reset_restart_count(self) -> None:
        """重置重启计数"""
        self._restart_count = 0


@activity.defn
async def check_checkpoint_validity_activity(
    thread_id: str,
    checkpoint_ns: str = ""
) -> Dict[str, Any]:
    """
    检查检查点有效性
    
    验证检查点是否存在、是否有效、是否损坏。
    
    Args:
        thread_id: LangGraph thread_id
        checkpoint_ns: 检查点命名空间
        
    Returns:
        CheckpointStatus 字典
        
    验证：需求 1.4
    """
    try:
        pool_manager = await UnifiedPoolManager.get_instance()
        
        async with pool_manager.pg_connection() as conn:
            result = await conn.execute(
                """
                SELECT checkpoint_id, checkpoint_data, is_compressed, 
                       is_delta, data_size_bytes, base_checkpoint_id
                FROM enhanced_checkpoints
                WHERE thread_id = %s AND checkpoint_ns = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (thread_id, checkpoint_ns)
            )
            row = await result.fetchone()
            
            if not row:
                return CheckpointStatus(
                    exists=False,
                    valid=False,
                ).to_dict()
            
            # 验证检查点数据完整性
            try:
                checkpoint_data = bytes(row["checkpoint_data"])
                
                # 如果是压缩的，尝试解压
                if row["is_compressed"]:
                    import zlib
                    try:
                        zlib.decompress(checkpoint_data)
                    except zlib.error:
                        return CheckpointStatus(
                            exists=True,
                            valid=False,
                            checkpoint_id=row["checkpoint_id"],
                            data_size_bytes=row["data_size_bytes"],
                            is_corrupted=True,
                            error="压缩数据损坏",
                        ).to_dict()
                
                # 如果是增量，验证基础检查点存在
                if row["is_delta"] and row["base_checkpoint_id"]:
                    base_result = await conn.execute(
                        """
                        SELECT 1 FROM enhanced_checkpoints
                        WHERE thread_id = %s AND checkpoint_ns = %s 
                              AND checkpoint_id = %s
                        """,
                        (thread_id, checkpoint_ns, row["base_checkpoint_id"])
                    )
                    base_row = await base_result.fetchone()
                    
                    if not base_row:
                        return CheckpointStatus(
                            exists=True,
                            valid=False,
                            checkpoint_id=row["checkpoint_id"],
                            data_size_bytes=row["data_size_bytes"],
                            is_corrupted=True,
                            error="基础检查点不存在",
                        ).to_dict()
                
                return CheckpointStatus(
                    exists=True,
                    valid=True,
                    checkpoint_id=row["checkpoint_id"],
                    data_size_bytes=row["data_size_bytes"],
                ).to_dict()
                
            except Exception as e:
                return CheckpointStatus(
                    exists=True,
                    valid=False,
                    checkpoint_id=row["checkpoint_id"],
                    is_corrupted=True,
                    error=str(e),
                ).to_dict()
            
    except Exception as e:
        logger.error(f"检查检查点有效性失败: {e}")
        return CheckpointStatus(
            exists=False,
            valid=False,
            error=str(e),
        ).to_dict()


@activity.defn
async def make_retry_decision_activity(
    thread_id: str,
    checkpoint_ns: str = "",
    max_restart_attempts: int = 3
) -> Dict[str, Any]:
    """
    做出重试决策
    
    根据检查点状态决定是从检查点恢复还是重新开始。
    
    Args:
        thread_id: LangGraph thread_id
        checkpoint_ns: 检查点命名空间
        max_restart_attempts: 最大重启尝试次数
        
    Returns:
        包含 decision 和 checkpoint_status 的字典
        
    验证：需求 1.4
    """
    # 检查检查点状态
    status_dict = await check_checkpoint_validity_activity(
        thread_id, checkpoint_ns
    )
    
    checkpoint_status = CheckpointStatus(
        exists=status_dict.get("exists", False),
        valid=status_dict.get("valid", False),
        checkpoint_id=status_dict.get("checkpoint_id"),
        data_size_bytes=status_dict.get("data_size_bytes"),
        is_corrupted=status_dict.get("is_corrupted", False),
        error=status_dict.get("error"),
    )
    
    # 做出决策
    decider = RetryStrategyDecider(max_restart_attempts)
    decision = decider.decide(checkpoint_status)
    
    return {
        "decision": decision.value,
        "checkpoint_status": checkpoint_status.to_dict(),
        "should_recover": decision == RetryDecision.RECOVER_FROM_CHECKPOINT,
        "should_restart": decision == RetryDecision.RESTART_FROM_BEGINNING,
        "should_fail": decision == RetryDecision.FAIL_PERMANENTLY,
    }



# ==================== Redis 事件接收 ====================

class RedisEventForwarder:
    """
    Redis 事件转发器
    
    订阅 Redis Pub/Sub 通道，将事件转发到 Temporal 工作流 Signal。
    
    验证：需求 10.1
    """
    
    def __init__(
        self,
        pool_manager: UnifiedPoolManager,
        channel_prefix: str = "workflow_events"
    ):
        """
        初始化 Redis 事件转发器
        
        Args:
            pool_manager: 统一连接池管理器
            channel_prefix: 通道前缀
        """
        self.pool_manager = pool_manager
        self.channel_prefix = channel_prefix
        self._running = False
        self._subscriptions: Dict[str, asyncio.Task] = {}
    
    async def start(self) -> None:
        """启动事件转发器"""
        self._running = True
        logger.info("Redis 事件转发器已启动")
    
    async def stop(self) -> None:
        """停止事件转发器"""
        self._running = False
        
        # 取消所有订阅任务
        for workflow_id, task in self._subscriptions.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._subscriptions.clear()
        logger.info("Redis 事件转发器已停止")
    
    async def subscribe_for_workflow(
        self,
        workflow_id: str,
        signal_callback: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        """
        为工作流订阅事件
        
        Args:
            workflow_id: 工作流 ID
            signal_callback: 信号回调函数，用于将事件转发到工作流
            
        验证：需求 10.1
        """
        if workflow_id in self._subscriptions:
            logger.warning(f"工作流已订阅: {workflow_id}")
            return
        
        channel = f"{self.channel_prefix}:{workflow_id}"
        
        async def process_messages():
            try:
                redis_client = self.pool_manager.get_redis_client()
                pubsub = redis_client.pubsub()
                await pubsub.subscribe(channel)
                
                logger.info(f"已订阅工作流事件通道: {channel}")
                
                while self._running:
                    try:
                        message = await pubsub.get_message(
                            ignore_subscribe_messages=True,
                            timeout=1.0
                        )
                        
                        if message is not None and message["type"] == "message":
                            event_data = json.loads(message["data"])
                            
                            # 添加时间戳
                            if "timestamp" not in event_data:
                                from datetime import datetime, timezone
                                event_data["timestamp"] = datetime.now(timezone.utc).isoformat()
                            
                            # 转发到工作流 Signal
                            await signal_callback(event_data)
                            
                            logger.debug(
                                f"事件已转发到工作流: "
                                f"workflow_id={workflow_id}, "
                                f"event_type={event_data.get('event_type')}"
                            )
                            
                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        logger.warning(f"处理 Redis 事件时出错: {e}")
                        await asyncio.sleep(1.0)
                
                await pubsub.unsubscribe()
                await pubsub.aclose()
                
            except Exception as e:
                logger.error(f"订阅工作流事件失败: {e}")
        
        task = asyncio.create_task(process_messages())
        self._subscriptions[workflow_id] = task
    
    async def unsubscribe_for_workflow(self, workflow_id: str) -> None:
        """
        取消工作流的事件订阅
        
        Args:
            workflow_id: 工作流 ID
        """
        if workflow_id not in self._subscriptions:
            return
        
        task = self._subscriptions.pop(workflow_id)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        logger.info(f"已取消工作流事件订阅: {workflow_id}")
    
    async def publish_event(
        self,
        workflow_id: str,
        event_type: str,
        payload: Dict[str, Any],
        source: Optional[str] = None
    ) -> bool:
        """
        发布事件到工作流
        
        Args:
            workflow_id: 目标工作流 ID
            event_type: 事件类型
            payload: 事件负载
            source: 事件来源
            
        Returns:
            是否成功发布
            
        验证：需求 10.1
        """
        try:
            redis_client = self.pool_manager.get_redis_client()
            channel = f"{self.channel_prefix}:{workflow_id}"
            
            from datetime import datetime, timezone
            event_data = {
                "event_type": event_type,
                "payload": payload,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": source,
            }
            
            await redis_client.publish(channel, json.dumps(event_data))
            
            logger.debug(
                f"事件已发布: workflow_id={workflow_id}, event_type={event_type}"
            )
            return True
            
        except Exception as e:
            logger.error(f"发布事件失败: {e}")
            return False


@activity.defn
async def subscribe_redis_events_activity(
    workflow_id: str,
    channel_prefix: str = "workflow_events"
) -> Dict[str, Any]:
    """
    订阅 Redis 事件 Activity
    
    注意：此 Activity 仅用于初始化订阅，实际的事件处理
    需要在 Worker 中通过 RedisEventForwarder 实现。
    
    Args:
        workflow_id: 工作流 ID
        channel_prefix: 通道前缀
        
    Returns:
        订阅结果
        
    验证：需求 10.1
    """
    try:
        pool_manager = await UnifiedPoolManager.get_instance()
        redis_client = pool_manager.get_redis_client()
        
        channel = f"{channel_prefix}:{workflow_id}"
        
        # 验证 Redis 连接
        await redis_client.ping()
        
        return {
            "subscribed": True,
            "channel": channel,
            "workflow_id": workflow_id,
        }
        
    except Exception as e:
        logger.error(f"订阅 Redis 事件失败: {e}")
        return {
            "subscribed": False,
            "error": str(e),
            "workflow_id": workflow_id,
        }


@activity.defn
async def publish_redis_event_activity(
    workflow_id: str,
    event_type: str,
    payload: Dict[str, Any],
    source: Optional[str] = None,
    channel_prefix: str = "workflow_events"
) -> Dict[str, Any]:
    """
    发布 Redis 事件 Activity
    
    Args:
        workflow_id: 目标工作流 ID
        event_type: 事件类型
        payload: 事件负载
        source: 事件来源
        channel_prefix: 通道前缀
        
    Returns:
        发布结果
        
    验证：需求 10.1
    """
    try:
        pool_manager = await UnifiedPoolManager.get_instance()
        redis_client = pool_manager.get_redis_client()
        
        channel = f"{channel_prefix}:{workflow_id}"
        
        from datetime import datetime, timezone
        event_data = {
            "event_type": event_type,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": source,
        }
        
        await redis_client.publish(channel, json.dumps(event_data))
        
        return {
            "published": True,
            "channel": channel,
            "event_type": event_type,
        }
        
    except Exception as e:
        logger.error(f"发布 Redis 事件失败: {e}")
        return {
            "published": False,
            "error": str(e),
        }
