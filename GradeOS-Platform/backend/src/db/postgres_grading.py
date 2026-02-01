"""PostgreSQL grading history storage."""

import uuid
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict

from src.utils.database import db
from src.utils.sql_logger import log_sql_operation


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
    rubric: Optional[Dict[str, Any]] = None  # 评分标准（解析后的 JSON）


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
    confession: Optional[str] = None
    result_data: Optional[Dict[str, Any]] = None
    imported_at: Optional[str] = None
    revoked_at: Optional[str] = None


@dataclass
class GradingPageImage:
    """批改页面图像索引"""
    
    id: str
    grading_history_id: str
    student_key: str
    page_index: int
    file_id: str  # file storage id
    file_url: Optional[str] = None  # file download url
    content_type: Optional[str] = None  # MIME type
    created_at: str = ""


_PAGE_IMAGES_TABLE_READY = False


async def ensure_page_images_table() -> None:
    """Ensure grading_page_images table exists and includes file reference columns."""
    global _PAGE_IMAGES_TABLE_READY
    if _PAGE_IMAGES_TABLE_READY:
        return

    create_query = """
        CREATE TABLE IF NOT EXISTS grading_page_images (
            id UUID PRIMARY KEY,
            grading_history_id UUID NOT NULL,
            student_key VARCHAR(200) NOT NULL,
            page_index INTEGER NOT NULL,
            file_id VARCHAR(200),
            file_url TEXT,
            content_type VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (grading_history_id) REFERENCES grading_history(id) ON DELETE CASCADE,
            CONSTRAINT unique_page_image UNIQUE (grading_history_id, student_key, page_index)
        )
    """
    alter_queries = [
        "ALTER TABLE grading_page_images ADD COLUMN IF NOT EXISTS file_id VARCHAR(200)",
        "ALTER TABLE grading_page_images ADD COLUMN IF NOT EXISTS file_url TEXT",
        "ALTER TABLE grading_page_images ADD COLUMN IF NOT EXISTS content_type VARCHAR(100)",
    ]
    index_queries = [
        "CREATE INDEX IF NOT EXISTS idx_page_images_history ON grading_page_images(grading_history_id)",
        "CREATE INDEX IF NOT EXISTS idx_page_images_student ON grading_page_images(grading_history_id, student_key)",
        "CREATE INDEX IF NOT EXISTS idx_page_images_file_id ON grading_page_images(file_id)",
    ]

    try:
        async with db.connection() as conn:
            await conn.execute(create_query)
            for statement in alter_queries:
                await conn.execute(statement)
            for statement in index_queries:
                await conn.execute(statement)
            await conn.commit()
        _PAGE_IMAGES_TABLE_READY = True
    except Exception as exc:
        logger.error(f"Ensure grading_page_images failed: {exc}")
        raise
async def save_grading_history(history: GradingHistory) -> None:
    """保存批改历史到 PostgreSQL"""
    if not history.created_at:
        history.created_at = datetime.now().isoformat()

    query = """
        INSERT INTO grading_history 
        (id, batch_id, class_ids, created_at, completed_at, status, 
         total_students, average_score, result_data, rubric)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (batch_id) DO UPDATE SET
            class_ids = EXCLUDED.class_ids,
            completed_at = EXCLUDED.completed_at,
            status = EXCLUDED.status,
            total_students = EXCLUDED.total_students,
            average_score = EXCLUDED.average_score,
            result_data = EXCLUDED.result_data,
            rubric = EXCLUDED.rubric
    """
    params = (
        history.id,
        history.batch_id,
        json.dumps(history.class_ids) if history.class_ids else None,
        history.created_at,
        history.completed_at,
        history.status,
        history.total_students,
        history.average_score,
        json.dumps(history.result_data) if history.result_data else None,
        json.dumps(history.rubric, ensure_ascii=False) if history.rubric else None,
    )

    try:
        # Avoid logging large result_data payloads in deploy logs
        log_sql_operation("INSERT/UPDATE", "grading_history")
        async with db.connection() as conn:
            await conn.execute(query, params)
            await conn.commit()
        log_sql_operation("INSERT/UPDATE", "grading_history", result_count=1)
        logger.info(f"批改历史已保存到 PostgreSQL: batch_id={history.batch_id}")
    except Exception as e:
        log_sql_operation("INSERT/UPDATE", "grading_history", error=e)
        logger.error(f"保存批改历史到 PostgreSQL 失败: {e}")
        raise


