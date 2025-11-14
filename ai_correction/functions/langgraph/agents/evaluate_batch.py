#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Evaluate Batch Agent - 批次评分Worker
实现批次评分worker，支持高效模式和专业模式
符合设计文档: AI批改LangGraph Agent架构设计文档 - 第8节
"""

import logging
import json
from typing import Dict, List, Any
from datetime import datetime

from ..state import GradingState, Evaluation
from ...llm_client import get_llm_client

logger = logging.getLogger(__name__)


class EvaluateBatchAgent:
    """
    批次评分Worker
    
    职责:
    1. 对指定批次内的题目进行批改
    2. 根据模式(efficient/professional)调整输出
    3. 返回evaluations列表
    """
    
    def __init__(self):
        self.llm_client = get_llm_client()
        
    async def __call__(self, batch_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        执行批次评分
        
        Args:
            batch_data: {
                'batch_index': int,
                'questions': List[Dict],
                'rubric_struct': Dict,
                'mm_tokens': List[Dict],
                'mode': str
            }
            
        Returns:
            evaluations列表
        """
        batch_index = batch_data['batch_index']
        questions = batch_data['questions']
        mode = batch_data.get('mode', 'professional')
        
        logger.info(f"Worker开始评分批次{batch_index}, 题目数:{len(questions)}, 模式:{mode}")
        
        evaluations = []
        
        for question in questions:
            try:
                # 评分单个题目
                evaluation = await self._evaluate_question(
                    question,
                    batch_data['rubric_struct'],
                    batch_data['mm_tokens'],
                    mode
                )
                evaluations.append(evaluation)
                
            except Exception as e:
                logger.error(f"题目{question['qid']}评分失败: {e}")
                # 创建错误评分
                evaluations.append(self._create_error_evaluation(question))
        
        logger.info(f"批次{batch_index}评分完成, 评分题目数:{len(evaluations)}")
        return evaluations
    
    async def _evaluate_question(
        self,
        question: Dict[str, Any],
        rubric_struct: Dict[str, Any],
        mm_tokens: List[Dict[str, Any]],
        mode: str
    ) -> Dict[str, Any]:
        """评分单个题目"""
        
        # 获取题目对应的评分标准
        rubric_q = self._find_rubric_question(question['qid'], rubric_struct)
        
        # 获取学生答案文本
        answer_text = self._extract_answer_text(question, mm_tokens)
        
        # 构建提示词
        if mode == 'efficient':
            prompt = self._build_efficient_prompt(question, rubric_q, answer_text)
        else:
            prompt = self._build_professional_prompt(question, rubric_q, answer_text)
        
        # 调用LLM
        messages = [
            {"role": "system", "content": self._get_system_prompt(mode)},
            {"role": "user", "content": prompt}
        ]
        
        response = self.llm_client.chat(messages, temperature=0.1, max_tokens=2000 if mode == 'efficient' else 3000)
        
        # 解析响应
        evaluation = self._parse_evaluation_response(response, question, mode)
        
        return evaluation
    
    def _find_rubric_question(self, qid: str, rubric_struct: Dict) -> Dict:
        """查找评分标准中的题目"""
        for q in rubric_struct.get('questions', []):
            if q['qid'] == qid:
                return q
        return {'qid': qid, 'max_score': 10, 'rubric_items': []}
    
    def _extract_answer_text(self, question: Dict, mm_tokens: List[Dict]) -> str:
        """提取学生答案文本"""
        token_ids = set(question.get('token_ids', []))
        answer_parts = []
        
        for token in mm_tokens:
            if token['id'] in token_ids:
                answer_parts.append(token.get('text', ''))
        
        return ' '.join(answer_parts)
    
    def _get_system_prompt(self, mode: str) -> str:
        """获取系统提示词"""
        if mode == 'efficient':
            return """你是严谨的自动批改助理。

任务：根据评分标准和学生答案，判断评分项是否符合。

要求：
1. 逐项检查评分项
2. 返回题号、得分、标签(correct/partial/wrong)、评分项id
3. 标记错误token的id列表
4. 不得输出任何解释或摘要

输出格式（严格JSON）：
{
  "qid": "Q1",
  "score": 3,
  "max_score": 4,
  "label": "partial",
  "rubric_item_id": "Q1_R2",
  "error_token_ids": ["t12", "t13"]
}"""
        else:
            return """你是专业的批改助理。

任务：根据评分标准和学生答案，进行详细批改。

要求：
1. 对每道题进行评分
2. 提供答案摘要
3. 列出错误详情和正确解法
4. 对学生表现进行评价并给出建议

输出格式（严格JSON）：
{
  "qid": "Q1",
  "score": 3,
  "max_score": 8,
  "label": "partial",
  "rubric_item_id": "Q1_R2",
  "error_token_ids": ["t12"],
  "summary": "学生正确使用了公式...",
  "error_analysis": [{
    "error_id": "E001",
    "token_ids": ["t12"],
    "description": "计算错误",
    "correct_solution": "正确解法...",
    "reason": "原因分析..."
  }],
  "comment": "评价和建议..."
}"""
    
    def _build_efficient_prompt(self, question: Dict, rubric_q: Dict, answer_text: str) -> str:
        """构建高效模式提示词"""
        return f"""评分标准：
题号：{rubric_q['qid']}
满分：{rubric_q['max_score']}
评分项：
{json.dumps(rubric_q.get('rubric_items', []), ensure_ascii=False, indent=2)}

学生答案：
{answer_text}

请进行批改，输出JSON格式结果。"""
    
    def _build_professional_prompt(self, question: Dict, rubric_q: Dict, answer_text: str) -> str:
        """构建专业模式提示词"""
        return f"""评分标准：
题号：{rubric_q['qid']}
满分：{rubric_q['max_score']}
评分项：
{json.dumps(rubric_q.get('rubric_items', []), ensure_ascii=False, indent=2)}

学生答案：
{answer_text}

请进行详细批改，包括摘要、错误分析和评价建议。输出JSON格式结果。"""
    
    def _parse_evaluation_response(self, response: str, question: Dict, mode: str) -> Dict:
        """解析评分响应"""
        try:
            # 提取JSON
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group(0))
            else:
                data = json.loads(response)
            
            # 基础字段
            evaluation = {
                'qid': question['qid'],
                'score': float(data.get('score', 0)),
                'max_score': float(data.get('max_score', question.get('max_score', 10))),
                'label': data.get('label', 'wrong'),
                'rubric_item_id': data.get('rubric_item_id', ''),
                'error_token_ids': data.get('error_token_ids', [])
            }
            
            # 专业模式扩展字段
            if mode == 'professional':
                evaluation['summary'] = data.get('summary', '')
                evaluation['error_analysis'] = data.get('error_analysis', [])
                evaluation['comment'] = data.get('comment', '')
            
            return evaluation
            
        except Exception as e:
            logger.error(f"解析评分响应失败: {e}")
            return self._create_error_evaluation(question)
    
    def _create_error_evaluation(self, question: Dict) -> Dict:
        """创建错误评分"""
        return {
            'qid': question['qid'],
            'score': 0,
            'max_score': question.get('max_score', 10),
            'label': 'error',
            'rubric_item_id': '',
            'error_token_ids': [],
            'summary': '评分失败',
            'error_analysis': [],
            'comment': '系统错误，请重新批改'
        }


def create_evaluate_batch_agent() -> EvaluateBatchAgent:
    """创建EvaluateBatchAgent实例"""
    return EvaluateBatchAgent()
