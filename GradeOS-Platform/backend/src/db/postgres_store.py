"""PostgreSQL 状态持久化模块

用于存储工作流暂停态和批改结果。
支持：
1. 工作流状态持久化
2. 批改历史记录
3. 学生批改结果
"""

import os
import uuid
import json
import hashlib
import logging
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict
from contextlib import contextmanager
import psycopg
from psycopg.rows import dict_row


logger = logging.getLogger(__name__)

# 数据库文件路径


def _get_connection_string() -> str:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        return database_url
    host = os.getenv("DB_HOST", "localhost").strip()
    port = os.getenv("DB_PORT", "5432").strip()
    name = os.getenv("DB_NAME", "ai_grading").strip()
    user = os.getenv("DB_USER", "postgres").strip()
    password = os.getenv("DB_PASSWORD", "postgres").strip()
    return f"postgresql://{user}:{password}@{host}:{port}/{name}"


class _PGConnectionWrapper:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def execute(self, query: str, params: Optional[tuple] = None):
        sql = query.replace("?", "%s")
        return self._conn.execute(sql, params or ())

    def __getattr__(self, name: str):
        return getattr(self._conn, name)


@contextmanager
def get_connection():
    """Get Postgres connection (context manager)."""
    conn = psycopg.connect(_get_connection_string(), row_factory=dict_row)
    try:
        yield _PGConnectionWrapper(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """初始化数据库表"""
    with get_connection() as conn:
        # 工作流状态表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS workflow_state (
                id TEXT PRIMARY KEY,
                batch_id TEXT UNIQUE NOT NULL,
                status TEXT NOT NULL DEFAULT 'running',
                pause_point TEXT,
                state_data TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # 批改历史表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS grading_history (
                id TEXT PRIMARY KEY,
                batch_id TEXT UNIQUE NOT NULL,
                class_ids TEXT,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                total_students INTEGER DEFAULT 0,
                average_score REAL,
                result_data TEXT
            )
        """)

        # Import records (per class)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS grading_imports (
                id TEXT PRIMARY KEY,
                batch_id TEXT NOT NULL,
                class_id TEXT NOT NULL,
                assignment_id TEXT,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'imported',
                revoked_at TEXT,
                student_count INTEGER DEFAULT 0
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_imports_batch_id ON grading_imports(batch_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_imports_class_id ON grading_imports(class_id)")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS grading_import_items (
                id TEXT PRIMARY KEY,
                import_id TEXT NOT NULL,
                batch_id TEXT NOT NULL,
                class_id TEXT NOT NULL,
                student_id TEXT NOT NULL,
                student_name TEXT,
                status TEXT NOT NULL DEFAULT 'imported',
                created_at TEXT NOT NULL,
                revoked_at TEXT,
                result_data TEXT,
                FOREIGN KEY (import_id) REFERENCES grading_imports(id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_import_items_import ON grading_import_items(import_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_import_items_student ON grading_import_items(student_id)")
        
        # 学生批改结果表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS student_grading_results (
                id TEXT PRIMARY KEY,
                grading_history_id TEXT NOT NULL,
                student_key TEXT NOT NULL,
                class_id TEXT,
                student_id TEXT,
                score REAL,
                max_score REAL,
                summary TEXT,
                self_report TEXT,
                result_data TEXT,
                imported_at TEXT,
                revoked_at TEXT,
                FOREIGN KEY (grading_history_id) REFERENCES grading_history(id)
            )
        """)
        
        # 创建索引
        conn.execute("CREATE INDEX IF NOT EXISTS idx_workflow_batch_id ON workflow_state(batch_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_grading_batch_id ON grading_history(batch_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_student_grading_history ON student_grading_results(grading_history_id)")
        
        # 作业提交表 - 存储班级作业的学生提交图片
        conn.execute("""
            CREATE TABLE IF NOT EXISTS homework_submissions (
                id TEXT PRIMARY KEY,
                class_id TEXT NOT NULL,
                homework_id TEXT NOT NULL,
                student_id TEXT NOT NULL,
                student_name TEXT,
                images TEXT,  -- JSON array of base64 or file paths
                content TEXT,
                submission_type TEXT,
                page_count INTEGER DEFAULT 0,
                submitted_at TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                grading_batch_id TEXT,
                score REAL,
                feedback TEXT,
                UNIQUE(class_id, homework_id, student_id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_homework_class ON homework_submissions(class_id, homework_id)")


        # Users table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                name TEXT,
                role TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")

        # Classes table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS classes (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                teacher_id TEXT NOT NULL,
                invite_code TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_classes_teacher ON classes(teacher_id)")

        # Class enrollments
        conn.execute("""
            CREATE TABLE IF NOT EXISTS class_students (
                class_id TEXT NOT NULL,
                student_id TEXT NOT NULL,
                joined_at TEXT NOT NULL,
                PRIMARY KEY (class_id, student_id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_class_students_class ON class_students(class_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_class_students_student ON class_students(student_id)")

        # Homework table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS homeworks (
                id TEXT PRIMARY KEY,
                class_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                deadline TEXT NOT NULL,
                allow_early_grading INTEGER DEFAULT 0,
                subject TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_homeworks_class ON homeworks(class_id)")
        
        # Assistant progress tables
        conn.execute("""
            CREATE TABLE IF NOT EXISTS assistant_concepts (
                student_id TEXT NOT NULL,
                class_id TEXT NOT NULL DEFAULT '',
                concept_key TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                parent_key TEXT,
                understood INTEGER DEFAULT 0,
                last_seen_at TEXT NOT NULL,
                PRIMARY KEY (student_id, class_id, concept_key)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_assistant_concepts_student ON assistant_concepts(student_id, class_id)")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS assistant_mastery_snapshots (
                id TEXT PRIMARY KEY,
                student_id TEXT NOT NULL,
                class_id TEXT NOT NULL DEFAULT '',
                score INTEGER NOT NULL,
                level TEXT NOT NULL,
                analysis TEXT,
                evidence TEXT,
                suggestions TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_assistant_mastery_student ON assistant_mastery_snapshots(student_id, class_id, created_at)")

        
        logger.info("PostgreSQL database initialized.")


# ==================== User/Class/Homework data ====================


@dataclass
class UserRecord:
    """User record."""
    id: str
    username: str
    name: Optional[str] = None
    role: str = "student"
    password_hash: str = ""
    created_at: str = ""


@dataclass
class ClassRecord:
    """Class record."""
    id: str
    name: str
    teacher_id: str
    invite_code: str
    created_at: str = ""


@dataclass
class HomeworkRecord:
    """Homework record."""
    id: str
    class_id: str
    title: str
    description: Optional[str] = None
    deadline: str = ""
    allow_early_grading: bool = False
    subject: Optional[str] = None
    created_at: str = ""


def create_user(user: UserRecord) -> None:
    """Create a user."""
    if not user.created_at:
        user.created_at = datetime.now().isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO users (id, username, name, role, password_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user.id,
                user.username,
                user.name,
                user.role,
                user.password_hash,
                user.created_at,
            ),
        )


def get_user_by_username(username: str) -> Optional[UserRecord]:
    """Get user by username."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    if not row:
        return None
    return UserRecord(
        id=row["user_id"],
        username=row["username"],
        name=row["real_name"] or row["username"],
        role=row["user_type"],
        password_hash=row["password_hash"],
        created_at=row["created_at"],
    )


def get_user_by_id(user_id: str) -> Optional[UserRecord]:
    """Get user by id."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    if not row:
        return None
    return UserRecord(
        id=row["user_id"],
        username=row["username"],
        name=row["real_name"] or row["username"],
        role=row["user_type"],
        password_hash=row["password_hash"],
        created_at=row["created_at"],
    )


def list_user_class_ids(user_id: str) -> List[str]:
    """List class ids for a student."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT class_id FROM class_students WHERE student_id = ?",
            (user_id,),
        ).fetchall()
    return [row["class_id"] for row in rows]


def create_class_record(record: ClassRecord) -> None:
    """Create a class."""
    if not record.created_at:
        record.created_at = datetime.now().isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO classes (id, name, teacher_id, invite_code, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.name,
                record.teacher_id,
                record.invite_code,
                record.created_at,
            ),
        )


def get_class_by_id(class_id: str) -> Optional[ClassRecord]:
    """Get class by id."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM classes WHERE class_id = ?",
            (class_id,),
        ).fetchone()
    if not row:
        return None
    return ClassRecord(
        id=row["class_id"],
        name=row["class_name"],
        teacher_id=row["teacher_id"],
        invite_code=row["invite_code"],
        created_at=row["created_at"],
    )


def get_class_by_invite_code(invite_code: str) -> Optional[ClassRecord]:
    """Get class by invite code."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM classes WHERE invite_code = ?",
            (invite_code,),
        ).fetchone()
    if not row:
        return None
    return ClassRecord(
        id=row["class_id"],
        name=row["class_name"],
        teacher_id=row["teacher_id"],
        invite_code=row["invite_code"],
        created_at=row["created_at"],
    )


def list_classes_by_teacher(teacher_id: str) -> List[ClassRecord]:
    """List classes for a teacher."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM classes WHERE teacher_id = ? ORDER BY created_at DESC",
            (teacher_id,),
        ).fetchall()
    return [
        ClassRecord(
            id=row["class_id"],
            name=row["class_name"],
            teacher_id=row["teacher_id"],
            invite_code=row["invite_code"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


def list_classes_by_student(student_id: str) -> List[ClassRecord]:
    """List classes for a student."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT c.class_id, c.class_name, c.teacher_id, c.invite_code, c.created_at
            FROM classes c
            JOIN student_class_relations scr ON c.class_id = scr.class_id
            WHERE scr.student_id = ?
            ORDER BY c.created_at DESC
            """,
            (student_id,),
        ).fetchall()
    return [
        ClassRecord(
            id=row["class_id"],
            name=row["class_name"],
            teacher_id=row["teacher_id"],
            invite_code=row["invite_code"],
            created_at=str(row["created_at"]) if row["created_at"] else "",
        )
        for row in rows
    ]


def add_student_to_class(class_id: str, student_id: str) -> None:
    """Add student to class if not exists."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO class_students (class_id, student_id, joined_at)
            VALUES (?, ?, ?)
            ON CONFLICT (class_id, student_id) DO NOTHING
            """,
            (class_id, student_id, datetime.now().isoformat()),
        )


def count_class_students(class_id: str) -> int:
    """Count students in class."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS total FROM class_students WHERE class_id = ?",
            (class_id,),
        ).fetchone()
    return int(row["total"]) if row else 0


def list_class_students(class_id: str) -> List[UserRecord]:
    """List students in class."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT u.user_id, u.username, u.real_name, u.user_type, u.password_hash, u.created_at
            FROM class_students cs
            JOIN users u ON cs.student_id = u.user_id
            WHERE cs.class_id = ?
            ORDER BY u.real_name
            """,
            (class_id,),
        ).fetchall()
    return [
        UserRecord(
            id=row["user_id"],
            username=row["username"],
            name=row["real_name"],
            role=row["user_type"] or "student",
            password_hash=row["password_hash"] or "",
            created_at=str(row["created_at"]) if row["created_at"] else "",
        )
        for row in rows
    ]


