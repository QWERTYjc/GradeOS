#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OrchestratorAgent - 编排协调Agent
职责：全局任务分解、Agent协调、资源优化
核心能力：
- 分析任务类型（单人/班级批改）
- 协调Agent执行顺序
- 优化Token使用策略
- 监控全局进度
"""

import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class OrchestratorAgent:
    """
    编排协调Agent
    主要负责逻辑编排，轻量级LLM调用或无LLM调用
    """
    
    def __init__(self):
        self.agent_name = "OrchestratorAgent"
    
    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行编排协调
        
        Args:
            state: 当前状态
            
        Returns:
            更新后的状态
        """
        logger.info(f"[{self.agent_name}] 开始任务编排...")
        
        try:
            state['current_step'] = "任务编排"
            state['progress_percentage'] = 5.0
            
            # 分析任务类型
            task_type = self._analyze_task_type(state)
            state['task_type'] = task_type
            
            logger.info(f"   任务类型: {task_type}")
            
            # 决定是否启用学生识别
            enable_student_detection = task_type in ['batch', 'class']
            state['enable_student_detection'] = enable_student_detection
            
            # 决定是否启用班级分析
            enable_class_analysis = task_type == 'class'
            state['enable_class_analysis'] = enable_class_analysis
            
            # 估算批次大小
            optimal_batch_size = self._calculate_optimal_batch_size(state)
            state['optimal_batch_size'] = optimal_batch_size
            
            logger.info(f"   学生识别: {'启用' if enable_student_detection else '跳过'}")
            logger.info(f"   班级分析: {'启用' if enable_class_analysis else '跳过'}")
            logger.info(f"   最优批次大小: {optimal_batch_size}")
            
            state['progress_percentage'] = 10.0
            
            logger.info(f"[{self.agent_name}] 任务编排完成")
            
            return state
            
        except Exception as e:
            error_msg = f"[{self.agent_name}] 执行失败: {str(e)}"
            logger.error(error_msg)
            
            if 'errors' not in state:
                state['errors'] = []
            state['errors'].append({
                'agent': self.agent_name,
                'error': error_msg,
                'timestamp': str(datetime.now())
            })
            
            return state
    
    def _analyze_task_type(self, state: Dict[str, Any]) -> str:
        """
        分析任务类型
        
        Returns:
            'single': 单个学生
            'batch': 批量学生
            'class': 班级作业
        """
        answer_files = state.get('answer_files', [])
        
        if len(answer_files) == 0:
            return 'single'
        elif len(answer_files) == 1:
            return 'single'
        elif len(answer_files) <= 5:
            return 'batch'
        else:
            return 'class'
    
    def _calculate_optimal_batch_size(self, state: Dict[str, Any]) -> int:
        """
        计算最优批次大小
        
        考虑因素：
        - 学生数量
        - LLM context限制
        - 并行处理能力
        """
        answer_files = state.get('answer_files', [])
        total_students = len(answer_files)
        
        # 默认配置
        max_batch_size = 10  # 最大批次大小
        max_parallel_batches = 3  # 最大并行批次数
        
        if total_students <= max_batch_size:
            # 学生数少，一个批次处理
            return total_students
        else:
            # 计算批次大小，确保能均匀分配
            optimal_size = max(1, total_students // max_parallel_batches)
            return min(optimal_size, max_batch_size)
