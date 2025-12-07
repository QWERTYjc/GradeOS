"""
语义缓存服务

提供基于 Redis 的语义缓存功能，用于缓存批改结果。
实现优雅降级：缓存失败时不影响正常批改流程。
"""

import json
import logging
from typing import Optional
from datetime import timedelta

import redis.asyncio as redis
from redis.exceptions import RedisError

from src.models.grading import GradingResult
from src.utils.hashing import compute_cache_key, compute_rubric_hash, compute_image_hash


logger = logging.getLogger(__name__)


class CacheService:
    """
    语义缓存服务
    
    使用 Redis 存储批改结果，通过感知哈希实现语义去重。
    所有操作都实现了优雅降级：失败时返回 None 而不抛出异常。
    
    验证：需求 6.2, 6.3, 6.4, 6.5
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        default_ttl_days: int = 30
    ):
        """
        初始化缓存服务
        
        Args:
            redis_client: Redis 异步客户端实例
            default_ttl_days: 默认缓存过期时间（天），默认 30 天
        """
        self.redis_client = redis_client
        self.default_ttl = timedelta(days=default_ttl_days)
        
    async def get_cached_result(
        self,
        rubric_text: str,
        image_data: bytes
    ) -> Optional[GradingResult]:
        """
        查询缓存的批改结果
        
        根据评分细则和图像计算缓存键，查询是否存在缓存结果。
        
        Args:
            rubric_text: 评分细则文本
            image_data: 题目图像字节数据
            
        Returns:
            如果缓存命中，返回 GradingResult 对象；
            如果缓存未命中或查询失败，返回 None
            
        验证：需求 6.2, 6.4
        """
        try:
            # 计算缓存键
            cache_key = compute_cache_key(rubric_text, image_data)
            
            # 查询 Redis
            cached_data = await self.redis_client.get(cache_key)
            
            if cached_data is None:
                logger.debug(f"缓存未命中: {cache_key}")
                return None
                
            # 反序列化为 GradingResult
            result_dict = json.loads(cached_data)
            result = GradingResult(**result_dict)
            
            logger.info(f"缓存命中: {cache_key}, question_id={result.question_id}")
            return result
            
        except RedisError as e:
            # Redis 错误：记录日志但不中断流程
            logger.warning(f"缓存查询失败（优雅降级）: {str(e)}")
            return None
            
        except (json.JSONDecodeError, ValueError) as e:
            # 数据格式错误：记录日志但不中断流程
            logger.warning(f"缓存数据解析失败: {str(e)}")
            return None
            
        except Exception as e:
            # 其他未预期错误：记录日志但不中断流程
            logger.error(f"缓存查询发生未预期错误: {str(e)}", exc_info=True)
            return None
    
    async def cache_result(
        self,
        rubric_text: str,
        image_data: bytes,
        result: GradingResult,
        ttl_days: Optional[int] = None
    ) -> bool:
        """
        缓存批改结果
        
        仅当置信度 > 0.9 时才缓存结果。
        
        Args:
            rubric_text: 评分细则文本
            image_data: 题目图像字节数据
            result: 批改结果对象
            ttl_days: 缓存过期时间（天），如果为 None 则使用默认值
            
        Returns:
            如果缓存成功返回 True，失败返回 False
            
        验证：需求 6.3, 6.4, 6.5
        """
        try:
            # 检查置信度阈值
            if result.confidence <= 0.9:
                logger.debug(
                    f"置信度 {result.confidence} <= 0.9，跳过缓存 "
                    f"(question_id={result.question_id})"
                )
                return False
            
            # 计算缓存键
            cache_key = compute_cache_key(rubric_text, image_data)
            
            # 序列化结果
            result_json = result.model_dump_json()
            
            # 计算 TTL
            ttl = timedelta(days=ttl_days) if ttl_days is not None else self.default_ttl
            
            # 存储到 Redis
            await self.redis_client.setex(
                cache_key,
                ttl,
                result_json
            )
            
            logger.info(
                f"缓存成功: {cache_key}, "
                f"question_id={result.question_id}, "
                f"confidence={result.confidence}, "
                f"ttl={ttl.days}天"
            )
            return True
            
        except RedisError as e:
            # Redis 错误：记录日志但不中断流程
            logger.warning(f"缓存存储失败（优雅降级）: {str(e)}")
            return False
            
        except Exception as e:
            # 其他未预期错误：记录日志但不中断流程
            logger.error(f"缓存存储发生未预期错误: {str(e)}", exc_info=True)
            return False
    
    async def invalidate_by_rubric(self, rubric_text: str) -> int:
        """
        使特定评分细则的所有缓存失效
        
        当评分细则更新时调用，删除所有使用该评分细则的缓存条目。
        
        Args:
            rubric_text: 评分细则文本
            
        Returns:
            删除的缓存条目数量，失败时返回 0
            
        验证：需求 9.4
        """
        try:
            rubric_hash = compute_rubric_hash(rubric_text)
            pattern = f"grade_cache:v1:{rubric_hash}:*"
            
            # 查找匹配的键
            cursor = 0
            deleted_count = 0
            
            while True:
                cursor, keys = await self.redis_client.scan(
                    cursor=cursor,
                    match=pattern,
                    count=100
                )
                
                if keys:
                    deleted = await self.redis_client.delete(*keys)
                    deleted_count += deleted
                
                if cursor == 0:
                    break
            
            logger.info(f"评分细则缓存失效: rubric_hash={rubric_hash}, 删除 {deleted_count} 条")
            return deleted_count
            
        except RedisError as e:
            logger.warning(f"缓存失效操作失败: {str(e)}")
            return 0
            
        except Exception as e:
            logger.error(f"缓存失效发生未预期错误: {str(e)}", exc_info=True)
            return 0
    
    async def get_cache_stats(self) -> dict:
        """
        获取缓存统计信息
        
        Returns:
            包含缓存统计信息的字典
        """
        try:
            info = await self.redis_client.info("stats")
            
            # 统计缓存键数量
            cursor = 0
            cache_key_count = 0
            
            while True:
                cursor, keys = await self.redis_client.scan(
                    cursor=cursor,
                    match="grade_cache:v1:*",
                    count=100
                )
                cache_key_count += len(keys)
                
                if cursor == 0:
                    break
            
            return {
                "total_cache_keys": cache_key_count,
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "hit_rate": (
                    info.get("keyspace_hits", 0) / 
                    (info.get("keyspace_hits", 0) + info.get("keyspace_misses", 1))
                )
            }
            
        except Exception as e:
            logger.error(f"获取缓存统计失败: {str(e)}")
            return {
                "total_cache_keys": 0,
                "keyspace_hits": 0,
                "keyspace_misses": 0,
                "hit_rate": 0.0,
                "error": str(e)
            }
