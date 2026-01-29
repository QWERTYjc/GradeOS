"""PostgreSQL grading history storage."""

import uuid
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict

from src.utils.database import db


logger = logging.getLogger(__name__)


@dataclass
class GradingHistory:
    """批改历史"""

    id: str
    batch_id: str
    status: str = "pending"  # pending, completed, imported, revoked
    class_ids: Optional[List[str]] = None
    created_at: str = ""
    completed_at: Optional[str] = None
    total_students: int = 0
    average_score: Optional[float] = None
    result_data: Optional[Dict[str, Any]] = None


@dataclass
class StudentGradingResult:
    """学生批改结果"""

    id: str
    grading_history_id: str
    student_key: str
    score: Optional[float] = None
    max_score: Optional[float] = None
    class_id: Optional[str] = None
    student_id: Optional[str] = None
    summary: Optional[str] = None
    self_report: Optional[str] = None
    result_data: Optional[Dict[str, Any]] = None
    imported_at: Optional[str] = None
    revoked_at: Optional[str] = None


async def save_grading_history(history: GradingHistory) -> None:
    """保存批改历史到 PostgreSQL"""
    if not history.created_at:
        history.created_at = datetime.now().isoformat()

    try:
        async with db.connection() as conn:
            await conn.execute(
                """
                INSERT INTO grading_history 
                (id, batch_id, class_ids, created_at, completed_at, status, 
                 total_students, average_score, result_data)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (batch_id) DO UPDATE SET
                    class_ids = EXCLUDED.class_ids,
                    completed_at = EXCLUDED.completed_at,
                    status = EXCLUDED.status,
                    total_students = EXCLUDED.total_students,
                    average_score = EXCLUDED.average_score,
                    result_data = EXCLUDED.result_data
                """,
                (
                    history.id,
                    history.batch_id,
                    json.dumps(history.class_ids) if history.class_ids else None,
                    history.created_at,
                    history.completed_at,
                    history.status,
                    history.total_students,
                    history.average_score,
                    json.dumps(history.result_data) if history.result_data else None,
                ),
            )
            await conn.commit()
        logger.info(f"批改历史已保存到 PostgreSQL: batch_id={history.batch_id}")
    except Exception as e:
        logger.error(f"保存批改历史到 PostgreSQL 失败: {e}")
        raise


async def get_grading_history(batch_id_or_id: str) -> Optional[GradingHistory]:
    """从 PostgreSQL 获取批改历史（支持通过 batch_id 或 id 查询）"""
    try:
        async with db.connection() as conn:
            # 先尝试通过 batch_id 查询
            cursor = await conn.execute(
                "SELECT * FROM grading_history WHERE batch_id = %s", (batch_id_or_id,)
            )
            row = await cursor.fetchone()

            # 如果没找到，尝试通过 id 查询
            if not row:
                cursor = await conn.execute(
                    "SELECT * FROM grading_history WHERE id::text = %s", (batch_id_or_id,)
                )
                row = await cursor.fetchone()

            if not row:
                return None

            # JSONB 字段可能已经是 dict，也可能是 str（取决于驱动）
            raw_class_ids = row["class_ids"]
            if isinstance(raw_class_ids, str):
                class_ids = json.loads(raw_class_ids) if raw_class_ids else None
            else:
                class_ids = raw_class_ids

            raw_result_data = row["result_data"]
            if isinstance(raw_result_data, str):
                result_data = json.loads(raw_result_data) if raw_result_data else None
            else:
                result_data = raw_result_data

            return GradingHistory(
                id=str(row["id"]),
                batch_id=row["batch_id"],
                status=row["status"],
                class_ids=class_ids,
                created_at=row["created_at"].isoformat() if row["created_at"] else "",
                completed_at=row["completed_at"].isoformat() if row["completed_at"] else None,
                total_students=row["total_students"] or 0,
                average_score=float(row["average_score"]) if row["average_score"] else None,
                result_data=result_data,
            )
    except Exception as e:
        logger.error(f"从 PostgreSQL 获取批改历史失败: {e}")
        return None


