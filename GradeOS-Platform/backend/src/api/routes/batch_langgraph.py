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
import inspect
import base64
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from fastapi import (
    APIRouter,
    HTTPException,
    UploadFile,
    File,
    Form,
    WebSocket,
    WebSocketDisconnect,
    Depends,
)
from starlette.websockets import WebSocketState
from pydantic import BaseModel, Field
import fitz
from PIL import Image
import os
import redis.asyncio as redis
from redis.exceptions import RedisError

from src.config.runtime_controls import get_runtime_controls
from src.models.enums import SubmissionStatus
from src.orchestration.base import Orchestrator, RunStatus
from src.api.dependencies import get_orchestrator
from src.utils.image import to_jpeg_bytes, pil_to_jpeg_bytes
from src.utils.pool_manager import UnifiedPoolManager, PoolNotInitializedError
from src.services.grading_run_control import GradingRunSnapshot, get_run_controller
from src.services.file_storage import get_file_storage_service, StoredFile

# PostgreSQL 作为主存储
from src.db import (
    GradingHistory,
    StudentGradingResult,
    save_grading_history,
    save_student_result,
    upsert_homework_submission_grade,
    list_class_students,
    get_grading_history,
    get_student_results,
    get_page_images,
    # PostgreSQL 图片存储
    save_batch_images_concurrent,
    get_batch_images_as_bytes_list,
)


logger = logging.getLogger(__name__)


async def _maybe_await(value):
    return await value if inspect.isawaitable(value) else value
router = APIRouter(prefix="/batch", tags=["批量提交"])

# 存储活跃的 WebSocket 连接
active_connections: Dict[str, List[WebSocket]] = {}
# WebSocket 锁：防止并发写入导致的竞态条件  
ws_locks: Dict[int, asyncio.Lock] = {}
# 缓存图片，避免 images_ready 早于 WebSocket 连接导致前端丢失
batch_image_cache: Dict[str, Dict[str, dict]] = {}
_active_stream_tasks: Dict[str, asyncio.Task] = {}
_RUNTIME_CONTROLS = get_runtime_controls()
DEBUG_LOG_PATH = os.getenv("GRADEOS_DEBUG_LOG_PATH")
TEACHER_MAX_ACTIVE_RUNS = _RUNTIME_CONTROLS.teacher_max_active_runs
RUN_QUEUE_POLL_SECONDS = _RUNTIME_CONTROLS.run_queue_poll_seconds
# 修复：设置默认超时为 60 秒，避免无限等待
RUN_QUEUE_TIMEOUT_SECONDS = _RUNTIME_CONTROLS.run_queue_timeout_seconds
RUN_UPLOAD_QUEUE_WATERMARK = _RUNTIME_CONTROLS.upload_queue_watermark
RUN_UPLOAD_ACTIVE_WATERMARK = _RUNTIME_CONTROLS.upload_active_watermark
REDIS_PROGRESS_TTL_SECONDS = int(os.getenv("REDIS_PROGRESS_TTL_SECONDS", "86400"))
REDIS_PROGRESS_KEY_PREFIX = os.getenv("REDIS_PROGRESS_KEY_PREFIX", "batch_progress")
_REDIS_CACHE_SKIP_TYPES = {"images_ready", "rubric_images_ready", "llm_stream_chunk"}
_REDIS_CLIENT: Optional[redis.Redis] = None
_REDIS_CLIENT_CHECKED: bool = False
_BATCH_IMAGE_CACHE_MAX_BATCHES = _RUNTIME_CONTROLS.batch_image_cache_max_batches


def _is_ws_connected(websocket: WebSocket) -> bool:
    return (
        websocket.client_state == WebSocketState.CONNECTED
        and websocket.application_state == WebSocketState.CONNECTED
    )


def _get_batch_cache_bucket(batch_id: str) -> Dict[str, Any]:
    """Get/create a bounded in-memory cache bucket for a batch."""
    if batch_id not in batch_image_cache:
        if _BATCH_IMAGE_CACHE_MAX_BATCHES > 0:
            while len(batch_image_cache) >= _BATCH_IMAGE_CACHE_MAX_BATCHES:
                oldest = next(iter(batch_image_cache), None)
                if oldest is None:
                    break
                batch_image_cache.pop(oldest, None)
        batch_image_cache[batch_id] = {}
    return batch_image_cache[batch_id]


def _discard_connection(batch_id: str, websocket: WebSocket) -> None:
    connections = active_connections.get(batch_id)
    if not connections:
        return
    try:
        connections.remove(websocket)
    except ValueError:
        return
    if not connections:
        active_connections.pop(batch_id, None)
    # 清理 WebSocket 锁
    ws_id = id(websocket)
    ws_locks.pop(ws_id, None)




def _progress_cache_key(batch_id: str) -> str:
    return f"{REDIS_PROGRESS_KEY_PREFIX}:{batch_id}"


def _decode_redis_value(value: Any) -> str:
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="ignore")
    return str(value)


async def _get_redis_client() -> Optional[redis.Redis]:
    global _REDIS_CLIENT, _REDIS_CLIENT_CHECKED
    if _REDIS_CLIENT_CHECKED:
        return _REDIS_CLIENT
    _REDIS_CLIENT_CHECKED = True
    try:
        pool_manager = await UnifiedPoolManager.get_instance()
        if pool_manager.is_initialized:
            _REDIS_CLIENT = pool_manager.get_redis_client()
    except PoolNotInitializedError:
        _REDIS_CLIENT = None
    except Exception as exc:
        logger.debug(f"Redis client unavailable: {exc}")
        _REDIS_CLIENT = None
    return _REDIS_CLIENT


async def _clear_progress_fields(
    redis_client: redis.Redis,
    cache_key: str,
    prefixes: Optional[List[str]] = None,
    fields: Optional[List[str]] = None,
) -> None:
    to_delete: List[Any] = []
    if fields:
        to_delete.extend(fields)
    if prefixes:
        try:
            existing_fields = await redis_client.hkeys(cache_key)
        except RedisError as exc:
            logger.debug(f"Failed to fetch Redis fields for cleanup: {exc}")
            existing_fields = []
        for field in existing_fields:
            field_name = _decode_redis_value(field)
            if any(field_name.startswith(prefix) for prefix in prefixes):
                to_delete.append(field)
    if not to_delete:
        return
    try:
        await redis_client.hdel(cache_key, *to_delete)
    except RedisError as exc:
        logger.debug(f"Failed to cleanup Redis progress cache: {exc}")


async def _cache_progress_message(batch_id: str, message: dict) -> None:
    msg_type = message.get("type", "unknown")
    if msg_type in _REDIS_CACHE_SKIP_TYPES:
        return

    redis_client = await _get_redis_client()
    if not redis_client:
        return

    cache_key = _progress_cache_key(batch_id)
    field = msg_type
    if msg_type == "workflow_update":
        node_id = message.get("nodeId")
        if node_id:
            field = f"{msg_type}:{node_id}"

    try:
        payload = json.dumps(message, ensure_ascii=False, default=str)
        await redis_client.hset(cache_key, field, payload)
        await redis_client.expire(cache_key, REDIS_PROGRESS_TTL_SECONDS)
        if msg_type in ("review_completed", "workflow_completed"):
            await _clear_progress_fields(
                redis_client,
                cache_key,
                fields=["review_required"],
            )
    except (TypeError, ValueError) as exc:
        logger.debug(f"Failed to serialize progress message: {exc}")
    except RedisError as exc:
        logger.debug(f"Failed to cache progress message in Redis: {exc}")


async def _load_cached_progress_messages(batch_id: str) -> List[dict]:
    redis_client = await _get_redis_client()
    if not redis_client:
        return []
    cache_key = _progress_cache_key(batch_id)
    try:
        entries = await redis_client.hgetall(cache_key)
    except RedisError as exc:
        logger.debug(f"Failed to fetch cached progress from Redis: {exc}")
        return []

    messages: List[dict] = []
    for field in sorted(entries.keys(), key=_decode_redis_value):
        payload = entries.get(field)
        if payload is None:
            continue
        raw = _decode_redis_value(payload)
        try:
            message = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(message, dict):
            messages.append(message)
    return messages


def _safe_to_jpeg_bytes(image_bytes: bytes, label: str) -> bytes:
    try:
        return to_jpeg_bytes(image_bytes)
    except Exception as exc:
        logger.debug(f"Failed to convert image to JPEG ({label}): {exc}")
        return image_bytes


def _normalize_teacher_key(teacher_id: Optional[str]) -> str:
    if teacher_id and teacher_id.strip():
        return teacher_id.strip()
    return "anonymous"


async def _enforce_submit_backpressure(run_controller, teacher_key: str) -> None:
    if not run_controller:
        return
    capacity = await run_controller.get_teacher_capacity(teacher_key)
    active_count = int(capacity.get("active_count", 0))
    queued_count = int(capacity.get("queued_count", 0))

    if RUN_UPLOAD_ACTIVE_WATERMARK > 0 and active_count >= RUN_UPLOAD_ACTIVE_WATERMARK:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Too many active runs for teacher={teacher_key}. "
                f"active={active_count}, limit={RUN_UPLOAD_ACTIVE_WATERMARK}"
            ),
        )

    if RUN_UPLOAD_QUEUE_WATERMARK > 0 and queued_count >= RUN_UPLOAD_QUEUE_WATERMARK:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Queue watermark reached for teacher={teacher_key}. "
                f"queued={queued_count}, limit={RUN_UPLOAD_QUEUE_WATERMARK}"
            ),
        )


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
    current_stage: Optional[str] = None
    error: Optional[str] = None
    total_students: int = Field(0, description="识别到的学生数")
    completed_students: int = Field(0, description="已完成批改的学生数")
    unidentified_pages: int = Field(0, description="未识别学生的页数")
    results: Optional[List[dict]] = Field(None, description="批改结果")


class ActiveRunItem(BaseModel):
    batch_id: str
    status: str
    class_id: Optional[str] = None
    homework_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    total_pages: Optional[int] = None
    progress: Optional[float] = None
    current_stage: Optional[str] = None


class ActiveRunsResponse(BaseModel):
    teacher_id: str
    runs: List[ActiveRunItem]


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
    parsed_rubric: Optional[dict] = None  # 添加 parsed_rubric 字段


def _pdf_to_images(pdf_path: str, dpi: int = 150) -> List[bytes]:
    """将 PDF 转换为图像列表"""
    pdf_doc = fitz.open(pdf_path)
    images = []

    for page_num in range(len(pdf_doc)):
        page = pdf_doc[page_num]
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        images.append(pil_to_jpeg_bytes(img))

    pdf_doc.close()
    return images


