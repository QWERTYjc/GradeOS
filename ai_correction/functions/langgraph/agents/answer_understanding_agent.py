#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AnswerUnderstandingAgent - 答案理解Agent
支持文本和Vision两种模态
"""

import logging
import json
import os
from typing import Dict, Any
from datetime import datetime

from ..state import GradingState
from ..multimodal_models import AnswerUnderstanding
from ..prompts.multimodal_prompts import format_answer_understanding_prompt
from ...llm_client import get_llm_client, LLMClient

logger = logging.getLogger(__name__)


class AnswerUnderstandingAgent:
    """答案理解Agent - 支持多模态输入"""

    def __init__(self):
        self.name = "AnswerUnderstandingAgent"
        # 使用 Gemini 原生 API
        self.llm_client = LLMClient(
            provider='gemini',
            model='gemini-2.0-flash-exp'
        )
    
    async def __call__(self, state: GradingState) -> GradingState:
        """执行答案理解"""
        logger.info(f"{self.name} 开始处理...")
        
        try:
            state['current_step'] = "答案理解"
            state['progress_percentage'] = 35.0
            
            # 获取多模态答案文件
            answer_files = state.get('answer_multimodal_files', [])
            if not answer_files:
                logger.warning("没有答案文件")
                return state
            
            # 处理第一个答案文件
            answer_file = answer_files[0]
            modality_type = answer_file['modality_type']
            content = answer_file['content_representation']
            
            logger.info(f"处理答案文件，模态类型: {modality_type}")
            
            # 根据模态类型选择处理方式
            # PDF现在直接使用Vision API处理，不提取文本
            if modality_type == 'text':
                understanding = await self._understand_text_answer(content['text'])
            elif modality_type == 'image':
                understanding = await self._understand_image_answer(content)
            elif modality_type == 'pdf':
                understanding = await self._understand_pdf_answer(answer_file.get('file_path') or content.get('file_path'))
            elif modality_type == 'pdf_text':
                # PDF文本格式（已废弃，现在PDF都使用Vision API）
                understanding = await self._understand_text_answer(content['text'])
            elif modality_type == 'pdf_image':
                # PDF图片格式：使用Vision API处理所有页面
                if content.get('pages'):
                    # 处理第一页（或所有页面）
                    understanding = await self._understand_image_answer(content['pages'][0])
                else:
                    # 如果没有页面，使用默认理解
                    understanding = self._default_understanding()
            else:
                understanding = self._default_understanding()
            
            # 只返回需要更新的字段，避免并发更新冲突
            # 注意：不返回progress_percentage和current_step，因为并行节点会冲突
            logger.info(f"{self.name} 处理完成")
            return {
                'answer_understanding': understanding
            }
            
        except Exception as e:
            logger.error(f"{self.name} 失败: {e}")
            return {
                'errors': [{
                    'step': 'answer_understanding',
                    'error': str(e),
                    'timestamp': str(datetime.now())
                }],
                'answer_understanding': self._default_understanding()
            }
    
    async def _understand_text_answer(self, answer_text: str) -> AnswerUnderstanding:
        """理解文本答案"""
        prompt = format_answer_understanding_prompt(answer_text, is_vision=False)
        
        messages = [
            {"role": "system", "content": "你是一位资深教育专家，擅长理解和分析学生答案。"},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = self.llm_client.chat(messages, temperature=0.3, max_tokens=2000)
            return self._parse_understanding(response, answer_text, "text")
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            return self._create_simple_understanding(answer_text, "text")
    
    async def _understand_image_answer(self, image_content: Dict[str, Any]) -> AnswerUnderstanding:
        """理解图片答案（使用 Gemini 原生多模态 API）"""
        # 获取文件路径
        file_path = image_content.get('file_path')
        if not file_path:
            logger.warning("图片答案缺少文件路径，使用默认理解")
            return self._default_understanding()
        
        logger.info(f"🖼️  使用 Gemini 解析图片答案: {file_path}")
        prompt = format_answer_understanding_prompt("", is_vision=True)
        messages = [{"role": "user", "content": prompt}]
        
        try:
            response = self.llm_client.chat(
                messages,
                temperature=0.3,
                max_tokens=2000,
                files=[file_path],  # 直接传文件路径
                thinking_level="medium",
                timeout=self._get_llm_timeout()
            )
            return self._parse_understanding(response, "", "vision_image")
        except Exception as e:
            logger.error(f"❌ Gemini 解析图片答案失败: {e}")
            return self._default_understanding()
    
    async def _understand_pdf_answer(self, pdf_path: str | None) -> AnswerUnderstanding:
        """使用 Gemini 原生多模态理解 PDF 答案"""
        if not pdf_path:
            logger.warning("PDF 答案缺少文件路径，使用默认理解")
            return self._default_understanding()
        
        logger.info(f"📄 使用 Gemini 解析 PDF 答案: {pdf_path}")
        prompt = format_answer_understanding_prompt("", is_vision=True)
        messages = [{"role": "user", "content": prompt}]
        
        try:
            response = self.llm_client.chat(
                messages,
                temperature=0.2,
                max_tokens=2000,
                files=[pdf_path],
                thinking_level="high",
                timeout=self._get_llm_timeout()
            )
            return self._parse_understanding(response, "", "vision_pdf")
        except Exception as e:
            logger.error(f"Gemini 解析 PDF 答案失败: {e}")
            return self._default_understanding()

    def _parse_understanding(self, response: str, answer_text: str, modality: str) -> AnswerUnderstanding:
        """解析LLM响应"""
        try:
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                result = json.loads(response[json_start:json_end])
                return AnswerUnderstanding(
                    answer_id=result.get('answer_id', 'A1'),
                    answer_text=result.get('answer_text', answer_text),
                    key_points=result.get('key_points', []),
                    structure=result.get('structure', {}),
                    completeness=result.get('completeness'),
                    modality_source=modality
                )
        except:
            pass
        return self._create_simple_understanding(answer_text, modality)
    
    def _get_llm_timeout(self) -> int:
        """获取LLM请求超时（秒）"""
        try:
            return int(os.getenv("ANSWER_LLM_TIMEOUT", os.getenv("LLM_REQUEST_TIMEOUT", "90")))
        except Exception:
            return 90
    
    def _create_simple_understanding(self, answer_text: str, modality: str) -> AnswerUnderstanding:
        """创建简单的理解结果"""
        return AnswerUnderstanding(
            answer_id='A1',
            answer_text=answer_text,
            key_points=[],
            structure={},
            modality_source=modality
        )
    
    def _default_understanding(self) -> AnswerUnderstanding:
        """默认理解结果"""
        return self._create_simple_understanding("", "unknown")
