"""
GradeOS 统一 API 路由
整合所有子系统的 API 接口
"""

import asyncio
import base64
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from pydantic import BaseModel

from src.api.dependencies import get_orchestrator
from src.orchestration.base import Orchestrator
from src.api.routes.batch_langgraph import _format_results_for_frontend
from src.utils.image import to_jpeg_bytes

router = APIRouter()

# 存储路径配置
UPLOAD_DIR = Path("./storage/scans")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ============ 数据模型 ============

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


class GradingImportTarget(BaseModel):
    class_id: str
    student_ids: List[str]
    assignment_id: Optional[str] = None


class GradingImportRequest(BaseModel):
    batch_id: str
    targets: List[GradingImportTarget]


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


# ============ In-memory stores ============

CLASSES: Dict[str, Dict[str, Any]] = {}
CLASS_STUDENTS: Dict[str, List[StudentInfo]] = {}
HOMEWORKS: Dict[str, Dict[str, Any]] = {}
SUBMISSIONS: Dict[str, List[Dict[str, Any]]] = {}
GRADING_IMPORTS: Dict[str, Dict[str, Any]] = {}
GRADING_IMPORT_ITEMS: Dict[str, Dict[str, Any]] = {}
HOMEWORK_GRADING_TASKS: Dict[str, asyncio.Task] = {}


def _ensure_seed_data() -> None:
    if CLASSES:
        return
    class_a = ClassResponse(
        class_id="c-001",
        class_name="Advanced Physics 2024",
        teacher_id="t-001",
        invite_code="PHY24A",
        student_count=3,
    ).dict()
    class_b = ClassResponse(
        class_id="c-002",
        class_name="Mathematics Grade 11",
        teacher_id="t-001",
        invite_code="MTH11B",
        student_count=3,
    ).dict()
    CLASSES[class_a["class_id"]] = class_a
    CLASSES[class_b["class_id"]] = class_b

    CLASS_STUDENTS[class_a["class_id"]] = [
        StudentInfo(id="s-001", name="Alice Chen", username="alice"),
        StudentInfo(id="s-002", name="Bob Wang", username="bob"),
        StudentInfo(id="s-003", name="Carol Liu", username="carol"),
    ]
    CLASS_STUDENTS[class_b["class_id"]] = [
        StudentInfo(id="s-004", name="David Zhang", username="david"),
        StudentInfo(id="s-005", name="Eva Li", username="eva"),
        StudentInfo(id="s-006", name="Frank Zhao", username="frank"),
    ]


def _parse_deadline(deadline: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(deadline)
    except ValueError:
        parsed = datetime.strptime(deadline, "%Y-%m-%d")
    if parsed.hour == 0 and parsed.minute == 0 and parsed.second == 0:
        parsed = parsed.replace(hour=23, minute=59, second=59)
    return parsed


def _get_student_map(class_id: str) -> Dict[str, str]:
    students = CLASS_STUDENTS.get(class_id, [])
    return {student.id: student.name for student in students}


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
    homework = HOMEWORKS.get(homework_id)
    if not homework or homework.get("grading_triggered"):
        return None

    class_id = homework["class_id"]
    submissions = SUBMISSIONS.get(homework_id, [])
    if not submissions:
        return None

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=400, detail="未配置 GEMINI_API_KEY")

    answer_images: List[bytes] = []
    manual_boundaries: List[Dict[str, Any]] = []
    page_cursor = 0
    for submission in submissions:
        images = submission.get("images", [])
        if not images:
            continue
        pages = list(range(page_cursor, page_cursor + len(images)))
        manual_boundaries.append({
            "student_id": submission["student_id"],
            "student_key": submission["student_name"],
            "pages": pages,
        })
        answer_images.extend(images)
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
            "expected_students": len(CLASS_STUDENTS.get(class_id, [])) or len(manual_boundaries),
        },
    }

    await orchestrator.start_run(
        graph_name="batch_grading",
        payload=payload,
        idempotency_key=batch_id,
    )

    homework["grading_triggered"] = True
    homework["grading_batch_id"] = batch_id
    homework["grading_triggered_at"] = datetime.utcnow().isoformat()
    return batch_id


async def _schedule_deadline_grading(homework_id: str, deadline: datetime, orchestrator: Orchestrator) -> None:
    delay = (deadline - datetime.utcnow()).total_seconds()
    if delay > 0:
        await asyncio.sleep(delay)
    await _trigger_homework_grading(homework_id, orchestrator)


