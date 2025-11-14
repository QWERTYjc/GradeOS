#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Student Information Matcher - 学生信息匹配器
实现模糊匹配和消歧逻辑
符合设计文档: AI批改LangGraph Agent架构设计文档 - 第16节
"""

import logging
from typing import List, Dict, Optional, Tuple
from difflib import SequenceMatcher
import re
from sqlalchemy.orm import Session
from .models import Student

logger = logging.getLogger(__name__)


class StudentMatcher:
    """
    学生信息匹配器
    
    职责:
    1. 模糊匹配学生姓名
    2. 学号精确匹配
    3. 消歧处理（多个匹配结果）
    4. 新学生自动注册
    """
    
    def __init__(self, db_session: Session, similarity_threshold: float = 0.75):
        """
        初始化匹配器
        
        参数:
            db_session: 数据库会话
            similarity_threshold: 相似度阈值（0.0-1.0）
        """
        self.db = db_session
        self.similarity_threshold = similarity_threshold
    
    def match_student(self, extracted_info: Dict, class_id: str = None) -> Tuple[Optional[Student], float, str]:
        """
        匹配学生信息
        
        参数:
            extracted_info: 从图片提取的学生信息 {'name': '张三', 'student_id': '20210001'}
            class_id: 班级ID（可选）
        
        返回:
            (Student对象, 置信度, 匹配方式)
        """
        name = extracted_info.get('name', '').strip()
        student_id = extracted_info.get('student_id', '').strip()
        
        if not name and not student_id:
            logger.warning("没有提供学生信息")
            return None, 0.0, 'no_info'
        
        # 优先级1: 学号精确匹配
        if student_id:
            student, confidence = self._match_by_student_id(student_id)
            if student:
                return student, confidence, 'student_id_exact'
        
        # 优先级2: 姓名+班级精确匹配
        if name and class_id:
            student, confidence = self._match_by_name_and_class(name, class_id)
            if student and confidence >= 0.95:
                return student, confidence, 'name_class_exact'
        
        # 优先级3: 姓名模糊匹配
        if name:
            student, confidence = self._fuzzy_match_by_name(name, class_id)
            if student and confidence >= self.similarity_threshold:
                return student, confidence, 'name_fuzzy'
        
        # 优先级4: 学号模糊匹配
        if student_id:
            student, confidence = self._fuzzy_match_by_student_id(student_id)
            if student and confidence >= self.similarity_threshold:
                return student, confidence, 'student_id_fuzzy'
        
        # 没有找到匹配
        logger.info(f"未找到匹配学生: name={name}, student_id={student_id}")
        return None, 0.0, 'no_match'
    
    def match_or_create(self, extracted_info: Dict, class_id: str = None) -> Tuple[Student, bool]:
        """
        匹配学生，如果不存在则创建新学生
        
        参数:
            extracted_info: 提取的学生信息
            class_id: 班级ID
        
        返回:
            (Student对象, 是否新创建)
        """
        student, confidence, match_type = self.match_student(extracted_info, class_id)
        
        if student:
            logger.info(f"匹配到学生: {student.name} ({match_type}, 置信度: {confidence:.2f})")
            return student, False
        
        # 创建新学生
        logger.info(f"创建新学生: {extracted_info}")
        new_student = self._create_student(extracted_info, class_id)
        return new_student, True
    
    def _match_by_student_id(self, student_id: str) -> Tuple[Optional[Student], float]:
        """学号精确匹配"""
        student = self.db.query(Student).filter(Student.student_id == student_id).first()
        
        if student:
            return student, 1.0
        return None, 0.0
    
    def _match_by_name_and_class(self, name: str, class_id: str) -> Tuple[Optional[Student], float]:
        """姓名+班级精确匹配"""
        student = self.db.query(Student).filter(
            Student.name == name,
            Student.class_id == class_id
        ).first()
        
        if student:
            return student, 1.0
        return None, 0.0
    
    def _fuzzy_match_by_name(self, name: str, class_id: str = None) -> Tuple[Optional[Student], float]:
        """姓名模糊匹配"""
        # 构建查询
        query = self.db.query(Student)
        if class_id:
            query = query.filter(Student.class_id == class_id)
        
        candidates = query.all()
        
        if not candidates:
            return None, 0.0
        
        # 计算相似度
        best_match = None
        best_score = 0.0
        
        for candidate in candidates:
            score = self._calculate_name_similarity(name, candidate.name)
            if score > best_score:
                best_score = score
                best_match = candidate
        
        return best_match, best_score
    
    def _fuzzy_match_by_student_id(self, student_id: str) -> Tuple[Optional[Student], float]:
        """学号模糊匹配"""
        candidates = self.db.query(Student).all()
        
        if not candidates:
            return None, 0.0
        
        best_match = None
        best_score = 0.0
        
        for candidate in candidates:
            score = self._calculate_student_id_similarity(student_id, candidate.student_id)
            if score > best_score:
                best_score = score
                best_match = candidate
        
        return best_match, best_score
    
    def _calculate_name_similarity(self, name1: str, name2: str) -> float:
        """
        计算姓名相似度
        
        考虑因素:
        - 字符串相似度
        - 拼音相似度（可扩展）
        - 常见错误（如形近字）
        """
        # 基础相似度
        base_similarity = SequenceMatcher(None, name1, name2).ratio()
        
        # 如果完全相同
        if name1 == name2:
            return 1.0
        
        # 去除空格后比较
        if name1.replace(' ', '') == name2.replace(' ', ''):
            return 0.98
        
        # 姓氏匹配加权
        if len(name1) >= 2 and len(name2) >= 2:
            if name1[0] == name2[0]:  # 姓氏相同
                base_similarity += 0.1
        
        return min(base_similarity, 1.0)
    
    def _calculate_student_id_similarity(self, id1: str, id2: str) -> float:
        """
        计算学号相似度
        
        考虑因素:
        - 数字相似度
        - OCR常见错误（0/O, 1/I等）
        """
        # 基础相似度
        base_similarity = SequenceMatcher(None, id1, id2).ratio()
        
        # 完全相同
        if id1 == id2:
            return 1.0
        
        # 去除非数字字符后比较
        id1_digits = re.sub(r'[^0-9]', '', id1)
        id2_digits = re.sub(r'[^0-9]', '', id2)
        
        if id1_digits == id2_digits:
            return 0.95
        
        # OCR错误纠正
        id1_corrected = self._correct_ocr_errors(id1)
        id2_corrected = self._correct_ocr_errors(id2)
        
        if id1_corrected == id2_corrected:
            return 0.90
        
        return base_similarity
    
    def _correct_ocr_errors(self, text: str) -> str:
        """纠正OCR常见错误"""
        corrections = {
            'O': '0',
            'o': '0',
            'I': '1',
            'l': '1',
            'Z': '2',
            'S': '5',
            'B': '8',
        }
        
        corrected = text
        for wrong, correct in corrections.items():
            corrected = corrected.replace(wrong, correct)
        
        return corrected
    
    def _create_student(self, extracted_info: Dict, class_id: str = None) -> Student:
        """创建新学生记录"""
        new_student = Student(
            student_id=extracted_info.get('student_id', f"AUTO_{id(extracted_info)}"),
            name=extracted_info.get('name', '未知学生'),
            class_id=class_id,
            extra_metadata={'auto_created': True, 'source': 'ocr_extraction'}
        )
        
        self.db.add(new_student)
        self.db.commit()
        
        logger.info(f"新学生已创建: {new_student.name} ({new_student.student_id})")
        return new_student
    
    def disambiguate(self, candidates: List[Student], extracted_info: Dict) -> Student:
        """
        消歧处理 - 从多个候选中选择最佳匹配
        
        参数:
            candidates: 候选学生列表
            extracted_info: 提取的学生信息
        
        返回:
            最佳匹配的学生
        """
        if len(candidates) == 1:
            return candidates[0]
        
        # 综合评分
        scores = []
        for candidate in candidates:
            score = 0.0
            
            # 姓名匹配分数
            if 'name' in extracted_info:
                name_score = self._calculate_name_similarity(
                    extracted_info['name'], 
                    candidate.name
                )
                score += name_score * 0.4
            
            # 学号匹配分数
            if 'student_id' in extracted_info:
                id_score = self._calculate_student_id_similarity(
                    extracted_info['student_id'],
                    candidate.student_id
                )
                score += id_score * 0.6
            
            scores.append(score)
        
        # 选择最高分
        best_index = scores.index(max(scores))
        return candidates[best_index]


# 使用示例
"""
from sqlalchemy.orm import Session
from .student_matcher import StudentMatcher

# 创建匹配器
matcher = StudentMatcher(db_session, similarity_threshold=0.75)

# 匹配学生
extracted_info = {'name': '张三', 'student_id': '20210001'}
student, confidence, match_type = matcher.match_student(extracted_info, class_id='class_001')

if student:
    print(f"匹配成功: {student.name} (置信度: {confidence:.2f}, 方式: {match_type})")
else:
    print("未找到匹配")

# 匹配或创建
student, is_new = matcher.match_or_create(extracted_info, class_id='class_001')
if is_new:
    print(f"创建新学生: {student.name}")
else:
    print(f"匹配到现有学生: {student.name}")
"""
