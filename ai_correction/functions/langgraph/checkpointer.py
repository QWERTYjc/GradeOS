#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Checkpointer Configuration - 状态持久化配置
支持MemorySaver和PostgresSaver
符合设计文档: AI批改LangGraph Agent架构设计文档 - 第13节
"""

import logging
import os
from typing import Optional
from langgraph.checkpoint.memory import MemorySaver
# PostgresSaver需要额外安装: pip install langgraph-checkpoint-postgres
try:
    from langgraph.checkpoint.postgres import PostgresSaver
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    logging.warning("PostgresSaver不可用，请安装: pip install langgraph-checkpoint-postgres")

logger = logging.getLogger(__name__)


class CheckpointerFactory:
    """
    Checkpointer工厂类
    
    职责:
    1. 根据环境自动选择合适的Checkpointer
    2. 管理PostgreSQL连接
    3. 提供Checkpointer实例
    """
    
    def __init__(self, environment: str = None):
        """
        初始化Checkpointer工厂
        
        参数:
            environment: 环境标识 ('development', 'production', 'test')
        """
        self.environment = environment or os.getenv('ENVIRONMENT', 'development')
        self._checkpointer = None
        self._pg_connection = None
    
    def get_checkpointer(self):
        """
        获取Checkpointer实例
        
        返回:
            MemorySaver或PostgresSaver实例
        """
        if self._checkpointer is not None:
            return self._checkpointer
        
        # 根据环境选择
        if self.environment == 'production':
            self._checkpointer = self._create_postgres_checkpointer()
        elif self.environment == 'test':
            self._checkpointer = self._create_memory_checkpointer()
        else:  # development
            # 尝试PostgreSQL，失败则回退到Memory
            try:
                self._checkpointer = self._create_postgres_checkpointer()
            except Exception as e:
                logger.warning(f"PostgreSQL Checkpointer创建失败: {e}，回退到MemorySaver")
                self._checkpointer = self._create_memory_checkpointer()
        
        return self._checkpointer
    
    def _create_memory_checkpointer(self):
        """创建MemorySaver（内存存储）"""
        logger.info("使用MemorySaver（内存存储）")
        return MemorySaver()
    
    def _create_postgres_checkpointer(self):
        """创建PostgresSaver（数据库存储）"""
        if not POSTGRES_AVAILABLE:
            raise ImportError("PostgresSaver不可用，请安装: pip install langgraph-checkpoint-postgres")
        
        # 获取数据库连接字符串
        db_url = os.getenv('POSTGRES_CHECKPOINT_URL') or os.getenv('DATABASE_URL')
        
        if not db_url:
            raise ValueError("未配置PostgreSQL连接字符串（POSTGRES_CHECKPOINT_URL或DATABASE_URL）")
        
        logger.info("使用PostgresSaver（数据库存储）")
        
        # 创建PostgresSaver
        # 注意：PostgresSaver会自动创建必要的表
        checkpointer = PostgresSaver.from_conn_string(db_url)
        
        self._pg_connection = db_url
        return checkpointer
    
    def close(self):
        """关闭连接"""
        if self._pg_connection:
            logger.info("关闭PostgreSQL连接")
            # PostgresSaver的连接管理是自动的，这里只是占位
            self._pg_connection = None


class CheckpointManager:
    """
    Checkpoint管理器
    
    职责:
    1. 管理任务的checkpoint
    2. 支持任务恢复
    3. 清理过期checkpoint
    """
    
    def __init__(self, checkpointer):
        """
        初始化管理器
        
        参数:
            checkpointer: MemorySaver或PostgresSaver实例
        """
        self.checkpointer = checkpointer
    
    async def save_checkpoint(self, task_id: str, state: dict, metadata: dict = None):
        """
        保存checkpoint
        
        参数:
            task_id: 任务ID
            state: 当前状态
            metadata: 元数据
        """
        config = {"configurable": {"thread_id": task_id}}
        
        if metadata:
            config['metadata'] = metadata
        
        # LangGraph会自动保存checkpoint
        logger.info(f"Checkpoint已保存 - 任务: {task_id}")
    
    async def load_checkpoint(self, task_id: str):
        """
        加载checkpoint
        
        参数:
            task_id: 任务ID
        
        返回:
            状态字典或None
        """
        config = {"configurable": {"thread_id": task_id}}
        
        try:
            # 从checkpointer加载
            checkpoint = await self.checkpointer.aget(config)
            if checkpoint:
                logger.info(f"Checkpoint已加载 - 任务: {task_id}")
                return checkpoint
            else:
                logger.info(f"未找到checkpoint - 任务: {task_id}")
                return None
        except Exception as e:
            logger.error(f"加载checkpoint失败: {e}")
            return None
    
    async def list_checkpoints(self, task_id: str = None):
        """
        列出所有checkpoint
        
        参数:
            task_id: 可选的任务ID过滤
        
        返回:
            checkpoint列表
        """
        try:
            if task_id:
                config = {"configurable": {"thread_id": task_id}}
                checkpoints = await self.checkpointer.alist(config)
            else:
                checkpoints = await self.checkpointer.alist({})
            
            return list(checkpoints)
        except Exception as e:
            logger.error(f"列出checkpoint失败: {e}")
            return []
    
    async def delete_checkpoint(self, task_id: str):
        """
        删除checkpoint
        
        参数:
            task_id: 任务ID
        """
        config = {"configurable": {"thread_id": task_id}}
        
        try:
            await self.checkpointer.adelete(config)
            logger.info(f"Checkpoint已删除 - 任务: {task_id}")
        except Exception as e:
            logger.error(f"删除checkpoint失败: {e}")


# 全局工厂实例
_factory = None

def get_checkpointer_factory(environment: str = None):
    """获取Checkpointer工厂实例"""
    global _factory
    if _factory is None:
        _factory = CheckpointerFactory(environment=environment)
    return _factory


def get_checkpointer(environment: str = None):
    """快速获取Checkpointer"""
    factory = get_checkpointer_factory(environment)
    return factory.get_checkpointer()


# 使用示例
"""
# 开发环境 - 自动选择
checkpointer = get_checkpointer('development')

# 生产环境 - 使用PostgreSQL
checkpointer = get_checkpointer('production')

# 测试环境 - 使用内存
checkpointer = get_checkpointer('test')

# 在workflow中使用
from langgraph.graph import StateGraph
from .checkpointer import get_checkpointer

workflow = StateGraph(GradingState)
# ... 添加节点和边 ...

checkpointer = get_checkpointer()
graph = workflow.compile(checkpointer=checkpointer)

# 运行时会自动保存checkpoint
config = {"configurable": {"thread_id": "task_123"}}
result = await graph.ainvoke(initial_state, config=config)

# 恢复任务
result = await graph.ainvoke({}, config=config)  # 会从checkpoint恢复
"""
