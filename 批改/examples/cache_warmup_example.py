"""
缓存预热服务使用示例

展示如何使用智能缓存预热服务进行启动预热、评分细则哈希预计算和异步批量预热。
"""

import asyncio
import logging
from datetime import datetime

from src.utils.pool_manager import UnifiedPoolManager
from src.services.multi_layer_cache import MultiLayerCacheService, CacheConfig
from src.services.cache_warmup import CacheWarmupService


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """主函数"""
    
    # 1. 初始化连接池管理器
    logger.info("初始化连接池管理器...")
    pool_manager = UnifiedPoolManager.get_instance()
    
    await pool_manager.initialize(
        pg_dsn="postgresql://user:password@localhost:5432/grading_db",
        redis_url="redis://localhost:6379/0",
        pg_min_size=5,
        pg_max_size=20,
        redis_max_connections=50
    )
    
    # 2. 创建多层缓存服务
    logger.info("创建多层缓存服务...")
    cache_config = CacheConfig(
        pubsub_channel="cache_invalidation",
        enable_pubsub=True
    )
    cache_service = MultiLayerCacheService(pool_manager, cache_config)
    await cache_service.start()
    
    # 3. 创建缓存预热服务
    logger.info("创建缓存预热服务...")
    warmup_service = CacheWarmupService(
        pool_manager=pool_manager,
        cache_service=cache_service,
        high_confidence_threshold=0.9,
        warmup_days=7,
        batch_size=100
    )
    
    # 4. 执行启动预热
    logger.info("=" * 60)
    logger.info("执行启动预热...")
    logger.info("=" * 60)
    
    warmup_result = await warmup_service.warmup_on_startup()
    
    logger.info(f"预热完成:")
    logger.info(f"  - 加载记录数: {warmup_result['loaded_count']}")
    logger.info(f"  - 缓存成功数: {warmup_result['cached_count']}")
    logger.info(f"  - 失败数: {warmup_result['failed_count']}")
    logger.info(f"  - 耗时: {warmup_result.get('elapsed_seconds', 0):.2f}秒")
    
    # 5. 预计算评分细则哈希
    logger.info("=" * 60)
    logger.info("预计算评分细则哈希...")
    logger.info("=" * 60)
    
    rubric_text = """
    评分细则：
    1. 正确使用公式 (5分)
    2. 计算过程正确 (3分)
    3. 结果正确 (2分)
    """
    
    rubric_hash = await warmup_service.precompute_rubric_hash(
        rubric_id="rubric_001",
        rubric_text=rubric_text,
        exam_id="exam_001",
        question_id="q1"
    )
    
    logger.info(f"预计算哈希: {rubric_hash}")
    
    # 6. 从缓存获取哈希
    cached_hash = await warmup_service.get_cached_rubric_hash(
        exam_id="exam_001",
        question_id="q1"
    )
    
    logger.info(f"从缓存获取哈希: {cached_hash}")
    logger.info(f"哈希匹配: {rubric_hash == cached_hash}")
    
    # 7. 异步批量预热
    logger.info("=" * 60)
    logger.info("执行异步批量预热...")
    logger.info("=" * 60)
    
    submission_ids = [
        "sub_001",
        "sub_002",
        "sub_003",
        "sub_004",
        "sub_005"
    ]
    
    warmup_task = await warmup_service.async_batch_warmup(submission_ids)
    logger.info(f"异步预热任务已启动: {warmup_task}")
    
    # 等待异步任务完成
    await warmup_task
    logger.info("异步预热任务完成")
    
    # 8. 查看预热统计
    logger.info("=" * 60)
    logger.info("预热统计信息:")
    logger.info("=" * 60)
    
    stats = warmup_service.warmup_stats
    for key, value in stats.items():
        logger.info(f"  - {key}: {value}")
    
    # 9. 查看缓存统计
    logger.info("=" * 60)
    logger.info("缓存统计信息:")
    logger.info("=" * 60)
    
    cache_stats = cache_service.get_stats_dict()
    for key, value in cache_stats.items():
        logger.info(f"  - {key}: {value}")
    
    # 10. 清理
    logger.info("=" * 60)
    logger.info("清理资源...")
    logger.info("=" * 60)
    
    await cache_service.stop()
    await pool_manager.shutdown()
    
    logger.info("示例完成！")


if __name__ == "__main__":
    asyncio.run(main())