def create_homework_record(record: HomeworkRecord) -> None:
    """Create homework."""
    if not record.created_at:
        record.created_at = datetime.now().isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO homeworks
            (id, class_id, title, description, deadline, allow_early_grading, subject, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.class_id,
                record.title,
                record.description,
                record.deadline,
                1 if record.allow_early_grading else 0,
                record.subject,
                record.created_at,
            ),
        )


def get_homework(homework_id: str) -> Optional[HomeworkRecord]:
    """Get homework by id."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM homeworks WHERE id = ?",
            (homework_id,),
        ).fetchone()
    if not row:
        return None
    return HomeworkRecord(
        id=row["id"],
        class_id=row["class_id"],
        title=row["title"],
        description=row["description"],
        deadline=row["deadline"],
        allow_early_grading=bool(row["allow_early_grading"]),
        subject=row["subject"],
        created_at=row["created_at"],
    )


def list_homeworks(class_id: Optional[str] = None, student_id: Optional[str] = None) -> List[HomeworkRecord]:
    """List homeworks with optional filters."""
    query = "SELECT h.* FROM homeworks h"
    params: List[Any] = []
    where = []
    if student_id:
        query += " JOIN class_students cs ON h.class_id = cs.class_id"
        where.append("cs.student_id = ?")
        params.append(student_id)
    if class_id:
        where.append("h.class_id = ?")
        params.append(class_id)
    if where:
        query += " WHERE " + " AND ".join(where)
    query += " ORDER BY h.created_at DESC"
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [
        HomeworkRecord(
            id=row["id"],
            class_id=row["class_id"],
            title=row["title"],
            description=row["description"],
            deadline=row["deadline"],
            allow_early_grading=bool(row["allow_early_grading"]),
            subject=row["subject"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


# ==================== 工作流状态操作 ====================


@dataclass
class WorkflowState:
    """工作流状态"""
    id: str
    batch_id: str
    status: str  # running, waiting_for_human, completed, failed
    pause_point: Optional[str] = None  # rubric_review, grading_review
    state_data: Optional[Dict[str, Any]] = None
    created_at: str = ""
    updated_at: str = ""


def save_workflow_state(state: WorkflowState) -> None:
    """保存工作流状态"""
    now = datetime.now().isoformat()
    state.updated_at = now
    if not state.created_at:
        state.created_at = now
    
    state_data_json = json.dumps(state.state_data) if state.state_data else None
    
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO workflow_state 
            (id, batch_id, status, pause_point, state_data, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (batch_id) DO UPDATE SET
                status = EXCLUDED.status,
                pause_point = EXCLUDED.pause_point,
                state_data = EXCLUDED.state_data,
                updated_at = EXCLUDED.updated_at
        """, (
            state.id,
            state.batch_id,
            state.status,
            state.pause_point,
            state_data_json,
            state.created_at,
            state.updated_at
        ))
    
    logger.info(f"工作流状态已保存: batch_id={state.batch_id}, status={state.status}")


