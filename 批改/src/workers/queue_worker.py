"""基于队列的独立 Worker 进程

支持两种模式：
1. Redis 队列模式（生产环境）
2. 内存队列模式（离线/开发环境）

使用方法：
    # 启动 Worker（独立进程）
    python -m src.workers.queue_worker
    
    # 或指定并发数
    WORKER_CONCURRENCY=5 python -m src.workers.queue_worker
"""

import asyncio
import logging
import signal
import os
import json
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class Task:
    """任务定义"""
    task_id: str
    graph_name: str
    payload: Dict[str, Any]
    status: TaskStatus = TaskStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


class TaskQueue:
    """任务队列抽象基类"""
    
    async def push(self, task: Task) -> bool:
        raise NotImplementedError
    
    async def pop(self, timeout: float = 1.0) -> Optional[Task]:
        raise NotImplementedError
    
    async def complete(self, task_id: str, result: Dict[str, Any]) -> bool:
        raise NotImplementedError
    
    async def fail(self, task_id: str, error: str) -> bool:
        raise NotImplementedError
    
    async def get_status(self, task_id: str) -> Optional[Task]:
        raise NotImplementedError


class InMemoryTaskQueue(TaskQueue):
    """内存任务队列（离线模式）"""
    
    _instance = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._queue: asyncio.Queue = asyncio.Queue()
        self._tasks: Dict[str, Task] = {}
        self._results: Dict[str, Dict[str, Any]] = {}
        self._initialized = True
    
    async def push(self, task: Task) -> bool:
        async with self._lock:
            self._tasks[task.task_id] = task
            await self._queue.put(task.task_id)
            logger.info(f"任务入队: {task.task_id}")
            return True
    
    async def pop(self, timeout: float = 1.0) -> Optional[Task]:
        try:
            task_id = await asyncio.wait_for(
                self._queue.get(),
                timeout=timeout
            )
            task = self._tasks.get(task_id)
            if task:
                task.status = TaskStatus.RUNNING
                task.started_at = datetime.now()
            return task
        except asyncio.TimeoutError:
            return None
    
    async def complete(self, task_id: str, result: Dict[str, Any]) -> bool:
        async with self._lock:
            task = self._tasks.get(task_id)
            if task:
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.now()
                task.result = result
                self._results[task_id] = result
                logger.info(f"任务完成: {task_id}")
                return True
            return False
    
    async def fail(self, task_id: str, error: str) -> bool:
        async with self._lock:
            task = self._tasks.get(task_id)
            if task:
                task.retry_count += 1
                if task.retry_count < task.max_retries:
                    # 重试
                    task.status = TaskStatus.RETRYING
                    task.error = error
                    await self._queue.put(task_id)
                    logger.warning(f"任务重试 ({task.retry_count}/{task.max_retries}): {task_id}")
                else:
                    # 最终失败
                    task.status = TaskStatus.FAILED
                    task.completed_at = datetime.now()
                    task.error = error
                    logger.error(f"任务失败: {task_id}, error={error}")
                return True
            return False
    
    async def get_status(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)
    
    async def get_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self._results.get(task_id)