async def get_grading_history(batch_id_or_id: str) -> Optional[GradingHistory]:
    """从 PostgreSQL 获取批改历史（支持通过 batch_id 或 id 查询）"""
    try:
        async with db.connection() as conn:
            # 先尝试通过 batch_id 查询
            query1 = "SELECT * FROM grading_history WHERE batch_id = %s"
            params1 = (batch_id_or_id,)
            log_sql_operation("SELECT", query1, params1)
            cursor = await conn.execute(query1, params1)
            row = await cursor.fetchone()

            # 如果没找到，尝试通过 id 查询
            if not row:
                query2 = "SELECT * FROM grading_history WHERE id::text = %s"
                params2 = (batch_id_or_id,)
                log_sql_operation("SELECT", query2, params2)
                cursor = await conn.execute(query2, params2)
                row = await cursor.fetchone()

            if not row:
                log_sql_operation("SELECT", "grading_history", result_count=0)
                return None

            log_sql_operation("SELECT", "grading_history", result_count=1)
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

            # 处理日期字段（可能是 datetime 对象或字符串）
            created_at_value = row["created_at"]
            if hasattr(created_at_value, 'isoformat'):
                created_at_value = created_at_value.isoformat()
            elif created_at_value:
                created_at_value = str(created_at_value)
            else:
                created_at_value = ""
            
            completed_at_value = row["completed_at"]
            if hasattr(completed_at_value, 'isoformat'):
                completed_at_value = completed_at_value.isoformat()
            elif completed_at_value:
                completed_at_value = str(completed_at_value)
            else:
                completed_at_value = None

            # 处理 rubric 字段（JSONB）
            raw_rubric = row.get("rubric")
            if isinstance(raw_rubric, str):
                rubric = json.loads(raw_rubric) if raw_rubric else None
            else:
                rubric = raw_rubric

            return GradingHistory(
                id=str(row["id"]),
                batch_id=row["batch_id"],
                status=row["status"],
                class_ids=class_ids,
                created_at=created_at_value,
                completed_at=completed_at_value,
                total_students=row["total_students"] or 0,
                average_score=float(row["average_score"]) if row["average_score"] else None,
                result_data=result_data,
                rubric=rubric,  # 添加 rubric 字段
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
                # 使用 JSONB 包含查询，同时包含 class_ids 为 NULL 的记录（控制台批改）
                query = """
                    SELECT * FROM grading_history 
                    WHERE class_ids @> %s::jsonb OR class_ids IS NULL
                    ORDER BY created_at DESC 
                    LIMIT %s
                """
                params = (json.dumps([class_id]), limit)
                log_sql_operation("SELECT", query, params)
                cursor = await conn.execute(query, params)
            else:
                query = "SELECT * FROM grading_history ORDER BY created_at DESC LIMIT %s"
                params = (limit,)
                log_sql_operation("SELECT", query, params)
                cursor = await conn.execute(query, params)

            rows = await cursor.fetchall()
            log_sql_operation("SELECT", "grading_history", result_count=len(rows))

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

                # 处理日期字段 - 可能是 datetime 对象或字符串
                created_at_value = row["created_at"]
                if hasattr(created_at_value, 'isoformat'):
                    created_at_value = created_at_value.isoformat()
                elif created_at_value:
                    created_at_value = str(created_at_value)
                else:
                    created_at_value = ""

                completed_at_value = row["completed_at"]
                if hasattr(completed_at_value, 'isoformat'):
                    completed_at_value = completed_at_value.isoformat()
                elif completed_at_value:
                    completed_at_value = str(completed_at_value)
                else:
                    completed_at_value = None

                histories.append(
                    GradingHistory(
                        id=str(row["id"]),
                        batch_id=row["batch_id"],
                        status=row["status"],
                        class_ids=class_ids,
                        created_at=created_at_value,
                        completed_at=completed_at_value,
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
    """????????? PostgreSQL"""
    # Normalize confession payloads and keep result_data in sync.
    result_data_payload = result.result_data
    confession_value = result.confession
    if isinstance(result_data_payload, dict):
        payload = dict(result_data_payload)
        if confession_value is None:
            confession_value = payload.get("confession")
        elif "confession" not in payload:
            payload["confession"] = confession_value

        for key in ("confession_data", "confessionData"):
            payload.pop(key, None)
        result_data_payload = payload

    if confession_value is not None and not isinstance(confession_value, str):
        try:
            confession_value = json.dumps(confession_value, ensure_ascii=False)
        except Exception as e:
            logger.error(f"??? confession ??: {e}")
            confession_value = None

    result_data_json = None
    if result_data_payload is not None:
        try:
            result_data_json = json.dumps(result_data_payload, ensure_ascii=False)
        except Exception as e:
            logger.error(f"??? result_data ??: {e}")
            result_data_json = "{}"

    # ?????
    update_params = (
        result.id,
        result.score,
        result.max_score,
        result.class_id,
        result.student_id,
        result.summary,
        confession_value,
        result_data_json,
        result.imported_at,
        result.revoked_at,
        result.grading_history_id,
        result.student_key,
    )

    insert_params = (
        result.id,
        result.grading_history_id,
        result.student_key,
        result.class_id,
        result.student_id,
        result.score,
        result.max_score,
        result.summary,
        confession_value,
        result_data_json,
        result.imported_at,
        result.revoked_at,
    )

    try:
        async with db.connection() as conn:
            # ??????????????
            update_query = """
                UPDATE student_grading_results 
                SET id = %s,
                    score = %s,
                    max_score = %s,
                    class_id = %s,
                    student_id = %s,
                    summary = %s,
                    confession = %s,
                    result_data = %s::jsonb,
                    imported_at = %s,
                    revoked_at = %s
                WHERE grading_history_id = %s AND student_key = %s
            """

            insert_query = """
                INSERT INTO student_grading_results 
                (id, grading_history_id, student_key, class_id, student_id,
                 score, max_score, summary, confession, result_data, 
                 imported_at, revoked_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
            """

            # ?????
            cursor = await conn.execute(update_query, update_params)
            updated_rows = cursor.rowcount

            # ??????????????????????
            if updated_rows == 0:
                log_sql_operation("INSERT", "student_grading_results")
                await conn.execute(insert_query, insert_params)
            else:
                log_sql_operation("UPDATE", "student_grading_results")

            await conn.commit()

        log_sql_operation("INSERT/UPDATE", "student_grading_results", result_count=1)
        logger.debug(f"???????: student_key={result.student_key}")
    except Exception as e:
        log_sql_operation("INSERT/UPDATE", "student_grading_results", error=e)
        logger.error(f"????????: {e}")
        raise


async def get_student_results(grading_history_id: str) -> List[StudentGradingResult]:
    """?????????????"""
    try:
        query = "SELECT * FROM student_grading_results WHERE grading_history_id = %s"
        params = (grading_history_id,)
        log_sql_operation("SELECT", query, params)

        async with db.connection() as conn:
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()

        log_sql_operation("SELECT", "student_grading_results", result_count=len(rows))

        results = []
        for row in rows:
            # JSONB ??????? dict????? str???????
            raw_result_data = row["result_data"]
            if isinstance(raw_result_data, str):
                result_data = json.loads(raw_result_data) if raw_result_data else None
            else:
                result_data = raw_result_data

            # ?????????? datetime ???????
            imported_at_value = row["imported_at"]
            if hasattr(imported_at_value, "isoformat"):
                imported_at_value = imported_at_value.isoformat()
            elif imported_at_value:
                imported_at_value = str(imported_at_value)
            else:
                imported_at_value = None

            revoked_at_value = row["revoked_at"]
            if hasattr(revoked_at_value, "isoformat"):
                revoked_at_value = revoked_at_value.isoformat()
            elif revoked_at_value:
                revoked_at_value = str(revoked_at_value)
            else:
                revoked_at_value = None

            if hasattr(row, "get"):
                confession_value = row.get("confession")
            else:
                confession_value = row["confession"]

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
                    confession=confession_value,
                    result_data=result_data,
                    imported_at=imported_at_value,
                    revoked_at=revoked_at_value,
                )
            )

        return results
    except Exception as e:
        logger.error(f"????????: {e}")
        return []


async def save_page_image(image: GradingPageImage) -> None:
    """保存批改页面图像到 PostgreSQL"""
    if not image.created_at:
        image.created_at = datetime.now().isoformat()

    await ensure_page_images_table()
    
    query = """
        INSERT INTO grading_page_images 
        (id, grading_history_id, student_key, page_index, 
         file_id, file_url, content_type, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (grading_history_id, student_key, page_index) DO UPDATE SET
            file_id = EXCLUDED.file_id,
            file_url = EXCLUDED.file_url,
            content_type = EXCLUDED.content_type,
            created_at = EXCLUDED.created_at
    """
    params = (
        image.id,
        image.grading_history_id,
        image.student_key,
        image.page_index,
        image.file_id,
        image.file_url,
        image.content_type,
        image.created_at,
    )
    
    try:
        log_sql_operation("INSERT/UPDATE", "grading_page_images")
        async with db.connection() as conn:
            await conn.execute(query, params)
            await conn.commit()
        log_sql_operation("INSERT", "grading_page_images", result_count=1)
        logger.debug(f"页面图像已保存: student_key={image.student_key}, page={image.page_index}")
    except Exception as e:
        log_sql_operation("INSERT", "grading_page_images", error=e)
        logger.error(f"保存页面图像失败: {e}")
        raise


async def get_page_images(
    grading_history_id: str, 
    student_key: Optional[str] = None
) -> List[GradingPageImage]:
    """获取批改页面图像"""
    try:
        if student_key:
            query = """
                SELECT * FROM grading_page_images 
                WHERE grading_history_id = %s AND student_key = %s
                ORDER BY page_index
            """
            params = (grading_history_id, student_key)
        else:
            query = """
                SELECT * FROM grading_page_images 
                WHERE grading_history_id = %s
                ORDER BY student_key, page_index
            """
            params = (grading_history_id,)
        
        log_sql_operation("SELECT", query, params)
        
        async with db.connection() as conn:
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()
        
        log_sql_operation("SELECT", "grading_page_images", result_count=len(rows))
        
        images = []
        for row in rows:
            # 处理日期字段（可能是 datetime 对象或字符串）
            created_at_value = row["created_at"]
            if hasattr(created_at_value, 'isoformat'):
                created_at_value = created_at_value.isoformat()
            elif created_at_value:
                created_at_value = str(created_at_value)
            else:
                created_at_value = ""
            
            images.append(
                GradingPageImage(
                    id=str(row["id"]),
                    grading_history_id=str(row["grading_history_id"]),
                    student_key=row["student_key"],
                    page_index=row["page_index"],
                    file_id=row["file_id"] or "",
                    file_url=row["file_url"],
                    content_type=row["content_type"],
                    created_at=created_at_value,
                )
            )
        
        return images
    except Exception as e:
        logger.error(f"获取页面图像失败: {e}")
        return []



@dataclass
class RubricImage:
    """评分标准图片"""
    
    id: str
    grading_history_id: str
    page_index: int
    image_data: bytes  # 图像二进制数据
    image_format: str = "png"  # 图像格式：png, jpg, webp
    created_at: str = ""


async def save_rubric_image(image: RubricImage) -> None:
    """保存评分标准图片到 PostgreSQL"""
    if not image.created_at:
        image.created_at = datetime.now().isoformat()
    
    query = """
        INSERT INTO rubric_images 
        (id, grading_history_id, page_index, 
         image_data, image_format, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (grading_history_id, page_index) 
        DO UPDATE SET
            image_data = EXCLUDED.image_data,
            image_format = EXCLUDED.image_format
    """
    params = (
        image.id,
        image.grading_history_id,
        image.page_index,
        image.image_data,
        image.image_format,
        image.created_at,
    )
    
    try:
        log_sql_operation("INSERT", "rubric_images", {"id": image.id})
        async with db.connection() as conn:
            await conn.execute(query, params)
            await conn.commit()
        log_sql_operation("INSERT", "rubric_images", result_count=1)
        logger.debug(f"评分标准图片已保存: page={image.page_index}")
    except Exception as e:
        log_sql_operation("INSERT", "rubric_images", error=e)
        logger.error(f"保存评分标准图片失败: {e}")
        raise


async def get_rubric_images(grading_history_id: str) -> List[RubricImage]:
    """获取评分标准图片"""
    try:
        query = """
            SELECT * FROM rubric_images 
            WHERE grading_history_id = %s
            ORDER BY page_index
        """
        params = (grading_history_id,)
        
        log_sql_operation("SELECT", query, params)
        
        async with db.connection() as conn:
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()
        
        log_sql_operation("SELECT", "rubric_images", result_count=len(rows))
        
        images = []
        for row in rows:
            # 处理日期字段（可能是 datetime 对象或字符串）
            created_at_value = row["created_at"]
            if hasattr(created_at_value, 'isoformat'):
                created_at_value = created_at_value.isoformat()
            elif created_at_value:
                created_at_value = str(created_at_value)
            else:
                created_at_value = ""
            
            images.append(
                RubricImage(
                    id=str(row["id"]),
                    grading_history_id=str(row["grading_history_id"]),
                    page_index=row["page_index"],
                    image_data=row["image_data"],
                    image_format=row["image_format"],
                    created_at=created_at_value,
                )
            )
        
        return images
    except Exception as e:
        logger.error(f"获取评分标准图片失败: {e}")
        return []
