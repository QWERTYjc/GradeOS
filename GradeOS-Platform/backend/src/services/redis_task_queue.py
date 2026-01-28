"""
Redis 任务队列服务

用于高并发批改任务的分布式处理。

Features:
- 异步任务队列
- 任务状态追踪
- 进度更新
- 结果缓存
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
import uuid

try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    aioredis = None  # type: ignore
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskInfo:
    """任务信息"""
    task_id: str
    task_type: str
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    message: str = ""
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status.value,
            "progress": self.progress,
            "message": self.message,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskInfo":
        return cls(
            task_id=data["task_id"],
            task_type=data["task_type"],
            status=TaskStatus(data["status"]),
            progress=data.get("progress", 0.0),
            message=data.get("message", ""),
            result=data.get("result"),
            error=data.get("error"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            metadata=data.get("metadata", {}),
        )


class RedisTaskQueue:
    """
    Redis 任务队列

    用于高并发批改任务的分布式处理。
    """

    # Redis key 前缀
    TASK_KEY_PREFIX = "gradeos:task:"
    QUEUE_KEY = "gradeos:task_queue"
    RESULT_KEY_PREFIX = "gradeos:result:"
    PROGRESS_CHANNEL = "gradeos:progress"

    def __init__(
        self,
        redis_url: Optional[str] = None,
        max_workers: int = 5,
        task_timeout: int = 3600,  # 1 hour
        result_ttl: int = 86400,  # 24 hours
    ):
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self.max_workers = max_workers
        self.task_timeout = task_timeout
        self.result_ttl = result_ttl

        self._redis: Optional[Any] = None
        self._workers: List[asyncio.Task[None]] = []
        self._handlers: Dict[str, Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]] = {}
        self._running = False
        self._local_tasks: Dict[str, TaskInfo] = {}  # 本地任务存储（无 Redis 时使用）

    async def connect(self) -> bool:
        """连接 Redis"""
        if not REDIS_AVAILABLE:
            logger.warning("[RedisTaskQueue] Redis 库不可用，使用本地模式")
            return False

        try:
            self._redis = aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            await self._redis.ping()
            logger.info(f"[RedisTaskQueue] 已连接到 Redis: {self.redis_url}")
            return True
        except Exception as e:
            logger.warning(f"[RedisTaskQueue] Redis 连接失败: {e}，使用本地模式")
            self._redis = None
            return False

    async def disconnect(self) -> None:
        """断开 Redis 连接"""
        if self._redis:
            await self._redis.close()
            self._redis = None
            logger.info("[RedisTaskQueue] 已断开 Redis 连接")

    def register_handler(
        self,
        task_type: str,
        handler: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]],
    ) -> None:
        """注册任务处理器"""
        self._handlers[task_type] = handler
        logger.info(f"[RedisTaskQueue] 已注册处理器: {task_type}")

    async def submit_task(
        self,
        task_type: str,
        payload: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        提交任务

        Returns:
            task_id: 任务 ID
        """
        task_id = str(uuid.uuid4())
        task_info = TaskInfo(
            task_id=task_id,
            task_type=task_type,
            metadata=metadata or {},
        )

        if self._redis:
            # 存储任务信息
            await self._redis.set(
                f"{self.TASK_KEY_PREFIX}{task_id}",
                json.dumps(task_info.to_dict()),
                ex=self.task_timeout,
            )

            # 添加到队列
            await self._redis.lpush(
                self.QUEUE_KEY,
                json.dumps({"task_id": task_id, "payload": payload}),
            )

            logger.info(f"[RedisTaskQueue] 任务已提交到 Redis: {task_id}")
        else:
            # 本地模式
            self._local_tasks[task_id] = task_info

            # 直接执行
            asyncio.create_task(self._execute_task_local(task_id, task_type, payload))

            logger.info(f"[RedisTaskQueue] 任务已提交到本地队列: {task_id}")

        return task_id

    async def get_task_status(self, task_id: str) -> Optional[TaskInfo]:
        """获取任务状态"""
        if self._redis:
            data = await self._redis.get(f"{self.TASK_KEY_PREFIX}{task_id}")
            if data:
                return TaskInfo.from_dict(json.loads(data))
        else:
            return self._local_tasks.get(task_id)

        return None

    async def update_task_progress(
        self,
        task_id: str,
        progress: float,
        message: str = "",
    ) -> None:
        """更新任务进度"""
        task_info = await self.get_task_status(task_id)
        if not task_info:
            return

        task_info.progress = progress
        task_info.message = message

        if self._redis:
            await self._redis.set(
                f"{self.TASK_KEY_PREFIX}{task_id}",
                json.dumps(task_info.to_dict()),
                ex=self.task_timeout,
            )

            # 发布进度更新
            await self._redis.publish(
                self.PROGRESS_CHANNEL,
                json.dumps({
                    "task_id": task_id,
                    "progress": progress,
                    "message": message,
                }),
            )
        else:
            self._local_tasks[task_id] = task_info

    async def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务结果"""
        if self._redis:
            data = await self._redis.get(f"{self.RESULT_KEY_PREFIX}{task_id}")
            if data:
                return json.loads(data)
        else:
            task_info = self._local_tasks.get(task_id)
            if task_info:
                return task_info.result

        return None


    async def _execute_task_local(
        self,
        task_id: str,
        task_type: str,
        payload: Dict[str, Any],
    ) -> None:
        """本地执行任务"""
        task_info = self._local_tasks.get(task_id)
        if not task_info:
            return

        handler = self._handlers.get(task_type)
        if not handler:
            task_info.status = TaskStatus.FAILED
            task_info.error = f"未知任务类型: {task_type}"
            return

        try:
            task_info.status = TaskStatus.RUNNING
            task_info.started_at = datetime.now().isoformat()

            result = await handler(payload)

            task_info.status = TaskStatus.COMPLETED
            task_info.result = result
            task_info.progress = 1.0
            task_info.completed_at = datetime.now().isoformat()

        except Exception as e:
            task_info.status = TaskStatus.FAILED
            task_info.error = str(e)
            task_info.completed_at = datetime.now().isoformat()
            logger.error(f"[RedisTaskQueue] 任务执行失败: {task_id}, {e}")

    async def start_workers(self) -> None:
        """启动工作进程"""
        if not self._redis:
            logger.info("[RedisTaskQueue] 本地模式，无需启动工作进程")
            return

        self._running = True

        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker_loop(i))
            self._workers.append(worker)

        logger.info(f"[RedisTaskQueue] 已启动 {self.max_workers} 个工作进程")

    async def stop_workers(self) -> None:
        """停止工作进程"""
        self._running = False

        for worker in self._workers:
            worker.cancel()

        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

        logger.info("[RedisTaskQueue] 已停止所有工作进程")

    async def _worker_loop(self, worker_id: int) -> None:
        """工作进程循环"""
        logger.info(f"[RedisTaskQueue] 工作进程 {worker_id} 已启动")

        while self._running:
            try:
                if not self._redis:
                    break

                # 从队列获取任务（阻塞等待）
                result = await self._redis.brpop(self.QUEUE_KEY, timeout=5)

                if not result:
                    continue

                _, task_data = result
                task_info_data = json.loads(task_data)
                task_id = task_info_data["task_id"]
                payload = task_info_data["payload"]

                # 获取任务详情
                task_status = await self.get_task_status(task_id)
                if not task_status:
                    continue

                task_type = task_status.task_type
                handler = self._handlers.get(task_type)

                if not handler:
                    await self._mark_task_failed(task_id, f"未知任务类型: {task_type}")
                    continue

                # 执行任务
                await self._execute_task(task_id, handler, payload)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[RedisTaskQueue] 工作进程 {worker_id} 错误: {e}")
                await asyncio.sleep(1)

        logger.info(f"[RedisTaskQueue] 工作进程 {worker_id} 已停止")

    async def _execute_task(
        self,
        task_id: str,
        handler: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]],
        payload: Dict[str, Any],
    ) -> None:
        """执行任务"""
        try:
            if not self._redis:
                return

            # 更新状态为运行中
            task_info = await self.get_task_status(task_id)
            if task_info:
                task_info.status = TaskStatus.RUNNING
                task_info.started_at = datetime.now().isoformat()
                await self._redis.set(
                    f"{self.TASK_KEY_PREFIX}{task_id}",
                    json.dumps(task_info.to_dict()),
                    ex=self.task_timeout,
                )

            # 执行处理器
            result = await handler(payload)

            # 更新状态为完成
            task_info = await self.get_task_status(task_id)
            if task_info:
                task_info.status = TaskStatus.COMPLETED
                task_info.result = result
                task_info.progress = 1.0
                task_info.completed_at = datetime.now().isoformat()

                await self._redis.set(
                    f"{self.TASK_KEY_PREFIX}{task_id}",
                    json.dumps(task_info.to_dict()),
                    ex=self.task_timeout,
                )

                # 存储结果
                await self._redis.set(
                    f"{self.RESULT_KEY_PREFIX}{task_id}",
                    json.dumps(result),
                    ex=self.result_ttl,
                )

            logger.info(f"[RedisTaskQueue] 任务完成: {task_id}")

        except Exception as e:
            await self._mark_task_failed(task_id, str(e))
            logger.error(f"[RedisTaskQueue] 任务失败: {task_id}, {e}")

    async def _mark_task_failed(self, task_id: str, error: str) -> None:
        """标记任务失败"""
        task_info = await self.get_task_status(task_id)
        if task_info:
            task_info.status = TaskStatus.FAILED
            task_info.error = error
            task_info.completed_at = datetime.now().isoformat()

            if self._redis:
                await self._redis.set(
                    f"{self.TASK_KEY_PREFIX}{task_id}",
                    json.dumps(task_info.to_dict()),
                    ex=self.task_timeout,
                )
            else:
                self._local_tasks[task_id] = task_info


# 全局实例
_task_queue: Optional[RedisTaskQueue] = None


def get_task_queue() -> RedisTaskQueue:
    """获取任务队列实例"""
    global _task_queue
    if _task_queue is None:
        _task_queue = RedisTaskQueue()
    return _task_queue


async def init_task_queue() -> RedisTaskQueue:
    """初始化任务队列"""
    queue = get_task_queue()
    await queue.connect()
    await queue.start_workers()
    return queue


async def shutdown_task_queue() -> None:
    """关闭任务队列"""
    global _task_queue
    if _task_queue:
        await _task_queue.stop_workers()
        await _task_queue.disconnect()
        _task_queue = None


__all__ = [
    "TaskStatus",
    "TaskInfo",
    "RedisTaskQueue",
    "get_task_queue",
    "init_task_queue",
    "shutdown_task_queue",
]