def get_workflow_state(batch_id: str) -> Optional[WorkflowState]:
    """获取工作流状态"""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM workflow_state WHERE batch_id = ?",
            (batch_id,)
        ).fetchone()
        
        if not row:
            return None
        
        state_data = json.loads(row["state_data"]) if row["state_data"] else None
        
        return WorkflowState(
            id=row["id"],
            batch_id=row["batch_id"],
            status=row["status"],
            pause_point=row["pause_point"],
            state_data=state_data,
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )


def update_workflow_status(batch_id: str, status: str, pause_point: Optional[str] = None) -> None:
    """更新工作流状态"""
    now = datetime.now().isoformat()
    
    with get_connection() as conn:
        conn.execute("""
            UPDATE workflow_state 
            SET status = ?, pause_point = ?, updated_at = ?
            WHERE batch_id = ?
        """, (status, pause_point, now, batch_id))
    
    logger.info(f"工作流状态已更新: batch_id={batch_id}, status={status}")


# ==================== 批改历史操作 ====================


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


def save_grading_history(history: GradingHistory) -> None:
    """保存批改历史"""
    if not history.created_at:
        history.created_at = datetime.now().isoformat()
    
    class_ids_json = json.dumps(history.class_ids) if history.class_ids else None
    result_data_json = json.dumps(history.result_data) if history.result_data else None
    
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO grading_history 
            (id, batch_id, class_ids, created_at, completed_at, status, 
             total_students, average_score, result_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (batch_id) DO UPDATE SET
                class_ids = EXCLUDED.class_ids,
                completed_at = EXCLUDED.completed_at,
                status = EXCLUDED.status,
                total_students = EXCLUDED.total_students,
                average_score = EXCLUDED.average_score,
                result_data = EXCLUDED.result_data
        """, (
            history.id,
            history.batch_id,
            class_ids_json,
            history.created_at,
            history.completed_at,
            history.status,
            history.total_students,
            history.average_score,
            result_data_json
        ))
    
    logger.info(f"批改历史已保存: batch_id={history.batch_id}")


def get_grading_history(batch_id: str) -> Optional[GradingHistory]:
    """获取批改历史"""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM grading_history WHERE batch_id = ?",
            (batch_id,)
        ).fetchone()
        
        if not row:
            return None
        
        class_ids = json.loads(row["class_ids"]) if row["class_ids"] else None
        result_data = json.loads(row["result_data"]) if row["result_data"] else None
        
        return GradingHistory(
            id=row["id"],
            batch_id=row["batch_id"],
            status=row["status"],
            class_ids=class_ids,
            created_at=row["created_at"],
            completed_at=row["completed_at"],
            total_students=row["total_students"],
            average_score=row["average_score"],
            result_data=result_data
        )


def list_grading_history(class_id: Optional[str] = None, limit: int = 50) -> List[GradingHistory]:
    """列出批改历史"""
    with get_connection() as conn:
        if class_id:
            rows = conn.execute(
                "SELECT * FROM grading_history WHERE class_ids LIKE ? ORDER BY created_at DESC LIMIT ?",
                (f'%"{class_id}"%', limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM grading_history ORDER BY created_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
        
        histories = []
        for row in rows:
            class_ids = json.loads(row["class_ids"]) if row["class_ids"] else None
            result_data = json.loads(row["result_data"]) if row["result_data"] else None
            
            histories.append(GradingHistory(
                id=row["id"],
                batch_id=row["batch_id"],
                status=row["status"],
                class_ids=class_ids,
                created_at=row["created_at"],
                completed_at=row["completed_at"],
                total_students=row["total_students"],
                average_score=row["average_score"],
                result_data=result_data
            ))
        
        return histories


# ==================== 学生批改结果操作 ====================


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


def save_student_result(result: StudentGradingResult) -> None:
    """保存学生批改结果"""
    result_data_json = json.dumps(result.result_data) if result.result_data else None
    
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO student_grading_results 
            (id, grading_history_id, student_key, class_id, student_id,
             score, max_score, summary, self_report, result_data, 
             imported_at, revoked_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET
                score = EXCLUDED.score,
                max_score = EXCLUDED.max_score,
                summary = EXCLUDED.summary,
                self_report = EXCLUDED.self_report,
                result_data = EXCLUDED.result_data,
                imported_at = EXCLUDED.imported_at,
                revoked_at = EXCLUDED.revoked_at
        """, (
            result.id,
            result.grading_history_id,
            result.student_key,
            result.class_id,
            result.student_id,
            result.score,
            result.max_score,
            result.summary,
            result.self_report,
            result_data_json,
            result.imported_at,
            result.revoked_at
        ))


