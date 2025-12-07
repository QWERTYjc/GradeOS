"""LangGraph 检查点配置工具"""

from typing import Optional

try:
    from langgraph.checkpoint.postgres import PostgresSaver
except ImportError:
    PostgresSaver = None

from .database import DatabaseConfig


def create_checkpointer(
    config: Optional[DatabaseConfig] = None
):
    """
    创建 PostgreSQL 检查点保存器
    
    Args:
        config: 数据库配置（可选）
        
    Returns:
        PostgresSaver: 检查点保存器实例，如果未安装则返回 None
    """
    if PostgresSaver is None:
        raise ImportError(
            "langgraph-checkpoint-postgres 未安装。"
            "请运行: uv pip install langgraph-checkpoint-postgres"
        )
    
    if config is None:
        config = DatabaseConfig()
    
    # 创建同步连接（PostgresSaver 需要同步连接）
    connection_string = config.connection_string
    
    # 创建 PostgresSaver
    checkpointer = PostgresSaver.from_conn_string(connection_string)
    
    return checkpointer


def get_thread_id(submission_id: str, question_id: str) -> str:
    """
    生成检查点线程 ID
    
    根据需求 3.7：thread_id = submission_id + question_id
    
    Args:
        submission_id: 提交 ID
        question_id: 题目 ID
        
    Returns:
        str: 线程 ID
    """
    return f"{submission_id}_{question_id}"
