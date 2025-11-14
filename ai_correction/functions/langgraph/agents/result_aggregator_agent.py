#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ResultAggregatorAgent - 结果聚合Agent
职责：汇总所有批次的批改结果，生成结构化报告
"""

import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class ResultAggregatorAgent:
    """结果聚合Agent"""
    
    def __init__(self):
        self.agent_name = "ResultAggregatorAgent"
    
    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行结果聚合"""
        logger.info(f"📊 [{self.agent_name}] 开始聚合结果...")
        
        try:
            state['current_step'] = "结果聚合"
            state['progress_percentage'] = 85.0
            
            grading_results = state.get('grading_results', [])
            
            if not grading_results:
                logger.warning("没有批改结果，跳过聚合")
                return state
            
            # 生成学生报告
            student_reports = []
            
            for result in grading_results:
                report = self._generate_student_report(result, state)
                student_reports.append(report)
            
            state['student_reports'] = student_reports
            
            # 计算统计信息
            total_students = len(student_reports)
            avg_score = sum(r['total_score'] for r in grading_results) / total_students if total_students > 0 else 0
            
            state['summary'] = {
                'total_students': total_students,
                'average_score': avg_score,
                'completed_at': str(datetime.now())
            }
            
            logger.info(f"   生成了 {total_students} 份学生报告")
            logger.info(f"   平均分: {avg_score:.1f}")
            logger.info(f"✅ [{self.agent_name}] 结果聚合完成")
            
            state['progress_percentage'] = 90.0
            
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
    
    def _generate_student_report(
        self,
        grading_result: Dict[str, Any],
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """为单个学生生成详细报告"""
        
        student_id = grading_result.get('student_id', '')
        student_name = grading_result.get('student_name', '')
        total_score = grading_result.get('total_score', 0)
        evaluations = grading_result.get('evaluations', [])
        
        # 计算等级
        grade_level = self._calculate_grade_level(total_score, state)
        
        # 生成反馈
        detailed_feedback = self._generate_feedback(evaluations)
        
        return {
            'student_id': student_id,
            'student_name': student_name,
            'total_score': total_score,
            'grade_level': grade_level,
            'evaluations': evaluations,
            'detailed_feedback': detailed_feedback,
            'strengths': self._extract_strengths(evaluations),
            'improvements': self._extract_improvements(evaluations)
        }
    
    def _calculate_grade_level(self, score: float, state: Dict[str, Any]) -> str:
        """计算等级"""
        total_points = state.get('batch_rubric_packages', {}).get('batch_001', {}).get('total_points', 100)
        percentage = (score / total_points * 100) if total_points > 0 else 0
        
        if percentage >= 90:
            return 'A'
        elif percentage >= 80:
            return 'B'
        elif percentage >= 70:
            return 'C'
        elif percentage >= 60:
            return 'D'
        else:
            return 'F'
    
    def _generate_feedback(self, evaluations: list) -> str:
        """生成反馈文本"""
        feedback_lines = []
        for eval in evaluations:
            feedback_lines.append(
                f"- {eval['criterion_id']}: {eval['satisfaction_level']} ({eval['score_earned']}分)"
            )
        return "\n".join(feedback_lines)
    
    def _extract_strengths(self, evaluations: list) -> list:
        """提取优点"""
        return [
            f"{e['criterion_id']}: {e['justification']}"
            for e in evaluations if e.get('is_met', False)
        ]
    
    def _extract_improvements(self, evaluations: list) -> list:
        """提取改进点"""
        return [
            f"{e['criterion_id']}: 需要改进"
            for e in evaluations if not e.get('is_met', False)
        ]
