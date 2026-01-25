"""API 依赖注入

提供全局依赖项，包括数据库连接池、编排器等。
"""

import logging
import os
import asyncio
from typing import Optional

from langgraph.checkpoint.memory import InMemorySaver
try:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
except ImportError:  # pragma: no cover - optional dependency for runtime
    AsyncPostgresSaver = None

from src.orchestration.langgraph_orchestrator import LangGraphOrchestrator
from src.graphs.batch_grading import create_batch_grading_graph
from src.utils.database import DatabaseConfig, db


logger = logging.getLogger(__name__)


# 全局编排器实例
_orchestrator: Optional[LangGraphOrchestrator] = None


async def init_orchestrator():
    """初始化 LangGraph 编排器（支持离线模式）"""
    global _orchestrator
    
    logger.info("初始化 LangGraph 编排器")
    
    try:
        offline_mode = os.getenv("OFFLINE_MODE", "false").lower() == "true"
        use_database = not offline_mode and not db.is_degraded

        checkpointer = None
        db_pool = None
        if use_database and AsyncPostgresSaver is not None:
            dsn = os.getenv("DATABASE_URL", "")
            if not dsn:
                dsn = DatabaseConfig().connection_string
            try:
                checkpointer = AsyncPostgresSaver.from_conn_string(dsn)
            except Exception as exc:
                logger.warning("Postgres checkpointer unavailable: %s", exc)
                checkpointer = None

        if checkpointer is None:
            checkpointer = InMemorySaver()
            offline_mode = True
        else:
            db_pool = db

        _orchestrator = LangGraphOrchestrator(
            db_pool=db_pool,
            checkpointer=checkpointer,
            offline_mode=offline_mode,
        )
        
        # 注册批量批改 Graph
        batch_grading_graph = create_batch_grading_graph(checkpointer=checkpointer)
        _orchestrator.register_graph("batch_grading", batch_grading_graph)

        asyncio.create_task(_orchestrator.recover_incomplete_runs(graph_name="batch_grading"))
        
        mode_label = "offline" if offline_mode else "database"
        logger.info("LangGraph 编排器初始化成功（%s）", mode_label)
        
    except Exception as e:
        logger.error(f"编排器初始化失败: {e}", exc_info=True)
        _orchestrator = None


async def get_orchestrator() -> Optional[LangGraphOrchestrator]:
    """获取编排器实例
    
    Returns:
        LangGraphOrchestrator 实例，如果未初始化则返回 None
    """
    return _orchestrator


async def close_orchestrator():
    """关闭编排器"""
    global _orchestrator
    _orchestrator = None
    logger.info("编排器已关闭")
