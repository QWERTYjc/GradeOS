#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Database Migration Script - 数据库迁移脚本
使用Alembic进行数据库版本管理
符合设计文档: AI批改LangGraph Agent架构设计文档 - 第15节
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from functions.database.models import Base
import logging

logger = logging.getLogger(__name__)


class DatabaseMigrationManager:
    """
    数据库迁移管理器
    
    职责:
    1. 初始化Alembic配置
    2. 生成迁移脚本
    3. 执行数据库迁移
    4. 回滚迁移
    """
    
    def __init__(self, database_url: str = None):
        """
        初始化迁移管理器
        
        参数:
            database_url: 数据库连接字符串
        """
        self.database_url = database_url or os.getenv('DATABASE_URL', 'sqlite:///ai_correction.db')
        self.alembic_ini_path = project_root / 'alembic.ini'
        self.migrations_dir = project_root / 'migrations'
        
    def init_alembic(self):
        """初始化Alembic配置"""
        if not self.migrations_dir.exists():
            logger.info("初始化Alembic...")
            
            # 创建Alembic配置
            alembic_cfg = Config()
            alembic_cfg.set_main_option('script_location', str(self.migrations_dir))
            alembic_cfg.set_main_option('sqlalchemy.url', self.database_url)
            
            # 初始化迁移目录
            command.init(alembic_cfg, str(self.migrations_dir))
            logger.info(f"Alembic已初始化 - 目录: {self.migrations_dir}")
        else:
            logger.info("Alembic已存在")
    
    def create_migration(self, message: str = None):
        """
        创建新的迁移脚本
        
        参数:
            message: 迁移消息
        """
        if not message:
            message = "auto_migration"
        
        logger.info(f"创建迁移脚本: {message}")
        
        alembic_cfg = self._get_config()
        
        # 自动生成迁移脚本
        command.revision(
            alembic_cfg,
            message=message,
            autogenerate=True
        )
        
        logger.info("迁移脚本已创建")
    
    def upgrade(self, revision: str = 'head'):
        """
        升级数据库到指定版本
        
        参数:
            revision: 目标版本，默认为最新版本(head)
        """
        logger.info(f"升级数据库到版本: {revision}")
        
        alembic_cfg = self._get_config()
        command.upgrade(alembic_cfg, revision)
        
        logger.info("数据库升级完成")
    
    def downgrade(self, revision: str = '-1'):
        """
        降级数据库到指定版本
        
        参数:
            revision: 目标版本，默认为上一个版本(-1)
        """
        logger.info(f"降级数据库到版本: {revision}")
        
        alembic_cfg = self._get_config()
        command.downgrade(alembic_cfg, revision)
        
        logger.info("数据库降级完成")
    
    def current(self):
        """显示当前数据库版本"""
        alembic_cfg = self._get_config()
        command.current(alembic_cfg)
    
    def history(self):
        """显示迁移历史"""
        alembic_cfg = self._get_config()
        command.history(alembic_cfg)
    
    def _get_config(self) -> Config:
        """获取Alembic配置"""
        alembic_cfg = Config(str(self.alembic_ini_path))
        alembic_cfg.set_main_option('script_location', str(self.migrations_dir))
        alembic_cfg.set_main_option('sqlalchemy.url', self.database_url)
        return alembic_cfg
    
    def create_all_tables(self):
        """直接创建所有表（不使用迁移）"""
        logger.info("直接创建所有表...")
        
        engine = create_engine(self.database_url)
        Base.metadata.create_all(engine)
        
        logger.info("所有表已创建")
    
    def drop_all_tables(self):
        """删除所有表（危险操作）"""
        logger.warning("删除所有表...")
        
        engine = create_engine(self.database_url)
        Base.metadata.drop_all(engine)
        
        logger.warning("所有表已删除")


def init_database(database_url: str = None):
    """
    初始化数据库
    
    这是一个快速初始化函数，用于开发环境
    生产环境应该使用Alembic迁移
    
    参数:
        database_url: 数据库连接字符串
    """
    manager = DatabaseMigrationManager(database_url)
    manager.create_all_tables()
    logger.info("数据库初始化完成")


def migrate_database(message: str = None, database_url: str = None):
    """
    执行数据库迁移
    
    参数:
        message: 迁移消息
        database_url: 数据库连接字符串
    """
    manager = DatabaseMigrationManager(database_url)
    
    # 初始化Alembic（如果需要）
    manager.init_alembic()
    
    # 创建迁移脚本
    manager.create_migration(message)
    
    # 执行升级
    manager.upgrade()
    
    logger.info("数据库迁移完成")


# CLI命令
if __name__ == '__main__':
    import argparse
    
    logging.basicConfig(level=logging.INFO)
    
    parser = argparse.ArgumentParser(description='数据库迁移工具')
    parser.add_argument('command', choices=['init', 'create', 'upgrade', 'downgrade', 'current', 'history', 'create_tables'],
                      help='命令')
    parser.add_argument('-m', '--message', help='迁移消息（用于create命令）')
    parser.add_argument('-r', '--revision', default='head', help='目标版本（用于upgrade/downgrade命令）')
    parser.add_argument('--url', help='数据库连接字符串')
    
    args = parser.parse_args()
    
    manager = DatabaseMigrationManager(database_url=args.url)
    
    if args.command == 'init':
        manager.init_alembic()
    elif args.command == 'create':
        manager.create_migration(args.message)
    elif args.command == 'upgrade':
        manager.upgrade(args.revision)
    elif args.command == 'downgrade':
        manager.downgrade(args.revision)
    elif args.command == 'current':
        manager.current()
    elif args.command == 'history':
        manager.history()
    elif args.command == 'create_tables':
        manager.create_all_tables()


# 使用示例
"""
# 1. 初始化Alembic
python migration.py init

# 2. 创建迁移脚本
python migration.py create -m "添加新表"

# 3. 升级到最新版本
python migration.py upgrade

# 4. 降级到上一个版本
python migration.py downgrade -r -1

# 5. 查看当前版本
python migration.py current

# 6. 查看迁移历史
python migration.py history

# 7. 直接创建所有表（开发环境）
python migration.py create_tables

# 8. 使用自定义数据库URL
python migration.py upgrade --url postgresql://user:pass@host:5432/db
"""
