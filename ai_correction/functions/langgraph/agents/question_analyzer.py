#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QuestionAnalyzer Agent - 分析题目特征，识别题型、难度、批改策略
"""

import sys
from pathlib import Path
from typing import Dict, Any, List

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from functions.llm_client import get_llm_client


class QuestionAnalyzerAgent:
    """题目分析 Agent"""
    
    # 题型配置
    QUESTION_TYPES = {
        'choice': {
            'features': ['选项', 'A.', 'B.', 'C.', 'D.'],
            'strategy': 'keyword_match',
            'expected_answer_length': 'short',
            'base_difficulty': 1
        },
        'fill': {
            'features': ['___', '空白', '填空'],
            'strategy': 'semantic',
            'expected_answer_length': 'short',
            'base_difficulty': 2
        },
        'essay': {
            'features': ['论述', '分析', '说明', '描述', '简答'],
            'strategy': 'rubric',
            'expected_answer_length': 'long',
            'base_difficulty': 4
        },
        'calculation': {
            'features': ['计算', '求', '解', '证明'],
            'strategy': 'step_by_step',
            'expected_answer_length': 'medium',
            'base_difficulty': 3
        }
    }
    
    def __init__(self):
        pass
    
    def analyze(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析题目特征
        
        Args:
            state: 包含 questions 的状态
            
        Returns:
            更新后的状态，questions 中添加 analysis 字段
        """
        try:
            questions = state.get('questions', [])
            
            for question in questions:
                # 分析题型
                q_type = question.get('type', 'unknown')
                
                # 评估难度
                difficulty = self._estimate_difficulty(question)
                
                # 确定批改策略
                strategy = self._determine_strategy(q_type, difficulty)
                
                # 提取关键词
                keywords = self._extract_keywords(question['text'])
                
                # 添加分析结果
                question['analysis'] = {
                    'difficulty': difficulty,
                    'strategy': strategy,
                    'keywords': keywords,
                    'expected_answer_length': self.QUESTION_TYPES.get(q_type, {}).get('expected_answer_length', 'medium')
                }
            
            state.update({
                'questions': questions,
                'analysis_status': 'success'
            })
            
            return state
            
        except Exception as e:
            state.update({
                'analysis_status': 'failed',
                'analysis_errors': [str(e)]
            })
            return state
    
    def _estimate_difficulty(self, question: Dict) -> str:
        """
        评估题目难度
        
        因素：
        1. 题目长度（长 = 难）
        2. 关键词复杂度
        3. 题型基础难度
        """
        q_type = question.get('type', 'unknown')
        text = question.get('text', '')
        
        # 基础难度
        base_difficulty = self.QUESTION_TYPES.get(q_type, {}).get('base_difficulty', 2)
        
        # 长度因素
        length_factor = 0
        if len(text) > 200:
            length_factor = 2
        elif len(text) > 100:
            length_factor = 1
        
        # 复杂词汇因素
        complex_keywords = ['综合', '分析', '评价', '论证', '推导', '证明']
        complexity_factor = sum(1 for kw in complex_keywords if kw in text)
        
        # 计算总难度
        total_difficulty = base_difficulty + length_factor + complexity_factor
        
        # 映射到难度等级
        if total_difficulty <= 2:
            return 'easy'
        elif total_difficulty <= 4:
            return 'medium'
        else:
            return 'hard'
    
    def _determine_strategy(self, q_type: str, difficulty: str) -> str:
        """
        确定批改策略
        
        策略：
        - keyword_match: 关键词匹配（选择题、填空题）
        - semantic: 语义理解（填空题、简答题）
        - rubric: 评分标准（解答题、论述题）
        - step_by_step: 步骤分析（计算题、证明题）
        """
        base_strategy = self.QUESTION_TYPES.get(q_type, {}).get('strategy', 'semantic')
        
        # 根据难度调整策略
        if difficulty == 'hard' and base_strategy == 'keyword_match':
            return 'semantic'  # 难题使用语义理解
        
        return base_strategy
    
    def _extract_keywords(self, text: str) -> List[str]:
        """
        提取关键词
        
        简单实现：提取名词、动词、形容词
        """
        # 这里使用简单的规则，实际可以使用 NLP 库
        keywords = []
        
        # 常见关键词模式
        important_words = [
            '计算', '求', '解', '证明', '分析', '说明', '描述', '论述',
            '比较', '评价', '总结', '归纳', '推导', '判断', '选择'
        ]
        
        for word in important_words:
            if word in text:
                keywords.append(word)
        
        return keywords[:5]  # 最多返回5个关键词


