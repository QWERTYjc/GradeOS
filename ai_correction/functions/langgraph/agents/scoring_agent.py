#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scoring Agent - AI智能评分
使用 LangGraph 系统的智能评分功能
"""

import os
import logging
import json
from typing import Dict, List, Any
from datetime import datetime

from ..state import GradingState
from ...llm_client import get_llm_client

logger = logging.getLogger(__name__)

class ScoringAgent:
    """
    AI评分代理
    集成现有的 calling_api.py 功能，提供智能评分
    """
    
    def __init__(self):
        self.supported_modes = ['efficient', 'detailed', 'batch', 'generate_scheme', 'auto']
        
    async def __call__(self, state: GradingState) -> GradingState:
        """
        执行AI评分
        """
        logger.info(f"开始AI评分 - 任务ID: {state['task_id']}")
        
        try:
            # 更新进度
            state['current_step'] = "AI智能评分"
            state['progress_percentage'] = 60.0
            
            # 获取评分参数
            mode = state.get('mode', 'auto')
            strictness_level = state.get('strictness_level', '中等')
            language = state.get('language', 'zh')
            
            # 获取文件路径
            question_files = state.get('question_files', [])
            answer_files = state.get('answer_files', [])
            marking_files = state.get('marking_files', [])
            
            # 执行评分
            scoring_results = await self._perform_scoring(
                question_files, answer_files, marking_files,
                mode, strictness_level, language
            )
            
            # 解析评分结果
            parsed_results = await self._parse_scoring_results(scoring_results)
            
            # 更新状态
            state['scoring_results'] = parsed_results
            state['final_score'] = parsed_results.get('final_score', 0)
            state['grade_level'] = parsed_results.get('grade_level', 'C')
            state['detailed_feedback'] = parsed_results.get('detailed_feedback', [])
            
            # 更新进度
            state['progress_percentage'] = 70.0
            state['step_results']['scoring'] = {
                'final_score': state['final_score'],
                'grade_level': state['grade_level'],
                'feedback_count': len(state['detailed_feedback'])
            }
            
            logger.info(f"AI评分完成 - 任务ID: {state['task_id']}, 得分: {state['final_score']}")
            return state
            
        except Exception as e:
            error_msg = f"AI评分失败: {str(e)}"
            logger.error(error_msg)
            state['errors'].append({
                'step': 'scoring',
                'error': error_msg,
                'timestamp': str(datetime.now())
            })
            raise
    
    async def _perform_scoring(
        self,
        question_files: List[str],
        answer_files: List[str], 
        marking_files: List[str],
        mode: str,
        strictness_level: str,
        language: str
    ) -> str:
        """执行评分 - 使用LLM直接评分"""
        try:
            # 获取LLM客户端
            llm_client = get_llm_client()
            
            # 读取文件内容
            file_contents = self._read_file_contents(question_files, answer_files, marking_files)
            
            # 构建评分提示词
            prompt = self._build_scoring_prompt(
                file_contents, strictness_level, language
            )
            
            # 构建消息
            messages = [
                {"role": "system", "content": "你是一位资深教育专家，擅长批改学生答案。使用标准Unicode数学符号，禁用LaTeX格式。"},
                {"role": "user", "content": prompt}
            ]
            
            # 调用LLM进行评分
            logger.info(f"调用LLM进行评分，文件数量: 题目{len(question_files)}, 答案{len(answer_files)}, 标准{len(marking_files)}")
            response = llm_client.chat(messages, temperature=0.7, max_tokens=4096)
            
            logger.info(f"LLM评分完成，响应长度: {len(response)}")
            return response
            
        except Exception as e:
            logger.error(f"LLM评分失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return self._create_fallback_scoring_result()
    
    def _read_file_contents(self, question_files, answer_files, marking_files):
        """读取文件内容"""
        contents = {
            'questions': [],
            'answers': [],
            'marking_schemes': []
        }
        
        # 读取题目
        for f in question_files:
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    contents['questions'].append(file.read())
            except Exception as e:
                logger.warning(f"读取题目文件失败 {f}: {e}")
        
        # 读取答案
        for f in answer_files:
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    contents['answers'].append(file.read())
            except Exception as e:
                logger.warning(f"读取答案文件失败 {f}: {e}")
        
        # 读取评分标准
        for f in marking_files:
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    contents['marking_schemes'].append(file.read())
            except Exception as e:
                logger.warning(f"读取评分标准失败 {f}: {e}")
        
        return contents
    
    def _build_scoring_prompt(self, file_contents, strictness_level, language):
        """构建评分提示词"""
        
        # 严格程度描述
        strictness_desc = {
            '宽松': '请温和地批改，对小错误给予适当宽容',
            '中等': '请公正地批改，关注主要概念和步骤',
            '严格': '请严格批改，对任何错误都要指出并合理扣分'
        }.get(strictness_level, '请公正地批改')
        
        prompt = f"""请对以下学生答案进行批改评分。

