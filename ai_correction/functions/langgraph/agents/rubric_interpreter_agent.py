#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RubricInterpreterAgent - 评分标准解析Agent
解析评分标准，提取评分点和分值
"""

import logging
import json
from typing import List, Dict, Any
from datetime import datetime

from ..state import GradingState
from ..multimodal_models import RubricUnderstanding, GradingCriterion
from ..prompts.multimodal_prompts import format_rubric_interpretation_prompt
from ...llm_client import get_llm_client

logger = logging.getLogger(__name__)


class RubricInterpreterAgent:
    """评分标准解析Agent"""
    
    def __init__(self):
        self.name = "RubricInterpreterAgent"
        self.llm_client = get_llm_client()
    
    async def __call__(self, state: GradingState) -> GradingState:
        """执行评分标准解析"""
        logger.info(f"🔄 {self.name} 开始处理...")
        
        try:
            state['current_step'] = "评分标准解析"
            state['progress_percentage'] = 45.0
            
            # 获取评分标准文件
            marking_files = state.get('marking_multimodal_files', [])
            if not marking_files:
                logger.warning("没有评分标准文件，使用默认标准")
                state['rubric_understanding'] = self._default_rubric()
                return state
            
            # 处理第一个评分标准文件
            marking_file = marking_files[0]
            modality_type = marking_file['modality_type']
            content = marking_file['content_representation']
            
            logger.info(f"处理评分标准文件，模态类型: {modality_type}")
            
            # 提取文本内容
            if modality_type == 'text':
                rubric_text = content['text']
            elif modality_type == 'pdf_text':
                rubric_text = content['text']
            else:
                rubric_text = ""
            
            # 解析评分标准
            if rubric_text:
                understanding = await self._interpret_rubric(rubric_text)
            else:
                understanding = self._default_rubric()
            
            # 更新状态
            state['rubric_understanding'] = understanding
            state['progress_percentage'] = 50.0
            
            logger.info(f"✅ {self.name} 处理完成，共{len(understanding.get('criteria', []))}个评分点")
            return state
            
        except Exception as e:
            logger.error(f"{self.name} 失败: {e}")
            state['errors'].append({
                'step': 'rubric_interpretation',
                'error': str(e),
                'timestamp': str(datetime.now())
            })
            state['rubric_understanding'] = self._default_rubric()
            return state
    
    async def _interpret_rubric(self, rubric_text: str) -> RubricUnderstanding:
        """解析评分标准"""
        prompt = format_rubric_interpretation_prompt(rubric_text)
        
        messages = [
            {"role": "system", "content": "你是一位资深教育专家，擅长解析评分标准。"},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = self.llm_client.chat(messages, temperature=0.2, max_tokens=3000)
            return self._parse_rubric(response)
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            return self._parse_simple_rubric(rubric_text)
    
    def _parse_rubric(self, response: str) -> RubricUnderstanding:
        """解析LLM响应"""
        try:
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                result = json.loads(response[json_start:json_end])
                
                # 转换criteria为GradingCriterion类型
                criteria = []
                for c in result.get('criteria', []):
                    criteria.append(GradingCriterion(
                        criterion_id=c.get('criterion_id', ''),
                        description=c.get('description', ''),
                        points=float(c.get('points', 0)),
                        evaluation_method=c.get('evaluation_method', 'semantic'),
                        keywords=c.get('keywords'),
                        required_elements=c.get('required_elements')
                    ))
                
                return RubricUnderstanding(
                    rubric_id=result.get('rubric_id', 'R1'),
                    criteria=criteria,
                    total_points=float(result.get('total_points', 0)),
                    grading_rules=result.get('grading_rules', {}),
                    strictness_guidance=result.get('strictness_guidance')
                )
        except Exception as e:
            logger.warning(f"JSON解析失败: {e}")
        
        return self._default_rubric()
    
    def _parse_simple_rubric(self, rubric_text: str) -> RubricUnderstanding:
        """简单解析评分标准（文本分析）"""
        import re
        
        # 尝试提取评分点和分值
        criteria = []
        total_points = 0.0
        
        # 查找包含分值的行
        lines = rubric_text.split('\n')
        for i, line in enumerate(lines):
            # 匹配模式如 "1. xxx (5分)" 或 "评分点1：xxx 5分"
            patterns = [
                r'(\d+)[.、：:]\s*(.+?)\s*[（(]?(\d+(?:\.\d+)?)\s*分[）)]?',
                r'(.+?)\s*[（(]?(\d+(?:\.\d+)?)\s*分[）)]?'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, line)
                if match:
                    groups = match.groups()
                    if len(groups) >= 2:
                        description = groups[-2] if len(groups) > 2 else groups[0]
                        points = float(groups[-1])
                        
                        criteria.append(GradingCriterion(
                            criterion_id=f"C{i+1}",
                            description=description.strip(),
                            points=points,
                            evaluation_method='semantic',
                            keywords=None,
                            required_elements=None
                        ))
                        total_points += points
                        break
        
        if not criteria:
            # 如果没有找到评分点，创建默认评分点
            criteria = [
                GradingCriterion(
                    criterion_id="C1",
                    description="答案正确性",
                    points=100.0,
                    evaluation_method='semantic',
                    keywords=None,
                    required_elements=None
                )
            ]
            total_points = 100.0
        
        return RubricUnderstanding(
            rubric_id='R1',
            criteria=criteria,
            total_points=total_points,
            grading_rules={},
            strictness_guidance=None
        )
    
    def _default_rubric(self) -> RubricUnderstanding:
        """默认评分标准"""
        return RubricUnderstanding(
            rubric_id='R_DEFAULT',
            criteria=[
                GradingCriterion(
                    criterion_id="C1",
                    description="答案完整性和正确性",
                    points=100.0,
                    evaluation_method='semantic',
                    keywords=None,
                    required_elements=None
                )
            ],
            total_points=100.0,
            grading_rules={'partial_credit': 'yes'},
            strictness_guidance=None
        )
