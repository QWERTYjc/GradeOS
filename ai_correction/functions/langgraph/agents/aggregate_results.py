#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aggregate Results Agent - 结果聚合
收集所有worker结果，计算总分，生成坐标标注
符合设计文档: AI批改LangGraph Agent架构设计文档 - 第9节
"""

import logging
from typing import Dict, List, Any
from datetime import datetime

from ..state import GradingState

logger = logging.getLogger(__name__)


class AggregateResultsAgent:
    """
    结果聚合Agent
    
    职责:
    1. 收集所有worker的评分结果
    2. 计算总分和各部分分数
    3. 生成坐标标注数据
    4. 专业模式生成学生评价
    """
    
    async def __call__(self, state: GradingState) -> GradingState:
        """执行结果聚合"""
        logger.info(f"开始结果聚合 - 任务ID: {state['task_id']}")
        
        try:
            state['current_step'] = '结果聚合'
            state['progress_percentage'] = 80.0
            
            evaluations = state.get('evaluations', [])
            mode = state.get('mode', 'professional')
            
            # 按题号排序
            evaluations.sort(key=lambda x: x.get('qid', ''))
            
            # 计算总分
            total_score = sum(e.get('score', 0) for e in evaluations)
            max_score = sum(e.get('max_score', 0) for e in evaluations)
            
            state['total_score'] = total_score
            state['final_score'] = total_score
            state['grade_level'] = self._calculate_grade(total_score, max_score)
            
            # 生成坐标标注
            annotations = self._generate_annotations(evaluations, state.get('mm_tokens', []))
            state['annotations'] = annotations
            state['coordinate_annotations'] = annotations  # 兼容
            
            # 专业模式：生成评价
            if mode == 'professional':
                state['student_evaluation'] = self._generate_student_evaluation(evaluations, total_score, max_score)
            
            state['progress_percentage'] = 90.0
            state['completion_status'] = 'completed'
            
            logger.info(f"结果聚合完成 - 总分: {total_score}/{max_score}")
            return state
            
        except Exception as e:
            logger.error(f"结果聚合失败: {e}")
            state['errors'].append({'step': 'aggregate', 'error': str(e), 'timestamp': str(datetime.now())})
            return state
    
    def _calculate_grade(self, score: float, max_score: float) -> str:
        """计算等级"""
        if max_score == 0:
            return 'F'
        percentage = (score / max_score) * 100
        if percentage >= 90:
            return 'A'
        elif percentage >= 80:
            return 'B'
        elif percentage >= 70:
            return 'C'
        elif percentage >= 60:
            return 'D'
        return 'F'
    
    def _generate_annotations(self, evaluations: List[Dict], mm_tokens: List[Dict]) -> List[Dict]:
        """生成坐标标注"""
        annotations = []
        token_map = {t['id']: t for t in mm_tokens}
        
        for eval_item in evaluations:
            error_token_ids = eval_item.get('error_token_ids', [])
            
            for token_id in error_token_ids:
                if token_id in token_map:
                    token = token_map[token_id]
                    annotations.append({
                        'annotation_id': f"A_{len(annotations)}",
                        'qid': eval_item['qid'],
                        'page': token.get('page', 0),
                        'bbox': token.get('bbox', {}),
                        'hint': '错误',
                        'error_type': 'general'
                    })
        
        return annotations
    
    def _generate_student_evaluation(self, evaluations: List[Dict], total_score: float, max_score: float) -> Dict:
        """生成学生个人评价"""
        strengths = []
        weaknesses = []
        
        for e in evaluations:
            if e.get('label') == 'correct':
                strengths.append(f"题目{e['qid']}表现优秀")
            elif e.get('label') == 'wrong':
                weaknesses.append(f"题目{e['qid']}需要加强")
        
        return {
            'total_score': total_score,
            'max_score': max_score,
            'percentage': (total_score / max_score * 100) if max_score > 0 else 0,
            'strengths': strengths,
            'weaknesses': weaknesses,
            'suggestions': ['继续保持优秀表现', '加强薄弱知识点练习']
        }


def create_aggregate_results_agent() -> AggregateResultsAgent:
    """创建AggregateResultsAgent实例"""
    return AggregateResultsAgent()
