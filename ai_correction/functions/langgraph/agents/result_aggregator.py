#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ResultAggregator Agent - 聚合批改结果，生成统计数据
"""

from typing import Dict, Any, List
from collections import defaultdict


class ResultAggregatorAgent:
    """结果聚合 Agent"""
    
    def __init__(self):
        pass
    
    def aggregate(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        聚合批改结果
        
        Args:
            state: 包含 grading_results 的状态
            
        Returns:
            更新后的状态，添加 aggregated_results, statistics
        """
        try:
            grading_results = state.get('grading_results', [])
            student_info = state.get('student_info', {})
            
            # 计算总分
            total_score = sum(r['score'] for r in grading_results)
            max_total_score = sum(r['max_score'] for r in grading_results)
            
            # 计算百分比
            percentage = (total_score / max_total_score * 100) if max_total_score > 0 else 0
            
            # 确定等级
            grade = self._calculate_grade(percentage)
            
            # 分析错误类型
            error_analysis = self._analyze_errors(grading_results)
            
            # 知识点分析
            knowledge_analysis = self._analyze_knowledge_points(grading_results, state.get('questions', []))
            
            # 生成总结
            summary = self._generate_summary(grading_results, total_score, max_total_score, grade)
            
            # 聚合结果
            aggregated_results = {
                'student_info': student_info,
                'total_score': total_score,
                'max_score': max_total_score,
                'percentage': percentage,
                'grade': grade,
                'question_count': len(grading_results),
                'correct_count': sum(1 for r in grading_results if r['score'] >= r['max_score'] * 0.6),
                'error_analysis': error_analysis,
                'knowledge_analysis': knowledge_analysis,
                'summary': summary,
                'details': grading_results
            }
            
            # 生成统计数据
            statistics = self._generate_statistics(grading_results, state.get('questions', []))
            
            state.update({
                'aggregated_results': aggregated_results,
                'statistics': statistics,
                'aggregation_status': 'success'
            })
            
            return state
            
        except Exception as e:
            state.update({
                'aggregation_status': 'failed',
                'aggregation_errors': [str(e)]
            })
            return state
    
    def _calculate_grade(self, percentage: float) -> str:
        """计算等级"""
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
    
    def _analyze_errors(self, results: List[Dict]) -> Dict:
        """分析错误类型"""
        error_types = defaultdict(int)
        error_questions = []
        
        for result in results:
            score_rate = result['score'] / result['max_score'] if result['max_score'] > 0 else 0
            
            if score_rate < 0.6:  # 得分率低于60%视为错误
                error_questions.append({
                    'question_id': result['question_id'],
                    'score': result['score'],
                    'max_score': result['max_score'],
                    'feedback': result.get('feedback', '')
                })
                
                # 统计错误类型
                strategy = result.get('strategy', 'unknown')
                error_types[strategy] += 1
        
        return {
            'total_errors': len(error_questions),
            'error_rate': len(error_questions) / len(results) if results else 0,
            'error_types': dict(error_types),
            'error_questions': error_questions
        }
    
    def _analyze_knowledge_points(self, results: List[Dict], questions: List[Dict]) -> Dict:
        """分析知识点掌握情况"""
        knowledge_points = defaultdict(lambda: {'total': 0, 'correct': 0, 'score': 0, 'max_score': 0})
        
        for result in results:
            question = next((q for q in questions if q['id'] == result['question_id']), None)
            if not question:
                continue
            
            # 提取知识点（从关键词）
            keywords = question.get('analysis', {}).get('keywords', [])
            
            for keyword in keywords:
                knowledge_points[keyword]['total'] += 1
                knowledge_points[keyword]['score'] += result['score']
                knowledge_points[keyword]['max_score'] += result['max_score']
                
                if result['score'] >= result['max_score'] * 0.6:
                    knowledge_points[keyword]['correct'] += 1
        
        # 计算掌握率
        for kp in knowledge_points.values():
            kp['mastery_rate'] = kp['correct'] / kp['total'] if kp['total'] > 0 else 0
            kp['score_rate'] = kp['score'] / kp['max_score'] if kp['max_score'] > 0 else 0
        
        return dict(knowledge_points)
    
    def _generate_summary(self, results: List[Dict], total_score: int, max_score: int, grade: str) -> str:
        """生成总结"""
        correct_count = sum(1 for r in results if r['score'] >= r['max_score'] * 0.6)
        total_count = len(results)
        
        summary = f"""
## 📊 批改总结

### 基本信息
- 总分：{total_score}/{max_score} 分
- 得分率：{total_score/max_score*100:.1f}%
- 等级：{grade}
- 答对题数：{correct_count}/{total_count}

### 整体评价
"""
        
        if grade in ['A', 'B']:
            summary += "- ✅ 整体表现优秀，继续保持！\n"
        elif grade == 'C':
            summary += "- ⚠️ 整体表现良好，还有提升空间。\n"
        else:
            summary += "- ❌ 需要加强学习，多做练习。\n"
        
        return summary
    
    def _generate_statistics(self, results: List[Dict], questions: List[Dict]) -> Dict:
        """生成统计数据"""
        # 按题型统计
        type_stats = defaultdict(lambda: {'count': 0, 'total_score': 0, 'max_score': 0})
        
        for result in results:
            question = next((q for q in questions if q['id'] == result['question_id']), None)
            if not question:
                continue
            
            q_type = question.get('type', 'unknown')
            type_stats[q_type]['count'] += 1
            type_stats[q_type]['total_score'] += result['score']
            type_stats[q_type]['max_score'] += result['max_score']
        
        # 计算得分率
        for stats in type_stats.values():
            stats['score_rate'] = stats['total_score'] / stats['max_score'] if stats['max_score'] > 0 else 0
        
        # 按难度统计
        difficulty_stats = defaultdict(lambda: {'count': 0, 'total_score': 0, 'max_score': 0})
        
        for result in results:
            question = next((q for q in questions if q['id'] == result['question_id']), None)
            if not question:
                continue
            
            difficulty = question.get('analysis', {}).get('difficulty', 'medium')
            difficulty_stats[difficulty]['count'] += 1
            difficulty_stats[difficulty]['total_score'] += result['score']
            difficulty_stats[difficulty]['max_score'] += result['max_score']
        
        # 计算得分率
        for stats in difficulty_stats.values():
            stats['score_rate'] = stats['total_score'] / stats['max_score'] if stats['max_score'] > 0 else 0
        
        return {
            'by_type': dict(type_stats),
            'by_difficulty': dict(difficulty_stats),
            'total_questions': len(results),
            'average_score': sum(r['score'] for r in results) / len(results) if results else 0
        }


class RubricInterpreterAgent:
    """评分标准解释 Agent"""
    
    def __init__(self):
        pass
    
    def interpret(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        解释评分标准
        
        Args:
            state: 包含 marking_scheme 的状态
            
        Returns:
            更新后的状态，添加 interpreted_rubric
        """
        try:
            marking_scheme = state.get('marking_scheme', {})
            
            if not marking_scheme:
                state.update({
                    'interpreted_rubric': {},
                    'rubric_status': 'empty'
                })
                return state
            
            # 解析评分标准
            criteria = marking_scheme.get('criteria', [])
            
            # 生成结构化的评分标准
            interpreted = {
                'total_points': sum(c['points'] for c in criteria),
                'criteria_count': len(criteria),
                'criteria': criteria,
                'raw_text': marking_scheme.get('raw_text', '')
            }
            
            state.update({
                'interpreted_rubric': interpreted,
                'rubric_status': 'success'
            })
            
            return state
            
        except Exception as e:
            state.update({
                'rubric_status': 'failed',
                'rubric_errors': [str(e)]
            })
            return state