def get_student_results(grading_history_id: str) -> List[StudentGradingResult]:
    """获取批改历史的所有学生结果"""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM student_grading_results WHERE grading_history_id = ?",
            (grading_history_id,)
        ).fetchall()
        
        results = []
        for row in rows:
            result_data = json.loads(row["result_data"]) if row["result_data"] else None
            
            results.append(StudentGradingResult(
                id=row["id"],
                grading_history_id=row["grading_history_id"],
                student_key=row["student_key"],
                class_id=row["class_id"],
                student_id=row["student_id"],
                score=row["score"],
                max_score=row["max_score"],
                summary=row["summary"],
                self_report=row["self_report"],
                result_data=result_data,
                imported_at=row["imported_at"],
                revoked_at=row["revoked_at"]
            ))
        
        return results


# ==================== 作业提交操作 ====================


@dataclass
class HomeworkSubmission:
    """作业提交记录"""
    id: str
    class_id: str
    homework_id: str
    student_id: str
    student_name: Optional[str] = None
    images: Optional[List[str]] = None  # base64 或 file paths
    content: Optional[str] = None
    submission_type: str = "scan"
    page_count: int = 0
    submitted_at: str = ""
    status: str = "pending"
    grading_batch_id: Optional[str] = None
    score: Optional[float] = None
    feedback: Optional[str] = None


