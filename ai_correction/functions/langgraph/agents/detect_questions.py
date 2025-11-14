#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Detect Questions Agent - 题目识别与划分
根据题号、版式和关键字划分每道题
符合设计文档: AI批改LangGraph Agent架构设计文档 - 第7.1节
"""

import logging
import re
from typing import Dict, List, Any, Optional
from datetime import datetime

from ..state import GradingState, Question
from ...llm_client import get_llm_client

logger = logging.getLogger(__name__)


class DetectQuestionsAgent:
    """
    题目识别Agent
    
    职责:
    1. 结合rubric_struct和mm_tokens划分每道题
    2. 根据题号、关键字、版式等识别题目区域
    3. 分配每个token到对应题目
    4. 提取关键词用于后续匹配
    """
    
    def __init__(self):
        self.llm_client = get_llm_client()
        
    async def __call__(self, state: GradingState) -> GradingState:
        """
        执行题目识别
        
        Args:
            state: 包含mm_tokens和rubric_struct的状态对象
            
        Returns:
            更新后的状态对象(包含questions列表)
        """
        logger.info(f"开始题目识别 - 任务ID: {state['task_id']}")
        
        try:
            # 更新进度
            state['current_step'] = '题目识别与划分'
            state['progress_percentage'] = 50.0
            
            mm_tokens = state.get('mm_tokens', [])
            rubric_struct = state.get('rubric_struct', {})
            
            if not mm_tokens:
                logger.warning("未找到mm_tokens，无法识别题目")
                state['questions'] = []
                return state
            
            if not rubric_struct or 'questions' not in rubric_struct:
                logger.warning("未找到评分标准，使用默认题目划分")
                questions = await self._detect_without_rubric(mm_tokens)
            else:
                # 基于评分标准识别题目
                questions = await self._detect_with_rubric(
                    mm_tokens, 
                    rubric_struct['questions']
                )
            
            # 验证题目数量
            expected_count = len(rubric_struct.get('questions', []))
            if expected_count > 0 and len(questions) != expected_count:
                logger.warning(
                    f"识别到的题目数({len(questions)})"
                    f"与评分标准不一致({expected_count})"
                )
                # 使用LLM二次确认
                questions = await self._llm_verify_questions(
                    mm_tokens, 
                    rubric_struct.get('questions', []),
                    questions
                )
            
            state['questions'] = questions
            
            # 更新进度
            state['progress_percentage'] = 55.0
            state['step_results']['detect_questions'] = {
                'questions_count': len(questions),
                'timestamp': str(datetime.now())
            }
            
            logger.info(f"题目识别完成 - 任务ID: {state['task_id']}, "
                       f"识别题目数: {len(questions)}")
            
            return state
            
        except Exception as e:
            error_msg = f"题目识别失败: {str(e)}"
            logger.error(error_msg)
            state['errors'].append({
                'step': 'detect_questions',
                'error': error_msg,
                'timestamp': str(datetime.now())
            })
            state['questions'] = []
            return state
    
    async def _detect_with_rubric(
        self,
        mm_tokens: List[Dict[str, Any]],
        rubric_questions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        基于评分标准识别题目
        
        Args:
            mm_tokens: 多模态token列表
            rubric_questions: 评分标准中的题目列表
            
        Returns:
            识别到的题目列表
        """
        questions = []
        
        # 为每道题目创建Question对象
        for rubric_q in rubric_questions:
            qid = rubric_q['qid']
            max_score = rubric_q['max_score']
            
            # 提取关键词
            keywords = self._extract_keywords_from_rubric(rubric_q)
            
            # 查找题目区域
            region = self._find_question_region(mm_tokens, qid, keywords)
            
            # 分配tokens
            token_ids = self._assign_tokens(mm_tokens, region)
            
            question = {
                'qid': qid,
                'max_score': max_score,
                'region': region,
                'token_ids': token_ids,
                'keywords': keywords
            }
            
            questions.append(question)
        
        return questions
    
    def _extract_keywords_from_rubric(
        self, 
        rubric_question: Dict[str, Any]
    ) -> List[str]:
        """从评分标准中提取关键词"""
        keywords = []
        
        # 从评分项的conditions中提取
        for item in rubric_question.get('rubric_items', []):
            conditions = item.get('conditions', [])
            keywords.extend(conditions)
        
        # 去重并过滤空字符串
        keywords = list(set([k.strip() for k in keywords if k.strip()]))
        
        return keywords
    
    def _find_question_region(
        self,
        mm_tokens: List[Dict[str, Any]],
        qid: str,
        keywords: List[str]
    ) -> Dict[str, Any]:
        """
        查找题目区域
        
        Args:
            mm_tokens: token列表
            qid: 题号
            keywords: 关键词列表
            
        Returns:
            题目区域信息
        """
        # 提取题号数字
        q_num = re.search(r'\d+', qid)
        if not q_num:
            return {'page': 0, 'start_token_id': None, 'end_token_id': None}
        
        q_num = q_num.group()
        
        # 搜索题号标记
        start_idx = None
        for i, token in enumerate(mm_tokens):
            text = token.get('text', '')
            
            # 匹配题号模式
            if self._is_question_marker(text, q_num):
                start_idx = i
                break
        
        if start_idx is None:
            # 未找到题号标记，使用关键词匹配
            start_idx = self._find_by_keywords(mm_tokens, keywords)
        
        # 查找下一题的起始位置作为结束位置
        end_idx = None
        if start_idx is not None:
            next_q_num = str(int(q_num) + 1)
            for i in range(start_idx + 1, len(mm_tokens)):
                text = mm_tokens[i].get('text', '')
                if self._is_question_marker(text, next_q_num):
                    end_idx = i - 1
                    break
        
        # 如果没有找到下一题，使用页面末尾
        if end_idx is None:
            end_idx = len(mm_tokens) - 1
        
        # 获取起始token的页码
        page = mm_tokens[start_idx].get('page', 0) if start_idx is not None else 0
        
        start_token_id = mm_tokens[start_idx]['id'] if start_idx is not None else None
        end_token_id = mm_tokens[end_idx]['id'] if end_idx is not None else None
        
        return {
            'page': page,
            'start_token_id': start_token_id,
            'end_token_id': end_token_id,
            'start_index': start_idx,
            'end_index': end_idx
        }
    
    def _is_question_marker(self, text: str, q_num: str) -> bool:
        """判断是否为题号标记"""
        # 常见题号模式
        patterns = [
            rf'^[题第]*\s*{q_num}[题.、：:）)]',
            rf'^{q_num}[.、：:）)]',
            rf'^\({q_num}\)',
            rf'^【{q_num}】',
            rf'^第{q_num}题',
        ]
        
        text = text.strip()
        for pattern in patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return True
        
        return False
    
    def _find_by_keywords(
        self, 
        mm_tokens: List[Dict[str, Any]], 
        keywords: List[str]
    ) -> Optional[int]:
        """使用关键词查找起始位置"""
        if not keywords:
            return None
        
        # 计算每个token与关键词的匹配度
        best_match = None
        best_score = 0
        
        for i, token in enumerate(mm_tokens):
            text = token.get('text', '')
            score = sum(1 for kw in keywords if kw in text)
            
            if score > best_score:
                best_score = score
                best_match = i
        
        return best_match if best_score > 0 else None
    
    def _assign_tokens(
        self,
        mm_tokens: List[Dict[str, Any]],
        region: Dict[str, Any]
    ) -> List[str]:
        """分配tokens到题目"""
        token_ids = []
        
        start_idx = region.get('start_index')
        end_idx = region.get('end_index')
        
        if start_idx is None or end_idx is None:
            return token_ids
        
        for i in range(start_idx, min(end_idx + 1, len(mm_tokens))):
            token_ids.append(mm_tokens[i]['id'])
        
        return token_ids
    
    async def _detect_without_rubric(
        self,
        mm_tokens: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        无评分标准时的题目识别(降级方案)
        
        Args:
            mm_tokens: token列表
            
        Returns:
            识别到的题目列表
        """
        questions = []
        
        # 搜索所有题号标记
        question_starts = []
        for i, token in enumerate(mm_tokens):
            text = token.get('text', '')
            
            # 匹配题号模式
            match = re.match(r'^[题第]*\s*(\d+)[题.、：:）)]', text.strip())
            if match:
                q_num = match.group(1)
                question_starts.append({
                    'index': i,
                    'q_num': q_num,
                    'qid': f'Q{q_num}'
                })
        
        # 如果没找到题号，创建单个默认题目
        if not question_starts:
            return [{
                'qid': 'Q1',
                'max_score': 10.0,
                'region': {
                    'page': 0,
                    'start_token_id': mm_tokens[0]['id'],
                    'end_token_id': mm_tokens[-1]['id'],
                    'start_index': 0,
                    'end_index': len(mm_tokens) - 1
                },
                'token_ids': [t['id'] for t in mm_tokens],
                'keywords': []
            }]
        
        # 创建题目
        for i, q_start in enumerate(question_starts):
            # 确定结束位置
            if i < len(question_starts) - 1:
                end_idx = question_starts[i + 1]['index'] - 1
            else:
                end_idx = len(mm_tokens) - 1
            
            token_ids = [
                mm_tokens[j]['id'] 
                for j in range(q_start['index'], end_idx + 1)
            ]
            
            question = {
                'qid': q_start['qid'],
                'max_score': 10.0,  # 默认分值
                'region': {
                    'page': mm_tokens[q_start['index']].get('page', 0),
                    'start_token_id': mm_tokens[q_start['index']]['id'],
                    'end_token_id': mm_tokens[end_idx]['id'],
                    'start_index': q_start['index'],
                    'end_index': end_idx
                },
                'token_ids': token_ids,
                'keywords': []
            }
            
            questions.append(question)
        
        return questions
    
    async def _llm_verify_questions(
        self,
        mm_tokens: List[Dict[str, Any]],
        rubric_questions: List[Dict[str, Any]],
        detected_questions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        使用LLM二次确认题目划分
        
        Args:
            mm_tokens: token列表
            rubric_questions: 评分标准题目
            detected_questions: 已识别的题目
            
        Returns:
            确认后的题目列表
        """
        logger.info("题目数量不一致，使用LLM二次确认")
        
        try:
            # 构建提示词
            system_prompt = """你是题目识别专家，帮助确认题目划分是否正确。

任务：根据学生答案内容和评分标准，确认每道题的起始和结束位置。

输出格式：JSON数组，每个元素包含qid、start_token_id、end_token_id"""
            
            user_prompt = f"""评分标准包含{len(rubric_questions)}道题：
{', '.join([q['qid'] for q in rubric_questions])}

当前识别到{len(detected_questions)}道题。

学生答案的token列表(仅显示前50个)：
{json.dumps([{
    'id': t['id'], 
    'text': t.get('text', '')[:20]
} for t in mm_tokens[:50]], ensure_ascii=False)}

请确认题目划分，输出每道题的token范围。"""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = self.llm_client.chat(
                messages=messages,
                temperature=0.1,
                max_tokens=2000
            )
            
            # 解析响应
            import json
            verified = json.loads(self._extract_json(response))
            
            # 更新detected_questions
            for v in verified:
                qid = v.get('qid')
                for q in detected_questions:
                    if q['qid'] == qid:
                        # 更新region
                        if 'start_token_id' in v:
                            q['region']['start_token_id'] = v['start_token_id']
                        if 'end_token_id' in v:
                            q['region']['end_token_id'] = v['end_token_id']
                        break
            
            return detected_questions
            
        except Exception as e:
            logger.warning(f"LLM二次确认失败: {e}")
            return detected_questions
    
    def _extract_json(self, text: str) -> str:
        """从文本中提取JSON"""
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        match = re.search(r'\[[\s\S]*\]', text)
        if match:
            return match.group(0)
        return text.strip()


# 便捷函数
def create_detect_questions_agent() -> DetectQuestionsAgent:
    """创建DetectQuestionsAgent实例"""
    return DetectQuestionsAgent()
