"""
智能缓存预热服务

提供缓存预热功能，包括启动预热、评分细则哈希预计算和异步批量预热。

验证：需求 6.1, 6.2, 6.4
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone

from src.utils.pool_manager import UnifiedPoolManager
from src.utils.hashing import compute_rubric_hash
from src.services.multi_layer_cache import MultiLayerCacheService


logger = logging.getLogger(__name__)


class CacheWarmupService:
    """
    智能缓存预热服务
    
    特性：
    - 启动预热：从 PostgreSQL 加载最近 7 天高置信度结果
    - 评分细则哈希预计算：创建评分细则时预计算哈希
    - 异步批量预热：批量导入时异步预热
    
    验证：需求 6.1, 6.2, 6.4
    """
    
    def __init__(
        self,
        pool_manager: UnifiedPoolManager,
        cache_service: MultiLayerCacheService,
        high_confidence_threshold: float = 0.9,
        warmup_days: int = 7,
        batch_size: int = 100
    ):
        """
        初始化缓存预热服务
        
        Args:
            pool_manager: 统一连接池管理器
            cache_service: 多层缓存服务
            high_confidence_threshold: 高置信度阈值
            warmup_days: 预热天数
            batch_size: 批量处理大小
        """
        self.pool_manager = pool_manager
        self.cache_service = cache_service
        self.high_confidence_threshold = high_confidence_threshold
        self.warmup_days = warmup_days
        self.batch_size = batch_size
        
        # 预热统计
        self._warmup_stats = {
            "total_loaded": 0,
            "total_cached": 0,
            "total_failed": 0,
            "last_warmup_at": None
        }
    
    @property
    def warmup_stats(self) -> Dict[str, Any]:
        """获取预热统计信息"""
        return self._warmup_stats.copy()
    
    async def warmup_on_startup(self) -> Dict[str, Any]:
        """
        启动预热
        
        从 PostgreSQL 加载最近 7 天的高置信度批改结果，
        异步加载到 Redis。
        
        Returns:
            预热统计信息
            
        验证：需求 6.1
        """
        logger.info(
            f"开始启动预热: threshold={self.high_confidence_threshold}, "
            f"days={self.warmup_days}"
        )
        
        start_time = datetime.now(timezone.utc)
        loaded_count = 0
        cached_count = 0
        failed_count = 0
        
        try:
            # 计算时间范围
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.warmup_days)
            
            # 从 PostgreSQL 查询高置信度结果
            query = """
                SELECT 
                    gr.submission_id,
                    gr.question_id,
                    gr.score,
                    gr.max_score,
                    gr.confidence_score,
                    gr.visual_annotations,
                    gr.agent_trace,
                    gr.student_feedback,
                    gr.created_at
                FROM grading_results gr
                WHERE gr.confidence_score >= %s
                  AND gr.created_at >= %s
                ORDER BY gr.created_at DESC
            """
            
            async with self.pool_manager.pg_connection() as conn:
                result = await conn.execute(
                    query,
                    (self.high_confidence_threshold, cutoff_date)
                )
                rows = await result.fetchall()
                loaded_count = len(rows)
                
                logger.info(f"从数据库加载了 {loaded_count} 条高置信度结果")
                
                # 批量预热到 Redis
                for i in range(0, len(rows), self.batch_size):
                    batch = rows[i:i + self.batch_size]
                    batch_cached, batch_failed = await self._warmup_batch(batch)
                    cached_count += batch_cached
                    failed_count += batch_failed
                    
                    # 避免阻塞太久
                    await asyncio.sleep(0.01)
            
            # 更新统计
            self._warmup_stats["total_loaded"] = loaded_count
            self._warmup_stats["total_cached"] = cached_count
            self._warmup_stats["total_failed"] = failed_count
            self._warmup_stats["last_warmup_at"] = start_time.isoformat()
            
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            logger.info(
                f"启动预热完成: loaded={loaded_count}, cached={cached_count}, "
                f"failed={failed_count}, elapsed={elapsed:.2f}s"
            )
            
            return {
                "loaded_count": loaded_count,
                "cached_count": cached_count,
                "failed_count": failed_count,
                "elapsed_seconds": elapsed,
                "started_at": start_time.isoformat()
            }
            
        except Exception as e:
            logger.error(f"启动预热失败: {e}", exc_info=True)
            return {
                "loaded_count": loaded_count,
                "cached_count": cached_count,
                "failed_count": failed_count,
                "error": str(e)
            }
    
    async def _warmup_batch(
        self,
        batch: List[Dict[str, Any]]
    ) -> tuple[int, int]:
        """
        预热一批结果
        
        Args:
            batch: 批改结果列表
            
        Returns:
            (成功数, 失败数)
        """
        cached_count = 0
        failed_count = 0
        
        for row in batch:
            try:
                # 构造缓存键
                key = f"grading_result:{row['submission_id']}:{row['question_id']}"
                
                # 构造缓存值
                value = {
                    "submission_id": str(row["submission_id"]),
                    "question_id": row["question_id"],
                    "score": float(row["score"]) if row["score"] else None,
                    "max_score": float(row["max_score"]) if row["max_score"] else None,
                    "confidence_score": float(row["confidence_score"]) if row["confidence_score"] else None,
                    "visual_annotations": row["visual_annotations"],
                    "agent_trace": row["agent_trace"],
                    "student_feedback": row["student_feedback"],
                    "created_at": row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else row["created_at"]
                }
                
                # 写入缓存（仅 Redis，不触发 Write-Through）
                await self._write_to_redis_only(key, value, ttl_seconds=3600)
                cached_count += 1
                
            except Exception as e:
                logger.warning(f"预热单条结果失败: {e}")
                failed_count += 1
        
        return cached_count, failed_count
    
    async def _write_to_redis_only(
        self,
        key: str,
        value: Any,
        ttl_seconds: int
    ) -> None:
        """
        仅写入 Redis（不触发 Write-Through）
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl_seconds: 过期时间（秒）
        """
        import json
        from redis.exceptions import RedisError
        
        try:
            redis_client = self.pool_manager.get_redis_client()
            full_key = f"{self.cache_service.config.hot_cache_prefix}:{key}"
            
            await redis_client.setex(
                full_key,
                ttl_seconds,
                json.dumps(value, default=str)
            )
            
        except RedisError as e:
            logger.warning(f"写入 Redis 失败: {e}")
            raise
    
    async def precompute_rubric_hash(
        self,
        rubric_id: str,
        rubric_text: str,
        exam_id: str,
        question_id: str
    ) -> Optional[str]:
        """
        预计算评分细则哈希
        
        创建评分细则时预计算哈希值并缓存。
        
        Args:
            rubric_id: 评分细则 ID
            rubric_text: 评分细则文本
            exam_id: 考试 ID
            question_id: 题目 ID
            
        Returns:
            哈希值，失败返回 None
            
        验证：需求 6.2
        """
        try:
            # 计算哈希
            rubric_hash = compute_rubric_hash(rubric_text)
            
            # 缓存哈希值
            cache_key = f"rubric_hash:{exam_id}:{question_id}"
            cache_value = {
                "rubric_id": rubric_id,
                "rubric_hash": rubric_hash,
                "exam_id": exam_id,
                "question_id": question_id,
                "computed_at": datetime.now(timezone.utc).isoformat()
            }
            
            # 缓存 7 天
            await self._write_to_redis_only(
                cache_key,
                cache_value,
                ttl_seconds=7 * 24 * 3600
            )
            
            logger.info(
                f"预计算评分细则哈希: rubric_id={rubric_id}, "
                f"hash={rubric_hash[:16]}..."
            )
            
            return rubric_hash
            
        except Exception as e:
            logger.error(f"预计算评分细则哈希失败: {e}")
            return None
    
    async def get_cached_rubric_hash(
        self,
        exam_id: str,
        question_id: str
    ) -> Optional[str]:
        """
        获取缓存的评分细则哈希
        
        Args:
            exam_id: 考试 ID
            question_id: 题目 ID
            
        Returns:
            哈希值，未找到返回 None
        """
        import json
        from redis.exceptions import RedisError
        
        try:
            redis_client = self.pool_manager.get_redis_client()
            cache_key = f"{self.cache_service.config.hot_cache_prefix}:rubric_hash:{exam_id}:{question_id}"
            
            data = await redis_client.get(cache_key)
            if data is not None:
                cache_value = json.loads(data)
                return cache_value.get("rubric_hash")
            
            return None
            
        except (RedisError, json.JSONDecodeError) as e:
            logger.warning(f"获取缓存的评分细则哈希失败: {e}")
            return None
    
    async def async_batch_warmup(
        self,
        submission_ids: List[str]
    ) -> asyncio.Task:
        """
        异步批量预热
        
        批量导入时异步预热，不阻塞主流程。
        
        Args:
            submission_ids: 提交 ID 列表
            
        Returns:
            异步任务
            
        验证：需求 6.4
        """
        async def _warmup_task():
            logger.info(f"开始异步批量预热: count={len(submission_ids)}")
            
            total_cached = 0
            total_failed = 0
            
            try:
                # 查询这些提交的高置信度结果
                query = """
                    SELECT 
                        gr.submission_id,
                        gr.question_id,
                        gr.score,
                        gr.max_score,
                        gr.confidence_score,
                        gr.visual_annotations,
                        gr.agent_trace,
                        gr.student_feedback,
                        gr.created_at
                    FROM grading_results gr
                    WHERE gr.submission_id = ANY(%s)
                      AND gr.confidence_score >= %s
                    ORDER BY gr.created_at DESC
                """
                
                async with self.pool_manager.pg_connection() as conn:
                    result = await conn.execute(
                        query,
                        (submission_ids, self.high_confidence_threshold)
                    )
                    rows = await result.fetchall()
                    
                    logger.info(f"异步批量预热: 查询到 {len(rows)} 条结果")
                    
                    # 批量预热
                    for i in range(0, len(rows), self.batch_size):
                        batch = rows[i:i + self.batch_size]
                        cached, failed = await self._warmup_batch(batch)
                        total_cached += cached
                        total_failed += failed
                        
                        # 避免阻塞太久
                        await asyncio.sleep(0.01)
                
                logger.info(
                    f"异步批量预热完成: cached={total_cached}, failed={total_failed}"
                )
                
            except Exception as e:
                logger.error(f"异步批量预热失败: {e}", exc_info=True)
        
        # 创建后台任务
        task = asyncio.create_task(_warmup_task())
        return task
    
    async def invalidate_rubric_hash_cache(
        self,
        exam_id: str,
        question_id: str
    ) -> bool:
        """
        使评分细则哈希缓存失效
        
        Args:
            exam_id: 考试 ID
            question_id: 题目 ID
            
        Returns:
            是否成功
        """
        from redis.exceptions import RedisError
        
        try:
            redis_client = self.pool_manager.get_redis_client()
            cache_key = f"{self.cache_service.config.hot_cache_prefix}:rubric_hash:{exam_id}:{question_id}"
            
            deleted = await redis_client.delete(cache_key)
            
            if deleted > 0:
                logger.info(f"使评分细则哈希缓存失效: {exam_id}:{question_id}")
            
            return deleted > 0
            
        except RedisError as e:
            logger.warning(f"使评分细则哈希缓存失效失败: {e}")
            return False
