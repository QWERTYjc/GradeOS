#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extract Via Multimodal Agent - 多模态文本和坐标提取
调用多模态大模型提取文本与像素坐标，识别学生信息
符合设计文档: AI批改LangGraph Agent架构设计文档 - 第5.1节
"""

import logging
import json
import re
from typing import Dict, List, Any, Optional
from datetime import datetime

from ..state import GradingState, MMToken
from ...llm_client import get_llm_client

logger = logging.getLogger(__name__)


class ExtractViaMM:
    """
    多模态提取Agent
    
    职责:
    1. 调用多模态大模型进行文本识别
    2. 提取每个token的像素坐标
    3. 识别学生信息(姓名、学号、班级)
    4. 返回mm_tokens和student_info
    """
    
    def __init__(self):
        self.llm_client = get_llm_client()
        self.max_images_per_call = 10  # 单次最多处理10张图片
        
    async def __call__(self, state: GradingState) -> GradingState:
        """
        执行多模态提取
        
        Args:
            state: 包含images的状态对象
            
        Returns:
            更新后的状态对象(包含mm_tokens和student_info)
        """
        logger.info(f"开始多模态提取 - 任务ID: {state['task_id']}")
        
        try:
            # 更新进度
            state['current_step'] = '多模态文本和坐标提取'
            state['progress_percentage'] = 20.0
            
            images = state.get('images', [])
            if not images:
                raise ValueError("未找到图片文件")
            
            # 分批处理图片
            all_mm_tokens = []
            student_info = {}
            
            for i in range(0, len(images), self.max_images_per_call):
                batch_images = images[i:i + self.max_images_per_call]
                logger.info(f"处理图片批次 {i//self.max_images_per_call + 1}, "
                           f"包含 {len(batch_images)} 张图片")
                
                # 调用多模态模型
                batch_result = await self._extract_batch(batch_images, i)
                
                # 合并结果
                all_mm_tokens.extend(batch_result['tokens'])
                
                # 提取学生信息(仅第一批次)
                if i == 0 and batch_result.get('student_info'):
                    student_info = batch_result['student_info']
            
            # 更新状态
            state['mm_tokens'] = all_mm_tokens
            state['student_info'] = student_info
            
            # 向后兼容: 同时更新ocr_results
            state['ocr_results'] = self._convert_to_ocr_format(all_mm_tokens)
            
            # 更新进度
            state['progress_percentage'] = 35.0
            state['step_results']['extract_via_mm'] = {
                'total_tokens': len(all_mm_tokens),
                'student_found': bool(student_info),
                'student_name': student_info.get('name', 'Unknown'),
                'timestamp': str(datetime.now())
            }
            
            logger.info(f"多模态提取完成 - 任务ID: {state['task_id']}, "
                       f"提取tokens: {len(all_mm_tokens)}")
            
            return state
            
        except Exception as e:
            error_msg = f"多模态提取失败: {str(e)}"
            logger.error(error_msg)
            state['errors'].append({
                'step': 'extract_via_mm',
                'error': error_msg,
                'timestamp': str(datetime.now())
            })
            raise
    
    async def _extract_batch(
        self, 
        images: List[str], 
        start_index: int
    ) -> Dict[str, Any]:
        """
        提取一批图片的文本和坐标
        
        Args:
            images: 图片文件路径列表
            start_index: 起始索引(用于计算页码)
            
        Returns:
            包含tokens和student_info的字典
        """
        # 构建提示词
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(images, start_index)
        
        # 调用多模态模型
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            response = self.llm_client.chat(
                messages=messages,
                temperature=0.1,  # 低温度保证准确性
                max_tokens=4000
            )
            
            # 解析响应
            result = self._parse_mm_response(response, start_index)
            
            return result
            
        except Exception as e:
            logger.error(f"多模态模型调用失败: {e}")
            # 降级处理: 返回空结果
            return {
                'tokens': [],
                'student_info': {}
            }
    
    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        return """你是一个多模态信息提取助手，专门用于处理学生作业图片。

任务:
1. 提取图片中的所有文本、数学式子和手写内容
2. 为每个token返回:
   - 文字内容
   - 所在页码(从0开始)
   - 四个角的像素坐标(x1, y1, x2, y2)，以图片左上角为原点
   - 同一行的标识符 line_id
   - 置信度 (0-1)
3. 识别学生姓名、学号、班级信息

输出格式: 严格JSON格式
{
  "student_info": {
    "name": "张三",
    "student_id": "20230001",
    "class_id": "数学一班"
  },
  "tokens": [
    {
      "id": "t1",
      "text": "在△ABC中",
      "page": 0,
      "bbox": {"x1": 120, "y1": 45, "x2": 280, "y2": 75},
      "line_id": "L0",
      "conf": 0.98
    }
  ]
}