async def broadcast_progress(batch_id: str, message: dict):
    """向所有连接的 WebSocket 客户端广播进度"""
    msg_type = message.get("type", "unknown")
    if msg_type in ("images_ready", "rubric_images_ready", "review_required"):
        cached = _get_batch_cache_bucket(batch_id)
        cached[msg_type] = message
    if msg_type == "llm_stream_chunk":
        node_id = message.get("nodeId") or ""
        if node_id in ("rubric_parse", "rubric_self_review", "rubric_review"):
            cached = _get_batch_cache_bucket(batch_id)
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
    if msg_type in (
        "workflow_update",
        "grading_progress",
        "workflow_completed",
        "workflow_error",
        "batch_error",
    ):
        run_updates: Dict[str, Any] = {"updated_at": datetime.now().isoformat()}
        if msg_type == "workflow_update":
            status = message.get("status")
            if status == "pending":
                run_updates["status"] = "queued"
            elif status in ("running", "paused"):
                run_updates["status"] = "running"
            elif status == "completed":
                run_updates["status"] = "completed"
                run_updates["completed_at"] = run_updates["updated_at"]
            elif status == "failed":
                run_updates["status"] = "failed"
                run_updates["completed_at"] = run_updates["updated_at"]
            node_id = message.get("nodeId")
            if node_id:
                run_updates["current_stage"] = node_id
        elif msg_type == "grading_progress":
            percentage = message.get("percentage")
            if percentage is not None:
                try:
                    progress_value = float(percentage)
                    if progress_value > 1.0:
                        progress_value = progress_value / 100.0
                    run_updates["progress"] = max(0.0, min(progress_value, 1.0))
                except (TypeError, ValueError):
                    pass
            stage = message.get("currentStage")
            if stage:
                run_updates["current_stage"] = stage
        elif msg_type == "workflow_completed":
            run_updates.update(
                {
                    "status": "completed",
                    "completed_at": run_updates["updated_at"],
                    "progress": 1.0,
                }
            )
        else:
            run_updates.update(
                {
                    "status": "failed",
                    "completed_at": run_updates["updated_at"],
                }
            )
        run_controller = await get_run_controller()
        if run_controller:
            await run_controller.update_run(batch_id, run_updates)
    try:
        await _cache_progress_message(batch_id, message)
    except Exception as exc:
        logger.debug(f"Failed to cache progress message: {exc}")
    if batch_id in active_connections:
        disconnected = []
        for ws in active_connections[batch_id]:
            if not _is_ws_connected(ws):
                disconnected.append(ws)
                continue
            
            # 使用锁保护并发写入
            ws_id = id(ws)
            if ws_id not in ws_locks:
                ws_locks[ws_id] = asyncio.Lock()
            
            try:
                async with ws_locks[ws_id]:
                    await ws.send_json(message)
            except WebSocketDisconnect:
                disconnected.append(ws)
            except (RuntimeError, AssertionError):
                # AssertionError: websockets 库内部 keepalive ping 与应用层写入的竞态条件
                # RuntimeError: 连接已关闭
                # 这两种错误都是预期的，静默处理
                disconnected.append(ws)
            except Exception:
                # 其他错误也静默处理，只记录断开
                disconnected.append(ws)

        # 移除断开的连接
        for ws in disconnected:
            _discard_connection(batch_id, ws)
            # 清理锁
            ws_id = id(ws)
            ws_locks.pop(ws_id, None)


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
    logger.info(f"[_start_run_with_teacher_limit] 开始执行: batch_id={batch_id}")
    
    try:
        run_controller = await get_run_controller()
    except Exception as e:
        logger.error(f"[_start_run_with_teacher_limit] get_run_controller异常: {e}")
        run_controller = None
    
    if run_controller:
        try:
            acquired = await run_controller.try_acquire_slot(
                teacher_key,
                batch_id,
                TEACHER_MAX_ACTIVE_RUNS,
            )
        except Exception as e:
            logger.error(f"[_start_run_with_teacher_limit] try_acquire_slot异常: {e}")
            acquired = False
        
        if not acquired:
            await broadcast_progress(
                batch_id,
                {
                    "type": "workflow_update",
                    "nodeId": "rubric_parse",
                    "status": "pending",
                    "message": "Queued: waiting for grading slot",
                },
            )
            max_wait = RUN_QUEUE_TIMEOUT_SECONDS if RUN_QUEUE_TIMEOUT_SECONDS > 0 else None
            acquired = await run_controller.wait_for_slot(
                teacher_key,
                batch_id,
                TEACHER_MAX_ACTIVE_RUNS,
                RUN_QUEUE_POLL_SECONDS,
                max_wait,
            )
            if not acquired:
                # 等待超时后，强制清理该教师的所有活动槽位并重新尝试
                logger.info(f"[_start_run_with_teacher_limit] 等待超时，尝试强制清理旧槽位并重新获取")
                try:
                    await run_controller.force_clear_teacher_slots(teacher_key)
                    acquired = await run_controller.try_acquire_slot(
                        teacher_key,
                        batch_id,
                        TEACHER_MAX_ACTIVE_RUNS,
                    )
                except Exception as cleanup_err:
                    logger.error(f"[_start_run_with_teacher_limit] 清理槽位失败: {cleanup_err}")
                    acquired = False
                
                if not acquired:
                    logger.info(f"[_start_run_with_teacher_limit] 清理后仍无法获取槽位，任务失败")
                    await run_controller.update_run(
                        batch_id,
                        {"status": "failed", "updated_at": datetime.now().isoformat()},
                    )
                    await run_controller.remove_from_queue(teacher_key, batch_id)
                    await broadcast_progress(
                        batch_id,
                        {
                            "type": "workflow_update",
                            "nodeId": "rubric_parse",
                            "status": "failed",
                            "message": "Queued run timed out - please try again",
                        },
                    )
                    return None
        
        logger.info(f"[_start_run_with_teacher_limit] 成功获取 slot，更新运行状态")
        await run_controller.update_run(
            batch_id,
            {
                "status": "running",
                "started_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            },
        )
    
    run_id: Optional[str] = None
    try:
        logger.info(f"[_start_run_with_teacher_limit] 准备启动 LangGraph run")
        run_id = await orchestrator.start_run(
            graph_name="batch_grading", payload=payload, idempotency_key=batch_id
        )
        logger.info(f"[_start_run_with_teacher_limit] LangGraph 启动成功: batch_id={batch_id}, run_id={run_id}")
        
        stream_task = asyncio.create_task(
            stream_langgraph_progress(
                batch_id=batch_id,
                run_id=run_id,
                orchestrator=orchestrator,
                class_id=class_id,
                homework_id=homework_id,
                student_mapping=student_mapping,
                teacher_key=teacher_key,
            )
        )
        _active_stream_tasks[batch_id] = stream_task
        logger.info(f"[_start_run_with_teacher_limit] 流式任务已创建")
        return run_id
    except Exception as exc:
        logger.error(f"[_start_run_with_teacher_limit] 启动失败: {exc}", exc_info=True)
        if run_controller:
            await run_controller.release_slot(teacher_key, batch_id)
            await run_controller.update_run(
                batch_id,
                {"status": "failed", "updated_at": datetime.now().isoformat()},
            )
        await broadcast_progress(
            batch_id,
            {
                "type": "workflow_update",
                "nodeId": "rubric_parse",
                "status": "failed",
                "message": "Queued run failed to start",
            },
        )
        return None


@router.post("/submit", response_model=BatchSubmissionResponse)
async def submit_batch(
    exam_id: Optional[str] = Form(None, description="考试 ID"),
    rubrics: List[UploadFile] = File(default=[], description="评分标准 PDF（可选）"),
    files: List[UploadFile] = File(..., description="学生作答 PDF"),
    api_key: Optional[str] = Form(None, description="LLM API Key"),
    teacher_id: Optional[str] = Form(None, description="?? ID"),
    auto_identify: bool = Form(True, description="是否自动识别学生身份"),
    student_boundaries: Optional[str] = Form(
        None, description="手动设置的学生边界 (JSON List of page indices)"
    ),
    expected_students: Optional[int] = Form(
        None, description="预期学生数量（强烈建议提供，用于更准确的分割）"
    ),
    expected_total_score: Optional[float] = Form(None, description="Expected total score"),
    # 新增：班级批改上下文
    class_id: Optional[str] = Form(None, description="班级 ID（用于成绩写回）"),
    homework_id: Optional[str] = Form(None, description="作业 ID（用于成绩写回）"),
    student_mapping_json: Optional[str] = Form(
        None, description="学生映射 JSON [{studentId, studentName, startIndex, endIndex}]"
    ),
    enable_review: bool = Form(True, description="是否启用人工交互"),
    grading_mode: Optional[str] = Form(
        None, description="grading mode: standard/assist_teacher/assist_student/auto"
    ),
    orchestrator: Orchestrator = Depends(get_orchestrator),
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
    # 检查 orchestrator 是否可用
    if not orchestrator:
        raise HTTPException(status_code=503, detail="批改服务未初始化，请稍后重试或检查服务配置")

    if not api_key:
        api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="未提供 API Key，请在请求中提供或配置环境变量 LLM_API_KEY/OPENROUTER_API_KEY",
        )

    # 解析学生边界
    parsed_boundaries = []
    if student_boundaries:
        try:
            logger.debug(
                f"接收到原始 student_boundaries: {student_boundaries} (type: {type(student_boundaries)})"
            )
            import json

            parsed_boundaries = json.loads(student_boundaries)
            logger.debug(f"解析后的 manual_boundaries: {parsed_boundaries}")
        except Exception as e:
            logger.debug(f"解析手动学生边界失败: {e}")

    if not exam_id:
        exam_id = str(uuid.uuid4())

    batch_id = str(uuid.uuid4())
    teacher_key = _normalize_teacher_key(teacher_id)
    try:
        run_controller = await get_run_controller()
    except Exception:
        run_controller = None
    await _enforce_submit_backpressure(run_controller, teacher_key)

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
            if file_name.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
                # 图片文件：直接使用内容
                answer_images.append(_safe_to_jpeg_bytes(content, file_name))
                logger.debug(f"读取图片文件: {file_name}, 大小: {len(content)} bytes")
            elif file_name.lower().endswith(".pdf"):
                # PDF 文件：转换为图像
                pdf_path = temp_path / f"answer_{idx}.pdf"
                with open(pdf_path, "wb") as f:
                    f.write(content)
                loop = asyncio.get_event_loop()
                pdf_images = await loop.run_in_executor(None, _pdf_to_images, str(pdf_path), 150)
                answer_images.extend(pdf_images)
                logger.debug(f"PDF 文件 {file_name} 转换为 {len(pdf_images)} 页图片")
            elif file_name.lower().endswith(".txt"):
                # 文本文件：直接使用内容
                answer_images.append(content)
                logger.debug(f"文本文件处理完成: {file_name}, 内容长度={len(content)}")
            else:
                # 尝试作为图片处理（可能没有扩展名）
                answer_images.append(_safe_to_jpeg_bytes(content, file_name))
                logger.debug(f"未知文件类型 {file_name}，尝试作为图片处理")

        total_pages = len(answer_images)

        if run_controller:
            await run_controller.register_run(
                GradingRunSnapshot(
                    batch_id=batch_id,
                    teacher_id=teacher_key,
                    status="queued",
                    class_id=class_id,
                    homework_id=homework_id,
                    created_at=datetime.now().isoformat(),
                    updated_at=datetime.now().isoformat(),
                    total_pages=total_pages,
                )
            )
        logger.info(f"答题文件处理完成: batch_id={batch_id}, 总页数={total_pages}")

        # === 处理评分标准（可选）===
        # Convert images to base64 and cache them immediately
        # (Fix: Rubric images not displaying on frontend)
        if answer_images:
            try:
                base64_images = [base64.b64encode(img).decode("utf-8") for img in answer_images]

                # Cache for direct WebSocket connection
                _get_batch_cache_bucket(batch_id)["images_ready"] = {
                    "type": "images_ready",
                    "images": base64_images,
                }

                # Broadcast (though no clients connected yet usually)
                await broadcast_progress(
                    batch_id, {"type": "images_ready", "images": base64_images}
                )
                logger.info(f"已缓存 {len(base64_images)} 张图片用于前端显示")
            except Exception as e:
                logger.error(f"图片 Base64 转换失败: {e}")

        # === 处理评分标准（可选）===
        rubric_images = []
        if rubrics and len(rubrics) > 0:
            for idx, rubric_file in enumerate(rubrics):
                rubric_name = rubric_file.filename or f"rubric_{idx}"
                rubric_content = await rubric_file.read()

                if rubric_name.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
                    rubric_images.append(_safe_to_jpeg_bytes(rubric_content, rubric_name))
                elif rubric_name.lower().endswith(".pdf"):
                    rubric_path = temp_path / f"rubric_{idx}.pdf"
                    with open(rubric_path, "wb") as f:
                        f.write(rubric_content)
                    loop = asyncio.get_event_loop()
                    pdf_rubric_images = await loop.run_in_executor(
                        None, _pdf_to_images, str(rubric_path), 150
                    )
                    rubric_images.extend(pdf_rubric_images)
                else:
                    rubric_images.append(_safe_to_jpeg_bytes(rubric_content, rubric_name))

            logger.info(f"评分标准处理完成: batch_id={batch_id}, 总页数={len(rubric_images)}")
            if rubric_images:
                try:
                    base64_rubric_images = [
                        base64.b64encode(img).decode("utf-8") for img in rubric_images
                    ]
                    _get_batch_cache_bucket(batch_id)["rubric_images_ready"] = {
                        "type": "rubric_images_ready",
                        "images": base64_rubric_images,
                    }
                    await broadcast_progress(
                        batch_id, {"type": "rubric_images_ready", "images": base64_rubric_images}
                    )
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

        # 📁 持久化存储原始文件到 PostgreSQL（高性能，替代本地文件存储）
        # 使用 PostgreSQL BYTEA 存储，避免本地文件系统瓶颈
        stored_files: List[StoredFile] = []
        use_pg_storage = os.getenv("USE_PG_IMAGE_STORAGE", "true").lower() == "true"
        
        if use_pg_storage:
            try:
                # 并发保存图片到 PostgreSQL（比本地文件快很多）
                answer_count = await save_batch_images_concurrent(
                    batch_id=batch_id,
                    images=answer_images,
                    image_type="answer",
                    max_concurrent=20,  # 高并发写入
                )
                logger.info(f"[PG-Storage] 答题图片保存完成: batch_id={batch_id}, count={answer_count}")
                
                # 保存评分标准图片
                if rubric_images:
                    rubric_count = await save_batch_images_concurrent(
                        batch_id=batch_id,
                        images=rubric_images,
                        image_type="rubric",
                        max_concurrent=10,
                    )
                    logger.info(f"[PG-Storage] 评分标准保存完成: batch_id={batch_id}, count={rubric_count}")
                
            except Exception as e:
                logger.warning(f"[PG-Storage] PostgreSQL 存储失败，回退到本地存储: {e}")
                use_pg_storage = False  # 回退标记
        
        # 回退到本地文件存储（如果 PostgreSQL 存储失败或禁用）
        if not use_pg_storage and os.getenv("ENABLE_FILE_STORAGE", "true").lower() == "true":
            try:
                file_storage = get_file_storage_service()

                # 保存答题文件（以处理后的图片形式）
                answer_filenames = [f"answer_page_{i+1}.jpg" for i in range(len(answer_images))]
                stored_answers = await file_storage.save_answer_files(
                    batch_id=batch_id,
                    files=answer_images,
                    filenames=answer_filenames,
                )
                stored_files.extend(stored_answers)

                # 保存评分标准文件（如果有）
                if rubric_images:
                    rubric_filenames = [f"rubric_page_{i+1}.jpg" for i in range(len(rubric_images))]
                    stored_rubrics = await file_storage.save_rubric_files(
                        batch_id=batch_id,
                        files=rubric_images,
                        filenames=rubric_filenames,
                    )
                    stored_files.extend(stored_rubrics)

                logger.info(
                    f"[FileStorage] 文件存储完成: batch_id={batch_id}, "
                    f"共保存 {len(stored_files)} 个文件"
                )
            except Exception as e:
                logger.warning(f"[FileStorage] 文件存储失败（不影响批改流程）: {e}")

        file_index_by_page: Dict[int, Dict[str, Any]] = {}
        answer_image_refs: List[Dict[str, Any]] = []
        rubric_image_refs: List[Dict[str, Any]] = []
        if stored_files:
            public_base = (
                os.getenv("BACKEND_PUBLIC_URL")
                or os.getenv("PUBLIC_BACKEND_URL")
                or os.getenv("PUBLIC_API_BASE_URL")
                or ""
            )

            def _build_file_url(file_id: str) -> str:
                if public_base:
                    return public_base.rstrip("/") + f"/api/batch/files/{file_id}/download"
                return f"/api/batch/files/{file_id}/download"

            for item in stored_files:
                meta = item.metadata or {}
                if meta.get("type") == "answer":
                    page_idx = meta.get("page_index")
                    if page_idx is not None:
                        file_url = _build_file_url(item.file_id)
                        file_index_by_page[int(page_idx)] = {
                            "file_id": item.file_id,
                            "content_type": item.content_type,
                            "file_url": file_url,
                        }
                        answer_image_refs.append(
                            {
                                "artifact_id": f"answer_page_{int(page_idx)}",
                                "uri": file_url,
                                "metadata": {
                                    "page_index": int(page_idx),
                                    "content_type": item.content_type,
                                    "source": "file_storage",
                                },
                            }
                        )
                elif meta.get("type") == "rubric":
                    file_url = _build_file_url(item.file_id)
                    rubric_image_refs.append(
                        {
                            "artifact_id": f"rubric_page_{meta.get('page_index', len(rubric_image_refs))}",
                            "uri": file_url,
                            "metadata": {
                                "page_index": meta.get("page_index"),
                                "content_type": item.content_type,
                                "source": "file_storage",
                            },
                        }
                    )



        # 🚀 使用 LangGraph Orchestrator 启动批改流程

        # 解析学生映射（班级批改模式）
        student_mapping = []
        if student_mapping_json:
            try:
                import json

                student_mapping = json.loads(student_mapping_json)
                logger.info(
                    f"班级批改模式: class_id={class_id}, homework_id={homework_id}, 学生数={len(student_mapping)}"
                )
            except Exception as e:
                logger.debug(f"解析学生映射失败: {e}")

        resolved_expected_students = expected_students or 0
        if resolved_expected_students <= 0:
            if student_mapping:
                resolved_expected_students = len(student_mapping)
            elif parsed_boundaries:
                resolved_expected_students = len(parsed_boundaries)
            else:
                resolved_expected_students = 1

        payload = {
            "batch_id": batch_id,
            "exam_id": exam_id,
            "temp_dir": str(temp_path),  # 临时目录（用于清理）
            "rubric_images": rubric_images,
            "answer_images": answer_images,
            "answer_image_refs": answer_image_refs,
            "rubric_image_refs": rubric_image_refs,
            "file_index_by_page": file_index_by_page,
            "api_key": api_key,
            "teacher_id": teacher_key,
            # 班级批改上下文（可选）
            "class_id": class_id,
            "homework_id": homework_id,
            "student_mapping": student_mapping,
            "inputs": {
                "rubric": "rubric_content",  # TODO: 解析 rubric
                "auto_identify": auto_identify,
                "manual_boundaries": parsed_boundaries,  # 传递人工边界
                "expected_students": resolved_expected_students,
                "expected_total_score": expected_total_score,
                "enable_review": enable_review,
                "grading_mode": grading_mode or "auto",
                "teacher_id": teacher_key,
            },
        }

        # 启动 LangGraph batch_grading Graph
        logger.info(f"准备启动批改任务: batch_id={batch_id}, answer_images={len(answer_images)}, rubric_images={len(rubric_images)}")
        
        task = asyncio.create_task(
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
        
        # 添加错误处理回调
        def task_done_callback(t):
            try:
                t.result()
            except asyncio.CancelledError:
                logger.info(f"Batch grading task cancelled: batch_id={batch_id}")
            except BaseException as e:
                logger.error(f"Batch grading task failed: batch_id={batch_id}, error={e}", exc_info=True)
        
        task.add_done_callback(task_done_callback)
        logger.info(f"批改任务已提交到事件循环: batch_id={batch_id}")

        return BatchSubmissionResponse(
            batch_id=batch_id,
            status=SubmissionStatus.UPLOADED,
            total_pages=total_pages,
            estimated_completion_time=total_pages * 3,  # Estimated: 3s per page
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
):
    """
    流式监听 LangGraph 执行进度并推送到 WebSocket

    这是实现实时进度推送的关键函数！

    Args:
        batch_id: 批次 ID
        run_id: LangGraph 运行 ID
        orchestrator: LangGraph Orchestrator
    """
    logger.info(f"开始流式监听 LangGraph 进度: batch_id={batch_id}, run_id={run_id}")

    try:
        # 🔥 使用 LangGraph 的流式 API
        async for event in orchestrator.stream_run(run_id):
            event_type = event.get("type")
            node_name = event.get("node")
            data = event.get("data", {})

            logger.debug(
                f"LangGraph 事件: batch_id={batch_id}, type={event_type}, node={node_name}"
            )

            # 将 LangGraph 事件转换为前端 WebSocket 消息
            if event_type == "node_start":
                await broadcast_progress(
                    batch_id,
                    {
                        "type": "workflow_update",
                        "nodeId": _map_node_to_frontend(node_name),
                        "status": "running",
                        "message": f"Running {_get_node_display_name(node_name)}...",
                    },
                )

            elif event_type == "node_end":
                await broadcast_progress(
                    batch_id,
                    {
                        "type": "workflow_update",
                        "nodeId": _map_node_to_frontend(node_name),
                        "status": "completed",
                        "message": f"{_get_node_display_name(node_name)} completed",
                    },
                )

                if node_name in ("confession", "logic_review"):
                    output = data.get("output", {})
                    student_count = None
                    if isinstance(output, dict):
                        if node_name == "confession":
                            student_count = len(
                                output.get("confessed_results")
                                or output.get("student_results")
                                or []
                            )
                        else:
                            student_count = len(
                                output.get("reviewed_results")
                                or output.get("student_results")
                                or []
                            )
                    logger.info(
                        f"[{node_name}] completed: batch_id={batch_id}, students={student_count}"
                    )

                # 处理节点输出
                output = data.get("output", {})
                if isinstance(output, dict):
                    interrupt_payload = output.get("__interrupt__")
                    if interrupt_payload:
                        review_type = (
                            interrupt_payload.get("type")
                            if isinstance(interrupt_payload, dict)
                            else "review_required"
                        )
                        await broadcast_progress(
                            batch_id,
                            {
                                "type": "review_required",
                                "reviewType": review_type,
                                "message": (
                                    interrupt_payload.get("message")
                                    if isinstance(interrupt_payload, dict)
                                    else None
                                ),
                                "payload": interrupt_payload,
                                "nodeId": (
                                    _map_node_to_frontend("grade_batch")
                                    if "grading_retry" in str(review_type)
                                    else (
                                        _map_node_to_frontend("rubric_review")
                                        if "rubric" in str(review_type)
                                        else _map_node_to_frontend("review")
                                    )
                                ),
                            },
                        )
                    # 评分标准解析完成
                    if node_name == "rubric_parse" and output.get("parsed_rubric"):
                        parsed = output["parsed_rubric"]
                        await broadcast_progress(
                            batch_id,
                            {
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
                                        "sourcePages": q.get("source_pages")
                                        or q.get("sourcePages")
                                        or [],
                                        "scoringPoints": [
                                            {
                                                "pointId": sp.get("point_id")
                                                or sp.get("pointId")
                                                or f"{q.get('question_id')}.{idx + 1}",
                                                "description": sp.get("description", ""),
                                                "expectedValue": sp.get("expected_value")
                                                or sp.get("expectedValue", ""),
                                                "keywords": sp.get("keywords") or [],
                                                "score": sp.get("score", 0),
                                                "isRequired": sp.get("is_required", True),
                                            }
                                            for idx, sp in enumerate(q.get("scoring_points", []))
                                        ],
                                        "deductionRules": [
                                            {
                                                "ruleId": dr.get("rule_id")
                                                or dr.get("ruleId")
                                                or f"{q.get('question_id')}.d{idx + 1}",
                                                "description": dr.get("description", ""),
                                                "deduction": dr.get(
                                                    "deduction", dr.get("score", 0)
                                                ),
                                                "conditions": dr.get("conditions")
                                                or dr.get("when")
                                                or "",
                                            }
                                            for idx, dr in enumerate(
                                                q.get("deduction_rules")
                                                or q.get("deductionRules")
                                                or []
                                            )
                                        ],
                                        "alternativeSolutions": [
                                            {
                                                "description": alt.get("description", ""),
                                                "scoringCriteria": alt.get("scoring_criteria", ""),
                                                "note": alt.get("note", ""),
                                            }
                                            for alt in q.get("alternative_solutions", [])
                                        ],
                                    }
                                    for q in parsed.get("questions", [])
                                ],
                            },
                        )

                    # 批改批次完成
                    if node_name == "grade_batch" and output.get("grading_results"):
                        results = output["grading_results"]
                        completed = sum(1 for r in results if r.get("status") == "completed")

                        await broadcast_progress(
                            batch_id,
                            {
                                "type": "batch_complete",
                                "batchSize": len(results),
                                "successCount": completed,
                                "totalScore": sum(
                                    r.get("score", 0)
                                    for r in results
                                    if r.get("status") == "completed"
                                ),
                                "pages": [r.get("page_index") for r in results],
                            },
                        )

                    # 学生识别完成
                    if output.get("student_boundaries"):
                        boundaries = output["student_boundaries"]
                        await broadcast_progress(
                            batch_id,
                            {
                                "type": "students_identified",
                                "studentCount": len(boundaries),
                                "students": [
                                    {
                                        "studentKey": b.get("student_key", ""),
                                        "startPage": b.get("start_page", 0),
                                        "endPage": b.get("end_page", 0),
                                        "confidence": b.get("confidence", 0),
                                        "needsConfirmation": b.get("needs_confirmation", False),
                                    }
                                    for b in boundaries
                                ],
                            },
                        )

                    # 审核完成
                    if node_name == "review" and output.get("review_summary"):
                        await broadcast_progress(
                            batch_id,
                            {"type": "review_completed", "summary": output["review_summary"]},
                        )

                    # 跨页题目合并完成
                    if node_name == "cross_page_merge":
                        cross_page_questions = output.get("cross_page_questions", [])
                        merged_questions = output.get("merged_questions", [])
                        if cross_page_questions:
                            await broadcast_progress(
                                batch_id,
                                {
                                    "type": "cross_page_detected",
                                    "questions": cross_page_questions,
                                    "mergedCount": len(merged_questions),
                                    "crossPageCount": len(cross_page_questions),
                                },
                            )

            elif event_type == "paused":
                # 处理 Graph 中断/暂停（通常是需要人工审核）
                data = event.get("data", {})
                interrupt_value = data.get("interrupt_value")

                logger.info(
                    f"LangGraph 暂停: batch_id={batch_id}, interrupt_value={interrupt_value}"
                )

                if interrupt_value:
                    # 如果有中断 payload，广播 review_required
                    review_type = (
                        interrupt_value.get("type")
                        if isinstance(interrupt_value, dict)
                        else "review_required"
                    )
                    await broadcast_progress(
                        batch_id,
                        {
                            "type": "review_required",
                            "reviewType": review_type,
                            "message": (
                                interrupt_value.get("message")
                                if isinstance(interrupt_value, dict)
                                else None
                            ),
                            "payload": interrupt_value,
                            "nodeId": (
                                _map_node_to_frontend("grade_batch")
                                if "grading_retry" in str(review_type)
                                else (
                                    _map_node_to_frontend("rubric_review")
                                    if "rubric" in str(review_type)
                                    else _map_node_to_frontend("review")
                                )
                            ),
                        },
                    )
                else:
                    # 如果没有 payload，至少通知状态变更
                    await broadcast_progress(
                        batch_id,
                        {
                            "type": "workflow_update",
                            "status": "paused",
                            "message": "Workflow paused (awaiting input)",
                        },
                    )

            elif event_type == "state_update":
                # 推送状态更新
                state = data.get("state", {})

                # 批次进度更新
                if state.get("progress"):
                    progress = state["progress"]
                    await broadcast_progress(
                        batch_id,
                        {
                            "type": "batch_progress",
                            "batchIndex": progress.get("current_batch", 0),
                            "totalBatches": progress.get("total_batches", 1),
                            "successCount": progress.get("success_count", 0),
                            "failureCount": progress.get("failure_count", 0),
                        },
                    )

                # 百分比进度
                if state.get("percentage"):
                    await broadcast_progress(
                        batch_id,
                        {
                            "type": "grading_progress",
                            "percentage": state["percentage"],
                            "currentStage": state.get("current_stage", ""),
                        },
                    )

            elif event_type == "llm_stream":
                # Real-time LLM token streaming
                node_name = event.get("node") or data.get("node", "")
                chunk = data.get("chunk") or data.get("content") or ""
                await broadcast_progress(
                    batch_id,
                    {
                        "type": "llm_stream_chunk",
                        "nodeId": _map_node_to_frontend(node_name) if node_name else None,
                        "nodeName": _get_node_display_name(node_name) if node_name else None,
                        "chunk": chunk,
                    },
                )

            elif event_type == "error":
                await broadcast_progress(
                    batch_id,
                    {"type": "workflow_error", "message": data.get("error", "Unknown error")},
                )

            elif event_type == "completed":
                # 工作流完成 - 获取完整的最终状态
                final_state = data.get("state", {})

                # 从 student_results 获取结果
                student_results = final_state.get("student_results", [])

                # 如果没有 student_results，尝试从 orchestrator 获取最终输出
                if not student_results:
                    try:
                        final_output = await orchestrator.get_final_output(run_id)
                        if final_output:
                            student_results = final_output.get("student_results", [])
                            logger.info(f"从 orchestrator 获取到 {len(student_results)} 个学生结果")
                    except Exception as e:
                        logger.debug(f"获取最终输出失败: {e}")

                if not student_results:
                    grading_results = final_state.get("grading_results") or []
                    if not grading_results:
                        try:
                            final_output = await orchestrator.get_final_output(run_id)
                            if final_output:
                                grading_results = final_output.get("grading_results") or []
                        except Exception as e:
                            logger.debug(f"鑾峰彇 grading_results 澶辫触: {e}")
                    if grading_results:
                        student_results = _build_student_results_from_grading_results(grading_results)
                        logger.info(
                            f"浠?grading_results 鎭㈠ {len(student_results)} 涓鐢熺粨鏋?"
                        )

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
                        s.get("score")
                        for s in formatted_results
                        if isinstance(s.get("score"), (int, float))
                    ]
                    average_score = None
                    if isinstance(class_report, dict):
                        average_score = class_report.get("average_score")
                    if average_score is None and scores:
                        average_score = round(sum(scores) / len(scores), 2)

                    # 先检查是否已经存在批改历史记录
                    existing_history = await get_grading_history(batch_id)
                    if existing_history:
                        history_id = existing_history.id
                        logger.info(f"使用已存在的批改历史: history_id={history_id}")
                    else:
                        history_id = str(uuid.uuid4())
                        history = GradingHistory(
                            id=history_id,
                            batch_id=batch_id,
                            teacher_id=teacher_key,
                            status="completed",
                            class_ids=[class_id] if class_id else None,
                            created_at=now,
                            completed_at=now,
                            total_students=len(formatted_results),
                            average_score=average_score,
                            result_data=(
                                {
                                    "summary": class_report,
                                    "class_id": class_id,
                                    "homework_id": homework_id,
                                }
                                if class_report or class_id or homework_id
                                else None
                            ),
                        )
                        await _maybe_await(save_grading_history(history))
                        logger.info(f"创建新的批改历史: history_id={history_id}")

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
                                student_name = (
                                    roster_hit.name or roster_hit.username or student_name
                                )
                        if not student_id and class_id and idx < len(roster):
                            roster_hit = roster[idx]
                            student_id = roster_hit.id
                            student_name = roster_hit.name or roster_hit.username or student_name
                        if not student_id and class_id:
                            student_id = f"auto-{idx + 1}"

                        student_summary = (
                            result.get("studentSummary") or result.get("student_summary") or {}
                        )
                        confession_payload = result.get("confession")
                        # Keep student_id whenever available so student-side pages can match records
                        student_id_value = student_id or None
                        student_result = StudentGradingResult(
                            id=_make_student_result_id(history_id, student_name, student_id_value),
                            grading_history_id=history_id,
                            student_key=student_name,
                            score=result.get("score"),
                            max_score=result.get("maxScore") or result.get("max_score"),
                            class_id=class_id,
                            student_id=student_id_value,
                            summary=(
                                student_summary.get("overall")
                                if isinstance(student_summary, dict)
                                else None
                            ),
                            confession=confession_payload,
                            result_data=result,
                        )
                        await _maybe_await(save_student_result(student_result))

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

                await broadcast_progress(
                    batch_id,
                    {
                        "type": "workflow_completed",
                        "message": f"Grading completed, processed {len(formatted_results)} students",
                        "results": formatted_results,
                        "classReport": class_report,
                    },
                )

        logger.info(f"LangGraph 进度流式传输完成: batch_id={batch_id}")

    except Exception as e:
        logger.error(f"流式传输失败: batch_id={batch_id}, error={str(e)}", exc_info=True)
        await broadcast_progress(
            batch_id, {"type": "workflow_error", "message": f"流式传输失败: {str(e)}"}
        )

    finally:
        run_controller = await get_run_controller()
        if run_controller and teacher_key:
            try:
                run_info = await orchestrator.get_status(run_id)
                status_value = (
                    run_info.status.value
                    if hasattr(run_info.status, "value")
                    else str(run_info.status)
                )
                if status_value in ("completed", "failed", "cancelled"):
                    await run_controller.update_run(
                        batch_id,
                        {
                            "status": "completed" if status_value == "completed" else "failed",
                            "completed_at": datetime.now().isoformat(),
                            "updated_at": datetime.now().isoformat(),
                        },
                    )
                    await run_controller.release_slot(teacher_key, batch_id)
            except Exception:
                await run_controller.release_slot(teacher_key, batch_id)
        current_task = asyncio.current_task()
        if current_task and _active_stream_tasks.get(batch_id) is current_task:
            _active_stream_tasks.pop(batch_id, None)


