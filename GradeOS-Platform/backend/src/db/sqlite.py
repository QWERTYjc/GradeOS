"""SQLite 状态持久化模块

用于存储工作流暂停态和批改结果。
支持：
1. 工作流状态持久化
2. 批改历史记录
3. 学生批改结果
"""

import os
import json
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict
from contextlib import contextmanager


logger = logging.getLogger(__name__)

# 数据库文件路径
DB_PATH = Path(os.getenv("GRADING_DB_PATH", "data/grading.db"))


def ensure_db_dir():
    """确保数据库目录存在"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_connection():
    """获取数据库连接（上下文管理器）"""
    ensure_db_dir()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
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
                page_count INTEGER DEFAULT 0,
                submitted_at TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                grading_batch_id TEXT,
                UNIQUE(class_id, homework_id, student_id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_homework_class ON homework_submissions(class_id, homework_id)")
        
        logger.info(f"SQLite 数据库已初始化: {DB_PATH}")


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
            INSERT OR REPLACE INTO workflow_state 
            (id, batch_id, status, pause_point, state_data, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
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
            INSERT OR REPLACE INTO grading_history 
            (id, batch_id, class_ids, created_at, completed_at, status, 
             total_students, average_score, result_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            INSERT OR REPLACE INTO student_grading_results 
            (id, grading_history_id, student_key, class_id, student_id,
             score, max_score, summary, self_report, result_data, 
             imported_at, revoked_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
    page_count: int = 0
    submitted_at: str = ""
    status: str = "pending"
    grading_batch_id: Optional[str] = None


def save_homework_submission(submission: HomeworkSubmission) -> None:
    """保存作业提交"""
    if not submission.submitted_at:
        submission.submitted_at = datetime.now().isoformat()
    
    images_json = json.dumps(submission.images) if submission.images else None
    
    with get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO homework_submissions 
            (id, class_id, homework_id, student_id, student_name, 
             images, page_count, submitted_at, status, grading_batch_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            submission.id,
            submission.class_id,
            submission.homework_id,
            submission.student_id,
            submission.student_name,
            images_json,
            submission.page_count,
            submission.submitted_at,
            submission.status,
            submission.grading_batch_id
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
                page_count=row["page_count"],
                submitted_at=row["submitted_at"],
                status=row["status"],
                grading_batch_id=row["grading_batch_id"]
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


# 初始化数据库
try:
    init_db()
except Exception as e:
    logger.warning(f"SQLite 数据库初始化失败，将在首次使用时重试: {e}")

