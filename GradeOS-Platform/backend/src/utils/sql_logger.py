"""SQL 操作详细日志记录器"""
import logging
import json
import os
from typing import Optional

logger = logging.getLogger(__name__)

_SENSITIVE_TABLES = (
    "student_grading_results",
    "grading_history",
    "grading_page_images",
)


def _is_sensitive_query(query: str) -> bool:
    lowered = query.lower()
    return any(table in lowered for table in _SENSITIVE_TABLES)


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
    log_params = os.getenv("SQL_LOG_PARAMS", "false").strip().lower() in ("1", "true", "yes")
    log_success = os.getenv("SQL_LOG_SUCCESS", "false").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    is_sensitive = _is_sensitive_query(query)
    if is_sensitive and not error:
        return
    log_data = {
        "operation": operation,
        "query": query.strip(),
    }
    if log_params and params and not is_sensitive:
        log_data["params"] = params
    
    if result_count is not None:
        log_data["result_count"] = result_count
    
    if error:
        log_data["error"] = str(error)
        logger.error(f"[SQL] ❌ {operation} 失败: {json.dumps(log_data, ensure_ascii=False)}")
    elif log_success and not is_sensitive:
        # Successful SQL logs are noisy and may contain sensitive data; default to disabled.
        logger.debug(f"[SQL] ✅ {operation}: {json.dumps(log_data, ensure_ascii=False)}")
