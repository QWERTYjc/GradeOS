"""SQL 操作详细日志记录器"""
import logging
import json
from typing import Any, Optional

logger = logging.getLogger(__name__)


def log_sql_operation(
    operation: str,
    query: str,
    params: Optional[tuple] = None,
    result_count: Optional[int] = None,
    error: Optional[Exception] = None,
):
    """
    记录 SQL 操作的详细日志
    
    Args:
        operation: 操作类型 (SELECT, INSERT, UPDATE, DELETE等)
        query: SQL 查询语句
        params: 查询参数
        result_count: 返回的记录数（如果适用）
        error: 错误信息（如果有）
    """
    log_data = {
        "operation": operation,
        "query": query.strip(),
        "params": params if params else None,
    }
    
    if result_count is not None:
        log_data["result_count"] = result_count
    
    if error:
        log_data["error"] = str(error)
        logger.error(f"[SQL] ❌ {operation} 失败: {json.dumps(log_data, ensure_ascii=False)}")
    else:
        logger.info(f"[SQL] ✅ {operation}: {json.dumps(log_data, ensure_ascii=False)}")
