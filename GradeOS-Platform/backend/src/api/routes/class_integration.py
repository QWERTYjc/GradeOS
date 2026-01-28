"""班级系统集成 API

按照 implementation_plan.md 实现：
- POST /grading/{batch_id}/import-to-class
- POST /grading/{batch_id}/revoke
- GET /class/{class_id}/grading-history
- POST /homework/{homework_id}/grade

Requirements: Phase 6
"""

import os
import json
import uuid
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

# PostgreSQL 作为主存储
from src.db import (
    GradingHistory,
    StudentGradingResult,
    save_grading_history,
    save_student_result,
    get_grading_history,
    get_student_results,
    list_grading_history,
    get_homework_submissions,
    get_connection,
)

from src.orchestration.langgraph_orchestrator import Orchestrator
from src.api.dependencies import get_orchestrator


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["班级系统集成"])


# ==================== 智能存储适配器 ====================


# ==================== Pydantic Models ====================


class StudentMapping(BaseModel):
    """学生映射"""
    student_key: str  # 批改结果中的学生标识
    student_id: str   # 班级系统中的学生 ID


class ImportToClassRequest(BaseModel):
    """导入到班级请求"""
    class_ids: List[str]
    student_mapping: List[StudentMapping]


class ImportToClassResponse(BaseModel):
    """导入到班级响应"""
    success: bool
    imported_count: int
    history_id: str
    message: str


class RevokeRequest(BaseModel):
    """撤回请求"""
    class_id: str
    reason: Optional[str] = None


class RevokeResponse(BaseModel):
    """撤回响应"""
    success: bool
    revoked_count: int
    message: str


class GradingHistoryItem(BaseModel):
    """批改历史项"""
    history_id: str
    batch_id: str
    class_ids: Optional[List[str]]
    status: str
    total_students: int
    average_score: Optional[float]
    created_at: str
    completed_at: Optional[str]


class GradingHistoryResponse(BaseModel):
    """批改历史响应"""
    records: List[GradingHistoryItem]


class HomeworkGradeRequest(BaseModel):
    """作业批改请求"""
    submission_ids: Optional[List[str]] = None  # 空=批改全部


class HomeworkGradeResponse(BaseModel):
    """作业批改响应"""
    success: bool
    batch_id: str
    message: str


# === 批改控制台集成模型 ===

class StudentSubmissionInfo(BaseModel):
    """学生提交信息（用于批改控制台）"""
    student_id: str
    student_name: str
    images: List[str]  # base64 或 URL
    page_count: int


class SubmissionsForGradingResponse(BaseModel):
    """获取批改所需的提交数据响应"""
    class_id: str
    class_name: str
    homework_id: str
    homework_name: str
    students: List[StudentSubmissionInfo]
    total_pages: int


# ==================== API Endpoints ====================


@router.get("/class/{class_id}/homework/{homework_id}/submissions-for-grading")
async def get_submissions_for_grading(
    class_id: str,
    homework_id: str,
) -> SubmissionsForGradingResponse:
    """
    获取班级作业的所有学生提交（用于批改控制台）
    
    返回格式化的数据，可直接用于批改控制台的 Gallery 预填充。
    """
    
    submissions = get_homework_submissions(class_id, homework_id)
    
    students = []
    total_pages = 0
    
    for sub in submissions:
        images = sub.images or []
        page_count = len(images)
        total_pages += page_count
        
        students.append(StudentSubmissionInfo(
            student_id=sub.student_id,
            student_name=sub.student_name or f"Student {sub.student_id}",
            images=images,
            page_count=page_count
        ))
    
    # TODO: 从数据库获取班级和作业名称
    # 目前使用占位符
    class_name = f"Class {class_id}"
    homework_name = f"Homework {homework_id}"
    
    return SubmissionsForGradingResponse(
        class_id=class_id,
        class_name=class_name,
        homework_id=homework_id,
        homework_name=homework_name,
        students=students,
        total_pages=total_pages
    )


