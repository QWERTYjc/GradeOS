#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库模型定义
"""

from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class Student(Base):
    """学生表 - 扩展支持班级系统集成"""
    __tablename__ = 'students'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    class_id = Column(String(100), index=True)  # 新增：关联班级
    class_name = Column(String(100))
    email = Column(String(200))  # 新增：邮箱
    phone = Column(String(50))  # 新增：电话
    extra_metadata = Column(JSON)  # 新增：其他元数据
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 关系
    grading_tasks = relationship('GradingTask', back_populates='student')


class GradingTask(Base):
    """批改任务表"""
    __tablename__ = 'grading_tasks'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String(50), ForeignKey('students.student_id'), nullable=False, index=True)
    subject = Column(String(50))
    total_questions = Column(Integer, default=0)
    status = Column(String(20), default='pending')  # pending, processing, completed, failed
    created_at = Column(DateTime, default=datetime.now)
    completed_at = Column(DateTime)
    
    # 关系
    student = relationship('Student', back_populates='grading_tasks')
    results = relationship('GradingResult', back_populates='task')
    statistics = relationship('GradingStatistics', back_populates='task', uselist=False)
    error_analysis = relationship('ErrorAnalysis', back_populates='task')


class GradingResult(Base):
    """批改结果表（逐题）"""
    __tablename__ = 'grading_results'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey('grading_tasks.id'), nullable=False, index=True)
    question_id = Column(Integer, nullable=False)
    score = Column(Float, nullable=False)
    max_score = Column(Float, nullable=False)
    feedback = Column(Text)
    strategy = Column(String(50))  # keyword_match, semantic, rubric, step_by_step
    created_at = Column(DateTime, default=datetime.now)
    
    # 关系
    task = relationship('GradingTask', back_populates='results')


class GradingStatistics(Base):
    """批改统计表"""
    __tablename__ = 'grading_statistics'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey('grading_tasks.id'), nullable=False, unique=True, index=True)
    total_score = Column(Float, nullable=False)
    max_score = Column(Float, nullable=False)
    percentage = Column(Float, nullable=False)
    grade = Column(String(10))  # A, B, C, D, F
    statistics_json = Column(JSON)  # 详细统计数据（JSON格式）
    created_at = Column(DateTime, default=datetime.now)
    
    # 关系
    task = relationship('GradingTask', back_populates='statistics')


class ErrorAnalysis(Base):
    """错误分析表"""
    __tablename__ = 'error_analysis'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey('grading_tasks.id'), nullable=False, index=True)
    question_id = Column(Integer, nullable=False)
    error_type = Column(String(50))  # keyword_missing, semantic_error, calculation_error, etc.
    description = Column(Text)
    suggestion = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    
    # 关系
    task = relationship('GradingTask', back_populates='error_analysis')


class Assignment(Base):
    """作业表 - 新增支持班级系统集成"""
    __tablename__ = 'assignments'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    assignment_id = Column(String(100), unique=True, nullable=False, index=True)
    class_id = Column(String(100), ForeignKey('classes.class_id'), nullable=False, index=True)
    teacher_id = Column(String(100), nullable=False, index=True)
    subject = Column(String(50))
    title = Column(String(200), nullable=False)
    description = Column(Text)
    rubric_id = Column(String(100))  # 评分标准ID
    rubric_text = Column(Text)  # 评分标准文本
    rubric_struct = Column(JSON)  # 评分标准结构化数据
    total_questions = Column(Integer, default=0)
    max_score = Column(Float, default=0)
    mode = Column(String(20), default='professional')  # efficient / professional
    deadline = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 关系
    class_obj = relationship('Class', back_populates='assignments')
    submissions = relationship('AssignmentSubmission', back_populates='assignment')


class Class(Base):
    """班级表 - 新增支持班级系统集成"""
    __tablename__ = 'classes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    class_id = Column(String(100), unique=True, nullable=False, index=True)
    class_name = Column(String(100), nullable=False)
    teacher_id = Column(String(100), nullable=False, index=True)
    subject = Column(String(50))
    student_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 关系
    assignments = relationship('Assignment', back_populates='class_obj')
    evaluations = relationship('ClassEvaluation', back_populates='class_obj')


class AssignmentSubmission(Base):
    """作业提交表 - 新增支持作业管理"""
    __tablename__ = 'assignment_submissions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    submission_id = Column(String(100), unique=True, nullable=False, index=True)
    assignment_id = Column(String(100), ForeignKey('assignments.assignment_id'), nullable=False, index=True)
    student_id = Column(String(50), ForeignKey('students.student_id'), nullable=False, index=True)
    task_id = Column(String(100), unique=True, index=True)  # LangGraph任务ID
    
    # 提交信息
    answer_files = Column(JSON)  # 答卷文件列表
    submitted_at = Column(DateTime, default=datetime.now)
    
    # 批改状态
    grading_status = Column(String(20), default='pending')  # pending, processing, completed, failed
    grading_mode = Column(String(20))  # efficient / professional
    
    # 批改结果
    total_score = Column(Float)
    max_score = Column(Float)
    percentage = Column(Float)
    grade_level = Column(String(10))  # A, B, C, D, F
    
    # 评价和反馈
    student_evaluation = Column(JSON)  # 学生个人评价
    evaluations = Column(JSON)  # 各题评分详情
    annotations = Column(JSON)  # 坐标标注数据
    
    # 导出数据
    export_payload = Column(JSON)  # 导出到班级系统的数据包
    push_status = Column(String(20))  # success, failed, pending
    push_timestamp = Column(DateTime)
    
    # 元数据
    mm_tokens = Column(JSON)  # 多模态token数据
    questions = Column(JSON)  # 题目划分数据
    batches = Column(JSON)  # 批次划分数据
    errors = Column(JSON)  # 错误日志
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 关系
    assignment = relationship('Assignment', back_populates='submissions')
    student = relationship('Student')


class ClassEvaluation(Base):
    """班级评价表 - 新增支持班级整体分析"""
    __tablename__ = 'class_evaluations'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    evaluation_id = Column(String(100), unique=True, nullable=False, index=True)
    class_id = Column(String(100), ForeignKey('classes.class_id'), nullable=False, index=True)
    assignment_id = Column(String(100), ForeignKey('assignments.assignment_id'), nullable=False, index=True)
    
    # 基本统计
    student_count = Column(Integer, nullable=False)
    average_score = Column(Float)
    max_score_value = Column(Float)
    min_score_value = Column(Float)
    median_score = Column(Float)
    average_percentage = Column(Float)
    pass_rate = Column(Float)  # 及格率
    
    # 分数分布
    score_distribution = Column(JSON)  # {'A': 10, 'B': 15, ...}
    
    # 问题分析
    common_issues = Column(JSON)  # 共性问题列表
    excellent_performances = Column(JSON)  # 优秀表现列表
    
    # 知识点掌握
    knowledge_mastery = Column(JSON)  # 各知识点掌握情况
    
    # 教学建议
    teaching_suggestions = Column(JSON)  # 教学建议列表
    
    # 完整评价数据
    evaluation_data = Column(JSON)  # 完整的评价JSON
    
    generated_at = Column(DateTime, default=datetime.now)
    created_at = Column(DateTime, default=datetime.now)
    
    # 关系
    class_obj = relationship('Class', back_populates='evaluations')


class StudentKnowledgePoint(Base):
    """学生知识点掌握表 - 新增支持知识图谱"""
    __tablename__ = 'student_knowledge_points'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String(50), ForeignKey('students.student_id'), nullable=False, index=True)
    knowledge_point = Column(String(200), nullable=False, index=True)
    subject = Column(String(50))
    
    # 掌握情况
    mastery_level = Column(Float, default=0.0)  # 0.0 - 1.0
    correct_count = Column(Integer, default=0)
    total_count = Column(Integer, default=0)
    
    # 最近表现
    last_assignment_id = Column(String(100))
    last_score = Column(Float)
    last_evaluated_at = Column(DateTime)
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 关系
    student = relationship('Student')
