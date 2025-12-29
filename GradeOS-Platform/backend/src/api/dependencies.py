"""API 依赖注入

提供全局依赖项，包括数据库连接池、编排器等。
"""

import logging
from typing import Optional

from src.orchestration.langgraph_orchestrator import LangGraphOrchestrator
from src.graphs.batch_grading import create_batch_grading_graph
from src.utils.database import get_db_pool


logger = logging.getLogger(__name__)


# 全局编排器实例
_orchestrator: Optional[LangGraphOrchestrator] = None


async def init_orchestrator():
    """初始化 LangGraph 编排器（支持离线模式）"""
    global _orchestrator
    
    logger.info("初始化 LangGraph 编排器")
    
    try:
        # 创建编排器（离线模式，不依赖数据库）
        _orchestrator = LangGraphOrchestrator(
            db_pool=None,
            checkpointer=None,
            offline_mode=True
        )
        
        # 注册批量批改 Graph
        batch_grading_graph = create_batch_grading_graph(checkpointer=None)
        _orchestrator.register_graph("batch_grading", batch_grading_graph)
        
        logger.info("LangGraph 编排器初始化成功（离线模式）")
        
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
