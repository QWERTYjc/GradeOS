#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Parse Rubric Agent - 评分标准解析
将评分标准文本解析为结构化JSON
符合设计文档: AI批改LangGraph Agent架构设计文档 - 第6节
"""

import logging
import json
import re
from typing import Dict, List, Any
from datetime import datetime

from ..state import GradingState
from ...llm_client import get_llm_client

logger = logging.getLogger(__name__)


class ParseRubricAgent:
    """
    评分标准解析Agent
    
    职责:
    1. 将教师提供的评分标准文本解析成结构化JSON
    2. 定义每道题的题号、最大分值、评分项及条件
    3. 验证评分项总分等于最大分值
    4. 确保后续批改节点只能选择预定义的评分项
    """
    
    def __init__(self):
        self.llm_client = get_llm_client()
        
    async def __call__(self, state: GradingState) -> GradingState:
        """
        执行评分标准解析
        
        Args:
            state: 包含rubric_text的状态对象
            
        Returns:
            更新后的状态对象(包含rubric_struct)
        """
        logger.info(f"开始评分标准解析 - 任务ID: {state['task_id']}")
        
        try:
            # 更新进度
            state['current_step'] = '评分标准解析'
            state['progress_percentage'] = 40.0
            
            rubric_text = state.get('rubric_text', '')
            
            if not rubric_text:
                logger.warning("未提供评分标准，使用默认配置")
                state['rubric_struct'] = self._create_default_rubric()
            else:
                # 解析评分标准
                rubric_struct = await self._parse_rubric_text(rubric_text)
                
                # 验证评分标准
                self._validate_rubric(rubric_struct)
                
                state['rubric_struct'] = rubric_struct
            
            # 向后兼容
            state['rubric_data'] = state['rubric_struct']
            state['scoring_criteria'] = self._extract_scoring_criteria(
                state['rubric_struct']
            )
            
            # 更新进度
            state['progress_percentage'] = 45.0
            state['step_results']['parse_rubric'] = {
                'questions_count': len(state['rubric_struct'].get('questions', [])),
                'has_rubric': bool(rubric_text),
                'timestamp': str(datetime.now())
            }
            
            logger.info(f"评分标准解析完成 - 任务ID: {state['task_id']}, "
                       f"题目数: {len(state['rubric_struct'].get('questions', []))}")
            
            return state
            
        except Exception as e:
            error_msg = f"评分标准解析失败: {str(e)}"
            logger.error(error_msg)
            state['errors'].append({
                'step': 'parse_rubric',
                'error': error_msg,
                'timestamp': str(datetime.now())
            })
            # 使用默认评分标准继续
            state['rubric_struct'] = self._create_default_rubric()
            return state
    
    async def _parse_rubric_text(self, rubric_text: str) -> Dict[str, Any]:
        """
        解析评分标准文本
        
        Args:
            rubric_text: 评分标准文本
            
        Returns:
            结构化的评分标准
        """
        # 构建提示词
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(rubric_text)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            response = self.llm_client.chat(
                messages=messages,
                temperature=0.1,  # 低温度保证准确性
                max_tokens=3000
            )
            
            # 解析响应
            rubric_struct = self._parse_llm_response(response)
            
            return rubric_struct
            
        except Exception as e:
            logger.error(f"LLM解析评分标准失败: {e}")
            # 尝试规则解析
            return self._rule_based_parse(rubric_text)
    
    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        return """你是评分标准解析器，将文本评分标准转换为严格的JSON结构。

要求：
1. 每道题必须包含：qid（题号）、max_score（最大分值）、rubric_items（评分项列表）
2. 每个评分项包含：
   - id: 唯一标识（如Q1_R1）
   - description: 评分点描述
   - score_if_fulfilled: 满足时得分
   - conditions: 判断该项满足的条件（关键词、公式、逻辑步骤等）
3. 不得新增评分项，严格按照原文解析
4. 验证所有score_if_fulfilled之和等于max_score
5. 输出严格JSON格式

输出格式示例：
{
  "questions": [
    {
      "qid": "Q1",
      "max_score": 8,
      "rubric_items": [
        {
          "id": "Q1_R1",
          "description": "正确使用余弦定理",
          "score_if_fulfilled": 2,
          "conditions": ["余弦定理", "cosA = (b²+c²-a²)/(2bc)"]
        },
        {
          "id": "Q1_R2",
          "description": "正确推导±c²=b²-a²",
          "score_if_fulfilled": 1,
          "conditions": ["c²", "b²-a²"]
        }
      ]
    }
  ]
}"""
    
    def _build_user_prompt(self, rubric_text: str) -> str:
        """构建用户提示词"""
        return f"""以下是老师提供的批改标准：

{rubric_text}

