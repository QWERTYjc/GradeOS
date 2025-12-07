#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Streamlit实时日志处理器
将日志输出实时传递到Streamlit界面
"""

import logging
import streamlit as st
from typing import Optional, List
from datetime import datetime
import threading


class StreamlitLogHandler(logging.Handler):
    """将日志输出到Streamlit的处理器"""
    
    def __init__(self, log_container=None):
        super().__init__()
        self.log_container = log_container
        self.logs: List[dict] = []
        self.lock = threading.Lock()
        self.max_logs = 2000  # 增加到2000条日志，确保捕获完整日志
        self.update_callback = None  # 外部更新回调函数
        
    def emit(self, record):
        """发送日志记录"""
        try:
            log_entry = {
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'level': record.levelname,
                'message': self.format(record),
                'agent': self._extract_agent_name(record.getMessage())
            }
            
            with self.lock:
                self.logs.append(log_entry)
                # 保持日志数量在限制内
                if len(self.logs) > self.max_logs:
                    self.logs = self.logs[-self.max_logs:]
            
            # 如果log_container存在，实时更新
            if self.log_container is not None:
                try:
                    self._update_streamlit(log_entry)
                except:
                    pass  # 忽略更新错误，避免阻塞
                    
        except Exception:
            pass  # 忽略日志处理错误
    
    def _extract_agent_name(self, message: str) -> str:
        """从日志消息中提取Agent名称"""
        # 尝试多种格式提取Agent名称
        import re
        
        # 格式1: [AgentName] 或 [AgentNameAgent]
        match = re.search(r'\[([A-Za-z]+(?:Agent)?)\]', message)
        if match:
            return match.group(1)
        
        # 格式2: AgentName: 或 AgentNameAgent:
        match = re.search(r'([A-Za-z]+(?:Agent)?):', message)
        if match:
            agent_name = match.group(1)
            if 'Agent' in agent_name or len(agent_name) > 5:
                return agent_name
        
        # 格式3: 包含常见Agent关键词
        agent_keywords = [
            'Orchestrator', 'MultiModal', 'Question', 'Answer', 'Rubric',
            'Student', 'Batch', 'Grading', 'Result', 'Class'
        ]
        for keyword in agent_keywords:
            if keyword in message:
                return f"{keyword}Agent"
        
        return 'System'
    
    def _update_streamlit(self, log_entry: dict):
        """更新Streamlit显示（不直接更新，由外部调用get_logs获取）"""
        # Streamlit的更新机制不适合在这里直接更新
        # 日志会通过get_logs()方法在外部更新
        # 如果设置了更新回调，调用它
        if self.update_callback:
            try:
                self.update_callback()
            except Exception:
                pass  # 忽略回调错误，避免阻塞日志记录
    
    def set_update_callback(self, callback):
        """设置日志更新回调函数"""
        self.update_callback = callback
    
    def get_logs(self, level: Optional[str] = None, agent: Optional[str] = None) -> List[dict]:
        """获取日志列表"""
        with self.lock:
            logs = self.logs.copy()
        
        if level:
            logs = [log for log in logs if log['level'] == level]
        if agent:
            logs = [log for log in logs if agent in log['agent']]
        
        return logs
    
    def clear_logs(self):
        """清空日志"""
        with self.lock:
            self.logs.clear()


# 全局日志处理器实例
_streamlit_handler: Optional[StreamlitLogHandler] = None


def setup_streamlit_logger(log_container=None):
    """设置Streamlit日志处理器"""
    global _streamlit_handler
    
    # 移除旧的处理器
    if _streamlit_handler:
        logger = logging.getLogger()
        logger.removeHandler(_streamlit_handler)
    
    # 创建新的处理器
    _streamlit_handler = StreamlitLogHandler(log_container)
    _streamlit_handler.setLevel(logging.DEBUG)  # 改为 DEBUG 以捕获所有日志
    
    # 设置格式
    formatter = logging.Formatter(
        '%(message)s',
        datefmt='%H:%M:%S'
    )
    _streamlit_handler.setFormatter(formatter)
    
    # 添加到根logger和所有子logger
    root_logger = logging.getLogger()
    
    # 移除旧的处理器，避免重复
    for handler in root_logger.handlers[:]:
        if isinstance(handler, StreamlitLogHandler):
            root_logger.removeHandler(handler)
    
    root_logger.addHandler(_streamlit_handler)
    root_logger.setLevel(logging.DEBUG)  # 改为 DEBUG
    
    # 确保所有相关模块的logger也使用这个处理器
    module_loggers = [
        'ai_correction.functions.langgraph',
        'ai_correction.functions.langgraph.agents',
        'ai_correction.functions.langgraph.workflow_multimodal',
        'ai_correction.functions.llm_client',
    ]
    for module_name in module_loggers:
        module_logger = logging.getLogger(module_name)
        
        # 移除旧的处理器
        for handler in module_logger.handlers[:]:
            if isinstance(handler, StreamlitLogHandler):
                module_logger.removeHandler(handler)
        
        module_logger.addHandler(_streamlit_handler)
        module_logger.setLevel(logging.DEBUG)  # 改为 DEBUG
        module_logger.propagate = True  # 改为 True，让日志向上传播
    
    return _streamlit_handler


def get_streamlit_logs(level: Optional[str] = None, agent: Optional[str] = None) -> List[dict]:
    """获取日志列表"""
    if _streamlit_handler:
        return _streamlit_handler.get_logs(level, agent)
    return []


def clear_streamlit_logs():
    """清空日志"""
    if _streamlit_handler:
        _streamlit_handler.clear_logs()

