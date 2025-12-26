"""API 依赖注入

提供全局依赖项，包括数据库连接池、编排器等。
"""

import logging
from typing import Optional

# 暂时注释掉 Orchestrator 导入以避免 asyncpg 错误
# from src.orchestration.base import Orchestrator
from src.utils.database import get_db_pool


logger = logging.getLogger(__name__)


# 全局编排器实例
_orchestrator: Optional[object] = None  # 改为 object 类型


async def init_orchestrator():
    """初始化 LangGraph 编排器（支持离线模式）"""
    global _orchestrator
    
    logger.info("初始化 LangGraph 编排器")
    
    # 暂时跳过编排器初始化
    logger.warning("编排器初始化已跳过（开发模式）")
    _orchestrator = None


async def get_orchestrator() -> Optional[object]:
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
