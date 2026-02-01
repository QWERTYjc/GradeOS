"""
GradeOS 统一 API 路由
整合所有子系统的 API 接口
"""

import asyncio
import base64
import hashlib
import json
import logging
import os
import re
import uuid
import inspect
import redis.asyncio as redis
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from pydantic import BaseModel, Field
from redis.exceptions import RedisError
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from src.api.dependencies import get_orchestrator
from src.orchestration.base import Orchestrator
from src.api.routes.batch_langgraph import _format_results_for_frontend
from src.utils.database import db
from src.utils.pool_manager import UnifiedPoolManager, PoolNotInitializedError
from src.db import (
    HomeworkSubmission,
    save_homework_submission,
    list_grading_history,
    get_grading_history as get_grading_history_record,
    GradingHistory,
    save_grading_history,
    StudentGradingResult,
    save_student_result,
    get_student_results,  # 同步版本 (SQLite fallback)
    get_connection,
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
    upsert_assistant_concepts,
    list_assistant_concepts,
    save_assistant_mastery_snapshot,
    list_assistant_mastery_snapshots,
)
from src.services.llm_client import LLMMessage, get_llm_client
from src.services.assistant_memory import AssistantMemory, build_assistant_session_id
from src.services.student_assistant_agent import (
    AssistantConceptNode,
    AssistantMastery,
    get_student_assistant_agent,
)
from src.utils.image import to_jpeg_bytes
from src.utils.auth import hash_password, verify_password

# 导入异步版本的 PostgreSQL 函数
from src.db.postgres_grading import (
    get_student_results as get_student_results_async,
    get_grading_history as get_grading_history_async,
    list_grading_history as list_grading_history_async,
)

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
    # 新增：学习模式
    session_mode: Optional[str] = "learning"  # learning / assessment
    concept_topic: Optional[str] = None  # 当前学习的概念主题
    # 新增：多模态支持 - 错题图片
    images: Optional[List[str]] = None  # base64 编码的图片列表
    # 新增：错题上下文（从错题本跳转时传入）
    wrong_question_context: Optional[Dict[str, Any]] = None


class ConceptNode(BaseModel):
    """概念分解节点（第一性原理）"""

    id: str
    name: str
    description: str
    understood: bool = False
    children: Optional[List["ConceptNode"]] = None


class MasteryData(BaseModel):
    """掌握度评估数据"""

    score: int  # 0-100
    level: str  # beginner / developing / proficient / mastery
    analysis: str  # 分析说明
    evidence: List[str] = []  # 证据列表
    suggestions: List[str] = []  # 改进建议


class AssistantChatResponse(BaseModel):
    content: str
    model: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None  # 支持 OpenRouter 扩展格式（含浮点数和嵌套字典）
    # 新增：结构化输出
    mastery: Optional[MasteryData] = None  # 掌握度评估
    next_question: Optional[str] = None  # 苏格拉底式追问
    question_options: Optional[List[str]] = None  # 追问的可选按钮
    focus_mode: bool = False  # 是否进入专注模式
    concept_breakdown: Optional[List[ConceptNode]] = None  # 第一性原理概念分解
    response_type: str = "chat"  # chat / question / assessment / explanation


class MasterySnapshot(BaseModel):
    score: int
    level: str
    analysis: str
    evidence: List[str] = []
    suggestions: List[str] = []
    created_at: str


class AssistantProgressResponse(BaseModel):
    student_id: str
    class_id: Optional[str] = None
    concept_breakdown: List[ConceptNode] = []
    mastery_history: List[MasterySnapshot] = []


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


# ============ 错题本手动录入模型 ============


class ManualWrongQuestionCreate(BaseModel):
    """手动录入错题请求"""
    student_id: str
    class_id: Optional[str] = None
    question_id: Optional[str] = None  # 可选，自动生成
    subject: Optional[str] = None  # 科目
    topic: Optional[str] = None  # 知识点/主题
    question_content: Optional[str] = None  # 题目内容（文字）
    student_answer: Optional[str] = None  # 学生答案
    correct_answer: Optional[str] = None  # 正确答案
    score: float = 0  # 得分
    max_score: float = 0  # 满分
    feedback: Optional[str] = None  # 反馈/解析
    images: List[str] = []  # 图片列表（base64）
    tags: List[str] = []  # 标签


class ManualWrongQuestionResponse(BaseModel):
    """手动录入错题响应"""
    id: str
    student_id: str
    class_id: Optional[str] = None
    question_id: str
    subject: Optional[str] = None
    topic: Optional[str] = None
    question_content: Optional[str] = None
    student_answer: Optional[str] = None
    correct_answer: Optional[str] = None
    score: float
    max_score: float
    feedback: Optional[str] = None
    images: List[str] = []
    tags: List[str] = []
    source: str = "manual"  # manual / grading
    created_at: str


class ManualWrongQuestionListResponse(BaseModel):
    """错题列表响应"""
    questions: List[ManualWrongQuestionResponse]
    total: int


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


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _get_student_map(class_id: str) -> Dict[str, str]:
    students = list_class_students(class_id)
    return {student.id: student.name or student.username or student.id for student in students}


def _extract_question_results(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    for key in (
        "questionResults",
        "question_results",
        "questions",
        "questionDetails",
        "question_details",
    ):
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


_ASSISTANT_REDIS_CLIENT: Optional[redis.Redis] = None
_ASSISTANT_REDIS_CHECKED: bool = False
_ASSISTANT_PROGRESS_TTL_SECONDS = int(os.getenv("ASSISTANT_PROGRESS_TTL_SECONDS", "900"))
_ASSISTANT_PROGRESS_KEY_PREFIX = os.getenv("ASSISTANT_PROGRESS_KEY_PREFIX", "assistant_progress")


def _assistant_progress_key(student_id: str, class_id: Optional[str]) -> str:
    suffix = class_id.strip() if class_id and class_id.strip() else "global"
    return f"{_ASSISTANT_PROGRESS_KEY_PREFIX}:{student_id}:{suffix}"


def _assistant_concept_key(name: str, parent_key: Optional[str]) -> str:
    normalized = f"{parent_key or 'root'}::{name.strip().lower()}"
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]