def save_homework_submission(submission: HomeworkSubmission) -> None:
    """保存作业提交"""
    if not submission.submitted_at:
        submission.submitted_at = datetime.now().isoformat()
    
    images_json = json.dumps(submission.images) if submission.images else None
    
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO homework_submissions 
            (id, class_id, homework_id, student_id, student_name, 
             images, content, submission_type, page_count, submitted_at, status, grading_batch_id, score, feedback)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (class_id, homework_id, student_id) DO UPDATE SET
                student_name = EXCLUDED.student_name,
                images = EXCLUDED.images,
                content = EXCLUDED.content,
                submission_type = EXCLUDED.submission_type,
                page_count = EXCLUDED.page_count,
                submitted_at = EXCLUDED.submitted_at,
                status = EXCLUDED.status,
                grading_batch_id = EXCLUDED.grading_batch_id,
                score = EXCLUDED.score,
                feedback = EXCLUDED.feedback
        """, (
            submission.id,
            submission.class_id,
            submission.homework_id,
            submission.student_id,
            submission.student_name,
            images_json,
            submission.content,
            submission.submission_type,
            submission.page_count,
            submission.submitted_at,
            submission.status,
            submission.grading_batch_id,
            submission.score,
            submission.feedback,
        ))
    
    logger.info(f"作业提交已保存: class_id={submission.class_id}, student_id={submission.student_id}")


def get_homework_submissions(class_id: str, homework_id: str) -> List[HomeworkSubmission]:
    """获取班级作业的所有学生提交"""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM homework_submissions 
               WHERE class_id = ? AND homework_id = ?
               ORDER BY student_name""",
            (class_id, homework_id)
        ).fetchall()
        
        submissions = []
        for row in rows:
            images = json.loads(row["images"]) if row["images"] else None
            
            submissions.append(HomeworkSubmission(
                id=row["id"],
                class_id=row["class_id"],
                homework_id=row["homework_id"],
                student_id=row["student_id"],
                student_name=row["student_name"],
                images=images,
                content=row["content"],
                submission_type=row["submission_type"] or ("scan" if images else "text"),
                page_count=row["page_count"],
                submitted_at=row["submitted_at"],
                status=row["status"],
                grading_batch_id=row["grading_batch_id"],
                score=row["score"],
                feedback=row["feedback"],
            ))
        
        return submissions