class RedisTaskQueue(TaskQueue):
    """Redis 任务队列（生产模式）"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self._redis = None
    
    async def _get_redis(self):
        if self._redis is None:
            import redis.asyncio as redis
            self._redis = redis.from_url(self.redis_url)
        return self._redis
    
    async def push(self, task: Task) -> bool:
        try:
            r = await self._get_redis()
            task_data = {
                "task_id": task.task_id,
                "graph_name": task.graph_name,
                "payload": task.payload,
                "status": task.status.value,
                "retry_count": task.retry_count,
                "max_retries": task.max_retries,
                "created_at": task.created_at.isoformat()
            }
            # 存储任务数据
            await r.hset(f"task:{task.task_id}", mapping={
                k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                for k, v in task_data.items()
            })
            # 推入队列
            await r.lpush("task_queue", task.task_id)
            return True
        except Exception as e:
            logger.error(f"Redis push 失败: {e}")
            return False
    
    async def pop(self, timeout: float = 1.0) -> Optional[Task]:
        try:
            r = await self._get_redis()
            result = await r.brpop("task_queue", timeout=int(timeout))
            if result:
                _, task_id = result
                task_id = task_id.decode() if isinstance(task_id, bytes) else task_id
                task_data = await r.hgetall(f"task:{task_id}")
                if task_data:
                    return Task(
                        task_id=task_id,
                        graph_name=task_data.get(b"graph_name", b"").decode(),
                        payload=json.loads(task_data.get(b"payload", b"{}")),
                        status=TaskStatus(task_data.get(b"status", b"pending").decode()),
                        retry_count=int(task_data.get(b"retry_count", b"0")),
                        max_retries=int(task_data.get(b"max_retries", b"3"))
                    )
            return None
        except Exception as e:
            logger.error(f"Redis pop 失败: {e}")
            return None
    
    async def complete(self, task_id: str, result: Dict[str, Any]) -> bool:
        try:
            r = await self._get_redis()
            await r.hset(f"task:{task_id}", mapping={
                "status": TaskStatus.COMPLETED.value,
                "completed_at": datetime.now().isoformat(),
                "result": json.dumps(result)
            })
            return True
        except Exception as e:
            logger.error(f"Redis complete 失败: {e}")
            return False
    
    async def fail(self, task_id: str, error: str) -> bool:
        try:
            r = await self._get_redis()
            task_data = await r.hgetall(f"task:{task_id}")
            retry_count = int(task_data.get(b"retry_count", b"0")) + 1
            max_retries = int(task_data.get(b"max_retries", b"3"))
            
            if retry_count < max_retries:
                await r.hset(f"task:{task_id}", mapping={
                    "status": TaskStatus.RETRYING.value,
                    "retry_count": str(retry_count),
                    "error": error
                })
                await r.lpush("task_queue", task_id)
            else:
                await r.hset(f"task:{task_id}", mapping={
                    "status": TaskStatus.FAILED.value,
                    "completed_at": datetime.now().isoformat(),
                    "error": error
                })
            return True
        except Exception as e:
            logger.error(f"Redis fail 失败: {e}")
            return False
    
    async def get_status(self, task_id: str) -> Optional[Task]:
        try:
            r = await self._get_redis()
            task_data = await r.hgetall(f"task:{task_id}")
            if task_data:
                return Task(
                    task_id=task_id,
                    graph_name=task_data.get(b"graph_name", b"").decode(),
                    payload=json.loads(task_data.get(b"payload", b"{}")),
                    status=TaskStatus(task_data.get(b"status", b"pending").decode()),
                    retry_count=int(task_data.get(b"retry_count", b"0"))
                )
            return None
        except Exception as e:
            logger.error(f"Redis get_status 失败: {e}")
            return None


# 全局队列实例
_task_queue: Optional[TaskQueue] = None


def get_task_queue() -> TaskQueue:
    """获取任务队列实例"""
    global _task_queue
    if _task_queue is None:
        redis_url = os.getenv("REDIS_URL")
        offline_mode = os.getenv("OFFLINE_MODE", "false").lower() == "true"
        
        if redis_url and not offline_mode:
            _task_queue = RedisTaskQueue(redis_url)
            logger.info("使用 Redis 任务队列")
        else:
            _task_queue = InMemoryTaskQueue()
            logger.info("使用内存任务队列（离线模式）")
    
    return _task_queue



class QueueWorker:
    """基于队列的独立 Worker
    
    特性：
    1. 独立进程运行
    2. 自动重试失败任务
    3. 支持并发执行
    4. 优雅关闭
    5. 健康检查
    """
    
    def __init__(
        self,
        concurrency: int = 5,
        poll_interval: float = 0.5
    ):
        self.concurrency = concurrency
        self.poll_interval = poll_interval
        self.queue = get_task_queue()
        self._running = False
        self._shutdown_event = asyncio.Event()
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self._graphs: Dict[str, Any] = {}
    
    def _register_graphs(self):
        """注册所有 Graphs"""
        from src.graphs import (
            create_exam_paper_graph,
            create_batch_grading_graph,
            create_rule_upgrade_graph
        )
        
        self._graphs["exam_paper"] = create_exam_paper_graph()
        self._graphs["batch_grading"] = create_batch_grading_graph()
        self._graphs["rule_upgrade"] = create_rule_upgrade_graph()
        
        logger.info(f"已注册 {len(self._graphs)} 个 Graphs")
    
    async def start(self):
        """启动 Worker"""
        logger.info("=" * 60)
        logger.info(f"Queue Worker 启动 (PID: {os.getpid()})")
        logger.info(f"并发数: {self.concurrency}")
        logger.info(f"轮询间隔: {self.poll_interval}s")
        logger.info("=" * 60)
        
        # 注册 Graphs
        self._register_graphs()
        
        # 设置信号处理
        self._setup_signal_handlers()
        
        # 开始处理
        self._running = True
        await self._process_loop()
    
    def _setup_signal_handlers(self):
        """设置信号处理"""
        loop = asyncio.get_event_loop()
        
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(
                    sig,
                    lambda: asyncio.create_task(self._shutdown())
                )
            except NotImplementedError:
                # Windows 不支持 add_signal_handler
                pass
    
    async def _shutdown(self):
        """优雅关闭"""
        logger.info("收到关闭信号，开始优雅关闭...")
        self._running = False
        self._shutdown_event.set()
        
        # 等待活跃任务完成
        if self._active_tasks:
            logger.info(f"等待 {len(self._active_tasks)} 个任务完成...")
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._active_tasks.values(), return_exceptions=True),
                    timeout=30.0
                )
            except asyncio.TimeoutError:
                logger.warning("等待超时，取消剩余任务")
                for task in self._active_tasks.values():
                    task.cancel()
        
        logger.info("Worker 已关闭")
    
    async def _process_loop(self):
        """主处理循环"""
        logger.info("开始处理任务...")
        
        while self._running:
            try:
                # 检查并发槽位
                available_slots = self.concurrency - len(self._active_tasks)
                
                if available_slots > 0:
                    # 获取任务
                    task = await self.queue.pop(timeout=self.poll_interval)
                    
                    if task:
                        # 启动任务执行
                        asyncio_task = asyncio.create_task(
                            self._execute_task(task)
                        )
                        self._active_tasks[task.task_id] = asyncio_task
                        
                        # 任务完成后清理
                        asyncio_task.add_done_callback(
                            lambda t, tid=task.task_id: self._active_tasks.pop(tid, None)
                        )
                else:
                    # 没有空闲槽位，等待
                    await asyncio.sleep(self.poll_interval)
                
            except Exception as e:
                logger.error(f"处理循环错误: {e}")
                await asyncio.sleep(self.poll_interval)
    
    async def _execute_task(self, task: Task):
        """执行单个任务"""
        logger.info(f"开始执行任务: {task.task_id}, graph={task.graph_name}")
        
        try:
            # 获取 Graph
            graph = self._graphs.get(task.graph_name)
            if not graph:
                raise ValueError(f"未注册的 Graph: {task.graph_name}")
            
            # 配置
            config = {
                "configurable": {
                    "thread_id": task.task_id
                }
            }
            
            # 执行 Graph
            result = {}
            async for event in graph.astream_events(task.payload, config=config, version="v2"):
                event_kind = event.get("event")
                event_name = event.get("name", "")
                event_data = event.get("data", {})
                
                # 累积结果
                if event_kind == "on_chain_end":
                    output = event_data.get("output", {})
                    if isinstance(output, dict):
                        for key, value in output.items():
                            if key in result and isinstance(result[key], list) and isinstance(value, list):
                                result[key].extend(value)
                            else:
                                result[key] = value
            
            # 标记完成
            await self.queue.complete(task.task_id, result)
            logger.info(f"任务完成: {task.task_id}")
            
        except Exception as e:
            logger.error(f"任务执行失败: {task.task_id}, error={e}")
            await self.queue.fail(task.task_id, str(e))
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return {
            "status": "healthy" if self._running else "stopped",
            "pid": os.getpid(),
            "active_tasks": len(self._active_tasks),
            "concurrency": self.concurrency,
            "queue_type": type(self.queue).__name__
        }


async def submit_task(
    graph_name: str,
    payload: Dict[str, Any],
    task_id: Optional[str] = None
) -> str:
    """提交任务到队列
    
    Args:
        graph_name: Graph 名称
        payload: 任务数据
        task_id: 任务 ID（可选，自动生成）
        
    Returns:
        task_id: 任务 ID
    """
    queue = get_task_queue()
    
    if task_id is None:
        task_id = str(uuid.uuid4())
    
    task = Task(
        task_id=task_id,
        graph_name=graph_name,
        payload=payload
    )
    
    await queue.push(task)
    return task_id


async def get_task_status(task_id: str) -> Optional[Task]:
    """获取任务状态"""
    queue = get_task_queue()
    return await queue.get_status(task_id)


async def get_task_result(task_id: str) -> Optional[Dict[str, Any]]:
    """获取任务结果"""
    queue = get_task_queue()
    if isinstance(queue, InMemoryTaskQueue):
        return await queue.get_result(task_id)
    else:
        task = await queue.get_status(task_id)
        return task.result if task else None


async def main():
    """主函数"""
    concurrency = int(os.getenv("WORKER_CONCURRENCY", "5"))
    poll_interval = float(os.getenv("WORKER_POLL_INTERVAL", "0.5"))
    
    worker = QueueWorker(
        concurrency=concurrency,
        poll_interval=poll_interval
    )
    
    await worker.start()


if __name__ == "__main__":
    # Windows 兼容性
    import sys
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main())
