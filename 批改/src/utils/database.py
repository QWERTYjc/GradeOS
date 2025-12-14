"""
数据库连接工具

提供数据库连接池管理，支持统一连接池管理器和传统连接池两种模式。
"""

import os
import logging
from typing import Optional
from contextlib import asynccontextmanager
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from src.utils.pool_manager import UnifiedPoolManager, PoolNotInitializedError


logger = logging.getLogger(__name__)


class DatabaseConfig:
    """数据库配置"""
    
    def __init__(self):
        self.host = os.getenv("DB_HOST", "localhost")
        self.port = int(os.getenv("DB_PORT", "5432"))
        self.database = os.getenv("DB_NAME", "ai_grading")
        self.user = os.getenv("DB_USER", "postgres")
        self.password = os.getenv("DB_PASSWORD", "postgres")
        self.min_size = int(os.getenv("DB_POOL_MIN_SIZE", "2"))
        self.max_size = int(os.getenv("DB_POOL_MAX_SIZE", "10"))
    
    @property
    def connection_string(self) -> str:
        """获取连接字符串"""
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
    
    验证：需求 2.1
    """
    
    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.config = config or DatabaseConfig()
        self._pool: Optional[AsyncConnectionPool] = None
        self._use_unified_pool = False
        self._unified_pool_manager: Optional[UnifiedPoolManager] = None
    
    async def connect(self, use_unified_pool: bool = True) -> None:
        """
        初始化连接池
        
        Args:
            use_unified_pool: 是否使用统一连接池管理器
        """
        # 尝试使用统一连接池
        if use_unified_pool:
            try:
                self._unified_pool_manager = await UnifiedPoolManager.get_instance()
                if self._unified_pool_manager.is_initialized:
                    self._use_unified_pool = True
                    logger.info("使用统一连接池管理器")
                    return
            except Exception as e:
                logger.warning(f"无法使用统一连接池管理器: {e}")
        
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
                logger.info("使用传统数据库连接池")
            except asyncio.TimeoutError:
                logger.error("数据库连接超时，启用离线模式")
                self._pool = None
            except Exception as e:
                logger.error(f"无法连接到数据库: {e}")
                self._pool = None
    
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
        """获取数据库连接"""
        # 使用统一连接池
        if self._use_unified_pool and self._unified_pool_manager:
            async with self._unified_pool_manager.pg_connection() as conn:
                yield conn
            return
        
        # 使用传统连接池
        if self._pool is None:
            await self.connect(use_unified_pool=False)
        
        async with self._pool.connection() as conn:
            yield conn
    
    @asynccontextmanager
    async def transaction(self):
        """获取事务连接"""
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