async def _get_assistant_redis_client() -> Optional[redis.Redis]:
    global _ASSISTANT_REDIS_CLIENT, _ASSISTANT_REDIS_CHECKED
    if _ASSISTANT_REDIS_CHECKED:
        return _ASSISTANT_REDIS_CLIENT
    _ASSISTANT_REDIS_CHECKED = True
    try:
        pool_manager = await UnifiedPoolManager.get_instance()
        if pool_manager.is_initialized:
            _ASSISTANT_REDIS_CLIENT = pool_manager.get_redis_client()
    except PoolNotInitializedError:
        _ASSISTANT_REDIS_CLIENT = None
    except Exception as exc:
        logger.debug(f"Redis client unavailable: {exc}")
        _ASSISTANT_REDIS_CLIENT = None
    return _ASSISTANT_REDIS_CLIENT


async def _load_assistant_progress_cache(
    student_id: str, class_id: Optional[str]
) -> Optional[Dict[str, Any]]:
    redis_client = await _get_assistant_redis_client()
    if not redis_client:
        return None
    try:
        cached = await redis_client.get(_assistant_progress_key(student_id, class_id))
    except RedisError as exc:
        logger.debug(f"Failed to load assistant progress cache: {exc}")
        return None
    if not cached:
        return None
    try:
        return json.loads(cached)
    except Exception:
        return None


async def _store_assistant_progress_cache(
    student_id: str,
    class_id: Optional[str],
    payload: Dict[str, Any],
) -> None:
    redis_client = await _get_assistant_redis_client()
    if not redis_client:
        return
    try:
        await redis_client.setex(
            _assistant_progress_key(student_id, class_id),
            _ASSISTANT_PROGRESS_TTL_SECONDS,
            json.dumps(payload, ensure_ascii=False),
        )
    except RedisError as exc:
        logger.debug(f"Failed to cache assistant progress: {exc}")


async def _invalidate_assistant_progress_cache(student_id: str, class_id: Optional[str]) -> None:
    redis_client = await _get_assistant_redis_client()
    if not redis_client:
        return
    try:
        await redis_client.delete(_assistant_progress_key(student_id, class_id))
    except RedisError as exc:
        logger.debug(f"Failed to invalidate assistant progress cache: {exc}")


