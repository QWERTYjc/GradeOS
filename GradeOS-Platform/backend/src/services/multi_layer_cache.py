"""
多层缓存服务

提供 Write-Through 策略、热数据缓存、Pub/Sub 失效通知和自动降级的缓存服务。

验证：需求 3.1, 3.2, 3.3, 3.4, 3.5
"""

import asyncio
import json
import logging
from typing import Optional, Any, Callable, Awaitable, Set
from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass, field

import redis.asyncio as redis
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError

from src.utils.pool_manager import UnifiedPoolManager, PoolNotInitializedError


logger = logging.getLogger(__name__)


class CacheStrategy(str, Enum):
    """缓存策略枚举"""
    WRITE_THROUGH = "write_through"
    CACHE_ASIDE = "cache_aside"
    WRITE_BEHIND = "write_behind"


@dataclass
class CacheStats:
    """缓存统计信息"""
    redis_hits: int = 0
    redis_misses: int = 0
    pg_hits: int = 0
    pg_misses: int = 0
    write_through_success: int = 0
    write_through_failures: int = 0
    fallback_activations: int = 0
    invalidation_notifications_sent: int = 0
    invalidation_notifications_received: int = 0


@dataclass
class CacheConfig:
    """缓存配置"""
    pubsub_channel: str = "cache_invalidation"
    workflow_state_channel_prefix: str = "workflow_state"
    default_ttl_seconds: int = 3600  # 1 小时
    workflow_state_ttl_seconds: int = 86400  # 24 小时
    hot_cache_prefix: str = "hot_cache"
    workflow_state_prefix: str = "workflow_state"
    enable_pubsub: bool = True
    fallback_retry_interval: float = 30.0  # 降级后重试间隔（秒）


