#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ClassAnalysisAgent - 班级分析Agent
职责：生成班级整体分析报告（仅班级批改模式启用）
"""

import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class ClassAnalysisAgent:
    """班级分析Agent"""
    
    def __init__(self):
        self.agent_name = "ClassAnalysisAgent"
    
    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行班级分析"""
        logger.info(f"🏫 [{self.agent_name}] 开始班级分析...")
        
        try:
            # 检查是否启用班级分析
            if not state.get('enable_class_analysis', False):
                logger.info("   班级分析未启用，跳过")
                return state
            
            state['current_step'] = "班级分析"
            state['progress_percentage'] = 95.0
            
            grading_results = state.get('grading_results', [])
            
            if len(grading_results) < 2:
                logger.info("   学生数量不足，跳过班级分析")
                return state
            
            # 统计分析
            scores = [r.get('total_score', 0) for r in grading_results]
            avg_score = sum(scores) / len(scores) if scores else 0
            max_score = max(scores) if scores else 0
            min_score = min(scores) if scores else 0
            
            class_analysis = {
                'total_students': len(grading_results),
                'average_score': avg_score,
                'max_score': max_score,
                'min_score': min_score,
                'score_distribution': self._calculate_distribution(scores),
                'common_issues': self._identify_common_issues(grading_results),
                'generated_at': str(datetime.now())
            }
            
            state['class_analysis'] = class_analysis
            
            logger.info(f"   班级人数: {class_analysis['total_students']}")
            logger.info(f"   平均分: {avg_score:.1f}")
            logger.info(f"✅ [{self.agent_name}] 班级分析完成")
            
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
    
    def _calculate_distribution(self, scores: list) -> dict:
        """计算分数分布"""
        distribution = {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0}
        
        for score in scores:
            if score >= 90:
                distribution['A'] += 1
            elif score >= 80:
                distribution['B'] += 1
            elif score >= 70:
                distribution['C'] += 1
            elif score >= 60:
                distribution['D'] += 1
            else:
                distribution['F'] += 1
        
        return distribution
    
    def _identify_common_issues(self, grading_results: list) -> list:
        """识别共性问题"""
        # 简化版：统计失分最多的评分点
        criterion_failures = {}
        
        for result in grading_results:
            for eval in result.get('evaluations', []):
                if not eval.get('is_met', False):
                    cid = eval.get('criterion_id', '')
                    criterion_failures[cid] = criterion_failures.get(cid, 0) + 1
        
        # 排序并返回前3个
        sorted_issues = sorted(
            criterion_failures.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return [
            {
                'criterion_id': cid,
                'failure_count': count,
                'failure_rate': count / len(grading_results) * 100
            }
            for cid, count in sorted_issues[:3]
        ]