def _flatten_concepts(
    nodes: List[AssistantConceptNode],
    parent_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    flattened: List[Dict[str, Any]] = []
    for node in nodes:
        name = (node.name or "").strip()
        if not name:
            continue
        concept_key = _assistant_concept_key(name, parent_key)
        flattened.append(
            {
                "concept_key": concept_key,
                "parent_key": parent_key,
                "name": name,
                "description": node.description or "",
                "understood": bool(node.understood),
            }
        )
        if node.children:
            flattened.extend(_flatten_concepts(node.children, concept_key))
    return flattened


def _build_concept_tree(rows: List[Dict[str, Any]]) -> List[ConceptNode]:
    node_map: Dict[str, ConceptNode] = {}
    for row in rows:
        node_map[row["concept_key"]] = ConceptNode(
            id=row["concept_key"],
            name=row["name"],
            description=row.get("description") or "",
            understood=bool(row.get("understood")),
            children=[],
        )

    roots: List[ConceptNode] = []
    for row in rows:
        node = node_map[row["concept_key"]]
        parent_key = row.get("parent_key")
        if parent_key and parent_key in node_map:
            parent = node_map[parent_key]
            if parent.children is None:
                parent.children = []
            parent.children.append(node)
        else:
            roots.append(node)

    for node in node_map.values():
        if node.children == []:
            node.children = None
    return roots


_CONFUSION_PATTERNS = (
    r"\b(i\s*(don't|do not)\s*know|no idea|not sure|confused|stuck|help|hint)\b",
    r"(不知道|不懂|不会|不会做|不会解|没思路|没想法|看不懂|搞不懂|太难|求助|求提示)",
)


def _is_confused_message(message: str) -> bool:
    if not message:
        return False
    lowered = message.lower()
    if re.search(_CONFUSION_PATTERNS[0], lowered):
        return True
    return re.search(_CONFUSION_PATTERNS[1], message) is not None


def _history_from_request(
    history: Optional[List[AssistantMessage]],
    current_message: str,
) -> List[BaseMessage]:
    if not history:
        return []
    items = list(history)
    if items and items[-1].role == "user" and items[-1].content.strip() == current_message.strip():
        items = items[:-1]
    messages: List[BaseMessage] = []
    for item in items[-10:]:
        content = (item.content or "").strip()
        if not content:
            continue
        role = item.role
        if role == "assistant":
            messages.append(AIMessage(content=content))
        elif role == "system":
            messages.append(SystemMessage(content=content))
        else:
            messages.append(HumanMessage(content=content))
    return messages


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

    with get_connection() as conn:
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
                    wrong_samples.append(
                        {
                            "question_id": str(q.get("questionId") or q.get("question_id") or ""),
                            "score": score,
                            "max_score": max_score,
                            "feedback": q.get("feedback") or "",
                            "student_answer": q.get("studentAnswer")
                            or q.get("student_answer")
                            or "",
                            "evidence": (
                                q.get("scoring_point_results") or q.get("scoringPointResults") or []
                            )[:2],
                        }
                    )

    submissions = []
    for submission in list_student_submissions(student_id, limit=5):
        homework = get_homework(submission.homework_id)
        submissions.append(
            {
                "homework_id": submission.homework_id,
                "title": homework.title if homework else None,
                "status": submission.status,
                "submitted_at": submission.submitted_at,
                "score": submission.score,
            }
        )

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
    run_info = await orchestrator.get_run_info(run_id) if orchestrator else None
    if run_info:
        state = run_info.state or {}
        student_results = state.get("student_results", [])
        if not student_results:
            final_output = await orchestrator.get_final_output(run_id)
            if final_output:
                student_results = final_output.get("student_results", [])
        if student_results:
            return _format_results_for_frontend(student_results)

    history = await _maybe_await(get_grading_history_record(batch_id))
    if not history:
        raise HTTPException(status_code=404, detail="批改批次不存在")

    raw_results: List[Dict[str, Any]] = []
    student_rows = await _maybe_await(get_student_results(history.id))
    for row in student_rows:
        data = row.result_data
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except Exception:
                data = {}
        if not isinstance(data, dict):
            data = {}
        if not data:
            data = {
                "studentName": row.student_key,
                "score": row.score,
                "maxScore": row.max_score,
            }
        raw_results.append(data)

    return _format_results_for_frontend(raw_results)


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
        manual_boundaries.append(
            {
                "student_id": submission.student_id,
                "student_key": submission.student_name or submission.student_id,
                "pages": pages,
            }
        )
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
            "expected_students": len(manual_boundaries) or count_class_students(class_id),
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


async def _schedule_deadline_grading(
    homework_id: str, deadline: datetime, orchestrator: Orchestrator
) -> None:
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
        classes.append(
            ClassResponse(
                class_id=class_record.id,
                class_name=class_record.name,
                teacher_id=class_record.teacher_id,
                invite_code=class_record.invite_code,
                student_count=count_class_students(class_record.id),
            )
        )
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
        classes.append(
            ClassResponse(
                class_id=class_record.id,
                class_name=class_record.name,
                teacher_id=class_record.teacher_id,
                invite_code=class_record.invite_code,
                student_count=count_class_students(class_record.id),
            )
        )
    return classes


@router.post("/teacher/classes", response_model=ClassResponse, tags=["班级管理"])
async def create_class(request: ClassCreate):
    """创建班级"""
    import random
    import string

    invite_code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

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
    with get_connection() as conn:
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
        submission_counts = {
            row["student_id"]: int(row["submitted_count"]) for row in submission_rows
        }

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
            "avgScore": (
                round(
                    (score_totals.get(student.id, 0.0) / score_counts.get(student.id, 1)) * 100, 1
                )
                if score_counts.get(student.id)
                else None
            ),
            "submissionRate": (
                round((submission_counts.get(student.id, 0) / total_homeworks) * 100, 1)
                if total_homeworks > 0
                else None
            ),
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
        responses.append(
            HomeworkResponse(
                homework_id=record.id,
                class_id=record.class_id,
                class_name=class_info.name if class_info else None,
                title=record.title,
                description=record.description or "",
                deadline=record.deadline,
                allow_early_grading=record.allow_early_grading,
                created_at=record.created_at,
            )
        )
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
        task = asyncio.create_task(
            _schedule_deadline_grading(homework_id, deadline_dt, orchestrator)
        )
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
            if "," in img_data:
                img_data = img_data.split(",")[1]

            # 解码并保存
            img_bytes = base64.b64decode(img_data)
            img_bytes = to_jpeg_bytes(img_bytes)
            file_path = submission_dir / f"page_{idx + 1}.jpg"

            with open(file_path, "wb") as f:
                f.write(img_bytes)

            saved_paths.append(str(file_path))
            images_bytes.append(img_bytes)
            stored_images.append(
                f"data:image/jpeg;base64,{base64.b64encode(img_bytes).decode('utf-8')}"
            )
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
        logger.warning(f"保存作业提交到 ??? 失败: {exc}")

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
    history_record = get_grading_history_record(request.batch_id)
    import_teacher_id = None
    for target in request.targets:
        class_info = get_class_by_id(target.class_id)
        if class_info:
            import_teacher_id = class_info.teacher_id
            break
    target_class_ids = [target.class_id for target in request.targets]
    total_students = sum(len(target.student_ids) for target in request.targets)
    if history_record:
        merged_class_ids = set(history_record.class_ids or [])
        merged_class_ids.update(target_class_ids)
        updated_history = GradingHistory(
            id=history_record.id,
            batch_id=history_record.batch_id,
            teacher_id=history_record.teacher_id or import_teacher_id,
            status="imported",
            class_ids=list(merged_class_ids),
            created_at=history_record.created_at or now,
            completed_at=history_record.completed_at or now,
            total_students=max(history_record.total_students or 0, total_students),
            average_score=history_record.average_score,
            result_data=history_record.result_data,
        )
        save_grading_history(updated_history)
        history_id = history_record.id
    else:
        history_id = str(uuid.uuid4())
        history = GradingHistory(
            id=history_id,
            batch_id=request.batch_id,
            teacher_id=import_teacher_id,
            status="imported",
            class_ids=target_class_ids,
            created_at=now,
            completed_at=now,
            total_students=total_students,
            average_score=None,
            result_data=None,
        )
        save_grading_history(history)

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
        with get_connection() as conn:
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
            with get_connection() as conn:
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
            if result:
                score_value = (
                    result.get("total_score") or result.get("totalScore") or result.get("score")
                )
                max_score_value = (
                    result.get("max_score")
                    or result.get("maxScore")
                    or result.get("max_total_score")
                    or result.get("maxTotalScore")
                )
                summary_data = (
                    result.get("studentSummary")
                    or result.get("student_summary")
                    or result.get("summary")
                )
                confession_payload = result.get("confession")
                summary_text = None
                if isinstance(summary_data, dict):
                    summary_text = summary_data.get("overall")
                elif isinstance(summary_data, str):
                    summary_text = summary_data
                confession_text = None
                if isinstance(confession_payload, dict):
                    confession_text = confession_payload.get("summary")
                elif isinstance(confession_payload, str):
                    confession_text = confession_payload
                identity_token = student_id or student_key or student_name
                stable_key = f"{history_id}:{identity_token}"
                result_id = str(uuid.uuid5(uuid.NAMESPACE_URL, stable_key))
                with get_connection() as conn:
                    if student_id:
                        conn.execute(
                            "DELETE FROM student_grading_results WHERE grading_history_id = ? AND student_id = ?",
                            (str(history_id), student_id),
                        )
                    else:
                        conn.execute(
                            "DELETE FROM student_grading_results WHERE grading_history_id = ? AND student_key = ?",
                            (str(history_id), student_key or student_name),
                        )
                student_result = StudentGradingResult(
                    id=result_id,
                    grading_history_id=str(history_id),
                    student_key=student_key or student_name,
                    score=float(score_value) if score_value is not None else None,
                    max_score=float(max_score_value) if max_score_value is not None else None,
                    class_id=target.class_id,
                    student_id=student_id,
                    summary=summary_text,
                    confession=confession_text,
                    result_data=result,
                    imported_at=now,
                )
                save_student_result(student_result)

        records.append(GradingImportRecord(**record))

    return GradingHistoryResponse(records=records)


@router.get("/grading/history", response_model=GradingHistoryResponse, tags=["批改历史"])
async def get_grading_history(
    class_id: Optional[str] = None,
    assignment_id: Optional[str] = None,
    teacher_id: Optional[str] = None,
):
    """Get grading history list from PostgreSQL."""
    records: List[Dict[str, Any]] = []

    allowed_class_ids: Optional[List[str]] = None
    if teacher_id:
        try:
            user = get_user_by_id(teacher_id)
            if user and user.role == 'teacher':
                allowed_class_ids = [c.id for c in list_classes_by_teacher(teacher_id)]
            elif user and user.role == 'student':
                allowed_class_ids = list_user_class_ids(user.id)
            else:
                allowed_class_ids = []
        except Exception:
            allowed_class_ids = []

    try:
        # 使用异步版本获取批改历史
        histories = await list_grading_history_async(class_id=class_id, limit=50)
        for history in histories:
            class_ids = history.class_ids or []
            if isinstance(class_ids, str):
                class_ids = [class_ids]
            if allowed_class_ids is not None:
                result_meta = history.result_data or {}
                if not isinstance(result_meta, dict):
                    result_meta = {}
                teacher_match = getattr(history, 'teacher_id', None) or result_meta.get('teacher_id') or result_meta.get('teacherId')
                if teacher_match and teacher_id and teacher_match == teacher_id:
                    pass
                else:
                    if class_ids:
                        if not any(cid in allowed_class_ids for cid in class_ids):
                            continue
                    else:
                        if teacher_match != teacher_id:
                            continue
            target_class_id = class_id or (class_ids[0] if class_ids else None)
            if class_id and class_id not in class_ids:
                continue
            result_meta = history.result_data or {}
            if not isinstance(result_meta, dict):
                result_meta = {}
            assignment_id_value = result_meta.get("homework_id") or result_meta.get("assignment_id")
            if assignment_id and assignment_id_value != assignment_id:
                continue
            class_info = get_class_by_id(target_class_id) if target_class_id else None
            assignment_title = None
            if assignment_id_value:
                assignment = get_homework(assignment_id_value)
                assignment_title = assignment.title if assignment else None
            created_at_value = history.created_at
            if isinstance(created_at_value, datetime):
                created_at_value = created_at_value.isoformat()
            elif created_at_value is not None:
                created_at_value = str(created_at_value)
            if not created_at_value:
                created_at_value = ""
            records.append(
                {
                    "import_id": str(history.id),
                    "batch_id": history.batch_id or "",
                    "class_id": target_class_id or "",
                    "class_name": class_info.name if class_info else None,
                    "assignment_id": assignment_id_value,
                    "assignment_title": assignment_title,
                    "student_count": history.total_students or 0,
                    "status": history.status or "unknown",
                    "created_at": created_at_value,
                    "revoked_at": None,
                }
            )
    except Exception as exc:
        logger.warning(f"PostgreSQL grading detail read failed: {exc}")

    try:
        with get_connection() as conn:
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
            if allowed_class_ids is not None and row.get('class_id') not in allowed_class_ids:
                continue
            if assignment_id and row["assignment_id"] != assignment_id:
                continue
            class_info = get_class_by_id(row["class_id"])
            assignment_title = None
            if row["assignment_id"]:
                assignment = get_homework(row["assignment_id"])
                assignment_title = assignment.title if assignment else None
            created_at_value = row["created_at"]
            if isinstance(created_at_value, datetime):
                created_at_value = created_at_value.isoformat()
            elif created_at_value is not None:
                created_at_value = str(created_at_value)
            if not created_at_value:
                created_at_value = ""
            records.append(
                {
                    "import_id": str(row["id"]),
                    "batch_id": row["batch_id"] or "",
                    "class_id": row["class_id"],
                    "class_name": class_info.name if class_info else None,
                    "assignment_id": row["assignment_id"],
                    "assignment_title": assignment_title,
                    "student_count": row["student_count"] or 0,
                    "status": row["status"] or "unknown",
                    "created_at": created_at_value,
                    "revoked_at": row["revoked_at"],
                }
            )
    except Exception as exc:
        logger.warning(f"grading import records read failed: {exc}")

    records = sorted(records, key=lambda item: item.get("created_at") or "", reverse=True)
    return GradingHistoryResponse(records=[GradingImportRecord(**record) for record in records])


async def _get_student_results_from_runs(batch_id: str) -> List[Dict[str, Any]]:
    """从 runs 表获取学生批改结果（作为 student_grading_results 的备选）
    
    runs 表的 run_id 格式为 batch_grading_{batch_id}
    output_data 包含 student_results 数组
    """
    if not db.is_available:
        return []
    
    try:
        run_id = f"batch_grading_{batch_id}"
        query = "SELECT output_data FROM runs WHERE run_id = %s"
        
        async with db.connection() as conn:
            cursor = await conn.execute(query, (run_id,))
            row = await cursor.fetchone()
        
        if not row or not row["output_data"]:
            return []
        
        output_data = row["output_data"]
        if isinstance(output_data, str):
            output_data = json.loads(output_data)
        
        student_results = output_data.get("student_results", [])
        logger.info(f"从 runs 表获取学生结果: batch_id={batch_id}, count={len(student_results)}")
        return student_results
    except Exception as e:
        logger.warning(f"从 runs 表获取学生结果失败: {e}")
        return []


@router.get(
    "/grading/history/{import_id}",
    response_model=GradingHistoryDetailResponse,
    tags=["Grading History"],
)
async def get_grading_history_detail(import_id: str):
    """Get grading history detail - 优先从 PostgreSQL 读取"""

    # 1. 优先尝试 PostgreSQL (使用异步版本)
    if db.is_available:
        try:
            # 尝试通过 batch_id 查找（import_id 可能是 history.id 或 batch_id）
            pg_history = await get_grading_history_async(import_id)
            if pg_history:
                class_ids = pg_history.class_ids or []
                result_data = pg_history.result_data or {}
                if not isinstance(result_data, dict):
                    result_data = {}
                class_id = class_ids[0] if class_ids else ""
                class_info = get_class_by_id(class_id) if class_id else None
                assignment_id_value = result_data.get("homework_id") or result_data.get(
                    "assignment_id"
                )
                assignment_title = None
                if assignment_id_value:
                    assignment = get_homework(assignment_id_value)
                    assignment_title = assignment.title if assignment else None
                created_at_value = pg_history.created_at
                if isinstance(created_at_value, datetime):
                    created_at_value = created_at_value.isoformat()
                elif created_at_value is not None:
                    created_at_value = str(created_at_value)
                if not created_at_value:
                    created_at_value = ""
                record = {
                    "import_id": str(pg_history.id),
                    "batch_id": pg_history.batch_id or "",
                    "class_id": class_id,
                    "class_name": class_info.name if class_info else None,
                    "assignment_id": assignment_id_value,
                    "assignment_title": assignment_title,
                    "student_count": pg_history.total_students or 0,
                    "status": pg_history.status or "unknown",
                    "created_at": created_at_value,
                    "revoked_at": None,
                }
                items = []
                # 使用异步版本获取学生结果
                pg_results = await get_student_results_async(pg_history.id)
                
                # 如果 student_grading_results 为空，尝试从 runs 表获取
                if not pg_results and pg_history.batch_id:
                    runs_results = await _get_student_results_from_runs(pg_history.batch_id)
                    for idx, student_data in enumerate(runs_results):
                        student_name = (
                            student_data.get("student_name")
                            or student_data.get("studentName")
                            or student_data.get("student_key")
                            or f"Student {idx + 1}"
                        )
                        # 构建 result 对象，包含分数信息
                        result = {
                            "total_score": student_data.get("total_score"),
                            "max_score": student_data.get("max_total_score") or student_data.get("max_score"),
                            "percentage": student_data.get("percentage"),
                            "student_name": student_name,
                            "question_results": student_data.get("question_results", []),
                        }
                        items.append(
                            {
                                "item_id": str(uuid.uuid4()),
                                "import_id": str(pg_history.id),
                                "batch_id": pg_history.batch_id,
                                "class_id": class_id,
                                "student_id": student_data.get("student_id") or "",
                                "student_name": student_name,
                                "status": "imported",
                                "created_at": pg_history.created_at,
                                "revoked_at": None,
                                "result": result,
                            }
                        )
                    logger.info(
                        f"从 runs 表读取学生结果: batch_id={pg_history.batch_id}, items={len(items)}"
                    )
                else:
                    # 使用 student_grading_results 表的数据
                    for idx, item in enumerate(pg_results):
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
                        items.append(
                            {
                                "item_id": str(item.id),
                                "import_id": str(pg_history.id),
                                "batch_id": pg_history.batch_id,
                                "class_id": class_id,
                                "student_id": item.student_id or "",
                                "student_name": student_name,
                                "status": "revoked" if item.revoked_at else "imported",
                                "created_at": item.imported_at or pg_history.created_at,
                                "revoked_at": item.revoked_at,
                                "result": result,
                            }
                        )
                logger.info(
                    f"从 PostgreSQL 读取批改详情: import_id={import_id}, items={len(items)}"
                )
                return GradingHistoryDetailResponse(
                    record=GradingImportRecord(**record),
                    items=[GradingImportItem(**item) for item in items],
                )
        except Exception as exc:
            logger.warning(f"PostgreSQL grading detail read failed: {exc}")

    # 2. Fallback detail
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM grading_history WHERE id = ?", (import_id,)
            ).fetchone()
        if row:
            # 安全解析 JSON 字段（可能已经是 dict）
            raw_class_ids = row["class_ids"]
            if isinstance(raw_class_ids, str):
                class_ids = json.loads(raw_class_ids) if raw_class_ids else []
            elif isinstance(raw_class_ids, list):
                class_ids = raw_class_ids
            else:
                class_ids = []

            raw_result_data = row["result_data"]
            if isinstance(raw_result_data, str):
                result_data = json.loads(raw_result_data) if raw_result_data else {}
            elif isinstance(raw_result_data, dict):
                result_data = raw_result_data
            else:
                result_data = {}

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
            for idx, item in enumerate(get_student_results(row["id"])):
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
                items.append(
                    {
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
                    }
                )
            return GradingHistoryDetailResponse(
                record=GradingImportRecord(**record),
                items=[GradingImportItem(**item) for item in items],
            )
    except Exception as exc:
        logger.warning("grading history detail read failed: %s", exc)

    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM grading_imports WHERE id = ?", (import_id,)
            ).fetchone()
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
                    items.append(
                        {
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
                        }
                    )

                return GradingHistoryDetailResponse(
                    record=GradingImportRecord(**record),
                    items=[GradingImportItem(**item) for item in items],
                )
    except Exception as exc:
        logger.warning("import detail read failed: %s", exc)

    raise HTTPException(status_code=404, detail="Record not found")


