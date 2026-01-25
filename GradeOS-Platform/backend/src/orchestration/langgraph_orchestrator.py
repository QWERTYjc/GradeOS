"""LangGraph Orchestrator 实现

实现 Orchestrator 抽象接口，使用 LangGraph 作为编排引擎。
支持后台执行、状态查询、取消、重试、人工介入等能力。

验证：需求 1.1, 1.2, 1.3, 1.4, 1.5, 1.6
"""

import logging
import uuid
import asyncio
import os
from typing import Any, Dict, List, Optional
from datetime import datetime
import json

from langgraph.graph import StateGraph
from langgraph.types import Command, interrupt

# 可选导入 - 支持离线模式
try:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    import asyncpg
except ImportError:
    AsyncPostgresSaver = None
    asyncpg = None

from src.orchestration.base import Orchestrator, RunStatus, RunInfo


logger = logging.getLogger(__name__)
DEBUG_LOG_PATH = os.getenv("GRADEOS_DEBUG_LOG_PATH")


def _write_debug_log(payload: Dict[str, Any]) -> None:
    if not DEBUG_LOG_PATH:
        return
    try:
        with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.debug(f"Failed to write debug log: {exc}")


class LangGraphOrchestrator(Orchestrator):
    """LangGraph 编排器实现
    
    使用 LangGraph 作为编排引擎，实现 Orchestrator 接口。
    将 LangGraph 的 Graph 概念映射到 Orchestrator 的 Run 概念。
    
    特性：
    - 持久化执行（PostgresSaver）
    - 后台运行（asyncio.create_task）
    - 状态查询（checkpointer.get）
    - 取消/重试（run 表管理）
    - 人工介入（interrupt + resume）
    
    验证：需求 1.1, 1.2, 1.3, 1.4, 1.5, 1.6
    """
    
    def __init__(
        self,
        db_pool: Optional[Any] = None,  # 改为 Any 以支持离线模式
        checkpointer: Optional[Any] = None,
        offline_mode: bool = False
    ):
        """初始化 LangGraph Orchestrator
        
        Args:
            db_pool: PostgreSQL 连接池（用于 run/attempt 表，可选）
            checkpointer: LangGraph Checkpointer（用于状态持久化，可选）
            offline_mode: 是否强制使用离线模式（跳过所有数据库操作）
        """
        self.db_pool = db_pool if not offline_mode else None
        self.checkpointer = checkpointer or self._create_default_checkpointer()
        self._offline_mode = offline_mode
        
        # Graph 名称到编译后 Graph 的映射
        self._graph_registry: Dict[str, Any] = {}
        
        # 后台任务管理
        self._background_tasks: Dict[str, asyncio.Task] = {}
        
        # 内存中的 run 记录（离线模式）
        self._runs: Dict[str, Dict[str, Any]] = {}
        
        # 事件队列（用于实时流式推送）
        self._event_queues: Dict[str, asyncio.Queue] = {}
        self._event_stream_complete: Dict[str, bool] = {}
        max_active_runs = int(os.getenv("RUN_MAX_CONCURRENCY", "3"))
        self._run_semaphore = asyncio.Semaphore(max(1, max_active_runs))
        self._graph_max_concurrency = int(os.getenv("LANGGRAPH_MAX_CONCURRENCY", "8"))
        self._graph_recursion_limit = int(os.getenv("LANGGRAPH_RECURSION_LIMIT", "50"))
        self._auto_resume_enabled = os.getenv("LANGGRAPH_AUTO_RESUME", "true").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        self._auto_resume_limit = int(os.getenv("LANGGRAPH_AUTO_RESUME_LIMIT", "25"))
        
        if offline_mode:
            logger.info("LangGraphOrchestrator 已初始化（离线模式）")
        else:
            logger.info("LangGraphOrchestrator 已初始化")
    
    def _create_default_checkpointer(self) -> Optional[AsyncPostgresSaver]:
        """创建默认 Checkpointer
        
        注意：如果数据库连接池不可用，返回 None（离线模式）
        """
        paused = False
        try:
            # 尝试从连接池获取连接字符串
            # 注意：asyncpg.Pool 没有 get_dsn 方法，需要从配置获取
            import os
            dsn = os.getenv("DATABASE_URL", "")
            if dsn:
                return AsyncPostgresSaver.from_conn_string(dsn)
            else:
                logger.warning("DATABASE_URL 未设置，Checkpointer 不可用")
                return None
        except Exception as e:
            logger.warning(f"创建 Checkpointer 失败: {e}")
            return None

    def _build_graph_config(self, run_id: str) -> Dict[str, Any]:
        config: Dict[str, Any] = {"configurable": {"thread_id": run_id}}
        if self._graph_max_concurrency > 0:
            config["max_concurrency"] = self._graph_max_concurrency
        if self._graph_recursion_limit > 0:
            config["recursion_limit"] = self._graph_recursion_limit
        return config
    
    def register_graph(self, graph_name: str, compiled_graph: Any):
        """注册编译后的 Graph
        
        Args:
            graph_name: Graph 名称（如 "exam_paper"）
            compiled_graph: 编译后的 LangGraph Graph
        """
        self._graph_registry[graph_name] = compiled_graph
        logger.info(f"已注册 Graph: {graph_name}")
    
    async def start_run(
        self,
        graph_name: str,
        payload: Dict[str, Any],
        idempotency_key: Optional[str] = None
    ) -> str:
        """启动 LangGraph Graph 执行
        
        Args:
            graph_name: Graph 名称
            payload: Graph 输入数据
            idempotency_key: 幂等键（可选）
            
        Returns:
            run_id: 执行 ID（即 thread_id）
            
        Raises:
            ValueError: 当 graph_name 未注册时
            Exception: 启动失败时
            
        验证：需求 1.1
        """
        # 检查 Graph 是否已注册
        if graph_name not in self._graph_registry:
            raise ValueError(f"未注册的 Graph: {graph_name}")
        
        compiled_graph = self._graph_registry[graph_name]
        
        # 生成 run_id（使用幂等键或生成新的 UUID）
        if idempotency_key:
            run_id = f"{graph_name}_{idempotency_key}"
        else:
            run_id = str(uuid.uuid4())
        
        logger.info(
            f"启动 LangGraph Graph: "
            f"graph_name={graph_name}, "
            f"run_id={run_id}, "
            f"idempotency_key={idempotency_key}"
        )
        
        try:
            # 检查幂等性：如果 run 已存在且未完成，返回现有 run_id
            existing_run = await self._get_run_from_db(run_id)
            if existing_run and existing_run["status"] in ["pending", "running", "paused"]:
                logger.info(
                    f"Run 已存在（幂等性）: "
                    f"run_id={run_id}, "
                    f"status={existing_run['status']}"
                )
                return run_id
            
            # 创建 run 记录
            await self._create_run_in_db(
                run_id=run_id,
                graph_name=graph_name,
                input_data=payload
            )
            
            # 启动后台任务执行 Graph
            task = asyncio.create_task(
                self._run_graph_background(
                    run_id=run_id,
                    graph_name=graph_name,
                    compiled_graph=compiled_graph,
                    payload=payload
                )
            )
            
            self._background_tasks[run_id] = task
            
            logger.info(f"Graph 已启动: run_id={run_id}")
            return run_id
            
        except Exception as e:
            logger.error(
                f"启动 Graph 失败: "
                f"run_id={run_id}, "
                f"error={str(e)}",
                exc_info=True
            )
            raise
    
    async def _run_graph_background(
        self,
        run_id: str,
        graph_name: str,
        compiled_graph: Any,
        payload: Dict[str, Any]
    ):
        """后台执行 Graph（支持实时事件推送）
        
        Args:
            run_id: 执行 ID
            graph_name: Graph 名称
            compiled_graph: 编译后的 Graph
            payload: 输入数据
        """
        paused = False  # 初始化，避免 finally 中 UnboundLocalError
        acquired = False
        try:
            await self._run_semaphore.acquire()
            acquired = True
            # 更新状态为 running
            await self._update_run_status(run_id, "running")
            
            # 配置 thread_id + LangGraph 内建并发控制
            config = self._build_graph_config(run_id)
            
            # 执行 Graph（使用 astream_events 获取详细事件）
            logger.info(f"开始执行 Graph: run_id={run_id}")
            
            result = None
            accumulated_state = dict(payload)  # 从初始 payload 开始累积状态
            
            # 使用 astream_events 获取详细的执行事件
            async for event in compiled_graph.astream_events(payload, config=config, version="v2"):
                event_kind = event.get("event")
                event_name = event.get("name", "")
                event_data = event.get("data", {})
                
                # 将事件存储到内存队列（供 stream_run 使用）
                await self._push_event(run_id, {
                    "kind": event_kind,
                    "name": event_name,
                    "data": event_data
                })
                
                # 检查是否有 interrupt
                if event_kind == "on_chain_end" and "__interrupt__" in event_data.get("output", {}):
                    logger.info(f"Graph 中断: run_id={run_id}")
                    paused = True
                    await self._update_run_status(run_id, "paused")
                    return  # 等待外部 resume
                
                # 处理 LLM 流式输出 (Requirement: 全流程流式)
                if event_kind == "on_chat_model_stream":
                    chunk = event_data.get("chunk")
                    if chunk:
                        # 尝试从 chunk 中提取内容
                        content = ""
                        if hasattr(chunk, "content"):
                            content = chunk.content
                        elif isinstance(chunk, dict) and "content" in chunk:
                            content = chunk["content"]
                        elif isinstance(chunk, str):
                            content = chunk
                        
                        if content:
                            await self._push_event(run_id, {
                                "kind": "llm_stream",
                                "name": event_name,
                                "data": {
                                    "chunk": content,
                                    "node": event.get("metadata", {}).get("langgraph_node", "")
                                }
                            })

                # 累积节点输出到状态
                if event_kind == "on_chain_end":
                    output = event_data.get("output", {})
                    if isinstance(output, dict):
                        # 合并输出到累积状态
                        for key, value in output.items():
                            # #region agent log - 假设F: 累积状态
                            if key == "student_results":
                                existing = accumulated_state.get(key, [])
                                _write_debug_log({
                                    "hypothesisId": "F",
                                    "location": "langgraph_orchestrator.py:accumulate",
                                    "message": f"累积student_results from {event_name}",
                                    "data": {
                                        "event_name": event_name,
                                        "existing_count": len(existing) if isinstance(existing, list) else 0,
                                        "new_count": len(value) if isinstance(value, list) else 0,
                                    },
                                    "timestamp": int(datetime.now().timestamp() * 1000),
                                    "sessionId": "debug-session",
                                })
                            # #endregion
                            
                            # 只对 grading_results 使用追加逻辑（它有 operator.add reducer）
                            # 其他字段（包括 student_results）使用覆盖逻辑
                            if key == "grading_results" and key in accumulated_state and isinstance(accumulated_state[key], list) and isinstance(value, list):
                                # 只有 grading_results 追加
                                accumulated_state[key].extend(value)
                            else:
                                # 其他类型：覆盖
                                accumulated_state[key] = value
                
                # 保存最后的结果
                if event_kind == "on_chain_end" and event_name == graph_name:
                    result = event_data.get("output", {})
            
            # 循环结束后再次检查 Graph 状态
            # astream_events 可能在 interrupt 时正常结束循环，我们需要通过 get_state 确认是否真的完成了
            snapshot = compiled_graph.get_state(config)
            if snapshot.next:
                logger.info(f"Graph 中断 (detected via state): run_id={run_id}, next={snapshot.next}")
                paused = True
                await self._update_run_status(run_id, "paused")
                
                # 尝试获取 interrupt payload
                interrupt_value = None
                if snapshot.tasks and hasattr(snapshot.tasks[0], "interrupts") and snapshot.tasks[0].interrupts:
                    # interrupts is usually a tuple or list
                    interrupt_value = snapshot.tasks[0].interrupts[0] if snapshot.tasks[0].interrupts else None
                
                await self._push_event(run_id, {
                    "kind": "paused", 
                    "name": None, 
                    "data": {
                        "state": snapshot.values,
                        "interrupt_value": interrupt_value
                    }
                })
                return
            
            # 执行完成 - 使用累积的完整状态
            logger.info(f"Graph 执行完成: run_id={run_id}")
            
            # #region agent log - 假设G: completed 事件发送前的 accumulated_state
            student_results = accumulated_state.get("student_results", [])
            _write_debug_log({
                "hypothesisId": "G",
                "location": "langgraph_orchestrator.py:completed:before_push",
                "message": "completed事件发送前的student_results",
                "data": {
                    "count": len(student_results),
                    "students": [
                        {
                            "key": r.get("student_key"),
                            "score": r.get("total_score"),
                            "max": r.get("max_total_score"),
                        }
                        for r in student_results
                    ],
                },
                "timestamp": int(datetime.now().timestamp() * 1000),
                "sessionId": "debug-session",
            })
            # #endregion
            
            await self._update_run_status(
                run_id,
                "completed",
                output_data=accumulated_state
            )
            
            # 标记事件流结束 - 传递完整状态
            await self._push_event(run_id, {"kind": "completed", "name": None, "data": {"state": accumulated_state}})

            
        except Exception as e:
            logger.error(
                f"Graph 执行失败: "
                f"run_id={run_id}, "
                f"error={str(e)}",
                exc_info=True
            )
            await self._update_run_status(
                run_id,
                "failed",
                error=str(e)
            )
            
            # 推送错误事件
            await self._push_event(run_id, {"kind": "error", "name": None, "data": {"error": str(e)}})
            
        finally:
            if acquired:
                self._run_semaphore.release()
            # 清理后台任务
            self._background_tasks.pop(run_id, None)
            
            # 标记事件流结束（如果还没标记）
            if not paused:
                await self._mark_event_stream_complete(run_id)

    async def _resume_from_checkpoint_background(
        self,
        run_id: str,
        graph_name: str,
        compiled_graph: Any,
        config: Dict[str, Any],
    ) -> None:
        """从 Checkpointer 恢复 Graph 执行（自动断点续跑）"""
        paused = False
        acquired = False
        try:
            await self._run_semaphore.acquire()
            acquired = True
            await self._update_run_status(run_id, "running")

            logger.info(f"恢复执行 Graph: run_id={run_id}")

            accumulated_state = await self.get_state(run_id) or {}
            if not accumulated_state:
                run = await self._get_run_from_db(run_id)
                if run and run.get("input_data"):
                    accumulated_state = run.get("input_data", {})
                    if isinstance(accumulated_state, str):
                        try:
                            accumulated_state = json.loads(accumulated_state)
                        except json.JSONDecodeError:
                            accumulated_state = {}

            result = None
            async for event in compiled_graph.astream_events(None, config=config, version="v2"):
                event_kind = event.get("event")
                event_name = event.get("name", "")
                event_data = event.get("data", {})

                await self._push_event(run_id, {
                    "kind": event_kind,
                    "name": event_name,
                    "data": event_data,
                })

                if event_kind == "on_chain_end" and "__interrupt__" in event_data.get("output", {}):
                    logger.info(f"Graph 中断: run_id={run_id}")
                    paused = True
                    await self._update_run_status(run_id, "paused")
                    return

                if event_kind == "on_chat_model_stream":
                    chunk = event_data.get("chunk")
                    if chunk:
                        content = ""
                        if hasattr(chunk, "content"):
                            content = chunk.content
                        elif isinstance(chunk, dict) and "content" in chunk:
                            content = chunk["content"]
                        elif isinstance(chunk, str):
                            content = chunk
                        if content:
                            await self._push_event(run_id, {
                                "kind": "llm_stream",
                                "name": event_name,
                                "data": {
                                    "chunk": content,
                                    "node": event.get("metadata", {}).get("langgraph_node", ""),
                                },
                            })

                if event_kind == "on_chain_end":
                    output = event_data.get("output", {})
                    if isinstance(output, dict):
                        for key, value in output.items():
                            if key == "grading_results" and key in accumulated_state and isinstance(accumulated_state[key], list) and isinstance(value, list):
                                accumulated_state[key].extend(value)
                            else:
                                accumulated_state[key] = value

                if event_kind == "on_chain_end" and event_name == graph_name:
                    result = event_data.get("output", {})

            snapshot = compiled_graph.get_state(config)
            if snapshot.next:
                logger.info(f"Graph 中断 (detected via state): run_id={run_id}, next={snapshot.next}")
                paused = True
                await self._update_run_status(run_id, "paused")
                interrupt_value = None
                if snapshot.tasks and hasattr(snapshot.tasks[0], "interrupts") and snapshot.tasks[0].interrupts:
                    interrupt_value = snapshot.tasks[0].interrupts[0] if snapshot.tasks[0].interrupts else None
                await self._push_event(run_id, {
                    "kind": "paused",
                    "name": None,
                    "data": {
                        "state": snapshot.values,
                        "interrupt_value": interrupt_value,
                    },
                })
                return

            logger.info(f"Graph 执行完成: run_id={run_id}")
            await self._update_run_status(run_id, "completed", output_data=accumulated_state)
            await self._push_event(run_id, {"kind": "completed", "name": None, "data": {"state": accumulated_state}})

        except Exception as exc:
            logger.error(
                f"Graph 恢复失败: run_id={run_id}, error={str(exc)}",
                exc_info=True,
            )
            await self._update_run_status(run_id, "failed", error=str(exc))
            await self._push_event(run_id, {"kind": "error", "name": None, "data": {"error": str(exc)}})
        finally:
            if acquired:
                self._run_semaphore.release()
            self._background_tasks.pop(run_id, None)
            if not paused:
                await self._mark_event_stream_complete(run_id)
    
    async def get_status(self, run_id: str) -> RunInfo:
        """查询 Graph 执行状态
        
        Args:
            run_id: 执行 ID
            
        Returns:
            RunInfo: 执行信息
            
        Raises:
            Exception: 查询失败或 run_id 不存在时
            
        验证：需求 1.2
        """
        try:
            # 从数据库查询 run 记录
            run = await self._get_run_from_db(run_id)
            if not run:
                raise ValueError(f"Run 不存在: {run_id}")
            
            # 从 Checkpointer 查询进度信息
            progress = {}
            try:
                config = {"configurable": {"thread_id": run_id}}
                checkpoint = await self.checkpointer.aget(config)
                if checkpoint:
                    channel_values = checkpoint.get("channel_values", {})
                    progress = channel_values.get("progress", {})
            except Exception as e:
                logger.debug(
                    f"查询 Checkpoint 失败: "
                    f"run_id={run_id}, "
                    f"error={str(e)}"
                )
            
            # 映射状态
            status_map = {
                "pending": RunStatus.PENDING,
                "running": RunStatus.RUNNING,
                "paused": RunStatus.PAUSED,
                "completed": RunStatus.COMPLETED,
                "failed": RunStatus.FAILED,
                "cancelled": RunStatus.CANCELLED
            }
            status = status_map.get(run["status"], RunStatus.PENDING)
            
            # 构建 RunInfo
            run_info = RunInfo(
                run_id=run_id,
                graph_name=run["graph_name"],
                status=status,
                progress=progress,
                created_at=run["created_at"],
                updated_at=run["updated_at"],
                error=run.get("error")
            )
            
            return run_info
            
        except Exception as e:
            logger.error(
                f"查询 Graph 状态失败: "
                f"run_id={run_id}, "
                f"error={str(e)}",
                exc_info=True
            )
            raise
    
    async def get_final_output(self, run_id: str) -> Optional[Dict[str, Any]]:
        """获取 Graph 执行的最终输出
        
        Args:
            run_id: 执行 ID
            
        Returns:
            最终输出数据，如果不存在则返回 None
        """
        try:
            # 首先从内存中获取
            if run_id in self._runs:
                run_data = self._runs[run_id]
                output_data = run_data.get("output_data")
                if output_data:
                    logger.info(f"从内存获取最终输出: run_id={run_id}, keys={list(output_data.keys())}")
                    return output_data
            
            # 如果内存中没有，尝试从数据库获取
            run = await self._get_run_from_db(run_id)
            if run and run.get("output_data"):
                logger.info(f"从数据库获取最终输出: run_id={run_id}")
                return run["output_data"]
            
            logger.warning(f"未找到最终输出: run_id={run_id}")
            return None
            
        except Exception as e:
            logger.error(f"获取最终输出失败: run_id={run_id}, error={e}")
            return None
    
    async def cancel(self, run_id: str) -> bool:
        """取消 Graph 执行
        
        Args:
            run_id: 执行 ID
            
        Returns:
            bool: 是否成功取消
            
        验证：需求 1.3
        """
        try:
            # 取消后台任务
            task = self._background_tasks.get(run_id)
            if task and not task.done():
                task.cancel()
                logger.info(f"后台任务已取消: run_id={run_id}")
            
            # 更新状态
            await self._update_run_status(run_id, "cancelled")
            
            logger.info(f"Graph 已取消: run_id={run_id}")
            return True
            
        except Exception as e:
            logger.error(
                f"取消 Graph 失败: "
                f"run_id={run_id}, "
                f"error={str(e)}",
                exc_info=True
            )
            return False
    
    async def retry(self, run_id: str) -> str:
        """重试失败的 Graph
        
        Args:
            run_id: 原执行 ID
            
        Returns:
            str: 新的执行 ID
            
        Raises:
            Exception: 重试失败时
            
        验证：需求 1.4
        """
        try:
            # 获取原 run 记录
            run = await self._get_run_from_db(run_id)
            if not run:
                raise ValueError(f"Run 不存在: {run_id}")
            
            # 提取 graph_name 和 input_data
            graph_name = run["graph_name"]
            input_data = run.get("input_data", {})
            
            # 生成新的 run_id
            new_run_id = str(uuid.uuid4())
            
            logger.info(
                f"重试 Graph: "
                f"original_run_id={run_id}, "
                f"new_run_id={new_run_id}"
            )
            
            # 启动新的 run
            return await self.start_run(
                graph_name=graph_name,
                payload=input_data
            )
            
        except Exception as e:
            logger.error(
                f"重试 Graph 失败: "
                f"run_id={run_id}, "
                f"error={str(e)}",
                exc_info=True
            )
            raise
    
    async def list_runs(
        self,
        graph_name: Optional[str] = None,
        status: Optional[RunStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[RunInfo]:
        """列出 Graph 执行
        
        Args:
            graph_name: 按 Graph 名称筛选
            status: 按状态筛选
            limit: 返回数量限制
            offset: 偏移量
            
        Returns:
            List[RunInfo]: 执行信息列表
            
        验证：需求 1.5
        """
        try:
            # 如果没有数据库连接，从内存返回
            if not self.db_pool:
                run_infos = []
                for run_id, run in self._runs.items():
                    if graph_name and run["graph_name"] != graph_name:
                        continue
                    if status and run["status"] != status.value:
                        continue
                    
                    status_map = {
                        "pending": RunStatus.PENDING,
                        "running": RunStatus.RUNNING,
                        "paused": RunStatus.PAUSED,
                        "completed": RunStatus.COMPLETED,
                        "failed": RunStatus.FAILED,
                        "cancelled": RunStatus.CANCELLED
                    }
                    
                    run_info = RunInfo(
                        run_id=run["run_id"],
                        graph_name=run["graph_name"],
                        status=status_map.get(run["status"], RunStatus.PENDING),
                        progress={},
                        created_at=run["created_at"],
                        updated_at=run["updated_at"],
                        error=run.get("error")
                    )
                    run_infos.append(run_info)
                
                return run_infos[offset:offset+limit]
            
            # 构建查询条件（兼容 psycopg3）
            conditions = []
            params = []
            
            if graph_name:
                conditions.append("graph_name = %s")
                params.append(graph_name)
            
            if status:
                conditions.append("status = %s")
                params.append(status.value)
            
            where_clause = " AND ".join(conditions) if conditions else "TRUE"
            
            # 查询数据库
            query = f"""
                SELECT run_id, graph_name, status, created_at, updated_at, error FROM runs
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """
            params.extend([limit, offset])
            
            async with self.db_pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, params)
                    rows = await cur.fetchall()
            
            # 构建 RunInfo 列表
            run_infos = []
            columns = ["run_id", "graph_name", "status", "created_at", "updated_at", "error"]
            for row in rows:
                row_dict = dict(zip(columns, row))
                status_map = {
                    "pending": RunStatus.PENDING,
                    "running": RunStatus.RUNNING,
                    "paused": RunStatus.PAUSED,
                    "completed": RunStatus.COMPLETED,
                    "failed": RunStatus.FAILED,
                    "cancelled": RunStatus.CANCELLED
                }
                
                run_info = RunInfo(
                    run_id=row_dict["run_id"],
                    graph_name=row_dict["graph_name"],
                    status=status_map.get(row_dict["status"], RunStatus.PENDING),
                    progress={},  # 简化处理，不查询 Checkpoint
                    created_at=row_dict["created_at"],
                    updated_at=row_dict["updated_at"],
                    error=row_dict.get("error")
                )
                run_infos.append(run_info)
            
            logger.info(f"查询到 {len(run_infos)} 个 Runs")
            return run_infos
            
        except Exception as e:
            logger.error(
                f"列出 Runs 失败: "
                f"error={str(e)}",
                exc_info=True
            )
            raise

    async def recover_incomplete_runs(
        self,
        graph_name: Optional[str] = None,
    ) -> int:
        """自动恢复中断的运行（依赖 Checkpointer）"""
        if not self._auto_resume_enabled:
            logger.info("Auto resume disabled; skipping recovery.")
            return 0
        if self._offline_mode or not self.db_pool or not self.checkpointer:
            logger.info("Auto resume unavailable (no DB/checkpointer).")
            return 0

        runs = await self._fetch_incomplete_runs(
            graph_name=graph_name,
            limit=self._auto_resume_limit,
        )
        resumed = 0
        for run in runs:
            run_id = run.get("run_id")
            graph = run.get("graph_name")
            status_value = run.get("status")
            if not run_id or not graph:
                continue
            if run_id in self._background_tasks:
                continue

            compiled_graph = self._graph_registry.get(graph)
            if not compiled_graph:
                continue

            config = self._build_graph_config(run_id)
            checkpoint = None
            try:
                checkpoint = await self.checkpointer.aget(config)
            except Exception as exc:
                logger.warning("Failed to fetch checkpoint for %s: %s", run_id, exc)

            if checkpoint:
                task = asyncio.create_task(
                    self._resume_from_checkpoint_background(
                        run_id=run_id,
                        graph_name=graph,
                        compiled_graph=compiled_graph,
                        config=config,
                    )
                )
                self._background_tasks[run_id] = task
                resumed += 1
                continue

            if status_value == "pending":
                payload = run.get("input_data") or {}
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except json.JSONDecodeError:
                        payload = {}
                task = asyncio.create_task(
                    self._run_graph_background(
                        run_id=run_id,
                        graph_name=graph,
                        compiled_graph=compiled_graph,
                        payload=payload,
                    )
                )
                self._background_tasks[run_id] = task
                resumed += 1

        if resumed:
            logger.info("Auto resumed %s runs.", resumed)
        return resumed

    async def _fetch_incomplete_runs(
        self,
        graph_name: Optional[str],
        limit: int,
    ) -> List[Dict[str, Any]]:
        if not self.db_pool:
            return []

        conditions = ["status IN ('running', 'pending')"]
        params: List[Any] = []
        if graph_name:
            conditions.append("graph_name = %s")
            params.append(graph_name)
        where_clause = " AND ".join(conditions)
        query = f"""
            SELECT run_id, graph_name, status, input_data
            FROM runs
            WHERE {where_clause}
            ORDER BY updated_at DESC
            LIMIT %s
        """
        params.append(limit)

        try:
            async with self.db_pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, params)
                    rows = await cur.fetchall()
        except Exception as exc:
            logger.warning("Failed to fetch incomplete runs: %s", exc)
            return []

        columns = ["run_id", "graph_name", "status", "input_data"]
        return [dict(zip(columns, row)) for row in rows]
    
    async def send_event(
        self,
        run_id: str,
        event_type: str,
        event_data: Dict[str, Any]
    ) -> bool:
        """发送事件到 Graph（用于 resume）
        
        Args:
            run_id: 执行 ID
            event_type: 事件类型（如 "review_signal"）
            event_data: 事件数据
            
        Returns:
            bool: 是否成功发送
            
        验证：需求 1.6
        """
        try:
            # 检查 run 是否存在且处于 paused 状态
            run = await self._get_run_from_db(run_id)
            if not run:
                raise ValueError(f"Run 不存在: {run_id}")
            
            if run["status"] != "paused":
                logger.warning(
                    f"Run 不处于 paused 状态: "
                    f"run_id={run_id}, "
                    f"status={run['status']}"
                )
                return False
            
            logger.info(
                f"发送事件到 Graph: "
                f"run_id={run_id}, "
                f"event_type={event_type}"
            )
            
            # 获取 Graph
            graph_name = run["graph_name"]
            compiled_graph = self._graph_registry.get(graph_name)
            if not compiled_graph:
                raise ValueError(f"Graph 未注册: {graph_name}")
            
            # 配置 thread_id + LangGraph 内建并发控制
            config = self._build_graph_config(run_id)
            
            # 使用 Command.resume 恢复执行
            resume_command = Command(resume=event_data)
            
            # 重新启动后台任务
            task = asyncio.create_task(
                self._resume_graph_background(
                    run_id=run_id,
                    graph_name=graph_name,
                    compiled_graph=compiled_graph,
                    resume_command=resume_command,
                    config=config
                )
            )
            
            self._background_tasks[run_id] = task
            
            logger.info(
                f"事件已发送，Graph 已恢复: "
                f"run_id={run_id}, "
                f"event_type={event_type}"
            )
            return True
            
        except Exception as e:
            logger.error(
                f"发送事件失败: "
                f"run_id={run_id}, "
                f"event_type={event_type}, "
                f"error={str(e)}",
                exc_info=True
            )
            return False
    
    async def _resume_graph_background(
        self,
        run_id: str,
        graph_name: str,
        compiled_graph: Any,
        resume_command: Command,
        config: Dict[str, Any]
    ):
        """后台恢复 Graph 执行
        
        Args:
            run_id: 执行 ID
            graph_name: Graph 名称
            compiled_graph: 编译后的 Graph
            resume_command: Resume 命令
            config: 配置
        """
        paused = False
        acquired = False
        accumulated_state: Dict[str, Any] = {}
        try:
            await self._run_semaphore.acquire()
            acquired = True
            # 更新状态为 running
            await self._update_run_status(run_id, "running")
            
            # 执行 Graph（从 interrupt 点恢复）
            logger.info(f"恢复执行 Graph: run_id={run_id}")
            
            accumulated_state = await self._get_final_state(run_id) or {}
            if not accumulated_state:
                run = await self._get_run_from_db(run_id)
                if run and run.get("input_data"):
                    accumulated_state = dict(run["input_data"])

            result = None
            async for event in compiled_graph.astream_events(resume_command, config=config, version="v2"):
                event_kind = event.get("event")
                event_name = event.get("name", "")
                event_data = event.get("data", {})
                logger.debug(f"Graph 事件: run_id={run_id}, event={event}")

                await self._push_event(run_id, {
                    "kind": event_kind,
                    "name": event_name,
                    "data": event_data
                })

                if event_kind == "on_chain_end" and "__interrupt__" in event_data.get("output", {}):
                    logger.info(f"Graph 再次中断: run_id={run_id}")
                    paused = True
                    await self._update_run_status(run_id, "paused")
                    return

                if event_kind == "on_chat_model_stream":
                    chunk = event_data.get("chunk")
                    if chunk:
                        content = ""
                        if hasattr(chunk, "content"):
                            content = chunk.content
                        elif isinstance(chunk, dict) and "content" in chunk:
                            content = chunk["content"]
                        elif isinstance(chunk, str):
                            content = chunk
                        if content:
                            await self._push_event(run_id, {
                                "kind": "llm_stream",
                                "name": event_name,
                                "data": {
                                    "chunk": content,
                                    "node": event.get("metadata", {}).get("langgraph_node", "")
                                }
                            })

                if event_kind == "on_chain_end":
                    output = event_data.get("output", {})
                    if isinstance(output, dict):
                        for key, value in output.items():
                            if (
                                key == "grading_results"
                                and key in accumulated_state
                                and isinstance(accumulated_state[key], list)
                                and isinstance(value, list)
                            ):
                                accumulated_state[key].extend(value)
                            else:
                                accumulated_state[key] = value

                if event_kind == "on_chain_end" and event_name == graph_name:
                    result = event_data.get("output", {})
            
            # 执行完成
            logger.info(f"Graph 恢复执行完成: run_id={run_id}")
            output_state = accumulated_state if accumulated_state else (result or {})
            await self._update_run_status(run_id, "completed", output_data=output_state)
            await self._push_event(
                run_id,
                {"kind": "completed", "name": None, "data": {"state": output_state}},
            )
            
        except Exception as e:
            logger.error(
                f"Graph 恢复执行失败: "
                f"run_id={run_id}, "
                f"error={str(e)}",
                exc_info=True
            )
            await self._update_run_status(
                run_id,
                "failed",
                error=str(e)
            )
        finally:
            if acquired:
                self._run_semaphore.release()
            self._background_tasks.pop(run_id, None)
            if not paused:
                await self._mark_event_stream_complete(run_id)
    
    # ==================== 流式 API ====================
    
    async def stream_run(self, run_id: str):
        """流式返回 Graph 执行事件（从内存队列）
        
        这是实现实时进度推送的关键方法！
        从内存事件队列读取 Graph 执行期间产生的事件。
        
        Args:
            run_id: 执行 ID（thread_id）
            
        Yields:
            事件字典，包含 type, node, data 等信息
            
        Example:
            async for event in orchestrator.stream_run(run_id):
                if event["type"] == "node_start":
                    print(f"节点开始: {event['node']}")
                elif event["type"] == "state_update":
                    print(f"状态更新: {event['data']}")
        """
        try:
            # 确保事件队列存在
            if run_id not in self._event_queues:
                self._event_queues[run_id] = asyncio.Queue()
            
            queue = self._event_queues[run_id]
            
            logger.info(f"开始流式监听 Graph（从队列）: run_id={run_id}")
            
            # 从队列读取事件
            while True:
                try:
                    # 等待事件（带超时）
                    event = await asyncio.wait_for(queue.get(), timeout=1.0)
                    
                    # 检查是否是结束标记
                    if event.get("kind") == "__end__":
                        logger.info(f"事件流结束: run_id={run_id}")
                        break
                    
                    # 转换事件格式
                    event_kind = event.get("kind")
                    event_name = event.get("name", "")
                    event_data = event.get("data", {})
                    
                    # 转换为统一的事件格式
                    if event_kind == "on_chain_start":
                        yield {
                            "type": "node_start",
                            "node": event_name,
                            "data": event_data
                        }
                    elif event_kind == "llm_stream":
                        yield {
                            "type": "llm_stream",
                            "node": event_data.get("node", ""),
                            "data": event_data
                        }
                    
                    elif event_kind == "on_chain_end":
                        yield {
                            "type": "node_end",
                            "node": event_name,
                            "data": {
                                "output": event_data.get("output", {})
                            }
                        }
                    
                    elif event_kind == "on_chain_stream":
                        # 流式输出（如 LLM 生成）
                        yield {
                            "type": "stream",
                            "node": event_name,
                            "data": event_data
                        }
                    
                    elif event_kind == "on_chat_model_stream":
                        # LLM 流式输出
                        chunk = event_data.get("chunk", {})
                        content = chunk.content if hasattr(chunk, "content") else str(chunk)
                        yield {
                            "type": "llm_stream",
                            "node": event_name,
                            "data": {
                                "content": content
                            }
                        }
                    
                    elif event_kind == "completed":
                        # 执行完成
                        yield {
                            "type": "completed",
                            "node": None,
                            "data": event_data
                        }
                        break
                    
                    elif event_kind == "error":
                        # 错误
                        yield {
                            "type": "error",
                            "node": None,
                            "data": event_data
                        }
                        break
                    
                    # 检查状态更新
                    if "output" in event_data:
                        output = event_data["output"]
                        if isinstance(output, dict):
                            yield {
                                "type": "state_update",
                                "node": event_name,
                                "data": {
                                    "state": output
                                }
                            }
                
                except asyncio.TimeoutError:
                    # 超时，检查是否已完成
                    if self._is_event_stream_complete(run_id):
                        logger.info(f"事件流已完成（超时检测）: run_id={run_id}")
                        break
                    # 否则继续等待
                    continue
            
            logger.info(f"流式监听完成: run_id={run_id}")
            
            # 清理队列
            await self._cleanup_event_queue(run_id)
            
        except Exception as e:
            logger.error(
                f"流式监听失败: run_id={run_id}, error={str(e)}",
                exc_info=True
            )
            yield {
                "type": "error",
                "node": None,
                "data": {
                    "error": str(e)
                }
            }
    
    async def stream_run_simple(self, run_id: str):
        """简化版流式监听（使用 astream）
        
        适用于不需要详细事件的场景，只关心节点输出。
        
        Args:
            run_id: 执行 ID
            
        Yields:
            节点输出字典
        """
        try:
            run = await self._get_run_from_db(run_id)
            if not run:
                raise ValueError(f"Run 不存在: {run_id}")
            
            graph_name = run["graph_name"]
            compiled_graph = self._graph_registry.get(graph_name)
            if not compiled_graph:
                raise ValueError(f"Graph 未注册: {graph_name}")
            
            config = self._build_graph_config(run_id)
            
            # 使用简单的 astream
            async for chunk in compiled_graph.astream(None, config=config):
                for node_name, node_output in chunk.items():
                    yield {
                        "type": "node_output",
                        "node": node_name,
                        "data": node_output
                    }
            
        except Exception as e:
            logger.error(f"简化流式监听失败: {str(e)}", exc_info=True)
            yield {
                "type": "error",
                "node": None,
                "data": {"error": str(e)}
            }
    
    async def get_run_info(self, run_id: str) -> Optional[RunInfo]:
        """获取 Run 详细信息（包含状态）
        
        Args:
            run_id: 执行 ID
            
        Returns:
            RunInfo 或 None（如果不存在）
        """
        try:
            run = await self._get_run_from_db(run_id)
            if not run:
                return None
            
            # 获取最新状态
            state = await self._get_final_state(run_id)
            
            status_map = {
                "pending": RunStatus.PENDING,
                "running": RunStatus.RUNNING,
                "paused": RunStatus.PAUSED,
                "completed": RunStatus.COMPLETED,
                "failed": RunStatus.FAILED,
                "cancelled": RunStatus.CANCELLED
            }
            
            return RunInfo(
                run_id=run_id,
                graph_name=run["graph_name"],
                status=status_map.get(run["status"], RunStatus.PENDING),
                progress=state.get("progress", {}),
                created_at=run["created_at"],
                updated_at=run["updated_at"],
                error=run.get("error"),
                state=state  # 包含完整状态
            )
            
        except Exception as e:
            logger.error(f"获取 Run 信息失败: {str(e)}", exc_info=True)
            return None
    
    async def get_state(self, run_id: str) -> Dict[str, Any]:
        """从 Checkpointer 获取当前/最终状态
        
        Args:
            run_id: 执行 ID
            
        Returns:
            状态字典
        """
        try:
            logger.info(f"DEBUG: get_state called for run_id={run_id}")
            config = {"configurable": {"thread_id": run_id}}
            checkpoint = await self.checkpointer.aget(config)
            logger.info(f"DEBUG: checkpointer.aget result for {run_id}: {bool(checkpoint)}")
            
            if checkpoint:
                return checkpoint.get("channel_values", {})
            
            # 如果 Checkpointer 中没有，尝试从 DB 或内存中获取（针对已完成的）
            run = await self._get_run_from_db(run_id)
            logger.info(f"DEBUG: _get_run_from_db result for {run_id}: {bool(run)}")
            
            if run:
                if run.get("output_data"):
                     return run["output_data"]
                if run.get("input_data"):
                     # 如果只有输入数据（刚开始），至少返回输入
                     return run["input_data"]

            return {}
        except Exception as e:
            logger.debug(f"获取 Checkpoint 失败: {str(e)}")
            return {}

    async def _get_final_state(self, run_id: str) -> Dict[str, Any]:
        """已弃用：请使用 get_state"""
        return await self.get_state(run_id)
    
    # ==================== 事件队列管理 ====================
    
    async def _push_event(self, run_id: str, event: Dict[str, Any]):
        """推送事件到队列
        
        Args:
            run_id: 执行 ID
            event: 事件数据
        """
        if run_id not in self._event_queues:
            self._event_queues[run_id] = asyncio.Queue()
        
        await self._event_queues[run_id].put(event)
    
    async def _mark_event_stream_complete(self, run_id: str):
        """标记事件流完成
        
        Args:
            run_id: 执行 ID
        """
        self._event_stream_complete[run_id] = True
        
        # 推送一个特殊的结束标记
        if run_id in self._event_queues:
            await self._event_queues[run_id].put({"kind": "__end__", "name": None, "data": {}})
    
    def _is_event_stream_complete(self, run_id: str) -> bool:
        """检查事件流是否完成
        
        Args:
            run_id: 执行 ID
            
        Returns:
            是否完成
        """
        return self._event_stream_complete.get(run_id, False)
    
    async def _cleanup_event_queue(self, run_id: str):
        """清理事件队列
        
        Args:
            run_id: 执行 ID
        """
        self._event_queues.pop(run_id, None)
        self._event_stream_complete.pop(run_id, None)
    
    # ==================== 数据库操作辅助方法 ====================
    
    async def _create_run_in_db(
        self,
        run_id: str,
        graph_name: str,
        input_data: Dict[str, Any]
    ):
        """在数据库中创建 run 记录（支持离线模式）"""
        if self.db_pool:
            try:
                async with self.db_pool.connection() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute(
                            """
                            INSERT INTO runs (run_id, graph_name, status, input_data, created_at, updated_at)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            """,
                            (run_id, graph_name, "pending", json.dumps(input_data), datetime.now(), datetime.now())
                        )
                    await conn.commit()
            except Exception as e:
                logger.warning(f"数据库写入失败，使用内存存储: {e}")
                self._create_run_in_memory(run_id, graph_name, input_data)
        else:
            self._create_run_in_memory(run_id, graph_name, input_data)
    
    def _create_run_in_memory(
        self,
        run_id: str,
        graph_name: str,
        input_data: Dict[str, Any]
    ):
        """在内存中创建 run 记录（离线模式）"""
        self._runs[run_id] = {
            "run_id": run_id,
            "graph_name": graph_name,
            "status": "pending",
            "input_data": input_data,
            "output_data": None,
            "error": None,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
    
    async def _get_run_from_db(self, run_id: str) -> Optional[Dict[str, Any]]:
        """从数据库查询 run 记录（支持离线模式）"""
        # 先检查内存
        if run_id in self._runs:
            return self._runs[run_id]
        
        # 再检查数据库（兼容 psycopg3 AsyncConnectionPool）
        if self.db_pool:
            try:
                async with self.db_pool.connection() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute(
                            "SELECT run_id, graph_name, status, input_data, output_data, error, created_at, updated_at FROM runs WHERE run_id = %s",
                            (run_id,)
                        )
                        row = await cur.fetchone()
                        if row:
                            columns = ["run_id", "graph_name", "status", "input_data", "output_data", "error", "created_at", "updated_at"]
                            return dict(zip(columns, row))
                        return None
            except Exception as e:
                logger.warning(f"数据库查询失败: {e}")
                return None
        
        return None
    
    async def _update_run_status(
        self,
        run_id: str,
        status: str,
        output_data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ):
        """更新 run 状态（支持离线模式）"""
        # 更新内存
        if run_id in self._runs:
            self._runs[run_id]["status"] = status
            self._runs[run_id]["updated_at"] = datetime.now()
            if output_data is not None:
                self._runs[run_id]["output_data"] = output_data
            if error is not None:
                self._runs[run_id]["error"] = error
        
        # 更新数据库（兼容 psycopg3 AsyncConnectionPool）
        if self.db_pool:
            try:
                async with self.db_pool.connection() as conn:
                    async with conn.cursor() as cur:
                        # 构建动态更新语句
                        set_parts = ["status = %s", "updated_at = %s"]
                        params = [status, datetime.now()]
                        
                        if output_data is not None:
                            set_parts.append("output_data = %s")
                            params.append(json.dumps(output_data))
                        
                        if error is not None:
                            set_parts.append("error = %s")
                            params.append(error)
                        
                        if status == "completed":
                            set_parts.append("completed_at = %s")
                            params.append(datetime.now())
                        
                        params.append(run_id)
                        query = f"UPDATE runs SET {', '.join(set_parts)} WHERE run_id = %s"
                        await cur.execute(query, params)
                    await conn.commit()
            except Exception as e:
                logger.warning(f"数据库更新失败: {e}")
