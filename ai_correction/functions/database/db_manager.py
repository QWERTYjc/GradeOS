#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库管理模块 - 支持 PostgreSQL 和 MySQL
"""

import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from contextlib import contextmanager


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, db_type: str = 'postgresql', connection_string: str = None):
        """
        初始化数据库管理器
        
        Args:
            db_type: 数据库类型 ('postgresql' 或 'mysql')
            connection_string: 数据库连接字符串
        """
        self.db_type = db_type
        self.connection_string = connection_string or self._get_connection_string()
        self.engine = None
        self.Session = None
        
        self._init_database()
    
    def _get_connection_string(self) -> str:
        """从环境变量获取数据库连接字符串"""
        if self.db_type == 'postgresql':
            return os.getenv('DATABASE_URL', 'postgresql://localhost/ai_correction')
        else:
            return os.getenv('DATABASE_URL', 'mysql://localhost/ai_correction')
    
    def _init_database(self):
        """初始化数据库连接"""
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            
            self.engine = create_engine(self.connection_string, echo=False)
            self.Session = sessionmaker(bind=self.engine)
            
            # 创建表
            self._create_tables()
            
        except ImportError:
            print("警告：SQLAlchemy 未安装，使用 JSON 文件存储")
            self.engine = None
            self.Session = None
    
    def _create_tables(self):
        """创建数据库表"""
        if not self.engine:
            return
        
        from sqlalchemy import MetaData
        from .models import Base
        
        # 创建所有表
        Base.metadata.create_all(self.engine)
    
    @contextmanager
    def get_session(self):
        """获取数据库会话"""
        if self.Session:
            session = self.Session()
            try:
                yield session
                session.commit()
            except Exception as e:
                session.rollback()
                raise e
            finally:
                session.close()
        else:
            # 使用 JSON 文件存储
            yield None
    
    def save_student(self, student_data: Dict[str, Any]) -> int:
        """保存学生信息"""
        with self.get_session() as session:
            if session:
                from .models import Student
                
                student = Student(
                    student_id=student_data['id'],
                    name=student_data['name'],
                    class_name=student_data.get('class', 'unknown')
                )
                session.add(student)
                session.flush()
                return student.id
            else:
                # JSON 存储
                return self._save_to_json('students', student_data)
    
    def save_grading_task(self, task_data: Dict[str, Any]) -> int:
        """保存批改任务"""
        with self.get_session() as session:
            if session:
                from .models import GradingTask
                
                task = GradingTask(
                    student_id=task_data['student_id'],
                    subject=task_data.get('subject', 'unknown'),
                    total_questions=task_data.get('total_questions', 0),
                    status='pending'
                )
                session.add(task)
                session.flush()
                return task.id
            else:
                return self._save_to_json('grading_tasks', task_data)
    
    def save_grading_results(self, results: List[Dict[str, Any]], task_id: int):
        """保存批改结果"""
        with self.get_session() as session:
            if session:
                from .models import GradingResult
                
                for result in results:
                    gr = GradingResult(
                        task_id=task_id,
                        question_id=result['question_id'],
                        score=result['score'],
                        max_score=result['max_score'],
                        feedback=result.get('feedback', ''),
                        strategy=result.get('strategy', 'unknown')
                    )
                    session.add(gr)
            else:
                for result in results:
                    result['task_id'] = task_id
                    self._save_to_json('grading_results', result)
    
    def save_statistics(self, stats_data: Dict[str, Any], task_id: int):
        """保存统计数据"""
        with self.get_session() as session:
            if session:
                from .models import GradingStatistics
                
                stats = GradingStatistics(
                    task_id=task_id,
                    total_score=stats_data['total_score'],
                    max_score=stats_data['max_score'],
                    percentage=stats_data['percentage'],
                    grade=stats_data['grade'],
                    statistics_json=json.dumps(stats_data.get('statistics', {}))
                )
                session.add(stats)
            else:
                stats_data['task_id'] = task_id
                self._save_to_json('statistics', stats_data)
    
    def save_error_analysis(self, error_data: Dict[str, Any], task_id: int):
        """保存错误分析"""
        with self.get_session() as session:
            if session:
                from .models import ErrorAnalysis
                
                for error in error_data.get('error_questions', []):
                    ea = ErrorAnalysis(
                        task_id=task_id,
                        question_id=error['question_id'],
                        error_type='low_score',
                        description=error.get('feedback', ''),
                        suggestion=''
                    )
                    session.add(ea)
            else:
                error_data['task_id'] = task_id
                self._save_to_json('error_analysis', error_data)
    
    def get_student_history(self, student_id: str) -> List[Dict]:
        """获取学生历史记录"""
        with self.get_session() as session:
            if session:
                from .models import GradingTask, GradingStatistics
                
                tasks = session.query(GradingTask).filter_by(student_id=student_id).all()
                
                history = []
                for task in tasks:
                    stats = session.query(GradingStatistics).filter_by(task_id=task.id).first()
                    history.append({
                        'task_id': task.id,
                        'subject': task.subject,
                        'created_at': task.created_at.isoformat(),
                        'total_score': stats.total_score if stats else 0,
                        'max_score': stats.max_score if stats else 0,
                        'grade': stats.grade if stats else 'N/A'
                    })
                
                return history
            else:
                return self._load_from_json('grading_tasks', {'student_id': student_id})
    
    def get_class_statistics(self, class_name: str) -> Dict:
        """获取班级统计"""
        with self.get_session() as session:
            if session:
                from .models import Student, GradingTask, GradingStatistics
                from sqlalchemy import func
                
                # 获取班级所有学生
                students = session.query(Student).filter_by(class_name=class_name).all()
                student_ids = [s.student_id for s in students]
                
                # 获取所有任务
                tasks = session.query(GradingTask).filter(
                    GradingTask.student_id.in_(student_ids)
                ).all()
                
                # 统计数据
                total_tasks = len(tasks)
                avg_score = session.query(func.avg(GradingStatistics.percentage)).join(
                    GradingTask
                ).filter(GradingTask.student_id.in_(student_ids)).scalar() or 0
                
                return {
                    'class_name': class_name,
                    'student_count': len(students),
                    'total_tasks': total_tasks,
                    'average_score': float(avg_score)
                }
            else:
                return {'class_name': class_name, 'student_count': 0, 'total_tasks': 0, 'average_score': 0}
    
    def _save_to_json(self, collection: str, data: Dict) -> int:
        """保存到 JSON 文件（备用方案）"""
        file_path = f'data/{collection}.json'
        os.makedirs('data', exist_ok=True)
        
        # 读取现有数据
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                records = json.load(f)
        else:
            records = []
        
        # 添加新记录
        data['id'] = len(records) + 1
        data['created_at'] = datetime.now().isoformat()
        records.append(data)
        
        # 保存
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        
        return data['id']
    
    def _load_from_json(self, collection: str, filters: Dict = None) -> List[Dict]:
        """从 JSON 文件加载（备用方案）"""
        file_path = f'data/{collection}.json'
        
        if not os.path.exists(file_path):
            return []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            records = json.load(f)
        
        # 应用过滤器
        if filters:
            records = [r for r in records if all(r.get(k) == v for k, v in filters.items())]
        
        return records


class DataPersistenceAgent:
    """数据持久化 Agent"""
    
    def __init__(self, db_manager: DatabaseManager = None):
        """
        Args:
            db_manager: 数据库管理器
        """
        self.db_manager = db_manager or DatabaseManager()
    
    def persist(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        持久化数据
        
        Args:
            state: 包含所有批改结果的状态
            
        Returns:
            更新后的状态，添加 persistence_status
        """
        try:
            # 保存学生信息
            student_info = state.get('student_info', {})
            student_db_id = self.db_manager.save_student(student_info)
            
            # 保存批改任务
            task_data = {
                'student_id': student_info.get('id'),
                'subject': state.get('subject', 'unknown'),
                'total_questions': len(state.get('questions', []))
            }
            task_id = self.db_manager.save_grading_task(task_data)
            
            # 保存批改结果
            grading_results = state.get('grading_results', [])
            self.db_manager.save_grading_results(grading_results, task_id)
            
            # 保存统计数据
            aggregated = state.get('aggregated_results', {})
            self.db_manager.save_statistics(aggregated, task_id)
            
            # 保存错误分析
            error_analysis = aggregated.get('error_analysis', {})
            self.db_manager.save_error_analysis(error_analysis, task_id)
            
            state.update({
                'task_id': task_id,
                'persistence_status': 'success'
            })
            
            return state
            
        except Exception as e:
            state.update({
                'persistence_status': 'failed',
                'persistence_errors': [str(e)]
            })
            return state