class MultiLayerCacheService:
    """
    多层缓存服务
    
    特性：
    - Write-Through 策略：同时写入 Redis 和 PostgreSQL
    - 热数据缓存：先查 Redis，未命中查 PostgreSQL
    - Pub/Sub 失效通知：通过 Redis Pub/Sub 广播缓存失效
    - 自动降级：Redis 故障时自动降级到 PostgreSQL
    
    验证：需求 3.1, 3.2, 3.3, 3.4, 3.5
    """
    
    def __init__(
        self,
        pool_manager: UnifiedPoolManager,
        config: Optional[CacheConfig] = None
    ):
        """
        初始化多层缓存服务
        
        Args:
            pool_manager: 统一连接池管理器
            config: 缓存配置
        """
        self.pool_manager = pool_manager
        self.config = config or CacheConfig()
        
        # 降级状态管理
        self._fallback_mode = False
        self._fallback_since: Optional[datetime] = None
        self._fallback_lock = asyncio.Lock()
        
        # Pub/Sub 订阅管理
        self._pubsub: Optional[redis.client.PubSub] = None
        self._pubsub_task: Optional[asyncio.Task] = None
        self._invalidation_callbacks: Set[Callable[[str], Awaitable[None]]] = set()
        self._running = False
        
        # 统计信息
        self._stats = CacheStats()
    
    @property
    def is_fallback_mode(self) -> bool:
        """检查是否处于降级模式"""
        return self._fallback_mode
    
    @property
    def stats(self) -> CacheStats:
        """获取缓存统计信息"""
        return self._stats

    async def start(self) -> None:
        """
        启动缓存服务
        
        初始化 Pub/Sub 订阅。
        """
        if self._running:
            return
        
        self._running = True
        
        if self.config.enable_pubsub:
            await self._start_pubsub_subscription()
        
        logger.info("多层缓存服务已启动")
    
    async def stop(self) -> None:
        """
        停止缓存服务
        
        关闭 Pub/Sub 订阅。
        """
        self._running = False
        
        if self._pubsub_task is not None:
            self._pubsub_task.cancel()
            try:
                await self._pubsub_task
            except asyncio.CancelledError:
                pass
            self._pubsub_task = None
        
        if self._pubsub is not None:
            await self._pubsub.unsubscribe()
            await self._pubsub.aclose()
            self._pubsub = None
        
        logger.info("多层缓存服务已停止")
    
    async def _start_pubsub_subscription(self) -> None:
        """启动 Pub/Sub 订阅"""
        try:
            redis_client = self.pool_manager.get_redis_client()
            self._pubsub = redis_client.pubsub()
            await self._pubsub.subscribe(self.config.pubsub_channel)
            
            # 启动消息处理任务
            self._pubsub_task = asyncio.create_task(
                self._process_pubsub_messages()
            )
            
            logger.info(f"已订阅缓存失效通道: {self.config.pubsub_channel}")
            
        except (RedisError, PoolNotInitializedError) as e:
            logger.warning(f"启动 Pub/Sub 订阅失败: {e}")
    
    async def _process_pubsub_messages(self) -> None:
        """处理 Pub/Sub 消息"""
        while self._running and self._pubsub is not None:
            try:
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0
                )
                
                if message is not None and message["type"] == "message":
                    await self._handle_invalidation_message(message["data"])
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"处理 Pub/Sub 消息时出错: {e}")
                await asyncio.sleep(1.0)
    
    async def _handle_invalidation_message(self, data: bytes) -> None:
        """
        处理缓存失效消息
        
        Args:
            data: 消息数据
        """
        try:
            pattern = data.decode("utf-8") if isinstance(data, bytes) else str(data)
            self._stats.invalidation_notifications_received += 1
            
            logger.debug(f"收到缓存失效通知: {pattern}")
            
            # 调用所有注册的回调
            for callback in self._invalidation_callbacks:
                try:
                    await callback(pattern)
                except Exception as e:
                    logger.warning(f"执行缓存失效回调时出错: {e}")
                    
        except Exception as e:
            logger.warning(f"处理缓存失效消息时出错: {e}")
    
    def register_invalidation_callback(
        self,
        callback: Callable[[str], Awaitable[None]]
    ) -> None:
        """
        注册缓存失效回调
        
        Args:
            callback: 异步回调函数，接收失效模式作为参数
        """
        self._invalidation_callbacks.add(callback)
    
    def unregister_invalidation_callback(
        self,
        callback: Callable[[str], Awaitable[None]]
    ) -> None:
        """
        取消注册缓存失效回调
        
        Args:
            callback: 要取消的回调函数
        """
        self._invalidation_callbacks.discard(callback)
    
    async def _enter_fallback_mode(self, reason: str) -> None:
        """
        进入降级模式
        
        Args:
            reason: 降级原因
        """
        async with self._fallback_lock:
            if not self._fallback_mode:
                self._fallback_mode = True
                self._fallback_since = datetime.now(timezone.utc)
                self._stats.fallback_activations += 1
                logger.warning(f"缓存服务进入降级模式: {reason}")
    
    async def _try_exit_fallback_mode(self) -> bool:
        """
        尝试退出降级模式
        
        Returns:
            是否成功退出降级模式
        """
        async with self._fallback_lock:
            if not self._fallback_mode:
                return True
            
            # 检查是否应该尝试恢复
            if self._fallback_since is not None:
                elapsed = (datetime.now(timezone.utc) - self._fallback_since).total_seconds()
                if elapsed < self.config.fallback_retry_interval:
                    return False
            
            # 尝试 ping Redis
            try:
                redis_client = self.pool_manager.get_redis_client()
                await redis_client.ping()
                
                self._fallback_mode = False
                self._fallback_since = None
                logger.info("缓存服务已退出降级模式")
                return True
                
            except Exception as e:
                self._fallback_since = datetime.now(timezone.utc)
                logger.debug(f"尝试退出降级模式失败: {e}")
                return False

    async def get_with_fallback(
        self,
        key: str,
        db_query: Callable[[], Awaitable[Optional[Any]]],
        ttl_seconds: Optional[int] = None
    ) -> Optional[Any]:
        """
        获取数据，支持降级
        
        查询顺序：
        1. 先查 Redis 热数据缓存
        2. 未命中则查 PostgreSQL
        3. PostgreSQL 结果回填 Redis
        4. Redis 故障时自动降级到直接查询 PostgreSQL
        
        Args:
            key: 缓存键
            db_query: 数据库查询函数（异步）
            ttl_seconds: 缓存过期时间（秒）
            
        Returns:
            查询结果，未找到返回 None
            
        验证：需求 3.2, 3.5
        """
        ttl = ttl_seconds or self.config.default_ttl_seconds
        full_key = f"{self.config.hot_cache_prefix}:{key}"
        
        # 如果处于降级模式，尝试恢复
        if self._fallback_mode:
            await self._try_exit_fallback_mode()
        
        # 尝试从 Redis 获取
        if not self._fallback_mode:
            try:
                redis_client = self.pool_manager.get_redis_client()
                cached_data = await redis_client.get(full_key)
                
                if cached_data is not None:
                    self._stats.redis_hits += 1
                    logger.debug(f"Redis 缓存命中: {key}")
                    return json.loads(cached_data)
                
                self._stats.redis_misses += 1
                logger.debug(f"Redis 缓存未命中: {key}")
                
            except (RedisError, RedisConnectionError) as e:
                await self._enter_fallback_mode(f"Redis 查询失败: {e}")
            except PoolNotInitializedError:
                await self._enter_fallback_mode("Redis 连接池未初始化")
        
        # 从 PostgreSQL 查询
        try:
            result = await db_query()
            
            if result is not None:
                self._stats.pg_hits += 1
                
                # 回填 Redis（如果不在降级模式）
                if not self._fallback_mode:
                    await self._backfill_cache(full_key, result, ttl)
            else:
                self._stats.pg_misses += 1
            
            return result
            
        except Exception as e:
            logger.error(f"数据库查询失败: {e}")
            raise
    
    async def _backfill_cache(
        self,
        key: str,
        value: Any,
        ttl_seconds: int
    ) -> None:
        """
        回填缓存
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl_seconds: 过期时间（秒）
        """
        try:
            redis_client = self.pool_manager.get_redis_client()
            await redis_client.setex(
                key,
                ttl_seconds,
                json.dumps(value, default=str)
            )
            logger.debug(f"缓存回填成功: {key}")
            
        except (RedisError, RedisConnectionError) as e:
            logger.warning(f"缓存回填失败: {e}")
        except Exception as e:
            logger.warning(f"缓存回填时发生未预期错误: {e}")
    
    async def write_through(
        self,
        key: str,
        value: Any,
        db_write: Callable[[Any], Awaitable[None]],
        ttl_seconds: Optional[int] = None
    ) -> bool:
        """
        Write-Through 写入
        
        同时写入 Redis 和 PostgreSQL，任一失败时执行补偿。
        
        Args:
            key: 缓存键
            value: 要写入的值
            db_write: 数据库写入函数（异步）
            ttl_seconds: 缓存过期时间（秒）
            
        Returns:
            写入是否成功
            
        验证：需求 3.1
        """
        ttl = ttl_seconds or self.config.default_ttl_seconds
        full_key = f"{self.config.hot_cache_prefix}:{key}"
        
        redis_written = False
        db_written = False
        
        try:
            # 步骤 1：写入 Redis
            if not self._fallback_mode:
                try:
                    redis_client = self.pool_manager.get_redis_client()
                    await redis_client.setex(
                        full_key,
                        ttl,
                        json.dumps(value, default=str)
                    )
                    redis_written = True
                    logger.debug(f"Redis 写入成功: {key}")
                    
                except (RedisError, RedisConnectionError) as e:
                    logger.warning(f"Redis 写入失败: {e}")
                    await self._enter_fallback_mode(f"Redis 写入失败: {e}")
                except PoolNotInitializedError:
                    logger.warning("Redis 连接池未初始化，跳过 Redis 写入")
            
            # 步骤 2：写入 PostgreSQL
            try:
                await db_write(value)
                db_written = True
                logger.debug(f"PostgreSQL 写入成功: {key}")
                
            except Exception as e:
                logger.error(f"PostgreSQL 写入失败: {e}")
                
                # 补偿：删除已写入的 Redis 缓存
                if redis_written:
                    await self._compensate_redis_write(full_key)
                
                self._stats.write_through_failures += 1
                raise
            
            self._stats.write_through_success += 1
            return True
            
        except Exception as e:
            logger.error(f"Write-Through 写入失败: {e}")
            return False
    
    async def _compensate_redis_write(self, key: str) -> None:
        """
        补偿 Redis 写入
        
        删除已写入的 Redis 缓存条目。
        
        Args:
            key: 缓存键
            
        验证：需求 4.2
        """
        try:
            redis_client = self.pool_manager.get_redis_client()
            await redis_client.delete(key)
            logger.info(f"补偿操作：已删除 Redis 缓存 {key}")
            
        except Exception as e:
            logger.error(f"补偿操作失败，无法删除 Redis 缓存 {key}: {e}")

    async def invalidate_with_notification(
        self,
        pattern: str
    ) -> int:
        """
        失效缓存并通知所有节点
        
        通过 Redis Pub/Sub 广播失效消息，所有订阅的 Worker 节点
        将收到通知并失效本地缓存。
        
        Args:
            pattern: 缓存键模式（支持通配符）
            
        Returns:
            删除的缓存条目数量
            
        验证：需求 3.3
        """
        deleted_count = 0
        full_pattern = f"{self.config.hot_cache_prefix}:{pattern}"
        
        try:
            redis_client = self.pool_manager.get_redis_client()
            
            # 删除匹配的缓存键
            cursor = 0
            while True:
                cursor, keys = await redis_client.scan(
                    cursor=cursor,
                    match=full_pattern,
                    count=100
                )
                
                if keys:
                    deleted = await redis_client.delete(*keys)
                    deleted_count += deleted
                
                if cursor == 0:
                    break
            
            # 发布失效通知
            await redis_client.publish(
                self.config.pubsub_channel,
                pattern
            )
            self._stats.invalidation_notifications_sent += 1
            
            logger.info(
                f"缓存失效完成: pattern={pattern}, "
                f"deleted={deleted_count}, notification_sent=True"
            )
            
        except (RedisError, RedisConnectionError) as e:
            logger.warning(f"缓存失效操作失败: {e}")
            await self._enter_fallback_mode(f"缓存失效失败: {e}")
        except PoolNotInitializedError:
            logger.warning("Redis 连接池未初始化，无法执行缓存失效")
        
        return deleted_count
    
    async def sync_workflow_state(
        self,
        workflow_id: str,
        state: dict
    ) -> None:
        """
        同步工作流状态到 Redis
        
        将工作流状态同步到 Redis 以支持实时查询。
        
        Args:
            workflow_id: 工作流 ID
            state: 工作流状态
            
        验证：需求 3.4
        """
        key = f"{self.config.workflow_state_prefix}:{workflow_id}"
        
        try:
            redis_client = self.pool_manager.get_redis_client()
            
            # 添加时间戳
            state_with_timestamp = {
                **state,
                "_synced_at": datetime.now(timezone.utc).isoformat()
            }
            
            await redis_client.setex(
                key,
                self.config.workflow_state_ttl_seconds,
                json.dumps(state_with_timestamp, default=str)
            )
            
            # 发布状态变更通知
            channel = f"{self.config.workflow_state_channel_prefix}:{workflow_id}"
            await redis_client.publish(
                channel,
                json.dumps(state_with_timestamp, default=str)
            )
            
            logger.debug(f"工作流状态已同步: {workflow_id}")
            
        except (RedisError, RedisConnectionError) as e:
            logger.warning(f"工作流状态同步失败: {e}")
            await self._enter_fallback_mode(f"状态同步失败: {e}")
        except PoolNotInitializedError:
            logger.warning("Redis 连接池未初始化，无法同步工作流状态")
    
    async def get_workflow_state(
        self,
        workflow_id: str
    ) -> Optional[dict]:
        """
        获取工作流状态
        
        Args:
            workflow_id: 工作流 ID
            
        Returns:
            工作流状态，未找到返回 None
        """
        key = f"{self.config.workflow_state_prefix}:{workflow_id}"
        
        try:
            redis_client = self.pool_manager.get_redis_client()
            data = await redis_client.get(key)
            
            if data is not None:
                return json.loads(data)
            return None
            
        except (RedisError, RedisConnectionError) as e:
            logger.warning(f"获取工作流状态失败: {e}")
            return None
        except PoolNotInitializedError:
            logger.warning("Redis 连接池未初始化，无法获取工作流状态")
            return None
    
    async def subscribe_workflow_state(
        self,
        workflow_id: str,
        callback: Callable[[dict], Awaitable[None]]
    ) -> Optional[asyncio.Task]:
        """
        订阅工作流状态变更
        
        Args:
            workflow_id: 工作流 ID
            callback: 状态变更回调函数
            
        Returns:
            订阅任务，失败返回 None
        """
        channel = f"{self.config.workflow_state_channel_prefix}:{workflow_id}"
        
        try:
            redis_client = self.pool_manager.get_redis_client()
            pubsub = redis_client.pubsub()
            await pubsub.subscribe(channel)
            
            async def process_messages():
                while self._running:
                    try:
                        message = await pubsub.get_message(
                            ignore_subscribe_messages=True,
                            timeout=1.0
                        )
                        
                        if message is not None and message["type"] == "message":
                            data = json.loads(message["data"])
                            await callback(data)
                            
                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        logger.warning(f"处理工作流状态消息时出错: {e}")
                
                await pubsub.unsubscribe()
                await pubsub.aclose()
            
            task = asyncio.create_task(process_messages())
            return task
            
        except Exception as e:
            logger.warning(f"订阅工作流状态失败: {e}")
            return None
    
    def get_stats_dict(self) -> dict:
        """
        获取统计信息字典
        
        Returns:
            统计信息字典
        """
        total_requests = (
            self._stats.redis_hits + 
            self._stats.redis_misses + 
            self._stats.pg_hits + 
            self._stats.pg_misses
        )
        
        redis_requests = self._stats.redis_hits + self._stats.redis_misses
        redis_hit_rate = (
            self._stats.redis_hits / redis_requests 
            if redis_requests > 0 else 0.0
        )
        
        return {
            "redis_hits": self._stats.redis_hits,
            "redis_misses": self._stats.redis_misses,
            "redis_hit_rate": redis_hit_rate,
            "pg_hits": self._stats.pg_hits,
            "pg_misses": self._stats.pg_misses,
            "write_through_success": self._stats.write_through_success,
            "write_through_failures": self._stats.write_through_failures,
            "fallback_mode": self._fallback_mode,
            "fallback_activations": self._stats.fallback_activations,
            "invalidation_notifications_sent": self._stats.invalidation_notifications_sent,
            "invalidation_notifications_received": self._stats.invalidation_notifications_received,
            "total_requests": total_requests,
        }
