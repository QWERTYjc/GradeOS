"""
增强型 Temporal 工作流

提供 Redis 事件接收、分布式锁、进度查询和并发控制的增强工作流混入类。
此文件已清理，移除了 Activity 定义和非确定性导入，以满足 Temporal 工作流沙箱要求。

验证：需求 1.1, 1.4, 1.5, 10.1, 10.2, 10.3, 10.4
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

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
    """工作流进度数据类"""
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
class LangGraphState:
    """LangGraph 状态快照"""
    thread_id: str
    checkpoint_id: Optional[str]
    channel_values: Dict[str, Any]
    metadata: Dict[str, Any]
    updated_at: str

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
        """查询当前进度"""
        return self._progress
    
    @workflow.query
    def get_langgraph_state(self) -> Optional[Dict[str, Any]]:
        """查询 LangGraph 状态快照"""
        return self._langgraph_state
    
    @workflow.query
    def get_external_events(self) -> List[Dict[str, Any]]:
        """查询已接收的外部事件"""
        return self._external_events
    
    @workflow.query
    def get_held_locks(self) -> Dict[str, str]:
        """查询当前持有的分布式锁"""
        return self._held_locks.copy()
    
    # ==================== Signal 方法 ====================
    
    @workflow.signal
    def external_event(self, event: Dict[str, Any]) -> None:
        """接收外部事件"""
        logger.info(f"收到外部事件: {event.get('event_type', 'unknown')}")
        self._external_events.append(event)
        self._event_received = True
    
    @workflow.signal
    def update_langgraph_state(self, state: Dict[str, Any]) -> None:
        """更新 LangGraph 状态快照"""
        self._langgraph_state = state
        logger.debug(f"LangGraph 状态已更新: checkpoint_id={state.get('checkpoint_id')}")
    
    @workflow.signal
    def lock_acquired(self, resource_id: str, lock_token: str) -> None:
        """通知锁已获取"""
        self._held_locks[resource_id] = lock_token
        logger.debug(f"锁已获取: resource_id={resource_id}")
    
    @workflow.signal
    def lock_released(self, resource_id: str) -> None:
        """通知锁已释放"""
        self._held_locks.pop(resource_id, None)
        logger.debug(f"锁已释放: resource_id={resource_id}")
    
    # ==================== 进度管理方法 ====================
    
    def update_progress(
        self,
        stage: str,
        percentage: float,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """更新进度信息"""
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
        """等待外部事件"""
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
        """获取 LangGraph thread_id"""
        return workflow.info().run_id
    
    def get_workflow_run_id(self) -> str:
        """获取工作流运行 ID"""
        return workflow.info().run_id
    
    def get_workflow_id(self) -> str:
        """获取工作流 ID"""
        return workflow.info().workflow_id

    # ==================== 重试策略决策方法 ====================
    
    async def should_recover_from_checkpoint(
        self,
        thread_id: str,
        checkpoint_ns: str = ""
    ) -> bool:
        """决定是否从检查点恢复"""
        result = await workflow.execute_activity(
            "check_checkpoint_exists_activity",
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
        """获取分布式锁"""
        lock_token = str(uuid.uuid4())
        
        result = await workflow.execute_activity(
            "acquire_lock_activity",
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
        """释放分布式锁"""
        lock_token = self._held_locks.get(resource_id)
        if not lock_token:
            logger.warning(f"尝试释放未持有的锁: resource_id={resource_id}")
            return False
        
        result = await workflow.execute_activity(
            "release_lock_activity",
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
        """分布式锁上下文管理器"""
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
        """批量启动子工作流，限制并发"""
        if not inputs:
            return []
        
        semaphore = asyncio.Semaphore(max_concurrent)
        results: List[Any] = [None] * len(inputs)
        errors: List[Optional[Exception]] = [None] * len(inputs)
        
        async def run_child(index: int, input_data: Any) -> None:
            async with semaphore:
                try:
                    child_id = f"{id_prefix or self.get_workflow_id()}_{index}"
                    handle = await workflow.start_child_workflow(
                        workflow_class,
                        input_data,
                        id=child_id,
                        task_queue=task_queue or workflow.info().task_queue,
                    )
                    result = await handle.result()
                    results[index] = result
                    
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
        
        tasks = [
            asyncio.create_task(run_child(i, input_data))
            for i, input_data in enumerate(inputs)
        ]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        failed_indices = [i for i, e in enumerate(errors) if e is not None]
        if failed_indices:
            logger.warning(f"部分子工作流失败: indices={failed_indices}")
        
        return results

# ==================== 状态标识一致性辅助类 ====================

class StateIdentityManager:
    """状态标识一致性管理器"""
    
    def __init__(self, workflow_run_id: str):
        self.workflow_run_id = workflow_run_id
        self.thread_id = workflow_run_id
        self._state_cache: Optional[Dict[str, Any]] = None
    
    def get_langgraph_config(self, checkpoint_ns: str = "") -> Dict[str, Any]:
        return {
            "configurable": {
                "thread_id": self.thread_id,
                "checkpoint_ns": checkpoint_ns,
            }
        }
    
    def update_state_cache(self, state: Dict[str, Any]) -> None:
        self._state_cache = state
    
    def get_state_cache(self) -> Optional[Dict[str, Any]]:
        return self._state_cache

# ==================== 重试策略决策 ====================

class RetryDecision(str, Enum):
    """重试决策枚举"""
    RECOVER_FROM_CHECKPOINT = "recover_from_checkpoint"
    RESTART_FROM_BEGINNING = "restart_from_beginning"
    FAIL_PERMANENTLY = "fail_permanently"

@dataclass
class CheckpointStatus:
    """检查点状态数据类"""
    exists: bool
    valid: bool
    checkpoint_id: Optional[str] = None
    data_size_bytes: Optional[int] = None
    is_corrupted: bool = False
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "exists": self.exists,
            "valid": self.valid,
            "checkpoint_id": self.checkpoint_id,
            "data_size_bytes": self.data_size_bytes,
            "is_corrupted": self.is_corrupted,
            "error": self.error,
        }

class RetryStrategyDecider:
    """重试策略决策器"""
    
    def __init__(self, max_restart_attempts: int = 3):
        self.max_restart_attempts = max_restart_attempts
        self._restart_count = 0
    
    def decide(self, checkpoint_status: CheckpointStatus) -> RetryDecision:
        if checkpoint_status.exists and checkpoint_status.valid:
            return RetryDecision.RECOVER_FROM_CHECKPOINT
        
        if not checkpoint_status.exists or checkpoint_status.is_corrupted:
            self._restart_count += 1
            if self._restart_count > self.max_restart_attempts:
                return RetryDecision.FAIL_PERMANENTLY
            return RetryDecision.RESTART_FROM_BEGINNING
        
        self._restart_count += 1
        return RetryDecision.RESTART_FROM_BEGINNING
    
    def reset_restart_count(self) -> None:
        self._restart_count = 0
