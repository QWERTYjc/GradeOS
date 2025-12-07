#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QuestionUnderstandingAgent - 题目理解Agent
支持文本和Vision两种模态
"""

import logging
import json
import os
from typing import Dict, Any
from datetime import datetime

from ..state import GradingState
from ..multimodal_models import QuestionUnderstanding
from ..prompts.multimodal_prompts import format_question_understanding_prompt
from ...llm_client import get_llm_client, LLMClient

logger = logging.getLogger(__name__)


class QuestionUnderstandingAgent:
    """题目理解Agent - 支持多模态输入"""

    def __init__(self):
        self.name = "QuestionUnderstandingAgent"
        # 使用 Gemini 原生 API
        self.llm_client = LLMClient(
            provider='gemini',
            model='gemini-2.0-flash-exp'
        )
    
    async def __call__(self, state: GradingState) -> GradingState:
        """执行题目理解"""
        logger.info(f"{self.name} 开始处理...")
        
        try:
            state['current_step'] = "题目理解"
            state['progress_percentage'] = 25.0
            
            # 获取多模态题目文件
            question_files = state.get('question_multimodal_files', [])
            if not question_files:
                logger.warning("没有题目文件")
                return state
            
            # 处理第一个题目文件（简化处理）
            question_file = question_files[0]
            modality_type = question_file['modality_type']
            content = question_file['content_representation']
            
            logger.info(f"处理题目文件，模态类型: {modality_type}")
            
            # 根据模态类型选择处理方式
            # PDF现在直接使用Vision API处理，不提取文本
            if modality_type == 'text':
                understanding = await self._understand_text_question(content['text'])
            elif modality_type == 'image':
                understanding = await self._understand_image_question(content)
            elif modality_type == 'pdf':
                understanding = await self._understand_pdf_question(question_file.get('file_path') or content.get('file_path'))
            elif modality_type == 'pdf_text':
                # PDF文本格式（已废弃，现在PDF都使用Vision API）
                understanding = await self._understand_text_question(content['text'])
            elif modality_type == 'pdf_image':
                # PDF图片格式：使用Vision API处理第一页
                if content.get('pages'):
                    understanding = await self._understand_image_question(content['pages'][0])
                else:
                    understanding = self._default_understanding()
            else:
                understanding = self._default_understanding()
            
            # 只返回需要更新的字段，避免并发更新冲突
            # 注意：不返回progress_percentage和current_step，因为并行节点会冲突
            logger.info(f"{self.name} 处理完成")
            return {
                'question_understanding': understanding
            }
            
        except Exception as e:
            logger.error(f"{self.name} 失败: {e}")
            return {
                'errors': [{
                    'step': 'question_understanding',
                    'error': str(e),
                    'timestamp': str(datetime.now())
                }],
                'question_understanding': self._default_understanding()
            }
    
    async def _understand_text_question(self, question_text: str) -> QuestionUnderstanding:
        """理解文本题目"""
        prompt = format_question_understanding_prompt(question_text, is_vision=False)
        
        messages = [
            {"role": "system", "content": "你是一位资深教育专家，擅长理解和分析题目。"},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = self.llm_client.chat(messages, temperature=0.3, max_tokens=2000)
            return self._parse_understanding(response, question_text, "text")
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            return self._create_simple_understanding(question_text, "text")
    
    async def _understand_image_question(self, image_content: Dict[str, Any]) -> QuestionUnderstanding:
        """理解图片题目（使用 Gemini 原生多模态 API）"""
        # 获取文件路径
        file_path = image_content.get('file_path')
        if not file_path:
            logger.warning("图片题目缺少文件路径，使用默认理解")
            return self._default_understanding()
        
        logger.info(f"🖼️  使用 Gemini 解析图片题目: {file_path}")
        prompt = format_question_understanding_prompt("", is_vision=True)
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
            logger.error(f"❌ Gemini 解析图片题目失败: {e}")
            return self._default_understanding()
    
    async def _understand_pdf_question(self, pdf_path: str | None) -> QuestionUnderstanding:
        """使用 Gemini 原生多模态理解 PDF 题目"""
        if not pdf_path:
            logger.warning("PDF 题目缺少文件路径，使用默认理解")
            return self._default_understanding()
        
        logger.info(f"📄 使用 Gemini 解析 PDF 题目: {pdf_path}")
        prompt = format_question_understanding_prompt("", is_vision=True)
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
            logger.error(f"Gemini 解析 PDF 题目失败: {e}")
            return self._default_understanding()

    def _parse_understanding(self, response: str, question_text: str, modality: str) -> QuestionUnderstanding:
        """解析LLM响应"""
        try:
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                result = json.loads(response[json_start:json_end])
                return QuestionUnderstanding(
                    question_id=result.get('question_id', 'Q1'),
                    question_text=result.get('question_text', question_text),
                    key_requirements=result.get('key_requirements', []),
                    context=result.get('context', {}),
                    difficulty_level=result.get('context', {}).get('difficulty_level'),
                    subject=result.get('context', {}).get('subject'),
                    modality_source=modality
                )
        except:
            pass
        return self._create_simple_understanding(question_text, modality)
    
    def _create_simple_understanding(self, question_text: str, modality: str) -> QuestionUnderstanding:
        """创建简单的理解结果"""
        return QuestionUnderstanding(
            question_id='Q1',
            question_text=question_text,
            key_requirements=[],
            context={},
            modality_source=modality
        )
    
    def _get_llm_timeout(self) -> int:
        """获取LLM请求超时（秒）"""
        try:
            return int(os.getenv("QUESTION_LLM_TIMEOUT", os.getenv("LLM_REQUEST_TIMEOUT", "90")))
        except Exception:
            return 90
    
    def _default_understanding(self) -> QuestionUnderstanding:
        """默认理解结果"""
        return self._create_simple_understanding("", "unknown")
