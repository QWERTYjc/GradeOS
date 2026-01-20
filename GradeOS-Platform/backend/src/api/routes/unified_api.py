"""
GradeOS 统一 API 路由
整合所有子系统的 API 接口
"""

import asyncio
import base64
import json
import logging
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from pydantic import BaseModel

from src.api.dependencies import get_orchestrator
from src.orchestration.base import Orchestrator
from src.api.routes.batch_langgraph import _format_results_for_frontend
from src.db.sqlite import (
    HomeworkSubmission,
    save_homework_submission,
    list_grading_history as list_sqlite_grading_history,
    get_student_results as get_sqlite_student_results,
    get_connection as get_sqlite_connection,
    UserRecord,
    ClassRecord,
    HomeworkRecord,
    create_user,
    get_user_by_username,
    get_user_by_id,
    list_user_class_ids,
    create_class_record,
    get_class_by_id,
    get_class_by_invite_code,
    list_classes_by_teacher,
    list_classes_by_student,
    add_student_to_class,
    count_class_students,
    list_class_students,
    create_homework_record,
    get_homework,
    list_homeworks,
    get_homework_submissions,
    list_student_submissions,
    update_homework_submission_status,
)
from src.services.llm_client import LLMMessage, get_llm_client
from src.utils.image import to_jpeg_bytes
from src.utils.auth import hash_password, verify_password

logger = logging.getLogger(__name__)

router = APIRouter()

# 存储路径配置
UPLOAD_DIR = Path("./storage/scans")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ============ 数据模型 ============

class RegisterRequest(BaseModel):
    """用户注册"""
    username: str
    password: str
    role: str = "teacher"


