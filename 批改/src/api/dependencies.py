"""API 依赖注入

提供全局依赖项，包括数据库连接池、编排器等。
"""

import logging
from typing import Optional

from src.orchestration.base import Orchestrator
from src.utils.database import get_db_pool


logger = logging.getLogger(__name__)


# 全局编排器实例
_orchestrator: Optional[Orchestrator] = None


async def init_orchestrator():
    """初始化 LangGraph 编排器（支持离线模式）"""
    global _orchestrator
    
    logger.info("初始化 LangGraph 编排器")
    
    from src.orchestration.langgraph_orchestrator import LangGraphOrchestrator
    from src.graphs.exam_paper import create_exam_paper_graph
    from src.graphs.batch_grading import create_batch_grading_graph
    from src.graphs.rule_upgrade import create_rule_upgrade_graph
    import os
    
    # 检查是否强制离线模式
    offline_mode = os.getenv("OFFLINE_MODE", "true").lower() == "true"
    
    if offline_mode:
        logger.info("使用离线模式（OFFLINE_MODE=true）")
        db_pool = None
    else:
        # 尝试获取数据库连接池
        try:
            db_pool = await get_db_pool()
        except Exception as e:
            logger.warning(f"获取数据库连接池失败，使用离线模式: {e}")
            db_pool = None
            offline_mode = True
    
    # 创建 LangGraph Orchestrator（支持离线模式）
    _orchestrator = LangGraphOrchestrator(db_pool=db_pool, offline_mode=offline_mode)
    
    # 注册 Graphs
    _orchestrator.register_graph("exam_paper", create_exam_paper_graph())
    _orchestrator.register_graph("batch_grading", create_batch_grading_graph())
    _orchestrator.register_graph("rule_upgrade", create_rule_upgrade_graph())
    
    logger.info("LangGraph 编排器已初始化")


async def get_orchestrator() -> Optional[Orchestrator]:
    """获取编排器实例
    
    Returns:
        Orchestrator 实例，如果未初始化则返回 None
    """
    return _orchestrator


async def close_orchestrator():
    """关闭编排器"""
    global _orchestrator
    _orchestrator = None
    logger.info("编排器已关闭")