请严格按照JSON格式解析为结构化评分标准。"""
    
    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """解析LLM响应"""
        try:
            # 提取JSON部分
            json_str = self._extract_json(response)
            
            # 解析JSON
            data = json.loads(json_str)
            
            # 验证基本结构
            if 'questions' not in data:
                raise ValueError("缺少questions字段")
            
            return data
            
        except Exception as e:
            logger.warning(f"解析LLM响应失败: {e}")
            raise
    
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
    
    def _rule_based_parse(self, rubric_text: str) -> Dict[str, Any]:
        """
        基于规则的评分标准解析(降级方案)
        
        Args:
            rubric_text: 评分标准文本
            
        Returns:
            结构化的评分标准
        """
        questions = []
        
        # 按行分割
        lines = rubric_text.strip().split('\n')
        
        current_question = None
        rubric_item_counter = 1
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 识别题目
            question_match = re.match(r'[题目]*\s*(\d+|[Q]\d+)[：:]\s*[（\(]?(\d+)\s*分[）\)]?', line, re.IGNORECASE)
            if question_match:
                if current_question:
                    questions.append(current_question)
                
                qid = f"Q{question_match.group(1)}" if not question_match.group(1).startswith('Q') else question_match.group(1)
                max_score = float(question_match.group(2))
                
                current_question = {
                    'qid': qid,
                    'max_score': max_score,
                    'rubric_items': []
                }
                rubric_item_counter = 1
                continue
            
            # 识别评分项
            if current_question:
                item_match = re.match(r'(\d+)[.、]\s*(.+?)[（\(]?(\d+(?:\.\d+)?)\s*分[）\)]?', line)
                if item_match:
                    description = item_match.group(2).strip()
                    score = float(item_match.group(3))
                    
                    # 提取条件关键词
                    conditions = self._extract_conditions(description)
                    
                    rubric_item = {
                        'id': f"{current_question['qid']}_R{rubric_item_counter}",
                        'description': description,
                        'score_if_fulfilled': score,
                        'conditions': conditions
                    }
                    
                    current_question['rubric_items'].append(rubric_item)
                    rubric_item_counter += 1
        
        # 添加最后一个题目
        if current_question:
            questions.append(current_question)
        
        # 如果没有解析到任何题目，创建默认
        if not questions:
            questions = self._create_default_rubric()['questions']
        
        return {'questions': questions}
    
    def _extract_conditions(self, description: str) -> List[str]:
        """从描述中提取关键条件"""
        conditions = []
        
        # 提取引号中的内容
        quoted = re.findall(r'[「『"\'](.*?)[」』"\']', description)
        conditions.extend(quoted)
        
        # 提取数学公式(简单识别)
        formulas = re.findall(r'[a-zA-Z]+\s*[=<>≤≥]\s*[^\s]+', description)
        conditions.extend(formulas)
        
        # 如果没有提取到，使用描述本身
        if not conditions:
            conditions = [description]
        
        return conditions
    
    def _validate_rubric(self, rubric_struct: Dict[str, Any]) -> None:
        """
        验证评分标准
        
        Args:
            rubric_struct: 结构化评分标准
            
        Raises:
            ValueError: 如果验证失败
        """
        questions = rubric_struct.get('questions', [])
        
        if not questions:
            raise ValueError("评分标准中没有题目")
        
        for question in questions:
            # 验证必需字段
            if 'qid' not in question:
                raise ValueError(f"题目缺少qid字段")
            if 'max_score' not in question:
                raise ValueError(f"题目{question['qid']}缺少max_score字段")
            if 'rubric_items' not in question:
                raise ValueError(f"题目{question['qid']}缺少rubric_items字段")
            
            # 验证评分项总分
            rubric_items = question['rubric_items']
            if rubric_items:
                total_score = sum([item.get('score_if_fulfilled', 0) for item in rubric_items])
                max_score = question['max_score']
                
                # 允许1分的误差(处理浮点数精度问题)
                if abs(total_score - max_score) > 1.0:
                    logger.warning(
                        f"题目{question['qid']}评分项总分({total_score})"
                        f"与最大分值({max_score})不一致"
                    )
    
    def _create_default_rubric(self) -> Dict[str, Any]:
        """创建默认评分标准"""
        return {
            'questions': [
                {
                    'qid': 'Q1',
                    'max_score': 10.0,
                    'rubric_items': [
                        {
                            'id': 'Q1_R1',
                            'description': '答案正确',
                            'score_if_fulfilled': 10.0,
                            'conditions': ['正确答案']
                        }
                    ]
                }
            ]
        }
    
    def _extract_scoring_criteria(
        self, 
        rubric_struct: Dict[str, Any]
    ) -> List[Dict]:
        """提取评分细则(向后兼容)"""
        criteria = []
        
        for question in rubric_struct.get('questions', []):
            for item in question.get('rubric_items', []):
                criteria.append({
                    'qid': question['qid'],
                    'item_id': item['id'],
                    'description': item['description'],
                    'score': item['score_if_fulfilled'],
                    'conditions': item['conditions']
                })
        
        return criteria


# 便捷函数
def create_parse_rubric_agent() -> ParseRubricAgent:
    """创建ParseRubricAgent实例"""
    return ParseRubricAgent()
