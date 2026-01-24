"""
部署模式检测与配置

支持两种运行模式：
1. 数据库模式：完整功能，需要 PostgreSQL 和 Redis
2. 无数据库模式：轻量级部署，仅使用内存缓存和 LLM API

验证：需求 11.1, 11.8
"""

import os
import logging
from enum import Enum
from typing import Optional


logger = logging.getLogger(__name__)


class DeploymentMode(Enum):
    """部署模式枚举"""
    DATABASE = "database"      # 完整数据库模式
    NO_DATABASE = "no_database"  # 无数据库模式（轻量级）


class DeploymentConfig:
    """
    部署配置管理器
    
    根据环境变量自动检测运行模式：
    - 如果 DATABASE_URL 为空或未设置，使用无数据库模式
    - 如果 DATABASE_URL 已设置，使用数据库模式
    
    验证：需求 11.1, 11.8
    """
    
    def __init__(self):
        self._mode: Optional[DeploymentMode] = None
        self._database_url: Optional[str] = None
        self._redis_url: Optional[str] = None
        self._redis_configured: bool = False
        self._detect_mode()
    
    def _detect_mode(self) -> None:
        """
        检测部署模式
        
        检测逻辑：
        1. 检查 DATABASE_URL 环境变量
        2. 默认为数据库模式（使用 SQLite 或 PostgreSQL）
        """
        self._database_url = os.getenv("DATABASE_URL", "").strip()
        db_host = os.getenv("DB_HOST", "").strip()
        self._redis_url = os.getenv("REDIS_URL", "").strip()
        redis_host = os.getenv("REDIS_HOST", "").strip()
        offline_env = os.getenv("OFFLINE_MODE", "").strip().lower()
        force_offline = offline_env in ("1", "true", "yes")
        self._redis_configured = bool(self._redis_url or redis_host)

        if force_offline:
            self._mode = DeploymentMode.NO_DATABASE
            logger.info("检测到 OFFLINE_MODE=true，强制使用无数据库模式")
        elif self._database_url or db_host:
            self._mode = DeploymentMode.DATABASE
            if self._database_url:
                logger.info(f"检测到数据库配置：{self._mask_connection_string(self._database_url)}")
            else:
                logger.info(f"检测到数据库配置：DB_HOST={db_host}")
        else:
            self._mode = DeploymentMode.NO_DATABASE
            logger.info("DATABASE_URL 未设置，将使用无数据库模式")

        if self._redis_url:
            logger.info(f"检测到 Redis 配置：{self._mask_connection_string(self._redis_url)}")
        elif redis_host:
            logger.info(f"检测到 Redis 配置：REDIS_HOST={redis_host}")
        else:
            logger.info("未检测到 Redis 配置，将使用内存缓存")
    
    @staticmethod
    def _mask_connection_string(conn_str: str) -> str:
        """
        遮蔽连接字符串中的敏感信息
        
        Args:
            conn_str: 连接字符串
            
        Returns:
            遮蔽后的连接字符串
        """
        if not conn_str:
            return ""
        
        # 简单遮蔽：只显示协议和主机
        try:
            if "://" in conn_str:
                protocol, rest = conn_str.split("://", 1)
                if "@" in rest:
                    _, host_part = rest.split("@", 1)
                    return f"{protocol}://***@{host_part}"
                return f"{protocol}://{rest}"
            return "***"
        except Exception:
            return "***"
    
    @property
    def mode(self) -> DeploymentMode:
        """获取当前部署模式"""
        return self._mode
    
    @property
    def is_database_mode(self) -> bool:
        """是否为数据库模式"""
        return self._mode == DeploymentMode.DATABASE
    
    @property
    def is_no_database_mode(self) -> bool:
        """是否为无数据库模式"""
        return self._mode == DeploymentMode.NO_DATABASE
    
    @property
    def database_url(self) -> Optional[str]:
        """获取数据库 URL"""
        return self._database_url if self._database_url else None
    
    @property
    def redis_url(self) -> Optional[str]:
        """获取 Redis URL"""
        return self._redis_url if self._redis_url else None
    
    def get_feature_availability(self) -> dict:
        """
        获取功能可用性
        
        Returns:
            功能可用性字典
        """
        if self.is_database_mode:
            return {
                "grading": True,
                "persistence": True,
                "history": True,
                "analytics": True,
                "caching": self._redis_configured,
                "websocket": self._redis_configured,
                "mode": "database"
            }
        else:
            return {
                "grading": True,
                "persistence": False,
                "history": False,
                "analytics": False,
                "caching": True,  # 内存缓存
                "websocket": False,
                "mode": "no_database"
            }


# 全局配置实例
_deployment_config: Optional[DeploymentConfig] = None


def get_deployment_mode() -> DeploymentConfig:
    """
    获取部署配置实例（单例）
    
    Returns:
        DeploymentConfig: 部署配置实例
    """
    global _deployment_config
    if _deployment_config is None:
        _deployment_config = DeploymentConfig()
    return _deployment_config


def reset_deployment_mode() -> None:
    """
    重置部署模式（主要用于测试）
    """
    global _deployment_config
    _deployment_config = None