def list_student_submissions(student_id: str, limit: int = 5) -> List[HomeworkSubmission]:
    """List recent submissions for a student."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM homework_submissions
            WHERE student_id = ?
            ORDER BY submitted_at DESC
            LIMIT ?
            """,
            (student_id, limit),
        ).fetchall()
    submissions = []
    for row in rows:
        images = json.loads(row["images"]) if row["images"] else None
        submissions.append(HomeworkSubmission(
            id=row["id"],
            class_id=row["class_id"],
            homework_id=row["homework_id"],
            student_id=row["student_id"],
            student_name=row["student_name"],
            images=images,
            content=row["content"],
            submission_type=row["submission_type"] or ("scan" if images else "text"),
            page_count=row["page_count"],
            submitted_at=row["submitted_at"],
            status=row["status"],
            grading_batch_id=row["grading_batch_id"],
            score=row["score"],
            feedback=row["feedback"],
        ))
    return submissions


def update_homework_submission_status(
    class_id: str, 
    homework_id: str, 
    student_id: str, 
    status: str,
    grading_batch_id: Optional[str] = None
) -> None:
    """更新作业提交状态"""
    with get_connection() as conn:
        if grading_batch_id:
            conn.execute("""
                UPDATE homework_submissions 
                SET status = ?, grading_batch_id = ?
                WHERE class_id = ? AND homework_id = ? AND student_id = ?
            """, (status, grading_batch_id, class_id, homework_id, student_id))
        else:
            conn.execute("""
                UPDATE homework_submissions 
                SET status = ?
                WHERE class_id = ? AND homework_id = ? AND student_id = ?
            """, (status, class_id, homework_id, student_id))


# ==================== 作业批改更新 ====================


def upsert_homework_submission_grade(
    class_id: str,
    homework_id: str,
    student_id: str,
    student_name: Optional[str],
    score: Optional[float],
    feedback: Optional[str],
    grading_batch_id: Optional[str] = None,
) -> None:
    """Upsert homework submission score and feedback."""
    if not class_id or not homework_id or not student_id:
        return

    now = datetime.now().isoformat()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, student_name
            FROM homework_submissions
            WHERE class_id = ? AND homework_id = ? AND student_id = ?
            """,
            (class_id, homework_id, student_id),
        ).fetchone()

        if row:
            existing_name = row["student_name"]
            conn.execute(
                """
                UPDATE homework_submissions
                SET score = ?, feedback = ?, status = ?, grading_batch_id = ?, student_name = ?
                WHERE id = ?
                """,
                (
                    score,
                    feedback,
                    "graded",
                    grading_batch_id,
                    student_name or existing_name,
                    row["id"],
                ),
            )
            return

        submission_id = str(uuid.uuid4())[:8]
        conn.execute(
            """
            INSERT INTO homework_submissions
            (id, class_id, homework_id, student_id, student_name,
             images, content, submission_type, page_count, submitted_at, status, grading_batch_id, score, feedback)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                submission_id,
                class_id,
                homework_id,
                student_id,
                student_name,
                None,
                None,
                "scan",
                0,
                now,
                "graded",
                grading_batch_id,
                score,
                feedback,
            ),
        )