@router.post(
    "/grading/import/{import_id}/revoke",
    response_model=GradingImportRecord,
    tags=["Grading History"],
)
async def revoke_grading_import(import_id: str, request: GradingRevokeRequest):
    """Revoke import record."""
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM grading_history WHERE id = ?", (import_id,)
            ).fetchone()
        if row:
            now = datetime.utcnow().isoformat()
            with get_connection() as conn:
                conn.execute(
                    "UPDATE student_grading_results SET revoked_at = ? WHERE grading_history_id = ? AND revoked_at IS NULL",
                    (now, import_id),
                )
                conn.execute(
                    "UPDATE grading_history SET status = 'revoked' WHERE id = ?", (import_id,)
                )
            raw_class_ids = row["class_ids"]
            if isinstance(raw_class_ids, str):
                class_ids = json.loads(raw_class_ids) if raw_class_ids else []
            elif isinstance(raw_class_ids, list):
                class_ids = raw_class_ids
            else:
                class_ids = []
            raw_result_data = row["result_data"]
            if isinstance(raw_result_data, str):
                result_data = json.loads(raw_result_data) if raw_result_data else {}
            elif isinstance(raw_result_data, dict):
                result_data = raw_result_data
            else:
                result_data = {}
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
        logger.warning("database operation: %s", exc)

    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM grading_imports WHERE id = ?", (import_id,)
            ).fetchone()
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
        logger.warning("database operation: %s", exc)

    raise HTTPException(status_code=404, detail="Record not found")


