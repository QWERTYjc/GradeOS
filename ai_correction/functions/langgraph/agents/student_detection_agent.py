#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
StudentDetectionAgent - 学生信息识别Agent
职责：从答案文件中识别学生信息（姓名、学号、班级）
利用Vision直接读取答案文件，识别学生身份信息
"""

import logging
import os
from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class StudentDetectionAgent:
    """学生信息识别Agent"""
    
    def __init__(self):
        self.agent_name = "StudentDetectionAgent"
    
    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行学生信息识别"""
        logger.info(f"👤 [{self.agent_name}] 开始识别学生信息...")
        
        try:
            state['current_step'] = "学生信息识别"
            state['progress_percentage'] = 15.0
            
            answer_files = state.get('answer_files', [])
            students_info = []
            
            # 简化版：从文件名提取学生信息
            for idx, file_path in enumerate(answer_files):
                filename = Path(file_path).stem
                student_id = f"Student_{idx+1:03d}"
                name = filename.split('_')[0] if '_' in filename else f"学生{idx+1}"
                
                students_info.append({
                    'student_id': student_id,
                    'name': name,
                    'class_name': None,
                    'answer_files': [file_path],
                    'detection_confidence': 0.8,
                    'detection_method': 'filename'
                })
            
            state['students_info'] = students_info
            state['total_students'] = len(students_info)
            
            logger.info(f"   识别到 {len(students_info)} 个学生")
            
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
