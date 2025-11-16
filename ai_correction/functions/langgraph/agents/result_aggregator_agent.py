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
        logger.info("=" * 60)
        logger.info(f"[{self.agent_name}] 开始聚合结果...")
        logger.info("=" * 60)
        
        try:
            state['current_step'] = "结果聚合"
            state['progress_percentage'] = 85.0
            
            grading_results = state.get('grading_results', [])
            logger.info(f"   收到 {len(grading_results)} 个批次的结果")
            
            if not grading_results:
                logger.warning("没有批改结果，跳过聚合")
                logger.warning(f"调试信息: students_info={len(state.get('students_info', []))}, batches_info={len(state.get('batches_info', []))}")
                logger.warning(f"调试信息: rubric_understanding存在={state.get('rubric_understanding') is not None}")
                # 即使没有批改结果，也创建一个空的学生报告，避免后续处理失败
                state['student_reports'] = []
                return state
            
            # 合并多个批次的评估结果（如果同一个学生有多个批次的结果）
            merged_results = {}
            logger.info(f"开始合并 {len(grading_results)} 个批次的结果...")
            for i, result in enumerate(grading_results):
                student_id = result.get('student_id', '')
                evaluations = result.get('evaluations', [])
                question_ids = result.get('question_ids', []) or []
                
                logger.info(f"  批次结果 {i+1}: 学生 {student_id}, {len(evaluations)} 个评估, 题目: {question_ids}")
                
                if student_id not in merged_results:
                    merged_results[student_id] = {
                        'student_id': student_id,
                        'student_name': result.get('student_name', ''),
                        'evaluations': [],
                        'total_score': 0,
                        'question_ids': []
                    }
                
                # 合并评估结果
                merged_results[student_id]['evaluations'].extend(evaluations)
                merged_results[student_id]['question_ids'].extend(question_ids)
            
            # 去重question_ids并重新计算总分（避免多种解法重复计算）
            for student_id, merged_result in merged_results.items():
                merged_result['question_ids'] = list(set(merged_result['question_ids']))

                # 重新计算总分 - 避免多种解法的分值重复计算
                # 对于同一题目的多种解法（如 Q8a_C1_Case1, Q8a_C2_Case2），只计算学生实际使用的方法的分数
                total_score = 0
                for eval_item in merged_result['evaluations']:
                    # 只累加满足条件的评分点（is_met=True）
                    # 未满足的评分点（is_met=False）不计入总分
                    if eval_item.get('is_met', False):
                        total_score += eval_item.get('score_earned', 0)

                merged_result['total_score'] = total_score
                logger.info(f"  学生 {student_id}: {len(merged_result['evaluations'])} 个评估, {len(merged_result['question_ids'])} 道题, 总分: {merged_result['total_score']}")
            
            # 生成学生报告
            student_reports = []
            for student_id, merged_result in merged_results.items():
                report = self._generate_student_report(merged_result, state)
                student_reports.append(report)
            
            logger.info("=" * 60)
            logger.info(f"[结果聚合完成]")
            logger.info(f"   合并了 {len(grading_results)} 个批次结果")
            logger.info(f"   生成了 {len(student_reports)} 份学生报告")
            
            # 统计总评估数量
            total_evaluations = sum(len(r.get('evaluations', [])) for r in student_reports)
            logger.info(f"   总评估结果数量: {total_evaluations}")
            
            # 统计题目覆盖
            all_questions = set()
            for report in student_reports:
                for eval_item in report.get('evaluations', []):
                    criterion_id = eval_item.get('criterion_id', '')
                    if '_' in criterion_id:
                        qid = criterion_id.split('_')[0]
                        all_questions.add(qid)
            logger.info(f"   覆盖题目数量: {len(all_questions)} 道题")
            logger.info(f"   题目列表: {sorted(all_questions)}")
            logger.info("=" * 60)
            
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
            logger.info(f"[{self.agent_name}] 结果聚合完成")
            
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
