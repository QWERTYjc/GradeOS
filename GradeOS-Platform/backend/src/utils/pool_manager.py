"""
统一连接池管理器

提供 PostgreSQL 和 Redis 的共享连接池，
供 Temporal Activities、LangGraph Checkpointer 和 Repository 层使用。

验证：需求 2.1, 8.1, 8.2, 8.3, 8.4, 8.5
"""

import asyncio
import logging
import os
from typing import Optional, Any
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool, PoolTimeout
import redis.asyncio as redis
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError


logger = logging.getLogger(__name__)


class PoolError(Exception):
    """连接池错误基类"""
    pass


class ConnectionTimeoutError(PoolError):
    """连接获取超时错误"""
    pass


class PoolExhaustedError(PoolError):
    """连接池耗尽错误"""
    pass


class PoolNotInitializedError(PoolError):
    """连接池未初始化错误"""
    pass


@dataclass
class PoolConfig:
    """连接池配置"""
    # PostgreSQL 配置
    pg_dsn: str = ""
    pg_min_size: int = 5
    pg_max_size: int = 20
    pg_connection_timeout: float = 5.0
    pg_idle_timeout: float = 300.0  # 5 分钟
    pg_max_lifetime: float = 3600.0  # 1 小时
    
    # Redis 配置
    redis_url: str = ""
    redis_max_connections: int = 50
    redis_connection_timeout: float = 5.0
    redis_socket_keepalive: bool = True
    redis_health_check_interval: int = 30
    
    # 关闭配置
    shutdown_timeout: float = 30.0
    
    @classmethod
    def from_env(cls) -> "PoolConfig":
        """从环境变量创建配置"""
        # 优先使用 DATABASE_URL，否则从分离的环境变量构建
        pg_dsn = os.getenv("DATABASE_URL", "")
        if not pg_dsn:
            # 只有当显式设置了 DB_HOST 时才构建 DSN，否则保持为空
            pg_host = os.getenv("DB_HOST")
            if pg_host:
                pg_port = os.getenv("DB_PORT", "5432")
                pg_database = os.getenv("DB_NAME", "ai_grading")
                pg_user = os.getenv("DB_USER", "postgres")
                pg_password = os.getenv("DB_PASSWORD", "postgres")
                
                pg_dsn = (
                    f"postgresql://{pg_user}:{pg_password}@"
                    f"{pg_host}:{pg_port}/{pg_database}"
                )
        
        # 优先使用 REDIS_URL，否则从分离的环境变量构建
        redis_url = os.getenv("REDIS_URL", "")
        if not redis_url:
            # 只有当显式设置了 REDIS_HOST 时才构建 URL
            redis_host = os.getenv("REDIS_HOST")
            if redis_host:
                redis_port = os.getenv("REDIS_PORT", "6379")
                redis_password = os.getenv("REDIS_PASSWORD", "")
                redis_db = os.getenv("REDIS_DB", "0")
                
                if redis_password:
                    redis_url = f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}"
                else:
                    redis_url = f"redis://{redis_host}:{redis_port}/{redis_db}"
        
        return cls(
            pg_dsn=pg_dsn,
            pg_min_size=int(os.getenv("DB_POOL_MIN_SIZE", "5")),
            pg_max_size=int(os.getenv("DB_POOL_MAX_SIZE", "20")),
            pg_connection_timeout=float(os.getenv("DB_CONNECTION_TIMEOUT", "5.0")),
            pg_idle_timeout=float(os.getenv("DB_IDLE_TIMEOUT", "300.0")),
            redis_url=redis_url,
            redis_max_connections=int(os.getenv("REDIS_MAX_CONNECTIONS", "50")),
            redis_connection_timeout=float(os.getenv("REDIS_CONNECTION_TIMEOUT", "5.0")),
            shutdown_timeout=float(os.getenv("POOL_SHUTDOWN_TIMEOUT", "30.0")),
        )




