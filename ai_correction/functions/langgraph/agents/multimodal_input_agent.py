#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MultiModalInputAgent - 多模态文件接收和识别
核心功能：
1. 接收文件路径列表
2. 识别文件模态（文本/图片/PDF等）
3. 不进行OCR转换
4. 保留原始模态信息
"""

import logging
from typing import List
from datetime import datetime

from ..state import GradingState
from ...file_processor import process_multimodal_file

logger = logging.getLogger(__name__)


class MultiModalInputAgent:
    """
    多模态输入处理Agent
    负责将上传的文件转换为多模态表示
    """
    
    def __init__(self):
        self.name = "MultiModalInputAgent"
    
    async def __call__(self, state: GradingState) -> GradingState:
        """
        处理多模态文件输入
        
        Args:
            state: 工作流状态
            
        Returns:
            更新后的状态（包含多模态文件信息）
        """
        logger.info(f"🔄 {self.name} 开始处理...")
        
        try:
            # 更新进度
            state['current_step'] = "多模态文件处理"
            state['progress_percentage'] = 10.0
            
            # 处理题目文件
            question_mm_files = []
            for file_path in state.get('question_files', []):
                try:
                    mm_file = process_multimodal_file(file_path, prefer_vision=False)
                    question_mm_files.append(mm_file)
                    logger.info(f"题目文件处理成功: {file_path}")
                except Exception as e:
                    logger.error(f"题目文件处理失败: {file_path}, 错误: {e}")
                    state['errors'].append({
                        'step': 'multimodal_input',
                        'file': file_path,
                        'error': str(e),
                        'timestamp': str(datetime.now())
                    })
            
            # 处理答案文件
            answer_mm_files = []
            for file_path in state.get('answer_files', []):
                try:
                    mm_file = process_multimodal_file(file_path, prefer_vision=False)
                    answer_mm_files.append(mm_file)
                    logger.info(f"答案文件处理成功: {file_path}")
                except Exception as e:
                    logger.error(f"答案文件处理失败: {file_path}, 错误: {e}")
                    state['errors'].append({
                        'step': 'multimodal_input',
                        'file': file_path,
                        'error': str(e),
                        'timestamp': str(datetime.now())
                    })
            
            # 处理评分标准文件
            marking_mm_files = []
            for file_path in state.get('marking_files', []):
                try:
                    mm_file = process_multimodal_file(file_path, prefer_vision=False)
                    marking_mm_files.append(mm_file)
                    logger.info(f"评分标准文件处理成功: {file_path}")
                except Exception as e:
                    logger.error(f"评分标准文件处理失败: {file_path}, 错误: {e}")
                    state['errors'].append({
                        'step': 'multimodal_input',
                        'file': file_path,
                        'error': str(e),
                        'timestamp': str(datetime.now())
                    })
            
            # 更新状态
            state['question_multimodal_files'] = question_mm_files
            state['answer_multimodal_files'] = answer_mm_files
            state['marking_multimodal_files'] = marking_mm_files
            
            # 更新进度
            state['progress_percentage'] = 15.0
            state['step_results']['multimodal_input'] = {
                'question_files_count': len(question_mm_files),
                'answer_files_count': len(answer_mm_files),
                'marking_files_count': len(marking_mm_files)
            }
            
            logger.info(f"{self.name} 处理完成")
            logger.info(f"   题目文件: {len(question_mm_files)}, 答案文件: {len(answer_mm_files)}, 评分标准: {len(marking_mm_files)}")
            
            return state
            
        except Exception as e:
            error_msg = f"{self.name} 处理失败: {str(e)}"
            logger.error(error_msg)
            state['errors'].append({
                'step': 'multimodal_input',
                'error': error_msg,
                'timestamp': str(datetime.now())
            })
            raise