@router.post("/grading/{batch_id}/import-to-class", response_model=ImportToClassResponse)
async def import_grading_to_class(
    batch_id: str,
    request: ImportToClassRequest,
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    """
    导入批改结果到班级系统
    
    将批改结果与班级学生关联，并保存到 PostgreSQL。
    """
    logger.info(f"导入批改结果到班级: batch_id={batch_id}, classes={request.class_ids}")

    def _load_from_db() -> List[Dict[str, Any]]:
        history = get_grading_history(batch_id)
        if not history:
            return []
        results: List[Dict[str, Any]] = []
        for row in get_student_results(history.id):
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
            results.append(data)
        return results

    student_results: List[Dict[str, Any]] = []
    # 获取批改结果
    if orchestrator:
        run_id = f"batch_grading_{batch_id}"
        run_info = await orchestrator.get_run_info(run_id)
        if run_info:
            state = run_info.state or {}
            student_results = state.get("student_results", [])
            if not student_results:
                final_output = await orchestrator.get_final_output(run_id)
                if final_output:
                    student_results = final_output.get("student_results", [])
        else:
            student_results = _load_from_db()
            if not student_results:
                raise HTTPException(status_code=404, detail="批改批次不存在")
    else:
        student_results = _load_from_db()

    if not student_results:
        raise HTTPException(status_code=400, detail="未找到批改结果")
    
    # 建立 student_key -> student_id 映射
    key_to_id = {m.student_key: m.student_id for m in request.student_mapping}
    
    # 计算平均分
    total_score = 0.0
    total_max = 0.0
    for result in student_results:
        total_score += result.get("totalScore", result.get("score", 0) or 0)
        total_max += result.get("maxTotalScore", result.get("maxScore", 0) or 0)
    
    avg_score = (total_score / len(student_results)) if student_results else 0.0
    
    # 保存批改历史
    history_id = str(uuid.uuid4())[:8]
    history = GradingHistory(
        id=history_id,
        batch_id=batch_id,
        status="imported",
        class_ids=request.class_ids,
        created_at=datetime.now().isoformat(),
        completed_at=datetime.now().isoformat(),
        total_students=len(student_results),
        average_score=avg_score,
    )
    save_grading_history(history)
    
    # 保存学生结果
    imported_count = 0
    for result in student_results:
        student_key = result.get("studentName") or result.get("studentKey", "")
        student_id = key_to_id.get(student_key)
        
        # 从 result 中提取 summary 和 self_report
        summary_data = result.get("summary") or result.get("studentSummary")
        self_report_data = result.get("selfReport") or result.get("self_report") or result.get("selfAudit")
        
        for class_id in request.class_ids:
            student_result = StudentGradingResult(
                id=str(uuid.uuid4())[:8],
                grading_history_id=history_id,
                student_key=student_key,
                class_id=class_id,
                student_id=student_id,
                score=result.get("totalScore", result.get("score")),
                max_score=result.get("maxTotalScore", result.get("maxScore")),
                summary=summary_data.get("overall") if isinstance(summary_data, dict) else None,
                self_report=self_report_data.get("summary") if isinstance(self_report_data, dict) else None,
                result_data=result,
                imported_at=datetime.now().isoformat(),
            )
            save_student_result(student_result)
            imported_count += 1
    
    logger.info(f"批改结果已导入: history_id={history_id}, count={imported_count}")
    
    return ImportToClassResponse(
        success=True,
        imported_count=imported_count,
        history_id=history_id,
        message=f"成功导入 {imported_count} 条学生批改记录",
    )


@router.post("/grading/{batch_id}/revoke", response_model=RevokeResponse)
async def revoke_grading_import(
    batch_id: str,
    request: RevokeRequest,
):
    """
    撤回批改结果导入
    
    将指定班级的导入记录标记为已撤回。
    """
    logger.info(f"撤回批改导入: batch_id={batch_id}, class_id={request.class_id}")
    
    # 查找历史记录
    history = get_grading_history(batch_id)
    if not history:
        raise HTTPException(status_code=404, detail="批改记录不存在")
    
    # 获取学生结果并撤回
    
    revoked_count = 0
    now = datetime.now().isoformat()
    
    with get_connection() as conn:
        # 更新学生结果
        cursor = conn.execute("""
            UPDATE student_grading_results 
            SET revoked_at = ?
            WHERE grading_history_id = ? AND class_id = ? AND revoked_at IS NULL
        """, (now, history.id, request.class_id))
        revoked_count = cursor.rowcount
        
        # 检查是否所有学生都已撤回，如果是则更新历史状态
        remaining = conn.execute("""
            SELECT COUNT(*) FROM student_grading_results 
            WHERE grading_history_id = ? AND revoked_at IS NULL
        """, (history.id,)).fetchone()[0]
        
        if remaining == 0:
            conn.execute("""
                UPDATE grading_history SET status = 'revoked' WHERE id = ?
            """, (history.id,))
    
    logger.info(f"批改已撤回: batch_id={batch_id}, revoked={revoked_count}")
    
    return RevokeResponse(
        success=True,
        revoked_count=revoked_count,
        message=f"成功撤回 {revoked_count} 条记录",
    )


@router.get("/class/{class_id}/grading-history", response_model=GradingHistoryResponse)
async def get_class_grading_history(
    class_id: str,
    limit: int = 50,
):
    """
    获取班级批改历史
    """
    logger.info(f"获取班级批改历史: class_id={class_id}")
    
    histories = list_grading_history(class_id=class_id, limit=limit)
    
    records = [
        GradingHistoryItem(
            history_id=h.id,
            batch_id=h.batch_id,
            class_ids=h.class_ids,
            status=h.status,
            total_students=h.total_students,
            average_score=h.average_score,
            created_at=h.created_at,
            completed_at=h.completed_at,
        )
        for h in histories
    ]
    
    return GradingHistoryResponse(records=records)


@router.post("/homework/{homework_id}/grade", response_model=HomeworkGradeResponse)
async def grade_homework(
    homework_id: str,
    request: HomeworkGradeRequest,
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    """
    一键批改作业
    
    收集作业的提交记录，触发批改工作流。
    """
    logger.info(f"一键批改作业: homework_id={homework_id}")
    
    if not orchestrator:
        raise HTTPException(status_code=503, detail="编排器未初始化")
    
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=400, detail="未配置 LLM_API_KEY/OPENROUTER_API_KEY")
    
    # 从 unified_api 获取提交记录
    from src.api.routes.unified_api import SUBMISSIONS, HOMEWORKS, CLASS_STUDENTS
    
    homework = HOMEWORKS.get(homework_id)
    if not homework:
        raise HTTPException(status_code=404, detail="作业不存在")
    
    submissions = SUBMISSIONS.get(homework_id, [])
    
    # 过滤指定的提交
    if request.submission_ids:
        submissions = [s for s in submissions if s["submission_id"] in request.submission_ids]
    
    if not submissions:
        raise HTTPException(status_code=400, detail="无提交记录可批改")
    
    # 收集图像和边界
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
        raise HTTPException(status_code=400, detail="提交记录中没有图片")
    
    # 创建批改批次
    batch_id = str(uuid.uuid4())
    class_id = homework["class_id"]
    
    payload = {
        "batch_id": batch_id,
        "exam_id": homework_id,
        "temp_dir": "",
        "rubric_images": [],
        "answer_images": answer_images,
        "api_key": api_key,
        "inputs": {
            "rubric": "",
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
    
    # 更新作业状态
    homework["grading_triggered"] = True
    homework["grading_batch_id"] = batch_id
    homework["grading_triggered_at"] = datetime.now().isoformat()
    
    logger.info(f"作业批改已启动: homework_id={homework_id}, batch_id={batch_id}")
    
    return HomeworkGradeResponse(
        success=True,
        batch_id=batch_id,
        message=f"批改已启动，共 {len(submissions)} 个提交",
    )