async def _ensure_stream_task(
    *,
    batch_id: str,
    run_id: str,
    orchestrator: Orchestrator,
    class_id: Optional[str] = None,
    homework_id: Optional[str] = None,
    student_mapping: Optional[List[dict]] = None,
    teacher_key: Optional[str] = None,
) -> None:
    existing = _active_stream_tasks.get(batch_id)
    if existing and not existing.done():
        return
    stream_task = asyncio.create_task(
        stream_langgraph_progress(
            batch_id=batch_id,
            run_id=run_id,
            orchestrator=orchestrator,
            class_id=class_id,
            homework_id=homework_id,
            student_mapping=student_mapping,
            teacher_key=teacher_key,
        )
    )
    _active_stream_tasks[batch_id] = stream_task


async def resume_orphaned_streams(orchestrator: Optional[Orchestrator]) -> None:
    if not orchestrator:
        return
    try:
        running_runs = await orchestrator.list_runs(
            graph_name="batch_grading", status=RunStatus.RUNNING, limit=50
        )
        pending_runs = await orchestrator.list_runs(
            graph_name="batch_grading", status=RunStatus.PENDING, limit=50
        )
    except Exception as exc:
        logger.debug("Failed to list runs for stream recovery: %s", exc)
        return

    run_controller = await get_run_controller()
    for run_info in [*running_runs, *pending_runs]:
        run_id = run_info.run_id
        if not run_id.startswith("batch_grading_"):
            continue
        batch_id = run_id.replace("batch_grading_", "", 1)
        teacher_key = None
        class_id = None
        homework_id = None
        if run_controller:
            snapshot = await run_controller.get_run(batch_id)
            if snapshot:
                teacher_key = snapshot.teacher_id
                class_id = snapshot.class_id
                homework_id = snapshot.homework_id
        await _ensure_stream_task(
            batch_id=batch_id,
            run_id=run_id,
            orchestrator=orchestrator,
            class_id=class_id,
            homework_id=homework_id,
            student_mapping=None,
            teacher_key=teacher_key,
        )


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
        "batch_notify": "export",
    }
    if node_name in mapping:
        return mapping[node_name]
    if ":" in node_name:
        base = node_name.split(":", 1)[0]
        if base in mapping:
            return mapping[base]
    if "." in node_name:
        base = node_name.split(".", 1)[0]
        if base in mapping:
            return mapping[base]
    return node_name