async def _maybe_trigger_grading(homework_id: str, orchestrator: Orchestrator) -> None:
    homework = HOMEWORKS.get(homework_id)
    if not homework or homework.get("grading_triggered"):
        return
    deadline = _parse_deadline(homework["deadline"])
    allow_early = homework.get("allow_early_grading", False)
    submissions = SUBMISSIONS.get(homework_id, [])
    total_students = len(CLASS_STUDENTS.get(homework["class_id"], []))

    if allow_early and total_students > 0 and len(submissions) >= total_students:
        await _trigger_homework_grading(homework_id, orchestrator)
        task = HOMEWORK_GRADING_TASKS.pop(homework_id, None)
        if task:
            task.cancel()
        return

    if not allow_early and datetime.utcnow() >= deadline:
        await _trigger_homework_grading(homework_id, orchestrator)

# ============ 认证接口 ============

@router.post("/auth/login", response_model=UserResponse, tags=["认证"])
async def login(request: LoginRequest):
    """用户登录"""
    # Mock 实现
    mock_users = {
        "teacher": {"user_id": "t-001", "name": "Demo Teacher", "user_type": "teacher", "class_ids": ["c-001"]},
        "student": {"user_id": "s-001", "name": "Demo Student", "user_type": "student", "class_ids": ["c-001"]},
    }
    
    if request.username in mock_users and request.password == "123456":
        user = mock_users[request.username]
        return UserResponse(username=request.username, **user)
    
    raise HTTPException(status_code=401, detail="Invalid credentials")


@router.get("/user/info", response_model=UserResponse, tags=["认证"])
async def get_user_info(user_id: str):
    """获取用户信息"""
    return UserResponse(
        user_id=user_id,
        username="demo",
        name="Demo User",
        user_type="student",
        class_ids=["c-001"]
    )


# ============ 班级管理接口 ============

@router.get("/class/my", response_model=List[ClassResponse], tags=["班级管理"])
async def get_my_classes(student_id: str):
    """获取学生加入的班级"""
    _ensure_seed_data()
    classes: List[ClassResponse] = []
    for class_id, students in CLASS_STUDENTS.items():
        if any(student.id == student_id for student in students):
            data = CLASSES.get(class_id)
            if data:
                classes.append(ClassResponse(**data))
    return classes


@router.post("/class/join", tags=["班级管理"])
async def join_class(request: JoinClassRequest):
    """学生加入班级"""
    _ensure_seed_data()
    class_info = next(
        (c for c in CLASSES.values() if c["invite_code"] == request.code),
        None,
    )
    if not class_info:
        raise HTTPException(status_code=404, detail="班级不存在")
    class_id = class_info["class_id"]
    students = CLASS_STUDENTS.setdefault(class_id, [])
    if not any(s.id == request.student_id for s in students):
        students.append(StudentInfo(id=request.student_id, name=f"Student {request.student_id}", username=request.student_id))
        class_info["student_count"] = len(students)
    return {
        "success": True,
        "class": {
            "id": class_id,
            "name": class_info["class_name"],
        },
    }


@router.get("/teacher/classes", response_model=List[ClassResponse], tags=["班级管理"])
async def get_teacher_classes(teacher_id: str):
    """获取教师的班级列表"""
    _ensure_seed_data()
    classes = [
        ClassResponse(**data)
        for data in CLASSES.values()
        if data["teacher_id"] == teacher_id
    ]
    return classes


@router.post("/teacher/classes", response_model=ClassResponse, tags=["班级管理"])
async def create_class(request: ClassCreate):
    """创建班级"""
    import random
    import string
    invite_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    
    class_id = str(uuid.uuid4())[:8]
    class_record = ClassResponse(
        class_id=class_id,
        class_name=request.name,
        teacher_id=request.teacher_id,
        invite_code=invite_code,
        student_count=0
    )
    CLASSES[class_id] = class_record.dict()
    CLASS_STUDENTS[class_id] = []
    return class_record


@router.get("/class/students", tags=["班级管理"])
async def get_class_students(class_id: str):
    """获取班级学生列表"""
    _ensure_seed_data()
    students = CLASS_STUDENTS.get(class_id, [])
    return [student.dict() for student in students]


# ============ 作业管理接口 ============

