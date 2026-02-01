"""
学生数据查询工具 - 供 AI Assistant Function Calling 使用
提供学生批改结果、错题分析、知识点掌握等数据查询功能
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import logging

from src.utils.database import get_connection

logger = logging.getLogger(__name__)


class StudentDataTools:
    """学生数据查询工具集"""

    @staticmethod
    def get_student_submissions(
        student_id: str,
        class_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        获取学生的作业提交记录
        
        Args:
            student_id: 学生ID
            class_id: 班级ID（可选）
            limit: 返回记录数量限制
            
        Returns:
            作业提交记录列表
        """
        try:
            with get_connection() as conn:
                query = """
                    SELECT 
                        s.submission_id,
                        s.assignment_id,
                        a.title as assignment_title,
                        a.subject,
                        s.total_score,
                        s.max_score,
                        s.percentage,
                        s.grade_level,
                        s.grading_status,
                        s.submitted_at,
                        s.teacher_comment
                    FROM assignment_submissions s
                    JOIN assignments a ON s.assignment_id = a.assignment_id
                    WHERE s.student_id = ?
                """
                params = [student_id]
                
                if class_id:
                    query += " AND a.class_id = ?"
                    params.append(class_id)
                
                query += " ORDER BY s.submitted_at DESC LIMIT ?"
                params.append(limit)
                
                result = conn.execute(query, params).fetchall()
                
                submissions = []
                for row in result:
                    submissions.append({
                        "submission_id": row[0],
                        "assignment_id": row[1],
                        "assignment_title": row[2],
                        "subject": row[3],
                        "total_score": row[4],
                        "max_score": row[5],
                        "percentage": row[6],
                        "grade_level": row[7],
                        "grading_status": row[8],
                        "submitted_at": row[9],
                        "teacher_comment": row[10]
                    })
                
                return submissions
                
        except Exception as e:
            logger.error(f"获取学生提交记录失败: {e}")
            return []

    @staticmethod
    def get_grading_results(
        submission_id: str
    ) -> Dict[str, Any]:
        """
        获取某次作业的详细批改结果
        
        Args:
            submission_id: 提交ID
            
        Returns:
            批改结果详情
        """
        try:
            with get_connection() as conn:
                # 获取总体信息
                submission_query = """
                    SELECT 
                        s.submission_id,
                        s.total_score,
                        s.max_score,
                        s.percentage,
                        s.grading_status,
                        a.title as assignment_title,
                        a.subject
                    FROM assignment_submissions s
                    JOIN assignments a ON s.assignment_id = a.assignment_id
                    WHERE s.submission_id = ?
                """
                submission_row = conn.execute(submission_query, [submission_id]).fetchone()
                
                if not submission_row:
                    return {"error": "未找到提交记录"}
        