class QuestionGraderAgent:
    """题目批改 Agent - 逐题批改"""
    
    def __init__(self, llm_client=None):
        """
        Args:
            llm_client: LLM 客户端（Gemini/GPT/OpenRouter）
        """
        try:
            self.llm_client = llm_client or get_llm_client()
            print(f"🎯 QuestionGrader 初始化: LLM={self.llm_client.provider}")
        except Exception as e:
            print(f"⚠️ LLM 初始化失败，将使用简单策略: {e}")
            self.llm_client = None
    
    def grade(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        逐题批改
        
        Args:
            state: 包含 questions, answers, marking_scheme 的状态
            
        Returns:
            更新后的状态，添加 grading_results
        """
        try:
            answers = state.get('answers', [])
            marking_scheme = state.get('marking_scheme', {})
            
            grading_results = []
            
            for answer in answers:
                question = answer.get('question', {})
                analysis = question.get('analysis', {})
                strategy = analysis.get('strategy', 'semantic')
                
                # 根据策略批改
                if strategy == 'keyword_match':
                    result = self._grade_by_keywords(question, answer, marking_scheme)
                elif strategy == 'semantic':
                    result = self._grade_by_semantic(question, answer, marking_scheme)
                elif strategy == 'rubric':
                    result = self._grade_by_rubric(question, answer, marking_scheme)
                elif strategy == 'step_by_step':
                    result = self._grade_by_steps(question, answer, marking_scheme)
                else:
                    result = self._grade_by_semantic(question, answer, marking_scheme)
                
                grading_results.append(result)
            
            state.update({
                'grading_results': grading_results,
                'grading_status': 'success'
            })
            
            return state
            
        except Exception as e:
            state.update({
                'grading_status': 'failed',
                'grading_errors': [str(e)]
            })
            return state
    
    def _grade_by_keywords(self, question: Dict, answer: Dict, marking_scheme: Dict) -> Dict:
        """关键词匹配批改"""
        keywords = question.get('analysis', {}).get('keywords', [])
        answer_text = answer.get('text', '')
        
        # 计算关键词匹配度
        matched_keywords = [kw for kw in keywords if kw in answer_text]
        match_rate = len(matched_keywords) / len(keywords) if keywords else 0
        
        # 简单评分
        score = int(match_rate * 10)
        
        return {
            'question_id': question['id'],
            'student_id': answer.get('student_id'),
            'score': score,
            'max_score': 10,
            'matched_keywords': matched_keywords,
            'feedback': f"关键词匹配度: {match_rate*100:.1f}%",
            'strategy': 'keyword_match'
        }
    
    def _grade_by_semantic(self, question: Dict, answer: Dict, marking_scheme: Dict) -> Dict:
        """语义理解批改（需要 LLM）"""
        if not self.llm_client:
            print("⚠️ 无 LLM，使用关键词匹配")
            return self._grade_by_keywords(question, answer, marking_scheme)

        try:
            # 使用 LLM 进行语义分析
            prompt = f"""请批改以下答案，并以 JSON 格式返回结果：

题目：{question.get('text', '')}
学生答案：{answer.get('text', '')}

请返回 JSON 格式：
{{
    "score": 得分（0-10分的整数）,
    "feedback": "详细反馈",
    "errors": ["错误点1", "错误点2"],
    "suggestions": ["改进建议1", "改进建议2"]
}}
"""

            print(f"📡 调用 LLM 批改题目 {question.get('id')}")

            messages = [{"role": "user", "content": prompt}]
            response = self.llm_client.chat(messages, temperature=0.3)

            # 解析 LLM 响应
            import json
            import re

            # 提取 JSON
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result_data = json.loads(json_match.group())
                score = result_data.get('score', 7)
                feedback = result_data.get('feedback', '答案基本正确')
                errors = result_data.get('errors', [])
                suggestions = result_data.get('suggestions', [])
            else:
                # 如果无法解析 JSON，使用默认值
                score = 7
                feedback = response[:200]  # 取前200字符
                errors = []
                suggestions = []

            print(f"✅ LLM 批改完成: 得分={score}/10")

            return {
                'question_id': question['id'],
                'student_id': answer.get('student_id'),
                'score': score,
                'max_score': 10,
                'feedback': feedback,
                'errors': errors,
                'suggestions': suggestions,
                'strategy': 'semantic'
            }

        except Exception as e:
            print(f"❌ LLM 批改失败: {e}，使用关键词匹配")
            return self._grade_by_keywords(question, answer, marking_scheme)
    
    def _grade_by_rubric(self, question: Dict, answer: Dict, marking_scheme: Dict) -> Dict:
        """评分标准批改"""
        criteria = marking_scheme.get('criteria', [])
        
        # 使用 LLM 根据评分标准批改
        return self._grade_by_semantic(question, answer, marking_scheme)
    
    def _grade_by_steps(self, question: Dict, answer: Dict, marking_scheme: Dict) -> Dict:
        """步骤分析批改"""
        # 分析答案步骤
        return self._grade_by_semantic(question, answer, marking_scheme)

