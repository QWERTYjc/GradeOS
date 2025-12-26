"""
限流器服务

提供基于 Redis 的滑动窗口限流功能，用于保护 API 和外部服务调用。
使用 Redis INCR 配合 EXPIRE 实现原子计数。
"""

import logging
from typing import Optional
from datetime import datetime, timedelta, timezone

import redis.asyncio as redis
from redis.exceptions import RedisError


logger = logging.getLogger(__name__)


class RateLimiter:
    """
    滑动窗口限流器
    
    使用 Redis 实现分布式限流，通过原子操作保证并发安全。
    支持按时间窗口限制请求数量。
    
    验证：需求 8.3
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        key_prefix: str = "rate_limit"
    ):
        """
        初始化限流器
        
        Args:
            redis_client: Redis 异步客户端实例
            key_prefix: Redis 键前缀，用于区分不同类型的限流
        """
        self.redis_client = redis_client
        self.key_prefix = key_prefix
    
    def _get_window_key(self, key: str, window_seconds: int) -> str:
        """
        生成时间窗口的 Redis 键
        
        Args:
            key: 限流标识（如 user_id, api_name 等）
            window_seconds: 时间窗口大小（秒）
            
        Returns:
            Redis 键，格式：rate_limit:{key}:{window_start_timestamp}
        """
        # 计算当前时间窗口的起始时间戳
        now = datetime.now(timezone.utc)
        window_start = int(now.timestamp() // window_seconds * window_seconds)
        
        return f"{self.key_prefix}:{key}:{window_start}"
    
    async def acquire(
        self,
        key: str,
        max_requests: int,
        window_seconds: int
    ) -> bool:
        """
        尝试获取限流令牌
        
        使用 Redis INCR 原子操作实现计数，配合 EXPIRE 自动清理过期窗口。
        
        Args:
            key: 限流标识（如 user_id, api_name 等）
            max_requests: 时间窗口内允许的最大请求数
            window_seconds: 时间窗口大小（秒）
            
        Returns:
            如果允许请求返回 True，超出限制返回 False
            
        验证：需求 8.3
        """
        try:
            window_key = self._get_window_key(key, window_seconds)
            
            # 使用 Redis Pipeline 保证原子性
            async with self.redis_client.pipeline(transaction=True) as pipe:
                # INCR 操作：原子递增计数器
                pipe.incr(window_key)
                # 设置过期时间（窗口大小 + 缓冲时间）
                pipe.expire(window_key, window_seconds + 60)
                
                results = await pipe.execute()
                current_count = results[0]
            
            # 判断是否超出限制
            if current_count <= max_requests:
                logger.debug(
                    f"限流通过: key={key}, "
                    f"count={current_count}/{max_requests}, "
                    f"window={window_seconds}s"
                )
                return True
            else:
                logger.warning(
                    f"限流拒绝: key={key}, "
                    f"count={current_count}/{max_requests}, "
                    f"window={window_seconds}s"
                )
                return False
                
        except RedisError as e:
            # Redis 错误：记录日志，默认允许请求（fail-open 策略）
            logger.error(
                f"限流器 Redis 错误（默认允许）: {str(e)}, key={key}",
                exc_info=True
            )
            return True
            
        except Exception as e:
            # 其他未预期错误：记录日志，默认允许请求
            logger.error(
                f"限流器发生未预期错误（默认允许）: {str(e)}, key={key}",
                exc_info=True
            )
            return True
    
    async def get_remaining(
        self,
        key: str,
        max_requests: int,
        window_seconds: int
    ) -> int:
        """
        获取剩余配额
        
        查询当前时间窗口内还可以发起多少次请求。
        
        Args:
            key: 限流标识
            max_requests: 时间窗口内允许的最大请求数
            window_seconds: 时间窗口大小（秒）
            
        Returns:
            剩余可用请求数，失败时返回 max_requests（保守估计）
        """
        try:
            window_key = self._get_window_key(key, window_seconds)
            
            # 获取当前计数
            current_count_str = await self.redis_client.get(window_key)
            
            if current_count_str is None:
                # 窗口不存在，说明还没有请求
                return max_requests
            
            current_count = int(current_count_str)
            remaining = max(0, max_requests - current_count)
            
            logger.debug(
                f"剩余配额: key={key}, "
                f"remaining={remaining}, "
                f"used={current_count}/{max_requests}"
            )
            
            return remaining
            
        except RedisError as e:
            logger.error(f"查询剩余配额失败（Redis 错误）: {str(e)}, key={key}")
            return max_requests  # 保守估计
            
        except (ValueError, TypeError) as e:
            logger.error(f"解析计数值失败: {str(e)}, key={key}")
            return max_requests  # 保守估计
            
        except Exception as e:
            logger.error(
                f"查询剩余配额发生未预期错误: {str(e)}, key={key}",
                exc_info=True
            )
            return max_requests  # 保守估计
    
    async def reset(self, key: str, window_seconds: int) -> bool:
        """
        重置限流计数器
        
        删除当前时间窗口的计数，通常用于测试或管理操作。
        
        Args:
            key: 限流标识
            window_seconds: 时间窗口大小（秒）
            
        Returns:
            如果重置成功返回 True，失败返回 False
        """
        try:
            window_key = self._get_window_key(key, window_seconds)
            deleted = await self.redis_client.delete(window_key)
            
            if deleted > 0:
                logger.info(f"限流计数器已重置: key={key}")
                return True
            else:
                logger.debug(f"限流计数器不存在，无需重置: key={key}")
                return True
                
        except RedisError as e:
            logger.error(f"重置限流计数器失败: {str(e)}, key={key}")
            return False
            
        except Exception as e:
            logger.error(
                f"重置限流计数器发生未预期错误: {str(e)}, key={key}",
                exc_info=True
            )
            return False
    
    async def get_rate_limit_info(
        self,
        key: str,
        max_requests: int,
        window_seconds: int
    ) -> dict:
        """
        获取限流详细信息
        
        返回当前限流状态的完整信息，用于监控和调试。
        
        Args:
            key: 限流标识
            max_requests: 时间窗口内允许的最大请求数
            window_seconds: 时间窗口大小（秒）
            
        Returns:
            包含限流信息的字典
        """
        try:
            window_key = self._get_window_key(key, window_seconds)
            
            # 获取当前计数和 TTL
            async with self.redis_client.pipeline(transaction=False) as pipe:
                pipe.get(window_key)
                pipe.ttl(window_key)
                results = await pipe.execute()
            
            current_count_str, ttl = results
            current_count = int(current_count_str) if current_count_str else 0
            remaining = max(0, max_requests - current_count)
            
            # 计算窗口重置时间
            now = datetime.now(timezone.utc)
            window_start = int(now.timestamp() // window_seconds * window_seconds)
            window_end = window_start + window_seconds
            reset_at = datetime.fromtimestamp(window_end, tz=timezone.utc)
            
            return {
                "key": key,
                "limit": max_requests,
                "remaining": remaining,
                "used": current_count,
                "window_seconds": window_seconds,
                "reset_at": reset_at.isoformat(),
                "ttl_seconds": ttl if ttl > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"获取限流信息失败: {str(e)}, key={key}")
            return {
                "key": key,
                "limit": max_requests,
                "remaining": max_requests,
                "used": 0,
                "window_seconds": window_seconds,
                "error": str(e)
            }
