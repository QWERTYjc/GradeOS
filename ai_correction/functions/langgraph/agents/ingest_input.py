#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ingest Input Agent - 输入数据摄取和验证
负责读取图片、作业编号、评分标准文本与批改模式
符合设计文档: AI批改LangGraph Agent架构设计文档 - 第6节
"""

import logging
import os
from typing import Dict, List, Any
from pathlib import Path
from datetime import datetime

from ..state import GradingState

logger = logging.getLogger(__name__)


class IngestInputAgent:
    """
    输入摄取Agent
    
    职责:
    1. 读取并验证所有输入文件
    2. 加载评分标准文本
    3. 解析批改模式和配置参数
    4. 初始化状态对象
    """
    
    def __init__(self):
        self.supported_image_formats = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp']
        self.supported_text_formats = ['.txt', '.md', '.json']
        
    async def __call__(self, state: GradingState) -> GradingState:
        """
        执行输入摄取
        
        Args:
            state: 包含初始参数的状态对象
            
        Returns:
            更新后的状态对象
        """
        logger.info(f"开始输入摄取 - 任务ID: {state['task_id']}")
        
        try:
            state.setdefault('errors', [])
            # 更新进度
            state['current_step'] = '输入验证与摄取'
            state['progress_percentage'] = 5.0
            
            # 1. 验证必需参数
            self._validate_required_params(state)
            
            # 2. 处理图片文件
            images = self._process_image_files(state)
            state['images'] = images
            
            # 3. 加载评分标准文本
            rubric_text = self._load_rubric_text(state)
            state['rubric_text'] = rubric_text
            
            # 4. 验证和设置批改模式
            mode = self._validate_mode(state.get('mode', 'professional'))
            state['mode'] = mode
            
            # 5. 初始化空的数据结构
            state = self._initialize_empty_structures(state)
            
            # 更新进度
            state['progress_percentage'] = 10.0
            state['step_results']['ingest_input'] = {
                'images_count': len(images),
                'has_rubric': bool(rubric_text),
                'mode': mode,
                'timestamp': str(datetime.now())
            }
            
            logger.info(f"输入摄取完成 - 任务ID: {state['task_id']}, "
                       f"图片数: {len(images)}, 模式: {mode}")
            
            return state
            
        except Exception as e:
            error_msg = f"输入摄取失败: {str(e)}"
            logger.error(error_msg)
            state['errors'].append({
                'step': 'ingest_input',
                'error': error_msg,
                'timestamp': str(datetime.now())
            })
            raise
    
    def _validate_required_params(self, state: GradingState) -> None:
        """验证必填项并为缺失字段提供兼容逻辑"""
        if not state.get('task_id'):
            raise ValueError("缺少必需参数: task_id")

        if not state.get('user_id'):
            fallback_user_id = (
                state.get('student_info', {}).get('student_id')
                or 'anonymous_user'
            )
            state['user_id'] = fallback_user_id
            logger.info("未提供 user_id，使用默认 user_id=anonymous_user 保持兼容")

        answer_files = state.get('answer_files') or []
        if not answer_files:
            raise ValueError("必须提供至少一个学生答案文件")

    def _process_image_files(self, state: GradingState) -> List[str]:
        """处理图片文件"""
        images = []

        # 收集所有图片文件
        all_files = []
        all_files.extend(state.get('answer_files', []))
        all_files.extend(state.get('question_files', []))

        for file_path in all_files:
            if not os.path.exists(file_path):
                logger.warning(f"文件不存在: {file_path}")
                continue

            # 检查是否为图片文件
            if self._is_image_file(file_path):
                # 验证文件可读
                if self._validate_image_file(file_path):
                    images.append(file_path)
                else:
                    logger.warning(f"图片文件验证失败: {file_path}")
            else:
                logger.info(f"跳过非图片文件: {file_path}")

        if not images:
            logger.info('未找到图片文件，直接以文本模式处理')
            return []

        # 按文件名排序，保证顺序一致
        images.sort()

        return images

    def _is_image_file(self, file_path: str) -> bool:
        """检查是否为图片文件"""
        suffix = Path(file_path).suffix.lower()
        return suffix in self.supported_image_formats
    
    def _validate_image_file(self, file_path: str) -> bool:
        """验证图片文件有效性"""
        try:
            # 检查文件大小
            file_size = os.path.getsize(file_path)
            
            # 文件不能为空
            if file_size == 0:
                logger.warning(f"图片文件为空: {file_path}")
                return False
            
            # 文件不能太大 (限制100MB)
            max_size = 100 * 1024 * 1024
            if file_size > max_size:
                logger.warning(f"图片文件过大: {file_path}, 大小: {file_size}")
                return False
            
            # 尝试打开图片验证格式
            from PIL import Image
            with Image.open(file_path) as img:
                img.verify()
            
            return True
            
        except Exception as e:
            logger.warning(f"图片文件验证失败: {file_path}, 错误: {e}")
            return False
    
    def _load_rubric_text(self, state: GradingState) -> str:
        """加载评分标准文本"""
        marking_files = state.get('marking_files', [])
        
        if not marking_files:
            logger.info("未提供评分标准文件")
            return ""
        
        rubric_text_parts = []
        
        for file_path in marking_files:
            if not os.path.exists(file_path):
                logger.warning(f"评分标准文件不存在: {file_path}")
                continue
            
            try:
                # 检查文件格式
                if self._is_text_file(file_path):
                    # 读取文本文件
                    with open(file_path, 'r', encoding='utf-8') as f:
                        text = f.read()
                        rubric_text_parts.append(text)
                elif self._is_image_file(file_path):
                    # 图片格式的评分标准，标记需要OCR处理
                    rubric_text_parts.append(f"[IMAGE_RUBRIC:{file_path}]")
                else:
                    logger.warning(f"不支持的评分标准文件格式: {file_path}")
                    
            except Exception as e:
                logger.warning(f"读取评分标准文件失败: {file_path}, 错误: {e}")
        
        return "\n\n---\n\n".join(rubric_text_parts)
    
    def _is_text_file(self, file_path: str) -> bool:
        """检查是否为文本文件"""
        suffix = Path(file_path).suffix.lower()
        return suffix in self.supported_text_formats
    
    def _validate_mode(self, mode: str) -> str:
        """验证并规范化批改模式"""
        valid_modes = ['efficient', 'professional']
        
        # 兼容旧的模式名称
        mode_mapping = {
            'detailed': 'professional',
            'auto': 'professional',
            'batch': 'efficient',
            'generate_scheme': 'professional'
        }
        
        # 转换为小写
        mode = mode.lower()
        
        # 映射旧模式名称
        if mode in mode_mapping:
            mode = mode_mapping[mode]
        
        # 验证模式有效性
        if mode not in valid_modes:
            logger.warning(f"无效的批改模式: {mode}, 使用默认模式: professional")
            mode = 'professional'
        
        return mode
    
    def _initialize_empty_structures(self, state: GradingState) -> GradingState:
        """初始化空的数据结构"""
        # 多模态提取结果
        if 'mm_tokens' not in state:
            state['mm_tokens'] = []
        if 'student_info' not in state:
            state['student_info'] = {}
        
        # 题目和批次
        if 'questions' not in state:
            state['questions'] = []
        if 'batches' not in state:
            state['batches'] = []
        
        # 评分结果
        if 'evaluations' not in state:
            state['evaluations'] = []
        if 'annotations' not in state:
            state['annotations'] = []
        
        # 评分标准
        if 'rubric_struct' not in state:
            state['rubric_struct'] = {}
        
        # 专业模式扩展
        if 'student_evaluation' not in state:
            state['student_evaluation'] = {}
        if 'class_evaluation' not in state:
            state['class_evaluation'] = {}
        if 'export_payload' not in state:
            state['export_payload'] = {}
        
        # 分数
        if 'total_score' not in state:
            state['total_score'] = 0.0
        if 'section_scores' not in state:
            state['section_scores'] = {}
        
        # 兼容性字段初始化
        if 'ocr_results' not in state:
            state['ocr_results'] = {}
        if 'image_regions' not in state:
            state['image_regions'] = {}
        if 'preprocessed_images' not in state:
            state['preprocessed_images'] = {}
        if 'coordinate_annotations' not in state:
            state['coordinate_annotations'] = []
        if 'knowledge_points' not in state:
            state['knowledge_points'] = []
        if 'error_analysis' not in state:
            state['error_analysis'] = {}
        if 'learning_suggestions' not in state:
            state['learning_suggestions'] = []
        
        # 状态追踪
        if 'step_results' not in state:
            state['step_results'] = {}
        if 'errors' not in state:
            state['errors'] = []
        if 'warnings' not in state:
            state['warnings'] = []
        
        return state


# 便捷函数
def create_ingest_input_agent() -> IngestInputAgent:
    """创建IngestInputAgent实例"""
    return IngestInputAgent()