async def list_grading_history(
    class_id: Optional[str] = None, limit: int = 50
) -> List[GradingHistory]:
    """列出批改历史"""
    try:
        async with db.connection() as conn:
            if class_id:
                # 使用 JSONB 包含查询
                cursor = await conn.execute(
                    """
                    SELECT * FROM grading_history 
                    WHERE class_ids @> %s::jsonb
                    ORDER BY created_at DESC 
                    LIMIT %s
                    """,
                    (json.dumps([class_id]), limit),
                )
            else:
                cursor = await conn.execute(
                    "SELECT * FROM grading_history ORDER BY created_at DESC LIMIT %s", (limit,)
                )

            rows = await cursor.fetchall()

            histories = []
            for row in rows:
                # JSONB 字段可能已经是 dict，也可能是 str（取决于驱动）
                raw_class_ids = row["class_ids"]
                if isinstance(raw_class_ids, str):
                    class_ids = json.loads(raw_class_ids) if raw_class_ids else None
                else:
                    class_ids = raw_class_ids  # 已经是 list/dict

                raw_result_data = row["result_data"]
                if isinstance(raw_result_data, str):
                    result_data = json.loads(raw_result_data) if raw_result_data else None
                else:
                    result_data = raw_result_data  # 已经是 dict

                histories.append(
                    GradingHistory(
                        id=str(row["id"]),
                        batch_id=row["batch_id"],
                        status=row["status"],
                        class_ids=class_ids,
                        created_at=row["created_at"].isoformat() if row["created_at"] else "",
                        completed_at=(
                            row["completed_at"].isoformat() if row["completed_at"] else None
                        ),
                        total_students=row["total_students"] or 0,
                        average_score=float(row["average_score"]) if row["average_score"] else None,
                        result_data=result_data,
                    )
                )

            return histories
    except Exception as e:
        logger.error(f"列出批改历史失败: {e}")
        return []


async def save_student_result(result: StudentGradingResult) -> None:
    """保存学生批改结果到 PostgreSQL"""
    try:
        async with db.connection() as conn:
            await conn.execute(
                """
                INSERT INTO student_grading_results 
                (id, grading_history_id, student_key, class_id, student_id,
                 score, max_score, summary, self_report, result_data, 
                 imported_at, revoked_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    score = EXCLUDED.score,
                    max_score = EXCLUDED.max_score,
                    summary = EXCLUDED.summary,
                    self_report = EXCLUDED.self_report,
                    result_data = EXCLUDED.result_data,
                    imported_at = EXCLUDED.imported_at,
                    revoked_at = EXCLUDED.revoked_at
                """,
                (
                    result.id,
                    result.grading_history_id,
                    result.student_key,
                    result.class_id,
                    result.student_id,
                    result.score,
                    result.max_score,
                    result.summary,
                    result.self_report,
                    json.dumps(result.result_data) if result.result_data else None,
                    result.imported_at,
                    result.revoked_at,
                ),
            )
            await conn.commit()
        logger.debug(f"学生结果已保存: student_key={result.student_key}")
    except Exception as e:
        logger.error(f"保存学生结果失败: {e}")
        raise


async def get_student_results(grading_history_id: str) -> List[StudentGradingResult]:
    """获取批改历史的所有学生结果"""
    try:
        async with db.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM student_grading_results WHERE grading_history_id = %s",
                (grading_history_id,),
            )
            rows = await cursor.fetchall()

            results = []
            for row in rows:
                # JSONB 字段可能已经是 dict，也可能是 str（取决于驱动）
                raw_result_data = row["result_data"]
                if isinstance(raw_result_data, str):
                    result_data = json.loads(raw_result_data) if raw_result_data else None
                else:
                    result_data = raw_result_data

                results.append(
                    StudentGradingResult(
                        id=str(row["id"]),
                        grading_history_id=str(row["grading_history_id"]),
                        student_key=row["student_key"],
                        class_id=row["class_id"],
                        student_id=row["student_id"],
                        score=float(row["score"]) if row["score"] else None,
                        max_score=float(row["max_score"]) if row["max_score"] else None,
                        summary=row["summary"],
                        self_report=row["self_report"],
                        result_data=result_data,
                        imported_at=row["imported_at"].isoformat() if row["imported_at"] else None,
                        revoked_at=row["revoked_at"].isoformat() if row["revoked_at"] else None,
                    )
                )

            return results
    except Exception as e:
        logger.error(f"获取学生结果失败: {e}")
        return []
