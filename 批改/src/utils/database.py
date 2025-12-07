"""数据库连接工具"""

import os
from typing import Optional
from contextlib import asynccontextmanager
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool


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
    """数据库连接池管理器"""
    
    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.config = config or DatabaseConfig()
        self._pool: Optional[AsyncConnectionPool] = None
    
    async def connect(self) -> None:
        """初始化连接池"""
        if self._pool is None:
            self._pool = AsyncConnectionPool(
                conninfo=self.config.connection_string,
                min_size=self.config.min_size,
                max_size=self.config.max_size,
                kwargs={"row_factory": dict_row}
            )
            await self._pool.open()
    
    async def disconnect(self) -> None:
        """关闭连接池"""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
    
    @asynccontextmanager
    async def connection(self):
        """获取数据库连接"""
        if self._pool is None:
            await self.connect()
        
        async with self._pool.connection() as conn:
            yield conn
    
    @asynccontextmanager
    async def transaction(self):
        """获取事务连接"""
        async with self.connection() as conn:
            async with conn.transaction():
                yield conn


# 全局数据库实例
db = Database()
