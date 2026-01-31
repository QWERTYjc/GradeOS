"""Redis 操作详细日志记录器"""
import logging
import json
from typing import Any, Optional

logger = logging.getLogger(__name__)


def log_redis_operation(
    operation: str,
    key: str,
    value: Optional[Any] = None,
    result: Optional[Any] = None,
    error: Optional[Exception] = None,
):
    """
    记录 Redis 操作的详细日志
    
    Args:
        operation: 操作类型 (GET, SET, HSET, ZADD等)
        key: Redis key
        value: 设置的值（如果适用）
        result: 操作结果
        error: 错误信息（如果有）
    """
    log_data = {
        "operation": operation,
        "key": key,
    }
    
    if value is not None:
        # 限制值的长度，避免日志过大
        value_str = str(value)
        if len(value_str) > 200:
            log_data["value"] = value_str[:200] + "... (truncated)"
        else:
            log_data["value"] = value_str
    
    if result is not None:
        log_data["result"] = str(result)
    
    if error:
        log_data["error"] = str(error)
        logger.error(f"[Redis] ❌ {operation} 失败: {json.dumps(log_data, ensure_ascii=False)}")
    else:
        logger.info(f"[Redis] ✅ {operation}: {json.dumps(log_data, ensure_ascii=False)}")
