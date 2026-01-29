"""评分细则仓储类"""

from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
import json

from src.utils.database import Database


class RubricRepository:
    """评分细则仓储"""

    def __init__(self, db: Database):
        self.db = db

    async def create(
        self,
        exam_id: str,
        question_id: str,
        rubric_text: str,
        max_score: float,
        scoring_points: List[Dict[str, Any]],
        standard_answer: Optional[str] = None,
    ) -> Dict[str, Any]:
        """创建评分细则"""
        query = """
            INSERT INTO rubrics (
                exam_id, question_id, rubric_text, max_score,
                scoring_points, standard_answer
            )
            VALUES (
                %(exam_id)s, %(question_id)s, %(rubric_text)s, %(max_score)s,
                %(scoring_points)s, %(standard_answer)s
            )
            RETURNING rubric_id, exam_id, question_id, rubric_text, max_score,
                      scoring_points, standard_answer, created_at, updated_at
        """

        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    query,
                    {
                        "exam_id": UUID(exam_id),
                        "question_id": question_id,
                        "rubric_text": rubric_text,
                        "max_score": max_score,
                        "scoring_points": json.dumps(scoring_points),
                        "standard_answer": standard_answer,
                    },
                )
                result = await cur.fetchone()
                return self._format_rubric(result)

    async def get_by_id(self, rubric_id: str) -> Optional[Dict[str, Any]]:
        """根据 ID 获取评分细则"""
        query = """
            SELECT rubric_id, exam_id, question_id, rubric_text, max_score,
                   scoring_points, standard_answer, created_at, updated_at
            FROM rubrics
            WHERE rubric_id = %(rubric_id)s
        """

        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, {"rubric_id": UUID(rubric_id)})
                result = await cur.fetchone()
                return self._format_rubric(result) if result else None

    async def get_by_exam_and_question(
        self, exam_id: str, question_id: str
    ) -> Optional[Dict[str, Any]]:
        """根据考试 ID 和题目 ID 获取评分细则"""
        query = """
            SELECT rubric_id, exam_id, question_id, rubric_text, max_score,
                   scoring_points, standard_answer, created_at, updated_at
            FROM rubrics
            WHERE exam_id = %(exam_id)s AND question_id = %(question_id)s
        """

        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, {"exam_id": UUID(exam_id), "question_id": question_id})
                result = await cur.fetchone()
                return self._format_rubric(result) if result else None

    async def get_by_exam(self, exam_id: str) -> List[Dict[str, Any]]:
        """获取考试的所有评分细则"""
        query = """
            SELECT rubric_id, exam_id, question_id, rubric_text, max_score,
                   scoring_points, standard_answer, created_at, updated_at
            FROM rubrics
            WHERE exam_id = %(exam_id)s
            ORDER BY question_id
        """

        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, {"exam_id": UUID(exam_id)})
                results = await cur.fetchall()
                return [self._format_rubric(row) for row in results]

    async def update(
        self,
        rubric_id: str,
        rubric_text: Optional[str] = None,
        max_score: Optional[float] = None,
        scoring_points: Optional[List[Dict[str, Any]]] = None,
        standard_answer: Optional[str] = None,
    ) -> bool:
        """更新评分细则"""
        updates = []
        params = {"rubric_id": UUID(rubric_id)}

        if rubric_text is not None:
            updates.append("rubric_text = %(rubric_text)s")
            params["rubric_text"] = rubric_text

        if max_score is not None:
            updates.append("max_score = %(max_score)s")
            params["max_score"] = max_score

        if scoring_points is not None:
            updates.append("scoring_points = %(scoring_points)s")
            params["scoring_points"] = json.dumps(scoring_points)

        if standard_answer is not None:
            updates.append("standard_answer = %(standard_answer)s")
            params["standard_answer"] = standard_answer

        if not updates:
            return False

        updates.append("updated_at = NOW()")

        query = f"""
            UPDATE rubrics
            SET {', '.join(updates)}
            WHERE rubric_id = %(rubric_id)s
        """

        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                return cur.rowcount > 0

    async def delete(self, rubric_id: str) -> bool:
        """删除评分细则"""
        query = "DELETE FROM rubrics WHERE rubric_id = %(rubric_id)s"

        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, {"rubric_id": UUID(rubric_id)})
                return cur.rowcount > 0

    async def delete_by_exam(self, exam_id: str) -> int:
        """删除考试的所有评分细则"""
        query = "DELETE FROM rubrics WHERE exam_id = %(exam_id)s"

        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, {"exam_id": UUID(exam_id)})
                return cur.rowcount

    async def exists(self, exam_id: str, question_id: str) -> bool:
        """检查评分细则是否存在"""
        query = """
            SELECT EXISTS(
                SELECT 1 FROM rubrics
                WHERE exam_id = %(exam_id)s AND question_id = %(question_id)s
            )
        """

        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, {"exam_id": UUID(exam_id), "question_id": question_id})
                result = await cur.fetchone()
                return result["exists"] if result else False

    def _format_rubric(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """格式化评分细则"""
        if not row:
            return {}

        return {
            "rubric_id": str(row["rubric_id"]),
            "exam_id": str(row["exam_id"]),
            "question_id": row["question_id"],
            "rubric_text": row["rubric_text"],
            "max_score": float(row["max_score"]),
            "scoring_points": row["scoring_points"],
            "standard_answer": row["standard_answer"],
            "created_at": (
                row["created_at"].isoformat()
                if isinstance(row["created_at"], datetime)
                else row["created_at"]
            ),
            "updated_at": (
                row["updated_at"].isoformat()
                if isinstance(row["updated_at"], datetime)
                else row["updated_at"]
            ),
        }