def _build_wrong_question_prompt(context: Dict[str, Any], images: Optional[List[str]] = None) -> str:
    """构建错题深究的增强提示"""
    prompt_parts = []
    
    prompt_parts.append("学生想要深究一道错题，请帮助分析错误原因并启发学生理解。")
    prompt_parts.append("")
    
    if context.get("questionId"):
        prompt_parts.append(f"**题目编号**: Q{context['questionId']}")
    if context.get("score") is not None and context.get("maxScore") is not None:
        prompt_parts.append(f"**得分**: {context['score']}/{context['maxScore']}")
    if context.get("subject"):
        prompt_parts.append(f"**科目**: {context['subject']}")
    if context.get("topic"):
        prompt_parts.append(f"**题型/知识点**: {context['topic']}")
    
    if context.get("studentAnswer"):
        prompt_parts.append(f"\n**学生答案**:\n{context['studentAnswer']}")
    
    if context.get("feedback"):
        prompt_parts.append(f"\n**批改反馈**:\n{context['feedback']}")
    
    scoring_points = context.get("scoringPointResults") or []
    if scoring_points:
        prompt_parts.append("\n**评分点明细**:")
        for idx, sp in enumerate(scoring_points):
            awarded = sp.get("awarded", 0)
            max_points = sp.get("max_points") or sp.get("maxPoints") or 1
            status = "✓" if awarded >= max_points else ("△" if awarded > 0 else "✗")
            desc = sp.get("description") or f"得分点{idx + 1}"
            evidence = sp.get("evidence") or ""
            prompt_parts.append(f"  {status} {desc}: {awarded}/{max_points} - {evidence}")
    
    if images and len(images) > 0:
        prompt_parts.append(f"\n**附带图片**: {len(images)} 张（包含题目原文和学生作答）")
        prompt_parts.append("请仔细分析图片中的题目内容和学生的作答过程。")
    
    prompt_parts.append("\n请按以下步骤帮助学生：")
    prompt_parts.append("1. 分析学生的错误原因（是概念理解问题、计算错误、还是审题不清？）")
    prompt_parts.append("2. 用苏格拉底式提问引导学生思考正确的解题思路")
    prompt_parts.append("3. 分解相关知识点，帮助学生建立第一性原理的理解")
    prompt_parts.append("4. 最后给出一道类似的练习题让学生巩固")
    
    return "\n".join(prompt_parts)