def _get_node_display_name(node_name: str) -> str:
    """获取节点的显示名称（中文）"""
    display_names = {
        "intake": "Ingest",
        "preprocess": "Preprocess",
        "index": "Index",
        "rubric_parse": "Rubric Parse",
        "rubric_self_review": "Auto Review",
        "rubric_review": "Rubric Review",
        "grading_fanout": "Batch Fanout",
        "grade_batch": "Batch Grading",
        "cross_page_merge": "Cross-Page Merge",
        "logic_review": "Logic Review",
        "index_merge": "Index Merge",
        "segment": "Index Merge",
        "review": "Final Review",
        "export": "Export",
    }
    if node_name in display_names:
        return display_names[node_name]
    if ":" in node_name:
        base = node_name.split(":", 1)[0]
        if base in display_names:
            return display_names[base]
    if "." in node_name:
        base = node_name.split(".", 1)[0]
        if base in display_names:
            return display_names[base]
    return node_name


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _make_student_result_id(
    grading_history_id: str,
    student_key: Optional[str],
    student_id: Optional[str] = None,
) -> str:
    seed = student_id or student_key or "unknown"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{grading_history_id}:{seed}"))


def _resolve_page_indices(question: Dict[str, Any], fallback_page_index: Optional[int] = None) -> List[int]:
    pages = question.get("page_indices") or question.get("pageIndices")
    if not pages:
        page_index = question.get("page_index")
        if page_index is None:
            page_index = question.get("pageIndex")
        if page_index is None:
            page_index = fallback_page_index
        if page_index is not None:
            pages = [page_index]
    if isinstance(pages, (list, tuple)):
        return [int(p) for p in pages if isinstance(p, (int, float, str)) and str(p).strip() != ""]
    if pages is None:
        return []
    try:
        return [int(pages)]
    except (TypeError, ValueError):
        return []


def _resolve_question_max_score(
    question: Dict[str, Any], scoring_results: List[Dict[str, Any]]
) -> float:
    max_score = _safe_float(
        question.get("max_score")
        or question.get("maxScore")
        or question.get("max_points")
        or question.get("maxPoints"),
        default=0.0,
    )
    if max_score > 0:
        return max_score
    total_points = 0.0
    for item in scoring_results or []:
        max_points = item.get("max_points") or item.get("maxPoints")
        if max_points is None:
            scoring_point = item.get("scoring_point") or item.get("scoringPoint") or {}
            max_points = scoring_point.get("score") or scoring_point.get("points")
        total_points += _safe_float(max_points, default=0.0)
    return total_points


def _resolve_question_confidence(
    question: Dict[str, Any],
    scoring_results: List[Dict[str, Any]],
    *,
    score: float,
    max_score: float,
) -> float:
    raw_confidence = question.get("confidence")
    if raw_confidence is None:
        raw_confidence = question.get("confidence_score")
        if raw_confidence is None:
            raw_confidence = question.get("confidenceScore")
    confidence = _safe_float(raw_confidence, default=0.0)
    has_signal = bool(
        scoring_results
        or question.get("student_answer")
        or question.get("studentAnswer")
        or question.get("feedback")
    )
    if confidence <= 0 and has_signal:
        if max_score > 0:
            confidence = max(0.1, min(1.0, score / max_score))
        elif scoring_results:
            total_points = 0.0
            awarded_points = 0.0
            for item in scoring_results:
                max_points = item.get("max_points") or item.get("maxPoints")
                if max_points is None:
                    scoring_point = item.get("scoring_point") or item.get("scoringPoint") or {}
                    max_points = scoring_point.get("score")
                total_points += _safe_float(max_points, default=0.0)
                awarded_points += _safe_float(item.get("awarded") or item.get("score"), default=0.0)
            if total_points > 0:
                confidence = max(0.1, min(1.0, awarded_points / total_points))
    if confidence <= 0 and has_signal:
        confidence = 0.6 if score > 0 else 0.35
    return max(0.0, min(1.0, confidence))


def _derive_confession_overall_status(confession: Dict[str, Any]) -> str:
    """Derive ok/caution/needs_review for ConfessionReport v1 (frontend convenience)."""
    try:
        items = confession.get("items") or []
        if not isinstance(items, list):
            items = []
        error_count = sum(
            1 for i in items if isinstance(i, dict) and str(i.get("severity", "")).lower() == "error"
        )
        warning_count = sum(
            1
            for i in items
            if isinstance(i, dict) and str(i.get("severity", "")).lower() == "warning"
        )
        risk = confession.get("risk_score")
        if risk is None:
            risk = confession.get("riskScore")
        risk_v = _safe_float(risk, default=0.0)
        if error_count > 0 or risk_v >= 0.6:
            return "needs_review"
        if warning_count >= 3 or risk_v >= 0.3:
            return "caution"
        return "ok"
    except Exception:
        return "caution"