注意事项:
- 按从上到下、从左到右的顺序提取
- 数学公式保持原有格式
- 坐标必须是像素值(整数)
- 同一行的内容使用相同的line_id
- 如果找不到学生信息，student_info各字段填"Unknown"
"""
    
    def _build_user_prompt(
        self, 
        images: List[str], 
        start_index: int
    ) -> str:
        """构建用户提示词"""
        prompt = f"以下是学生提交的作业图片(共{len(images)}张)，请识别学生信息并提取所有文本token。\n\n"
        
        # 注意: 实际实现中需要将图片编码为base64或使用多模态API
        # 这里仅作示例
        for i, image_path in enumerate(images):
            page_num = start_index + i
            prompt += f"图片{page_num + 1}: {image_path}\n"
        
        prompt += "\n请按照JSON格式返回结果。"
        
        return prompt
    
    def _parse_mm_response(
        self, 
        response: str, 
        start_index: int
    ) -> Dict[str, Any]:
        """
        解析多模态模型响应
        
        Args:
            response: 模型返回的JSON字符串
            start_index: 起始页码索引
            
        Returns:
            包含tokens和student_info的字典
        """
        try:
            # 提取JSON部分(可能包含markdown代码块)
            json_str = self._extract_json(response)
            
            # 解析JSON
            data = json.loads(json_str)
            
            # 验证和规范化数据
            tokens = self._normalize_tokens(
                data.get('tokens', []), 
                start_index
            )
            
            student_info = self._normalize_student_info(
                data.get('student_info', {})
            )
            
            return {
                'tokens': tokens,
                'student_info': student_info
            }
            
        except Exception as e:
            logger.warning(f"解析多模态响应失败: {e}")
            return {
                'tokens': [],
                'student_info': {}
            }
    
    def _extract_json(self, text: str) -> str:
        """从文本中提取JSON"""
        # 移除markdown代码块标记
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        
        # 查找JSON对象
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            return match.group(0)
        
        return text.strip()
    
    def _normalize_tokens(
        self, 
        tokens: List[Dict], 
        start_index: int
    ) -> List[Dict[str, Any]]:
        """规范化token数据"""
        normalized = []
        
        for i, token in enumerate(tokens):
            try:
                # 生成唯一ID
                token_id = token.get('id', f"t{start_index * 1000 + i}")
                
                # 提取bbox
                bbox = token.get('bbox', {})
                if isinstance(bbox, dict):
                    bbox = {
                        'x1': float(bbox.get('x1', 0)),
                        'y1': float(bbox.get('y1', 0)),
                        'x2': float(bbox.get('x2', 0)),
                        'y2': float(bbox.get('y2', 0))
                    }
                else:
                    bbox = {'x1': 0, 'y1': 0, 'x2': 0, 'y2': 0}
                
                normalized_token = {
                    'id': token_id,
                    'text': str(token.get('text', '')),
                    'page': int(token.get('page', start_index)),
                    'bbox': bbox,
                    'conf': float(token.get('conf', 0.9)),
                    'line_id': str(token.get('line_id', f"L{i}"))
                }
                
                normalized.append(normalized_token)
                
            except Exception as e:
                logger.warning(f"规范化token失败: {e}")
                continue
        
        return normalized
    
    def _normalize_student_info(self, info: Dict) -> Dict[str, Any]:
        """规范化学生信息"""
        return {
            'name': info.get('name', 'Unknown'),
            'student_id': info.get('student_id', 'Unknown'),
            'class_id': info.get('class_id', 'Unknown'),
            'extracted_at': str(datetime.now())
        }
    
    def _convert_to_ocr_format(
        self, 
        mm_tokens: List[Dict]
    ) -> Dict[str, Any]:
        """
        将mm_tokens转换为OCR格式(向后兼容)
        
        Args:
            mm_tokens: 多模态token列表
            
        Returns:
            OCR格式的结果字典
        """
        # 按页码分组
        pages = {}
        for token in mm_tokens:
            page = token.get('page', 0)
            if page not in pages:
                pages[page] = []
            pages[page].append(token)
        
        # 生成OCR格式结果
        ocr_results = {}
        for page, tokens in pages.items():
            text = ' '.join([t.get('text', '') for t in tokens])
            ocr_results[f"page_{page}"] = {
                'success': True,
                'text': text,
                'words': tokens,
                'lines': self._group_by_line(tokens),
                'confidence': sum([t.get('conf', 0) for t in tokens]) / len(tokens) if tokens else 0
            }
        
        return ocr_results
    
    def _group_by_line(self, tokens: List[Dict]) -> List[Dict]:
        """按行分组tokens"""
        lines = {}
        for token in tokens:
            line_id = token.get('line_id', 'L0')
            if line_id not in lines:
                lines[line_id] = []
            lines[line_id].append(token)
        
        return [
            {
                'line_id': line_id,
                'text': ' '.join([t.get('text', '') for t in tokens]),
                'tokens': tokens
            }
            for line_id, tokens in lines.items()
        ]


# 便捷函数
def create_extract_via_mm_agent() -> ExtractViaMM:
    """创建ExtractViaMM实例"""
    return ExtractViaMM()
