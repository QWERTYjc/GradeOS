"""测试 SQL 和 Redis 日志功能"""
import asyncio
import logging
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.sql_logger import log_sql_operation
from src.utils.redis_logger import log_redis_operation

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('batch_grading.log', mode='a', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)


def test_sql_logger():
    """测试 SQL 日志记录器"""
    logger.info("=" * 80)
    logger.info("测试 SQL 日志记录器")
    logger.info("=" * 80)
    
    # 测试 SELECT 操作
    log_sql_operation(
        "SELECT",
        "SELECT * FROM grading_history WHERE batch_id = %s",
        params=("test_batch_123",),
        result_count=1
    )
    
    # 测试 INSERT 操作
    log_sql_operation(
        "INSERT",
        "INSERT INTO grading_history (id, batch_id, status) VALUES (%s, %s, %s)",
        params=("uuid-123", "batch-456", "completed"),
        result_count=1
    )
    
    # 测试错误情况
    log_sql_operation(
        "UPDATE",
        "UPDATE grading_history SET status = %s WHERE id = %s",
        params=("failed", "uuid-999"),
        error=Exception("连接超时")
    )
    
    logger.info("SQL 日志测试完成\n")


def test_redis_logger():
    """测试 Redis 日志记录器"""
    logger.info("=" * 80)
    logger.info("测试 Redis 日志记录器")
    logger.info("=" * 80)
    
    # 测试 HSET 操作
    log_redis_operation(
        "HSET",
        "grading_run:record:batch_123",
        value={"status": "running", "progress": "0.5"},
        result="OK"
    )
    
    # 测试 ZADD 操作
    log_redis_operation(
        "ZADD",
        "grading_run:queue:teacher_001",
        value={"batch_456": 1738305600.0},
        result=1
    )
    
    # 测试 SMEMBERS 操作
    log_redis_operation(
        "SMEMBERS",
        "grading_run:runs:teacher_001",
        result="count=5"
    )
    
    # 测试长值截断
    long_value = "x" * 300
    log_redis_operation(
        "SET",
        "test:long_value",
        value=long_value,
        result="OK"
    )
    
    # 测试错误情况
    log_redis_operation(
        "GET",
        "grading_run:record:batch_999",
        error=Exception("连接被拒绝")
    )
    
    logger.info("Redis 日志测试完成\n")


if __name__ == "__main__":
    logger.info("\n" + "=" * 80)
    logger.info("开始测试日志功能")
    logger.info("=" * 80 + "\n")
    
    test_sql_logger()
    test_redis_logger()
    
    logger.info("=" * 80)
    logger.info("所有测试完成！请检查 batch_grading.log 文件")
    logger.info("=" * 80)