@router.get("/homework/list", response_model=List[HomeworkResponse], tags=["作业管理"])
async def get_homework_list(class_id: Optional[str] = None, student_id: Optional[str] = None):
    """获取作业列表"""
    _ensure_seed_data()
    records = list(HOMEWORKS.values())
    if class_id:
        records = [record for record in records if record["class_id"] == class_id]
    return [HomeworkResponse(**record) for record in records]


@router.get("/homework/detail/{homework_id}", response_model=HomeworkResponse, tags=["作业管理"])
async def get_homework_detail(homework_id: str):
    """获取作业详情"""
    record = HOMEWORKS.get(homework_id)
    if not record:
        raise HTTPException(status_code=404, detail="作业不存在")
    return HomeworkResponse(**record)


@router.post("/homework/create", response_model=HomeworkResponse, tags=["作业管理"])
async def create_homework(
    request: HomeworkCreate,
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    """创建作业"""
    _ensure_seed_data()
    class_info = CLASSES.get(request.class_id)
    if not class_info:
        raise HTTPException(status_code=404, detail="班级不存在")

    homework_id = str(uuid.uuid4())[:8]
    record = HomeworkResponse(
        homework_id=homework_id,
        class_id=request.class_id,
        class_name=class_info["class_name"],
        title=request.title,
        description=request.description,
        deadline=request.deadline,
        allow_early_grading=request.allow_early_grading,
        created_at=datetime.now().isoformat(),
    ).dict()
    record["grading_triggered"] = False
    record["grading_batch_id"] = None
    HOMEWORKS[homework_id] = record

    deadline_dt = _parse_deadline(request.deadline)
    if orchestrator:
        task = asyncio.create_task(_schedule_deadline_grading(homework_id, deadline_dt, orchestrator))
        HOMEWORK_GRADING_TASKS[homework_id] = task

    return HomeworkResponse(**record)


@router.post("/homework/submit", response_model=SubmissionResponse, tags=["作业管理"])
async def submit_homework(request: SubmissionCreate):
    """提交作业（文本）"""
    _ensure_seed_data()
    if request.homework_id not in HOMEWORKS:
        raise HTTPException(status_code=404, detail="作业不存在")

    submission_id = str(uuid.uuid4())[:8]
    submission_record = {
        "submission_id": submission_id,
        "homework_id": request.homework_id,
        "student_id": request.student_id,
        "student_name": request.student_name,
        "submitted_at": datetime.now().isoformat(),
        "status": "submitted",
        "content": request.content,
        "images": [],
    }
    SUBMISSIONS.setdefault(request.homework_id, []).append(submission_record)

    return SubmissionResponse(
        submission_id=submission_id,
        homework_id=request.homework_id,
        student_id=request.student_id,
        student_name=request.student_name,
        submitted_at=submission_record["submitted_at"],
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
    _ensure_seed_data()
    if request.homework_id not in HOMEWORKS:
        raise HTTPException(status_code=404, detail="作业不存在")

    submission_id = str(uuid.uuid4())[:8]
    
    # 创建提交目录
    submission_dir = UPLOAD_DIR / submission_id
    submission_dir.mkdir(parents=True, exist_ok=True)
    
    saved_paths = []
    
    images_bytes: List[bytes] = []
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
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"图片 {idx + 1} 处理失败: {str(e)}")
    
    submission_record = {
        "submission_id": submission_id,
        "homework_id": request.homework_id,
        "student_id": request.student_id,
        "student_name": request.student_name,
        "submitted_at": datetime.now().isoformat(),
        "status": "submitted",
        "images": images_bytes,
        "image_paths": saved_paths,
    }
    SUBMISSIONS.setdefault(request.homework_id, []).append(submission_record)

    if orchestrator:
        await _maybe_trigger_grading(request.homework_id, orchestrator)

    return SubmissionResponse(
        submission_id=submission_id,
        homework_id=request.homework_id,
        student_id=request.student_id,
        student_name=request.student_name,
        submitted_at=submission_record["submitted_at"],
        status="submitted",
        score=None,
        feedback=None,
    )


@router.get("/homework/submissions", response_model=List[SubmissionResponse], tags=["作业管理"])
async def get_submissions(homework_id: str):
    """获取作业提交列表"""
    submissions = SUBMISSIONS.get(homework_id, [])
    return [
        SubmissionResponse(
            submission_id=submission["submission_id"],
            homework_id=submission["homework_id"],
            student_id=submission["student_id"],
            student_name=submission["student_name"],
            submitted_at=submission["submitted_at"],
            status=submission["status"],
            score=submission.get("score"),
            feedback=submission.get("feedback"),
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
    _ensure_seed_data()
    if not orchestrator:
        raise HTTPException(status_code=503, detail="编排器未初始化")

    formatted_results = await _get_formatted_results(request.batch_id, orchestrator)
    results_by_key = {result.get("studentName"): result for result in formatted_results}

    records: List[GradingImportRecord] = []
    now = datetime.utcnow().isoformat()

    for target in request.targets:
        if not target.student_ids:
            raise HTTPException(status_code=400, detail="必须选择学生")

        class_info = CLASSES.get(target.class_id)
        if not class_info:
            raise HTTPException(status_code=404, detail="班级不存在")

        student_map = _get_student_map(target.class_id)
        assignment_title = None
        if target.assignment_id and target.assignment_id in HOMEWORKS:
            assignment_title = HOMEWORKS[target.assignment_id]["title"]

        import_id = str(uuid.uuid4())[:8]
        record = {
            "import_id": import_id,
            "batch_id": request.batch_id,
            "class_id": target.class_id,
            "class_name": class_info["class_name"],
            "assignment_id": target.assignment_id,
            "assignment_title": assignment_title,
            "student_count": len(target.student_ids),
            "status": "imported",
            "created_at": now,
            "revoked_at": None,
        }
        GRADING_IMPORTS[import_id] = record

        for student_id in target.student_ids:
            student_name = student_map.get(student_id, student_id)
            result = results_by_key.get(student_name) or results_by_key.get(student_id)
            item_id = str(uuid.uuid4())[:8]
            GRADING_IMPORT_ITEMS[item_id] = {
                "item_id": item_id,
                "import_id": import_id,
                "batch_id": request.batch_id,
                "class_id": target.class_id,
                "student_id": student_id,
                "student_name": student_name,
                "status": "imported",
                "created_at": now,
                "revoked_at": None,
                "result": result,
            }

        records.append(GradingImportRecord(**record))

    return GradingHistoryResponse(records=records)


@router.get("/grading/history", response_model=GradingHistoryResponse, tags=["批改历史"])
async def get_grading_history(
    class_id: Optional[str] = None,
    assignment_id: Optional[str] = None,
):
    """获取批改历史列表"""
    records = list(GRADING_IMPORTS.values())
    if class_id:
        records = [record for record in records if record["class_id"] == class_id]
    if assignment_id:
        records = [record for record in records if record.get("assignment_id") == assignment_id]

    records = sorted(records, key=lambda item: item.get("created_at") or "", reverse=True)
    return GradingHistoryResponse(records=[GradingImportRecord(**record) for record in records])


@router.get("/grading/history/{import_id}", response_model=GradingHistoryDetailResponse, tags=["批改历史"])
async def get_grading_history_detail(import_id: str):
    """获取批改历史详情"""
    record = GRADING_IMPORTS.get(import_id)
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")

    items = [
        GradingImportItem(**item)
        for item in GRADING_IMPORT_ITEMS.values()
        if item["import_id"] == import_id
    ]
    return GradingHistoryDetailResponse(record=GradingImportRecord(**record), items=items)


@router.post("/grading/import/{import_id}/revoke", response_model=GradingImportRecord, tags=["批改历史"])
async def revoke_grading_import(import_id: str, request: GradingRevokeRequest):
    """撤回导入记录"""
    record = GRADING_IMPORTS.get(import_id)
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")

    if record.get("status") != "revoked":
        record["status"] = "revoked"
        record["revoked_at"] = datetime.utcnow().isoformat()
        for item in GRADING_IMPORT_ITEMS.values():
            if item["import_id"] == import_id:
                item["status"] = "revoked"
                item["revoked_at"] = record["revoked_at"]

    return GradingImportRecord(**record)


# ============ 错题分析接口 (IntelliLearn) ============

@router.post("/v1/analysis/submit-error", response_model=ErrorAnalysisResponse, tags=["错题分析"])
async def analyze_error(request: ErrorAnalysisRequest):
    """提交错题进行 AI 分析"""
    analysis_id = str(uuid.uuid4())[:8]
    
    # 模拟 AI 分析结果
    return ErrorAnalysisResponse(
        analysis_id=analysis_id,
        error_type="概念错误",
        error_severity="medium",
        root_cause="对二次函数顶点式的理解存在偏差，特别是在符号判断方面",
        knowledge_gaps=[
            {"knowledge_point": "二次函数顶点式", "mastery_level": 0.65, "confidence": 0.85},
            {"knowledge_point": "配方法", "mastery_level": 0.72, "confidence": 0.90}
        ],
        detailed_analysis={
            "step_by_step_correction": [
                "首先确认二次函数的一般形式 y=ax²+bx+c",
                "使用配方法将其转换为顶点式 y=a(x-h)²+k",
                "注意 h 的符号：当 h>0 时，图像向右平移"
            ],
            "common_mistakes": "忽略 a 的正负影响开口方向",
            "correct_solution": "正确解法详细步骤..."
        },
        recommendations={
            "immediate_actions": ["复习配方法基础", "练习顶点式转换"],
            "practice_exercises": ["练习题1", "练习题2"],
            "learning_path": {"short_term": ["本周完成顶点式专项"], "long_term": ["下月掌握二次函数全部内容"]}
        }
    )


@router.get("/v1/diagnosis/report/{student_id}", response_model=DiagnosisReportResponse, tags=["错题分析"])
async def get_diagnosis_report(student_id: str):
    """获取学生诊断报告"""
    return DiagnosisReportResponse(
        student_id=student_id,
        report_period="2024年12月",
        overall_assessment={
            "mastery_score": 0.785,
            "improvement_rate": 0.045,
            "consistency_score": 82
        },
        progress_trend=[
            {"date": "12-01", "score": 0.72, "average": 0.70},
            {"date": "12-08", "score": 0.75, "average": 0.71},
            {"date": "12-15", "score": 0.78, "average": 0.72},
            {"date": "12-22", "score": 0.79, "average": 0.73}
        ],
        knowledge_map=[
            {"knowledge_area": "二次函数", "mastery_level": 0.75, "weak_points": ["顶点式"], "strengths": ["图像绘制"]},
            {"knowledge_area": "不等式", "mastery_level": 0.82, "weak_points": ["边界条件"], "strengths": ["基本运算"]},
            {"knowledge_area": "解析几何", "mastery_level": 0.68, "weak_points": ["圆与直线"], "strengths": ["直线方程"]}
        ],
        error_patterns={
            "most_common_error_types": [
                {"type": "概念错误", "count": 8, "percentage": 40},
                {"type": "计算错误", "count": 5, "percentage": 25},
                {"type": "审题错误", "count": 4, "percentage": 20}
            ]
        },
        personalized_insights=[
            "你在代数运算方面表现稳定，建议继续保持",
            "几何直觉需要加强，建议多做图形变换练习",
            "审题时注意关键条件的提取，避免遗漏"
        ]
    )


@router.get("/v1/class/wrong-problems", tags=["错题分析"])
async def get_class_wrong_problems(class_id: Optional[str] = None):
    """获取班级高频错题"""
    return {
        "problems": [
            {"id": "p-001", "question": "已知二次函数 y=x²-4x+3，求其顶点坐标", "errorRate": "32%", "tags": ["二次函数", "顶点式"]},
            {"id": "p-002", "question": "解不等式 2x-1 > 3x+2", "errorRate": "28%", "tags": ["不等式", "变号"]},
            {"id": "p-003", "question": "圆 x²+y²=4 与直线 y=x+k 相切，求 k 的值", "errorRate": "45%", "tags": ["圆", "切线"]}
        ]
    }


# ============ 统计接口 ============

@router.get("/teacher/statistics/class/{class_id}", tags=["统计分析"])
async def get_class_statistics(class_id: str, homework_id: Optional[str] = None):
    """获取班级统计数据"""
    return {
        "class_id": class_id,
        "total_students": 32,
        "submitted_count": 28,
        "graded_count": 28,
        "average_score": 82.5,
        "max_score": 98,
        "min_score": 65,
        "pass_rate": 0.875,
        "score_distribution": {
            "90-100": 8,
            "80-89": 12,
            "70-79": 5,
            "60-69": 3,
            "0-59": 0
        }
    }


@router.post("/teacher/statistics/merge", tags=["统计分析"])
async def merge_statistics(class_id: str, external_data: Optional[str] = None):
    """合并外部成绩数据"""
    return {
        "students": [
            {"id": "s-001", "name": "Alice Chen", "scores": {"Homework 1": 92, "Homework 2": 88, "Midterm": 85}},
            {"id": "s-002", "name": "Bob Wang", "scores": {"Homework 1": 78, "Homework 2": 82, "Midterm": 75}},
        ],
        "internalAssignments": ["Homework 1", "Homework 2"],
        "externalAssignments": ["Midterm"]
    }