# ==================== Assistant progress ====================


def _normalize_class_id(class_id: Optional[str]) -> str:
    if class_id and class_id.strip():
        return class_id.strip()
    return ""


def _concept_key(name: str, parent_key: Optional[str]) -> str:
    normalized = f"{parent_key or 'root'}::{name.strip().lower()}"
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()
    return digest[:16]


def upsert_assistant_concepts(
    student_id: str,
    class_id: Optional[str],
    concepts: List[Dict[str, Any]],
) -> None:
    if not student_id or not concepts:
        return
    normalized_class = _normalize_class_id(class_id)
    now = datetime.now().isoformat()
    with get_connection() as conn:
        for concept in concepts:
            name = (concept.get("name") or "").strip()
            if not name:
                continue
            parent_key = concept.get("parent_key")
            concept_key = concept.get("concept_key") or _concept_key(name, parent_key)
            description = concept.get("description") or ""
            understood = 1 if concept.get("understood") else 0
            conn.execute(
                """
                INSERT INTO assistant_concepts
                (student_id, class_id, concept_key, name, description, parent_key, understood, last_seen_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (student_id, class_id, concept_key) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = CASE
                        WHEN EXCLUDED.description IS NULL OR EXCLUDED.description = ''
                        THEN assistant_concepts.description
                        ELSE EXCLUDED.description
                    END,
                    parent_key = EXCLUDED.parent_key,
                    understood = EXCLUDED.understood,
                    last_seen_at = EXCLUDED.last_seen_at
                """,
                (
                    student_id,
                    normalized_class,
                    concept_key,
                    name,
                    description,
                    parent_key,
                    understood,
                    now,
                ),
            )


def list_assistant_concepts(student_id: str, class_id: Optional[str]) -> List[Dict[str, Any]]:
    normalized_class = _normalize_class_id(class_id)
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT concept_key, name, description, parent_key, understood
            FROM assistant_concepts
            WHERE student_id = ? AND class_id = ?
            ORDER BY name ASC
            """,
            (student_id, normalized_class),
        ).fetchall()
    return [
        {
            "concept_key": row["concept_key"],
            "name": row["name"],
            "description": row["description"] or "",
            "parent_key": row["parent_key"],
            "understood": bool(row["understood"]),
        }
        for row in rows
    ]


def save_assistant_mastery_snapshot(
    student_id: str,
    class_id: Optional[str],
    mastery: Dict[str, Any],
) -> None:
    if not student_id or not mastery:
        return
    normalized_class = _normalize_class_id(class_id)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO assistant_mastery_snapshots
            (id, student_id, class_id, score, level, analysis, evidence, suggestions, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                student_id,
                normalized_class,
                int(mastery.get("score") or 0),
                mastery.get("level") or "developing",
                mastery.get("analysis") or "",
                json.dumps(mastery.get("evidence") or []),
                json.dumps(mastery.get("suggestions") or []),
                datetime.now().isoformat(),
            ),
        )


def list_assistant_mastery_snapshots(
    student_id: str,
    class_id: Optional[str],
    limit: int = 6,
) -> List[Dict[str, Any]]:
    normalized_class = _normalize_class_id(class_id)
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT score, level, analysis, evidence, suggestions, created_at
            FROM assistant_mastery_snapshots
            WHERE student_id = ? AND class_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (student_id, normalized_class, limit),
        ).fetchall()
    snapshots: List[Dict[str, Any]] = []
    for row in reversed(rows):
        snapshots.append(
            {
                "score": int(row["score"] or 0),
                "level": row["level"],
                "analysis": row["analysis"] or "",
                "evidence": json.loads(row["evidence"]) if row["evidence"] else [],
                "suggestions": json.loads(row["suggestions"]) if row["suggestions"] else [],
                "created_at": row["created_at"],
            }
        )
    return snapshots

# 初始化数据库
try:
    init_db()
except Exception as e:
    logger.warning(f"PostgreSQL 数据库初始化失败，将在首次使用时重试: {e}")