@router.post("/assistant/chat", response_model=AssistantChatResponse, tags=["Student Assistant"])
async def assistant_chat(request: AssistantChatRequest):
    """Student assistant chat with Socratic questioning and mastery assessment.
    
    支持多模态输入：
    - images: base64 编码的图片列表（用于错题分析）
    - wrong_question_context: 错题上下文（从错题本跳转时传入）
    """
    context = _build_student_context(request.student_id, request.class_id)
    
    # 如果有错题上下文，增强学生上下文
    if request.wrong_question_context:
        context["wrong_question_context"] = request.wrong_question_context
    
    agent = get_student_assistant_agent()

    session_id = build_assistant_session_id(request.student_id, request.class_id)
    memory = AssistantMemory(session_id)
    history_messages: List[BaseMessage] = []
    
    # 如果有错题上下文，清空历史记录开启新会话
    if request.wrong_question_context:
        try:
            await memory.clear()
        except Exception as exc:
            logger.debug("Assistant memory clear failed: %s", exc)
    else:
        try:
            history_messages = await memory.load()
        except Exception as exc:
            logger.debug("Assistant memory load failed: %s", exc)

    if not history_messages:
        seed_messages = _history_from_request(request.history, request.message)
        if seed_messages:
            try:
                await memory.append(seed_messages)
                history_messages = await memory.load()
            except Exception as exc:
                logger.debug("Assistant memory seed failed: %s", exc)
                history_messages = seed_messages

    prompt_history = list(history_messages)
    
    # 构建消息内容
    message_content = request.message
    
    # 如果有错题上下文，构建增强提示
    if request.wrong_question_context:
        enhanced_prompt = _build_wrong_question_prompt(
            request.wrong_question_context, 
            request.images
        )
        message_content = f"{enhanced_prompt}\n\n学生的问题: {request.message}"
        
        # 添加系统提示，指导 AI 进入错题深究模式
        prompt_history.append(
            SystemMessage(
                content=(
                    "Student is reviewing a wrong question from their error book. "
                    "Focus on understanding their specific mistake, use Socratic questioning to guide them, "
                    "and help them build first-principles understanding. "
                    "Be encouraging but rigorous. Analyze any provided images carefully."
                ),
            )
        )
    elif _is_confused_message(request.message):
        prompt_history.append(
            SystemMessage(
                content=(
                    "Student indicates they are stuck. Provide a brief explanation of the missing concept, "
                    "then ask a simpler Socratic question."
                ),
            )
        )

    # 调用 agent（目前不支持图片，但消息中包含了图片描述）
    # TODO: 未来可以升级为多模态 LLM 调用
    result = await agent.ainvoke(
        message=message_content,
        student_context=context,
        session_mode=request.session_mode or "learning",
        concept_topic=request.concept_topic or "general",
        history=prompt_history,
    )

    assistant_content = result.raw_content
    if result.parsed and result.parsed.content:
        assistant_content = result.parsed.content
    try:
        await memory.append(
            [
                HumanMessage(content=request.message),
                AIMessage(content=assistant_content),
            ]
        )
    except Exception as exc:
        logger.debug("Assistant memory append failed: %s", exc)

    if not result.parsed:
        return AssistantChatResponse(
            content=result.raw_content,
            model=result.model,
            usage=result.usage or {},
            response_type="chat",
        )

    mastery_data = None
    if result.parsed.mastery:
        mastery: AssistantMastery = result.parsed.mastery
        mastery_data = MasteryData(
            score=mastery.score,
            level=mastery.level or "developing",
            analysis=mastery.analysis or "",
            evidence=mastery.evidence or [],
            suggestions=mastery.suggestions or [],
        )

    def _convert_concept(node: AssistantConceptNode) -> ConceptNode:
        return ConceptNode(
            id=node.id or str(uuid.uuid4())[:8],
            name=node.name or "",
            description=node.description or "",
            understood=bool(node.understood),
            children=(
                [_convert_concept(child) for child in node.children] if node.children else None
            ),
        )

    concept_nodes = None
    if result.parsed.concept_breakdown:
        concept_nodes = [_convert_concept(node) for node in result.parsed.concept_breakdown]
        try:
            flattened = _flatten_concepts(result.parsed.concept_breakdown)
            upsert_assistant_concepts(request.student_id, request.class_id, flattened)
        except Exception as exc:
            logger.warning("Assistant concept persistence failed: %s", exc)

    if mastery_data:
        try:
            save_assistant_mastery_snapshot(
                request.student_id,
                request.class_id,
                mastery_data.dict(),
            )
        except Exception as exc:
            logger.warning("Assistant mastery persistence failed: %s", exc)

    await _invalidate_assistant_progress_cache(request.student_id, request.class_id)

    return AssistantChatResponse(
        content=result.parsed.content or result.raw_content,
        model=result.model,
        usage=result.usage or {},
        mastery=mastery_data,
        next_question=result.parsed.next_question,
        question_options=result.parsed.question_options,
        focus_mode=result.parsed.focus_mode,
        concept_breakdown=concept_nodes,
        response_type=result.parsed.response_type or "chat",
    )