class UnifiedPoolManager:
    """
    统一连接池管理器
    
    提供 PostgreSQL 和 Redis 的共享连接池，
    供 Temporal Activities、LangGraph Checkpointer 和 Repository 层使用。
    
    特性：
    - 单例模式确保全局唯一实例
    - 支持 PostgreSQL 和 Redis 连接池
    - 提供上下文管理器获取和归还连接
    - 支持健康检查
    - 支持优雅关闭
    - 连接超时处理
    
    验证：需求 2.1, 8.1, 8.2, 8.3, 8.4, 8.5
    """
    
    _instance: Optional["UnifiedPoolManager"] = None
    _lock: asyncio.Lock = asyncio.Lock()
    
    def __init__(self):
        """初始化（私有，请使用 get_instance）"""
        self._pg_pool: Optional[AsyncConnectionPool] = None
        self._redis_client: Optional[redis.Redis] = None
        self._config: Optional[PoolConfig] = None
        self._initialized = False
        self._shutting_down = False
        self._active_operations: int = 0
        self._operations_lock = asyncio.Lock()
    
    @classmethod
    async def get_instance(cls) -> "UnifiedPoolManager":
        """
        获取单例实例
        
        Returns:
            UnifiedPoolManager: 单例实例
        """
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    @classmethod
    def get_instance_sync(cls) -> "UnifiedPoolManager":
        """
        同步获取单例实例（用于非异步上下文）
        
        Returns:
            UnifiedPoolManager: 单例实例
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset_instance(cls) -> None:
        """重置单例实例（仅用于测试）"""
        cls._instance = None
    
    @property
    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized
    
    @property
    def config(self) -> Optional[PoolConfig]:
        """获取当前配置"""
        return self._config
    
    async def initialize(
        self,
        config: Optional[PoolConfig] = None,
        pg_dsn: Optional[str] = None,
        redis_url: Optional[str] = None,
        **kwargs
    ) -> None:
        """
        初始化连接池
        
        Args:
            config: 连接池配置对象
            pg_dsn: PostgreSQL 连接字符串（可选，覆盖 config）
            redis_url: Redis 连接字符串（可选，覆盖 config）
            **kwargs: 其他配置参数
            
        Raises:
            PoolError: 初始化失败时抛出
            
        验证：需求 8.1
        """
        # 检查是否强制离线模式
        if os.getenv("OFFLINE_MODE", "false").lower() == "true":
            logger.info("离线模式：跳过数据库和 Redis 连接池初始化")
            self._initialized = True
            return
        
        if self._initialized:
            logger.warning("连接池已初始化，跳过重复初始化")
            return
        
        # 构建配置
        if config is None:
            config = PoolConfig.from_env()
        
        # 覆盖配置
        if pg_dsn:
            config.pg_dsn = pg_dsn
        if redis_url:
            config.redis_url = redis_url
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        self._config = config
        
        try:
            # 初始化 PostgreSQL 连接池
            await self._init_pg_pool()
            
            # 初始化 Redis 连接池
            await self._init_redis_pool()
            
            self._initialized = True
            logger.debug(
                f"统一连接池初始化完成: "
                f"PostgreSQL(min={config.pg_min_size}, max={config.pg_max_size}), "
                f"Redis(max={config.redis_max_connections})"
            )
            
        except Exception as e:
            logger.error(f"连接池初始化失败: {e}")
            # 清理已创建的资源
            await self._cleanup()
            raise PoolError(f"连接池初始化失败: {e}") from e
    
    async def _init_pg_pool(self) -> None:
        """初始化 PostgreSQL 连接池"""
        if not self._config or not self._config.pg_dsn:
            logger.info("PostgreSQL DSN 未配置，跳过 PostgreSQL 连接池初始化")
            return
        
        self._pg_pool = AsyncConnectionPool(
            conninfo=self._config.pg_dsn,
            min_size=self._config.pg_min_size,
            max_size=self._config.pg_max_size,
            timeout=self._config.pg_connection_timeout,
            max_idle=self._config.pg_idle_timeout,
            max_lifetime=self._config.pg_max_lifetime,
            kwargs={"row_factory": dict_row},
            open=False,
        )
        await asyncio.wait_for(self._pg_pool.open(), timeout=3.0)
        logger.debug("PostgreSQL 连接池初始化完成")
    
    async def _init_redis_pool(self) -> None:
        """初始化 Redis 连接池"""
        if not self._config or not self._config.redis_url:
            logger.debug("Redis URL 未配置，跳过 Redis 连接池初始化")
            return
        
        try:
            self._redis_client = redis.from_url(
                self._config.redis_url,
                max_connections=self._config.redis_max_connections,
                socket_timeout=self._config.redis_connection_timeout,
                socket_connect_timeout=self._config.redis_connection_timeout,
                socket_keepalive=self._config.redis_socket_keepalive,
                health_check_interval=self._config.redis_health_check_interval,
                decode_responses=False,  # 保持字节模式以支持二进制数据
            )
            # 测试连接
            await asyncio.wait_for(self._redis_client.ping(), timeout=2.0)
            logger.info("Redis 连接池初始化完成")
        except Exception as e:
            logger.debug(f"Redis 连接失败 (将在降级模式下运行): {e}")
            self._redis_client = None
    
    async def _cleanup(self) -> None:
        """清理资源"""
        if self._pg_pool is not None:
            try:
                await self._pg_pool.close()
            except Exception as e:
                logger.warning(f"关闭 PostgreSQL 连接池时出错: {e}")
            self._pg_pool = None
        
        if self._redis_client is not None:
            try:
                await self._redis_client.aclose()
            except Exception as e:
                logger.warning(f"关闭 Redis 连接时出错: {e}")
            self._redis_client = None

    async def shutdown(self, timeout: Optional[float] = None) -> None:
        """
        优雅关闭所有连接
        
        等待进行中的操作完成，然后关闭所有连接。
        
        Args:
            timeout: 关闭超时时间（秒），默认使用配置值
            
        验证：需求 8.5
        """
        if not self._initialized:
            return
        
        self._shutting_down = True
        timeout = timeout or (self._config.shutdown_timeout if self._config else 30.0)
        
        logger.info(f"开始优雅关闭连接池，超时时间: {timeout}秒")
        
        # 等待进行中的操作完成
        start_time = asyncio.get_event_loop().time()
        while self._active_operations > 0:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout:
                logger.warning(
                    f"关闭超时，仍有 {self._active_operations} 个操作进行中，强制关闭"
                )
                break
            await asyncio.sleep(0.1)
        
        # 关闭连接池
        await self._cleanup()
        
        self._initialized = False
        self._shutting_down = False
        logger.info("连接池已关闭")
    
    def _check_initialized(self) -> None:
        """检查是否已初始化"""
        if not self._initialized:
            raise PoolNotInitializedError("连接池未初始化，请先调用 initialize()")
        if self._shutting_down:
            raise PoolError("连接池正在关闭，无法获取连接")
    
    async def _track_operation(self) -> None:
        """跟踪活跃操作数"""
        async with self._operations_lock:
            self._active_operations += 1
    
    async def _untrack_operation(self) -> None:
        """取消跟踪活跃操作数"""
        async with self._operations_lock:
            self._active_operations -= 1
    
    @asynccontextmanager
    async def pg_connection(self):
        """
        获取 PostgreSQL 连接
        
        使用上下文管理器自动归还连接到连接池。
        
        Yields:
            psycopg.AsyncConnection: PostgreSQL 异步连接
            
        Raises:
            PoolNotInitializedError: 连接池未初始化
            ConnectionTimeoutError: 获取连接超时
            PoolExhaustedError: 连接池耗尽
            
        验证：需求 8.2, 8.4
        """
        self._check_initialized()
        
        if self._pg_pool is None:
            raise PoolNotInitializedError("PostgreSQL 连接池未初始化")
        
        await self._track_operation()
        try:
            async with self._pg_pool.connection(
                timeout=self._config.pg_connection_timeout if self._config else 5.0
            ) as conn:
                yield conn
        except PoolTimeout as e:
            raise ConnectionTimeoutError(
                f"获取 PostgreSQL 连接超时 "
                f"(timeout={self._config.pg_connection_timeout if self._config else 5.0}s): {e}"
            ) from e
        except Exception as e:
            if "pool exhausted" in str(e).lower():
                raise PoolExhaustedError(f"PostgreSQL 连接池耗尽: {e}") from e
            raise
        finally:
            await self._untrack_operation()
    
    @asynccontextmanager
    async def pg_transaction(self):
        """
        获取 PostgreSQL 事务连接
        
        使用上下文管理器自动提交或回滚事务。
        
        Yields:
            psycopg.AsyncConnection: PostgreSQL 异步连接（在事务中）
            
        验证：需求 2.2, 2.3
        """
        async with self.pg_connection() as conn:
            async with conn.transaction():
                yield conn
    
    def get_redis_client(self) -> redis.Redis:
        """
        获取 Redis 客户端
        
        Returns:
            redis.Redis: Redis 异步客户端
            
        Raises:
            PoolNotInitializedError: 连接池未初始化
        """
        self._check_initialized()
        
        if self._redis_client is None:
            raise PoolNotInitializedError("Redis 连接池未初始化")
        
        return self._redis_client
    
    @asynccontextmanager
    async def redis_connection(self):
        """
        获取 Redis 连接（上下文管理器形式）
        
        Yields:
            redis.Redis: Redis 异步客户端
            
        验证：需求 8.2
        """
        self._check_initialized()
        
        if self._redis_client is None:
            raise PoolNotInitializedError("Redis 连接池未初始化")
        
        await self._track_operation()
        try:
            yield self._redis_client
        finally:
            await self._untrack_operation()
    
    async def health_check(self) -> dict:
        """
        执行健康检查
        
        检查 PostgreSQL 和 Redis 连接是否正常。
        
        Returns:
            dict: 健康检查结果，包含各组件状态
            
        验证：需求 8.1
        """
        result = {
            "healthy": True,
            "postgresql": {"status": "unknown", "details": {}},
            "redis": {"status": "unknown", "details": {}},
        }
        
        # 检查 PostgreSQL
        if self._pg_pool is not None:
            try:
                async with self._pg_pool.connection(timeout=2.0) as conn:
                    await conn.execute("SELECT 1")
                logger.debug("PostgreSQL 连接池初始化完成")   
                pool_stats = self._pg_pool.get_stats()
                result["postgresql"] = {
                    "status": "healthy",
                    "details": {
                        "pool_size": pool_stats.get("pool_size", 0),
                        "pool_available": pool_stats.get("pool_available", 0),
                        "requests_waiting": pool_stats.get("requests_waiting", 0),
                        "connections_used": pool_stats.get("connections_num", 0),
                    }
                }
            except Exception as e:
                result["healthy"] = False
                result["postgresql"] = {
                    "status": "unhealthy",
                    "details": {"error": str(e)}
                }
        else:
            result["postgresql"] = {
                "status": "not_configured",
                "details": {}
            }
        
        # 检查 Redis
        if self._redis_client is not None:
            try:
                await self._redis_client.ping()
                info = await self._redis_client.info("clients")
                result["redis"] = {
                    "status": "healthy",
                    "details": {
                        "connected_clients": info.get("connected_clients", 0),
                    }
                }
            except Exception as e:
                result["healthy"] = False
                result["redis"] = {
                    "status": "unhealthy",
                    "details": {"error": str(e)}
                }
        else:
            result["redis"] = {
                "status": "not_configured",
                "details": {}
            }
        
        return result
    
    def get_pool_stats(self) -> dict:
        """
        获取连接池统计信息
        
        Returns:
            dict: 连接池统计信息
        """
        stats = {
            "initialized": self._initialized,
            "shutting_down": self._shutting_down,
            "active_operations": self._active_operations,
            "postgresql": {},
            "redis": {},
        }
        
        if self._pg_pool is not None:
            try:
                pg_stats = self._pg_pool.get_stats()
                stats["postgresql"] = {
                    "pool_size": pg_stats.get("pool_size", 0),
                    "pool_available": pg_stats.get("pool_available", 0),
                    "pool_min": self._config.pg_min_size if self._config else 0,
                    "pool_max": self._config.pg_max_size if self._config else 0,
                    "requests_waiting": pg_stats.get("requests_waiting", 0),
                }
            except Exception as e:
                stats["postgresql"] = {"error": str(e)}
        
        if self._redis_client is not None:
            stats["redis"] = {
                "max_connections": self._config.redis_max_connections if self._config else 0,
            }
        
        return stats


# 便捷函数
async def get_pool_manager() -> UnifiedPoolManager:
    """
    获取统一连接池管理器实例
    
    Returns:
        UnifiedPoolManager: 单例实例
    """
    return await UnifiedPoolManager.get_instance()


async def init_pool_manager(
    config: Optional[PoolConfig] = None,
    **kwargs
) -> UnifiedPoolManager:
    """
    初始化并获取统一连接池管理器
    
    Args:
        config: 连接池配置
        **kwargs: 其他配置参数
        
    Returns:
        UnifiedPoolManager: 已初始化的单例实例
    """
    manager = await UnifiedPoolManager.get_instance()
    if not manager.is_initialized:
        await manager.initialize(config=config, **kwargs)
    return manager

