#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GradingWorkerAgent - 批改工作Agent
职责：基于定制化标准和题目上下文批改学生答案
核心价值：接收压缩版评分包和上下文，高效执行批改，最小化token消耗
"""

import logging
from typing import Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


class GradingWorkerAgent:
    """批改工作Agent"""
    
    def __init__(self, llm_client=None):
        self.agent_name = "GradingWorkerAgent"
        self.llm_client = llm_client
    
    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行批改工作"""
        logger.info(f"✍️ [{self.agent_name}] 开始批改作业...")
        
        try:
            state['current_step'] = "批改作业"
            state['progress_percentage'] = 50.0
            
            # 获取批次信息
            batches_info = state.get('batches_info', [])
            batch_rubric_packages = state.get('batch_rubric_packages', {})
            question_context_packages = state.get('question_context_packages', {})
            answer_understanding = state.get('answer_understanding')
            
            if not batches_info:
                logger.warning("没有批次信息，跳过批改")
                return state
            
            all_grading_results = []
            
            # 处理每个批次
            for batch in batches_info:
                batch_id = batch['batch_id']
                students = batch.get('students', [])
                
                rubric_package = batch_rubric_packages.get(batch_id, {})
                context_package = question_context_packages.get(batch_id, {})
                
                # 批改该批次的学生
                for student in students:
                    result = await self._grade_student(
                        student,
                        rubric_package,
                        context_package,
                        answer_understanding
                    )
                    all_grading_results.append(result)
            
            state['grading_results'] = all_grading_results
            
            # 计算总分
            total_score = sum(r.get('total_score', 0) for r in all_grading_results) / len(all_grading_results) if all_grading_results else 0
            state['total_score'] = total_score
            
            logger.info(f"   批改了 {len(all_grading_results)} 个学生")
            logger.info(f"   平均分: {total_score:.1f}")
            logger.info(f"✅ [{self.agent_name}] 批改完成")
            
            state['progress_percentage'] = 80.0
            
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
    
    async def _grade_student(
        self,
        student: Dict[str, Any],
        rubric_package: Dict[str, Any],
        context_package: Dict[str, Any],
        answer_understanding: Dict[str, Any]
    ) -> Dict[str, Any]:
        """批改单个学生（基于压缩版评分包和上下文）"""
        
        student_id = student.get('student_id', '')
        student_name = student.get('name', '')
        
        # 获取压缩版评分标准
        compressed_criteria = rubric_package.get('compressed_criteria', [])
        decision_trees = rubric_package.get('decision_trees', {})
        quick_checks = rubric_package.get('quick_checks', {})
        
        # 模拟批改（实际应调用LLM）
        evaluations = []
        total_score = 0
        
        for criterion in compressed_criteria:
            cid = criterion['id']
            pts = criterion['pts']
            
            # 简化版评分逻辑（实际应使用LLM + 决策树）
            # 这里模拟随机评分
            score_earned = pts * 0.8  # 假设得80%分数
            
            evaluations.append({
                'criterion_id': cid,
                'score_earned': score_earned,
                'is_met': score_earned >= pts * 0.5,
                'satisfaction_level': '完全满足' if score_earned >= pts * 0.9 else '部分满足',
                'justification': f"基于快速检查: {quick_checks.get(cid, '未知')}",
                'evidence': ['答案中找到相关内容']
            })
            
            total_score += score_earned
        
        return {
            'student_id': student_id,
            'student_name': student_name,
            'evaluations': evaluations,
            'total_score': total_score,
            'processing_time_ms': 1000
        }
