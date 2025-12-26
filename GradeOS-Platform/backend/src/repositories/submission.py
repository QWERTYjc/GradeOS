"""提交记录仓储类"""

from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
import json

from src.utils.database import Database
from src.models.enums import SubmissionStatus


class SubmissionRepository:
    """提交记录仓储"""
    
    def __init__(self, db: Database):
        self.db = db
    
    async def create(
        self,
        exam_id: str,
        student_id: str,
        file_paths: List[str],
        status: SubmissionStatus = SubmissionStatus.UPLOADED
    ) -> Dict[str, Any]:
        """创建提交记录"""
        query = """
            INSERT INTO submissions (exam_id, student_id, status, file_paths)
            VALUES (%(exam_id)s, %(student_id)s, %(status)s, %(file_paths)s)
            RETURNING submission_id, exam_id, student_id, status, total_score, 
                      max_total_score, file_paths, created_at, updated_at
        """
        
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    query,
                    {
                        "exam_id": UUID(exam_id),
                        "student_id": UUID(student_id),
                        "status": status.value,
                        "file_paths": json.dumps(file_paths)
                    }
                )
                result = await cur.fetchone()
                return self._format_submission(result)
    
    async def get_by_id(self, submission_id: str) -> Optional[Dict[str, Any]]:
        """根据 ID 获取提交记录"""
        query = """
            SELECT submission_id, exam_id, student_id, status, total_score,
                   max_total_score, file_paths, created_at, updated_at
            FROM submissions
            WHERE submission_id = %(submission_id)s
        """
        
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, {"submission_id": UUID(submission_id)})
                result = await cur.fetchone()
                return self._format_submission(result) if result else None
    
    async def update_status(
        self,
        submission_id: str,
        status: str | SubmissionStatus
    ) -> bool:
        """更新提交状态"""
        # 如果是枚举类型，转换为字符串
        if isinstance(status, SubmissionStatus):
            status_value = status.value
        else:
            status_value = status
        
        query = """
            UPDATE submissions
            SET status = %(status)s, updated_at = NOW()
            WHERE submission_id = %(submission_id)s
        """
        
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    query,
                    {
                        "submission_id": UUID(submission_id),
                        "status": status_value
                    }
                )
                return cur.rowcount > 0
    
    async def update_scores(
        self,
        submission_id: str,
        total_score: float,
        max_total_score: float
    ) -> bool:
        """更新总分"""
        query = """
            UPDATE submissions
            SET total_score = %(total_score)s,
                max_total_score = %(max_total_score)s,
                updated_at = NOW()
            WHERE submission_id = %(submission_id)s
        """
        
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    query,
                    {
                        "submission_id": UUID(submission_id),
                        "total_score": total_score,
                        "max_total_score": max_total_score
                    }
                )
                return cur.rowcount > 0
    
    async def get_by_student(
        self,
        student_id: str,
        limit: int = 10,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """获取学生的提交记录列表"""
        query = """
            SELECT submission_id, exam_id, student_id, status, total_score,
                   max_total_score, file_paths, created_at, updated_at
            FROM submissions
            WHERE student_id = %(student_id)s
            ORDER BY created_at DESC
            LIMIT %(limit)s OFFSET %(offset)s
        """
        
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    query,
                    {
                        "student_id": UUID(student_id),
                        "limit": limit,
                        "offset": offset
                    }
                )
                results = await cur.fetchall()
                return [self._format_submission(row) for row in results]
    
    async def get_by_exam(
        self,
        exam_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """获取考试的提交记录列表"""
        query = """
            SELECT submission_id, exam_id, student_id, status, total_score,
                   max_total_score, file_paths, created_at, updated_at
            FROM submissions
            WHERE exam_id = %(exam_id)s
            ORDER BY created_at DESC
            LIMIT %(limit)s OFFSET %(offset)s
        """
        
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    query,
                    {
                        "exam_id": UUID(exam_id),
                        "limit": limit,
                        "offset": offset
                    }
                )
                results = await cur.fetchall()
                return [self._format_submission(row) for row in results]
    
    async def get_pending_reviews(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取待审核的提交记录"""
        query = """
            SELECT submission_id, exam_id, student_id, status, total_score,
                   max_total_score, file_paths, created_at, updated_at
            FROM submissions
            WHERE status = 'REVIEWING'
            ORDER BY created_at ASC
            LIMIT %(limit)s
        """
        
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, {"limit": limit})
                results = await cur.fetchall()
                return [self._format_submission(row) for row in results]
    
    async def delete(self, submission_id: str) -> bool:
        """删除提交记录"""
        query = "DELETE FROM submissions WHERE submission_id = %(submission_id)s"
        
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, {"submission_id": UUID(submission_id)})
                return cur.rowcount > 0
    
    def _format_submission(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """格式化提交记录"""
        if not row:
            return {}
        
        return {
            "submission_id": str(row["submission_id"]),
            "exam_id": str(row["exam_id"]),
            "student_id": str(row["student_id"]),
            "status": row["status"],
            "total_score": float(row["total_score"]) if row["total_score"] else None,
            "max_total_score": float(row["max_total_score"]) if row["max_total_score"] else None,
            "file_paths": row["file_paths"],
            "created_at": row["created_at"].isoformat() if isinstance(row["created_at"], datetime) else row["created_at"],
            "updated_at": row["updated_at"].isoformat() if isinstance(row["updated_at"], datetime) else row["updated_at"]
        }
