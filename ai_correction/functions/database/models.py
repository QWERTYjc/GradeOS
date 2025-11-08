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
    """学生表"""
    __tablename__ = 'students'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    class_name = Column(String(100))
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

