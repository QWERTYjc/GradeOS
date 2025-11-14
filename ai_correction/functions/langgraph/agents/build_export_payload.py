#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build Export Payload Agent - 数据导出构建器
构建班级系统API数据包
符合设计文档: AI批改LangGraph Agent架构设计文档 - 第10节
"""

import logging
from typing import Dict, List, Any
from datetime import datetime
import json

from ..state import GradingState

logger = logging.getLogger(__name__)


class BuildExportPayloadAgent:
    """
    数据导出构建器
    
    职责:
    1. 整合批改结果
    2. 格式化为班级系统API规范
    3. 生成学生数据包
    4. 生成班级统计数据包
    5. 添加必要的元数据
    """
    
    def __init__(self, api_version: str = 'v1'):
        """
        初始化导出构建器
        
        参数:
            api_version: 班级系统API版本
        """
        self.api_version = api_version
    
    async def __call__(self, state: GradingState) -> GradingState:
        """
        构建导出数据包
        
        参数:
            state: 完整的批改状态
        
        返回:
            更新后的状态（包含export_payload）
        """
        logger.info(f"构建导出数据包 - 任务ID: {state.get('task_id')}")
        
        try:
            # 提取核心数据
            student_info = state.get('student_info', {})
            evaluations = state.get('evaluations', [])
            annotations = state.get('annotations', [])
            total_score = state.get('total_score', 0)
            grade_level = state.get('grade_level', 'F')
            student_evaluation = state.get('student_evaluation', {})
            
            # 构建学生数据包
            student_payload = self._build_student_payload(
                student_info, evaluations, annotations, total_score, grade_level, student_evaluation
            )
            
            # 构建题目评分详情
            question_details = self._build_question_details(evaluations)
            
            # 构建坐标标注数据
            annotation_data = self._build_annotation_data(annotations)
            
            # 构建完整数据包
            export_payload = {
                'api_version': self.api_version,
                'timestamp': str(datetime.now()),
                'task_id': state.get('task_id'),
                'mode': state.get('mode', 'professional'),
                'student': student_payload,
                'questions': question_details,
                'annotations': annotation_data,
                'metadata': {
                    'rubric_id': state.get('rubric_id'),
                    'assignment_id': state.get('assignment_id'),
                    'class_id': state.get('class_id'),
                    'teacher_id': state.get('teacher_id'),
                }
            }
            
            # 更新状态
            state['export_payload'] = export_payload
            state['current_step'] = '数据导出构建'
            state['progress_percentage'] = 95.0
            
            logger.info(f"导出数据包构建完成 - 学生: {student_info.get('name')}")
            return state
            
        except Exception as e:
            logger.error(f"数据包构建失败: {e}")
            state['errors'].append({'step': 'build_export', 'error': str(e), 'timestamp': str(datetime.now())})
            return state
    
    def _build_student_payload(self, student_info: Dict, evaluations: List[Dict],
                               annotations: List[Dict], total_score: float,
                               grade_level: str, student_evaluation: Dict) -> Dict[str, Any]:
        """构建学生数据包"""
        return {
            'student_id': student_info.get('student_id', ''),
            'student_name': student_info.get('name', ''),
            'total_score': total_score,
            'max_score': sum(e.get('max_score', 0) for e in evaluations),
            'percentage': (total_score / sum(e.get('max_score', 1) for e in evaluations) * 100) 
                         if evaluations else 0,
            'grade_level': grade_level,
            'evaluation': student_evaluation,
            'question_count': len(evaluations),
            'annotation_count': len(annotations),
            'submission_time': str(datetime.now())
        }
    
    def _build_question_details(self, evaluations: List[Dict]) -> List[Dict]:
        """构建题目评分详情"""
        question_details = []
        
        for eval_item in evaluations:
            detail = {
                'qid': eval_item.get('qid', ''),
                'score': eval_item.get('score', 0),
                'max_score': eval_item.get('max_score', 0),
                'label': eval_item.get('label', ''),
                'feedback': eval_item.get('detailed_feedback', {}),
                'error_token_ids': eval_item.get('error_token_ids', []),
                'rubric_analysis': eval_item.get('detailed_feedback', {}).get('rubric_analysis', [])
            }
            question_details.append(detail)
        
        return question_details
    
    def _build_annotation_data(self, annotations: List[Dict]) -> List[Dict]:
        """构建坐标标注数据"""
        annotation_data = []
        
        for anno in annotations:
            data = {
                'annotation_id': anno.get('annotation_id', ''),
                'qid': anno.get('qid', ''),
                'page': anno.get('page', 0),
                'bbox': anno.get('bbox', {}),
                'hint': anno.get('hint', ''),
                'error_type': anno.get('error_type', 'general'),
                'severity': anno.get('severity', 'medium')
            }
            annotation_data.append(data)
        
        return annotation_data
    
    def export_to_json(self, export_payload: Dict, file_path: str) -> bool:
        """导出数据包到JSON文件"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_payload, f, ensure_ascii=False, indent=2)
            logger.info(f"数据包已导出到: {file_path}")
            return True
        except Exception as e:
            logger.error(f"JSON导出失败: {e}")
            return False


def create_build_export_payload_agent(api_version: str = 'v1') -> BuildExportPayloadAgent:
    """创建BuildExportPayloadAgent实例"""
    return BuildExportPayloadAgent(api_version=api_version)
