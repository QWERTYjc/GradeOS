"""
数据库连接工具

提供数据库连接池管理，支持统一连接池管理器和传统连接池两种模式。
支持数据库降级：连接失败时自动切换到无数据库模式。

验证：需求 11.6, 11.7
"""

import os
import logging
from typing import Optional
from contextlib import asynccontextmanager
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from src.utils.pool_manager import UnifiedPoolManager, PoolNotInitializedError
from src.config.deployment_mode import get_deployment_mode, DeploymentMode


logger = logging.getLogger(__name__)


class DatabaseConfig:
    """数据库配置"""
    
    def __init__(self):
        # 优先使用 DATABASE_URL，否则从分离的环境变量构建
        database_url = os.getenv("DATABASE_URL", "")
        if database_url:
            self._connection_string = database_url
            # 从 URL 解析出 host 等信息用于日志
            self.host = "from-database-url"
            self.port = 5432
            self.database = "from-database-url"
            self.user = "from-database-url"
            self.password = "***"
        else:
            self.host = os.getenv("DB_HOST", "localhost")
            self.port = int(os.getenv("DB_PORT", "5432"))
            self.database = os.getenv("DB_NAME", "ai_grading")
            self.user = os.getenv("DB_USER", "postgres")
            self.password = os.getenv("DB_PASSWORD", "postgres")
            self._connection_string = None
        
        self.min_size = int(os.getenv("DB_POOL_MIN_SIZE", "2"))
        self.max_size = int(os.getenv("DB_POOL_MAX_SIZE", "10"))
    
    @property
    def connection_string(self) -> str:
        """获取连接字符串"""
        if self._connection_string:
            return self._connection_string
        return (
            f"postgresql://{self.user}:{self.password}@"
            f"{self.host}:{self.port}/{self.database}"
        )



class Database:
    """
    数据库连接池管理器
    
    支持两种模式：
    1. 统一连接池模式：使用 UnifiedPoolManager（推荐）
    2. 传统模式：使用独立的 AsyncConnectionPool
    
    支持数据库降级：
    - 连接失败时自动降级到无数据库模式
    - 降级后系统继续运行，使用内存缓存
    
    验证：需求 2.1, 11.6, 11.7
    """
    
    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.config = config or DatabaseConfig()
        self._pool: Optional[AsyncConnectionPool] = None
        self._use_unified_pool = False
        self._unified_pool_manager: Optional[UnifiedPoolManager] = None
        self._degraded_mode = False  # 降级模式标志
        self._deployment_config = get_deployment_mode()
    
    @property
    def is_degraded(self) -> bool:
        """是否处于降级模式"""
        return self._degraded_mode
    
    @property
    def is_available(self) -> bool:
        """数据库是否可用"""
        return not self._degraded_mode and (
            self._use_unified_pool or self._pool is not None
        )
    
    async def connect(self, use_unified_pool: bool = True) -> None:
        """
        初始化连接池
        
        支持数据库降级：
        - 如果是无数据库模式，直接进入降级模式
        - 如果连接失败，自动降级到无数据库模式
        
        Args:
            use_unified_pool: 是否使用统一连接池管理器
            
        验证：需求 11.6, 11.7
        """
        # 检查部署模式
        if self._deployment_config.is_no_database_mode:
            logger.info("无数据库模式：跳过数据库连接")
            self._degraded_mode = True
            return
        
        # 尝试使用统一连接池
        if use_unified_pool:
            try:
                self._unified_pool_manager = await UnifiedPoolManager.get_instance()
                if self._unified_pool_manager.is_initialized:
                    self._use_unified_pool = True
                    self._degraded_mode = False
                    logger.debug("使用统一连接池管理器")
                    return
            except Exception as e:
                logger.warning(f"无法使用统一连接池管理器: {e}")
                logger.info("尝试降级到传统连接池...")
        
        # 回退到传统连接池
        if self._pool is None:
            try:
                import asyncio
                self._pool = AsyncConnectionPool(
                    conninfo=self.config.connection_string,
                    min_size=self.config.min_size,
                    max_size=self.config.max_size,
                    kwargs={"row_factory": dict_row},
                    open=False  # Don't open immediately
                )
                # Add 3 second timeout for connection
                await asyncio.wait_for(self._pool.open(), timeout=3.0)
                self._degraded_mode = False
                logger.info("使用传统数据库连接池")
            except asyncio.TimeoutError:
                logger.error("数据库连接超时，降级到无数据库模式")
                self._pool = None
                self._degraded_mode = True
                logger.warning("系统将使用内存缓存继续运行")
            except Exception as e:
                logger.error(f"无法连接到数据库: {e}")
                logger.warning("降级到无数据库模式")
                self._pool = None
                self._degraded_mode = True
                logger.warning("系统将使用内存缓存继续运行")
    
    async def disconnect(self) -> None:
        """关闭连接池"""
        if self._use_unified_pool:
            # 统一连接池由 UnifiedPoolManager 管理，不在这里关闭
            self._use_unified_pool = False
            self._unified_pool_manager = None
            logger.info("断开统一连接池连接")
        elif self._pool is not None:
            await self._pool.close()
            self._pool = None
            logger.info("关闭传统数据库连接池")
    
    @asynccontextmanager
    async def connection(self):
        """
        获取数据库连接
        
        如果处于降级模式，抛出异常提示调用者使用替代方案
        """
        # 检查降级模式
        if self._degraded_mode:
            raise RuntimeError(
                "数据库不可用（降级模式）。"
                "请使用内存缓存或其他替代方案。"
            )
        
        # 使用统一连接池
        if self._use_unified_pool and self._unified_pool_manager:
            async with self._unified_pool_manager.pg_connection() as conn:
                yield conn
            return
        
        # 使用传统连接池
        if self._pool is None:
            await self.connect(use_unified_pool=False)
        
        if self._pool is None:
            raise RuntimeError("数据库连接不可用")
        
        async with self._pool.connection() as conn:
            yield conn
    
    @asynccontextmanager
    async def transaction(self):
        """
        获取事务连接
        
        如果处于降级模式，抛出异常提示调用者使用替代方案
        """
        # 检查降级模式
        if self._degraded_mode:
            raise RuntimeError(
                "数据库不可用（降级模式）。"
                "请使用内存缓存或其他替代方案。"
            )
        
        # 使用统一连接池
        if self._use_unified_pool and self._unified_pool_manager:
            async with self._unified_pool_manager.pg_transaction() as conn:
                yield conn
            return
        
        # 使用传统连接池
        async with self.connection() as conn:
            async with conn.transaction():
                yield conn


# 全局数据库实例
db = Database()


async def init_db_pool(use_unified_pool: bool = True) -> None:
    """
    初始化数据库连接池
    
    Args:
        use_unified_pool: 是否使用统一连接池管理器
    """
    await db.connect(use_unified_pool=use_unified_pool)


async def close_db_pool() -> None:
    """关闭数据库连接池"""
    await db.disconnect()


async def get_db_pool() -> AsyncConnectionPool:
    """
    获取数据库连接池
    
    用于 Temporal Workers 和其他需要直接访问连接池的组件。
    
    Returns:
        AsyncConnectionPool: 数据库连接池实例
        
    注意：如果使用统一连接池，此方法将返回 None
    """
    if db._use_unified_pool:
        logger.warning("使用统一连接池时，不应直接访问连接池，请使用 db.connection() 或 db.transaction()")
        return None
    
    if db._pool is None:
        await db.connect(use_unified_pool=False)
    return db._pool
