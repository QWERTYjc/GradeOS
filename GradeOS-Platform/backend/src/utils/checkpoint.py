"""LangGraph 检查点配置工具"""

from typing import Optional
import psycopg

try:
    from langgraph.checkpoint.postgres import PostgresSaver
except ImportError:
    PostgresSaver = None

from .database import DatabaseConfig


def create_checkpointer(
    config: Optional[DatabaseConfig] = None
) -> Optional["PostgresSaver"]:
    """
    创建 PostgreSQL 检查点保存器
    
    根据需求 3.7，配置 PostgresSaver 用于持久化 LangGraph 状态转换。
    
    Args:
        config: 数据库配置（可选）
        
    Returns:
        PostgresSaver: 检查点保存器实例
        
    Raises:
        ImportError: 如果 langgraph-checkpoint-postgres 未安装
    """
    if PostgresSaver is None:
        raise ImportError(
            "langgraph-checkpoint-postgres 未安装。"
            "请运行: uv sync 或 uv pip install langgraph-checkpoint-postgres"
        )
    
    if config is None:
        config = DatabaseConfig()
    
    # 创建同步连接（PostgresSaver 需要同步连接）
    connection_string = config.connection_string
    
    # PostgresSaver.from_conn_string() 会自动创建所需的表结构
    # 如果表已存在，则直接使用
    checkpointer = PostgresSaver.from_conn_string(connection_string)
    
    return checkpointer


def get_thread_id(submission_id: str, question_id: str) -> str:
    """
    生成检查点线程 ID
    
    根据需求 3.7：thread_id = submission_id + question_id
    
    Args:
        submission_id: 提交 ID（UUID 字符串）
        question_id: 题目 ID（字符串）
        
    Returns:
        str: 线程 ID，格式为 "{submission_id}_{question_id}"
    """
    return f"{submission_id}_{question_id}"