@router.get(
    "/assistant/progress", response_model=AssistantProgressResponse, tags=["Student Assistant"]
)
async def assistant_progress(student_id: str, class_id: Optional[str] = None):
    """Fetch persisted assistant progress for a student."""
    cached = await _load_assistant_progress_cache(student_id, class_id)
    if cached:
        return AssistantProgressResponse(**cached)

    concept_rows: List[Dict[str, Any]] = []
    mastery_rows: List[Dict[str, Any]] = []
    try:
        concept_rows = list_assistant_concepts(student_id, class_id)
        mastery_rows = list_assistant_mastery_snapshots(student_id, class_id, limit=6)
    except Exception as exc:
        logger.warning("Assistant progress read failed: %s", exc)

    response = AssistantProgressResponse(
        student_id=student_id,
        class_id=class_id,
        concept_breakdown=_build_concept_tree(concept_rows),
        mastery_history=[MasterySnapshot(**item) for item in mastery_rows],
    )

    await _store_assistant_progress_cache(student_id, class_id, response.dict())
    return response


# ============ Error Analysis (IntelliLearn) ============


@router.post(
    "/v1/analysis/submit-error", response_model=ErrorAnalysisResponse, tags=["Error Analysis"]
)
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


@router.get(
    "/v1/diagnosis/report/{student_id}",
    response_model=DiagnosisReportResponse,
    tags=["Error Analysis"],
)
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

    with get_connection() as conn:
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
                q.get("questionId") or q.get("question_id") or q.get("id") or q.get("qid") or ""
            ).strip()
            question_text = (
                q.get("questionText") or q.get("question") or q.get("prompt") or q.get("stem") or ""
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
        problems_seed.append(
            {
                "id": question_id,
                "question": entry["question"],
                "errorRate": f"{error_rate * 100:.1f}%",
                "wrong": wrong,
                "total": total,
            }
        )

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
            LLMMessage(
                role="user", content=json.dumps({"problems": problems_seed}, ensure_ascii=False)
            ),
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

    with get_connection() as conn:
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
        histories = list_grading_history(class_id=class_id, limit=200)
        history_ids = []
        for history in histories:
            result_meta = history.result_data or {}
            assignment_id_value = result_meta.get("homework_id") or result_meta.get("assignment_id")
            if homework_id and assignment_id_value != homework_id:
                continue
            history_ids.append(history.id)

        fallback_scores = []
        for history_id in history_ids:
            for item in get_student_results(history_id):
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

    students = {
        s.id: {"id": s.id, "name": s.name or s.username or s.id, "scores": {}}
        for s in list_class_students(class_id)
    }
    homeworks = list_homeworks(class_id)
    homework_titles = {hw.id: hw.title for hw in homeworks}

    with get_connection() as conn:
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


# ============ 错题本手动录入 API ============

# 内存存储（生产环境应使用数据库）
_MANUAL_WRONG_QUESTIONS: Dict[str, Dict[str, Any]] = {}


@router.post("/wrongbook/add", response_model=ManualWrongQuestionResponse, tags=["错题本"])
async def add_manual_wrong_question(request: ManualWrongQuestionCreate):
    """手动录入错题（拍照/上传）"""
    question_id = request.question_id or f"Q{len(_MANUAL_WRONG_QUESTIONS) + 1}"
    entry_id = str(uuid.uuid4())
    
    # 处理图片：保存到存储目录
    saved_images: List[str] = []
    for idx, img_data in enumerate(request.images):
        if not img_data:
            continue
        try:
            # 解析 base64 图片
            if "," in img_data and img_data.startswith("data:"):
                img_data = img_data.split(",", 1)[1]
            img_bytes = base64.b64decode(img_data)
            
            # 保存到文件
            img_dir = UPLOAD_DIR / "wrongbook" / request.student_id
            img_dir.mkdir(parents=True, exist_ok=True)
            img_path = img_dir / f"{entry_id}_{idx}.jpg"
            
            # 转换为 JPEG
            jpeg_bytes = to_jpeg_bytes(img_bytes)
            img_path.write_bytes(jpeg_bytes)
            
            # 返回相对路径或 base64
            saved_images.append(f"data:image/jpeg;base64,{base64.b64encode(jpeg_bytes).decode('ascii')}")
        except Exception as exc:
            logger.warning(f"Failed to save image: {exc}")
            # 保留原始 base64
            if request.images[idx]:
                saved_images.append(request.images[idx])
    
    entry = {
        "id": entry_id,
        "student_id": request.student_id,
        "class_id": request.class_id,
        "question_id": question_id,
        "subject": request.subject,
        "topic": request.topic,
        "question_content": request.question_content,
        "student_answer": request.student_answer,
        "correct_answer": request.correct_answer,
        "score": request.score,
        "max_score": request.max_score,
        "feedback": request.feedback,
        "images": saved_images,
        "tags": request.tags,
        "source": "manual",
        "created_at": datetime.utcnow().isoformat(),
    }
    
    _MANUAL_WRONG_QUESTIONS[entry_id] = entry
    
    return ManualWrongQuestionResponse(**entry)


@router.get("/wrongbook/list", response_model=ManualWrongQuestionListResponse, tags=["错题本"])
async def list_manual_wrong_questions(
    student_id: str,
    class_id: Optional[str] = None,
    subject: Optional[str] = None,
    limit: int = 100,
):
    """获取手动录入的错题列表"""
    questions = []
    
    for entry in _MANUAL_WRONG_QUESTIONS.values():
        if entry["student_id"] != student_id:
            continue
        if class_id and entry.get("class_id") != class_id:
            continue
        if subject and entry.get("subject") != subject:
            continue
        questions.append(ManualWrongQuestionResponse(**entry))
    
    # 按创建时间倒序
    questions.sort(key=lambda x: x.created_at, reverse=True)
    
    return ManualWrongQuestionListResponse(
        questions=questions[:limit],
        total=len(questions),
    )


@router.delete("/wrongbook/{entry_id}", tags=["错题本"])
async def delete_manual_wrong_question(entry_id: str, student_id: str):
    """删除手动录入的错题"""
    entry = _MANUAL_WRONG_QUESTIONS.get(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="错题不存在")
    if entry["student_id"] != student_id:
        raise HTTPException(status_code=403, detail="无权删除此错题")
    
    del _MANUAL_WRONG_QUESTIONS[entry_id]
    return {"success": True, "message": "删除成功"}


@router.put("/wrongbook/{entry_id}", response_model=ManualWrongQuestionResponse, tags=["错题本"])
async def update_manual_wrong_question(entry_id: str, request: ManualWrongQuestionCreate):
    """更新手动录入的错题"""
    entry = _MANUAL_WRONG_QUESTIONS.get(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="错题不存在")
    if entry["student_id"] != request.student_id:
        raise HTTPException(status_code=403, detail="无权修改此错题")
    
    # 更新字段
    entry.update({
        "class_id": request.class_id,
        "question_id": request.question_id or entry["question_id"],
        "subject": request.subject,
        "topic": request.topic,
        "question_content": request.question_content,
        "student_answer": request.student_answer,
        "correct_answer": request.correct_answer,
        "score": request.score,
        "max_score": request.max_score,
        "feedback": request.feedback,
        "tags": request.tags,
    })
    
    # 如果有新图片，更新图片
    if request.images:
        saved_images: List[str] = []
        for idx, img_data in enumerate(request.images):
            if not img_data:
                continue
            try:
                if "," in img_data and img_data.startswith("data:"):
                    img_data = img_data.split(",", 1)[1]
                img_bytes = base64.b64decode(img_data)
                jpeg_bytes = to_jpeg_bytes(img_bytes)
                saved_images.append(f"data:image/jpeg;base64,{base64.b64encode(jpeg_bytes).decode('ascii')}")
            except Exception:
                saved_images.append(request.images[idx])
        entry["images"] = saved_images
    
    return ManualWrongQuestionResponse(**entry)


# ============ 常错知识点 AI 总结 ============

class SummarizeMistakesRequest(BaseModel):
    """常错知识点总结请求"""
    feedbacks: List[str] = Field(..., description="错题反馈列表")
    assignment_title: str = Field(default="作业", description="作业标题")


class SummarizeMistakesResponse(BaseModel):
    """常错知识点总结响应"""
    summary: str = Field(..., description="AI 总结的常错知识点")
    question_count: int = Field(default=0, description="分析的错题数量")


@router.post("/assistant/summarize-mistakes", response_model=SummarizeMistakesResponse, tags=["Student Assistant"])
async def summarize_common_mistakes(request: SummarizeMistakesRequest):
    """AI 总结学生常错知识点
    
    基于全班错题的 feedback，使用 Gemini Flash 总结常见错误类型和知识点薄弱环节。
    """
    import os
    import httpx
    
    feedbacks = request.feedbacks
    if not feedbacks:
        return SummarizeMistakesResponse(
            summary="本次作业没有错题反馈数据，全班表现优秀！",
            question_count=0
        )
    
    # 去重并限制数量
    unique_feedbacks = list(set(feedbacks))[:50]
    
    # 构建 prompt
    prompt = f"""你是一位经验丰富的教师，正在分析学生作业的错题反馈。

作业名称：{request.assignment_title}
错题反馈数量：{len(feedbacks)} 条（去重后 {len(unique_feedbacks)} 条）

以下是学生答错题目的批改反馈：
{chr(10).join([f"- {fb}" for fb in unique_feedbacks])}

请分析这些错题反馈，总结出：
1. **常见错误类型**：学生最容易犯的错误有哪些？（列出3-5个主要错误类型）
2. **知识点薄弱环节**：哪些知识点学生掌握不牢？（列出需要重点复习的知识点）

请用简洁的中文回答，使用 markdown 格式，重点突出，不要给出教学建议。"""

    # 调用 OpenRouter API (Gemini Flash)
    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    model = os.getenv("LLM_SUMMARY_MODEL", "google/gemini-2.0-flash-001")
    
    if not api_key:
        # 如果没有 API key，返回简单的本地总结
        summary = f"本次作业共有 {len(feedbacks)} 条错题反馈。\n\n"
        summary += "**常见问题类型：**\n"
        for i, fb in enumerate(unique_feedbacks[:10], 1):
            summary += f"{i}. {fb[:100]}{'...' if len(fb) > 100 else ''}\n"
        return SummarizeMistakesResponse(
            summary=summary,
            question_count=len(feedbacks)
        )
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 1500,
                }
            )
            response.raise_for_status()
            data = response.json()
            
            summary = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if not summary:
                summary = "AI 分析失败，请稍后重试。"
            
            return SummarizeMistakesResponse(
                summary=summary,
                question_count=len(feedbacks)
            )
    except Exception as e:
        logger.error(f"AI 总结失败: {e}")
        # 返回简单的本地总结
        summary = f"本次作业共有 {len(feedbacks)} 条错题反馈。\n\n"
        summary += "**常见问题类型：**\n"
        for i, fb in enumerate(unique_feedbacks[:10], 1):
            summary += f"{i}. {fb[:100]}{'...' if len(fb) > 100 else ''}\n"
        return SummarizeMistakesResponse(
            summary=summary,
            question_count=len(feedbacks)
        )
