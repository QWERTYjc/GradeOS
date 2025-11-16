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
        """执行批次规划 - 基于题目和评分点分批次，支持并行批改"""
        logger.info("=" * 60)
        logger.info(f"[{self.agent_name}] 开始批次规划...")
        logger.info("=" * 60)
        
        try:
            state['current_step'] = "批次规划"
            state['progress_percentage'] = 20.0
            
            students_info = state.get('students_info', [])
            rubric_understanding = state.get('rubric_understanding', {})
            
            # 获取所有评分点
            criteria = rubric_understanding.get('criteria', [])
            
            if not criteria:
                logger.warning("没有评分标准，创建默认批次")
                # 如果没有评分标准，按学生分批次（向后兼容）
                total_students = len(students_info)
                if total_students == 0:
                    state['batches_info'] = []
                    return state
                
                batches_info = [{
                    'batch_id': 'batch_001',
                    'students': students_info,
                    'question_range': 'all',
                    'estimated_tokens': total_students * 1500,
                    'parallel_priority': 0
                }]
                state['batches_info'] = batches_info
                state['total_batches'] = 1
                logger.info(f"   创建了1个默认批次（按学生）")
                return state
            
            # 按题目分组评分点
            questions_dict = {}
            for criterion in criteria:
                question_id = criterion.get('question_id', '')
                if not question_id:
                    # 如果没有question_id，尝试从criterion_id提取
                    criterion_id = criterion.get('criterion_id', '')
                    if '_' in criterion_id:
                        question_id = criterion_id.split('_')[0]
                    else:
                        question_id = 'UNKNOWN'
                
                if question_id not in questions_dict:
                    questions_dict[question_id] = []
                questions_dict[question_id].append(criterion)
            
            # 按题目编号排序
            sorted_questions = sorted(questions_dict.items(), key=lambda x: self._extract_question_number(x[0]))
            
            logger.info(f"   识别到 {len(sorted_questions)} 道题: {[q[0] for q in sorted_questions]}")
            
            # 如果题目数量较少（<=5），不分批，所有题目一起处理
            # 如果题目数量较多，按题目分批次（每批约5-7道题）
            if len(sorted_questions) <= 5:
                # 单批次：所有题目一起处理
                batches_info = [{
                    'batch_id': 'batch_001',
                    'students': students_info,
                    'question_ids': [q[0] for q in sorted_questions],
                    'question_range': 'all',
                    'estimated_tokens': len(criteria) * 500,
                    'parallel_priority': 0
                }]
                logger.info(f"   题目数量较少（{len(sorted_questions)}道），创建1个批次处理所有题目")
            else:
                # 多批次：按题目分批次
                questions_per_batch = max(5, math.ceil(len(sorted_questions) / 3))  # 每批约5-7道题，最多3个批次
                batches_info = []
                
                for batch_idx in range(0, len(sorted_questions), questions_per_batch):
                    batch_questions = sorted_questions[batch_idx:batch_idx + questions_per_batch]
                    question_ids = [q[0] for q in batch_questions]
                    batch_criteria_count = sum(len(q[1]) for q in batch_questions)
                    
                    batches_info.append({
                        'batch_id': f"batch_{batch_idx // questions_per_batch + 1:03d}",
                        'students': students_info,  # 所有批次处理相同的学生
                        'question_ids': question_ids,
                        'question_range': f"{question_ids[0]}-{question_ids[-1]}",
                        'estimated_tokens': batch_criteria_count * 500,
                        'parallel_priority': batch_idx // questions_per_batch
                    })
                    
                    logger.info(f"   批次{batch_idx // questions_per_batch + 1}: 题目 {question_ids[0]}-{question_ids[-1]} ({len(question_ids)}道题, {batch_criteria_count}个评分点)")
            
            state['batches_info'] = batches_info
            state['total_batches'] = len(batches_info)
            
            logger.info("=" * 60)
            logger.info(f"[批次规划完成]")
            logger.info(f"   规划了 {len(batches_info)} 个批次，支持并行批改")
            logger.info("=" * 60)
            
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
    
    def _extract_question_number(self, question_id: str) -> int:
        """从题目ID中提取数字（用于排序）"""
        import re
        # 提取Q后面的数字，如Q17 -> 17, Q1 -> 1
        match = re.search(r'Q?(\d+)', question_id)
        if match:
            return int(match.group(1))
        # 如果没有数字，返回0（排在最后）
        return 0
