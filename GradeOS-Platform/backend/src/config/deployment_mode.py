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
        self._detect_mode()
    
    def _detect_mode(self) -> None:
        """
        检测部署模式
        
        检测逻辑：
        1. 检查 DATABASE_URL 环境变量
        2. 如果为空或未设置，使用无数据库模式
        3. 如果已设置，使用数据库模式
        """
        self._database_url = os.getenv("DATABASE_URL", "").strip()
        self._redis_url = os.getenv("REDIS_URL", "").strip()
        
        # 检测模式
        if not self._database_url:
            self._mode = DeploymentMode.NO_DATABASE
            logger.info("检测到无数据库模式：DATABASE_URL 未设置")
            logger.info("系统将使用内存缓存和 LLM API 运行")
        else:
            self._mode = DeploymentMode.DATABASE
            logger.info("检测到数据库模式：DATABASE_URL 已设置")
            logger.info(f"数据库连接: {self._mask_connection_string(self._database_url)}")
            
            if self._redis_url:
                logger.info(f"Redis 连接: {self._mask_connection_string(self._redis_url)}")
            else:
                logger.warning("Redis URL 未设置，某些功能可能受限")
    
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
                "caching": bool(self._redis_url),
                "websocket": bool(self._redis_url),
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