class LoginRequest(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    user_id: str
    username: str
    name: str
    user_type: str  # student/teacher/admin
    class_ids: List[str] = []

class ClassCreate(BaseModel):
    name: str
    teacher_id: str

class ClassResponse(BaseModel):
    class_id: str
    class_name: str
    teacher_id: str
    invite_code: str
    student_count: int

class StudentInfo(BaseModel):
    """学生信息模型"""
    id: str
    name: str
    username: str

class JoinClassRequest(BaseModel):
    code: str
    student_id: str

class HomeworkCreate(BaseModel):
    class_id: str
    title: str
    description: str
    deadline: str
    allow_early_grading: bool = False

class HomeworkResponse(BaseModel):
    homework_id: str
    class_id: str
    class_name: Optional[str]
    title: str
    description: str
    deadline: str
    allow_early_grading: bool = False
    created_at: str

class SubmissionCreate(BaseModel):
    homework_id: str
    student_id: str
    student_name: str
    content: str

class ScanSubmissionCreate(BaseModel):
    """扫描提交请求"""
    homework_id: str
    student_id: str
    student_name: str
    images: List[str]  # Base64 编码的图片列表

class SubmissionResponse(BaseModel):
    submission_id: str
    homework_id: str
    student_id: str
    student_name: str
    submitted_at: str
    status: str
    score: Optional[float]
    feedback: Optional[str]


class GradingStudentMapping(BaseModel):
    student_key: str
    student_id: str


class GradingImportTarget(BaseModel):
    class_id: str
    student_ids: List[str]
    assignment_id: Optional[str] = None
    student_mapping: Optional[List[GradingStudentMapping]] = None


class GradingImportRequest(BaseModel):
    batch_id: str
    targets: List[GradingImportTarget]


class AssistantMessage(BaseModel):
    role: str
    content: str


class AssistantChatRequest(BaseModel):
    student_id: str
    message: str
    class_id: Optional[str] = None
    history: Optional[List[AssistantMessage]] = None


class AssistantChatResponse(BaseModel):
    content: str
    model: Optional[str] = None
    usage: Optional[Dict[str, int]] = None


class GradingImportRecord(BaseModel):
    import_id: str
    batch_id: str
    class_id: str
    class_name: Optional[str] = None
    assignment_id: Optional[str] = None
    assignment_title: Optional[str] = None
    student_count: int
    status: str
    created_at: str
    revoked_at: Optional[str] = None


class GradingImportItem(BaseModel):
    item_id: str
    import_id: str
    batch_id: str
    class_id: str
    student_id: str
    student_name: str
    status: str
    created_at: str
    revoked_at: Optional[str] = None
    result: Optional[dict] = None


class GradingHistoryResponse(BaseModel):
    records: List[GradingImportRecord]


class GradingHistoryDetailResponse(BaseModel):
    record: GradingImportRecord
    items: List[GradingImportItem]


class GradingRevokeRequest(BaseModel):
    reason: Optional[str] = None

class ErrorAnalysisRequest(BaseModel):
    subject: str
    question: str
    student_answer: str
    student_id: Optional[str] = None

class ErrorAnalysisResponse(BaseModel):
    analysis_id: str
    error_type: str
    error_severity: str
    root_cause: str
    knowledge_gaps: List[dict]
    detailed_analysis: dict
    recommendations: dict

class DiagnosisReportResponse(BaseModel):
    student_id: str
    report_period: str
    overall_assessment: dict
    progress_trend: List[dict]
    knowledge_map: List[dict]
    error_patterns: dict
    personalized_insights: List[str]


# ============ Runtime tasks ============

HOMEWORK_GRADING_TASKS: Dict[str, asyncio.Task] = {}


def _parse_deadline(deadline: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(deadline)
    except ValueError:
        parsed = datetime.strptime(deadline, "%Y-%m-%d")
    if parsed.hour == 0 and parsed.minute == 0 and parsed.second == 0:
        parsed = parsed.replace(hour=23, minute=59, second=59)
    return parsed


def _get_student_map(class_id: str) -> Dict[str, str]:
    students = list_class_students(class_id)
    return {student.id: student.name or student.username or student.id for student in students}


def _extract_question_results(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    for key in ("questionResults", "question_results", "questions", "questionDetails", "question_details"):
        values = result.get(key)
        if isinstance(values, list) and values:
            return values
    return []


def _parse_llm_json(text: str) -> Dict[str, Any]:
    """Parse JSON object from LLM response."""
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def _build_student_context(student_id: str, class_id: Optional[str] = None) -> Dict[str, Any]:
    class_ids: List[str] = []
    class_names: Dict[str, str] = {}

    for cls in list_classes_by_student(student_id):
        class_ids.append(cls.id)
        class_names[cls.id] = cls.name

    if class_id and class_id not in class_ids:
        class_ids.append(class_id)
    if class_id and class_id not in class_names:
        class_record = get_class_by_id(class_id)
        if class_record:
            class_names[class_id] = class_record.name

    wrong_samples = []
    total_questions = 0
    total_wrong = 0
    total_score = 0.0
    total_max = 0.0

    with get_sqlite_connection() as conn:
        if class_id:
            rows = conn.execute(
                "SELECT * FROM student_grading_results WHERE student_id = ? AND class_id = ?",
                (student_id, class_id),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM student_grading_results WHERE student_id = ?",
                (student_id,),
            ).fetchall()

    for row in rows:
        result_data = row["result_data"]
        if isinstance(result_data, str):
            try:
                result = json.loads(result_data)
            except Exception:
                result = {}
        else:
            result = result_data or {}

        questions = _extract_question_results(result)
        for q in questions:
            score = float(q.get("score", 0) or 0)
            max_score = float(q.get("maxScore") or q.get("max_score") or 0)
            if max_score <= 0:
                continue
            total_questions += 1
            total_score += score
            total_max += max_score
            if score < max_score:
                total_wrong += 1
                if len(wrong_samples) < 8:
                    wrong_samples.append({
                        "question_id": str(q.get("questionId") or q.get("question_id") or ""),
                        "score": score,
                        "max_score": max_score,
                        "feedback": q.get("feedback") or "",
                        "student_answer": q.get("studentAnswer") or q.get("student_answer") or "",
                        "evidence": (q.get("scoring_point_results") or q.get("scoringPointResults") or [])[:2],
                    })

    submissions = []
    for submission in list_student_submissions(student_id, limit=5):
        homework = get_homework(submission.homework_id)
        submissions.append({
            "homework_id": submission.homework_id,
            "title": homework.title if homework else None,
            "status": submission.status,
            "submitted_at": submission.submitted_at,
            "score": submission.score,
        })

    return {
        "student_id": student_id,
        "class_ids": class_ids,
        "class_names": class_names,
        "grading_summary": {
            "total_questions": total_questions,
            "wrong_questions": total_wrong,
            "total_score": total_score,
            "total_max": total_max,
        },
        "wrong_question_samples": wrong_samples,
        "recent_submissions": submissions,
    }


async def _get_formatted_results(batch_id: str, orchestrator: Orchestrator) -> List[Dict[str, Any]]:
    run_id = f"batch_grading_{batch_id}"
    run_info = await orchestrator.get_run_info(run_id)
    if not run_info:
        raise HTTPException(status_code=404, detail="批改批次不存在")
    state = run_info.state or {}
    student_results = state.get("student_results", [])
    if not student_results:
        final_output = await orchestrator.get_final_output(run_id)
        if final_output:
            student_results = final_output.get("student_results", [])
    return _format_results_for_frontend(student_results)


async def _trigger_homework_grading(homework_id: str, orchestrator: Orchestrator) -> Optional[str]:
    homework = get_homework(homework_id)
    if not homework:
        return None

    class_id = homework.class_id
    submissions = get_homework_submissions(class_id, homework_id)
    if not submissions:
        return None
    if any(submission.grading_batch_id for submission in submissions):
        return None

    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=400, detail="未配置 LLM_API_KEY/OPENROUTER_API_KEY")

    answer_images: List[bytes] = []
    manual_boundaries: List[Dict[str, Any]] = []
    page_cursor = 0
    for submission in submissions:
        images = submission.images or []
        if not images:
            continue
        pages = list(range(page_cursor, page_cursor + len(images)))
        manual_boundaries.append({
            "student_id": submission.student_id,
            "student_key": submission.student_name or submission.student_id,
            "pages": pages,
        })
        for img in images:
            img_data = img
            if isinstance(img_data, str):
                if "," in img_data and img_data.startswith("data:"):
                    img_data = img_data.split(",", 1)[1]
                try:
                    answer_images.append(base64.b64decode(img_data))
                    continue
                except Exception:
                    pass
                try:
                    path = Path(img_data)
                    if path.exists():
                        answer_images.append(path.read_bytes())
                        continue
                except Exception:
                    continue
            elif isinstance(img_data, (bytes, bytearray)):
                answer_images.append(bytes(img_data))
        page_cursor += len(images)

    if not answer_images:
        return None

    batch_id = str(uuid.uuid4())
    payload = {
        "batch_id": batch_id,
        "exam_id": homework_id,
        "temp_dir": "",
        "rubric_images": [],
        "answer_images": answer_images,
        "api_key": api_key,
        "inputs": {
            "rubric": "rubric_content",
            "auto_identify": False,
            "manual_boundaries": manual_boundaries,
            "expected_students": count_class_students(class_id) or len(manual_boundaries),
        },
    }

    await orchestrator.start_run(
        graph_name="batch_grading",
        payload=payload,
        idempotency_key=batch_id,
    )

    for submission in submissions:
        update_homework_submission_status(
            class_id=class_id,
            homework_id=homework_id,
            student_id=submission.student_id,
            status="queued",
            grading_batch_id=batch_id,
        )
    return batch_id


async def _schedule_deadline_grading(homework_id: str, deadline: datetime, orchestrator: Orchestrator) -> None:
    delay = (deadline - datetime.utcnow()).total_seconds()
    if delay > 0:
        await asyncio.sleep(delay)
    await _trigger_homework_grading(homework_id, orchestrator)


async def _maybe_trigger_grading(homework_id: str, orchestrator: Orchestrator) -> None:
    homework = get_homework(homework_id)
    if not homework:
        return
    submissions = get_homework_submissions(homework.class_id, homework_id)
    if any(submission.grading_batch_id for submission in submissions):
        return
    deadline = _parse_deadline(homework.deadline)
    allow_early = homework.allow_early_grading
    total_students = count_class_students(homework.class_id)

    if allow_early and total_students > 0 and len(submissions) >= total_students:
        await _trigger_homework_grading(homework_id, orchestrator)
        task = HOMEWORK_GRADING_TASKS.pop(homework_id, None)
        if task:
            task.cancel()
        return

    if not allow_early and datetime.utcnow() >= deadline:
        await _trigger_homework_grading(homework_id, orchestrator)

# ============ 认证接口 ============

@router.post("/auth/register", response_model=UserResponse, tags=["认证"])
async def register(request: RegisterRequest):
    """用户注册（Mock）"""
    username = request.username.strip()
    if not username or not request.password:
        raise HTTPException(status_code=400, detail="Invalid registration info")

    existing = get_user_by_username(username)
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")

    role = request.role if request.role in ("teacher", "student") else "teacher"
    user_id = f"{role[0]}-{uuid.uuid4().hex[:8]}"
    user = UserRecord(
        id=user_id,
        username=username,
        name=username,
        role=role,
        password_hash=hash_password(request.password),
    )
    create_user(user)

    return UserResponse(
        user_id=user.id,
        username=user.username,
        name=user.name or user.username,
        user_type=user.role,
        class_ids=[],
    )


@router.post("/auth/login", response_model=UserResponse, tags=["Authentication"])
async def login(request: LoginRequest):
    """User login."""
    user = get_user_by_username(request.username)
    if user and verify_password(request.password, user.password_hash):
        class_ids = list_user_class_ids(user.id)
        return UserResponse(
            user_id=user.id,
            username=user.username,
            name=user.name or user.username,
            user_type=user.role,
            class_ids=class_ids,
        )
    raise HTTPException(status_code=401, detail="Invalid credentials")


@router.get("/user/info", response_model=UserResponse, tags=["认证"])
async def get_user_info(user_id: str):
    """获取用户信息"""
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    class_ids = list_user_class_ids(user.id)
    return UserResponse(
        user_id=user.id,
        username=user.username,
        name=user.name or user.username,
        user_type=user.role,
        class_ids=class_ids,
    )


# ============ 班级管理接口 ============

@router.get("/class/my", response_model=List[ClassResponse], tags=["班级管理"])
async def get_my_classes(student_id: str):
    """获取学生加入的班级"""
    classes: List[ClassResponse] = []
    for class_record in list_classes_by_student(student_id):
        classes.append(ClassResponse(
            class_id=class_record.id,
            class_name=class_record.name,
            teacher_id=class_record.teacher_id,
            invite_code=class_record.invite_code,
            student_count=count_class_students(class_record.id),
        ))
    return classes


@router.post("/class/join", tags=["Class Management"])
async def join_class(request: JoinClassRequest):
    """Join a class."""
    class_info = get_class_by_invite_code(request.code)
    if not class_info:
        raise HTTPException(status_code=404, detail="Class not found")
    student = get_user_by_id(request.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    add_student_to_class(class_info.id, student.id)
    return {
        "success": True,
        "class": {
            "id": class_info.id,
            "name": class_info.name,
        },
    }


@router.get("/teacher/classes", response_model=List[ClassResponse], tags=["班级管理"])
async def get_teacher_classes(teacher_id: str):
    """获取教师的班级列表"""
    classes: List[ClassResponse] = []
    for class_record in list_classes_by_teacher(teacher_id):
        classes.append(ClassResponse(
            class_id=class_record.id,
            class_name=class_record.name,
            teacher_id=class_record.teacher_id,
            invite_code=class_record.invite_code,
            student_count=count_class_students(class_record.id),
        ))
    return classes


@router.post("/teacher/classes", response_model=ClassResponse, tags=["班级管理"])
async def create_class(request: ClassCreate):
    """创建班级"""
    import random
    import string
    invite_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    
    teacher = get_user_by_id(request.teacher_id)
    if not teacher:
        raise HTTPException(status_code=404, detail="教师不存在")

    class_id = str(uuid.uuid4())[:8]
    record = ClassRecord(
        id=class_id,
        name=request.name,
        teacher_id=request.teacher_id,
        invite_code=invite_code,
    )
    create_class_record(record)
    return ClassResponse(
        class_id=record.id,
        class_name=record.name,
        teacher_id=record.teacher_id,
        invite_code=record.invite_code,
        student_count=0,
    )


@router.get("/class/students", tags=["班级管理"])
async def get_class_students(class_id: str):
    """获取班级学生列表"""
    students = list_class_students(class_id)
    with get_sqlite_connection() as conn:
        total_homeworks_row = conn.execute(
            "SELECT COUNT(*) AS total FROM homeworks WHERE class_id = ?",
            (class_id,),
        ).fetchone()
        total_homeworks = int(total_homeworks_row["total"]) if total_homeworks_row else 0

        submission_rows = conn.execute(
            """
            SELECT student_id, COUNT(*) AS submitted_count
            FROM homework_submissions
            WHERE class_id = ?
            GROUP BY student_id
            """,
            (class_id,),
        ).fetchall()
        submission_counts = {row["student_id"]: int(row["submitted_count"]) for row in submission_rows}

        score_rows = conn.execute(
            """
            SELECT student_id, score, max_score
            FROM student_grading_results
            WHERE class_id = ? AND score IS NOT NULL AND max_score IS NOT NULL AND max_score > 0
            """,
            (class_id,),
        ).fetchall()

    score_totals: Dict[str, float] = {}
    score_counts: Dict[str, int] = {}
    for row in score_rows:
        student_id = row["student_id"]
        score = row["score"]
        max_score = row["max_score"]
        if student_id is None or score is None or max_score is None:
            continue
        ratio = float(score) / float(max_score)
        score_totals[student_id] = score_totals.get(student_id, 0.0) + ratio
        score_counts[student_id] = score_counts.get(student_id, 0) + 1

    return [
        {
            "id": student.id,
            "name": student.name or student.username or student.id,
            "username": student.username,
            "avgScore": round((score_totals.get(student.id, 0.0) / score_counts.get(student.id, 1)) * 100, 1)
            if score_counts.get(student.id)
            else None,
            "submissionRate": round((submission_counts.get(student.id, 0) / total_homeworks) * 100, 1)
            if total_homeworks > 0
            else None,
        }
        for student in students
    ]


# ============ 作业管理接口 ============

@router.get("/homework/list", response_model=List[HomeworkResponse], tags=["作业管理"])
async def get_homework_list(class_id: Optional[str] = None, student_id: Optional[str] = None):
    """获取作业列表"""
    records = list_homeworks(class_id=class_id, student_id=student_id)
    responses = []
    for record in records:
        class_info = get_class_by_id(record.class_id)
        responses.append(HomeworkResponse(
            homework_id=record.id,
            class_id=record.class_id,
            class_name=class_info.name if class_info else None,
            title=record.title,
            description=record.description or "",
            deadline=record.deadline,
            allow_early_grading=record.allow_early_grading,
            created_at=record.created_at,
        ))
    return responses


@router.get("/homework/detail/{homework_id}", response_model=HomeworkResponse, tags=["作业管理"])
async def get_homework_detail(homework_id: str):
    """获取作业详情"""
    record = get_homework(homework_id)
    if not record:
        raise HTTPException(status_code=404, detail="作业不存在")
    class_info = get_class_by_id(record.class_id)
    return HomeworkResponse(
        homework_id=record.id,
        class_id=record.class_id,
        class_name=class_info.name if class_info else None,
        title=record.title,
        description=record.description or "",
        deadline=record.deadline,
        allow_early_grading=record.allow_early_grading,
        created_at=record.created_at,
    )


@router.post("/homework/create", response_model=HomeworkResponse, tags=["作业管理"])
async def create_homework(
    request: HomeworkCreate,
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    """创建作业"""
    class_info = get_class_by_id(request.class_id)
    if not class_info:
        raise HTTPException(status_code=404, detail="班级不存在")

    homework_id = str(uuid.uuid4())[:8]
    record = HomeworkRecord(
        id=homework_id,
        class_id=request.class_id,
        title=request.title,
        description=request.description,
        deadline=request.deadline,
        allow_early_grading=request.allow_early_grading,
        created_at=datetime.now().isoformat(),
    )
    create_homework_record(record)

    deadline_dt = _parse_deadline(request.deadline)
    if orchestrator:
        task = asyncio.create_task(_schedule_deadline_grading(homework_id, deadline_dt, orchestrator))
        HOMEWORK_GRADING_TASKS[homework_id] = task

    return HomeworkResponse(
        homework_id=record.id,
        class_id=record.class_id,
        class_name=class_info.name,
        title=record.title,
        description=record.description or "",
        deadline=record.deadline,
        allow_early_grading=record.allow_early_grading,
        created_at=record.created_at,
    )


@router.post("/homework/submit", response_model=SubmissionResponse, tags=["作业管理"])
async def submit_homework(request: SubmissionCreate):
    """提交作业（文本）"""
    homework = get_homework(request.homework_id)
    if not homework:
        raise HTTPException(status_code=404, detail="作业不存在")

    submission_id = str(uuid.uuid4())[:8]
    submission_record = HomeworkSubmission(
        id=submission_id,
        class_id=homework.class_id,
        homework_id=request.homework_id,
        student_id=request.student_id,
        student_name=request.student_name,
        content=request.content,
        submission_type="text",
        page_count=0,
        submitted_at=datetime.now().isoformat(),
        status="submitted",
    )
    save_homework_submission(submission_record)

    return SubmissionResponse(
        submission_id=submission_id,
        homework_id=request.homework_id,
        student_id=request.student_id,
        student_name=request.student_name,
        submitted_at=submission_record.submitted_at,
        status="submitted",
        score=None,
        feedback=None,
    )


@router.post("/homework/submit-scan", response_model=SubmissionResponse, tags=["作业管理"])
async def submit_scan_homework(
    request: ScanSubmissionCreate,
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    """
    提交扫描作业（图片）
    
    接收 Base64 编码的图片列表，保存到本地存储，并触发 AI 批改
    """
    homework = get_homework(request.homework_id)
    if not homework:
        raise HTTPException(status_code=404, detail="作业不存在")

    submission_id = str(uuid.uuid4())[:8]
    
    # 创建提交目录
    submission_dir = UPLOAD_DIR / submission_id
    submission_dir.mkdir(parents=True, exist_ok=True)
    
    saved_paths = []
    
    images_bytes: List[bytes] = []
    stored_images: List[str] = []
    # 保存图片
    for idx, img_data in enumerate(request.images):
        try:
            # 移除 data:image/xxx;base64, 前缀
            if ',' in img_data:
                img_data = img_data.split(',')[1]
            
            # 解码并保存
            img_bytes = base64.b64decode(img_data)
            img_bytes = to_jpeg_bytes(img_bytes)
            file_path = submission_dir / f"page_{idx + 1}.jpg"
            
            with open(file_path, 'wb') as f:
                f.write(img_bytes)
            
            saved_paths.append(str(file_path))
            images_bytes.append(img_bytes)
            stored_images.append(f"data:image/jpeg;base64,{base64.b64encode(img_bytes).decode('utf-8')}")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"图片 {idx + 1} 处理失败: {str(e)}")
    
    submission_record = HomeworkSubmission(
        id=submission_id,
        class_id=homework.class_id,
        homework_id=request.homework_id,
        student_id=request.student_id,
        student_name=request.student_name,
        images=stored_images,
        submission_type="scan",
        page_count=len(stored_images),
        submitted_at=datetime.now().isoformat(),
        status="submitted",
    )
    try:
        save_homework_submission(submission_record)
    except Exception as exc:
        logger.warning(f"保存作业提交到 SQLite 失败: {exc}")

    if orchestrator:
        await _maybe_trigger_grading(request.homework_id, orchestrator)

    return SubmissionResponse(
        submission_id=submission_id,
        homework_id=request.homework_id,
        student_id=request.student_id,
        student_name=request.student_name,
        submitted_at=submission_record.submitted_at,
        status="submitted",
        score=None,
        feedback=None,
    )


@router.get("/homework/submissions", response_model=List[SubmissionResponse], tags=["作业管理"])
async def get_submissions(homework_id: str):
    """获取作业提交列表"""
    homework = get_homework(homework_id)
    if not homework:
        raise HTTPException(status_code=404, detail="作业不存在")
    submissions = get_homework_submissions(homework.class_id, homework_id)
    return [
        SubmissionResponse(
            submission_id=submission.id,
            homework_id=submission.homework_id,
            student_id=submission.student_id,
            student_name=submission.student_name or submission.student_id,
            submitted_at=submission.submitted_at,
            status=submission.status,
            score=submission.score,
            feedback=submission.feedback,
        )
        for submission in submissions
    ]


# ============ 批改结果导入与历史 ============

@router.post("/grading/import", response_model=GradingHistoryResponse, tags=["批改历史"])
async def import_grading_results(
    request: GradingImportRequest,
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    """导入批改结果到班级"""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="编排器未初始化")

    formatted_results = await _get_formatted_results(request.batch_id, orchestrator)
    results_by_key: Dict[str, Dict[str, Any]] = {}
    for result in formatted_results:
        for key in [
            result.get("studentName"),
            result.get("student_name"),
            result.get("studentKey"),
            result.get("student_key"),
            result.get("studentId"),
            result.get("student_id"),
        ]:
            if key:
                results_by_key[str(key)] = result

    records: List[GradingImportRecord] = []
    now = datetime.utcnow().isoformat()

    for target in request.targets:
        if not target.student_ids:
            raise HTTPException(status_code=400, detail="必须选择学生")

        class_info = get_class_by_id(target.class_id)
        if not class_info:
            raise HTTPException(status_code=404, detail="班级不存在")

        student_map = _get_student_map(target.class_id)
        mapping_by_id = {m.student_id: m.student_key for m in (target.student_mapping or [])}
        assignment_title = None
        if target.assignment_id:
            assignment = get_homework(target.assignment_id)
            assignment_title = assignment.title if assignment else None

        import_id = str(uuid.uuid4())[:8]
        record = {
            "import_id": import_id,
            "batch_id": request.batch_id,
            "class_id": target.class_id,
            "class_name": class_info.name,
            "assignment_id": target.assignment_id,
            "assignment_title": assignment_title,
            "student_count": len(target.student_ids),
            "status": "imported",
            "created_at": now,
            "revoked_at": None,
        }
        with get_sqlite_connection() as conn:
            conn.execute(
                """
                INSERT INTO grading_imports
                (id, batch_id, class_id, assignment_id, created_at, status, revoked_at, student_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    import_id,
                    request.batch_id,
                    target.class_id,
                    target.assignment_id,
                    now,
                    "imported",
                    None,
                    len(target.student_ids),
                ),
            )

        for student_id in target.student_ids:
            student_name = student_map.get(student_id, student_id)
            student_key = mapping_by_id.get(student_id)
            result = None
            if student_key:
                result = results_by_key.get(student_key)
            if not result:
                result = results_by_key.get(student_name) or results_by_key.get(student_id)
            item_id = str(uuid.uuid4())[:8]
            result_payload = json.dumps(result) if result else None
            with get_sqlite_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO grading_import_items
                    (id, import_id, batch_id, class_id, student_id, student_name, status, created_at, revoked_at, result_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item_id,
                        import_id,
                        request.batch_id,
                        target.class_id,
                        student_id,
                        student_name,
                        "imported",
                        now,
                        None,
                        result_payload,
                    ),
                )

        records.append(GradingImportRecord(**record))

    return GradingHistoryResponse(records=records)


@router.get("/grading/history", response_model=GradingHistoryResponse, tags=["批改历史"])
async def get_grading_history(
    class_id: Optional[str] = None,
    assignment_id: Optional[str] = None,
):
    """获取批改历史列表"""
    records: List[Dict[str, Any]] = []

    try:
        sqlite_histories = list_sqlite_grading_history(class_id=class_id, limit=50)
        for history in sqlite_histories:
            class_ids = history.class_ids or []
            target_class_id = class_id or (class_ids[0] if class_ids else None)
            if class_id and class_id not in class_ids:
                continue
            result_meta = history.result_data or {}
            assignment_id_value = result_meta.get("homework_id") or result_meta.get("assignment_id")
            if assignment_id and assignment_id_value != assignment_id:
                continue
            class_info = get_class_by_id(target_class_id) if target_class_id else None
            assignment_title = None
            if assignment_id_value:
                assignment = get_homework(assignment_id_value)
                assignment_title = assignment.title if assignment else None
            records.append({
                "import_id": history.id,
                "batch_id": history.batch_id,
                "class_id": target_class_id or "",
                "class_name": class_info.name if class_info else None,
                "assignment_id": assignment_id_value,
                "assignment_title": assignment_title,
                "student_count": history.total_students,
                "status": history.status,
                "created_at": history.created_at,
                "revoked_at": None,
            })
    except Exception as exc:
        logger.warning(f"SQLite 批改历史读取失败: {exc}")

    try:
        with get_sqlite_connection() as conn:
            if class_id:
                rows = conn.execute(
                    "SELECT * FROM grading_imports WHERE class_id = ? ORDER BY created_at DESC",
                    (class_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM grading_imports ORDER BY created_at DESC"
                ).fetchall()
        for row in rows:
            if assignment_id and row["assignment_id"] != assignment_id:
                continue
            class_info = get_class_by_id(row["class_id"])
            assignment_title = None
            if row["assignment_id"]:
                assignment = get_homework(row["assignment_id"])
                assignment_title = assignment.title if assignment else None
            records.append({
                "import_id": row["id"],
                "batch_id": row["batch_id"],
                "class_id": row["class_id"],
                "class_name": class_info.name if class_info else None,
                "assignment_id": row["assignment_id"],
                "assignment_title": assignment_title,
                "student_count": row["student_count"] or 0,
                "status": row["status"],
                "created_at": row["created_at"],
                "revoked_at": row["revoked_at"],
            })
    except Exception as exc:
        logger.warning(f"SQLite 导入记录读取失败: {exc}")

    records = sorted(records, key=lambda item: item.get("created_at") or "", reverse=True)
    return GradingHistoryResponse(records=[GradingImportRecord(**record) for record in records])


@router.get("/grading/history/{import_id}", response_model=GradingHistoryDetailResponse, tags=["Grading History"])
async def get_grading_history_detail(import_id: str):
    """Get grading history detail."""
    try:
        with get_sqlite_connection() as conn:
            row = conn.execute("SELECT * FROM grading_history WHERE id = ?", (import_id,)).fetchone()
        if row:
            class_ids = json.loads(row["class_ids"]) if row["class_ids"] else []
            result_data = json.loads(row["result_data"]) if row["result_data"] else {}
            class_id = class_ids[0] if class_ids else ""
            class_info = get_class_by_id(class_id) if class_id else None
            assignment_id_value = result_data.get("homework_id") or result_data.get("assignment_id")
            assignment_title = None
            if assignment_id_value:
                assignment = get_homework(assignment_id_value)
                assignment_title = assignment.title if assignment else None
            record = {
                "import_id": row["id"],
                "batch_id": row["batch_id"],
                "class_id": class_id,
                "class_name": class_info.name if class_info else None,
                "assignment_id": assignment_id_value,
                "assignment_title": assignment_title,
                "student_count": row["total_students"] or 0,
                "status": row["status"],
                "created_at": row["created_at"],
                "revoked_at": None,
            }
            items = []
            for idx, item in enumerate(get_sqlite_student_results(row["id"])):
                result = item.result_data or {}
                if isinstance(result, str):
                    try:
                        result = json.loads(result)
                    except Exception:
                        result = {}
                student_name = (
                    result.get("studentName")
                    or result.get("student_name")
                    or item.student_key
                    or item.student_id
                    or f"Student {idx + 1}"
                )
                items.append({
                    "item_id": item.id,
                    "import_id": row["id"],
                    "batch_id": row["batch_id"],
                    "class_id": class_id,
                    "student_id": item.student_id or "",
                    "student_name": student_name,
                    "status": "revoked" if item.revoked_at else "imported",
                    "created_at": item.imported_at or row["created_at"],
                    "revoked_at": item.revoked_at,
                    "result": result,
                })
            return GradingHistoryDetailResponse(
                record=GradingImportRecord(**record),
                items=[GradingImportItem(**item) for item in items],
            )
    except Exception as exc:
        logger.warning("SQLite grading history detail read failed: %s", exc)

    try:
        with get_sqlite_connection() as conn:
            row = conn.execute("SELECT * FROM grading_imports WHERE id = ?", (import_id,)).fetchone()
            if row:
                class_info = get_class_by_id(row["class_id"])
                assignment_title = None
                if row["assignment_id"]:
                    assignment = get_homework(row["assignment_id"])
                    assignment_title = assignment.title if assignment else None
                record = {
                    "import_id": row["id"],
                    "batch_id": row["batch_id"],
                    "class_id": row["class_id"],
                    "class_name": class_info.name if class_info else None,
                    "assignment_id": row["assignment_id"],
                    "assignment_title": assignment_title,
                    "student_count": row["student_count"] or 0,
                    "status": row["status"],
                    "created_at": row["created_at"],
                    "revoked_at": row["revoked_at"],
                }

                item_rows = conn.execute(
                    "SELECT * FROM grading_import_items WHERE import_id = ? ORDER BY created_at",
                    (import_id,),
                ).fetchall()
                items = []
                for item in item_rows:
                    result_data = item["result_data"]
                    if isinstance(result_data, str):
                        try:
                            result = json.loads(result_data)
                        except Exception:
                            result = {}
                    else:
                        result = result_data or {}
                    items.append({
                        "item_id": item["id"],
                        "import_id": item["import_id"],
                        "batch_id": item["batch_id"],
                        "class_id": item["class_id"],
                        "student_id": item["student_id"],
                        "student_name": item["student_name"],
                        "status": item["status"],
                        "created_at": item["created_at"],
                        "revoked_at": item["revoked_at"],
                        "result": result,
                    })

                return GradingHistoryDetailResponse(
                    record=GradingImportRecord(**record),
                    items=[GradingImportItem(**item) for item in items],
                )
    except Exception as exc:
        logger.warning("SQLite import detail read failed: %s", exc)

    raise HTTPException(status_code=404, detail="Record not found")


@router.post("/grading/import/{import_id}/revoke", response_model=GradingImportRecord, tags=["Grading History"])
async def revoke_grading_import(import_id: str, request: GradingRevokeRequest):
    """Revoke import record."""
    try:
        with get_sqlite_connection() as conn:
            row = conn.execute("SELECT * FROM grading_history WHERE id = ?", (import_id,)).fetchone()
        if row:
            now = datetime.utcnow().isoformat()
            with get_sqlite_connection() as conn:
                conn.execute(
                    "UPDATE student_grading_results SET revoked_at = ? WHERE grading_history_id = ? AND revoked_at IS NULL",
                    (now, import_id),
                )
                conn.execute("UPDATE grading_history SET status = 'revoked' WHERE id = ?", (import_id,))
            class_ids = json.loads(row["class_ids"]) if row["class_ids"] else []
            result_data = json.loads(row["result_data"]) if row["result_data"] else {}
            class_id = class_ids[0] if class_ids else ""
            class_info = get_class_by_id(class_id) if class_id else None
            assignment_id_value = result_data.get("homework_id") or result_data.get("assignment_id")
            assignment_title = None
            if assignment_id_value:
                assignment = get_homework(assignment_id_value)
                assignment_title = assignment.title if assignment else None
            record = {
                "import_id": row["id"],
                "batch_id": row["batch_id"],
                "class_id": class_id,
                "class_name": class_info.name if class_info else None,
                "assignment_id": assignment_id_value,
                "assignment_title": assignment_title,
                "student_count": row["total_students"] or 0,
                "status": "revoked",
                "created_at": row["created_at"],
                "revoked_at": now,
            }
            return GradingImportRecord(**record)
    except Exception as exc:
        logger.warning("SQLite operation: %s", exc)

    try:
        with get_sqlite_connection() as conn:
            row = conn.execute("SELECT * FROM grading_imports WHERE id = ?", (import_id,)).fetchone()
            if row:
                now = datetime.utcnow().isoformat()
                conn.execute(
                    "UPDATE grading_imports SET status = 'revoked', revoked_at = ? WHERE id = ?",
                    (now, import_id),
                )
                conn.execute(
                    "UPDATE grading_import_items SET status = 'revoked', revoked_at = ? WHERE import_id = ? AND revoked_at IS NULL",
                    (now, import_id),
                )
                class_info = get_class_by_id(row["class_id"])
                assignment_title = None
                if row["assignment_id"]:
                    assignment = get_homework(row["assignment_id"])
                    assignment_title = assignment.title if assignment else None
                record = {
                    "import_id": row["id"],
                    "batch_id": row["batch_id"],
                    "class_id": row["class_id"],
                    "class_name": class_info.name if class_info else None,
                    "assignment_id": row["assignment_id"],
                    "assignment_title": assignment_title,
                    "student_count": row["student_count"] or 0,
                    "status": "revoked",
                    "created_at": row["created_at"],
                    "revoked_at": now,
                }
                return GradingImportRecord(**record)
    except Exception as exc:
        logger.warning("SQLite operation: %s", exc)

    raise HTTPException(status_code=404, detail="Record not found")


@router.post("/assistant/chat", response_model=AssistantChatResponse, tags=["Student Assistant"])
async def assistant_chat(request: AssistantChatRequest):
    """Student assistant chat."""
    context = _build_student_context(request.student_id, request.class_id)
    system_prompt = f"""You are GradeOS Student Assistant, focused on data-driven tutoring.
Use the provided context as ground truth for scores, wrong questions, recent submissions, and class membership.
If the context is insufficient, explain what is missing and propose next steps.
Be concise, structured, and actionable.

CONTEXT:
{json.dumps(context, ensure_ascii=False)}"""

    messages: List[LLMMessage] = [LLMMessage(role="system", content=system_prompt)]
    if request.history:
        for msg in request.history[-8:]:
            role = msg.role if msg.role in ("system", "user", "assistant") else "user"
            messages.append(LLMMessage(role=role, content=msg.content))
    messages.append(LLMMessage(role="user", content=request.message))

    client = get_llm_client()
    response = await client.invoke(
        messages=messages,
        purpose="assistant",
        temperature=0.3,
        max_tokens=2048,
    )

    return AssistantChatResponse(
        content=response.content,
        model=response.model,
        usage=response.usage or {},
    )


# ============ Error Analysis (IntelliLearn) ============

# ============ Error Analysis (IntelliLearn) ============

@router.post("/v1/analysis/submit-error", response_model=ErrorAnalysisResponse, tags=["Error Analysis"])
async def analyze_error(request: ErrorAnalysisRequest):
    """Analyze a single wrong answer with LLM."""
    analysis_id = str(uuid.uuid4())[:8]
    context = _build_student_context(request.student_id, None) if request.student_id else {}

    system_prompt = """You are GradeOS error analysis engine.
Return a single JSON object only with this schema:
{
  "error_type": "...",
  "error_severity": "low|medium|high",
  "root_cause": "...",
  "knowledge_gaps": [{"knowledge_point": "...", "mastery_level": 0.0, "confidence": 0.0}],
  "detailed_analysis": {
    "step_by_step_correction": ["..."],
    "common_mistakes": "...",
    "correct_solution": "..."
  },
  "recommendations": {
    "immediate_actions": ["..."],
    "practice_exercises": ["..."],
    "learning_path": {"short_term": ["..."], "long_term": ["..."]}
  }
}
Use only the provided data. If data is insufficient, return empty lists where appropriate."""

    payload = {
        "subject": request.subject,
        "question": request.question,
        "student_answer": request.student_answer,
        "student_context": context,
    }

    client = get_llm_client()
    response = await client.invoke(
        messages=[
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=json.dumps(payload, ensure_ascii=False)),
        ],
        purpose="analysis",
        temperature=0.2,
        max_tokens=1200,
    )

    try:
        data = _parse_llm_json(response.content)
        return ErrorAnalysisResponse(analysis_id=analysis_id, **data)
    except Exception as exc:
        logger.error("Failed to parse error analysis response: %s", exc)
        raise HTTPException(status_code=502, detail="Invalid LLM response")


@router.get("/v1/diagnosis/report/{student_id}", response_model=DiagnosisReportResponse, tags=["Error Analysis"])
async def get_diagnosis_report(student_id: str):
    """Generate a diagnosis report for a student."""
    context = _build_student_context(student_id, None)
    submissions = list_student_submissions(student_id, limit=12)

    scored = [s for s in submissions if s.score is not None]
    scored_sorted = sorted(scored, key=lambda s: s.submitted_at or "")
    trend_seed = []
    for sub in scored_sorted:
        date_value = (sub.submitted_at or "")[:10] or sub.submitted_at or ""
        trend_seed.append({"date": date_value, "score": sub.score})

    summary = context.get("grading_summary", {})
    total_max = float(summary.get("total_max") or 0)
    total_score = float(summary.get("total_score") or 0)
    mastery = round(total_score / total_max, 4) if total_max > 0 else 0.0

    report_period = "all_time"
    if scored_sorted:
        start_date = (scored_sorted[0].submitted_at or "")[:10]
        end_date = (scored_sorted[-1].submitted_at or "")[:10]
        if start_date and end_date:
            report_period = f"{start_date} to {end_date}"

    payload = {
        "student_id": student_id,
        "report_period": report_period,
        "context": context,
        "trend_seed": trend_seed,
        "mastery_score": mastery,
    }

    system_prompt = """You are GradeOS diagnosis report engine.
Return a single JSON object only with this schema:
{
  "report_period": "...",
  "overall_assessment": {"mastery_score": 0.0, "improvement_rate": 0.0, "consistency_score": 0},
  "progress_trend": [{"date": "YYYY-MM-DD", "score": 0.0, "average": 0.0}],
  "knowledge_map": [{"knowledge_area": "...", "mastery_level": 0.0, "weak_points": ["..."], "strengths": ["..."]}],
  "error_patterns": {"most_common_error_types": [{"type": "...", "count": 0, "percentage": 0.0}]},
  "personalized_insights": ["..."]
}
Use only the provided data. If data is insufficient, return empty lists where appropriate."""

    client = get_llm_client()
    response = await client.invoke(
        messages=[
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=json.dumps(payload, ensure_ascii=False)),
        ],
        purpose="analysis",
        temperature=0.25,
        max_tokens=1400,
    )

    try:
        data = _parse_llm_json(response.content)
        return DiagnosisReportResponse(student_id=student_id, **data)
    except Exception as exc:
        logger.warning("Failed to parse diagnosis report response: %s", exc)
        fallback = {
            "report_period": report_period,
            "overall_assessment": {
                "mastery_score": mastery,
                "improvement_rate": 0.0,
                "consistency_score": 0,
            },
            "progress_trend": trend_seed,
            "knowledge_map": [],
            "error_patterns": {"most_common_error_types": []},
            "personalized_insights": [],
        }
        return DiagnosisReportResponse(student_id=student_id, **fallback)


@router.get("/v1/class/wrong-problems", tags=["Error Analysis"])
async def get_class_wrong_problems(class_id: Optional[str] = None):
    """Get high-frequency wrong problems for a class."""
    if not class_id:
        raise HTTPException(status_code=400, detail="class_id is required")

    with get_sqlite_connection() as conn:
        rows = conn.execute(
            "SELECT result_data FROM student_grading_results WHERE class_id = ?",
            (class_id,),
        ).fetchall()

    stats = {}
    for row in rows:
        result_data = row["result_data"]
        if isinstance(result_data, str):
            try:
                result = json.loads(result_data)
            except Exception:
                result = {}
        else:
            result = result_data or {}

        for q in _extract_question_results(result):
            max_score = float(q.get("maxScore") or q.get("max_score") or 0)
            if max_score <= 0:
                continue
            score = float(q.get("score") or 0)
            question_id = str(
                q.get("questionId")
                or q.get("question_id")
                or q.get("id")
                or q.get("qid")
                or ""
            ).strip()
            question_text = (
                q.get("questionText")
                or q.get("question")
                or q.get("prompt")
                or q.get("stem")
                or ""
            )
            if not question_id and question_text:
                question_id = question_text[:32]
            if not question_id:
                question_id = "unknown"

            entry = stats.setdefault(
                question_id,
                {"question": question_text or question_id, "wrong": 0, "total": 0},
            )
            entry["total"] += 1
            if score < max_score:
                entry["wrong"] += 1

    problems_seed = []
    for question_id, entry in stats.items():
        total = entry["total"]
        wrong = entry["wrong"]
        if total <= 0:
            continue
        error_rate = wrong / total
        problems_seed.append({
            "id": question_id,
            "question": entry["question"],
            "errorRate": f"{error_rate * 100:.1f}%",
            "wrong": wrong,
            "total": total,
        })

    problems_seed = sorted(
        problems_seed,
        key=lambda item: (-(item["wrong"] / item["total"]), -item["wrong"]),
    )[:8]

    if not problems_seed:
        return {"problems": []}

    client = get_llm_client()
    system_prompt = """You are GradeOS class error analysis engine.
Given a list of wrong problems with error rates, return JSON only with this schema:
{
  "problems": [
    {"id": "...", "question": "...", "errorRate": "12.3%", "tags": ["..."]}
  ]
}
Do not invent new problems; only enrich the provided ones."""
    response = await client.invoke(
        messages=[
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=json.dumps({"problems": problems_seed}, ensure_ascii=False)),
        ],
        purpose="analysis",
        temperature=0.2,
        max_tokens=600,
    )

    try:
        data = _parse_llm_json(response.content)
        problems = data.get("problems") if isinstance(data, dict) else None
        if isinstance(problems, list):
            return {"problems": problems}
    except Exception as exc:
        logger.warning("Failed to parse wrong-problems response: %s", exc)

    fallback = [
        {"id": item["id"], "question": item["question"], "errorRate": item["errorRate"], "tags": []}
        for item in problems_seed
    ]
    return {"problems": fallback}


# ============ Statistics ============

@router.get("/teacher/statistics/class/{class_id}", tags=["Statistics"])
async def get_class_statistics(class_id: str, homework_id: Optional[str] = None):
    """Get class statistics based on real submissions."""
    total_students = count_class_students(class_id)

    with get_sqlite_connection() as conn:
        if homework_id:
            rows = conn.execute(
                "SELECT score FROM homework_submissions WHERE class_id = ? AND homework_id = ?",
                (class_id, homework_id),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT score FROM homework_submissions WHERE class_id = ?",
                (class_id,),
            ).fetchall()

    submitted_count = len(rows)
    scores = [row["score"] for row in rows if row["score"] is not None]
    graded_count = len(scores)

    if not scores:
        histories = list_sqlite_grading_history(class_id=class_id, limit=200)
        history_ids = []
        for history in histories:
            result_meta = history.result_data or {}
            assignment_id_value = result_meta.get("homework_id") or result_meta.get("assignment_id")
            if homework_id and assignment_id_value != homework_id:
                continue
            history_ids.append(history.id)

        fallback_scores = []
        for history_id in history_ids:
            for item in get_sqlite_student_results(history_id):
                if item.score is not None:
                    fallback_scores.append(item.score)

        if fallback_scores:
            scores = fallback_scores
            graded_count = len(scores)
            submitted_count = max(submitted_count, len(scores))

    if scores:
        average_score = round(sum(scores) / len(scores), 2)
        max_score = max(scores)
        min_score = min(scores)
        pass_rate = round(len([s for s in scores if s >= 60]) / len(scores), 3)
    else:
        average_score = 0.0
        max_score = 0.0
        min_score = 0.0
        pass_rate = 0.0

    distribution = {
        "90-100": 0,
        "80-89": 0,
        "70-79": 0,
        "60-69": 0,
        "0-59": 0,
    }
    for score in scores:
        if score >= 90:
            distribution["90-100"] += 1
        elif score >= 80:
            distribution["80-89"] += 1
        elif score >= 70:
            distribution["70-79"] += 1
        elif score >= 60:
            distribution["60-69"] += 1
        else:
            distribution["0-59"] += 1

    return {
        "class_id": class_id,
        "total_students": total_students,
        "submitted_count": submitted_count,
        "graded_count": graded_count,
        "average_score": average_score,
        "max_score": max_score,
        "min_score": min_score,
        "pass_rate": pass_rate,
        "score_distribution": distribution,
    }


class MergeStatisticsRequest(BaseModel):
    external_data: Optional[Any] = None


@router.post("/teacher/statistics/merge", tags=["Statistics"])
async def merge_statistics(class_id: str, request: Optional[MergeStatisticsRequest] = None):
    """Merge external score data with internal submissions."""
    external_data = request.external_data if request else None
    if isinstance(external_data, str):
        try:
            external_data = json.loads(external_data)
        except Exception:
            external_data = None

    students = {s.id: {"id": s.id, "name": s.name or s.username or s.id, "scores": {}} for s in list_class_students(class_id)}
    homeworks = list_homeworks(class_id)
    homework_titles = {hw.id: hw.title for hw in homeworks}

    with get_sqlite_connection() as conn:
        rows = conn.execute(
            "SELECT homework_id, student_id, student_name, score FROM homework_submissions WHERE class_id = ?",
            (class_id,),
        ).fetchall()
    for row in rows:
        if row["score"] is None:
            continue
        title = homework_titles.get(row["homework_id"], row["homework_id"])
        student_id = row["student_id"]
        if student_id not in students:
            students[student_id] = {
                "id": student_id,
                "name": row["student_name"] or student_id,
                "scores": {},
            }
        students[student_id]["scores"][title] = row["score"]

    internal_assignments = sorted(set(homework_titles.values()))
    external_assignments = []

    external_students = []
    if isinstance(external_data, dict):
        if isinstance(external_data.get("students"), list):
            external_students = external_data.get("students")
        elif isinstance(external_data.get("data"), list):
            external_students = external_data.get("data")
    elif isinstance(external_data, list):
        external_students = external_data

    for ext in external_students:
        if not isinstance(ext, dict):
            continue
        student_id = str(ext.get("id") or ext.get("student_id") or "").strip()
        if not student_id:
            continue
        name = ext.get("name") or ext.get("student_name") or student_id
        scores = ext.get("scores") or ext.get("assignments") or {}
        if student_id not in students:
            students[student_id] = {"id": student_id, "name": name, "scores": {}}
        for assignment, score in scores.items():
            students[student_id]["scores"][assignment] = score
            if assignment not in internal_assignments and assignment not in external_assignments:
                external_assignments.append(assignment)

    return {
        "students": list(students.values()),
        "internalAssignments": internal_assignments,
        "externalAssignments": external_assignments,
    }


class BookscanEditRequest(BaseModel):
    image_base64: str
    prompt: str
    mime_type: Optional[str] = "image/jpeg"
    model: Optional[str] = None


class BookscanGenerateRequest(BaseModel):
    prompt: str
    size: Optional[str] = None
    model: Optional[str] = None


def _ensure_llm_api_key() -> None:
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=400, detail="LLM_API_KEY/OPENROUTER_API_KEY is required")


@router.post("/bookscan/edit", tags=["Bookscan"])
async def bookscan_edit(request: BookscanEditRequest):
    """Edit image via LLM-assisted pipeline (currently returns original image)."""
    _ensure_llm_api_key()
    image_data = request.image_base64
    mime_type = request.mime_type or "image/jpeg"
    if image_data.startswith("data:") and "," in image_data:
        header, image_data = image_data.split(",", 1)
        if header.startswith("data:") and ";base64" in header:
            mime_type = header.split("data:", 1)[1].split(";", 1)[0] or mime_type

    client = get_llm_client()
    try:
        await client.invoke(
            messages=[
                LLMMessage(
                    role="system",
                    content="You are GradeOS image edit planner. Summarize the edit plan in 2 bullet points.",
                ),
                LLMMessage(role="user", content=request.prompt),
            ],
            purpose="analysis",
            temperature=0.2,
            max_tokens=200,
            model=request.model,
        )
    except Exception as exc:
        logger.warning("Bookscan edit planner failed: %s", exc)

    return {"image": f"data:{mime_type};base64,{image_data}"}


@router.post("/bookscan/generate", tags=["Bookscan"])
async def bookscan_generate(request: BookscanGenerateRequest):
    """Generate an SVG image via LLM."""
    _ensure_llm_api_key()
    size_map = {"1K": 1024, "2K": 2048, "4K": 4096}
    size_px = size_map.get((request.size or "").upper(), 1024)
    prompt = request.prompt.strip()

    client = get_llm_client()
    response = await client.invoke(
        messages=[
            LLMMessage(
                role="system",
                content=(
                    "Return a single SVG only. Do not use markdown or code fences. "
                    f"Use width and height {size_px}."
                ),
            ),
            LLMMessage(role="user", content=prompt),
        ],
        purpose="text",
        temperature=0.7,
        max_tokens=1200,
        model=request.model,
    )

    svg_text = response.content.strip()
    if not svg_text.lower().startswith("<svg"):
        match = re.search(r"<svg[\\s\\S]*?</svg>", svg_text, re.I)
        if match:
            svg_text = match.group(0)
        else:
            svg_text = (
                f"<svg xmlns='http://www.w3.org/2000/svg' width='{size_px}' height='{size_px}'>"
                "<rect width='100%' height='100%' fill='#f8fafc'/>"
                f"<text x='50%' y='50%' font-size='32' text-anchor='middle' fill='#0f172a'>"
                f"{prompt or 'Generated Image'}</text></svg>"
            )

    svg_base64 = base64.b64encode(svg_text.encode("utf-8")).decode("ascii")
    return {"image": f"data:image/svg+xml;base64,{svg_base64}"}
