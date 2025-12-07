"""批改结果仓储类"""

from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
import json

from src.utils.database import Database


class GradingResultRepository:
    """批改结果仓储"""
    
    def __init__(self, db: Database):
        self.db = db
    
    async def create(
        self,
        submission_id: str,
        question_id: str,
        score: float,
        max_score: float,
        confidence_score: float,
        visual_annotations: List[Dict[str, Any]],
        agent_trace: Dict[str, Any],
        student_feedback: Dict[str, Any]
    ) -> Dict[str, Any]:
        """创建批改结果"""
        query = """
            INSERT INTO grading_results (
                submission_id, question_id, score, max_score, confidence_score,
                visual_annotations, agent_trace, student_feedback
            )
            VALUES (
                %(submission_id)s, %(question_id)s, %(score)s, %(max_score)s,
                %(confidence_score)s, %(visual_annotations)s, %(agent_trace)s,
                %(student_feedback)s
            )
            RETURNING submission_id, question_id, score, max_score, confidence_score,
                      visual_annotations, agent_trace, student_feedback, created_at, updated_at
        """
        
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    query,
                    {
                        "submission_id": UUID(submission_id),
                        "question_id": question_id,
                        "score": score,
                        "max_score": max_score,
                        "confidence_score": confidence_score,
                        "visual_annotations": json.dumps(visual_annotations),
                        "agent_trace": json.dumps(agent_trace),
                        "student_feedback": json.dumps(student_feedback)
                    }
                )
                result = await cur.fetchone()
                return self._format_result(result)
    
    async def get_by_composite_key(
        self,
        submission_id: str,
        question_id: str
    ) -> Optional[Dict[str, Any]]:
        """根据复合键获取批改结果"""
        query = """
            SELECT submission_id, question_id, score, max_score, confidence_score,
                   visual_annotations, agent_trace, student_feedback, created_at, updated_at
            FROM grading_results
            WHERE submission_id = %(submission_id)s AND question_id = %(question_id)s
        """
        
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    query,
                    {
                        "submission_id": UUID(submission_id),
                        "question_id": question_id
                    }
                )
                result = await cur.fetchone()
                return self._format_result(result) if result else None
    
    async def get_by_submission(self, submission_id: str) -> List[Dict[str, Any]]:
        """获取提交的所有批改结果"""
        query = """
            SELECT submission_id, question_id, score, max_score, confidence_score,
                   visual_annotations, agent_trace, student_feedback, created_at, updated_at
            FROM grading_results
            WHERE submission_id = %(submission_id)s
            ORDER BY question_id
        """
        
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, {"submission_id": UUID(submission_id)})
                results = await cur.fetchall()
                return [self._format_result(row) for row in results]
    
    async def update(
        self,
        submission_id: str,
        question_id: str,
        score: Optional[float] = None,
        confidence_score: Optional[float] = None,
        visual_annotations: Optional[List[Dict[str, Any]]] = None,
        agent_trace: Optional[Dict[str, Any]] = None,
        student_feedback: Optional[Dict[str, Any]] = None
    ) -> bool:
        """更新批改结果"""
        updates = []
        params = {
            "submission_id": UUID(submission_id),
            "question_id": question_id
        }
        
        if score is not None:
            updates.append("score = %(score)s")
            params["score"] = score
        
        if confidence_score is not None:
            updates.append("confidence_score = %(confidence_score)s")
            params["confidence_score"] = confidence_score
        
        if visual_annotations is not None:
            updates.append("visual_annotations = %(visual_annotations)s")
            params["visual_annotations"] = json.dumps(visual_annotations)
        
        if agent_trace is not None:
            updates.append("agent_trace = %(agent_trace)s")
            params["agent_trace"] = json.dumps(agent_trace)
        
        if student_feedback is not None:
            updates.append("student_feedback = %(student_feedback)s")
            params["student_feedback"] = json.dumps(student_feedback)
        
        if not updates:
            return False
        
        updates.append("updated_at = NOW()")
        
        query = f"""
            UPDATE grading_results
            SET {', '.join(updates)}
            WHERE submission_id = %(submission_id)s AND question_id = %(question_id)s
        """
        
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                return cur.rowcount > 0
    
    async def get_low_confidence_results(
        self,
        threshold: float = 0.75,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """获取低置信度的批改结果"""
        query = """
            SELECT submission_id, question_id, score, max_score, confidence_score,
                   visual_annotations, agent_trace, student_feedback, created_at, updated_at
            FROM grading_results
            WHERE confidence_score < %(threshold)s
            ORDER BY confidence_score ASC, created_at DESC
            LIMIT %(limit)s
        """
        
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    query,
                    {
                        "threshold": threshold,
                        "limit": limit
                    }
                )
                results = await cur.fetchall()
                return [self._format_result(row) for row in results]
    
    async def delete(self, submission_id: str, question_id: str) -> bool:
        """删除批改结果"""
        query = """
            DELETE FROM grading_results
            WHERE submission_id = %(submission_id)s AND question_id = %(question_id)s
        """
        
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    query,
                    {
                        "submission_id": UUID(submission_id),
                        "question_id": question_id
                    }
                )
                return cur.rowcount > 0
    
    async def delete_by_submission(self, submission_id: str) -> int:
        """删除提交的所有批改结果"""
        query = "DELETE FROM grading_results WHERE submission_id = %(submission_id)s"
        
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, {"submission_id": UUID(submission_id)})
                return cur.rowcount
    
    def _format_result(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """格式化批改结果"""
        if not row:
            return {}
        
        return {
            "submission_id": str(row["submission_id"]),
            "question_id": row["question_id"],
            "score": float(row["score"]) if row["score"] else None,
            "max_score": float(row["max_score"]) if row["max_score"] else None,
            "confidence_score": float(row["confidence_score"]) if row["confidence_score"] else None,
            "visual_annotations": row["visual_annotations"],
            "agent_trace": row["agent_trace"],
            "student_feedback": row["student_feedback"],
            "created_at": row["created_at"].isoformat() if isinstance(row["created_at"], datetime) else row["created_at"],
            "updated_at": row["updated_at"].isoformat() if isinstance(row["updated_at"], datetime) else row["updated_at"]
        }
