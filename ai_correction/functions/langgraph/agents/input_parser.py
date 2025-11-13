#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
InputParser Agent - 解析输入文件，提取题目、答案、学生信息
"""

import re
import json
from typing import List, Dict, Any, Optional
from pathlib import Path


class InputParserAgent:
    """输入解析 Agent"""

    def __init__(self, llm_client=None):
        self.supported_formats = ['.txt', '.md', '.json', '.csv', '.pdf', '.docx', '.doc',
                                 '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
        self.llm_client = llm_client
        
    def parse(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析输入文件
        
        Args:
            state: 包含 question_files, answer_files, marking_files 的状态
            
        Returns:
            更新后的状态，包含 questions, answers, student_info
        """
        try:
            # 解析题目文件
            questions = self._parse_questions(state.get('question_files', []))
            
            # 解析答案文件
            answers = self._parse_answers(state.get('answer_files', []))
            
            # 解析评分标准
            marking_scheme = self._parse_marking_scheme(state.get('marking_files', []))
            
            # 提取学生信息
            student_info = self._extract_student_info(state.get('answer_files', []))
            
            # 匹配答案与题目
            matched_data = self._match_answers(questions, answers)
            
            # 更新状态
            state.update({
                'questions': questions,
                'answers': matched_data,
                'marking_scheme': marking_scheme,
                'student_info': student_info,
                'parse_status': 'success',
                'parse_errors': []
            })
            
            return state
            
        except Exception as e:
            state.update({
                'parse_status': 'failed',
                'parse_errors': [str(e)]
            })
            return state
    
    def _parse_questions(self, files: List[str]) -> List[Dict]:
        """解析题目文件"""
        questions = []
        
        for file_path in files:
            try:
                content = self._read_file(file_path)
                parsed = self._extract_questions_from_text(content)
                questions.extend(parsed)
            except Exception as e:
                print(f"解析题目文件失败 {file_path}: {e}")
                
        return questions
    
    def _parse_answers(self, files: List[str]) -> List[Dict]:
        """解析答案文件"""
        answers = []
        
        for file_path in files:
            try:
                content = self._read_file(file_path)
                parsed = self._extract_answers_from_text(content, file_path)
                answers.extend(parsed)
            except Exception as e:
                print(f"解析答案文件失败 {file_path}: {e}")
                
        return answers
    
    def _parse_marking_scheme(self, files: List[str]) -> Dict:
        """解析评分标准"""
        if not files:
            return {}
            
        try:
            content = self._read_file(files[0])
            return self._extract_marking_scheme(content)
        except Exception as e:
            print(f"解析评分标准失败: {e}")
            return {}
    
    def _read_file(self, file_path: str) -> str:
        """读取文件内容（支持图片、PDF、Word等格式）"""
        from ...file_processor import process_file, extract_text_from_image_with_llm

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        if path.suffix not in self.supported_formats:
            raise ValueError(f"不支持的文件格式: {path.suffix}")

        # 处理文件
        file_data = process_file(file_path)

        # 如果是图片，使用 LLM 提取文字
        if file_data['type'] == 'image':
            if self.llm_client:
                print(f"📸 正在从图片中提取文字: {path.name}")
                return extract_text_from_image_with_llm(file_data['content'], self.llm_client)
            else:
                return f"[图片文件: {path.name}，需要 LLM 支持才能提取文字]"

        # 其他格式直接返回文本内容
        return file_data['content']
    
    def _extract_questions_from_text(self, text: str) -> List[Dict]:
        """从文本中提取题目"""
        questions = []

        # 支持多种题号格式：1. / (1) / 1) / 第1题 / 题目1
        patterns = [
            r'题目(\d+)[：:]\s*(.+?)(?=\n题目\d+[：:]|$)',  # 题目1：题目
            r'(\d+)\.\s*(.+?)(?=\n\d+\.|$)',  # 1. 题目
            r'\((\d+)\)\s*(.+?)(?=\n\(\d+\)|$)',  # (1) 题目
            r'(\d+)\)\s*(.+?)(?=\n\d+\)|$)',  # 1) 题目
            r'第(\d+)题[：:]\s*(.+?)(?=\n第\d+题|$)',  # 第1题：题目
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.DOTALL | re.MULTILINE)
            for match in matches:
                q_id = int(match.group(1))
                q_text = match.group(2).strip()
                
                # 识别题型
                q_type = self._identify_question_type(q_text)
                
                # 提取选项（如果是选择题）
                options = self._extract_options(q_text) if q_type == 'choice' else []
                
                questions.append({
                    'id': q_id,
                    'text': q_text,
                    'type': q_type,
                    'options': options,
                    'raw_text': match.group(0)
                })
                
            if questions:
                break  # 找到匹配就停止
                
        return questions
    
    def _extract_answers_from_text(self, text: str, file_path: str) -> List[Dict]:
        """从文本中提取答案"""
        answers = []

        # 提取学生信息
        student_id, student_name = self._extract_student_from_filename(file_path)

        # 提取答案
        patterns = [
            r'题目(\d+)答案[：:]\s*(.+?)(?=\n题目\d+答案[：:]|$)',  # 题目1答案：答案
            r'(\d+)\.\s*(.+?)(?=\n\d+\.|$)',
            r'\((\d+)\)\s*(.+?)(?=\n\(\d+\)|$)',
            r'(\d+)\)\s*(.+?)(?=\n\d+\)|$)',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.DOTALL | re.MULTILINE)
            for match in matches:
                q_id = int(match.group(1))
                answer_text = match.group(2).strip()
                
                answers.append({
                    'question_id': q_id,
                    'text': answer_text,
                    'student_id': student_id,
                    'student_name': student_name
                })
                
            if answers:
                break
                
        return answers
    
    def _extract_marking_scheme(self, text: str) -> Dict:
        """提取评分标准"""
        # 简单实现：将整个文本作为评分标准
        return {
            'raw_text': text,
            'criteria': self._parse_criteria(text)
        }
    
    def _parse_criteria(self, text: str) -> List[Dict]:
        """解析评分细则"""
        criteria = []
        
        # 查找评分点（如：1. xxx (2分)）
        pattern = r'(\d+)\.\s*(.+?)\s*\((\d+)分\)'
        matches = re.finditer(pattern, text)
        
        for match in matches:
            criteria.append({
                'id': int(match.group(1)),
                'description': match.group(2).strip(),
                'points': int(match.group(3))
            })
            
        return criteria
    
    def _identify_question_type(self, text: str) -> str:
        """识别题型"""
        if re.search(r'[A-D]\.\s*', text):
            return 'choice'
        elif re.search(r'_{3,}', text) or '填空' in text:
            return 'fill'
        elif any(kw in text for kw in ['论述', '分析', '说明', '描述', '简答']):
            return 'essay'
        elif any(kw in text for kw in ['计算', '求', '解', '证明']):
            return 'calculation'
        else:
            return 'unknown'
    
    def _extract_options(self, text: str) -> List[str]:
        """提取选择题选项"""
        options = []
        pattern = r'([A-D])\.\s*(.+?)(?=[A-D]\.|$)'
        matches = re.finditer(pattern, text, re.DOTALL)
        
        for match in matches:
            options.append(f"{match.group(1)}. {match.group(2).strip()}")
            
        return options
    
    def _extract_student_from_filename(self, file_path: str) -> tuple:
        """从文件名提取学生信息"""
        filename = Path(file_path).stem
        
        # 尝试匹配格式：001_张三 或 张三_001
        pattern = r'(\d+)_(.+)|(.+)_(\d+)'
        match = re.search(pattern, filename)
        
        if match:
            if match.group(1):
                return match.group(1), match.group(2)
            else:
                return match.group(4), match.group(3)
        
        return 'unknown', filename
    
    def _extract_student_info(self, files: List[str]) -> Dict:
        """提取学生信息"""
        if not files:
            return {'id': 'unknown', 'name': 'unknown', 'class': 'unknown'}
            
        student_id, student_name = self._extract_student_from_filename(files[0])
        
        return {
            'id': student_id,
            'name': student_name,
            'class': 'unknown'  # 可以从文件内容中提取
        }
    
    def _match_answers(self, questions: List[Dict], answers: List[Dict]) -> List[Dict]:
        """匹配答案与题目"""
        matched = []
        
        for answer in answers:
            q_id = answer['question_id']
            question = next((q for q in questions if q['id'] == q_id), None)
            
            if question:
                matched.append({
                    **answer,
                    'question': question
                })
            else:
                print(f"警告：找不到题目 {q_id} 对应的答案")
                
        return matched