def _build_student_results_from_grading_results(
    grading_results: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not grading_results:
        return []
    try:
        from src.graphs.batch_grading import _build_student_results_from_page_results

        return _build_student_results_from_page_results(grading_results)
    except Exception as exc:
        logger.debug(f"Failed to rebuild student_results from grading_results: {exc}")
        return []


def _merge_question_results(existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    merged = existing.copy()
    merged["score"] = max(_safe_float(existing.get("score", 0)), _safe_float(incoming.get("score", 0)))
    merged["maxScore"] = max(
        _safe_float(existing.get("maxScore", 0)),
        _safe_float(incoming.get("maxScore", 0)),
    )
    if not merged.get("feedback") and incoming.get("feedback"):
        merged["feedback"] = incoming.get("feedback")
    if not merged.get("studentAnswer") and incoming.get("studentAnswer"):
        merged["studentAnswer"] = incoming.get("studentAnswer")
    merged_conf = _safe_float(existing.get("confidence", 0))
    incoming_conf = _safe_float(incoming.get("confidence", 0))
    merged["confidence"] = max(merged_conf, incoming_conf)
    pages = set(existing.get("page_indices") or existing.get("pageIndices") or [])
    pages.update(incoming.get("page_indices") or incoming.get("pageIndices") or [])
    if pages:
        merged["page_indices"] = sorted(pages)
        merged["pageIndices"] = sorted(pages)
    if not merged.get("scoring_point_results") and incoming.get("scoring_point_results"):
        merged["scoring_point_results"] = incoming.get("scoring_point_results")
    if not merged.get("steps") and incoming.get("steps"):
        merged["steps"] = incoming.get("steps")
    return merged


def _dedupe_formatted_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for result in results:
        student_id = result.get("studentId") or result.get("student_id")
        student_name = result.get("studentName") or result.get("student_name") or ""
        student_key = result.get("studentKey") or result.get("student_key")
        start_page = result.get("startPage")
        end_page = result.get("endPage")
        key: Optional[str] = None
        if student_id:
            key = f"id:{student_id}"
        elif student_name and (start_page is not None or end_page is not None):
            key = f"name:{student_name}:{start_page}-{end_page}"
        elif student_name:
            key = f"name:{student_name}"
        elif student_key:
            key = f"key:{student_key}"
        if not key:
            key = str(len(grouped))
        entry = grouped.get(key)
        if not entry:
            grouped[key] = result
            continue

        merged = entry.copy()
        merged_questions: Dict[str, Dict[str, Any]] = {}
        for q in entry.get("questionResults", []) or []:
            qid = str(q.get("questionId") or q.get("question_id") or "")
            if not qid:
                qid = f"idx:{len(merged_questions)}"
            merged_questions[qid] = q
        for q in result.get("questionResults", []) or []:
            qid = str(q.get("questionId") or q.get("question_id") or "")
            if not qid:
                qid = f"idx:{len(merged_questions)}"
            if qid in merged_questions:
                merged_questions[qid] = _merge_question_results(merged_questions[qid], q)
            else:
                merged_questions[qid] = q
        merged["questionResults"] = list(merged_questions.values())

        # Prefer newer post-processing fields when the current entry is missing them.
        for field in (
            "confession",
            "logicReview",
            "logicReviewedAt",
            "draftQuestionDetails",
            "draftTotalScore",
            "draftMaxScore",
        ):
            if not merged.get(field) and result.get(field):
                merged[field] = result.get(field)

        merged_start = merged.get("startPage")
        merged_end = merged.get("endPage")
        candidate_start = result.get("startPage")
        candidate_end = result.get("endPage")
        if merged_start is not None and candidate_start is not None:
            merged["startPage"] = min(merged_start, candidate_start)
        elif merged_start is None and candidate_start is not None:
            merged["startPage"] = candidate_start
        if merged_end is not None and candidate_end is not None:
            merged["endPage"] = max(merged_end, candidate_end)
        elif merged_end is None and candidate_end is not None:
            merged["endPage"] = candidate_end

        if merged.get("startPage") is not None:
            if merged.get("endPage") is not None and merged["endPage"] != merged["startPage"]:
                merged["pageRange"] = f"{merged['startPage'] + 1}-{merged['endPage'] + 1}"
            else:
                merged["pageRange"] = str(merged["startPage"] + 1)

        question_scores = [
            _safe_float(q.get("score", 0)) for q in merged.get("questionResults", []) or []
        ]
        question_max = [
            _safe_float(q.get("maxScore", 0)) for q in merged.get("questionResults", []) or []
        ]
        if question_scores:
            merged["score"] = sum(question_scores)
        if question_max:
            merged["maxScore"] = sum(question_max)

        grouped[key] = merged
    return list(grouped.values())


def _format_results_for_frontend(results: List[Dict]) -> List[Dict]:
    """格式化批改结果为前端格式"""
    formatted = []
    for r in results:
        # 处理 question_details 格式
        question_results = []

        # 优先使用 question_details
        if r.get("question_details"):
            for q in r.get("question_details", []):
                scoring_results = q.get("scoring_point_results") or q.get("scoring_results") or []
                score_value = _safe_float(q.get("score", 0))
                max_score_value = _resolve_question_max_score(q, scoring_results)
                page_indices = _resolve_page_indices(q)
                confidence = _resolve_question_confidence(
                    q,
                    scoring_results,
                    score=score_value,
                    max_score=max_score_value,
                )
                question_results.append(
                    {
                        "questionId": str(q.get("question_id", "")),
                        "score": score_value,
                        "maxScore": max_score_value,
                        "feedback": q.get("feedback", ""),
                        "confidence": confidence,
                        "confidence_reason": q.get("confidence_reason")
                        or q.get("confidenceReason"),
                        "rubric_refs": q.get("rubric_refs") or q.get("rubricRefs"),
                        "review_summary": q.get("review_summary") or q.get("reviewSummary"),
                        "review_corrections": q.get("review_corrections")
                        or q.get("reviewCorrections"),
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
                        "confessionItems": q.get("confession_items")
                        or q.get("confessionItems")
                        or [],
                        "typo_notes": q.get("typo_notes") or q.get("typoNotes"),
                        "studentAnswer": q.get("student_answer", ""),
                        "question_type": q.get("question_type") or q.get("questionType"),
                        "isCorrect": q.get("is_correct", False),
                        "scoring_point_results": scoring_results,
                        "page_indices": page_indices,
                        "is_cross_page": q.get("is_cross_page", False),
                        "merge_source": q.get("merge_source"),
                        # 🔥 批注坐标字段（后端不再返回，改为前端渲染/按需生成）
                        "annotations": [],
                        "steps": q.get("steps") or [],
                        "answerRegion": q.get("answer_region") or q.get("answerRegion"),
                    }
                )
        # 兼容旧格式 grading_results
        elif r.get("grading_results"):
            for q in r.get("grading_results", []):
                scoring_results = q.get("scoring_point_results") or q.get("scoring_results") or []
                score_value = _safe_float(q.get("score", 0))
                max_score_value = _resolve_question_max_score(q, scoring_results)
                page_indices = _resolve_page_indices(q)
                confidence = _resolve_question_confidence(
                    q,
                    scoring_results,
                    score=score_value,
                    max_score=max_score_value,
                )
                question_results.append(
                    {
                        "questionId": str(q.get("question_id", "")),
                        "score": score_value,
                        "maxScore": max_score_value,
                        "feedback": q.get("feedback", ""),
                        "confidence": confidence,
                        "confidence_reason": q.get("confidence_reason")
                        or q.get("confidenceReason"),
                        "rubric_refs": q.get("rubric_refs") or q.get("rubricRefs"),
                        "review_summary": q.get("review_summary") or q.get("reviewSummary"),
                        "review_corrections": q.get("review_corrections")
                        or q.get("reviewCorrections"),
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
                        "confessionItems": q.get("confession_items")
                        or q.get("confessionItems")
                        or [],
                        "typo_notes": q.get("typo_notes") or q.get("typoNotes"),
                        "studentAnswer": q.get("student_answer", ""),
                        "question_type": q.get("question_type") or q.get("questionType"),
                        "scoring_point_results": scoring_results,
                        "page_indices": page_indices,
                        "is_cross_page": q.get("is_cross_page", False),
                        "merge_source": q.get("merge_source"),
                        # 🔥 批注坐标字段（后端不再返回，改为前端渲染/按需生成）
                        "annotations": [],
                        "steps": q.get("steps") or [],
                        "answerRegion": q.get("answer_region") or q.get("answerRegion"),
                    }
                )
        # å…¼å®¹ export_data çš„ question_results
        elif r.get("question_results") or r.get("questionResults"):
            raw_question_results = r.get("question_results") or r.get("questionResults") or []
            for q in raw_question_results:
                scoring_results = (
                    q.get("scoring_point_results")
                    or q.get("scoring_results")
                    or q.get("scoringPointResults")
                    or []
                )
                score_value = _safe_float(q.get("score", 0))
                max_score_value = _resolve_question_max_score(q, scoring_results)
                page_indices = _resolve_page_indices(q)
                confidence = _resolve_question_confidence(
                    q,
                    scoring_results,
                    score=score_value,
                    max_score=max_score_value,
                )
                question_results.append(
                    {
                        "questionId": str(q.get("question_id") or q.get("questionId") or ""),
                        "score": score_value,
                        "maxScore": max_score_value,
                        "feedback": q.get("feedback", ""),
                        "confidence": confidence,
                        "confidence_reason": q.get("confidence_reason")
                        or q.get("confidenceReason"),
                        "rubric_refs": q.get("rubric_refs") or q.get("rubricRefs"),
                        "review_summary": q.get("review_summary") or q.get("reviewSummary"),
                        "review_corrections": q.get("review_corrections")
                        or q.get("reviewCorrections"),
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
                        "confessionItems": q.get("confession_items")
                        or q.get("confessionItems")
                        or [],
                        "typo_notes": q.get("typo_notes") or q.get("typoNotes"),
                        "studentAnswer": q.get("student_answer") or q.get("studentAnswer") or "",
                        "question_type": q.get("question_type") or q.get("questionType"),
                        "isCorrect": q.get("is_correct", False),
                        "scoring_point_results": scoring_results,
                        "page_indices": page_indices,
                        "is_cross_page": q.get("is_cross_page", False),
                        "merge_source": q.get("merge_source"),
                        # 🔥 批注坐标字段（后端不再返回，改为前端渲染/按需生成）
                        "annotations": [],
                        "steps": q.get("steps") or [],
                        "answerRegion": q.get("answer_region") or q.get("answerRegion"),
                    }
                )
        # 从 page_results 提取
        elif r.get("page_results"):
            for page in r.get("page_results", []):
                if page.get("status") == "completed":
                    # 从页面结果中提取题目详情
                    for q in page.get("question_details", []):
                        scoring_results = (
                            q.get("scoring_point_results") or q.get("scoring_results") or []
                        )
                        score_value = _safe_float(q.get("score", 0))
                        max_score_value = _resolve_question_max_score(q, scoring_results)
                        page_indices = _resolve_page_indices(q, page.get("page_index"))
                        confidence = _resolve_question_confidence(
                            q,
                            scoring_results,
                            score=score_value,
                            max_score=max_score_value,
                        )
                        question_results.append(
                            {
                                "questionId": str(q.get("question_id", "")),
                                "score": score_value,
                                "maxScore": max_score_value,
                                "feedback": q.get("feedback", ""),
                                "confidence": confidence,
                                "confidence_reason": q.get("confidence_reason")
                                or q.get("confidenceReason"),
                                "rubric_refs": q.get("rubric_refs") or q.get("rubricRefs"),
                                "review_summary": q.get("review_summary") or q.get("reviewSummary"),
                                "review_corrections": q.get("review_corrections")
                                or q.get("reviewCorrections"),
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
                                "confessionItems": q.get("confession_items")
                                or q.get("confessionItems")
                                or [],
                                "typo_notes": q.get("typo_notes") or q.get("typoNotes"),
                                "studentAnswer": q.get("student_answer", ""),
                                "question_type": q.get("question_type") or q.get("questionType"),
                                "isCorrect": q.get("is_correct", False),
                                "scoring_point_results": scoring_results,
                                "page_indices": page_indices or [],
                                "is_cross_page": q.get("is_cross_page", False),
                                "merge_source": q.get("merge_source"),
                                # 🔥 批注坐标字段（后端不再返回，改为前端渲染/按需生成）
                                "annotations": [],
                                "steps": q.get("steps") or [],
                                "answerRegion": q.get("answer_region") or q.get("answerRegion"),
                            }
                        )

        computed_score = sum(_safe_float(q.get("score", 0)) for q in question_results)
        computed_max = sum(_safe_float(q.get("maxScore", 0)) for q in question_results)
        raw_score = _safe_float(r.get("total_score", r.get("score", 0)))
        raw_max = _safe_float(r.get("max_total_score", r.get("max_score", 0)))
        final_score = raw_score if raw_score > 0 or computed_score <= 0 else computed_score
        final_max = raw_max if raw_max > 0 or computed_max <= 0 else computed_max

        student_summary = r.get("student_summary") or r.get("studentSummary")
        confession_raw = r.get("confession")
        if isinstance(confession_raw, str):
            try:
                confession_raw = json.loads(confession_raw)
            except Exception:
                confession_raw = None

        logic_review_raw = r.get("logic_review") or r.get("logicReview")
        if isinstance(logic_review_raw, str):
            try:
                logic_review_raw = json.loads(logic_review_raw)
            except Exception:
                logic_review_raw = None

        # 标准化 confession 格式，确保前端能正确显示
        confession = None
        if confession_raw and isinstance(confession_raw, dict):
            confession = {}
            # 复制所有原始字段
            confession.update(confession_raw)
            # ConfessionReport v1: add frontend convenience fields.
            if confession_raw.get("version") == "confession_report_v1":
                if "overallStatus" not in confession:
                    confession["overallStatus"] = _derive_confession_overall_status(confession_raw)
                if "overallConfidence" not in confession and "overall_confidence" in confession_raw:
                    confession["overallConfidence"] = confession_raw.get("overall_confidence")
                if "riskScore" not in confession and "risk_score" in confession_raw:
                    confession["riskScore"] = confession_raw.get("risk_score")

        # 🔥 第一次批改记录（逻辑复核前的原始结果）
        draft_question_details = r.get("draft_question_details") or r.get("draftQuestionDetails")
        draft_question_results = []
        if draft_question_details:
            for dq in draft_question_details:
                draft_scoring_results = (
                    dq.get("scoring_point_results") or dq.get("scoring_results") or []
                )
                draft_score_value = _safe_float(dq.get("score", 0))
                draft_max_score_value = _resolve_question_max_score(
                    dq, draft_scoring_results
                )
                draft_page_indices = _resolve_page_indices(dq)
                draft_confidence = _resolve_question_confidence(
                    dq,
                    draft_scoring_results,
                    score=draft_score_value,
                    max_score=draft_max_score_value,
                )
                draft_question_results.append(
                    {
                        "questionId": str(dq.get("question_id", "")),
                        "score": draft_score_value,
                        "maxScore": draft_max_score_value,
                        "feedback": dq.get("feedback", ""),
                        "confidence": draft_confidence,
                        "studentAnswer": dq.get("student_answer", ""),
                        "question_type": dq.get("question_type") or dq.get("questionType"),
                        "scoring_point_results": draft_scoring_results,
                        "page_indices": draft_page_indices,
                    }
                )

        # 计算页面范围显示字符串
        start_page = r.get("start_page") if r.get("start_page") is not None else r.get("startPage")
        end_page = r.get("end_page") if r.get("end_page") is not None else r.get("endPage")
        page_range = ""
        if start_page is not None:
            if end_page is not None and end_page != start_page:
                page_range = f"{start_page + 1}-{end_page + 1}"
            else:
                page_range = str(start_page + 1)

        student_id = r.get("student_id") or r.get("studentId")
        student_key = r.get("student_key") or r.get("studentKey")
        formatted.append(
            {
                "studentName": r.get("student_name")
                or r.get("studentName")
                or student_key
                or student_id
                or "Unknown",
                "studentId": student_id,
                "studentKey": student_key,
                "score": final_score,
                "maxScore": final_max if final_max > 0 else 0,
                "startPage": start_page,
                "endPage": end_page,
                "pageRange": page_range,
                "questionResults": question_results,
                "confidence": r.get("confidence", 0),
                "needsConfirmation": r.get("needs_confirmation", False),
                "gradingMode": r.get("grading_mode") or r.get("gradingMode"),
                "studentSummary": student_summary,
                # 🔥 新增：批改透明度字段
                "confession": confession,
                "logicReview": logic_review_raw,
                "draftQuestionDetails": draft_question_results if draft_question_results else None,
                "draftTotalScore": r.get("draft_total_score") or r.get("draftTotalScore"),
                "draftMaxScore": r.get("draft_max_score") or r.get("draftMaxScore"),
                "logicReviewedAt": r.get("logic_reviewed_at") or r.get("logicReviewedAt"),
                
            }
        )
    formatted = _dedupe_formatted_results(formatted)
    return formatted


@router.websocket("/ws/{batch_id}")
async def websocket_endpoint(websocket: WebSocket, batch_id: str):
    """
    WebSocket 端点，用于实时推送批改进度

    前端通过此端点接收 LangGraph 的实时执行进度
    """
    await websocket.accept()
    
    # 为新连接创建锁
    ws_id = id(websocket)
    if ws_id not in ws_locks:
        ws_locks[ws_id] = asyncio.Lock()

    redis_client = await _get_redis_client()
    use_redis_cache = redis_client is not None

    cached_images = batch_image_cache.get(batch_id, {})
    if cached_images:
        try:
            for key, message in cached_images.items():
                if key == "llm_stream_cache":
                    continue
                if use_redis_cache and key not in ("images_ready", "rubric_images_ready"):
                    continue
                async with ws_locks[ws_id]:
                    await websocket.send_json(message)
        except Exception as e:
            logger.debug(f"发送缓存图片失败: {e}")

    if use_redis_cache:
        try:
            cached_progress = await _load_cached_progress_messages(batch_id)
            for message in cached_progress:
                # 不重放 workflow_completed，避免错误跳转到结果页
                if message.get("type") == "workflow_completed":
                    logger.debug(f"跳过重放 workflow_completed 缓存: batch_id={batch_id}")
                    continue
                async with ws_locks[ws_id]:
                    await websocket.send_json(message)
        except Exception as e:
            logger.debug(f"发送缓存进度失败: {e}")

    if cached_images:
        try:
            stream_cache = cached_images.get("llm_stream_cache")
            if isinstance(stream_cache, dict):
                for stream_message in stream_cache.values():
                    async with ws_locks[ws_id]:
                        await websocket.send_json(
                            {
                                "type": "llm_stream_chunk",
                                **stream_message,
                            }
                        )
        except Exception as e:
            logger.debug(f"发送流式缓存失败: {e}")

    # 注册连接
    if batch_id not in active_connections:
        active_connections[batch_id] = []
    active_connections[batch_id].append(websocket)

    # 检查该批次是否有活跃的 LangGraph 运行
    orchestrator_check = await get_orchestrator()
    run_exists = False
    if orchestrator_check:
        try:
            run_info = await orchestrator_check.get_run_info(f"batch_grading_{batch_id}")
            run_exists = run_info is not None
        except Exception:
            pass
    
    logger.debug(f"WebSocket 连接建立: batch_id={batch_id}, run_exists={run_exists}")
    
    # 如果批次不存在活跃的运行，静默关闭连接
    # 这是正常情况（前端可能连接到已完成的批次），不需要记录错误
    if not run_exists:
        try:
            async with ws_locks[ws_id]:
                await websocket.send_json({
                    "type": "batch_not_found",
                    "message": f"Batch {batch_id} has no active run. It may have completed or does not exist.",
                    "batchId": batch_id,
                })
        except Exception:
            pass  # 静默处理 - 连接可能已关闭，这是预期的
        # 清理连接
        _discard_connection(batch_id, websocket)
        ws_locks.pop(ws_id, None)
        try:
            await websocket.close(code=1000, reason="Batch not found")
        except Exception:
            pass
        return  # 直接返回，不进入 while 循环

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
                    async with ws_locks[ws_id]:
                        await websocket.send_json(
                            {
                                "type": "grading_progress",
                                "percentage": percentage or 0,
                                "currentStage": current_stage,
                            }
                        )
                if state.get("student_boundaries"):
                    boundaries = state.get("student_boundaries", [])
                    async with ws_locks[ws_id]:
                        await websocket.send_json(
                            {
                                "type": "students_identified",
                                "studentCount": len(boundaries),
                                "students": [
                                    {
                                        "studentKey": b.get("student_key", ""),
                                        "startPage": b.get("start_page", 0),
                                        "endPage": b.get("end_page", 0),
                                        "confidence": b.get("confidence", 0),
                                        "needsConfirmation": b.get("needs_confirmation", False),
                                    }
                                    for b in boundaries
                                ],
                            }
                        )
                if state.get("parsed_rubric"):
                    parsed = state.get("parsed_rubric", {})
                    async with ws_locks[ws_id]:
                        await websocket.send_json(
                            {
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
                                                "pointId": sp.get("point_id")
                                                or sp.get("pointId")
                                                or f"{q.get('question_id')}.{idx + 1}",
                                                "description": sp.get("description", ""),
                                                "expectedValue": sp.get("expected_value")
                                                or sp.get("expectedValue", ""),
                                                "keywords": sp.get("keywords") or [],
                                                "score": sp.get("score", 0),
                                                "isRequired": sp.get("is_required", True),
                                            }
                                            for idx, sp in enumerate(q.get("scoring_points", []))
                                        ],
                                        "deductionRules": [
                                            {
                                                "ruleId": dr.get("rule_id")
                                                or dr.get("ruleId")
                                                or f"{q.get('question_id')}.d{idx + 1}",
                                                "description": dr.get("description", ""),
                                                "deduction": dr.get("deduction", dr.get("score", 0)),
                                                "conditions": dr.get("conditions")
                                                or dr.get("when")
                                                or "",
                                            }
                                            for idx, dr in enumerate(
                                                q.get("deduction_rules")
                                                or q.get("deductionRules")
                                                or []
                                            )
                                        ],
                                        "alternativeSolutions": [
                                            {
                                                "description": alt.get("description", ""),
                                                "scoringCriteria": alt.get("scoring_criteria", ""),
                                                "note": alt.get("note", ""),
                                            }
                                            for alt in q.get("alternative_solutions", [])
                                        ],
                                    }
                                    for q in parsed.get("questions", [])
                                ],
                            }
                        )
                if run_info.status and run_info.status.value == "completed":
                    student_results = state.get("student_results", [])
                    formatted_results = _format_results_for_frontend(student_results)
                    # 🔥 FIX: 只有在有实际结果数据时才发送 workflow_completed
                    # 避免在工作流异常完成（如跳过批改）时错误发送完成事件
                    if formatted_results and len(formatted_results) > 0:
                        class_report = state.get("class_report")
                        if not class_report and state.get("export_data"):
                            class_report = state.get("export_data", {}).get("class_report")
                        async with ws_locks[ws_id]:
                            await websocket.send_json(
                                {
                                    "type": "workflow_completed",
                                    "message": f"Grading completed, processed {len(formatted_results)} students",
                                    "results": formatted_results,
                                    "cross_page_questions": state.get("cross_page_questions", []),
                                    "classReport": class_report,
                                }
                            )
                    else:
                        logger.warning(f"跳过发送 workflow_completed: 状态为 completed 但没有结果数据, batch_id={batch_id}")
            if run_info and run_info.status and run_info.status.value in ("running", "pending"):
                run_controller = await get_run_controller()
                teacher_key = None
                class_id = None
                homework_id = None
                if run_controller:
                    snapshot = await run_controller.get_run(batch_id)
                    if snapshot:
                        teacher_key = snapshot.teacher_id
                        class_id = snapshot.class_id
                        homework_id = snapshot.homework_id
                await _ensure_stream_task(
                    batch_id=batch_id,
                    run_id=run_id,
                    orchestrator=orchestrator,
                    class_id=class_id,
                    homework_id=homework_id,
                    student_mapping=None,
                    teacher_key=teacher_key,
                )
    except Exception:
        pass  # 状态快照发送失败是正常情况，静默处理

    try:
        # 保持连接，等待客户端消息或断开
        while True:
            if not _is_ws_connected(websocket):
                break
            data = await websocket.receive_text()
            logger.debug(f"收到 WebSocket 消息: batch_id={batch_id}, data={data}")

    except (WebSocketDisconnect, RuntimeError, AssertionError):
        # WebSocketDisconnect: 正常断开
        # RuntimeError: 连接已关闭时的操作
        # AssertionError: websockets 库内部 keepalive ping 竞态条件
        # 这些都是预期的断开情况，静默处理
        pass
    except Exception:
        # 其他异常也静默处理
        pass
    finally:
        # 🔥 FIX: 无论如何都要清理连接，防止连接泄漏
        _discard_connection(batch_id, websocket)
        ws_locks.pop(ws_id, None)


