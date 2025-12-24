"""LangGraph Worker

后台执行 LangGraph Graph 的 Worker 进程。
替代 Temporal Worker，提供持久化执行能力。

使用方法：
    python -m src.workers.langgraph_worker
"""

import asyncio
import logging
import signal
import os
from typing import Optional
from datetime import datetime

from src.orchestration.langgraph_orchestrator import LangGraphOrchestrator
from src.graphs import (
    create_exam_paper_graph,
    create_batch_grading_graph,
    create_rule_upgrade_graph
)
from src.utils.database import get_db_pool


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class LangGraphWorker:
    """LangGraph Worker
    
    轮询数据库中的 pending runs，执行 Graph。
    支持优雅关闭和崩溃恢复。
    """
    
    def __init__(
        self,
        poll_interval: float = 1.0,
        max_concurrent_runs: int = 10
    ):
        """初始化 Worker
        
        Args:
            poll_interval: 轮询间隔（秒）
            max_concurrent_runs: 最大并发 run 数
        """
        self.poll_interval = poll_interval
        self.max_concurrent_runs = max_concurrent_runs
        self.orchestrator: Optional[LangGraphOrchestrator] = None
        self._running = False
        self._current_runs: set = set()
        self._shutdown_event = asyncio.Event()
    
    async def start(self):
        """启动 Worker"""
        logger.info("=" * 60)
        logger.info("LangGraph Worker 启动")
        logger.info(f"轮询间隔: {self.poll_interval}s")
        logger.info(f"最大并发: {self.max_concurrent_runs}")
        logger.info("=" * 60)
        
        # 初始化数据库连接
        db_pool = await get_db_pool()
        if db_pool is None:
            raise RuntimeError("数据库连接池初始化失败")
        
        # 初始化 Orchestrator
        self.orchestrator = LangGraphOrchestrator(db_pool=db_pool)
        
        # 注册 Graphs
        self._register_graphs()
        
        # 恢复中断的 runs
        await self._recover_interrupted_runs()
        
        # 设置信号处理
        self._setup_signal_handlers()
        
        # 开始轮询
        self._running = True
        await self._poll_loop()
    
    def _register_graphs(self):
        """注册所有 Graphs"""
        logger.info("注册 Graphs...")
        
        self.orchestrator.register_graph(
            "exam_paper",
            create_exam_paper_graph()
        )
        self.orchestrator.register_graph(
            "batch_grading",
            create_batch_grading_graph()
        )
        self.orchestrator.register_graph(
            "rule_upgrade",
            create_rule_upgrade_graph()
        )
        
        logger.info("已注册 3 个 Graphs")
    
    async def _recover_interrupted_runs(self):
        """恢复中断的 runs"""
        logger.info("检查中断的 runs...")
        
        try:
            # 查询 running 状态的 runs（可能是 Worker 崩溃导致）
            from src.orchestration.base import RunStatus
            
            running_runs = await self.orchestrator.list_runs(
                status=RunStatus.RUNNING,
                limit=100
            )
            
            if running_runs:
                logger.info(f"发现 {len(running_runs)} 个中断的 runs")
                
                for run_info in running_runs:
                    logger.info(f"恢复 run: {run_info.run_id}")
                    # 重新启动（Orchestrator 会从 checkpoint 恢复）
                    try:
                        await self.orchestrator.retry(run_info.run_id)
                    except Exception as e:
                        logger.error(f"恢复失败: {run_info.run_id}, error={e}")
            else:
                logger.info("没有中断的 runs")
                
        except Exception as e:
            logger.error(f"恢复检查失败: {e}")
    
    def _setup_signal_handlers(self):
        """设置信号处理"""
        loop = asyncio.get_event_loop()
        
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(
                sig,
                lambda: asyncio.create_task(self._shutdown())
            )
    
    async def _shutdown(self):
        """优雅关闭"""
        logger.info("收到关闭信号，开始优雅关闭...")
        self._running = False
        self._shutdown_event.set()
        
        # 等待当前 runs 完成（最多 30 秒）
        if self._current_runs:
            logger.info(f"等待 {len(self._current_runs)} 个 runs 完成...")
            try:
                await asyncio.wait_for(
                    self._wait_for_runs(),
                    timeout=30.0
                )
            except asyncio.TimeoutError:
                logger.warning("等待超时，强制关闭")
        
        logger.info("Worker 已关闭")
    
    async def _wait_for_runs(self):
        """等待所有 runs 完成"""
        while self._current_runs:
            await asyncio.sleep(0.5)
    
    async def _poll_loop(self):
        """轮询循环"""
        logger.info("开始轮询 pending runs...")
        
        while self._running:
            try:
                # 检查是否有空闲槽位
                available_slots = self.max_concurrent_runs - len(self._current_runs)
                
                if available_slots > 0:
                    # 查询 pending runs
                    pending_runs = await self._get_pending_runs(limit=available_slots)
                    
                    for run in pending_runs:
                        # 启动执行
                        asyncio.create_task(
                            self._execute_run(run["run_id"], run["graph_name"])
                        )
                
                # 等待下一次轮询
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=self.poll_interval
                    )
                    break  # 收到关闭信号
                except asyncio.TimeoutError:
                    pass  # 正常超时，继续轮询
                    
            except Exception as e:
                logger.error(f"轮询错误: {e}")
                await asyncio.sleep(self.poll_interval)
    
    async def _get_pending_runs(self, limit: int) -> list:
        """获取 pending runs"""
        try:
            rows = await self.orchestrator.db_pool.fetch(
                """
                SELECT run_id, graph_name, input_data
                FROM runs
                WHERE status = 'pending'
                ORDER BY created_at ASC
                LIMIT $1
                """,
                limit
            )
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"查询 pending runs 失败: {e}")
            return []
    
    async def _execute_run(self, run_id: str, graph_name: str):
        """执行单个 run"""
        self._current_runs.add(run_id)
        
        try:
            logger.info(f"开始执行: run_id={run_id}, graph={graph_name}")
            
            # 获取 Graph
            compiled_graph = self.orchestrator._graph_registry.get(graph_name)
            if not compiled_graph:
                raise ValueError(f"未注册的 Graph: {graph_name}")
            
            # 获取输入数据
            row = await self.orchestrator.db_pool.fetchrow(
                "SELECT input_data FROM runs WHERE run_id = $1",
                run_id
            )
            
            if not row:
                raise ValueError(f"Run 不存在: {run_id}")
            
            import json
            payload = json.loads(row["input_data"]) if row["input_data"] else {}
            
            # 执行 Graph
            await self.orchestrator._run_graph_background(
                run_id=run_id,
                graph_name=graph_name,
                compiled_graph=compiled_graph,
                payload=payload
            )
            
            logger.info(f"执行完成: run_id={run_id}")
            
        except Exception as e:
            logger.error(f"执行失败: run_id={run_id}, error={e}")
            
            # 更新状态为 failed
            await self.orchestrator._update_run_status(
                run_id,
                "failed",
                error=str(e)
            )
        finally:
            self._current_runs.discard(run_id)


async def main():
    """主函数"""
    # 从环境变量读取配置
    poll_interval = float(os.getenv("WORKER_POLL_INTERVAL", "1.0"))
    max_concurrent = int(os.getenv("WORKER_MAX_CONCURRENT", "10"))
    
    worker = LangGraphWorker(
        poll_interval=poll_interval,
        max_concurrent_runs=max_concurrent
    )
    
    await worker.start()


if __name__ == "__main__":
    asyncio.run(main())