【评分要求】
- 严格程度：{strictness_desc}
- 输出语言：{'中文' if language == 'zh' else '英文'}
- 使用标准Unicode数学符号，禁用LaTeX格式

"""
        
        # 添加题目内容
        if file_contents['questions']:
            prompt += "【题目】\n"
            for i, q in enumerate(file_contents['questions'], 1):
                prompt += f"题目{i}：\n{q}\n\n"
        
        # 添加学生答案
        if file_contents['answers']:
            prompt += "【学生答案】\n"
            for i, a in enumerate(file_contents['answers'], 1):
                prompt += f"答案{i}：\n{a}\n\n"
        
        # 添加评分标准
        if file_contents['marking_schemes']:
            prompt += "【评分标准】\n"
            for i, m in enumerate(file_contents['marking_schemes'], 1):
                prompt += f"标准{i}：\n{m}\n\n"
        else:
            prompt += "【评分标准】\n请根据题目要求和学生答案自行制定合理的评分标准。\n\n"
        
        prompt += """【输出要求】
请以JSON格式输出批改结果，包含以下字段：
{
  "score": 得分(数字),
  "total": 总分(数字),
  "grade": "等级(A/B/C/D/F)",
  "feedback": ["反馈列表"],
  "errors": ["错误列表"],
  "strengths": ["优点列表"],
  "suggestions": ["改进建议列表"]
}
"""
        
        return prompt
    
    def _create_fallback_scoring_result(self):
        """创建备选评分结果"""
        return json.dumps({
            "score": 0,
            "grade": "F",
            "feedback": ["评分系统暂时不可用"],
            "errors": ["LLM调用失败"],
            "strengths": [],
            "suggestions": ["请稍后重试"]
        })
    
    def _load_marking_scheme(self, marking_file: str) -> str:
        """加载评分标准"""
        try:
            # 如果是文本文件，直接读取
            if marking_file.endswith(('.txt', '.md')):
                with open(marking_file, 'r', encoding='utf-8') as f:
                    return f.read()
            else:
                # 如果是图像文件，需要OCR识别
                # 这里可以调用OCR功能，暂时返回默认标准
                return "请根据标准答案进行评分"
        except Exception as e:
            logger.warning(f"加载评分标准失败: {e}")
            return "请根据标准答案进行评分"
    
    async def _parse_scoring_results(self, raw_result: str) -> Dict[str, Any]:
        """解析评分结果"""
        try:
            # 尝试解析JSON格式的结果
            if raw_result.strip().startswith('{'):
                json_result = json.loads(raw_result)
                return self._process_json_result(json_result)
            else:
                # 解析文本格式的结果
                return self._process_text_result(raw_result)
                
        except Exception as e:
            logger.warning(f"解析评分结果失败: {e}")
            return self._create_fallback_result(raw_result)
    
    def _process_json_result(self, json_result: Dict[str, Any]) -> Dict[str, Any]:
        """处理JSON格式的评分结果"""
        return {
            'final_score': json_result.get('score', 0),
            'grade_level': json_result.get('grade', 'C'),
            'detailed_feedback': json_result.get('feedback', []),
            'errors': json_result.get('errors', []),
            'strengths': json_result.get('strengths', []),
            'suggestions': json_result.get('suggestions', []),
            'raw_result': json_result
        }
    
    def _process_text_result(self, text_result: str) -> Dict[str, Any]:
        """处理文本格式的评分结果"""
        # 提取得分
        score = self._extract_score_from_text(text_result)
        
        # 提取等级
        grade = self._extract_grade_from_text(text_result)
        
        # 提取反馈
        feedback = self._extract_feedback_from_text(text_result)
        
        return {
            'final_score': score,
            'grade_level': grade,
            'detailed_feedback': feedback,
            'errors': [],
            'strengths': [],
            'suggestions': [],
            'raw_result': text_result
        }
    
    def _extract_score_from_text(self, text: str) -> float:
        """从文本中提取得分"""
        import re
        
        # 查找得分模式
        score_patterns = [
            r'得分[：:]\s*(\d+(?:\.\d+)?)',
            r'分数[：:]\s*(\d+(?:\.\d+)?)',
            r'(\d+(?:\.\d+)?)\s*分',
            r'(\d+(?:\.\d+)?)/\d+',
        ]
        
        for pattern in score_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    continue
        
        return 0.0
    
    def _extract_grade_from_text(self, text: str) -> str:
        """从文本中提取等级"""
        import re
        
        # 查找等级模式
        grade_patterns = [
            r'等级[：:]\s*([A-F][+-]?)',
            r'级别[：:]\s*([A-F][+-]?)',
            r'([A-F][+-]?)\s*等',
        ]
        
        for pattern in grade_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        
        # 根据得分推断等级
        score = self._extract_score_from_text(text)
        if score >= 90:
            return 'A'
        elif score >= 80:
            return 'B'
        elif score >= 70:
            return 'C'
        elif score >= 60:
            return 'D'
        else:
            return 'F'
    
    def _extract_feedback_from_text(self, text: str) -> List[Dict[str, Any]]:
        """从文本中提取反馈"""
        feedback = []
        
        # 分割文本为段落
        paragraphs = text.split('\n')
        
        current_feedback = {}
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            
            # 识别不同类型的反馈
            if any(keyword in paragraph for keyword in ['错误', '问题', '不正确']):
                if current_feedback:
                    feedback.append(current_feedback)
                current_feedback = {
                    'type': 'error',
                    'content': paragraph,
                    'severity': 'medium'
                }
            elif any(keyword in paragraph for keyword in ['正确', '很好', '优秀']):
                if current_feedback:
                    feedback.append(current_feedback)
                current_feedback = {
                    'type': 'strength',
                    'content': paragraph,
                    'severity': 'low'
                }
            elif any(keyword in paragraph for keyword in ['建议', '改进', '可以']):
                if current_feedback:
                    feedback.append(current_feedback)
                current_feedback = {
                    'type': 'suggestion',
                    'content': paragraph,
                    'severity': 'low'
                }
            else:
                # 通用反馈
                if current_feedback:
                    current_feedback['content'] += '\n' + paragraph
                else:
                    current_feedback = {
                        'type': 'general',
                        'content': paragraph,
                        'severity': 'low'
                    }
        
        if current_feedback:
            feedback.append(current_feedback)
        
        return feedback
    
    def _create_fallback_result(self, raw_result: str) -> Dict[str, Any]:
        """创建备选结果"""
        return {
            'final_score': 0.0,
            'grade_level': 'F',
            'detailed_feedback': [{
                'type': 'error',
                'content': '评分结果解析失败，请检查原始结果',
                'severity': 'high'
            }],
            'errors': ['评分结果解析失败'],
            'strengths': [],
            'suggestions': ['请重新提交进行评分'],
            'raw_result': raw_result
        }
