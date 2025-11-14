#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BatchPlanningAgent - 批次规划Agent
职责：基于学生列表和题目信息规划批次
"""

import logging
import math
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class BatchPlanningAgent:
    """批次规划Agent（纯逻辑，无LLM调用）"""
    
    def __init__(self):
        self.agent_name = "BatchPlanningAgent"
    
    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行批次规划"""
        logger.info(f"📋 [{self.agent_name}] 开始批次规划...")
        
        try:
            state['current_step'] = "批次规划"
            state['progress_percentage'] = 20.0
            
            students_info = state.get('students_info', [])
            total_students = len(students_info)
            optimal_batch_size = state.get('optimal_batch_size', 10)
            
            if total_students == 0:
                state['batches_info'] = []
                return state
            
            # 计算批次数量
            num_batches = math.ceil(total_students / optimal_batch_size)
            
            batches_info = []
            for batch_idx in range(num_batches):
                start_idx = batch_idx * optimal_batch_size
                end_idx = min((batch_idx + 1) * optimal_batch_size, total_students)
                
                batch_students = students_info[start_idx:end_idx]
                
                batches_info.append({
                    'batch_id': f"batch_{batch_idx+1:03d}",
                    'students': batch_students,
                    'question_range': 'all',
                    'estimated_tokens': len(batch_students) * 1500,
                    'parallel_priority': batch_idx
                })
            
            state['batches_info'] = batches_info
            state['total_batches'] = num_batches
            
            logger.info(f"   规划了 {num_batches} 个批次")
            
            return state
            
        except Exception as e:
            logger.error(f"[{self.agent_name}] 执行失败: {e}")
            if 'errors' not in state:
                state['errors'] = []
            state['errors'].append({
                'agent': self.agent_name,
                'error': str(e),
                'timestamp': str(datetime.now())
            })
            return state