@router.get("/active", response_model=ActiveRunsResponse)
async def list_active_runs(teacher_id: Optional[str] = None) -> ActiveRunsResponse:
    teacher_key = _normalize_teacher_key(teacher_id)
    run_controller = await get_run_controller()
    if not run_controller:
        return ActiveRunsResponse(teacher_id=teacher_key, runs=[])
    snapshots = await run_controller.list_runs(teacher_key)
    runs = [
        ActiveRunItem(
            batch_id=item.batch_id,
            status=item.status,
            class_id=item.class_id,
            homework_id=item.homework_id,
            created_at=item.created_at,
            updated_at=item.updated_at,
            started_at=item.started_at,
            completed_at=item.completed_at,
            total_pages=item.total_pages,
            progress=item.progress,
            current_stage=item.current_stage,
        )
        for item in snapshots
    ]
    return ActiveRunsResponse(teacher_id=teacher_key, runs=runs)


@router.get("/status/{batch_id}", response_model=BatchStatusResponse)
async def get_batch_status(batch_id: str, orchestrator: Orchestrator = Depends(get_orchestrator)):
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
            current_stage=state.get("current_stage"),
            error=run_info.error,
            total_students=len(state.get("student_boundaries", [])),
            completed_students=len(state.get("student_results", [])),
            unidentified_pages=0,
            results=state.get("student_results"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询批次状态失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/rubric/{batch_id}", response_model=RubricReviewContextResponse)
async def get_rubric_review_context(
    batch_id: str, orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """获取 rubric review 页面上下文（支持从文件存储和数据库读取）"""
    
    async def _load_rubric_images_from_pg() -> List[str]:
        """从 PostgreSQL batch_images 表加载 rubric 图片（优先）"""
        try:
            images_bytes = await get_batch_images_as_bytes_list(batch_id, "rubric")
            if not images_bytes:
                return []
            images = [base64.b64encode(img).decode("utf-8") for img in images_bytes]
            logger.info(f"[PG-Storage] 从 PostgreSQL 加载了 {len(images)} 张 rubric 图片")
            return images
        except Exception as exc:
            logger.debug(f"从 PostgreSQL 加载 rubric 图片失败: {exc}")
            return []
    
    async def _load_rubric_images_from_storage() -> List[str]:
        """从文件存储加载 rubric 图片（备用）"""
        try:
            file_storage = get_file_storage_service()
            stored_files = await file_storage.list_batch_files(batch_id)
            if not stored_files:
                return []
            
            rubric_files = [
                item for item in stored_files
                if item.metadata.get("type") == "rubric" or item.filename.startswith("rubric_page")
            ]
            if not rubric_files:
                return []
            
            rubric_files.sort(key=lambda f: f.filename)
            images: List[str] = []
            for item in rubric_files:
                data = await file_storage.get_file(item.file_id)
                if not data:
                    continue
                images.append(base64.b64encode(data).decode("utf-8"))
            
            logger.info(f"从文件存储加载了 {len(images)} 张 rubric 图片")
            return images
        except Exception as exc:
            logger.debug(f"从文件存储加载 rubric 图片失败: {exc}")
            return []
    
    async def _load_from_db() -> RubricReviewContextResponse:
        """从数据库加载 rubric 数据"""
        history = await _maybe_await(get_grading_history(batch_id))
        if not history:
            raise HTTPException(status_code=404, detail="批次不存在")
        
        parsed_rubric = None
        if history.rubric_data:
            try:
                if isinstance(history.rubric_data, str):
                    parsed_rubric = json.loads(history.rubric_data)
                elif isinstance(history.rubric_data, dict):
                    parsed_rubric = history.rubric_data
            except Exception as exc:
                logger.debug(f"解析数据库中的 rubric_data 失败: {exc}")
        
        # 优先从 PostgreSQL 加载图片
        rubric_images = await _load_rubric_images_from_pg()
        if not rubric_images:
            rubric_images = await _load_rubric_images_from_storage()
        
        logger.info(f"从数据库加载 rubric 上下文: parsed_rubric={'有' if parsed_rubric else '无'}, images={len(rubric_images)}")
        
        return RubricReviewContextResponse(
            batch_id=batch_id,
            status=history.status,
            current_stage=history.current_stage,
            parsed_rubric=parsed_rubric,
            rubric_images=rubric_images,
        )
    
    try:
        # 1. 优先从 LangGraph state 读取（实时数据）
        if orchestrator:
            run_id = f"batch_grading_{batch_id}"
            run_info = await orchestrator.get_run_info(run_id)
            
            if run_info:
                state = run_info.state or {}
                parsed_rubric = state.get("parsed_rubric")
                
                # 尝试从缓存读取图片
                cached = batch_image_cache.get(batch_id, {})
                cached_images = cached.get("rubric_images_ready", {}).get("images") if cached else None
                rubric_images: List[str] = cached_images or []
                
                # 从 state 读取图片
                if not rubric_images and state.get("rubric_images"):
                    try:
                        rubric_images = []
                        for img in state.get("rubric_images", []):
                            if isinstance(img, (bytes, bytearray)):
                                rubric_images.append(base64.b64encode(img).decode("utf-8"))
                            elif isinstance(img, str) and img:
                                rubric_images.append(img)
                    except Exception as exc:
                        logger.debug(f"从 state 转换 rubric 图片失败: {exc}")
                
                # 如果从 state 获取到了数据，直接返回
                if parsed_rubric or rubric_images:
                    logger.info(f"从 LangGraph state 加载 rubric: parsed_rubric={'有' if parsed_rubric else '无'}, images={len(rubric_images)}")
                    return RubricReviewContextResponse(
                        batch_id=batch_id,
                        status=run_info.status.value if run_info.status else None,
                        current_stage=state.get("current_stage"),
                        parsed_rubric=parsed_rubric,
                        rubric_images=rubric_images,
                    )
        
        # 2. Fallback: 从数据库和文件存储读取
        logger.info(f"LangGraph state 无数据，尝试从数据库加载 rubric: batch_id={batch_id}")
        return await _load_from_db()
        
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"获取 rubric 上下文失败: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取失败: {str(exc)}")


@router.get("/results-review/{batch_id}", response_model=ResultsReviewContextResponse)
async def get_results_review_context(
    batch_id: str, orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """获取 results review 页面上下文"""

    async def _load_answer_images_from_pg() -> List[str]:
        """从 PostgreSQL batch_images 表加载答题图片（优先）"""
        try:
            images_bytes = await get_batch_images_as_bytes_list(batch_id, "answer")
            if not images_bytes:
                return []
            # 转换为 base64 字符串
            images = [base64.b64encode(img).decode("utf-8") for img in images_bytes]
            logger.info(f"[PG-Storage] 从 PostgreSQL 加载了 {len(images)} 张答题图片")
            return images
        except Exception as exc:
            logger.debug(f"Failed to load answer images from PostgreSQL: {exc}")
            return []

    async def _load_answer_images_from_storage() -> List[str]:
        """从本地文件存储加载答题图片（备用）"""
        try:
            file_storage = get_file_storage_service()
            stored_files = await file_storage.list_batch_files(batch_id)
            if not stored_files:
                return []
            answer_files = [
                item
                for item in stored_files
                if item.metadata.get("type") == "answer"
                or item.filename.startswith("answer_page")
            ]
            if not answer_files:
                return []
            answer_files.sort(key=lambda f: f.filename)
            images: List[str] = []
            for item in answer_files:
                data = await file_storage.get_file(item.file_id)
                if not data:
                    continue
                images.append(base64.b64encode(data).decode("utf-8"))
            return images
        except Exception as exc:
            logger.debug(f"Failed to load answer images from storage: {exc}")
            return []

    async def _load_answer_images_from_db(history_id: str) -> List[str]:
        try:
            images = await _maybe_await(get_page_images(history_id))
            if not images:
                return []
            return [img.file_url for img in images if img.file_url]
        except Exception as exc:
            logger.debug(f"Failed to load answer images from DB: {exc}")
            return []

    def _has_post_confession_fields(results: List[Dict[str, Any]]) -> bool:
        for item in results:
            if not isinstance(item, dict):
                continue
            if item.get("confession") or item.get("logic_review") or item.get("logicReview"):
                return True
        return False

    async def _load_from_db() -> ResultsReviewContextResponse:
        """从数据库加载批改结果"""
        history = await _maybe_await(get_grading_history(batch_id))
        if not history:
            raise HTTPException(status_code=404, detail="批次不存在")

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
            confession_value = row.confession
            if confession_value and not data.get("confession"):
                if isinstance(confession_value, str):
                    try:
                        confession_value = json.loads(confession_value)
                    except Exception:
                        confession_value = None
                if confession_value:
                    data["confession"] = confession_value
            raw_results.append(data)

        # 从 history.result_data 中获取 parsed_rubric
        parsed_rubric = None
        if history.result_data and isinstance(history.result_data, dict):
            parsed_rubric = history.result_data.get("parsed_rubric")

        answer_images = await _load_answer_images_from_db(history.id)
        if not answer_images:
            answer_images = await _load_answer_images_from_storage()
        return ResultsReviewContextResponse(
            batch_id=batch_id,
            status=history.status,
            current_stage=None,
            student_results=_format_results_for_frontend(raw_results),
            answer_images=answer_images,
            parsed_rubric=parsed_rubric,
        )

    try:
        if not orchestrator:
            return await _load_from_db()

        run_id = f"batch_grading_{batch_id}"
        run_info = await orchestrator.get_run_info(run_id)
        if not run_info:
            return await _load_from_db()

        state = run_info.state or {}
        student_results = (
            state.get("reviewed_results")
            or state.get("confessed_results")
            or state.get("student_results", [])
        )
        if not student_results:
            try:
                final_output = await orchestrator.get_final_output(run_id)
                if final_output:
                    student_results = final_output.get("student_results", [])
            except Exception as exc:
                logger.debug(f"获取最终输出失败: {exc}")

        if not student_results:
            export_students = (state.get("export_data") or {}).get("students", [])
            if export_students:
                student_results = export_students
            else:
                grading_results = state.get("grading_results") or []
                if not grading_results:
                    try:
                        final_output = await orchestrator.get_final_output(run_id)
                        if final_output:
                            grading_results = final_output.get("grading_results") or []
                    except Exception as exc:
                        logger.debug(f"Failed to load grading_results from orchestrator: {exc}")
                if grading_results:
                    student_results = _build_student_results_from_grading_results(grading_results)
                if not student_results:
                    try:
                        return await _load_from_db()
                    except HTTPException:
                        student_results = []

        # Attach logic review payloads from state when missing on student_results.
        logic_review_by_student: Dict[str, Any] = {}
        for item in state.get("logic_review_results") or []:
            if not isinstance(item, dict):
                continue
            key = item.get("student_key") or item.get("studentKey")
            if key:
                logic_review_by_student[key] = item
        if logic_review_by_student:
            for student in student_results:
                if not isinstance(student, dict):
                    continue
                if student.get("logic_review") or student.get("logicReview"):
                    continue
                key = (
                    student.get("student_key")
                    or student.get("studentKey")
                    or student.get("student_name")
                    or student.get("studentName")
                )
                payload = logic_review_by_student.get(key)
                if payload:
                    student["logic_review"] = payload
                    student["logicReview"] = payload
                    if not student.get("logic_reviewed_at") and payload.get("reviewed_at"):
                        student["logic_reviewed_at"] = payload.get("reviewed_at")

        # If the run completed but confession/logic_review is missing, prefer DB results.
        if (
            student_results
            and run_info.status
            and run_info.status.value == "completed"
            and not _has_post_confession_fields(student_results)
        ):
            try:
                return await _load_from_db()
            except HTTPException:
                pass

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
                logger.debug(f"Failed to convert answer images: {exc}")
        if not answer_images:
            history = await _maybe_await(get_grading_history(batch_id))
            if history:
                answer_images = await _load_answer_images_from_db(history.id)
        else:
            # Prefer DB image URLs over large base64 blobs when available.
            if any(
                isinstance(img, str) and img.startswith("data:")
                for img in answer_images
            ):
                history = await _maybe_await(get_grading_history(batch_id))
                if history:
                    db_images = await _load_answer_images_from_db(history.id)
                    if db_images:
                        answer_images = db_images
        if not answer_images:
            # 优先从 PostgreSQL batch_images 表加载
            answer_images = await _load_answer_images_from_pg()
        if not answer_images:
            # 回退到本地文件存储
            answer_images = await _load_answer_images_from_storage()
        
        # 从 state 中获取 parsed_rubric
        parsed_rubric = state.get("parsed_rubric")
        
        return ResultsReviewContextResponse(
            batch_id=batch_id,
            status=run_info.status.value if run_info.status else None,
            current_stage=state.get("current_stage"),
            student_results=_format_results_for_frontend(student_results),
            answer_images=answer_images,
            parsed_rubric=parsed_rubric,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"获取 results 上下文失败: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取失败: {str(exc)}")


@router.get("/results/{batch_id}")
async def get_batch_results(batch_id: str, orchestrator: Orchestrator = Depends(get_orchestrator)):
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
        # 注意：confessed_results 已移除（批改和审计一体化改造）
        student_results = (
            state.get("reviewed_results")
            or state.get("student_results", [])
        )

        # 如果没有 student_results，尝试从 orchestrator 获取最终输出
        if not student_results:
            try:
                final_output = await orchestrator.get_final_output(run_id)
                if final_output:
                    student_results = (
                        final_output.get("reviewed_results")
                        or final_output.get("student_results", [])
                    )
            except Exception as e:
                logger.debug(f"获取最终输出失败: {e}")

        
        # Attach logic review payloads from state when missing on student_results.
        logic_review_by_student: Dict[str, Any] = {}
        for item in state.get("logic_review_results") or []:
            if not isinstance(item, dict):
                continue
            key = item.get("student_key") or item.get("studentKey")
            if key:
                logic_review_by_student[key] = item
        if logic_review_by_student:
            for student in student_results:
                if not isinstance(student, dict):
                    continue
                if student.get("logic_review") or student.get("logicReview"):
                    continue
                key = (
                    student.get("student_key")
                    or student.get("studentKey")
                    or student.get("student_name")
                    or student.get("studentName")
                )
                payload = logic_review_by_student.get(key)
                if payload:
                    student["logic_review"] = payload
                    student["logicReview"] = payload
                    if not student.get("logic_reviewed_at") and payload.get("reviewed_at"):
                        student["logic_reviewed_at"] = payload.get("reviewed_at")
        return {
            "batch_id": batch_id,
            "status": run_info.status.value,
            "results": _format_results_for_frontend(student_results),
            "class_report": state.get("class_report"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取批改结果失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.get("/full-results/{batch_id}")
async def get_full_batch_results(
    batch_id: str, orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """
    获取批次完整批改结果（包含跨页题目信息）

    Args:
        batch_id: 批次 ID
        orchestrator: LangGraph Orchestrator

    Returns:
        完整批改结果（包含跨页题目信息）
    """

    async def _load_answer_images_from_db(history_id: str) -> List[str]:
        try:
            images = await _maybe_await(get_page_images(history_id))
            if not images:
                return []
            return [img.file_url for img in images if img.file_url]
        except Exception as exc:
            logger.debug(f"Failed to load answer images from DB: {exc}")
            return []

    async def _load_from_db() -> Dict[str, Any]:
        history = await get_grading_history(batch_id)
        if not history:
            raise HTTPException(status_code=404, detail="批次不存在")

        raw_results: List[Dict[str, Any]] = []
        for row in await get_student_results(history.id):
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

        class_report = None
        history_data = history.result_data
        if history_data:
            if isinstance(history_data, str):
                try:
                    history_data = json.loads(history_data)
                except Exception:
                    history_data = {}
            if isinstance(history_data, dict):
                class_report = history_data.get("summary") or history_data.get("class_report")

        formatted_results = _format_results_for_frontend(raw_results)
        total_max = 0.0
        for item in formatted_results:
            try:
                total_max = max(total_max, float(item.get("maxScore") or 0))
            except (TypeError, ValueError):
                continue

        return {
            "batch_id": batch_id,
            "status": history.status or "completed",
            "results": formatted_results,
            "cross_page_questions": [],
            "parsed_rubric": {},
            "class_report": class_report,
            "total_students": len(formatted_results),
            "total_score": total_max or 100,
        }

    try:
        if not orchestrator:
            return await _load_from_db()

        run_id = f"batch_grading_{batch_id}"
        run_info = await orchestrator.get_run_info(run_id)

        if not run_info:
            return await _load_from_db()

        state = run_info.state or {}
        student_results = (
            state.get("reviewed_results")
            or state.get("confessed_results")
            or state.get("student_results", [])
        ) or []
        cross_page_questions = state.get("cross_page_questions", []) or []
        parsed_rubric = state.get("parsed_rubric", {}) or {}
        class_report = state.get("class_report") or state.get("export_data", {}).get("class_report")
        final_output: Optional[Dict[str, Any]] = None

        # Attach logic review payloads from state when missing on student_results.
        logic_review_by_student: Dict[str, Any] = {}
        for item in state.get("logic_review_results") or []:
            if not isinstance(item, dict):
                continue
            key = item.get("student_key") or item.get("studentKey")
            if key:
                logic_review_by_student[key] = item
        if logic_review_by_student:
            for student in student_results:
                if not isinstance(student, dict):
                    continue
                if student.get("logic_review") or student.get("logicReview"):
                    continue
                key = (
                    student.get("student_key")
                    or student.get("studentKey")
                    or student.get("student_name")
                    or student.get("studentName")
                )
                payload = logic_review_by_student.get(key)
                if payload:
                    student["logic_review"] = payload
                    student["logicReview"] = payload
                    if not student.get("logic_reviewed_at") and payload.get("reviewed_at"):
                        student["logic_reviewed_at"] = payload.get("reviewed_at")

        if not student_results or not parsed_rubric:
            final_output = await orchestrator.get_final_output(run_id)
            if final_output:
                student_results = (
                    student_results
                    or final_output.get("reviewed_results")
                    or final_output.get("confessed_results")
                    or final_output.get("student_results")
                    or final_output.get("results")
                    or []
                )
                parsed_rubric = parsed_rubric or final_output.get("parsed_rubric", {}) or {}
                cross_page_questions = cross_page_questions or final_output.get("cross_page_questions", []) or []

        if not student_results:
            grading_results = state.get("grading_results") or []
            if not grading_results and final_output:
                grading_results = final_output.get("grading_results") or []
            if grading_results:
                student_results = _build_student_results_from_grading_results(grading_results)

        # 如果 orchestrator 返回空结果，回退到数据库查询
        if not student_results:
            logger.info(f"Orchestrator 返回空结果，回退到数据库查询: batch_id={batch_id}")
            return await _load_from_db()

        return {
            "batch_id": batch_id,
            "status": run_info.status.value,
            "results": _format_results_for_frontend(student_results),
            "cross_page_questions": cross_page_questions,
            "parsed_rubric": parsed_rubric,
            "class_report": class_report,
            "total_students": len(student_results),
            "total_score": parsed_rubric.get("total_score", 100) if parsed_rubric else 100,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取完整批改结果失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.get("/cross-page-questions/{batch_id}")
async def get_cross_page_questions(
    batch_id: str, orchestrator: Orchestrator = Depends(get_orchestrator)
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


class GradingRetryRequest(BaseModel):
    """批改断点重试请求（用于恢复被暂停的 grade_batch 节点）。"""

    batch_id: str = Field(..., description="批次 ID")
    action: str = Field(..., description="retry/abort")
    notes: Optional[str] = Field(None, description="补充说明")


@router.post("/review/rubric")
async def submit_rubric_review(
    request: RubricReviewRequest, orchestrator: Orchestrator = Depends(get_orchestrator)
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

        # After resuming a paused graph, restart the stream forwarder so the frontend
        # continues to receive subsequent workflow updates.
        await _ensure_stream_task(
            batch_id=request.batch_id,
            run_id=run_id,
            orchestrator=orchestrator,
        )

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
    request: ResultsReviewRequest, orchestrator: Orchestrator = Depends(get_orchestrator)
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
        if not success and not request.results:
            raise HTTPException(status_code=409, detail="批次未处于可复核状态")

        # Restart stream forwarder after resume so the frontend can see subsequent nodes.
        await _ensure_stream_task(
            batch_id=request.batch_id,
            run_id=run_id,
            orchestrator=orchestrator,
        )

        cached = batch_image_cache.get(request.batch_id)
        if cached and "review_required" in cached:
            cached.pop("review_required", None)

        if request.results:
            try:
                history = await get_grading_history(request.batch_id)
                if history:
                    raw_history_data = history.result_data
                    history_data: Dict[str, Any] = {}
                    if isinstance(raw_history_data, dict):
                        history_data = raw_history_data
                    elif isinstance(raw_history_data, str):
                        try:
                            parsed_history = json.loads(raw_history_data)
                            if isinstance(parsed_history, dict):
                                history_data = parsed_history
                        except Exception:
                            history_data = {}

                    class_id = history_data.get("class_id") if history_data else None
                    homework_id = history_data.get("homework_id") if history_data else None

                    existing_results = {
                        row.student_key: row for row in await get_student_results(history.id)
                    }

                    updated_scores: List[float] = []
                    updated_keys: set[str] = set()

                    for incoming in request.results:
                        student_key = (
                            incoming.get("studentKey")
                            or incoming.get("student_key")
                            or incoming.get("studentName")
                            or incoming.get("student_name")
                        )
                        if not student_key:
                            continue

                        existing_row = existing_results.get(student_key)
                        existing_data = existing_row.result_data if existing_row else None
                        if isinstance(existing_data, str):
                            try:
                                existing_data = json.loads(existing_data)
                            except Exception:
                                existing_data = {}
                        if not isinstance(existing_data, dict):
                            existing_data = {}

                        question_results = (
                            existing_data.get("questionResults")
                            or existing_data.get("question_results")
                            or []
                        )
                        if not isinstance(question_results, list):
                            question_results = []
                        original_scores = {
                            str(q.get("questionId") or q.get("question_id")): _safe_float(
                                q.get("score")
                            )
                            for q in question_results
                            if q.get("questionId") or q.get("question_id")
                        }

                        updates = (
                            incoming.get("questionResults")
                            or incoming.get("question_results")
                            or []
                        )
                        if not isinstance(updates, list):
                            updates = []

                        for update in updates:
                            question_id = str(
                                update.get("questionId") or update.get("question_id") or ""
                            )
                            if not question_id:
                                continue
                            updated_score = update.get("score")
                            updated_feedback = update.get("feedback")
                            target = next(
                                (
                                    q
                                    for q in question_results
                                    if str(q.get("questionId") or q.get("question_id"))
                                    == question_id
                                ),
                                None,
                            )
                            if not target:
                                target = {
                                    "questionId": question_id,
                                    "score": updated_score or 0,
                                    "feedback": updated_feedback or "",
                                }
                                question_results.append(target)
                                continue
                            original_score = original_scores.get(
                                question_id, target.get("score") or 0
                            )
                            target["score"] = (
                                updated_score if updated_score is not None else original_score
                            )
                            if updated_feedback is not None:
                                target["feedback"] = updated_feedback

                        existing_data["questionResults"] = question_results

                        total_score = sum(_safe_float(q.get("score")) for q in question_results)
                        total_max = sum(
                            _safe_float(q.get("maxScore") or q.get("max_score"))
                            for q in question_results
                        )
                        existing_data["score"] = total_score
                        if total_max > 0:
                            existing_data["maxScore"] = total_max
                            existing_data.pop("gradingAnnotations", None)
                            existing_data.pop("grading_annotations", None)

                        updated_scores.append(total_score)
                        updated_keys.add(student_key)

                        student_id_value = existing_row.student_id if existing_row else None
                        student_result = StudentGradingResult(
                            id=existing_row.id if existing_row else _make_student_result_id(history.id, student_key, student_id_value),
                            grading_history_id=history.id,
                            student_key=student_key,
                            score=total_score,
                            max_score=total_max or None,
                            class_id=existing_row.class_id if existing_row else None,
                            student_id=student_id_value,
                            summary=existing_row.summary if existing_row else None,
                            confession=existing_row.confession if existing_row else None,
                            result_data=existing_data,
                        )
                        await save_student_result(student_result)

                        if class_id and homework_id and student_result.student_id:
                            upsert_homework_submission_grade(
                                class_id=class_id,
                                homework_id=homework_id,
                                student_id=student_result.student_id,
                                student_name=student_key,
                                score=total_score,
                                feedback=(
                                    existing_data.get("studentSummary", {}).get("overall")
                                    if isinstance(existing_data.get("studentSummary"), dict)
                                    else None
                                ),
                                grading_batch_id=request.batch_id,
                            )

                    if updated_scores:
                        remaining_scores = [
                            row.score or 0
                            for key, row in existing_results.items()
                            if key not in updated_keys
                        ]
                        all_scores = [*updated_scores, *remaining_scores]
                        history.average_score = (
                            round(sum(all_scores) / len(all_scores), 2) if all_scores else None
                        )
                        history.total_students = len(all_scores)
                        if history_data:
                            summary = history_data.get("summary")
                            if isinstance(summary, dict):
                                summary["average_score"] = history.average_score
                            history.result_data = history_data
                        await save_grading_history(history)
            except Exception as exc:
                logger.error("保存复核结果失败: %s", exc, exc_info=True)

        if success:
            return {"success": True, "message": "批改结果复核已提交"}
        return {"success": True, "message": "批改结果已保存，流程未恢复"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"提交批改复核失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"提交失败: {str(e)}")


@router.post("/review/grading")
async def submit_grading_retry(
    request: GradingRetryRequest, orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """提交批改断点重试/终止信号，恢复被暂停的 workflow。"""
    try:
        if not orchestrator:
            raise HTTPException(status_code=503, detail="编排器未初始化")

        action = request.action.lower().strip()
        if action not in ("retry", "abort"):
            raise HTTPException(status_code=400, detail="无效的 action")

        run_id = f"batch_grading_{request.batch_id}"
        run_info = await orchestrator.get_run_info(run_id)
        if not run_info:
            raise HTTPException(status_code=404, detail="批次不存在")

        payload: Dict[str, Any] = {"action": action}
        if request.notes:
            payload["notes"] = request.notes

        success = await orchestrator.send_event(run_id, "review_signal", payload)
        if not success:
            raise HTTPException(status_code=409, detail="批次未处于可继续状态")

        await _ensure_stream_task(
            batch_id=request.batch_id,
            run_id=run_id,
            orchestrator=orchestrator,
        )

        cached = batch_image_cache.get(request.batch_id)
        if cached and "review_required" in cached:
            cached.pop("review_required", None)

        return {"success": True, "message": "Grading retry signal submitted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"提交批改断点重试失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"提交失败: {str(e)}")


@router.post("/confirm-boundary")
async def confirm_student_boundary(
    request: ConfirmBoundaryRequest, orchestrator: Orchestrator = Depends(get_orchestrator)
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
            student_boundaries.append(
                {
                    "student_key": request.student_key,
                    "pages": request.confirmed_pages,
                    "confirmed": True,
                }
            )

        logger.info(
            f"学生边界已确认: batch_id={request.batch_id}, student_key={request.student_key}"
        )

        return {"success": True, "message": f"学生 {request.student_key} 的边界已确认"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"确认学生边界失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"确认失败: {str(e)}")


# ==================== 导出 API ====================


class ExportAnnotatedImagesRequest(BaseModel):
    """导出带批注图片请求"""

    include_original: bool = Field(default=False, description="是否包含原始图片")


class ExportExcelRequest(BaseModel):
    """导出 Excel 请求"""

    columns: Optional[List[Dict[str, Any]]] = Field(None, description="自定义列配置")


class SmartExcelRequest(BaseModel):
    """智能 Excel 生成请求"""

    prompt: str = Field(..., description="用户描述的格式需求")
    template_base64: Optional[str] = Field(None, description="模板 Excel Base64")


@router.post("/export/annotated-images/{batch_id}")
async def export_annotated_images(
    batch_id: str,
    request: ExportAnnotatedImagesRequest = ExportAnnotatedImagesRequest(),
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    """
    导出带批注的学生作答图片 (ZIP)

    将所有学生的作答图片渲染批注后打包为 ZIP 下载
    """
    raise HTTPException(
        status_code=410,
        detail="后端批注渲染已禁用，请使用前端 Canvas 渲染与导出。",
    )


@router.post("/export/excel/{batch_id}")
async def export_excel(
    batch_id: str,
    request: ExportExcelRequest = ExportExcelRequest(),
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    """
    导出 Excel 统计数据

    包含学生成绩、题目统计、班级报告等多个 Sheet
    """
    from fastapi.responses import Response
    from src.services.export_service import ExcelExporter

    try:
        if not orchestrator:
            raise HTTPException(status_code=503, detail="编排器未初始化")

        run_id = f"batch_grading_{batch_id}"
        run_info = await orchestrator.get_run_info(run_id)

        if not run_info:
            raise HTTPException(status_code=404, detail="批次不存在")

        state = run_info.state or {}
        student_results = (
            state.get("reviewed_results")
            or state.get("confessed_results")
            or state.get("student_results", [])
        )
        class_report = state.get("class_report") or state.get("export_data", {}).get("class_report")

        if not student_results:
            raise HTTPException(status_code=404, detail="无批改结果")

        # 格式化结果
        formatted_results = _format_results_for_frontend(student_results)

        # 导出
        exporter = ExcelExporter()
        excel_bytes = exporter.export_basic(formatted_results, class_report, request.columns)

        filename = f"grading_report_{batch_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

        return Response(
            content=excel_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"导出 Excel 失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


@router.post("/export/smart-excel/{batch_id}")
async def export_smart_excel(
    batch_id: str,
    request: SmartExcelRequest,
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    """
    LLM 智能 Excel 生成

    支持：
    - 用户对话描述格式需求
    - 导入已有 Excel 模板并填充数据
    """
    from fastapi.responses import Response
    from src.services.export_service import SmartExcelGenerator
    from src.services.llm_client import get_llm_client

    try:
        if not orchestrator:
            raise HTTPException(status_code=503, detail="编排器未初始化")

        run_id = f"batch_grading_{batch_id}"
        run_info = await orchestrator.get_run_info(run_id)

        if not run_info:
            raise HTTPException(status_code=404, detail="批次不存在")

        state = run_info.state or {}
        student_results = state.get("student_results", [])
        class_report = state.get("class_report") or state.get("export_data", {}).get("class_report")

        if not student_results:
            raise HTTPException(status_code=404, detail="无批改结果")

        # 格式化结果
        formatted_results = _format_results_for_frontend(student_results)

        # 解码模板
        template_bytes = None
        if request.template_base64:
            import base64

            try:
                if request.template_base64.startswith("data:"):
                    request.template_base64 = request.template_base64.split(",", 1)[1]
                template_bytes = base64.b64decode(request.template_base64)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"模板解码失败: {e}")

        # 获取 LLM 客户端
        llm_client = None
        try:
            llm_client = get_llm_client()
        except Exception as e:
            logger.debug(f"获取 LLM 客户端失败: {e}")

        # 生成 Excel
        generator = SmartExcelGenerator(llm_client)
        excel_bytes, explanation = await generator.generate_from_prompt(
            formatted_results,
            class_report,
            request.prompt,
            template_bytes,
        )

        filename = f"grading_smart_{batch_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

        return Response(
            content=excel_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-LLM-Explanation": explanation.encode("utf-8").decode("latin-1"),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"智能 Excel 生成失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")


@router.post("/render/batch/{batch_id}")
async def render_batch_annotations(
    batch_id: str,
    page_indices: Optional[List[int]] = None,
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    """
    批量渲染批注到图片

    返回指定页面的带批注图片 Base64 列表
    """
    raise HTTPException(
        status_code=410,
        detail="后端批注渲染已禁用，请使用前端 Canvas 渲染。",
    )


# ==================== Confession API (Task 11) ====================


class ConfessionResponse(BaseModel):
    """Confession report response"""

    batch_id: str
    overall_status: str
    overall_confidence: float
    issues: List[Dict[str, Any]]
    warnings: List[str]
    summary: str
    memory_updates: List[Dict[str, Any]]
    generated_at: str


@router.get("/confession/{batch_id}", response_model=ConfessionResponse)
async def get_batch_confession(
    batch_id: str,
    include_memory_updates: bool = True,
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    """
    Get batch confession report (enhanced).

    Returns:
        Confession report with issues, warnings, and memory updates.
    """
    try:
        if not orchestrator:
            raise HTTPException(status_code=503, detail="Orchestrator not initialized")

        run_id = f"batch_grading_{batch_id}"
        run_info = await orchestrator.get_run_info(run_id)

        if not run_info:
            raise HTTPException(status_code=404, detail="Batch not found")

        state = run_info.state or {}
        student_results = (
            state.get("reviewed_results")
            or state.get("confessed_results")
            or state.get("student_results", [])
        )

        if not student_results:
            try:
                final_output = await orchestrator.get_final_output(run_id)
                if final_output:
                    student_results = (
                        final_output.get("reviewed_results")
                        or final_output.get("confessed_results")
                        or final_output.get("student_results", [])
                    )
            except Exception:
                student_results = []
        if not student_results:
            raise HTTPException(status_code=404, detail="No grading results")

        all_issues: List[Dict[str, Any]] = []
        all_warnings: List[str] = []
        total_confidence = 0.0
        student_count = 0

        for student in student_results:
            confession = student.get("confession") or {}
            if isinstance(confession, str):
                try:
                    confession = json.loads(confession)
                except Exception:
                    confession = {}
            if not isinstance(confession, dict):
                confession = {}

            items = confession.get("items") or []
            if isinstance(items, list):
                student_key = student.get("student_key") or student.get("studentKey") or "Unknown"
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    issue_copy = dict(item)
                    issue_copy["student_key"] = student_key
                    all_issues.append(issue_copy)

            conf = confession.get("overall_confidence") or confession.get("overallConfidence")
            if conf is not None:
                total_confidence += float(conf)
                student_count += 1

        avg_confidence = total_confidence / student_count if student_count > 0 else 0.5

        error_count = sum(
            1 for i in all_issues if str(i.get("severity") or "").lower() == "error"
        )
        warning_count = sum(
            1 for i in all_issues if str(i.get("severity") or "").lower() == "warning"
        )

        if error_count > 0:
            overall_status = "needs_review"
        elif warning_count > 3:
            overall_status = "caution"
        else:
            overall_status = "ok"

        memory_updates: List[Dict[str, Any]] = []
        if include_memory_updates:
            try:
                for student in student_results:
                    confession = student.get("confession") or {}
                    updates = confession.get("memory_updates") or []
                    if not isinstance(updates, list):
                        continue
                    student_key = (
                        student.get("student_key")
                        or student.get("studentKey")
                        or student.get("student_name")
                        or student.get("studentName")
                        or "Unknown"
                    )
                    for update in updates:
                        if isinstance(update, dict):
                            update_copy = dict(update)
                            update_copy.setdefault("student_key", student_key)
                            memory_updates.append(update_copy)
            except Exception as exc:
                logger.debug(f"Failed to collect memory updates: {exc}")

        return {
            "batch_id": batch_id,
            "overall_status": overall_status,
            "overall_confidence": round(avg_confidence, 3),
            "issues": all_issues,
            "warnings": list(set(all_warnings)),
            "summary": f"Batch {batch_id}: {len(student_results)} students, avg confidence {avg_confidence:.1%}",
            "memory_updates": memory_updates,
            "generated_at": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get confession report: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get confession: {str(e)}")


@router.get("/{batch_id}/files")
async def list_batch_files(batch_id: str):
    """获取批次的所有存储文件列表"""
    try:
        file_storage = get_file_storage_service()
        files = await file_storage.list_batch_files(batch_id)
        
        return {
            "batch_id": batch_id,
            "files": [f.to_dict() for f in files],
            "total_count": len(files),
        }
    except Exception as e:
        logger.error(f"获取文件列表失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取文件列表失败: {str(e)}")


@router.get("/files/{file_id}")
async def get_file(file_id: str):
    """获取文件信息"""
    try:
        file_storage = get_file_storage_service()
        file_info = await file_storage.get_file_info(file_id)
        
        if not file_info:
            raise HTTPException(status_code=404, detail="文件不存在")
        
        return file_info.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取文件信息失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取文件信息失败: {str(e)}")


@router.get("/files/{file_id}/download")
async def download_file(file_id: str):
    """下载文件"""
    from fastapi.responses import Response
    
    try:
        file_storage = get_file_storage_service()
        file_info = await file_storage.get_file_info(file_id)
        
        if not file_info:
            raise HTTPException(status_code=404, detail="文件不存在")
        
        content = await file_storage.get_file(file_id)
        if not content:
            raise HTTPException(status_code=404, detail="文件内容不存在")
        
        return Response(
            content=content,
            media_type=file_info.content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{file_info.filename}"',
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"下载文件失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"下载文件失败: {str(e)}")


# ====================== 管理 API ======================

@router.post("/admin/clear-slots")
async def admin_clear_all_slots(teacher_id: Optional[str] = None):
    """
    管理端点：清理教师的活动槽位（用于解决槽位卡死问题）
    
    如果提供 teacher_id，只清理该教师的槽位；
    否则清理所有已知教师的槽位。
    """
    try:
        run_controller = await get_run_controller()
        if not run_controller:
            return {"success": False, "message": "Redis 不可用，无法清理槽位"}
        
        cleared_teachers = []
        
        if teacher_id:
            # 清理指定教师的槽位
            await run_controller.force_clear_teacher_slots(teacher_id)
            cleared_teachers.append(teacher_id)
        else:
            # 清理所有已知教师的槽位
            # 从 Redis 中获取所有教师的 active 槽位 key
            redis_client = run_controller._redis
            pattern = "grading_run:*:active"
            async for key in redis_client.scan_iter(match=pattern):
                key_str = key.decode("utf-8") if isinstance(key, bytes) else key
                # 从 key 中提取 teacher_key
                parts = key_str.split(":")
                if len(parts) >= 3:
                    teacher_key = parts[1]
                    await run_controller.force_clear_teacher_slots(teacher_key)
                    cleared_teachers.append(teacher_key)
        
        logger.info(f"[admin_clear_all_slots] 已清理槽位: {cleared_teachers}")
        return {
            "success": True,
            "message": f"已清理 {len(cleared_teachers)} 个教师的槽位",
            "cleared_teachers": cleared_teachers,
        }
    except Exception as e:
        logger.error(f"清理槽位失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"清理槽位失败: {str(e)}")


@router.post("/admin/clear-progress-cache")
async def admin_clear_progress_cache(batch_id: Optional[str] = None):
    """
    管理端点：清理批改进度缓存（用于解决旧批次缓存重放问题）
    
    如果提供 batch_id，只清理该批次的缓存；
    否则清理所有批次的缓存。
    """
    try:
        redis_client = await _get_redis_client()
        if not redis_client:
            return {"success": False, "message": "Redis 不可用，无法清理缓存"}
        
        cleared_count = 0
        
        if batch_id:
            # 清理指定批次的缓存
            cache_key = _progress_cache_key(batch_id)
            await redis_client.delete(cache_key)
            cleared_count = 1
        else:
            # 清理所有批次的缓存
            pattern = f"{REDIS_PROGRESS_KEY_PREFIX}:*"
            async for key in redis_client.scan_iter(match=pattern):
                await redis_client.delete(key)
                cleared_count += 1
        
        logger.info(f"[admin_clear_progress_cache] 已清理 {cleared_count} 个批次的进度缓存")
        return {
            "success": True,
            "message": f"已清理 {cleared_count} 个批次的进度缓存",
            "cleared_count": cleared_count,
        }
    except Exception as e:
        logger.error(f"清理进度缓存失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"清理进度缓存失败: {str(e)}")
