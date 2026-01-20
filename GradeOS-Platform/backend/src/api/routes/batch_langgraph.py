"""批量提交 API 路由 - 使用 LangGraph Orchestrator

正确的架构：
1. 使用 LangGraph Orchestrator 启动批改流程
2. 通过 LangGraph 的流式 API 实时推送进度
3. 利用 PostgreSQL Checkpointer 实现持久化和断点恢复
"""

import uuid
import logging
import tempfile
import asyncio
import base64
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, WebSocket, WebSocketDisconnect, Depends
from starlette.websockets import WebSocketState
from pydantic import BaseModel, Field
import fitz
from PIL import Image
import os

from src.models.enums import SubmissionStatus
from src.orchestration.base import Orchestrator
from src.api.dependencies import get_orchestrator
from src.utils.image import to_jpeg_bytes, pil_to_jpeg_bytes
from src.db.sqlite import (
    save_grading_history, 
    save_student_result, 
    GradingHistory, 
    StudentGradingResult,
    upsert_homework_submission_grade,
    list_class_students,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/batch", tags=["批量提交"])

# 存储活跃的 WebSocket 连接
active_connections: Dict[str, List[WebSocket]] = {}
# 缓存图片，避免 images_ready 早于 WebSocket 连接导致前端丢失
batch_image_cache: Dict[str, Dict[str, dict]] = {}
DEBUG_LOG_PATH = os.getenv("GRADEOS_DEBUG_LOG_PATH")
TEACHER_MAX_ACTIVE_RUNS = int(os.getenv("TEACHER_MAX_ACTIVE_RUNS", "3"))
_TEACHER_SEMAPHORE_LOCK = asyncio.Lock()
_TEACHER_SEMAPHORES: Dict[str, asyncio.Semaphore] = {}


def _is_ws_connected(websocket: WebSocket) -> bool:
    return (
        websocket.client_state == WebSocketState.CONNECTED
        and websocket.application_state == WebSocketState.CONNECTED
    )


def _write_debug_log(payload: Dict[str, Any]) -> None:
    if not DEBUG_LOG_PATH:
        return
    try:
        Path(DEBUG_LOG_PATH).parent.mkdir(parents=True, exist_ok=True)
        with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.debug(f"Failed to write debug log: {exc}")


def _safe_to_jpeg_bytes(image_bytes: bytes, label: str) -> bytes:
    try:
        return to_jpeg_bytes(image_bytes)
    except Exception as exc:
        logger.warning(f"Failed to convert image to JPEG ({label}): {exc}")
        return image_bytes



def _normalize_teacher_key(teacher_id: Optional[str]) -> str:
    if teacher_id and teacher_id.strip():
        return teacher_id.strip()
    return "anonymous"


async def _get_teacher_semaphore(teacher_key: str) -> asyncio.Semaphore:
    async with _TEACHER_SEMAPHORE_LOCK:
        semaphore = _TEACHER_SEMAPHORES.get(teacher_key)
        if not semaphore:
            semaphore = asyncio.Semaphore(max(1, TEACHER_MAX_ACTIVE_RUNS))
            _TEACHER_SEMAPHORES[teacher_key] = semaphore
    return semaphore


class BatchSubmissionResponse(BaseModel):
    """批量提交响应"""
    batch_id: str = Field(..., description="批次 ID")
    status: SubmissionStatus = Field(..., description="状态")
    total_pages: int = Field(..., description="总页数")
    estimated_completion_time: int = Field(..., description="预计完成时间（秒）")


class BatchStatusResponse(BaseModel):
    """批量状态查询响应"""
    batch_id: str
    exam_id: str
    status: str
    total_students: int = Field(0, description="识别到的学生数")
    completed_students: int = Field(0, description="已完成批改的学生数")
    unidentified_pages: int = Field(0, description="未识别学生的页数")
    results: Optional[List[dict]] = Field(None, description="批改结果")


class RubricReviewContextResponse(BaseModel):
    """前端 rubric review 上下文"""
    batch_id: str
    status: Optional[str] = None
    current_stage: Optional[str] = None
    parsed_rubric: Optional[dict] = None
    rubric_images: List[str] = []


class ResultsReviewContextResponse(BaseModel):
    """前端 results review 上下文"""
    batch_id: str
    status: Optional[str] = None
    current_stage: Optional[str] = None
    student_results: List[dict] = []
    answer_images: List[str] = []


def _pdf_to_images(pdf_path: str, dpi: int = 150) -> List[bytes]:
    """将 PDF 转换为图像列表"""
    pdf_doc = fitz.open(pdf_path)
    images = []
    
    for page_num in range(len(pdf_doc)):
        page = pdf_doc[page_num]
        mat = fitz.Matrix(dpi/72, dpi/72)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        images.append(pil_to_jpeg_bytes(img))
    
    pdf_doc.close()
    return images


async def broadcast_progress(batch_id: str, message: dict):
    """向所有连接的 WebSocket 客户端广播进度"""
    # #region agent log - 假设J: broadcast_progress 被调用
    msg_type = message.get("type", "unknown")
    if msg_type in ("images_ready", "rubric_images_ready", "review_required"):
        cached = batch_image_cache.setdefault(batch_id, {})
        cached[msg_type] = message
    if msg_type == "llm_stream_chunk":
        node_id = message.get("nodeId") or ""
        if node_id in ("rubric_parse", "rubric_review"):
            cached = batch_image_cache.setdefault(batch_id, {})
            stream_cache = cached.setdefault("llm_stream_cache", {})
            cache_key = f"{node_id}:{message.get('agentId') or 'all'}:{message.get('streamType') or 'output'}"
            existing = stream_cache.get(cache_key, {})
            chunk_data = message.get("chunk", "") or ""
            if isinstance(chunk_data, list):
                chunk_data = "".join([str(c) for c in chunk_data])
            else:
                chunk_data = str(chunk_data)
            
            existing_chunk = existing.get("chunk", "") or ""
            combined = existing_chunk + chunk_data
            max_chars = 12000
            if len(combined) > max_chars:
                combined = combined[-max_chars:]
            stream_cache[cache_key] = {
                **message,
                "chunk": combined,
            }
    if msg_type in ("review_completed", "workflow_completed"):
        cached = batch_image_cache.get(batch_id)
        if cached and "review_required" in cached:
            cached.pop("review_required", None)
        if cached and "llm_stream_cache" in cached:
            cached.pop("llm_stream_cache", None)
    if msg_type == "workflow_completed":
        import traceback as _tb_j
        stack = ''.join(_tb_j.format_stack()[-5:-1])  # 获取调用栈
        _write_debug_log({
            "hypothesisId": "J",
            "location": "batch_langgraph.py:broadcast_progress",
            "message": "broadcast_progress发送workflow_completed",
            "data": {
                "batch_id": batch_id,
                "results_count": len(message.get("results", [])),
                "stack_trace": stack[:500],
            },
            "timestamp": int(datetime.now().timestamp() * 1000),
            "sessionId": "debug-session",
        })
    # #endregion
    if batch_id in active_connections:
        disconnected = []
        for ws in active_connections[batch_id]:
            if not _is_ws_connected(ws):
                disconnected.append(ws)
                continue
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.error(f"WebSocket 发送失败: {e}")
                disconnected.append(ws)
        
        # 移除断开的连接
        for ws in disconnected:
            if ws in active_connections[batch_id]:
                active_connections[batch_id].remove(ws)



async def _start_run_with_teacher_limit(
    *,
    teacher_key: str,
    batch_id: str,
    payload: Dict[str, Any],
    orchestrator: Orchestrator,
    class_id: Optional[str],
    homework_id: Optional[str],
    student_mapping: List[dict],
) -> Optional[str]:
    semaphore = await _get_teacher_semaphore(teacher_key)
    await semaphore.acquire()
    run_id: Optional[str] = None
    try:
        run_id = await orchestrator.start_run(
            graph_name="batch_grading",
            payload=payload,
            idempotency_key=batch_id
        )
        logger.info(
            f"LangGraph ??????? "
            f"batch_id={batch_id}, "
            f"run_id={run_id}"
        )
        asyncio.create_task(
            stream_langgraph_progress(
                batch_id=batch_id,
                run_id=run_id,
                orchestrator=orchestrator,
                class_id=class_id,
                homework_id=homework_id,
                student_mapping=student_mapping,
                teacher_key=teacher_key,
                teacher_semaphore=semaphore,
            )
        )
        return run_id
    except Exception as exc:
        logger.error(f"????????: {exc}", exc_info=True)
        semaphore.release()
        await broadcast_progress(batch_id, {
            "type": "workflow_update",
            "nodeId": "rubric_parse",
            "status": "failed",
            "message": "Queued run failed to start"
        })
        return None


@router.post("/submit", response_model=BatchSubmissionResponse)
async def submit_batch(
    exam_id: Optional[str] = Form(None, description="考试 ID"),
    rubrics: List[UploadFile] = File(default=[], description="评分标准 PDF（可选）"),
    files: List[UploadFile] = File(..., description="学生作答 PDF"),
    api_key: Optional[str] = Form(None, description="LLM API Key"),
    teacher_id: Optional[str] = Form(None, description="?? ID"),
    auto_identify: bool = Form(True, description="是否自动识别学生身份"),
    student_boundaries: Optional[str] = Form(None, description="手动设置的学生边界 (JSON List of page indices)"),
    expected_students: Optional[int] = Form(None, description="预期学生数量（强烈建议提供，用于更准确的分割）"),
    # 新增：班级批改上下文
    class_id: Optional[str] = Form(None, description="班级 ID（用于成绩写回）"),
    homework_id: Optional[str] = Form(None, description="作业 ID（用于成绩写回）"),
    student_mapping_json: Optional[str] = Form(None, description="学生映射 JSON [{studentId, studentName, startIndex, endIndex}]"),
    enable_review: bool = Form(True, description="是否启用人工交互"),
    grading_mode: Optional[str] = Form(None, description="grading mode: standard/assist_teacher/assist_student/auto"),
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    批量提交试卷并进行批改（使用 LangGraph Orchestrator）
    
    正确的架构：
    1. 使用 LangGraph Orchestrator 启动 batch_grading Graph
    2. Graph 自动处理：边界检测 → 并行批改 → 聚合 → 持久化 → 通知
    3. 通过 WebSocket 实时推送 LangGraph 的执行进度
    
    Args:
        exam_id: 考试 ID
        rubrics: 评分标准 PDF 文件列表
        files: 学生作答 PDF 文件列表
        api_key: LLM API Key
        auto_identify: 是否启用自动学生识别
        orchestrator: LangGraph Orchestrator（依赖注入）
        
    Returns:
        BatchSubmissionResponse: 批次信息
    """
    # #region agent log - 假设K: submit_batch 被调用
    _write_debug_log({
        "hypothesisId": "K",
        "location": "batch_langgraph.py:submit_batch:entry",
        "message": "submit_batch端点被调用",
        "data": {"files_count": len(files), "rubrics_count": len(rubrics)},
        "timestamp": int(datetime.now().timestamp() * 1000),
        "sessionId": "debug-session",
    })
    # #endregion
    # 检查 orchestrator 是否可用
    if not orchestrator:
        raise HTTPException(
            status_code=503, 
            detail="批改服务未初始化，请稍后重试或检查服务配置"
        )
    
    if not api_key:
        api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="未提供 API Key，请在请求中提供或配置环境变量 LLM_API_KEY/OPENROUTER_API_KEY"
        )


    
    # 解析学生边界
    parsed_boundaries = []
    if student_boundaries:
        try:
            logger.info(f"接收到原始 student_boundaries: {student_boundaries} (type: {type(student_boundaries)})")
            import json
            parsed_boundaries = json.loads(student_boundaries)
            logger.info(f"解析后的 manual_boundaries: {parsed_boundaries}")
        except Exception as e:
            logger.warning(f"解析手动学生边界失败: {e}")

    if not exam_id:
        exam_id = str(uuid.uuid4())

    batch_id = str(uuid.uuid4())
    
    logger.info(
        f"收到批量提交（LangGraph）: "
        f"batch_id={batch_id}, "
        f"exam_id={exam_id}, "
        f"auto_identify={auto_identify}"
    )
    
    temp_dir = None
    try:
        # 创建临时目录
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir)
        
        # === 处理答题文件（支持图片列表或单个 PDF）===
        answer_images = []
        
        for idx, file in enumerate(files):
            file_name = file.filename or f"file_{idx}"
            content = await file.read()
            
            # 检查文件类型
            if file_name.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.gif')):
                # 图片文件：直接使用内容
                answer_images.append(_safe_to_jpeg_bytes(content, file_name))
                logger.debug(f"读取图片文件: {file_name}, 大小: {len(content)} bytes")
            elif file_name.lower().endswith('.pdf'):
                # PDF 文件：转换为图像
                pdf_path = temp_path / f"answer_{idx}.pdf"
                with open(pdf_path, "wb") as f:
                    f.write(content)
                loop = asyncio.get_event_loop()
                pdf_images = await loop.run_in_executor(None, _pdf_to_images, str(pdf_path), 150)
                answer_images.extend(pdf_images)
                logger.info(f"PDF 文件 {file_name} 转换为 {len(pdf_images)} 页图片")
            elif file_name.lower().endswith('.txt'):
                # 文本文件：直接使用内容
                answer_images.append(content)
                logger.info(f"文本文件处理完成: {file_name}, 内容长度={len(content)}")
            else:
                # 尝试作为图片处理（可能没有扩展名）
                answer_images.append(_safe_to_jpeg_bytes(content, file_name))
                logger.warning(f"未知文件类型 {file_name}，尝试作为图片处理")
        
        total_pages = len(answer_images)
        logger.info(f"答题文件处理完成: batch_id={batch_id}, 总页数={total_pages}")
        
        # === 处理评分标准（可选）===
        # Convert images to base64 and cache them immediately
        # (Fix: Rubric images not displaying on frontend)
        if answer_images:
            try:
                base64_images = [base64.b64encode(img).decode('utf-8') for img in answer_images]
                
                # Cache for direct WebSocket connection
                batch_image_cache.setdefault(batch_id, {})["images_ready"] = {
                    "type": "images_ready",
                    "images": base64_images
                }
                
                # Broadcast (though no clients connected yet usually)
                await broadcast_progress(batch_id, {
                    "type": "images_ready",
                    "images": base64_images
                })
                logger.info(f"已缓存 {len(base64_images)} 张图片用于前端显示")
            except Exception as e:
                logger.error(f"图片 Base64 转换失败: {e}")

        # === 处理评分标准（可选）===
        rubric_images = []
        if rubrics and len(rubrics) > 0:
            for idx, rubric_file in enumerate(rubrics):
                rubric_name = rubric_file.filename or f"rubric_{idx}"
                rubric_content = await rubric_file.read()
                
                if rubric_name.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.gif')):
                    rubric_images.append(_safe_to_jpeg_bytes(rubric_content, rubric_name))
                elif rubric_name.lower().endswith('.pdf'):
                    rubric_path = temp_path / f"rubric_{idx}.pdf"
                    with open(rubric_path, "wb") as f:
                        f.write(rubric_content)
                    loop = asyncio.get_event_loop()
                    pdf_rubric_images = await loop.run_in_executor(None, _pdf_to_images, str(rubric_path), 150)
                    rubric_images.extend(pdf_rubric_images)
                else:
                    rubric_images.append(_safe_to_jpeg_bytes(rubric_content, rubric_name))
            
            logger.info(f"评分标准处理完成: batch_id={batch_id}, 总页数={len(rubric_images)}")
            if rubric_images:
                try:
                    base64_rubric_images = [base64.b64encode(img).decode("utf-8") for img in rubric_images]
                    batch_image_cache.setdefault(batch_id, {})["rubric_images_ready"] = {
                        "type": "rubric_images_ready",
                        "images": base64_rubric_images
                    }
                    await broadcast_progress(batch_id, {
                        "type": "rubric_images_ready",
                        "images": base64_rubric_images
                    })
                    logger.info(f"已缓存 {len(base64_rubric_images)} 张评分标准图片用于前端显示")
                except Exception as e:
                    logger.error(f"评分标准 Base64 转换失败: {e}")
        else:
            logger.info(f"未提供评分标准，将使用默认评分: batch_id={batch_id}")
        
        logger.info(
            f"文件处理完成: "
            f"batch_id={batch_id}, "
            f"rubric_pages={len(rubric_images)}, "
            f"answer_pages={total_pages}"
        )
        
        # 🚀 使用 LangGraph Orchestrator 启动批改流程
        
        # 解析学生映射（班级批改模式）
        student_mapping = []
        if student_mapping_json:
            try:
                import json
                student_mapping = json.loads(student_mapping_json)
                logger.info(f"班级批改模式: class_id={class_id}, homework_id={homework_id}, 学生数={len(student_mapping)}")
            except Exception as e:
                logger.warning(f"解析学生映射失败: {e}")
        
        payload = {
            "batch_id": batch_id,
            "exam_id": exam_id,
            "temp_dir": str(temp_path),  # 临时目录（用于清理）
            "rubric_images": rubric_images,
            "answer_images": answer_images,
            "api_key": api_key,
            # 班级批改上下文（可选）
            "class_id": class_id,
            "homework_id": homework_id,
            "student_mapping": student_mapping,
            "inputs": {
                "rubric": "rubric_content",  # TODO: 解析 rubric
                "auto_identify": auto_identify,
                "manual_boundaries": parsed_boundaries,  # 传递人工边界
                "expected_students": expected_students if expected_students else 2,  # 🔥 默认 2 名学生
                "enable_review": enable_review,
                "grading_mode": grading_mode or "auto",
            }
        }
        
        # 启动 LangGraph batch_grading Graph
        teacher_key = _normalize_teacher_key(teacher_id)
        teacher_semaphore = await _get_teacher_semaphore(teacher_key)
        if teacher_semaphore.locked():
            await broadcast_progress(batch_id, {
                "type": "workflow_update",
                "nodeId": "rubric_parse",
                "status": "pending",
                "message": "Queued: waiting for teacher slot"
            })
        asyncio.create_task(
            _start_run_with_teacher_limit(
                teacher_key=teacher_key,
                batch_id=batch_id,
                payload=payload,
                orchestrator=orchestrator,
                class_id=class_id,
                homework_id=homework_id,
                student_mapping=student_mapping,
            )
        )

        return BatchSubmissionResponse(
            batch_id=batch_id,
            status=SubmissionStatus.UPLOADED,
            total_pages=total_pages,
            estimated_completion_time=total_pages * 3  # Estimated: 3s per page
        )
        
    except Exception as e:
        logger.error(f"批量提交失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"批量提交失败: {str(e)}")


async def stream_langgraph_progress(
    batch_id: str,
    run_id: str,
    orchestrator: Orchestrator,
    class_id: Optional[str] = None,
    homework_id: Optional[str] = None,
    student_mapping: Optional[List[dict]] = None,
    teacher_key: Optional[str] = None,
    teacher_semaphore: Optional[asyncio.Semaphore] = None
):
    """
    流式监听 LangGraph 执行进度并推送到 WebSocket
    
    这是实现实时进度推送的关键函数！
    
    Args:
        batch_id: 批次 ID
        run_id: LangGraph 运行 ID
        orchestrator: LangGraph Orchestrator
    """
    # #region agent log - 假设G: stream_langgraph_progress 入口
    _write_debug_log({
        "hypothesisId": "G",
        "location": "batch_langgraph.py:stream_langgraph_progress:entry",
        "message": "stream_langgraph_progress函数被调用",
        "data": {"batch_id": batch_id, "run_id": run_id},
        "timestamp": int(datetime.now().timestamp() * 1000),
        "sessionId": "debug-session",
    })
    # #endregion
    logger.info(f"开始流式监听 LangGraph 进度: batch_id={batch_id}, run_id={run_id}")
    
    try:
        # 🔥 使用 LangGraph 的流式 API
        async for event in orchestrator.stream_run(run_id):
            event_type = event.get("type")
            node_name = event.get("node")
            data = event.get("data", {})
            
            logger.debug(
                f"LangGraph 事件: "
                f"batch_id={batch_id}, "
                f"type={event_type}, "
                f"node={node_name}"
            )
            
            # 将 LangGraph 事件转换为前端 WebSocket 消息
            if event_type == "node_start":
                await broadcast_progress(batch_id, {
                    "type": "workflow_update",
                    "nodeId": _map_node_to_frontend(node_name),
                    "status": "running",
                    "message": f"Running {_get_node_display_name(node_name)}..."
                })
            
            elif event_type == "node_end":
                await broadcast_progress(batch_id, {
                    "type": "workflow_update",
                    "nodeId": _map_node_to_frontend(node_name),
                    "status": "completed",
                    "message": f"{_get_node_display_name(node_name)} completed"
                })
                
                # 处理节点输出
                output = data.get("output", {})
                if isinstance(output, dict):
                    interrupt_payload = output.get("__interrupt__")
                    if interrupt_payload:
                        review_type = interrupt_payload.get("type") if isinstance(interrupt_payload, dict) else "review_required"
                        await broadcast_progress(batch_id, {
                            "type": "review_required",
                            "reviewType": review_type,
                            "payload": interrupt_payload,
                            "nodeId": _map_node_to_frontend("rubric_review") if "rubric" in review_type else _map_node_to_frontend("review"),
                        })
                    # 评分标准解析完成
                    if node_name == "rubric_parse" and output.get("parsed_rubric"):
                        parsed = output["parsed_rubric"]
                        await broadcast_progress(batch_id, {
                            "type": "rubric_parsed",
                            "totalQuestions": parsed.get("total_questions", 0),
                            "totalScore": parsed.get("total_score", 0),
                            "generalNotes": parsed.get("general_notes", ""),
                            "rubricFormat": parsed.get("rubric_format", ""),
                            "questions": [
                                {
                                    "questionId": q.get("question_id", ""),
                                    "maxScore": q.get("max_score", 0),
                                    "questionText": q.get("question_text", ""),
                                    "standardAnswer": q.get("standard_answer", ""),
                                    "gradingNotes": q.get("grading_notes", ""),
                                    "sourcePages": q.get("source_pages") or q.get("sourcePages") or [],
                                    "scoringPoints": [
                                        {
                                            "pointId": sp.get("point_id") or sp.get("pointId") or f"{q.get('question_id')}.{idx + 1}",
                                            "description": sp.get("description", ""),
                                            "expectedValue": sp.get("expected_value") or sp.get("expectedValue", ""),
                                            "keywords": sp.get("keywords") or [],
                                            "score": sp.get("score", 0),
                                            "isRequired": sp.get("is_required", True),
                                        }
                                        for idx, sp in enumerate(q.get("scoring_points", []))
                                    ],
                                    "deductionRules": [
                                        {
                                            "ruleId": dr.get("rule_id") or dr.get("ruleId") or f"{q.get('question_id')}.d{idx + 1}",
                                            "description": dr.get("description", ""),
                                            "deduction": dr.get("deduction", dr.get("score", 0)),
                                            "conditions": dr.get("conditions") or dr.get("when") or "",
                                        }
                                        for idx, dr in enumerate(q.get("deduction_rules") or q.get("deductionRules") or [])
                                    ],
                                    "alternativeSolutions": [
                                        {
                                            "description": alt.get("description", ""),
                                            "scoringCriteria": alt.get("scoring_criteria", ""),
                                            "note": alt.get("note", ""),
                                        }
                                        for alt in q.get("alternative_solutions", [])
                                    ]
                                }
                                for q in parsed.get("questions", [])
                            ]
                        })
                    
                    # 批改批次完成
                    if node_name == "grade_batch" and output.get("grading_results"):
                        results = output["grading_results"]
                        completed = sum(1 for r in results if r.get("status") == "completed")
                        
                        await broadcast_progress(batch_id, {
                            "type": "batch_complete",
                            "batchSize": len(results),
                            "successCount": completed,
                            "totalScore": sum(r.get("score", 0) for r in results if r.get("status") == "completed"),
                            "pages": [r.get("page_index") for r in results]
                        })
                    
                    # 索引完成（学生识别）
                    if node_name == "index" and output.get("student_boundaries"):
                        boundaries = output["student_boundaries"]
                        await broadcast_progress(batch_id, {
                            "type": "students_identified",
                            "studentCount": len(boundaries),
                            "students": [
                                {
                                    "studentKey": b.get("student_key", ""),
                                    "startPage": b.get("start_page", 0),
                                    "endPage": b.get("end_page", 0),
                                    "confidence": b.get("confidence", 0),
                                    "needsConfirmation": b.get("needs_confirmation", False)
                                }
                                for b in boundaries
                            ]
                        })
                    
                    # 审核完成
                    if node_name == "review" and output.get("review_summary"):
                        await broadcast_progress(batch_id, {
                            "type": "review_completed",
                            "summary": output["review_summary"]
                        })
                    
                    # 跨页题目合并完成
                    if node_name == "cross_page_merge":
                        cross_page_questions = output.get("cross_page_questions", [])
                        merged_questions = output.get("merged_questions", [])
                        if cross_page_questions:
                            await broadcast_progress(batch_id, {
                                "type": "cross_page_detected",
                                "questions": cross_page_questions,
                                "mergedCount": len(merged_questions),
                                "crossPageCount": len(cross_page_questions)
                            })
            
            elif event_type == "paused":
                # 处理 Graph 中断/暂停（通常是需要人工审核）
                data = event.get("data", {})
                interrupt_value = data.get("interrupt_value")
                
                logger.info(f"LangGraph 暂停: batch_id={batch_id}, interrupt_value={interrupt_value}")
                
                if interrupt_value:
                    # 如果有中断 payload，广播 review_required
                    review_type = interrupt_value.get("type") if isinstance(interrupt_value, dict) else "review_required"
                    await broadcast_progress(batch_id, {
                        "type": "review_required",
                        "reviewType": review_type,
                        "payload": interrupt_value,
                        "nodeId": _map_node_to_frontend("rubric_review") if "rubric" in review_type else _map_node_to_frontend("review"),
                    })
                else:
                    # 如果没有 payload，至少通知状态变更
                    await broadcast_progress(batch_id, {
                        "type": "workflow_update",
                        "status": "paused",
                        "message": "Workflow paused (awaiting input)"
                    })

            elif event_type == "state_update":
                # 推送状态更新
                state = data.get("state", {})
                
                # 批次进度更新
                if state.get("progress"):
                    progress = state["progress"]
                    await broadcast_progress(batch_id, {
                        "type": "batch_progress",
                        "batchIndex": progress.get("current_batch", 0),
                        "totalBatches": progress.get("total_batches", 1),
                        "successCount": progress.get("success_count", 0),
                        "failureCount": progress.get("failure_count", 0)
                    })
                
                # 百分比进度
                if state.get("percentage"):
                    await broadcast_progress(batch_id, {
                        "type": "grading_progress",
                        "percentage": state["percentage"],
                        "currentStage": state.get("current_stage", "")
                    })
            
            elif event_type == "llm_stream":
                # Real-time LLM token streaming
                node_name = event.get("node") or data.get("node", "")
                chunk = data.get("chunk") or data.get("content") or ""
                await broadcast_progress(batch_id, {
                    "type": "llm_stream_chunk",
                    "nodeId": _map_node_to_frontend(node_name) if node_name else None,
                    "nodeName": _get_node_display_name(node_name) if node_name else None,
                    "chunk": chunk,
                })

            elif event_type == "error":
                await broadcast_progress(batch_id, {
                    "type": "workflow_error",
                    "message": data.get("error", "Unknown error")
                })
            
            elif event_type == "completed":
                # #region agent log - 假设H: completed 事件
                _write_debug_log({
                    "hypothesisId": "H",
                    "location": "batch_langgraph.py:event_completed",
                    "message": "收到completed事件",
                    "data": {
                        "event_type": event_type,
                        "data_keys": list(data.keys()) if isinstance(data, dict) else str(type(data)),
                    },
                    "timestamp": int(datetime.now().timestamp() * 1000),
                    "sessionId": "debug-session",
                })
                # #endregion
                # 工作流完成 - 获取完整的最终状态
                final_state = data.get("state", {})
                
                # 从 student_results 获取结果
                student_results = final_state.get("student_results", [])
                
                # #region agent log - 假设I: student_results 原始数据
                _write_debug_log({
                    "hypothesisId": "I",
                    "location": "batch_langgraph.py:student_results_raw",
                    "message": "student_results原始数据",
                    "data": {
                        "count": len(student_results),
                        "students": [{"key": r.get("student_key"), "score": r.get("total_score")} for r in student_results],
                    },
                    "timestamp": int(datetime.now().timestamp() * 1000),
                    "sessionId": "debug-session",
                })
                # #endregion
                
                # 如果没有 student_results，尝试从 orchestrator 获取最终输出
                if not student_results:
                    try:
                        final_output = await orchestrator.get_final_output(run_id)
                        if final_output:
                            student_results = final_output.get("student_results", [])
                            logger.info(f"从 orchestrator 获取到 {len(student_results)} 个学生结果")
                    except Exception as e:
                        logger.warning(f"获取最终输出失败: {e}")
                
                formatted_results = _format_results_for_frontend(student_results)
                class_report = final_state.get("class_report")
                if not class_report and final_state.get("export_data"):
                    class_report = final_state.get("export_data", {}).get("class_report")
                
                # 保存批改历史与学生结果（支持班级/非班级模式）
                try:
                    logger.info(
                        f"保存批改结果: batch_id={batch_id}, class_id={class_id}, homework_id={homework_id}"
                    )

                    now = datetime.now().isoformat()
                    scores = [
                        s.get("score") for s in formatted_results
                        if isinstance(s.get("score"), (int, float))
                    ]
                    average_score = None
                    if isinstance(class_report, dict):
                        average_score = class_report.get("average_score")
                    if average_score is None and scores:
                        average_score = round(sum(scores) / len(scores), 2)

                    history_id = str(uuid.uuid4())
                    history = GradingHistory(
                        id=history_id,
                        batch_id=batch_id,
                        status="completed",
                        class_ids=[class_id] if class_id else None,
                        created_at=now,
                        completed_at=now,
                        total_students=len(formatted_results),
                        average_score=average_score,
                        result_data={
                            "summary": class_report,
                            "class_id": class_id,
                            "homework_id": homework_id,
                        } if class_report or class_id or homework_id else None,
                    )
                    save_grading_history(history)

                    student_map_by_index = {}
                    student_map_by_name = {}
                    if student_mapping:
                        for idx, mapping in enumerate(student_mapping):
                            student_map_by_index[idx] = mapping
                            name_key = (mapping.get("studentName") or "").strip().lower()
                            if name_key:
                                student_map_by_name[name_key] = mapping

                    roster = list_class_students(class_id) if class_id else []
                    roster_by_name = {
                        (student.name or student.username or "").strip().lower(): student
                        for student in roster
                        if (student.name or student.username)
                    }

                    for idx, result in enumerate(formatted_results):
                        student_name = (
                            result.get("studentName")
                            or result.get("student_name")
                            or f"Student {idx + 1}"
                        )
                        student_id = result.get("studentId") or result.get("student_id")

                        if not student_id and student_map_by_index.get(idx):
                            mapping = student_map_by_index[idx]
                            student_id = mapping.get("studentId")
                            student_name = mapping.get("studentName") or student_name
                        if not student_id and student_name:
                            mapping = student_map_by_name.get(student_name.strip().lower())
                            if mapping:
                                student_id = mapping.get("studentId")
                                student_name = mapping.get("studentName") or student_name
                        if not student_id and student_name:
                            roster_hit = roster_by_name.get(student_name.strip().lower())
                            if roster_hit:
                                student_id = roster_hit.id
                                student_name = roster_hit.name or roster_hit.username or student_name
                        if not student_id and class_id and idx < len(roster):
                            roster_hit = roster[idx]
                            student_id = roster_hit.id
                            student_name = roster_hit.name or roster_hit.username or student_name
                        if not student_id and class_id:
                            student_id = f"auto-{idx + 1}"

                        student_summary = result.get("studentSummary") or result.get("student_summary") or {}
                        self_audit = result.get("selfAudit") or result.get("self_audit") or {}
                        student_result = StudentGradingResult(
                            id=str(uuid.uuid4()),
                            grading_history_id=history_id,
                            student_key=student_name,
                            score=result.get("score"),
                            max_score=result.get("maxScore") or result.get("max_score"),
                            class_id=class_id,
                            student_id=student_id if class_id else None,
                            summary=student_summary.get("overall") if isinstance(student_summary, dict) else None,
                            self_report=self_audit.get("summary") if isinstance(self_audit, dict) else None,
                            result_data=result,
                        )
                        save_student_result(student_result)

                        if class_id and homework_id and student_id:
                            feedback = None
                            if isinstance(student_summary, dict):
                                feedback = student_summary.get("overall")
                            upsert_homework_submission_grade(
                                class_id=class_id,
                                homework_id=homework_id,
                                student_id=student_id,
                                student_name=student_name,
                                score=result.get("score"),
                                feedback=feedback,
                                grading_batch_id=batch_id,
                            )

                    logger.info(f"批改结果已保存: history_id={history_id}")
                except Exception as e:
                    logger.error(f"保存批改结果失败: {e}", exc_info=True)

                # #region agent log - 假设E: WebSocket 消息发送
                _write_debug_log({
                    "hypothesisId": "E",
                    "location": "batch_langgraph.py:workflow_completed",
                    "message": "发送workflow_completed",
                    "data": {
                        "student_count": len(formatted_results),
                        "students": [{"name": f.get("studentName"), "score": f.get("score")} for f in formatted_results],
                    },
                    "timestamp": int(datetime.now().timestamp() * 1000),
                    "sessionId": "debug-session",
                })
                # #endregion
                
                await broadcast_progress(batch_id, {
                    "type": "workflow_completed",
                    "message": f"Grading completed, processed {len(formatted_results)} students",
                    "results": formatted_results,
                    "classReport": class_report
                })
        
        logger.info(f"LangGraph 进度流式传输完成: batch_id={batch_id}")
        
    except Exception as e:
        logger.error(
            f"流式传输失败: batch_id={batch_id}, error={str(e)}",
            exc_info=True
        )
        await broadcast_progress(batch_id, {
            "type": "workflow_error",
            "message": f"流式传输失败: {str(e)}"
        })

    finally:
        if teacher_semaphore:
            try:
                run_info = await orchestrator.get_status(run_id)
                status_value = run_info.status.value if hasattr(run_info.status, "value") else str(run_info.status)
                if status_value in ("completed", "failed", "cancelled"):
                    teacher_semaphore.release()
            except Exception:
                teacher_semaphore.release()


def _map_node_to_frontend(node_name: str) -> str:
    """将 LangGraph 节点名称映射到前端节点 ID
    
    前端工作流节点（consoleStore.ts initialNodes）：
    - intake: 接收文件
    - rubric_parse: 解析评分标准
    - grade_batch: 分批并行批改（isParallelContainer）
    - cross_page_merge: 跨页题目合并
    - index: 批改前索引
    - index_merge: 索引聚合
    - export: 导出结果
    """
    mapping = {
        # 主要节点（与后端 batch_grading.py 完全对应）
        "intake": "intake",
        "rubric_parse": "rubric_parse",
        "rubric_review": "rubric_review",
        "grade_batch": "grade_batch",
        "cross_page_merge": "cross_page_merge",
        "index": "index",
        "index_merge": "index_merge",
        "segment": "index_merge",
        "review": "review",
        "logic_review": "logic_review",
        "export": "export",
        # 兼容旧名称
        "detect_boundaries": "index",
        "grade_student": "grade_batch",
        "grading": "grade_batch",
        "aggregate": "review",
        "batch_persist": "export",
        "batch_notify": "export"
    }
    return mapping.get(node_name, node_name)


def _get_node_display_name(node_name: str) -> str:
    """获取节点的显示名称（中文）"""
    display_names = {
        "intake": "Ingest",
        "preprocess": "Preprocess",
        "index": "Index",
        "rubric_parse": "Rubric Parse",
        "rubric_review": "Rubric Review",
        "grading_fanout": "Batch Fanout",
        "grade_batch": "Batch Grading",
        "cross_page_merge": "Cross-Page Merge",
        "logic_review": "Logic Review",
        "index_merge": "Index Merge",
        "segment": "Index Merge",
        "review": "Final Review",
        "export": "Export"
    }
    return display_names.get(node_name, node_name)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _format_results_for_frontend(results: List[Dict]) -> List[Dict]:
    """格式化批改结果为前端格式"""
    # #region agent log - 假设D: _format_results_for_frontend 输入
    _write_debug_log({
        "hypothesisId": "D",
        "location": "batch_langgraph.py:_format_results_for_frontend:input",
        "message": "输入的results",
        "data": {
            "count": len(results),
            "students": [{"key": r.get("student_key"), "score": r.get("total_score")} for r in results],
        },
        "timestamp": int(datetime.now().timestamp() * 1000),
        "sessionId": "debug-session",
    })
    # #endregion
    formatted = []
    for r in results:
        # 处理 question_details 格式
        question_results = []
        
        # 优先使用 question_details
        if r.get("question_details"):
            for q in r.get("question_details", []):
                scoring_results = q.get("scoring_point_results") or q.get("scoring_results") or []
                question_results.append({
                    "questionId": str(q.get("question_id", "")),
                    "score": q.get("score", 0),
                    "maxScore": q.get("max_score", 0),
                    "feedback": q.get("feedback", ""),
                    "confidence": q.get("confidence", 0),
                    "confidence_reason": q.get("confidence_reason") or q.get("confidenceReason"),
                    "self_critique": q.get("self_critique") or q.get("selfCritique"),
                    "self_critique_confidence": q.get("self_critique_confidence") or q.get("selfCritiqueConfidence"),
                    "rubric_refs": q.get("rubric_refs") or q.get("rubricRefs"),
                    "review_summary": q.get("review_summary") or q.get("reviewSummary"),
                    "review_corrections": q.get("review_corrections") or q.get("reviewCorrections"),
                    "needsReview": (
                        q.get("needs_review")
                        if q.get("needs_review") is not None
                        else q.get("needsReview", False)
                    ),
                    "reviewReasons": (
                        q.get("review_reasons")
                        if q.get("review_reasons") is not None
                        else q.get("reviewReasons") or []
                    ),
                    "auditFlags": (
                        q.get("audit_flags")
                        if q.get("audit_flags") is not None
                        else q.get("auditFlags") or []
                    ),
                    "typo_notes": q.get("typo_notes") or q.get("typoNotes"),
                    "studentAnswer": q.get("student_answer", ""),
                    "question_type": q.get("question_type") or q.get("questionType"),
                    "isCorrect": q.get("is_correct", False),
                    "scoring_point_results": scoring_results,
                    "page_indices": q.get("page_indices", []),
                    "is_cross_page": q.get("is_cross_page", False),
                    "merge_source": q.get("merge_source")
                })
        # 兼容旧格式 grading_results
        elif r.get("grading_results"):
            for q in r.get("grading_results", []):
                scoring_results = q.get("scoring_point_results") or q.get("scoring_results") or []
                question_results.append({
                    "questionId": str(q.get("question_id", "")),
                    "score": q.get("score", 0),
                    "maxScore": q.get("max_score", 0),
                    "feedback": q.get("feedback", ""),
                    "confidence": q.get("confidence", 0),
                    "confidence_reason": q.get("confidence_reason") or q.get("confidenceReason"),
                    "self_critique": q.get("self_critique") or q.get("selfCritique"),
                    "self_critique_confidence": q.get("self_critique_confidence") or q.get("selfCritiqueConfidence"),
                    "rubric_refs": q.get("rubric_refs") or q.get("rubricRefs"),
                    "review_summary": q.get("review_summary") or q.get("reviewSummary"),
                    "review_corrections": q.get("review_corrections") or q.get("reviewCorrections"),
                    "needsReview": (
                        q.get("needs_review")
                        if q.get("needs_review") is not None
                        else q.get("needsReview", False)
                    ),
                    "reviewReasons": (
                        q.get("review_reasons")
                        if q.get("review_reasons") is not None
                        else q.get("reviewReasons") or []
                    ),
                    "auditFlags": (
                        q.get("audit_flags")
                        if q.get("audit_flags") is not None
                        else q.get("auditFlags") or []
                    ),
                    "typo_notes": q.get("typo_notes") or q.get("typoNotes"),
                    "studentAnswer": q.get("student_answer", ""),
                    "question_type": q.get("question_type") or q.get("questionType"),
                    "scoring_point_results": scoring_results,
                    "page_indices": q.get("page_indices", []),
                    "is_cross_page": q.get("is_cross_page", False),
                    "merge_source": q.get("merge_source")
                })
        # å…¼å®¹ export_data çš„ question_results
        elif r.get("question_results"):
            for q in r.get("question_results", []):
                scoring_results = q.get("scoring_point_results") or q.get("scoring_results") or []
                question_results.append({
                    "questionId": str(q.get("question_id", "")),
                    "score": q.get("score", 0),
                    "maxScore": q.get("max_score", 0),
                    "feedback": q.get("feedback", ""),
                    "confidence": q.get("confidence", 0),
                    "confidence_reason": q.get("confidence_reason") or q.get("confidenceReason"),
                    "self_critique": q.get("self_critique") or q.get("selfCritique"),
                    "self_critique_confidence": q.get("self_critique_confidence") or q.get("selfCritiqueConfidence"),
                    "rubric_refs": q.get("rubric_refs") or q.get("rubricRefs"),
                    "review_summary": q.get("review_summary") or q.get("reviewSummary"),
                    "review_corrections": q.get("review_corrections") or q.get("reviewCorrections"),
                    "needsReview": (
                        q.get("needs_review")
                        if q.get("needs_review") is not None
                        else q.get("needsReview", False)
                    ),
                    "reviewReasons": (
                        q.get("review_reasons")
                        if q.get("review_reasons") is not None
                        else q.get("reviewReasons") or []
                    ),
                    "auditFlags": (
                        q.get("audit_flags")
                        if q.get("audit_flags") is not None
                        else q.get("auditFlags") or []
                    ),
                    "typo_notes": q.get("typo_notes") or q.get("typoNotes"),
                    "studentAnswer": q.get("student_answer", ""),
                    "question_type": q.get("question_type") or q.get("questionType"),
                    "isCorrect": q.get("is_correct", False),
                    "scoring_point_results": scoring_results,
                    "page_indices": q.get("page_indices", []),
                    "is_cross_page": q.get("is_cross_page", False),
                    "merge_source": q.get("merge_source"),
                })
        # 从 page_results 提取
        elif r.get("page_results"):
            for page in r.get("page_results", []):
                if page.get("status") == "completed":
                    # 从页面结果中提取题目详情
                    for q in page.get("question_details", []):
                        scoring_results = q.get("scoring_point_results") or q.get("scoring_results") or []
                        page_indices = q.get("page_indices")
                        if not page_indices and page.get("page_index") is not None:
                            page_indices = [page.get("page_index")]
                        question_results.append({
                            "questionId": str(q.get("question_id", "")),
                            "score": q.get("score", 0),
                            "maxScore": q.get("max_score", 0),
                            "feedback": q.get("feedback", ""),
                            "confidence": q.get("confidence", 0),
                            "confidence_reason": q.get("confidence_reason") or q.get("confidenceReason"),
                            "self_critique": q.get("self_critique") or q.get("selfCritique"),
                            "self_critique_confidence": q.get("self_critique_confidence") or q.get("selfCritiqueConfidence"),
                            "rubric_refs": q.get("rubric_refs") or q.get("rubricRefs"),
                            "review_summary": q.get("review_summary") or q.get("reviewSummary"),
                            "review_corrections": q.get("review_corrections") or q.get("reviewCorrections"),
                            "needsReview": (
                                q.get("needs_review")
                                if q.get("needs_review") is not None
                                else q.get("needsReview", False)
                            ),
                            "reviewReasons": (
                                q.get("review_reasons")
                                if q.get("review_reasons") is not None
                                else q.get("reviewReasons") or []
                            ),
                            "auditFlags": (
                                q.get("audit_flags")
                                if q.get("audit_flags") is not None
                                else q.get("auditFlags") or []
                            ),
                            "typo_notes": q.get("typo_notes") or q.get("typoNotes"),
                            "studentAnswer": q.get("student_answer", ""),
                            "question_type": q.get("question_type") or q.get("questionType"),
                            "isCorrect": q.get("is_correct", False),
                            "scoring_point_results": scoring_results,
                            "page_indices": page_indices or [],
                            "is_cross_page": q.get("is_cross_page", False),
                            "merge_source": q.get("merge_source")
                        })
        
        computed_score = sum(_safe_float(q.get("score", 0)) for q in question_results)
        computed_max = sum(_safe_float(q.get("maxScore", 0)) for q in question_results)
        raw_score = _safe_float(r.get("total_score", r.get("score", 0)))
        raw_max = _safe_float(r.get("max_total_score", r.get("max_score", 0)))
        final_score = raw_score if raw_score > 0 or computed_score <= 0 else computed_score
        final_max = raw_max if raw_max > 0 or computed_max <= 0 else computed_max

        student_summary = r.get("student_summary") or r.get("studentSummary")
        self_audit = r.get("self_audit") or r.get("selfAudit")
        formatted.append({
            "studentName": r.get("student_key") or r.get("student_name") or r.get("student_id", "Unknown"),
            "score": final_score,
            "maxScore": final_max if final_max > 0 else 0,
            "startPage": r.get("start_page"),   # 🔥 新增：学生页面范围
            "endPage": r.get("end_page"),       # 🔥 新增：学生页面范围
            "questionResults": question_results,
            "confidence": r.get("confidence", 0),
            "needsConfirmation": r.get("needs_confirmation", False),
            "gradingMode": r.get("grading_mode") or r.get("gradingMode"),
            "studentSummary": student_summary,
            "selfAudit": self_audit
        })
    # #region agent log - 假设D: _format_results_for_frontend 输出
    _write_debug_log({
        "hypothesisId": "D",
        "location": "batch_langgraph.py:_format_results_for_frontend:output",
        "message": "输出的formatted",
        "data": {
            "count": len(formatted),
            "students": [{"name": f.get("studentName"), "score": f.get("score")} for f in formatted],
        },
        "timestamp": int(datetime.now().timestamp() * 1000),
        "sessionId": "debug-session",
    })
    # #endregion
    return formatted


@router.websocket("/ws/{batch_id}")
async def websocket_endpoint(websocket: WebSocket, batch_id: str):
    """
    WebSocket 端点，用于实时推送批改进度
    
    前端通过此端点接收 LangGraph 的实时执行进度
    """
    await websocket.accept()

    cached_images = batch_image_cache.get(batch_id, {})
    if cached_images:
        try:
            for key, message in cached_images.items():
                if key == "llm_stream_cache":
                    continue
                await websocket.send_json(message)
            stream_cache = cached_images.get("llm_stream_cache")
            if isinstance(stream_cache, dict):
                for stream_message in stream_cache.values():
                    await websocket.send_json({
                        "type": "llm_stream_chunk",
                        **stream_message,
                    })
        except Exception as e:
            logger.warning(f"发送缓存图片失败: {e}")
    
    # 注册连接
    if batch_id not in active_connections:
        active_connections[batch_id] = []
    active_connections[batch_id].append(websocket)
    
    logger.info(f"WebSocket 连接建立: batch_id={batch_id}")

    # 连接建立后尝试发送当前状态快照，避免前端错过早期事件导致卡住
    try:
        orchestrator = await get_orchestrator()
        if orchestrator:
            run_id = f"batch_grading_{batch_id}"
            run_info = await orchestrator.get_run_info(run_id)
            if run_info and run_info.state:
                state = run_info.state or {}
                current_stage = state.get("current_stage", "")
                percentage = state.get("percentage", 0)
                if current_stage or percentage:
                    await websocket.send_json({
                        "type": "grading_progress",
                        "percentage": percentage or 0,
                        "currentStage": current_stage
                    })
                if state.get("student_boundaries"):
                    boundaries = state.get("student_boundaries", [])
                    await websocket.send_json({
                        "type": "students_identified",
                        "studentCount": len(boundaries),
                        "students": [
                            {
                                "studentKey": b.get("student_key", ""),
                                "startPage": b.get("start_page", 0),
                                "endPage": b.get("end_page", 0),
                                "confidence": b.get("confidence", 0),
                                "needsConfirmation": b.get("needs_confirmation", False)
                            }
                            for b in boundaries
                        ]
                    })
                if state.get("parsed_rubric"):
                    parsed = state.get("parsed_rubric", {})
                    await websocket.send_json({
                        "type": "rubric_parsed",
                        "totalQuestions": parsed.get("total_questions", 0),
                        "totalScore": parsed.get("total_score", 0),
                        "generalNotes": parsed.get("general_notes", ""),
                        "rubricFormat": parsed.get("rubric_format", ""),
                        "questions": [
                            {
                                "questionId": q.get("question_id", ""),
                                "maxScore": q.get("max_score", 0),
                                "questionText": q.get("question_text", ""),
                                "standardAnswer": q.get("standard_answer", ""),
                                "gradingNotes": q.get("grading_notes", ""),
                          "scoringPoints": [
                              {
                                  "pointId": sp.get("point_id") or sp.get("pointId") or f"{q.get('question_id')}.{idx + 1}",
                                  "description": sp.get("description", ""),
                                  "expectedValue": sp.get("expected_value") or sp.get("expectedValue", ""),
                                  "keywords": sp.get("keywords") or [],
                                  "score": sp.get("score", 0),
                                  "isRequired": sp.get("is_required", True),
                              }
                              for idx, sp in enumerate(q.get("scoring_points", []))
                          ],
                          "deductionRules": [
                              {
                                  "ruleId": dr.get("rule_id") or dr.get("ruleId") or f"{q.get('question_id')}.d{idx + 1}",
                                  "description": dr.get("description", ""),
                                  "deduction": dr.get("deduction", dr.get("score", 0)),
                                  "conditions": dr.get("conditions") or dr.get("when") or "",
                              }
                              for idx, dr in enumerate(q.get("deduction_rules") or q.get("deductionRules") or [])
                          ],
                                "alternativeSolutions": [
                                    {
                                        "description": alt.get("description", ""),
                                        "scoringCriteria": alt.get("scoring_criteria", ""),
                                        "note": alt.get("note", ""),
                                    }
                                    for alt in q.get("alternative_solutions", [])
                                ]
                            }
                            for q in parsed.get("questions", [])
                        ]
                    })
                if run_info.status and run_info.status.value == "completed":
                    student_results = state.get("student_results", [])
                    formatted_results = _format_results_for_frontend(student_results)
                    class_report = state.get("class_report")
                    if not class_report and state.get("export_data"):
                        class_report = state.get("export_data", {}).get("class_report")
                    await websocket.send_json({
                        "type": "workflow_completed",
                        "message": f"Grading completed, processed {len(formatted_results)} students",
                        "results": formatted_results,
                        "cross_page_questions": state.get("cross_page_questions", []),
                        "classReport": class_report
                    })
    except Exception as e:
        logger.warning(f"发送状态快照失败: {e}")
    
    try:
        # 保持连接，等待客户端消息或断开
        while True:
            if not _is_ws_connected(websocket):
                break
            data = await websocket.receive_text()
            logger.debug(f"收到 WebSocket 消息: batch_id={batch_id}, data={data}")
            
    except (WebSocketDisconnect, RuntimeError) as exc:
        logger.info(f"WebSocket 连接断开: batch_id={batch_id}, reason={exc}")
        if batch_id in active_connections and websocket in active_connections[batch_id]:
            active_connections[batch_id].remove(websocket)
            if not active_connections[batch_id]:
                del active_connections[batch_id]
        return
    except Exception as exc:
        logger.warning(f"WebSocket 接收异常: batch_id={batch_id}, error={exc}")
        logger.info(f"WebSocket 连接断开: batch_id={batch_id}")
        if batch_id in active_connections and websocket in active_connections[batch_id]:
            active_connections[batch_id].remove(websocket)
            if not active_connections[batch_id]:
                del active_connections[batch_id]


@router.get("/status/{batch_id}", response_model=BatchStatusResponse)
async def get_batch_status(
    batch_id: str,
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    查询批次状态（从 LangGraph Orchestrator）
    
    Args:
        batch_id: 批次 ID
        orchestrator: LangGraph Orchestrator
        
    Returns:
        BatchStatusResponse: 批次状态
    """
    try:
        if not orchestrator:
            raise HTTPException(status_code=503, detail="编排器未初始化")
        
        # 构建 run_id（与 start_run 中的格式一致）
        run_id = f"batch_grading_{batch_id}"
        
        # 从 LangGraph Orchestrator 查询状态
        run_info = await orchestrator.get_run_info(run_id)
        
        if not run_info:
            raise HTTPException(status_code=404, detail="批次不存在")
        
        state = run_info.state or {}
        
        return BatchStatusResponse(
            batch_id=batch_id,
            exam_id=state.get("exam_id", ""),
            status=run_info.status.value,
            total_students=len(state.get("student_boundaries", [])),
            completed_students=len(state.get("student_results", [])),
            unidentified_pages=0,
            results=state.get("student_results")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询批次状态失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/rubric/{batch_id}", response_model=RubricReviewContextResponse)
async def get_rubric_review_context(
    batch_id: str,
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """获取 rubric review 页面上下文"""
    try:
        if not orchestrator:
            raise HTTPException(status_code=503, detail="编排器未初始化")

        run_id = f"batch_grading_{batch_id}"
        run_info = await orchestrator.get_run_info(run_id)
        if not run_info:
            raise HTTPException(status_code=404, detail="批次不存在")

        state = run_info.state or {}
        parsed_rubric = state.get("parsed_rubric")

        cached = batch_image_cache.get(batch_id, {})
        cached_images = cached.get("rubric_images_ready", {}).get("images") if cached else None
        rubric_images: List[str] = cached_images or []

        if not rubric_images and state.get("rubric_images"):
            try:
                rubric_images = []
                for img in state.get("rubric_images", []):
                    if isinstance(img, (bytes, bytearray)):
                        rubric_images.append(base64.b64encode(img).decode("utf-8"))
                    elif isinstance(img, str) and img:
                        rubric_images.append(img)
            except Exception as exc:
                logger.warning(f"Failed to convert rubric images: {exc}")
        return RubricReviewContextResponse(
            batch_id=batch_id,
            status=run_info.status.value if run_info.status else None,
            current_stage=state.get("current_stage"),
            parsed_rubric=parsed_rubric,
            rubric_images=rubric_images,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"获取 rubric 上下文失败: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取失败: {str(exc)}")


@router.get("/results-review/{batch_id}", response_model=ResultsReviewContextResponse)
async def get_results_review_context(
    batch_id: str,
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """获取 results review 页面上下文"""
    try:
        if not orchestrator:
            raise HTTPException(status_code=503, detail="编排器未初始化")

        run_id = f"batch_grading_{batch_id}"
        run_info = await orchestrator.get_run_info(run_id)
        if not run_info:
            raise HTTPException(status_code=404, detail="批次不存在")

        state = run_info.state or {}
        student_results = state.get("student_results", [])
        if not student_results:
            try:
                final_output = await orchestrator.get_final_output(run_id)
                if final_output:
                    student_results = final_output.get("student_results", [])
            except Exception as exc:
                logger.warning(f"获取最终输出失败: {exc}")

        if not student_results:
            export_students = (state.get("export_data") or {}).get("students", [])
            if export_students:
                student_results = export_students

        cached = batch_image_cache.get(batch_id, {})
        cached_images = cached.get("images_ready", {}).get("images") if cached else None
        answer_images: List[str] = cached_images or []

        if not answer_images:
            raw_images = state.get("processed_images") or state.get("answer_images") or []
            try:
                answer_images = []
                for img in raw_images:
                    if isinstance(img, (bytes, bytearray)):
                        answer_images.append(base64.b64encode(img).decode("utf-8"))
                    elif isinstance(img, str) and img:
                        answer_images.append(img)
            except Exception as exc:
                logger.warning(f"Failed to convert answer images: {exc}")
        return ResultsReviewContextResponse(
            batch_id=batch_id,
            status=run_info.status.value if run_info.status else None,
            current_stage=state.get("current_stage"),
            student_results=_format_results_for_frontend(student_results),
            answer_images=answer_images,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"获取 results 上下文失败: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取失败: {str(exc)}")


@router.get("/results/{batch_id}")
async def get_batch_results(
    batch_id: str,
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    获取批次批改结果（从 LangGraph Orchestrator）
    
    Args:
        batch_id: 批次 ID
        orchestrator: LangGraph Orchestrator
        
    Returns:
        批改结果
    """
    try:
        if not orchestrator:
            raise HTTPException(status_code=503, detail="编排器未初始化")
        
        # 构建 run_id（与 start_run 中的格式一致）
        run_id = f"batch_grading_{batch_id}"
        
        run_info = await orchestrator.get_run_info(run_id)
        
        if not run_info:
            raise HTTPException(status_code=404, detail="批次不存在")
        
        state = run_info.state or {}
        
        # 优先从 student_results 获取结果
        student_results = state.get("student_results", [])
        
        # 如果没有 student_results，尝试从 orchestrator 获取最终输出
        if not student_results:
            try:
                final_output = await orchestrator.get_final_output(run_id)
                if final_output:
                    student_results = final_output.get("student_results", [])
            except Exception as e:
                logger.warning(f"获取最终输出失败: {e}")
        
        return {
            "batch_id": batch_id,
            "status": run_info.status.value,
            "results": _format_results_for_frontend(student_results),
            "class_report": state.get("class_report")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取批改结果失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.get("/full-results/{batch_id}")
async def get_full_batch_results(
    batch_id: str,
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    获取批次完整批改结果（包含跨页题目信息）
    
    Args:
        batch_id: 批次 ID
        orchestrator: LangGraph Orchestrator
        
    Returns:
        完整批改结果（包含跨页题目信息）
    """
    try:
        if not orchestrator:
            raise HTTPException(status_code=503, detail="编排器未初始化")
        
        run_id = f"batch_grading_{batch_id}"
        run_info = await orchestrator.get_run_info(run_id)
        
        if not run_info:
            raise HTTPException(status_code=404, detail="批次不存在")
        
        state = run_info.state or {}
        student_results = state.get("student_results", [])
        cross_page_questions = state.get("cross_page_questions", [])
        parsed_rubric = state.get("parsed_rubric", {})
        class_report = state.get("class_report") or state.get("export_data", {}).get("class_report")
        
        return {
            "batch_id": batch_id,
            "status": run_info.status.value,
            "results": _format_results_for_frontend(student_results),
            "cross_page_questions": cross_page_questions,
            "parsed_rubric": parsed_rubric,
            "class_report": class_report,
            "total_students": len(student_results),
            "total_score": parsed_rubric.get("total_score", 100) if parsed_rubric else 100
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取完整批改结果失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.get("/cross-page-questions/{batch_id}")
async def get_cross_page_questions(
    batch_id: str,
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    获取跨页题目信息
    
    Args:
        batch_id: 批次 ID
        orchestrator: LangGraph Orchestrator
        
    Returns:
        跨页题目信息列表
    """
    try:
        if not orchestrator:
            raise HTTPException(status_code=503, detail="编排器未初始化")
        
        run_id = f"batch_grading_{batch_id}"
        run_info = await orchestrator.get_run_info(run_id)
        
        if not run_info:
            raise HTTPException(status_code=404, detail="批次不存在")
        
        state = run_info.state or {}
        cross_page_questions = state.get("cross_page_questions", [])
        
        return cross_page_questions
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取跨页题目信息失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


class ConfirmBoundaryRequest(BaseModel):
    """确认学生边界请求"""
    batch_id: str = Field(..., description="批次 ID")
    student_key: str = Field(..., description="学生标识")
    confirmed_pages: List[int] = Field(..., description="确认的页面索引列表")


class RubricReviewRequest(BaseModel):
    """提交评分标准人工确认结果"""
    batch_id: str = Field(..., description="批次 ID")
    action: str = Field(..., description="approve/update/reparse")
    parsed_rubric: Optional[Dict[str, Any]] = Field(None, description="修正后的评分标准")
    selected_question_ids: Optional[List[str]] = Field(None, description="仅重修正的问题 ID 列表")
    notes: Optional[str] = Field(None, description="补充说明")


class ResultsReviewRequest(BaseModel):
    """提交批改结果人工确认结果"""
    batch_id: str = Field(..., description="批次 ID")
    action: str = Field(..., description="approve/update/regrade")
    results: Optional[List[Dict[str, Any]]] = Field(None, description="修正后的结果")
    regrade_items: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="需要重新批改的题目项",
    )
    notes: Optional[str] = Field(None, description="补充说明")


@router.post("/review/rubric")
async def submit_rubric_review(
    request: RubricReviewRequest,
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """提交评分标准复核结果，恢复 workflow"""
    try:
        if not orchestrator:
            raise HTTPException(status_code=503, detail="编排器未初始化")

        action = request.action.lower().strip()
        if action not in ("approve", "update", "override", "reparse"):
            raise HTTPException(status_code=400, detail="无效的 review action")

        run_id = f"batch_grading_{request.batch_id}"
        run_info = await orchestrator.get_run_info(run_id)
        if not run_info:
            raise HTTPException(status_code=404, detail="批次不存在")

        payload: Dict[str, Any] = {
            "action": action,
        }
        if request.parsed_rubric is not None:
            payload["parsed_rubric"] = request.parsed_rubric
        if request.selected_question_ids:
            payload["selected_question_ids"] = request.selected_question_ids
        if request.notes:
            payload["notes"] = request.notes

        success = await orchestrator.send_event(run_id, "review_signal", payload)
        if not success:
            raise HTTPException(status_code=409, detail="批次未处于可复核状态")

        cached = batch_image_cache.get(request.batch_id)
        if cached and "review_required" in cached:
            cached.pop("review_required", None)

        return {"success": True, "message": "评分标准复核已提交"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"提交评分标准复核失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"提交失败: {str(e)}")


@router.post("/review/results")
async def submit_results_review(
    request: ResultsReviewRequest,
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """提交批改结果复核，恢复 workflow"""
    try:
        if not orchestrator:
            raise HTTPException(status_code=503, detail="编排器未初始化")

        action = request.action.lower().strip()
        if action not in ("approve", "update", "override", "regrade"):
            raise HTTPException(status_code=400, detail="无效的 review action")

        run_id = f"batch_grading_{request.batch_id}"
        run_info = await orchestrator.get_run_info(run_id)
        if not run_info:
            raise HTTPException(status_code=404, detail="批次不存在")

        payload: Dict[str, Any] = {
            "action": action,
        }
        if request.results is not None:
            payload["results"] = request.results
        if request.regrade_items is not None:
            payload["regrade_items"] = request.regrade_items
        if request.notes:
            payload["notes"] = request.notes

        success = await orchestrator.send_event(run_id, "review_signal", payload)
        if not success:
            raise HTTPException(status_code=409, detail="批次未处于可复核状态")

        cached = batch_image_cache.get(request.batch_id)
        if cached and "review_required" in cached:
            cached.pop("review_required", None)

        return {"success": True, "message": "批改结果复核已提交"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"提交批改复核失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"提交失败: {str(e)}")


@router.post("/confirm-boundary")
async def confirm_student_boundary(
    request: ConfirmBoundaryRequest,
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    确认学生边界
    
    当 AI 识别的学生边界不准确时，允许用户手动确认
    
    Args:
        request: 确认边界请求
        orchestrator: LangGraph Orchestrator
        
    Returns:
        确认结果
    """
    try:
        if not orchestrator:
            raise HTTPException(status_code=503, detail="编排器未初始化")
        
        run_id = f"batch_grading_{request.batch_id}"
        run_info = await orchestrator.get_run_info(run_id)
        
        if not run_info:
            raise HTTPException(status_code=404, detail="批次不存在")
        
        # 更新状态中的学生边界
        state = run_info.state or {}
        student_boundaries = state.get("student_boundaries", [])
        
        # 查找并更新对应学生的边界
        updated = False
        for boundary in student_boundaries:
            if boundary.get("student_key") == request.student_key:
                boundary["pages"] = request.confirmed_pages
                boundary["confirmed"] = True
                updated = True
                break
        
        if not updated:
            # 如果没有找到，添加新的边界
            student_boundaries.append({
                "student_key": request.student_key,
                "pages": request.confirmed_pages,
                "confirmed": True
            })
        
        logger.info(f"学生边界已确认: batch_id={request.batch_id}, student_key={request.student_key}")
        
        return {
            "success": True,
            "message": f"学生 {request.student_key} 的边界已确认"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"确认学生边界失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"确认失败: {str(e)}")
