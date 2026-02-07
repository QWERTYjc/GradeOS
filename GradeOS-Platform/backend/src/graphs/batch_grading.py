import logging
import os
import asyncio
import json
import re
import time
import copy
from functools import lru_cache
from typing import Optional, List, Dict, Any, Literal, Tuple
from datetime import datetime
from dataclasses import dataclass, field

from langgraph.graph import StateGraph, END
from langgraph.types import Send, interrupt
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langchain_core.runnables import RunnableConfig, RunnableLambda

from src.graphs.state import BatchGradingGraphState
from src.utils.llm_thinking import split_thinking_content


logger = logging.getLogger(__name__)


# PostgreSQL 图片存储（延迟导入以避免循环依赖）
def _get_pg_image_reader():
    """获取 PostgreSQL 图片读取函数"""
    try:
        from src.db.postgres_images import get_batch_images_as_bytes_list
        return get_batch_images_as_bytes_list
    except ImportError:
        return None

# Stdout-visible workflow markers for Railway verification.
workflow_logger = logging.getLogger("gradeos.workflow")


@lru_cache(maxsize=1)
def _get_broadcast_progress():
    """延迟加载进度广播函数，避免测试场景触发重依赖导入。"""
    if os.getenv("DISABLE_PROGRESS_BROADCAST", "false").strip().lower() in (
        "1",
        "true",
        "yes",
    ):

        async def _noop(*_args, **_kwargs) -> None:
            return None

        return _noop

    from src.api.routes.batch_langgraph import broadcast_progress

    return broadcast_progress


async def _broadcast_progress(batch_id: str, message: Dict[str, Any]) -> None:
    """包装进度广播，便于测试中禁用。"""
    await _get_broadcast_progress()(batch_id, message)


# ==================== 批次配置 ====================


@dataclass
class BatchConfig:
    """
    批次配置类

    支持配置批次大小和并发数量。

    Requirements: 3.1, 10.1
    """

    batch_size: int = 1000  # 每批处理的页面数量 (解除限制)
    max_concurrent_workers: int = 5  # 最大并发 Worker 数量
    max_retries: int = 2  # 批次失败最大重试次数
    retry_delay: float = 1.0  # 重试延迟（秒）

    @classmethod
    def from_env(cls) -> "BatchConfig":
        """从环境变量加载配置"""
        return cls(
            batch_size=int(os.getenv("GRADING_BATCH_SIZE", "1000")),
            max_concurrent_workers=int(os.getenv("GRADING_MAX_WORKERS", "5")),
            max_retries=int(os.getenv("GRADING_MAX_RETRIES", "2")),
            retry_delay=float(os.getenv("GRADING_RETRY_DELAY", "1.0")),
        )


# 全局批次配置
_batch_config: Optional[BatchConfig] = None


def get_batch_config() -> BatchConfig:
    """获取批次配置"""
    global _batch_config
    if _batch_config is None:
        _batch_config = BatchConfig.from_env()
    return _batch_config


def set_batch_config(config: BatchConfig) -> None:
    """设置批次配置"""
    global _batch_config
    _batch_config = config
    logger.info(
        f"批次配置已更新: batch_size={config.batch_size}, "
        f"max_workers={config.max_concurrent_workers}, "
        f"max_retries={config.max_retries}"
    )


# ==================== 进度报告 ====================


@dataclass
class BatchProgress:
    """
    批次进度信息

    Requirements: 3.4
    """

    batch_id: str
    total_batches: int
    completed_batches: int = 0
    failed_batches: int = 0
    in_progress_batches: int = 0
    total_pages: int = 0
    processed_pages: int = 0
    failed_pages: int = 0
    current_stage: str = "initialized"
    percentage: float = 0.0
    batch_details: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    timestamps: Dict[str, str] = field(default_factory=dict)

    def update_batch_status(
        self,
        batch_index: int,
        status: str,
        pages_processed: int = 0,
        pages_failed: int = 0,
        error: Optional[str] = None,
    ) -> None:
        """更新单个批次状态"""
        self.batch_details[batch_index] = {
            "status": status,
            "pages_processed": pages_processed,
            "pages_failed": pages_failed,
            "error": error,
            "updated_at": datetime.now().isoformat(),
        }

        # 重新计算统计
        self.completed_batches = sum(
            1 for d in self.batch_details.values() if d["status"] == "completed"
        )
        self.failed_batches = sum(1 for d in self.batch_details.values() if d["status"] == "failed")
        self.in_progress_batches = sum(
            1 for d in self.batch_details.values() if d["status"] == "in_progress"
        )
        self.processed_pages = sum(d["pages_processed"] for d in self.batch_details.values())
        self.failed_pages = sum(d["pages_failed"] for d in self.batch_details.values())

        # 计算百分比（批改阶段占 15%-80%）
        if self.total_batches > 0:
            batch_progress = self.completed_batches / self.total_batches
            self.percentage = 15.0 + batch_progress * 65.0

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "batch_id": self.batch_id,
            "total_batches": self.total_batches,
            "completed_batches": self.completed_batches,
            "failed_batches": self.failed_batches,
            "in_progress_batches": self.in_progress_batches,
            "total_pages": self.total_pages,
            "processed_pages": self.processed_pages,
            "failed_pages": self.failed_pages,
            "current_stage": self.current_stage,
            "percentage": self.percentage,
            "batch_details": self.batch_details,
            "timestamps": self.timestamps,
        }


# 进度报告回调类型
ProgressCallback = Optional[callable]


# ==================== 批次任务状态 ====================


@dataclass
class BatchTaskState:
    """
    单个批次任务的状态

    用于跟踪批次执行状态和支持重试。

    Requirements: 3.3, 9.3
    """

    batch_id: str
    batch_index: int
    total_batches: int
    page_indices: List[int]
    images: List[str]
    rubric: str
    parsed_rubric: Dict[str, Any]
    api_key: str
    page_index_contexts: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 2
    status: str = "pending"  # pending, in_progress, completed, failed
    error: Optional[str] = None
    results: List[Dict[str, Any]] = field(default_factory=list)


# ==================== 节点实现 ====================


async def intake_node(state: BatchGradingGraphState) -> Dict[str, Any]:
    """
    接收文件节点

    验证输入文件，准备处理环境。
    """
    batch_id = state["batch_id"]
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

    logger.info(f"[intake] 开始接收文件: batch_id={batch_id}")

    # 验证必要的输入
    answer_images = state.get("answer_images", [])
    rubric_images = state.get("rubric_images", [])

    if not answer_images:
        raise ValueError("未提供答题图像")

    logger.info(
        f"[intake] 文件接收完成: batch_id={batch_id}, "
        f"答题页数={len(answer_images)}, 评分标准页数={len(rubric_images)}"
    )

    return {
        "current_stage": "intake_completed",
        "percentage": 5.0,
        "timestamps": {**state.get("timestamps", {}), "intake_at": datetime.now().isoformat()},
    }


async def preprocess_node(state: BatchGradingGraphState) -> Dict[str, Any]:
    """
    图像预处理节点

    对图像进行预处理：
    1. 转换为 JPEG 格式
    2. 压缩质量控制
    3. 去噪、增强、旋转校正等（TODO）
    """
    batch_id = state["batch_id"]
    answer_images = state.get("answer_images", [])

    logger.info(f"[preprocess] 开始图像预处理: batch_id={batch_id}, 页数={len(answer_images)}")

    # 转换为 JPEG 格式
    processed_images = []
    for idx, img_bytes in enumerate(answer_images):
        try:
            from PIL import Image
            import io

            # 打开图像
            img = Image.open(io.BytesIO(img_bytes))

            # 转换为 RGB（JPEG 不支持 RGBA 和 P 模式）
            if img.mode in ("RGBA", "P", "LA"):
                # 创建白色背景
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                if img.mode in ("RGBA", "LA"):
                    background.paste(img, mask=img.split()[-1])  # 使用 alpha 通道作为 mask
                    img = background
                else:
                    img = img.convert("RGB")
            elif img.mode != "RGB":
                img = img.convert("RGB")

            # 保存为 JPEG
            output = io.BytesIO()
            img.save(output, format="JPEG", quality=85, optimize=True)
            processed_images.append(output.getvalue())

            logger.debug(
                f"[preprocess] 页面 {idx} 转换为 JPEG: {len(img_bytes)} -> {len(output.getvalue())} bytes"
            )
        except Exception as e:
            logger.warning(f"[preprocess] 页面 {idx} JPEG 转换失败: {e}，使用原图")
            processed_images.append(img_bytes)

    logger.info(
        f"[preprocess] 图像预处理完成: batch_id={batch_id}, JPEG转换={len(processed_images)}/{len(answer_images)}"
    )

    student_boundaries = _build_student_boundaries(state, len(processed_images))

    return {
        "processed_images": processed_images,
        "student_boundaries": student_boundaries,
        "current_stage": "preprocess_completed",
        "percentage": 10.0,
        "timestamps": {**state.get("timestamps", {}), "preprocess_at": datetime.now().isoformat()},
    }


def _coerce_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _first_not_none(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _sanitize_pages(raw_pages: Any, total_pages: int) -> List[int]:
    if not isinstance(raw_pages, (list, tuple)):
        return []
    cleaned = []
    for item in raw_pages:
        idx = _coerce_int(item)
        if idx is None:
            continue
        if 0 <= idx < total_pages:
            cleaned.append(idx)
    return sorted(set(cleaned))


def _normalize_manual_boundaries(raw: Any, total_pages: int) -> List[Dict[str, Any]]:
    if not raw:
        return []

    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return []

    if isinstance(raw, dict):
        for key in ("boundaries", "students", "start_pages", "start_indices"):
            if key in raw:
                raw = raw[key]
                break
        else:
            raw = []

    if isinstance(raw, list) and raw and all(not isinstance(x, (list, dict)) for x in raw):
        start_indices = _sanitize_pages(raw, total_pages)
        if 0 not in start_indices:
            start_indices.insert(0, 0)
        groups = []
        for idx, start in enumerate(start_indices):
            end = start_indices[idx + 1] - 1 if idx + 1 < len(start_indices) else total_pages - 1
            if end < start:
                continue
            groups.append(
                {
                    "pages": list(range(start, end + 1)),
                    "start_page": start,
                    "end_page": end,
                }
            )
        return groups

    if not isinstance(raw, list):
        return []

    groups = []
    for entry in raw:
        if isinstance(entry, list):
            pages = _sanitize_pages(entry, total_pages)
            if pages:
                groups.append({"pages": pages})
            continue
        if not isinstance(entry, dict):
            continue

        pages = entry.get("pages") or entry.get("page_indices") or entry.get("pageIndices")
        if pages is None:
            start = _first_not_none(
                entry.get("start_page"),
                entry.get("startPage"),
                entry.get("start"),
            )
            end = _first_not_none(
                entry.get("end_page"),
                entry.get("endPage"),
                entry.get("end"),
            )
            start_idx = _coerce_int(start) if start is not None else None
            end_idx = _coerce_int(end) if end is not None else None
            if start_idx is not None and end_idx is not None:
                pages = list(range(start_idx, end_idx + 1))

        pages = _sanitize_pages(pages, total_pages) if pages is not None else []
        if not pages:
            continue

        group = {"pages": pages}
        student_key = entry.get("student_key") or entry.get("studentKey")
        if student_key:
            group["student_key"] = str(student_key)
        student_id = entry.get("student_id") or entry.get("studentId")
        if student_id:
            group["student_id"] = str(student_id)
        student_name = entry.get("student_name") or entry.get("studentName") or entry.get("name")
        if student_name:
            group["student_name"] = str(student_name)
        class_name = entry.get("class_name") or entry.get("className")
        if class_name:
            group["class_name"] = str(class_name)
        groups.append(group)

    return groups


def _build_student_boundaries(
    state: BatchGradingGraphState, total_pages: int
) -> List[Dict[str, Any]]:
    inputs = state.get("inputs", {})
    manual_boundaries = _normalize_manual_boundaries(inputs.get("manual_boundaries"), total_pages)
    student_mapping = state.get("student_mapping") or inputs.get("student_mapping")
    student_boundaries: List[Dict[str, Any]] = []

    if student_mapping and isinstance(student_mapping, list):
        for idx, mapping in enumerate(student_mapping):
            pages = (
                mapping.get("pages") or mapping.get("page_indices") or mapping.get("pageIndices")
            )
            pages = _sanitize_pages(pages, total_pages) if pages is not None else []
            if not pages:
                start_idx = _first_not_none(
                    mapping.get("start_index"),
                    mapping.get("startIndex"),
                    mapping.get("start_page"),
                    mapping.get("startPage"),
                )
                end_idx = _first_not_none(
                    mapping.get("end_index"),
                    mapping.get("endIndex"),
                    mapping.get("end_page"),
                    mapping.get("endPage"),
                )
                start_page = _coerce_int(start_idx) if start_idx is not None else None
                end_page = _coerce_int(end_idx) if end_idx is not None else None
                if start_page is not None and end_page is not None:
                    pages = _sanitize_pages(list(range(start_page, end_page + 1)), total_pages)
            if not pages:
                continue

            student_name = mapping.get("student_name") or mapping.get("studentName")
            student_id = mapping.get("student_id") or mapping.get("studentId")
            student_key = (
                mapping.get("student_key")
                or mapping.get("studentKey")
                or student_name
                or student_id
                or f"学生{idx + 1}"
            )
            student_boundaries.append(
                {
                    "student_key": student_key,
                    "student_id": student_id,
                    "student_name": student_name,
                    "start_page": min(pages),
                    "end_page": max(pages),
                    "pages": sorted(pages),
                }
            )
    if not student_boundaries and manual_boundaries:
        for idx, boundary in enumerate(manual_boundaries):
            pages = boundary.get("pages") or boundary.get("page_indices") or boundary.get(
                "pageIndices"
            )
            pages = _sanitize_pages(pages, total_pages) if pages is not None else []
            if not pages:
                start_page = _first_not_none(
                    boundary.get("start_page"),
                    boundary.get("startPage"),
                    boundary.get("start"),
                )
                end_page = _first_not_none(
                    boundary.get("end_page"),
                    boundary.get("endPage"),
                    boundary.get("end"),
                )
                start_idx = _coerce_int(start_page) if start_page is not None else None
                end_idx = _coerce_int(end_page) if end_page is not None else None
                if start_idx is not None and end_idx is not None:
                    pages = _sanitize_pages(list(range(start_idx, end_idx + 1)), total_pages)
            if not pages:
                continue
            merged = dict(boundary)
            merged["pages"] = sorted(pages)
            merged.setdefault("start_page", pages[0])
            merged.setdefault("end_page", pages[-1])
            if "student_key" not in merged:
                merged["student_key"] = f"学生{idx + 1}"
            student_boundaries.append(merged)

    return student_boundaries


async def rubric_parse_node(state: BatchGradingGraphState) -> Dict[str, Any]:
    """
    解析评分标准节点

    使用专门的 RubricParserService 解析评分标准图像，
    支持分批处理多页评分标准，提取完整的题目结构和评分细则。

    **关键**: 解析后的评分标准会注册到 RubricRegistry，供后续批改时通过
    GradingSkills.get_rubric_for_question 动态获取指定题目的评分标准。
    """
    batch_id = state["batch_id"]
    rubric_images = state.get("rubric_images", [])
    rubric_text = state.get("rubric", "")
    api_key = state.get("api_key") or os.getenv("LLM_API_KEY") or os.getenv("OPENROUTER_API_KEY")

    logger.info(
        f"[rubric_parse] 开始解析评分标准: batch_id={batch_id}, 评分标准页数={len(rubric_images)}"
    )

    # 🔍 诊断日志：检查 rubric_images 是否传入
    if rubric_images:
        logger.info(f"[rubric_parse] 📸 rubric_images 详情: 共 {len(rubric_images)} 页")
        for i, img in enumerate(rubric_images):
            if isinstance(img, bytes):
                logger.info(f"[rubric_parse]   - 第 {i+1} 页: {len(img)} bytes")
            else:
                logger.warning(f"[rubric_parse]   - 第 {i+1} 页: 类型异常 {type(img)}")
    else:
        logger.warning(f"[rubric_parse] ⚠️ rubric_images 为空！请检查前端是否正确上传了批改标准")

    parsed_rubric = {"total_questions": 0, "total_score": 0, "questions": []}

    # 创建 RubricRegistry 用于存储解析后的评分标准
    from src.services.rubric_registry import RubricRegistry
    from src.models.grading_models import QuestionRubric, ScoringPoint, AlternativeSolution

    rubric_registry = RubricRegistry()

    try:
        if rubric_images and api_key:
            # 使用专门的 RubricParserService 进行分批解析
            from src.services.rubric_parser import RubricParserService

            parser = RubricParserService(api_key=api_key)

            # 流式输出回调 - 发送 llm_stream_chunk 事件到前端
            parse_agent_id = "rubric-parse"
            review_agent_id = "rubric-review"
            parse_agent_name = "Rubric Parse"
            review_agent_name = "Rubric Review"

            await _broadcast_progress(
                batch_id,
                {
                    "type": "agent_update",
                    "agentId": parse_agent_id,
                    "agentName": parse_agent_name,
                    "agentLabel": parse_agent_name,
                    "parentNodeId": "rubric_parse",
                    "status": "running",
                    "progress": 0,
                    "message": "Preparing rubric parse",
                },
            )

            async def stream_callback(stream_type: str, chunk: str) -> None:
                phase = "parse"
                real_type = stream_type

                parts = stream_type.split(":")
                if len(parts) >= 3:
                    phase = parts[1]
                    real_type = ":".join(parts[2:])
                elif len(parts) == 2:
                    real_type = parts[1]

                target_node = "rubric_parse"
                target_agent = parse_agent_id
                node_name = parse_agent_name

                if phase == "review":
                    target_node = "rubric_review"
                    target_agent = review_agent_id
                    node_name = review_agent_name

                await _broadcast_progress(
                    batch_id,
                    {
                        "type": "llm_stream_chunk",
                        "nodeId": target_node,
                        "agentId": target_agent,
                        "nodeName": node_name,
                        "streamType": real_type,
                        "chunk": chunk,
                    },
                )

            async def progress_callback(
                batch_index: int,
                total_batches: int,
                status: str,
                message: Optional[str],
            ) -> None:

                normalized_total = max(1, total_batches)
                batch_progress = int(((batch_index + 1) / normalized_total) * 100)
                is_last_batch = (batch_index + 1) >= normalized_total

                if status == "reviewing":
                    await _broadcast_progress(
                        batch_id,
                        {
                            "type": "agent_update",
                            "agentId": parse_agent_id,
                            "agentName": parse_agent_name,
                            "agentLabel": parse_agent_name,
                            "parentNodeId": "rubric_parse",
                            "status": "completed" if is_last_batch else "running",
                            "progress": 100 if is_last_batch else batch_progress,
                            "message": (
                                "Parsing completed"
                                if is_last_batch
                                else (message or f"Batch {batch_index + 1}/{total_batches}")
                            ),
                        },
                    )
                    await _broadcast_progress(
                        batch_id,
                        {
                            "type": "agent_update",
                            "agentId": review_agent_id,
                            "agentName": review_agent_name,
                            "agentLabel": review_agent_name,
                            "parentNodeId": "rubric_review",
                            "status": "running",
                            "progress": 0,
                            "message": message or "Reviewing...",
                        },
                    )
                    return

                if status == "completed":
                    await _broadcast_progress(
                        batch_id,
                        {
                            "type": "agent_update",
                            "agentId": parse_agent_id,
                            "agentName": parse_agent_name,
                            "agentLabel": parse_agent_name,
                            "parentNodeId": "rubric_parse",
                            "status": "completed",
                            "progress": 100,
                            "message": message or "Parsing completed",
                        },
                    )
                    return

                status_map = {
                    "parsing": "running",
                    "running": "running",
                    "failed": "failed",
                }
                progress = 100 if status == "failed" else batch_progress

                await _broadcast_progress(
                    batch_id,
                    {
                        "type": "agent_update",
                        "agentId": parse_agent_id,
                        "agentName": parse_agent_name,
                        "agentLabel": parse_agent_name,
                        "parentNodeId": "rubric_parse",
                        "status": status_map.get(status, "running"),
                        "progress": progress,
                        "message": message or f"Batch {batch_index + 1}/{total_batches}",
                    },
                )

            # 添加超时保护，默认 10 分钟（评分标准可能很长）
            rubric_parse_timeout = int(os.getenv("RUBRIC_PARSE_TIMEOUT", "600"))
            try:
                result = await asyncio.wait_for(
                    parser.parse_rubric(
                        rubric_images=rubric_images,
                        progress_callback=progress_callback,
                        stream_callback=stream_callback,
                    ),
                    timeout=rubric_parse_timeout,
                )
            except asyncio.TimeoutError:
                logger.error(f"[rubric_parse] 解析超时（{rubric_parse_timeout}秒），batch_id={batch_id}")
                await _broadcast_progress(
                    batch_id,
                    {
                        "type": "workflow_error",
                        "error": f"评分标准解析超时（{rubric_parse_timeout}秒），请尝试减少评分标准页数或稍后重试",
                        "stage": "rubric_parse",
                    },
                )
                raise Exception(f"Rubric parse timeout after {rubric_parse_timeout}s")

            # 转换为字典格式
            parsed_rubric = {
                "total_questions": result.total_questions,
                "total_score": result.total_score,
                "rubric_format": result.rubric_format,
                "general_notes": result.general_notes,
                # LLM 直接生成的自白（极短）
                "confession": result.confession.to_dict() if hasattr(result.confession, 'to_dict') else {
                    "risks": getattr(result.confession, 'risks', []),
                    "uncertainties": getattr(result.confession, 'uncertainties', []),
                    "blindSpots": getattr(result.confession, 'blind_spots', []),
                    "needsReview": getattr(result.confession, 'needs_review', []),
                    "confidence": getattr(result.confession, 'confidence', 1.0),
                },
                "questions": [
                    {
                        "id": q.question_id,
                        "question_id": q.question_id,
                        "max_score": q.max_score,
                        "question_text": q.question_text,
                        "standard_answer": q.standard_answer,
                        "source_pages": getattr(q, "source_pages", []),
                        "criteria": [sp.description for sp in q.scoring_points],
                        # LLM 直接生成的题目级自白（极短）
                        "confession": q.confession.to_dict() if hasattr(q.confession, 'to_dict') else {
                            "risk": getattr(q.confession, 'risk', ''),
                            "uncertainty": getattr(q.confession, 'uncertainty', ''),
                        },
                        "scoring_points": [
                            {
                                "point_id": sp.point_id or f"{q.question_id}.{idx + 1}",
                                "description": sp.description,
                                "score": sp.score,
                                "is_required": sp.is_required,
                                "keywords": sp.keywords or [],
                                "expected_value": sp.expected_value,
                            }
                            for idx, sp in enumerate(q.scoring_points)
                        ],
                        "alternative_solutions": [
                            {
                                "description": alt.description,
                                "scoring_criteria": alt.scoring_criteria,
                                "note": alt.note,
                            }
                            for alt in q.alternative_solutions
                        ],
                        "deduction_rules": [
                            {
                                "rule_id": dr.rule_id or f"{q.question_id}.d{idx + 1}",
                                "description": dr.description,
                                "deduction": dr.deduction,
                                "conditions": dr.conditions,
                            }
                            for idx, dr in enumerate(getattr(q, "deduction_rules", []) or [])
                        ],
                        "grading_notes": q.grading_notes,
                    }
                    for q in result.questions
                ],
            }

            # 🔥 关键：将解析的评分标准注册到 RubricRegistry
            # 这样后续批改时可以通过 GradingSkills.get_rubric_for_question 获取
            rubric_registry.register_rubrics(result.questions)
            logger.info(f"[rubric_parse] 已注册 {len(result.questions)} 道题目到 RubricRegistry")

            # 同时生成格式化的评分标准上下文（供批改使用）
            rubric_context = parser.format_rubric_context(result)
            parsed_rubric["rubric_context"] = rubric_context

            # 生成自白报告
            inputs_dict = state.get("inputs", {}) or {}
            expected_question_count = inputs_dict.get("expected_question_count")
            expected_total_score = inputs_dict.get("expected_total_score")

            parse_confession = parser._generate_parse_confession(
                rubric=result,
                expected_question_count=expected_question_count,
                expected_total_score=expected_total_score,
            )

            # 将自白报告添加到 parsed_rubric
            parsed_rubric["overall_parse_confidence"] = parse_confession["overallConfidence"]
            parsed_rubric["parse_confession"] = parse_confession
            
            # 🔧 重要：用计算出的置信度覆盖 LLM 返回的置信度
            parsed_rubric["confession"]["confidence"] = parse_confession["overallConfidence"]

            # 同时更新 ParsedRubric 对象（如果需要重新注册）
            result.overall_parse_confidence = parse_confession["overallConfidence"]
            result.parse_confession = parse_confession

            logger.info(
                f"[rubric_parse] 评分标准解析成功: "
                f"题目数={result.total_questions}, 总分={result.total_score}, "
                f"置信度={parse_confession['overallConfidence']:.2f}, "
                f"状态={parse_confession['overallStatus']}"
            )
            
            # 🔍 输出完整的 AI 返回结果 JSON (仅在 DEBUG 模式)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"[rubric_parse] 📋 AI 返回的完整评分标准 JSON:")
                logger.debug(f"[rubric_parse] {json.dumps(parsed_rubric, ensure_ascii=False, indent=2)}")
            else:
                # 生产环境只输出题目列表
                question_ids = [q.get('question_id', '?') for q in parsed_rubric.get('questions', [])]
                logger.info(f"[rubric_parse] 题目列表: {', '.join(question_ids)}")

        elif rubric_text:
            # 如果有文本形式的评分标准，简单解析
            parsed_rubric["raw_text"] = rubric_text

    except Exception as e:
        logger.error(f"[rubric_parse] Rubric parse failed: {e}", exc_info=True)
        try:
            await _broadcast_progress(
                batch_id,
                {
                    "type": "rubric_parse_failed",
                    "message": "Rubric parse failed. Please re-upload a clear rubric.",
                    "error": str(e),
                },
            )
        except Exception:
            logger.debug("[rubric_parse] Failed to broadcast parse error")
        raise

    logger.info(
        f"[rubric_parse] 评分标准解析完成: batch_id={batch_id}, "
        f"题目数={parsed_rubric.get('total_questions', 0)}, "
        f"总分={parsed_rubric.get('total_score', 0)}"
    )

    inputs_dict = state.get("inputs", {}) or {}
    expected_total_score = inputs_dict.get("expected_total_score")
    if expected_total_score is not None:
        try:
            expected_total_score = float(expected_total_score)
            parsed_total_score = float(parsed_rubric.get("total_score", 0) or 0)
            if parsed_total_score > 0 and parsed_total_score < expected_total_score:
                message = (
                    f"Parsed total score {parsed_total_score} is lower than "
                    f"expected {expected_total_score}."
                )
                await _broadcast_progress(
                    batch_id,
                    {
                        "type": "rubric_score_mismatch",
                        "expected_total_score": expected_total_score,
                        "parsed_total_score": parsed_total_score,
                        "message": message,
                    },
                )
                raise ValueError(message)
        except (TypeError, ValueError) as exc:
            logger.warning(f"[rubric_parse] Expected total score check skipped: {exc}")

    try:
        await _broadcast_progress(
            batch_id,
            {
                "type": "rubric_parsed",
                "totalQuestions": parsed_rubric.get("total_questions", 0),
                "totalScore": parsed_rubric.get("total_score", 0),
                "generalNotes": parsed_rubric.get("general_notes", ""),
                "rubricFormat": parsed_rubric.get("rubric_format", ""),
                "overallParseConfidence": parsed_rubric.get("overall_parse_confidence", 1.0),
                "parseConfession": parsed_rubric.get("parse_confession"),
                "questions": [
                    {
                        "questionId": q.get("question_id", ""),
                        "maxScore": q.get("max_score", 0),
                        "questionText": q.get("question_text", ""),
                        "standardAnswer": q.get("standard_answer", ""),
                        "gradingNotes": q.get("grading_notes", ""),
                        "sourcePages": q.get("source_pages") or q.get("sourcePages") or [],
                        "parseConfidence": q.get("parse_confidence", 1.0),
                        "parseUncertainties": q.get("parse_uncertainties")
                        or q.get("parseUncertainties")
                        or [],
                        "parseQualityIssues": q.get("parse_quality_issues")
                        or q.get("parseQualityIssues")
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
                                "deduction": dr.get("deduction", dr.get("score", 0)),
                                "conditions": dr.get("conditions") or dr.get("when") or "",
                            }
                            for idx, dr in enumerate(
                                q.get("deduction_rules") or q.get("deductionRules") or []
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
                    for q in parsed_rubric.get("questions", [])
                ],
            },
        )
    except Exception as exc:
        logger.warning(f"[rubric_parse] failed to emit rubric_parsed: {exc}")

    # 注意：不序列化 RubricRegistry，因为 grade_batch_node 会从 parsed_rubric 重建
    # 这样可以避免类型转换问题

    # 🔧 修复：显式传递图片数据，防止在 state 传递中丢失（大批量图片场景）
    result = {
        "parsed_rubric": parsed_rubric,
        "current_stage": "rubric_parse_completed",
        "percentage": 15.0,
        "timestamps": {
            **state.get("timestamps", {}),
            "rubric_parse_at": datetime.now().isoformat(),
        },
    }
    
    # 确保图片数据不丢失
    if state.get("processed_images"):
        result["processed_images"] = state.get("processed_images")
    if state.get("answer_images"):
        result["answer_images"] = state.get("answer_images")
    if state.get("student_boundaries"):
        result["student_boundaries"] = state.get("student_boundaries")
    
    return result


def _preserve_images_in_result(state: BatchGradingGraphState, result: Dict[str, Any]) -> Dict[str, Any]:
    """确保图片数据在节点返回时不丢失（修复大批量图片场景）"""
    if state.get("processed_images"):
        result["processed_images"] = state.get("processed_images")
    if state.get("answer_images"):
        result["answer_images"] = state.get("answer_images")
    if state.get("student_boundaries"):
        result["student_boundaries"] = state.get("student_boundaries")
    return result


async def rubric_self_review_node(state: BatchGradingGraphState) -> Dict[str, Any]:
    """
    评分标准自动复核节点（基于自白的 LLM 复核）
    
    在人工复核之前，基于 LLM 生成的 confession（自白）和原图，
    自动调用 LLM 复核并修正解析结果中的风险点和不确定项。
    
    触发条件：
    - confession 中有 needs_review 项
    - confession 中有 risks 或 uncertainties
    - 整体置信度 < 0.9
    """
    batch_id = state["batch_id"]
    parsed_rubric = state.get("parsed_rubric", {})
    rubric_images = state.get("rubric_images", [])
    api_key = state.get("api_key") or os.getenv("LLM_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    
    # 获取 confession
    confession = parsed_rubric.get("confession", {})
    overall_confidence = confession.get("confidence", 1.0)
    needs_review = confession.get("needsReview") or confession.get("needs_review") or []
    risks = confession.get("risks", [])
    uncertainties = confession.get("uncertainties", [])
    blind_spots = confession.get("blindSpots") or confession.get("blind_spots") or []
    
    # 判断是否需要自动复核
    should_self_review = (
        needs_review or 
        (risks and len(risks) > 0) or 
        (uncertainties and len(uncertainties) > 0) or
        overall_confidence < 0.9
    )
    
    if not should_self_review:
        logger.info(f"[rubric_self_review] skip (no issues): batch_id={batch_id}, confidence={overall_confidence}")
        return _preserve_images_in_result(state, {
            "current_stage": "rubric_self_review_skipped",
            "percentage": 16.0,
            "timestamps": {
                **state.get("timestamps", {}),
                "rubric_self_review_at": datetime.now().isoformat(),
            },
        })
    
    if not api_key or not rubric_images:
        logger.info(f"[rubric_self_review] skip (no api_key or images): batch_id={batch_id}")
        return _preserve_images_in_result(state, {
            "current_stage": "rubric_self_review_skipped",
            "percentage": 16.0,
            "timestamps": {
                **state.get("timestamps", {}),
                "rubric_self_review_at": datetime.now().isoformat(),
            },
        })
    
    logger.info(
        f"[rubric_self_review] 开始自动复核: batch_id={batch_id}, "
        f"risks={len(risks)}, uncertainties={len(uncertainties)}, "
        f"needs_review={len(needs_review)}, confidence={overall_confidence}"
    )
    
    # 广播进度
    await _broadcast_progress(
        batch_id,
        {
            "type": "agent_update",
            "agentId": "rubric-self-review",
            "agentName": "Rubric Self Review",
            "agentLabel": "Rubric Self Review",
            "parentNodeId": "rubric_self_review",
            "status": "running",
            "progress": 0,
            "message": "开始自动复核解析结果...",
        },
    )
    
    try:
        from src.services.llm_reasoning import LLMReasoningClient
        
        client = LLMReasoningClient(api_key=api_key)
        
        # 构建复核提示词
        review_prompt = _build_self_review_prompt(parsed_rubric, confession)
        
        # 流式回调
        async def stream_callback(stream_type: str, chunk: str) -> None:
            await _broadcast_progress(
                batch_id,
                {
                    "type": "llm_stream_chunk",
                    "nodeId": "rubric_self_review",
                    "agentId": "rubric-self-review",
                    "nodeName": "Rubric Self Review",
                    "streamType": stream_type,
                    "chunk": chunk,
                },
            )
        
        # 调用 LLM 进行复核
        response = await client.analyze_with_vision(
            images=rubric_images,
            prompt=review_prompt,
            stream_callback=stream_callback,
        )
        
        result_text = response.get("response", "")
        
        # 解析复核结果
        updated_rubric = _parse_self_review_result(result_text, parsed_rubric)
        
        # 更新 confession 状态
        if updated_rubric.get("confession"):
            updated_rubric["confession"]["self_reviewed"] = True
            updated_rubric["confession"]["self_review_applied"] = True
        
        logger.info(f"[rubric_self_review] 自动复核完成: batch_id={batch_id}")
        
        await _broadcast_progress(
            batch_id,
            {
                "type": "agent_update",
                "agentId": "rubric-self-review",
                "agentName": "Rubric Self Review",
                "agentLabel": "Rubric Self Review",
                "parentNodeId": "rubric_self_review",
                "status": "completed",
                "progress": 100,
                "message": "自动复核完成",
            },
        )
        
        # 广播复核结果
        await _broadcast_progress(
            batch_id,
            {
                "type": "rubric_self_reviewed",
                "batch_id": batch_id,
                "changes_made": updated_rubric.get("self_review_changes", []),
                "confidence_before": overall_confidence,
                "confidence_after": updated_rubric.get("confession", {}).get("confidence", overall_confidence),
            },
        )
        
        return _preserve_images_in_result(state, {
            "parsed_rubric": updated_rubric,
            "current_stage": "rubric_self_review_completed",
            "percentage": 17.0,
            "timestamps": {
                **state.get("timestamps", {}),
                "rubric_self_review_at": datetime.now().isoformat(),
            },
        })
        
    except Exception as e:
        logger.warning(f"[rubric_self_review] 自动复核失败: {e}", exc_info=True)
        await _broadcast_progress(
            batch_id,
            {
                "type": "agent_update",
                "agentId": "rubric-self-review",
                "agentName": "Rubric Self Review",
                "agentLabel": "Rubric Self Review",
                "parentNodeId": "rubric_self_review",
                "status": "failed",
                "progress": 100,
                "message": f"自动复核失败: {str(e)}",
            },
        )
        # 失败时不阻塞流程，继续使用原有的 parsed_rubric
        return _preserve_images_in_result(state, {
            "current_stage": "rubric_self_review_failed",
            "percentage": 17.0,
            "timestamps": {
                **state.get("timestamps", {}),
                "rubric_self_review_at": datetime.now().isoformat(),
            },
        })


def _build_self_review_prompt(parsed_rubric: Dict[str, Any], confession: Dict[str, Any]) -> str:
    """构建自动复核的提示词"""
    risks = confession.get("risks", [])
    uncertainties = confession.get("uncertainties", [])
    blind_spots = confession.get("blindSpots") or confession.get("blind_spots") or []
    needs_review = confession.get("needsReview") or confession.get("needs_review") or []
    
    # 收集题目级别的风险
    question_issues = []
    for q in parsed_rubric.get("questions", []):
        q_conf = q.get("confession", {})
        if q_conf.get("risk") or q_conf.get("uncertainty"):
            question_issues.append({
                "question_id": q.get("question_id"),
                "risk": q_conf.get("risk", ""),
                "uncertainty": q_conf.get("uncertainty", ""),
            })
    
    prompt = f"""你是一位专业的评分标准复核专家。请根据以下自白（confession）信息，重新审视原图并修正解析结果。

## 当前解析结果摘要
- 总题数: {parsed_rubric.get('total_questions', 0)}
- 总分: {parsed_rubric.get('total_score', 0)}
- 置信度: {confession.get('confidence', 1.0):.2f}

## 自白信息（需要复核的问题）
"""
    
    if risks:
        prompt += f"\n### 风险点\n"
        for r in risks:
            prompt += f"- {r}\n"
    
    if uncertainties:
        prompt += f"\n### 不确定点\n"
        for u in uncertainties:
            prompt += f"- {u}\n"
    
    if blind_spots:
        prompt += f"\n### 可能遗漏\n"
        for b in blind_spots:
            prompt += f"- {b}\n"
    
    if needs_review:
        prompt += f"\n### 建议复核\n"
        for n in needs_review:
            prompt += f"- {n}\n"
    
    if question_issues:
        prompt += f"\n### 题目级问题\n"
        for qi in question_issues:
            prompt += f"- Q{qi['question_id']}: "
            if qi['risk']:
                prompt += f"风险={qi['risk']} "
            if qi['uncertainty']:
                prompt += f"不确定={qi['uncertainty']}"
            prompt += "\n"
    
    prompt += """
## 当前解析的题目结构
"""
    for q in parsed_rubric.get("questions", []):
        prompt += f"\n### 题目 {q.get('question_id')} (满分 {q.get('max_score')} 分)\n"
        prompt += f"得分点: {len(q.get('scoring_points', []))} 个\n"
        for sp in q.get("scoring_points", []):
            prompt += f"  - [{sp.get('point_id')}] {sp.get('description')} ({sp.get('score')}分)\n"
    
    prompt += """
## 任务
请仔细查看原图，针对上述自白中的问题进行复核：
1. 确认或修正题目数量
2. 确认或修正各题分值
3. 确认或修正得分点
4. 补充可能遗漏的内容

## 输出格式（仅返回 JSON，不要 markdown 代码块）
如果需要修正，返回：
{{
  "has_changes": true,
  "changes": ["修正1的描述", "修正2的描述"],
  "updated_confidence": 0.95,
  "corrections": [
    {{
      "question_id": "修正的题目ID",
      "field": "max_score|scoring_points|standard_answer",
      "old_value": "原值",
      "new_value": "新值",
      "reason": "修正原因"
    }}
  ]
}}

如果确认无需修正，返回：
{{
  "has_changes": false,
  "confirmation": "确认当前解析正确",
  "updated_confidence": 0.95
}}

注意：
- 只修正有明确问题的内容
- 不要过度修正或猜测
- 修正后的置信度应该提高"""
    
    return prompt


def _parse_self_review_result(result_text: str, original_rubric: Dict[str, Any]) -> Dict[str, Any]:
    """解析自动复核结果"""
    import json
    
    updated_rubric = copy.deepcopy(original_rubric)
    
    try:
        # 提取 JSON
        json_text = result_text
        if "```json" in result_text:
            json_start = result_text.find("```json") + 7
            json_end = result_text.find("```", json_start)
            if json_end > json_start:
                json_text = result_text[json_start:json_end].strip()
        elif "```" in result_text:
            json_start = result_text.find("```") + 3
            json_end = result_text.find("```", json_start)
            if json_end > json_start:
                json_text = result_text[json_start:json_end].strip()
        
        if not json_text.startswith("{"):
            brace_start = json_text.find("{")
            if brace_start >= 0:
                json_text = json_text[brace_start:]
        
        data = json.loads(json_text)
        
        if data.get("has_changes"):
            # 记录修正
            updated_rubric["self_review_changes"] = data.get("changes", [])
            
            # 应用修正
            corrections = data.get("corrections", [])
            for correction in corrections:
                qid = correction.get("question_id")
                field = correction.get("field")
                new_value = correction.get("new_value")
                
                if not qid or not field or new_value is None:
                    continue
                
                # 找到对应题目
                for q in updated_rubric.get("questions", []):
                    if q.get("question_id") == qid or q.get("id") == qid:
                        if field == "max_score":
                            try:
                                q["max_score"] = float(new_value)
                            except (ValueError, TypeError):
                                pass
                        elif field == "standard_answer":
                            q["standard_answer"] = str(new_value)
                        elif field == "scoring_points" and isinstance(new_value, list):
                            # 更新得分点（更复杂的逻辑）
                            q["scoring_points"] = new_value
                        break
            
            # 更新置信度
            if "updated_confidence" in data:
                if "confession" not in updated_rubric:
                    updated_rubric["confession"] = {}
                updated_rubric["confession"]["confidence"] = float(data["updated_confidence"])
            
            # 重新计算总分
            updated_rubric["total_score"] = sum(
                q.get("max_score", 0) for q in updated_rubric.get("questions", [])
            )
            
            logger.info(f"[rubric_self_review] 应用了 {len(corrections)} 个修正")
        else:
            # 无修正，但可能更新置信度
            updated_rubric["self_review_changes"] = []
            if "updated_confidence" in data:
                if "confession" not in updated_rubric:
                    updated_rubric["confession"] = {}
                updated_rubric["confession"]["confidence"] = float(data["updated_confidence"])
            logger.info("[rubric_self_review] 确认解析正确，无需修正")
            
    except json.JSONDecodeError as e:
        logger.warning(f"[rubric_self_review] 无法解析复核结果 JSON: {e}")
        updated_rubric["self_review_changes"] = []
    except Exception as e:
        logger.warning(f"[rubric_self_review] 处理复核结果失败: {e}")
        updated_rubric["self_review_changes"] = []
    
    return updated_rubric


async def rubric_review_node(state: BatchGradingGraphState) -> Dict[str, Any]:
    """
    Rubric review node with interrupt.
    """
    batch_id = state["batch_id"]
    parsed_rubric = state.get("parsed_rubric", {})
    api_key = state.get("api_key") or os.getenv("LLM_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    enable_review = state.get("inputs", {}).get("enable_review", True)
    grading_mode = _resolve_grading_mode(state.get("inputs", {}), parsed_rubric)

    if grading_mode.startswith("assist"):
        logger.info(f"[rubric_review] skip (assist mode): batch_id={batch_id}")
        return _preserve_images_in_result(state, {
            "current_stage": "rubric_review_skipped",
            "percentage": 18.0,
            "timestamps": {
                **state.get("timestamps", {}),
                "rubric_review_at": datetime.now().isoformat(),
            },
        })

    if not parsed_rubric or not parsed_rubric.get("questions"):
        logger.info(f"[rubric_review] skip (no rubric): batch_id={batch_id}")
        return _preserve_images_in_result(state, {
            "current_stage": "rubric_review_skipped",
            "percentage": 18.0,
            "timestamps": {
                **state.get("timestamps", {}),
                "rubric_review_at": datetime.now().isoformat(),
            },
        })

    if not enable_review:
        logger.info(f"[rubric_review] skip (review disabled): batch_id={batch_id}")
        return _preserve_images_in_result(state, {
            "current_stage": "rubric_review_skipped",
            "percentage": 18.0,
            "timestamps": {
                **state.get("timestamps", {}),
                "rubric_review_at": datetime.now().isoformat(),
            },
        })

    review_request = {
        "type": "rubric_review_required",
        "batch_id": batch_id,
        "message": "Rubric review required",
        "requested_at": datetime.now().isoformat(),
        "parsed_rubric": parsed_rubric,
    }
    review_response = interrupt(review_request)

    action = (review_response or {}).get("action", "approve").lower()
    updated_rubric = parsed_rubric

    if action in ("update", "override"):
        updated_payload = (review_response or {}).get("parsed_rubric") or {}
        updated_rubric = _normalize_parsed_rubric_input(updated_payload, parsed_rubric)
    elif action == "reparse":
        selected_ids = (review_response or {}).get("selected_question_ids") or []
        notes = (review_response or {}).get("notes") or ""
        if selected_ids and api_key:
            try:
                from src.services.rubric_parser import RubricParserService

                parser = RubricParserService(api_key=api_key)
                selected_questions = [
                    q
                    for q in parsed_rubric.get("questions", [])
                    if q.get("question_id") in selected_ids or q.get("id") in selected_ids
                ]
                revised = await parser.revise_questions(selected_questions, notes=notes)
                revised_map = {
                    (q.get("question_id") or q.get("id")): q for q in revised if isinstance(q, dict)
                }
                updated_questions = []
                for q in parsed_rubric.get("questions", []):
                    qid = q.get("question_id") or q.get("id")
                    if qid in revised_map:
                        normalized = _normalize_parsed_rubric_input(
                            {
                                "questions": [revised_map[qid]],
                            },
                            parsed_rubric,
                        )
                        if normalized.get("questions"):
                            updated_questions.append(normalized["questions"][0])
                            continue
                    updated_questions.append(q)
                updated_rubric = {
                    **parsed_rubric,
                    "questions": updated_questions,
                }
            except Exception as exc:
                logger.warning(f"[rubric_review] reparse failed: {exc}", exc_info=True)

    if updated_rubric.get("questions"):
        updated_rubric["total_questions"] = len(updated_rubric["questions"])
        updated_rubric["total_score"] = sum(
            q.get("max_score", 0) for q in updated_rubric["questions"]
        )
        updated_rubric["rubric_context"] = _format_rubric_context_from_dict(updated_rubric)

    return _preserve_images_in_result(state, {
        "parsed_rubric": updated_rubric,
        "rubric_review_result": review_response,
        "current_stage": "rubric_review_completed",
        "percentage": 20.0,
        "timestamps": {
            **state.get("timestamps", {}),
            "rubric_review_at": datetime.now().isoformat(),
        },
    })


def grading_fanout_router(state: BatchGradingGraphState) -> List[Send]:
    """
    批改扇出路由

    将所有页面分批，每批并行批改。
    不预先分割学生，而是批改所有页面。
    支持可配置的批次大小。

    **关键**: 使用深拷贝确保 Worker 之间不共享可变状态 (Requirement 3.2)

    Requirements: 3.1, 3.2, 10.1
    """
    import copy

    batch_id = state["batch_id"]
    inputs = state.get("inputs", {})
    rubric = state.get("rubric", "")
    parsed_rubric = state.get("parsed_rubric", {})
    api_key = state.get("api_key", "")
    student_boundaries = state.get("student_boundaries")
    
    # 🔧 修复：从多个来源获取图片，并添加详细日志诊断大批量图片丢失问题
    processed_images = state.get("processed_images") or []
    answer_images = state.get("answer_images") or []
    
    # 优先使用 processed_images（已预处理），fallback 到 answer_images（原始）
    images_to_use = processed_images if processed_images else answer_images
    
    logger.info(
        f"[grading_fanout] 图片来源诊断: batch_id={batch_id}, "
        f"processed_images={len(processed_images)}, answer_images={len(answer_images)}, "
        f"state_keys={list(state.keys())}"
    )
    
    if not student_boundaries:
        student_boundaries = _build_student_boundaries(state, len(images_to_use))
        if student_boundaries:
            logger.info(f"[grading_fanout] 生成 {len(student_boundaries)} 个学生边界")

    if not images_to_use:
        logger.warning(f"[grading_fanout] ⚠️ state 中没有图片，尝试恢复: batch_id={batch_id}")
        logger.debug(f"[grading_fanout] 🔍 诊断: state keys={sorted(list(state.keys()))}")
        logger.debug(f"[grading_fanout] 🔍 inputs keys={sorted(list(inputs.keys())) if inputs else 'None'}")
        
        # 1. 先尝试从 inputs 中恢复
        input_answer_images = inputs.get("answer_images") or []
        if input_answer_images:
            logger.info(f"[grading_fanout] ✅ 从 inputs 恢复 {len(input_answer_images)} 张图片")
            images_to_use = input_answer_images
        else:
            # 2. 尝试从 PostgreSQL 读取（最后一道防线）
            pg_reader = _get_pg_image_reader()
            if pg_reader:
                try:
                    # 在同步上下文中运行异步函数
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # 如果已有事件循环，创建新任务
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(asyncio.run, pg_reader(batch_id, "answer"))
                            pg_images = future.result(timeout=60)
                    else:
                        pg_images = loop.run_until_complete(pg_reader(batch_id, "answer"))
                    
                    if pg_images:
                        logger.info(f"[grading_fanout] ✅ 从 PostgreSQL 恢复 {len(pg_images)} 张图片")
                        # 转换为 base64 格式（与 answer_images 格式一致）
                        import base64
                        images_to_use = [
                            f"data:image/jpeg;base64,{base64.b64encode(img).decode('utf-8')}"
                            for img in pg_images
                        ]
                except Exception as e:
                    logger.error(f"[grading_fanout] ❌ PostgreSQL 读取图片失败: {e}")
            
            if not images_to_use:
                logger.error(f"[grading_fanout] ❌ 无法恢复图片，跳过批改直接进入 confession")
                return [Send("logic_review", state)]
    
    # 更新变量名以保持后续代码兼容
    processed_images = images_to_use

    # 不再从 page_index_contexts 推导 student_boundaries
    # 如果前端没有提供 student_mapping，则按批次大小分配

    # 获取批次配置 (Requirements: 3.1, 10.1)
    config = get_batch_config()
    max_retries = config.max_retries
    total_pages = len(processed_images)

    # 🔥 优先按学生边界动态分配批次
    if student_boundaries and len(student_boundaries) > 0:
        num_batches = len(student_boundaries)
        logger.info(
            f"[grading_fanout] 按学生边界创建批改任务: batch_id={batch_id}, "
            f"学生数={num_batches}, 总页数={total_pages}"
        )

        sends = []
        for batch_idx, boundary in enumerate(student_boundaries):
            student_key = boundary.get("student_key", f"student_{batch_idx}")
            student_name = boundary.get("student_name")
            student_id = boundary.get("student_id")
            pages = boundary.get("pages")
            if pages:
                page_indices = sorted(list(pages))
            else:
                start_page = boundary.get("start_page", 0)
                end_page = boundary.get("end_page", total_pages - 1)
                page_indices = list(range(start_page, end_page + 1))
            if page_indices:
                start_page = page_indices[0]
                end_page = page_indices[-1]
            else:
                start_page = 0
                end_page = 0

            batch_images = [processed_images[i] for i in page_indices if i < len(processed_images)]

            if not batch_images:
                logger.warning(f"[grading_fanout] 学生 {student_key} 没有图像，跳过")
                continue

            task_state = {
                "batch_id": batch_id,
                "batch_index": batch_idx,
                "total_batches": num_batches,
                "student_key": student_key,
                "student_name": student_name,
                "student_id": student_id,
                "page_indices": page_indices,
                "images": batch_images,
                "rubric": rubric,
                "parsed_rubric": copy.deepcopy(parsed_rubric),
                "api_key": api_key,
                "retry_count": 0,
                "max_retries": max_retries,
                "inputs": copy.deepcopy(inputs),
            }

            sends.append(Send("grade_batch", task_state))
            logger.info(
                f"[grading_fanout] 创建学生批次: student={student_key}, pages={start_page}-{end_page}"
            )

        if sends:
            logger.info(f"[grading_fanout] ✅ 成功创建 {len(sends)} 个学生批改任务")
            return sends
        logger.warning(f"[grading_fanout] ⚠️ 没有有效的学生批次")
        logger.warning(f"[grading_fanout] 🔍 student_boundaries={student_boundaries}")

    # 回退：按固定批次大小分配
    batch_size = config.batch_size
    if batch_size <= 0:
        batch_size = max(1, total_pages)
    num_batches = (total_pages + batch_size - 1) // batch_size

    logger.info(
        f"[grading_fanout] 创建批改任务: batch_id={batch_id}, "
        f"总页数={total_pages}, 批次数={num_batches}, "
        f"批次大小={batch_size}, 最大重试={max_retries}"
    )

    sends = []
    for batch_idx in range(num_batches):
        start_idx = batch_idx * batch_size
        end_idx = min(start_idx + batch_size, total_pages)
        batch_images = processed_images[start_idx:end_idx]

        # 🔧 修复：为回退逻辑添加默认 student_key（修复 total_students=0 问题）
        # 当没有 student_mapping 时，创建一个默认学生覆盖所有页面
        if num_batches == 1:
            # 只有一个批次，视为单个学生
            default_student_key = "学生1"
        else:
            # 多个批次，为每个批次分配一个学生编号
            default_student_key = f"学生{batch_idx + 1}"

        task_state = {
            "batch_id": batch_id,
            "batch_index": batch_idx,
            "total_batches": num_batches,
            "student_key": default_student_key,  # ✅ 添加 student_key
            "page_indices": list(range(start_idx, end_idx)),
            "images": batch_images,
            "rubric": rubric,
            "parsed_rubric": copy.deepcopy(parsed_rubric),
            "api_key": api_key,
            "retry_count": 0,
            "max_retries": max_retries,
            "inputs": copy.deepcopy(inputs),
        }

        logger.info(
            f"[grading_fanout] 回退批次: batch={batch_idx+1}/{num_batches}, "
            f"student_key={default_student_key}, pages={start_idx}-{end_idx-1}"
        )

        sends.append(Send("grade_batch", task_state))

    return sends


def _normalize_question_id(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    for token in ["第", "题目", "题", "Q", "q"]:
        text = text.replace(token, "")
    return text.strip().rstrip(".:：")


def _normalize_logic_review_items(raw_items: Any) -> List[Dict[str, Any]]:
    """
    标准化逻辑复核返回的题目列表。
    
    处理各种可能的字段名变体（驼峰/下划线）和数据结构。
    
    Args:
        raw_items: 原始的题目复核数据（可能是列表或其他格式）
    
    Returns:
        标准化后的题目字典列表
    """
    if not raw_items:
        return []
    
    # 如果不是列表，尝试转换
    if not isinstance(raw_items, list):
        if isinstance(raw_items, dict):
            # 可能是单个题目，包装成列表
            raw_items = [raw_items]
        else:
            return []
    
    normalized = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        
        # 标准化字段名（统一使用下划线命名）
        normalized_item = {}
        
        # question_id / questionId
        qid = item.get("question_id") or item.get("questionId")
        if qid:
            normalized_item["question_id"] = qid
        
        # confidence
        if "confidence" in item:
            normalized_item["confidence"] = item["confidence"]
        
        # confidence_reason / confidenceReason
        conf_reason = item.get("confidence_reason") or item.get("confidenceReason")
        if conf_reason:
            normalized_item["confidence_reason"] = conf_reason
        
        # review_summary / reviewSummary
        review_summary = item.get("review_summary") or item.get("reviewSummary")
        if review_summary:
            normalized_item["review_summary"] = review_summary
        
        # review_corrections / reviewCorrections
        corrections = item.get("review_corrections") or item.get("reviewCorrections")
        if corrections:
            normalized_item["review_corrections"] = corrections
        
        # self_critique / selfCritique
        self_critique = item.get("self_critique") or item.get("selfCritique")
        if self_critique:
            normalized_item["self_critique"] = self_critique
        
        # self_critique_confidence / selfCritiqueConfidence
        self_conf = item.get("self_critique_confidence") or item.get("selfCritiqueConfidence")
        if self_conf:
            normalized_item["self_critique_confidence"] = self_conf
        
        # 保留其他所有字段
        for key, value in item.items():
            if key not in normalized_item:
                normalized_item[key] = value
        
        normalized.append(normalized_item)
    
    return normalized


def _normalize_logic_review_self_audit(raw_audit: Any) -> Optional[Dict[str, Any]]:
    """
    标准化逻辑复核返回的 self_audit 数据。
    
    处理各种可能的字段名变体（驼峰/下划线）和数据结构。
    
    Args:
        raw_audit: 原始的 self_audit 数据
    
    Returns:
        标准化后的 self_audit 字典，如果输入无效则返回 None
    """
    if not raw_audit or not isinstance(raw_audit, dict):
        return None
    
    normalized = {}
    
    # summary
    summary = raw_audit.get("summary")
    if summary:
        normalized["summary"] = summary
    
    # confidence
    confidence = raw_audit.get("confidence")
    if confidence is not None:
        normalized["confidence"] = _safe_float(confidence, 0.0)
    
    # issues
    issues = raw_audit.get("issues")
    if issues and isinstance(issues, list):
        normalized["issues"] = issues
    
    # compliance_analysis / complianceAnalysis
    compliance = raw_audit.get("compliance_analysis") or raw_audit.get("complianceAnalysis")
    if compliance and isinstance(compliance, list):
        normalized["compliance_analysis"] = compliance
    
    # uncertainties_and_conflicts / uncertaintiesAndConflicts
    uncertainties = raw_audit.get("uncertainties_and_conflicts") or raw_audit.get(
        "uncertaintiesAndConflicts"
    )
    if uncertainties and isinstance(uncertainties, list):
        normalized["uncertainties_and_conflicts"] = uncertainties
    
    # overall_compliance_grade / overallComplianceGrade
    grade = raw_audit.get("overall_compliance_grade") or raw_audit.get("overallComplianceGrade")
    if grade is not None:
        normalized["overall_compliance_grade"] = grade
    
    # honesty_note / honestyNote
    honesty = raw_audit.get("honesty_note") or raw_audit.get("honestyNote")
    if honesty:
        normalized["honesty_note"] = honesty
    
    # 保留其他所有字段
    for key, value in raw_audit.items():
        if key not in normalized:
            normalized[key] = value
    
    return normalized if normalized else None


def _build_logic_review_summary(question_details: List[Dict[str, Any]]) -> str:
    """
    构建逻辑复核摘要。
    
    基于题目详情生成一个简短的摘要，说明复核结果。
    
    Args:
        question_details: 题目详情列表
    
    Returns:
        复核摘要字符串
    """
    if not question_details:
        return "No questions to review"
    
    total_questions = len(question_details)
    total_score = sum(_safe_float(q.get("score", 0), 0.0) for q in question_details)
    max_score = sum(_safe_float(q.get("max_score", 0), 0.0) for q in question_details)
    
    # 统计低置信度题目
    low_confidence_count = sum(
        1 for q in question_details 
        if _safe_float(q.get("confidence", 1.0), 1.0) < 0.7
    )
    
    # 统计有修正的题目
    corrected_count = sum(
        1 for q in question_details 
        if q.get("review_corrections") and len(q.get("review_corrections", [])) > 0
    )
    
    # 构建摘要
    parts = [f"Reviewed {total_questions} question(s)"]
    
    if max_score > 0:
        percentage = (total_score / max_score) * 100
        parts.append(f"score {total_score:.1f}/{max_score:.1f} ({percentage:.0f}%)")
    
    if corrected_count > 0:
        parts.append(f"{corrected_count} correction(s)")
    
    if low_confidence_count > 0:
        parts.append(f"{low_confidence_count} low confidence")
    
    return ", ".join(parts)


def _estimate_page_max_score(
    parsed_rubric: Optional[Dict[str, Any]],
    page_context: Optional[Dict[str, Any]],
) -> float:
    if not parsed_rubric or not page_context:
        return 0.0
    if page_context.get("is_cover_page"):
        return 0.0
    question_numbers = page_context.get("question_numbers") or []
    if not question_numbers:
        return 0.0
    normalized = {_normalize_question_id(qnum) for qnum in question_numbers if qnum is not None}
    normalized = {qid for qid in normalized if qid}
    if not normalized:
        return 0.0
    total = 0.0
    for question in parsed_rubric.get("questions", []):
        qid = _normalize_question_id(question.get("question_id") or question.get("id"))
        if not qid or qid not in normalized:
            continue
        try:
            total += float(question.get("max_score", 0) or 0)
        except (TypeError, ValueError):
            continue
    return total


def _is_placeholder_evidence(text: Optional[str]) -> bool:
    if not text:
        return True
    content = text.strip()
    if not content:
        return True
    placeholders = [
        "未找到",
        "未识别",
        "不清晰",
        "无法辨认",
        "N/A",
        "null",
        "None",
        "【原文引用】未找到",
    ]
    return any(p in content for p in placeholders)


def _trim_text(value: Any, max_len: int) -> str:
    if value is None:
        return ""
    text = str(value)
    if max_len <= 0:
        return ""
    if len(text) <= max_len:
        return text
    if max_len <= 3:
        return text[:max_len]
    return text[: max_len - 3].rstrip() + "..."


def _normalize_scoring_point_results(
    raw_points: Any,
    question_id: str,
) -> List[Dict[str, Any]]:
    if not isinstance(raw_points, list):
        return []
    qid = _normalize_question_id(question_id) or str(question_id or "").strip()
    normalized = []
    for idx, spr in enumerate(raw_points, 1):
        if not isinstance(spr, dict):
            continue
        scoring_point = spr.get("scoring_point") or spr.get("scoringPoint") or {}
        point_id = (
            spr.get("point_id")
            or spr.get("pointId")
            or scoring_point.get("point_id")
            or f"{qid}.{idx}"
        )
        description = scoring_point.get("description") or spr.get("description") or ""
        rubric_reference = spr.get("rubric_reference") or spr.get("rubricReference") or ""
        rubric_reference_source = spr.get("rubric_reference_source") or spr.get(
            "rubricReferenceSource"
        )
        if not rubric_reference:
            rubric_reference = f"[{point_id}] {description}".strip()
            rubric_reference_source = "system"
        max_points = (
            spr.get("max_points")
            or spr.get("maxPoints")
            or spr.get("max_score")
            or spr.get("maxScore")
            or scoring_point.get("score")
            or 0
        )
        normalized.append(
            {
                **spr,
                "point_id": point_id,
                "rubric_reference": rubric_reference,
                "rubric_reference_source": rubric_reference_source,
                "max_points": max_points,
            }
        )
    return normalized


def _trim_list(items: Any, max_items: int) -> List[Any]:
    if items is None:
        return []
    if isinstance(items, list):
        values = items
    elif isinstance(items, tuple):
        values = list(items)
    else:
        values = [items]
    if max_items <= 0:
        return []
    return values[:max_items]


def _compact_evidence(evidence: Dict[str, Any], limits: Dict[str, int]) -> Dict[str, Any]:
    if not isinstance(evidence, dict):
        return evidence
    max_qnums = limits.get("max_question_numbers", 6)
    qnums = evidence.get("question_numbers")
    if isinstance(qnums, list):
        evidence["question_numbers"] = qnums[:max_qnums]
    evidence["page_summary"] = _trim_text(
        evidence.get("page_summary", ""),
        limits.get("max_page_summary_chars", 100),
    )
    answers = evidence.get("answers")
    if isinstance(answers, list):
        for answer in answers:
            if not isinstance(answer, dict):
                continue
            answer["answer_text"] = _trim_text(
                answer.get("answer_text", ""),
                limits.get("max_answer_chars", 160),
            )
            snippets = answer.get("evidence_snippets", [])
            snippets = _trim_list(snippets, limits.get("max_snippets", 1))
            answer["evidence_snippets"] = [
                _trim_text(snippet, limits.get("max_snippet_chars", 90))
                for snippet in snippets
                if snippet
            ]
            flags = answer.get("uncertainty_flags", [])
            answer["uncertainty_flags"] = _trim_list(
                flags,
                limits.get("max_uncertainty_flags", 3),
            )
    return evidence


def _compact_score_result(result: Dict[str, Any], limits: Dict[str, int]) -> Dict[str, Any]:
    if not isinstance(result, dict):
        return result
    result["page_summary"] = _trim_text(
        result.get("page_summary", ""),
        limits.get("max_page_summary_chars", 100),
    )
    q_details = result.get("question_details")
    if isinstance(q_details, list):
        for q in q_details:
            if not isinstance(q, dict):
                continue
            q["feedback"] = _trim_text(
                q.get("feedback", ""),
                limits.get("max_feedback_chars", 120),
            )
            q["student_answer"] = _trim_text(
                q.get("student_answer", ""),
                limits.get("max_student_answer_chars", 120),
            )
            typo_notes = q.get("typo_notes") or q.get("typoNotes") or []
            typo_notes = _trim_list(typo_notes, limits.get("max_typo_notes", 3))
            q["typo_notes"] = [
                _trim_text(note, limits.get("max_typo_chars", 24)) for note in typo_notes if note
            ]
            sprs = q.get("scoring_point_results") or q.get("scoring_results") or []
            if isinstance(sprs, list):
                for spr in sprs:
                    if not isinstance(spr, dict):
                        continue
                    spr["evidence"] = _trim_text(
                        spr.get("evidence", ""),
                        limits.get("max_evidence_chars", 90),
                    )
                    spr["reason"] = _trim_text(
                        spr.get("reason", ""),
                        limits.get("max_reason_chars", 120),
                    )
                    spr["decision"] = _trim_text(
                        spr.get("decision", ""),
                        limits.get("max_decision_chars", 24),
                    )
    return result


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _is_choice_question(question_text: str, standard_answer: str) -> bool:
    text = _normalize_text(question_text)
    answer = _normalize_text(standard_answer)
    if not text and not answer:
        return False
    text_no_space = re.sub(r"\s+", "", text)
    if re.search(r"[A-D][\\.、．]", text_no_space):
        return True
    if any(token in text for token in ["选择题", "单选", "多选", "选项", "请选择", "下列"]):
        return True
    if answer:
        answer_clean = re.sub(r"\s+", "", answer.upper())
        if re.fullmatch(r"[A-D](?:[、,/， ]*[A-D]){0,3}", answer_clean):
            return True
    return False


def _infer_question_type(question: Dict[str, Any]) -> str:
    raw_type = question.get("question_type") or question.get("questionType") or ""
    raw_type = str(raw_type).strip().lower()
    if raw_type:
        return raw_type

    question_text = _normalize_text(
        question.get("question_text") or question.get("questionText") or ""
    )
    grading_notes = _normalize_text(
        question.get("grading_notes") or question.get("gradingNotes") or ""
    )
    standard_answer = _normalize_text(
        question.get("standard_answer") or question.get("standardAnswer") or ""
    )
    alternative_solutions = (
        question.get("alternative_solutions") or question.get("alternativeSolutions") or []
    )

    if _is_choice_question(question_text, standard_answer):
        return "choice"

    text_blob = f"{question_text} {grading_notes}".lower()
    subjective_keywords = [
        "简答",
        "论述",
        "证明",
        "推导",
        "解释",
        "分析",
        "讨论",
        "设计",
        "说明",
        "过程",
        "步骤",
        "应用",
        "实验",
    ]
    objective_keywords = [
        "判断",
        "填空",
        "对错",
        "是非",
        "true",
        "false",
        "√",
        "×",
    ]

    if alternative_solutions:
        return "subjective"
    if any(token.lower() in text_blob for token in subjective_keywords):
        return "subjective"
    if any(token.lower() in text_blob for token in objective_keywords):
        return "objective"

    if standard_answer:
        answer_clean = re.sub(r"\s+", "", standard_answer)
        # 注意: 在字符类中 - 需要放在末尾避免被解释为范围
        if len(answer_clean) <= 4 and re.fullmatch(r"[0-9A-Za-z+.=()（）/\\-]+", answer_clean):
            return "objective"
        if len(standard_answer) > 30 or "\n" in standard_answer:
            return "subjective"

    return "objective"


def _resolve_grading_mode(
    inputs: Optional[Dict[str, Any]],
    parsed_rubric: Optional[Dict[str, Any]],
) -> str:
    raw_mode = (inputs or {}).get("grading_mode") or (inputs or {}).get("gradingMode") or ""
    mode = str(raw_mode).strip().lower()
    mode_map = {
        "standard": "standard",
        "auto": "auto",
        "assist_teacher": "assist_teacher",
        "teacher_assist": "assist_teacher",
        "assistant_teacher": "assist_teacher",
        "assist_student": "assist_student",
        "student_assist": "assist_student",
        "assistant_student": "assist_student",
        "teacher": "assist_teacher",
        "student": "assist_student",
    }
    resolved = mode_map.get(mode, "auto" if not mode else "standard")
    has_rubric = bool((parsed_rubric or {}).get("questions"))
    if resolved == "auto":
        return "standard" if has_rubric else "assist_teacher"
    if resolved.startswith("assist"):
        return resolved
    return "standard"


def _build_rubric_question_map(parsed_rubric: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    question_map: Dict[str, Dict[str, Any]] = {}
    for q in parsed_rubric.get("questions", []):
        qid = _normalize_question_id(q.get("question_id") or q.get("id"))
        if not qid:
            continue
        question_type = _infer_question_type(q)
        scoring_points = []
        for idx, sp in enumerate(q.get("scoring_points", [])):
            point_id = sp.get("point_id") or sp.get("pointId") or f"{qid}.{idx + 1}"
            scoring_points.append(
                {
                    "point_id": point_id,
                    "description": sp.get("description", ""),
                    "score": sp.get("score", 0),
                    "is_required": sp.get("is_required", True),
                    "expected_value": sp.get("expected_value") or sp.get("expectedValue") or "",
                    "keywords": sp.get("keywords") or [],
                }
            )
        alternative_solutions = []
        for alt in q.get("alternative_solutions") or q.get("alternativeSolutions") or []:
            if not isinstance(alt, dict):
                continue
            alternative_solutions.append(
                {
                    "description": alt.get("description", ""),
                    "scoring_criteria": alt.get("scoring_criteria")
                    or alt.get("scoringCriteria")
                    or alt.get("scoring_conditions")
                    or alt.get("scoringConditions")
                    or "",
                    "max_score": alt.get("max_score", alt.get("maxScore", q.get("max_score", 0))),
                }
            )
        question_map[qid] = {
            "question_id": qid,
            "max_score": q.get("max_score", 0),
            "question_text": q.get("question_text", ""),
            "question_type": question_type,
            "is_choice": question_type == "choice",
            "standard_answer": q.get("standard_answer", ""),
            "grading_notes": q.get("grading_notes", ""),
            "scoring_points": scoring_points,
            "deduction_rules": q.get("deduction_rules") or q.get("deductionRules") or [],
            "alternative_solutions": alternative_solutions,
        }
    return question_map


def _normalize_parsed_rubric_input(
    raw_rubric: Dict[str, Any],
    fallback: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    fallback = fallback or {}
    raw_questions = raw_rubric.get("questions") or []
    normalized_questions = []

    for q in raw_questions:
        qid = q.get("question_id") or q.get("questionId") or q.get("id") or ""
        max_score = q.get("max_score", q.get("maxScore"))
        question_text = q.get("question_text") or q.get("questionText") or ""
        standard_answer = q.get("standard_answer") or q.get("standardAnswer") or ""
        question_type = q.get("question_type") or q.get("questionType") or ""
        grading_notes = q.get("grading_notes") or q.get("gradingNotes") or ""
        source_pages = q.get("source_pages") or q.get("sourcePages") or []
        if not isinstance(source_pages, list):
            source_pages = []

        scoring_points_raw = q.get("scoring_points") or q.get("scoringPoints") or []
        scoring_points = []
        for idx, sp in enumerate(scoring_points_raw):
            if isinstance(sp, dict):
                point_id = sp.get("point_id") or sp.get("pointId") or f"{qid}.{idx + 1}"
                keywords = sp.get("keywords") or []
                if isinstance(keywords, str):
                    keywords = [keywords]
                scoring_points.append(
                    {
                        "point_id": point_id,
                        "description": sp.get("description", ""),
                        "score": float(sp.get("score", sp.get("maxScore", 0)) or 0),
                        "is_required": sp.get("is_required", sp.get("isRequired", True)),
                        "keywords": keywords,
                        "expected_value": sp.get("expected_value") or sp.get("expectedValue") or "",
                    }
                )
            elif isinstance(sp, str):
                scoring_points.append(
                    {
                        "point_id": f"{qid}.{idx + 1}",
                        "description": sp,
                        "score": 0,
                        "is_required": True,
                        "keywords": [],
                        "expected_value": "",
                    }
                )

        if max_score is None:
            max_score = sum(sp.get("score", 0) for sp in scoring_points)
        max_score = float(max_score or 0)

        alternative_solutions_raw = (
            q.get("alternative_solutions") or q.get("alternativeSolutions") or []
        )
        alternative_solutions = []
        for alt in alternative_solutions_raw:
            if isinstance(alt, dict):
                alternative_solutions.append(
                    {
                        "description": alt.get("description", ""),
                        "scoring_criteria": alt.get("scoring_criteria")
                        or alt.get("scoringCriteria")
                        or "",
                        "note": alt.get("note", ""),
                    }
                )
            elif isinstance(alt, str):
                alternative_solutions.append(
                    {
                        "description": alt,
                        "scoring_criteria": "",
                        "note": "",
                    }
                )

        deduction_rules_raw = q.get("deduction_rules") or q.get("deductionRules") or []
        deduction_rules = []
        for idx, dr in enumerate(deduction_rules_raw):
            if isinstance(dr, dict):
                deduction_rules.append(
                    {
                        "rule_id": dr.get("rule_id") or dr.get("ruleId") or f"{qid}.d{idx + 1}",
                        "description": dr.get("description", ""),
                        "deduction": float(dr.get("deduction", dr.get("score", 0)) or 0),
                        "conditions": dr.get("conditions") or dr.get("when") or "",
                    }
                )
            elif isinstance(dr, str):
                deduction_rules.append(
                    {
                        "rule_id": f"{qid}.d{idx + 1}",
                        "description": dr,
                        "deduction": 0.0,
                        "conditions": "",
                    }
                )

        criteria = q.get("criteria")
        if not criteria:
            criteria = [sp.get("description", "") for sp in scoring_points]

        normalized_questions.append(
            {
                "id": qid,
                "question_id": qid,
                "max_score": max_score,
                "question_text": question_text,
                "question_type": question_type,
                "standard_answer": standard_answer,
                "criteria": criteria,
                "scoring_points": scoring_points,
                "alternative_solutions": alternative_solutions,
                "deduction_rules": deduction_rules,
                "grading_notes": grading_notes,
                "source_pages": source_pages,
            }
        )

    total_score = raw_rubric.get("total_score") or raw_rubric.get("totalScore")
    if total_score is None:
        total_score = sum(q.get("max_score", 0) for q in normalized_questions)

    return {
        "total_questions": int(
            raw_rubric.get("total_questions")
            or raw_rubric.get("totalQuestions")
            or len(normalized_questions)
        ),
        "total_score": float(total_score or 0),
        "rubric_format": raw_rubric.get("rubric_format")
        or raw_rubric.get("rubricFormat")
        or fallback.get("rubric_format", "standard"),
        "general_notes": raw_rubric.get("general_notes")
        or raw_rubric.get("generalNotes")
        or fallback.get("general_notes", ""),
        "questions": normalized_questions,
        "rubric_context": raw_rubric.get("rubric_context") or fallback.get("rubric_context"),
        "raw_text": raw_rubric.get("raw_text") or fallback.get("raw_text"),
    }


def _format_rubric_context_from_dict(parsed_rubric: Dict[str, Any]) -> str:
    def ensure_str(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, list):
            return " ".join(str(item) for item in value)
        return str(value)

    lines = [
        "=" * 60,
        "RUBRIC SUMMARY",
        "=" * 60,
        f"Questions: {parsed_rubric.get('total_questions', 0)}",
        f"Total Score: {parsed_rubric.get('total_score', 0)}",
        f"Format: {ensure_str(parsed_rubric.get('rubric_format', 'standard'))}",
        "",
    ]

    general_notes = ensure_str(parsed_rubric.get("general_notes", ""))
    if general_notes:
        lines.append(f"General Notes: {general_notes}")
        lines.append("")

    for q in parsed_rubric.get("questions", []):
        lines.append("-" * 40)
        question_id = ensure_str(q.get("question_id", ""))
        lines.append(f"Question {question_id} max_score: {q.get('max_score', 0)}")

        question_text = ensure_str(q.get("question_text", ""))
        if question_text:
            preview = question_text[:100] if len(question_text) > 100 else question_text
            lines.append(f"Question text: {preview}")

        standard_answer = ensure_str(q.get("standard_answer", ""))
        if standard_answer:
            preview = standard_answer[:200] if len(standard_answer) > 200 else standard_answer
            lines.append(f"Standard answer: {preview}")

        scoring_points = q.get("scoring_points", [])
        if scoring_points:
            lines.append("Scoring points:")
            for idx, sp in enumerate(scoring_points, 1):
                required = "required" if sp.get("is_required", True) else "optional"
                keywords = sp.get("keywords") or []
                keywords_str = f" keywords:{keywords}" if keywords else ""
                expected_value = ensure_str(sp.get("expected_value", ""))
                expected_value_str = f" expected:{expected_value}" if expected_value else ""
                point_id = sp.get("point_id") or sp.get("pointId") or f"{question_id}.{idx}"
                lines.append(
                    f"  [{point_id}] {sp.get('score', 0)}?/{required} - "
                    f"{ensure_str(sp.get('description', ''))}{keywords_str}{expected_value_str}"
                )

        deduction_rules = q.get("deduction_rules") or q.get("deductionRules") or []
        if deduction_rules:
            lines.append("Deduction rules:")
            for idx, dr in enumerate(deduction_rules, 1):
                rule_id = dr.get("rule_id") or dr.get("ruleId") or f"{question_id}.d{idx}"
                deduction = dr.get("deduction", dr.get("score", 0))
                conditions = ensure_str(dr.get("conditions") or dr.get("when") or "")
                condition_text = f" conditions:{conditions}" if conditions else ""
                lines.append(
                    f"  [{rule_id}] -{deduction} {ensure_str(dr.get('description', ''))}{condition_text}"
                )

        alternative_solutions = q.get("alternative_solutions", [])
        if alternative_solutions:
            lines.append("Alternative solutions:")
            for alt in alternative_solutions:
                lines.append(f"  - {ensure_str(alt.get('description', ''))}")
                lines.append(f"    criteria: {ensure_str(alt.get('scoring_criteria', ''))}")

        grading_notes = ensure_str(q.get("grading_notes", ""))
        if grading_notes:
            lines.append(f"Notes: {grading_notes}")

        lines.append("")

    return "\n".join(lines)


def _finalize_scoring_result(
    raw_result: Dict[str, Any],
    evidence: Dict[str, Any],
    rubric_map: Dict[str, Dict[str, Any]],
    page_index: int,
) -> Dict[str, Any]:
    raw_questions = raw_result.get("question_details") or []
    raw_by_id = {}
    for q in raw_questions:
        qid = _normalize_question_id(q.get("question_id"))
        if qid:
            raw_by_id[qid] = q

    answer_map = {}
    for answer in evidence.get("answers", []):
        qid = _normalize_question_id(answer.get("question_id"))
        if qid:
            answer_map[qid] = answer

    question_ids = list(answer_map.keys())
    if not question_ids:
        question_ids = [
            _normalize_question_id(q.get("question_id"))
            for q in raw_questions
            if q.get("question_id")
        ]
    if not question_ids:
        question_ids = list(rubric_map.keys())
    seen = set()
    question_ids = [qid for qid in question_ids if qid and not (qid in seen or seen.add(qid))]

    question_details = []
    for qid in question_ids:
        rubric = rubric_map.get(qid, {})
        expected_points = rubric.get("scoring_points", [])
        raw_question = raw_by_id.get(qid, {})
        question_type = rubric.get("question_type") or (
            _infer_question_type(rubric) if rubric else ""
        )
        if not question_type:
            question_type = (
                raw_question.get("question_type") or raw_question.get("questionType") or ""
            )
        is_choice = bool(rubric.get("is_choice") or question_type == "choice")
        raw_scoring = (
            raw_question.get("scoring_point_results") or raw_question.get("scoring_results") or []
        )
        answer_info = answer_map.get(qid, {}) if isinstance(answer_map, dict) else {}
        evidence_snippets = answer_info.get("evidence_snippets") or []
        fallback_snippet = ""
        if isinstance(evidence_snippets, list) and evidence_snippets:
            fallback_snippet = _trim_text(evidence_snippets[0], 90)
        raw_scoring_by_id = {
            _normalize_question_id(spr.get("point_id") or spr.get("pointId")): spr
            for spr in raw_scoring
            if spr.get("point_id") or spr.get("pointId")
        }

        scoring_point_results = []
        review_corrections = []
        missing_points = 0
        missing_evidence = 0
        for idx, sp in enumerate(expected_points):
            point_id = _normalize_question_id(sp.get("point_id")) or f"{qid}.{idx + 1}"
            existing = raw_scoring_by_id.get(point_id, {})
            awarded = existing.get("awarded", existing.get("score", 0))
            max_points = sp.get("score", existing.get("max_points", 0))
            if awarded is None:
                awarded = 0
            if max_points is None:
                max_points = 0
            if awarded > max_points:
                review_corrections.append(
                    {
                        "point_id": point_id,
                        "review_reason": "Score exceeds max; capped to max.",
                    }
                )
                awarded = max_points
            if awarded < 0:
                review_corrections.append(
                    {
                        "point_id": point_id,
                        "review_reason": "Score below zero; clamped to 0.",
                    }
                )
                awarded = 0

            evidence_text = existing.get("evidence")
            if _is_placeholder_evidence(evidence_text):
                missing_evidence += 1
                if fallback_snippet:
                    evidence_text = f"【原文引用】{fallback_snippet}"
                elif not evidence_text:
                    evidence_text = "【原文引用】未找到"
            if not existing:
                missing_points += 1
                review_corrections.append(
                    {
                        "point_id": point_id,
                        "review_reason": "Missing scoring point; added with 0 score.",
                    }
                )

            description = sp.get("description", "")
            expected_value = sp.get("expected_value") or sp.get("expectedValue") or ""
            
            # 🔧 强化 rubric_reference 生成逻辑
            # 优先使用评分标准中的描述，确保 Logic Review 能获取到完整信息
            rubric_reference = f"[{point_id}] {description}".strip()
            if expected_value:
                rubric_reference = f"{rubric_reference}（标准值:{expected_value}）"
            
            # 如果 description 为空，尝试从 rubric_map 中获取
            if not description and rubric:
                for rubric_sp in rubric.get("scoring_points", []):
                    if rubric_sp.get("point_id") == point_id:
                        rubric_desc = rubric_sp.get("description", "")
                        if rubric_desc:
                            rubric_reference = f"[{point_id}] {rubric_desc}".strip()
                            if expected_value:
                                rubric_reference = f"{rubric_reference}（标准值:{expected_value}）"
                        break

            scoring_point_results.append(
                {
                    "point_id": point_id,
                    "rubric_reference": rubric_reference,
                    "rubric_reference_source": "system",
                    "decision": "得分" if awarded > 0 else "未得分",
                    "awarded": awarded,
                    "max_points": max_points,
                    "evidence": evidence_text,
                    "reason": existing.get("reason", ""),
                    "scoring_point": {
                        "description": sp.get("description", ""),
                        "score": max_points,
                        "is_required": sp.get("is_required", True),
                    },
                }
            )
            
            # 🔍 诊断日志：检查 rubric_reference 是否为空
            if not rubric_reference or rubric_reference == f"[{point_id}]":
                logger.warning(
                    f"[grading] ⚠️ rubric_reference 为空或不完整: "
                    f"qid={qid}, point_id={point_id}, description={description}, "
                    f"rubric_reference={rubric_reference}"
                )

        if not scoring_point_results and raw_scoring:
            for idx, spr in enumerate(raw_scoring, 1):
                point_id = spr.get("point_id") or spr.get("pointId") or f"{qid}.{idx}"
                scoring_point = spr.get("scoring_point") or spr.get("scoringPoint") or {}
                description = scoring_point.get("description") or spr.get("description") or ""
                rubric_reference = spr.get("rubric_reference") or spr.get("rubricReference") or ""
                rubric_reference_source = spr.get("rubric_reference_source") or spr.get(
                    "rubricReferenceSource"
                )
                
                # 🔧 强化 rubric_reference 生成逻辑
                if not rubric_reference:
                    rubric_reference = f"[{point_id}] {description}".strip()
                    rubric_reference_source = "system"
                    
                    # 如果 description 为空，尝试从 rubric_map 中获取
                    if not description and rubric:
                        for rubric_sp in rubric.get("scoring_points", []):
                            if rubric_sp.get("point_id") == point_id:
                                rubric_desc = rubric_sp.get("description", "")
                                if rubric_desc:
                                    rubric_reference = f"[{point_id}] {rubric_desc}".strip()
                                break
                
                max_points = spr.get("max_points", spr.get("maxScore"))
                if max_points is None:
                    max_points = scoring_point.get("score", 0)
                scoring_point_results.append(
                    {
                        "point_id": point_id,
                        "rubric_reference": rubric_reference,
                        "rubric_reference_source": rubric_reference_source,
                        "decision": spr.get("decision") or spr.get("result") or "",
                        "awarded": spr.get("awarded", spr.get("score", 0)),
                        "max_points": max_points or 0,
                        "evidence": spr.get("evidence", ""),
                        "reason": spr.get("reason", ""),
                        "scoring_point": scoring_point if scoring_point else None,
                    }
                )

        sum_awarded = sum(r.get("awarded", 0) for r in scoring_point_results)
        max_score = rubric.get("max_score", raw_question.get("max_score", 0))
        if not max_score:
            max_score = sum(r.get("max_points", 0) for r in scoring_point_results)
        score = raw_question.get("score")
        score_adjusted = False
        if score is None:
            score = sum_awarded
        if abs(sum_awarded - score) > 0.25:
            score = sum_awarded
            score_adjusted = True
        if score > max_score:
            score = max_score
            score_adjusted = True
        if score_adjusted:
            review_corrections.append(
                {
                    "point_id": qid,
                    "review_reason": "Total mismatch; recalculated from point scores.",
                }
            )

        typo_notes = raw_question.get("typo_notes") or raw_question.get("typoNotes") or []
        if isinstance(typo_notes, str):
            typo_notes = [typo_notes]
        if not isinstance(typo_notes, list):
            typo_notes = []

        total_points = (
            max(1, len(expected_points)) if expected_points else max(1, len(scoring_point_results))
        )
        coverage = min(1.0, len(scoring_point_results) / total_points)
        evidence_ok = min(1.0, (total_points - missing_evidence) / total_points)
        consistency = 1.0 if not score_adjusted else 0.6
        confidence = 0.2 + coverage * 0.5 + evidence_ok * 0.2 + consistency * 0.1
        answer_confidence = answer_map.get(qid, {}).get("confidence")
        if isinstance(answer_confidence, (int, float)):
            confidence = max(0.0, min(1.0, confidence * max(0.4, min(1.0, answer_confidence))))
        used_alt = bool(
            raw_question.get("used_alternative_solution")
            or raw_question.get("usedAlternativeSolution")
            or raw_question.get("alternative_solution_ref")
            or raw_question.get("alternativeSolutionRef")
        )
        confidence_multiplier = 1.0
        if question_type in ("subjective", "essay", "stepwise"):
            confidence_multiplier *= 0.85
        if used_alt or rubric.get("alternative_solutions"):
            confidence_multiplier *= 0.9
        confidence = max(0.0, min(1.0, confidence * confidence_multiplier))

        rubric_ref_coverage = 1.0
        if scoring_point_results:
            rubric_ref_coverage = sum(
                1 for spr in scoring_point_results if spr.get("rubric_reference")
            ) / max(1, len(scoring_point_results))
            if rubric_ref_coverage < 1.0:
                confidence = max(0.0, min(1.0, confidence * (0.6 + 0.4 * rubric_ref_coverage)))

        issues = []
        if missing_points:
            issues.append(f"Scoring coverage incomplete (missing {missing_points} points)")
        if missing_evidence:
            issues.append("Insufficient evidence for some points")
        if score_adjusted:
            issues.append("Point sum mismatched; adjusted total")

        missing_rubric_ref = any(not spr.get("rubric_reference") for spr in scoring_point_results)
        missing_point_id = any(not spr.get("point_id") for spr in scoring_point_results)
        if missing_rubric_ref:
            issues.append("Missing rubric reference for some points")
        if missing_point_id:
            issues.append("Missing point_id for some points")

        audit_flags = []
        if missing_points:
            audit_flags.append("missing_scoring_points")
        if missing_evidence:
            audit_flags.append("missing_evidence")
        if score_adjusted:
            audit_flags.append("score_adjusted")
        if missing_rubric_ref:
            audit_flags.append("missing_rubric_reference")
        if missing_point_id:
            audit_flags.append("missing_point_id")

        review_summary = "; ".join(issues) if issues else "Logic consistent; no obvious issues"

        confidence_reason = (
            f"coverage={coverage:.2f}, evidence={evidence_ok:.2f}, consistency={consistency:.2f}"
        )
        if question_type:
            confidence_reason = f"{confidence_reason}, type={question_type}"
        if used_alt or rubric.get("alternative_solutions"):
            confidence_reason = f"{confidence_reason}, alt_solution=1"
        confidence_reason = f"{confidence_reason}, rubric_refs={rubric_ref_coverage:.2f}"

        feedback = raw_question.get("feedback", "")
        self_critique = raw_question.get("self_critique") or review_summary
        if is_choice:
            feedback = ""
            self_critique = ""

        question_details.append(
            {
                "question_id": qid,
                "score": score,
                "max_score": max_score,
                "confidence": confidence,
                "confidence_reason": confidence_reason,
                "feedback": feedback,
                "student_answer": raw_question.get("student_answer")
                or answer_map.get(qid, {}).get("answer_text", ""),
                "self_critique": self_critique,
                "self_critique_confidence": raw_question.get(
                    "self_critique_confidence", confidence
                ),
                "typo_notes": typo_notes,
                "rubric_refs": [
                    spr.get("rubric_reference")
                    for spr in scoring_point_results
                    if spr.get("rubric_reference")
                ],
                "scoring_point_results": scoring_point_results,
                "review_summary": review_summary,
                "review_corrections": review_corrections,
                "audit_flags": audit_flags,
                "page_indices": [page_index],
                "is_correct": max_score > 0 and score >= max_score,
                "question_type": question_type,
                "used_alternative_solution": used_alt,
                "alternative_solution_ref": raw_question.get("alternative_solution_ref")
                or raw_question.get("alternativeSolutionRef")
                or "",
            }
        )

    page_confidence = (
        sum(q.get("confidence", 0) for q in question_details) / len(question_details)
        if question_details
        else 0.0
    )
    return {
        "question_details": question_details,
        "score": sum(q.get("score", 0) for q in question_details),
        "max_score": sum(q.get("max_score", 0) for q in question_details),
        "page_confidence": page_confidence,
    }


def _finalize_assist_result(
    raw_result: Dict[str, Any],
    evidence: Dict[str, Any],
    page_index: int,
    grading_mode: str,
) -> Dict[str, Any]:
    raw_questions = raw_result.get("question_details") or []
    raw_by_id = {}
    for q in raw_questions:
        qid = _normalize_question_id(q.get("question_id"))
        if qid:
            raw_by_id[qid] = q

    answer_map = {}
    for answer in evidence.get("answers", []):
        qid = _normalize_question_id(answer.get("question_id"))
        if qid:
            answer_map[qid] = answer

    question_ids = list(answer_map.keys())
    if not question_ids:
        question_ids = [
            _normalize_question_id(q.get("question_id"))
            for q in raw_questions
            if q.get("question_id")
        ]
    seen = set()
    question_ids = [qid for qid in question_ids if qid and not (qid in seen or seen.add(qid))]

    question_details = []
    for qid in question_ids:
        raw_question = raw_by_id.get(qid, {})
        answer_info = answer_map.get(qid, {}) if isinstance(answer_map, dict) else {}
        feedback = raw_question.get("feedback", "")
        if not feedback:
            feedback = raw_question.get("explanation") or raw_question.get("analysis") or ""
        if not feedback:
            hints = raw_question.get("error_hints") or raw_question.get("errorHints") or []
            if isinstance(hints, list) and hints:
                feedback = "；".join([str(h).strip() for h in hints if h])
        confidence = raw_question.get("confidence", 0.4)
        if not isinstance(confidence, (int, float)):
            confidence = 0.4
        question_type = (
            raw_question.get("question_type") or raw_question.get("questionType") or "unknown"
        )

        question_details.append(
            {
                "question_id": qid,
                "score": 0.0,
                "max_score": 0.0,
                "confidence": float(confidence),
                "feedback": feedback,
                "student_answer": raw_question.get("student_answer")
                or answer_info.get("answer_text", ""),
                "self_critique": raw_question.get("self_critique") or "",
                "self_critique_confidence": raw_question.get(
                    "self_critique_confidence", confidence
                ),
                "typo_notes": raw_question.get("typo_notes") or raw_question.get("typoNotes") or [],
                "rubric_refs": [],
                "scoring_point_results": [],
                "review_summary": "",
                "review_corrections": [],
                "audit_flags": ["assist_mode", grading_mode],
                "page_indices": [page_index],
                "is_correct": False,
                "question_type": question_type,
                "grading_mode": grading_mode,
            }
        )

    page_confidence = (
        sum(q.get("confidence", 0) for q in question_details) / len(question_details)
        if question_details
        else 0.0
    )
    return {
        "question_details": question_details,
        "score": 0.0,
        "max_score": 0.0,
        "page_confidence": page_confidence,
    }


async def grade_batch_node(state: Dict[str, Any]) -> Dict[str, Any]:
    return await _grade_batch_node_impl(state)


async def _grade_batch_node_impl(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    批量批改节点

    批改一批页面，返回每页的批改结果。

    **核心流程**:
    1. 从 parsed_rubric 重建 RubricRegistry
    2. 创建 GradingSkills 实例
    3. 批改时识别题目编号
    4. 使用 GradingSkills.get_rubric_for_question 获取该题目的评分标准
    5. 基于指定评分标准进行批改

    特性：
    - Worker 独立性：每个 Worker 独立获取评分标准，不共享可变状态 (Req 3.2)
    - Agent Skill 集成：使用 GradingSkills 动态获取题目评分标准 (Req 5.1)
    - 批次失败重试：单批次失败不影响其他批次，支持重试 (Req 3.3, 9.3)
    - 进度报告：实时报告批次处理进度 (Req 3.4)
    - 错误隔离：单页失败不影响其他页面，记录错误并继续处理 (Req 9.2)

    Requirements: 3.2, 3.3, 3.4, 5.1, 9.2, 9.3
    """
    batch_id = state["batch_id"]
    batch_index = state["batch_index"]
    total_batches = state["total_batches"]
    page_indices = state["page_indices"]
    images = state["images"]
    rubric = state.get("rubric", "")
    page_index_contexts = state.get("page_index_contexts", {})
    api_key = state.get("api_key") or os.getenv("LLM_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 2)
    batch_student_key = state.get("student_key") or f"Student {batch_index + 1}"
    batch_student_name = state.get("student_name")
    batch_student_id = state.get("student_id")

    logger.info(
        f"[grade_batch] 开始批改批次 {batch_index + 1}/{total_batches}: "
        f"batch_id={batch_id}, 页面={page_indices}, 重试次数={retry_count}"
    )

    page_results = []
    batch_error = None
    output_limits = {
        "max_answer_chars": int(os.getenv("GRADING_MAX_ANSWER_CHARS", "160")),
        "max_student_answer_chars": int(os.getenv("GRADING_MAX_STUDENT_ANSWER_CHARS", "4000")),
        "max_snippet_chars": int(os.getenv("GRADING_MAX_SNIPPET_CHARS", "90")),
        "max_snippets": int(os.getenv("GRADING_MAX_SNIPPETS", "1")),
        "max_page_summary_chars": int(os.getenv("GRADING_MAX_PAGE_SUMMARY_CHARS", "100")),
        "max_feedback_chars": int(os.getenv("GRADING_MAX_FEEDBACK_CHARS", "120")),
        "max_evidence_chars": int(os.getenv("GRADING_MAX_EVIDENCE_CHARS", "90")),
        "max_reason_chars": int(os.getenv("GRADING_MAX_REASON_CHARS", "120")),
        "max_decision_chars": int(os.getenv("GRADING_MAX_DECISION_CHARS", "24")),
        "max_typo_notes": int(os.getenv("GRADING_MAX_TYPO_NOTES", "3")),
        "max_typo_chars": int(os.getenv("GRADING_MAX_TYPO_CHARS", "24")),
        "max_question_numbers": int(os.getenv("GRADING_MAX_QUESTION_NUMBERS", "6")),
        "max_uncertainty_flags": int(os.getenv("GRADING_MAX_UNCERTAINTY_FLAGS", "3")),
    }
    second_pass_threshold = float(os.getenv("GRADING_SECOND_PASS_CONFIDENCE", "0.65"))
    second_pass_max_ratio = float(os.getenv("GRADING_SECOND_PASS_MAX_RATIO", "0.2"))
    second_pass_budget_fraction = float(os.getenv("GRADING_SECOND_PASS_BUDGET_FRACTION", "0.25"))
    budget_per_page = float(os.getenv("GRADING_BUDGET_PER_PAGE_USD", "0.01"))
    cost_per_m_input = float(os.getenv("GRADING_COST_PER_M_INPUT_TOKENS", "0.5"))
    cost_per_m_output = float(os.getenv("GRADING_COST_PER_M_OUTPUT_TOKENS", "3.0"))
    strict_est_input_tokens = int(os.getenv("GRADING_STRICT_EST_INPUT_TOKENS", "1200"))
    strict_est_output_tokens = int(os.getenv("GRADING_STRICT_EST_OUTPUT_TOKENS", "600"))
    fast_pass_only = os.getenv("GRADING_FAST_PASS_ONLY", "false").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    max_second_passes = int(len(page_indices) * max(0.0, second_pass_max_ratio))
    if second_pass_max_ratio > 0 and max_second_passes == 0:
        max_second_passes = 1
    second_pass_used = 0
    second_pass_lock = asyncio.Lock()
    est_second_pass_cost = (strict_est_input_tokens / 1_000_000.0) * cost_per_m_input + (
        strict_est_output_tokens / 1_000_000.0
    ) * cost_per_m_output
    budget_allows_second_pass = (
        budget_per_page > 0
        and est_second_pass_cost <= budget_per_page * second_pass_budget_fraction
    )
    grading_mode = _resolve_grading_mode(state.get("inputs", {}), state.get("parsed_rubric", {}))

    try:
        if not api_key:
            raise ValueError("API key 未配置")

        # Worker 独立性保证 (Requirement 3.2)
        # 每个 Worker 独立创建实例，不共享可变状态
        from src.services.llm_reasoning import LLMReasoningClient
        from src.utils.error_handling import execute_with_isolation, get_error_manager
        from src.services.rubric_registry import RubricRegistry

        # 注意：已移除 Agent Skill，直接使用 rubric_registry
        from src.models.grading_models import QuestionRubric, ScoringPoint

        # 独立获取评分标准副本（不共享可变状态）
        parsed_rubric = state.get("parsed_rubric", {})
        import copy

        local_parsed_rubric = copy.deepcopy(parsed_rubric)
        rubric_map = _build_rubric_question_map(local_parsed_rubric)
        grading_mode = _resolve_grading_mode(state.get("inputs", {}), local_parsed_rubric)
        if grading_mode == "assist_student":
            output_limits["max_feedback_chars"] = int(
                os.getenv("GRADING_ASSIST_FEEDBACK_CHARS", "600")
            )
            output_limits["max_page_summary_chars"] = int(
                os.getenv("GRADING_ASSIST_SUMMARY_CHARS", "180")
            )
            output_limits["max_student_answer_chars"] = int(
                os.getenv("GRADING_ASSIST_ANSWER_CHARS", "220")
            )
        logger.info(f"[grade_batch] grading_mode={grading_mode}")

        # 🔍 调试日志：确认 parsed_rubric 内容
        logger.info(
            f"[grade_batch] 接收到 parsed_rubric: "
            f"total_questions={local_parsed_rubric.get('total_questions', 0)}, "
            f"total_score={local_parsed_rubric.get('total_score', 0)}, "
            f"questions_count={len(local_parsed_rubric.get('questions', []))}"
        )

        # 🔥 关键：从 parsed_rubric 重建 RubricRegistry (Requirement 5.1)
        rubric_registry = RubricRegistry(total_score=local_parsed_rubric.get("total_score", 100.0))

        # 将解析的题目注册到 Registry
        questions_data = local_parsed_rubric.get("questions", [])
        if questions_data:
            question_rubrics = []
            for q in questions_data:
                # 构建 ScoringPoint 列表
                qid = q.get("question_id") or q.get("id") or ""
                scoring_points = [
                    ScoringPoint(
                        description=sp.get("description", ""),
                        score=sp.get("score", 0),
                        is_required=sp.get("is_required", True),
                        point_id=sp.get("point_id") or sp.get("pointId") or f"{qid}.{idx + 1}",
                    )
                    for idx, sp in enumerate(q.get("scoring_points", []))
                ]

                # 构建 QuestionRubric
                question_rubric = QuestionRubric(
                    question_id=str(qid),
                    question_text=q.get("question_text", ""),
                    max_score=q.get("max_score", 0),
                    scoring_points=scoring_points,
                    standard_answer=q.get("standard_answer", ""),
                    grading_notes=q.get("grading_notes", ""),
                    alternative_solutions=[],  # 简化处理
                )
                question_rubrics.append(question_rubric)

            rubric_registry.register_rubrics(question_rubrics, log=False)
            logger.info(f"[grade_batch] 已重建 RubricRegistry，注册 {len(question_rubrics)} 道题目")

        # 创建 LLMReasoningClient（已移除 Agent Skill）
        reasoning_client = LLMReasoningClient(
            api_key=api_key,
            rubric_registry=rubric_registry,
        )
        # 错误隔离：单页失败不影响其他页面 (Requirement 9.2)
        error_manager = get_error_manager()

        batch_agent_id = f"batch_{batch_index}"
        batch_student_key = state.get("student_key")
        batch_agent_label = batch_student_key or f"Student Batch {batch_index + 1}"
        total_pages_in_batch = len(page_indices)
        pages_done = 0
        pages_lock = asyncio.Lock()

        async def emit_agent_update(
            status: str,
            message: str = "",
            progress: Optional[int] = None,
        ) -> None:
            payload = {
                "type": "agent_update",
                "parentNodeId": "grade_batch",
                "agentId": batch_agent_id,
                "agentName": batch_agent_label,
                "agentLabel": batch_agent_label,
                "status": status,
                "message": message,
            }
            if progress is not None:
                payload["progress"] = progress
            await _broadcast_progress(batch_id, payload)

        async def emit_stage(message: str) -> None:
            await emit_agent_update("running", message)

        async def mark_page_done(page_idx: int, detail: str) -> None:
            nonlocal pages_done
            async with pages_lock:
                pages_done += 1
                progress = int((pages_done / max(1, total_pages_in_batch)) * 100)
            await emit_agent_update("running", detail, progress=progress)

        await emit_agent_update(
            "running",
            f"Start grading {total_pages_in_batch} pages",
            progress=0,
        )

        async def allow_second_pass() -> bool:
            nonlocal second_pass_used
            async with second_pass_lock:
                if second_pass_used >= max_second_passes:
                    return False
                second_pass_used += 1
                return True

        # 🚀 始终使用 grade_student 一次 LLM call 批改整个学生（避免逐页浪费 token）
        async def stream_callback(stream_type: str, chunk: str) -> None:
            await _broadcast_progress(
                batch_id,
                {
                    "type": "llm_stream_chunk",
                    "nodeId": "grade_batch",
                    "nodeName": "Batch Grading",
                    "agentId": f"batch_{batch_index}",
                    "agentLabel": batch_student_key,
                    "streamType": stream_type,
                    "chunk": chunk,
                },
            )

        await _broadcast_progress(
            batch_id,
            {
                "type": "agent_update",
                "parentNodeId": "grade_batch",
                "agentId": f"batch_{batch_index}",
                "agentName": batch_student_key,
                "agentLabel": batch_student_key,
                "status": "running",
                "message": f"Grading {len(images)} pages...",
                "progress": 10,
            },
        )

        try:
            logger.info(f"[grade_batch] grade_student for {batch_student_key} pages={len(images)}")

            # grade_student - 一次性批改整个学生
            student_result = await reasoning_client.grade_student(
                images=images,
                student_key=batch_student_key,
                parsed_rubric=local_parsed_rubric,
                page_indices=page_indices,
                page_contexts=page_index_contexts,
                stream_callback=stream_callback,
            )

            # Convert to legacy page result format
            if student_result.get("status") == "completed":
                total_score = student_result.get("total_score", 0)
                max_score = student_result.get("max_score", 0)
                question_details = student_result.get("question_details", [])

                page_results.append(
                    {
                        "page_index": page_indices[0] if page_indices else 0,
                        "page_indices": page_indices,
                        "status": "completed",
                        "score": total_score,
                        "max_score": max_score,
                        "confidence": student_result.get("confidence", 0.8),
                        "feedback": student_result.get("overall_feedback", ""),
                        "question_details": question_details,
                        "student_key": batch_student_key,
                        "student_name": batch_student_name,
                        "student_id": batch_student_id,
                        "batch_index": batch_index,
                    }
                )
                
                await emit_agent_update(
                    "completed",
                    f"Grading completed: {total_score}/{max_score}",
                    progress=100,
                )
            else:
                error_msg = student_result.get("error", "Unknown error")
                logger.error(
                    f"[grade_batch] grade_student failed for {batch_student_key}: {error_msg}"
                )
                
                await emit_agent_update(
                    "failed",
                    f"Grading failed: {error_msg}",
                    progress=0,
                )
                
                page_results.append(
                    {
                        "page_index": page_indices[0] if page_indices else 0,
                        "page_indices": page_indices,
                        "status": "failed",
                        "error": error_msg,
                        "student_key": batch_student_key,
                        "student_name": batch_student_name,
                        "student_id": batch_student_id,
                        "batch_index": batch_index,
                    }
                )

        except Exception as exc:
            logger.error(
                f"[grade_batch] Unexpected exception for {batch_student_key}: {exc}",
                exc_info=True
            )
            
            await emit_agent_update(
                "failed",
                f"System error: {str(exc)[:100]}",
                progress=0,
            )
            
            page_results.append(
                {
                    "page_index": page_indices[0] if page_indices else 0,
                    "page_indices": page_indices,
                    "status": "failed",
                    "error": f"System exception: {str(exc)}",
                    "student_key": batch_student_key,
                    "student_name": batch_student_name,
                    "student_id": batch_student_id,
                    "batch_index": batch_index,
                }
            )

    except Exception as e:
        batch_error = str(e)
        logger.error(f"[grade_batch] 批次 {batch_index} 批改失败: {e}", exc_info=True)
        try:
            await emit_agent_update("failed", "Batch failed", progress=100)
        except Exception:
            pass

        # 记录批次级错误
        from src.utils.error_handling import get_error_manager

        error_manager = get_error_manager()
        error_manager.add_error(
            exc=e,
            context={
                "batch_id": batch_id,
                "batch_index": batch_index,
                "function": "grade_batch_node",
                "retry_count": retry_count,
            },
            batch_id=batch_id,
            retry_count=retry_count,
        )

        # 批次失败重试逻辑 (Requirements: 3.3, 9.3)
        if retry_count < max_retries:
            logger.info(
                f"[grade_batch] 批次 {batch_index} 将进行重试 " f"({retry_count + 1}/{max_retries})"
            )
            # 返回重试标记，让调度器重新调度
            return {
                "grading_results": [],
                "batch_retry_needed": {
                    "batch_index": batch_index,
                    "retry_count": retry_count + 1,
                    "error": batch_error,
                },
            }

        # 所有页面标记为失败
        for page_idx in page_indices:
            page_results.append(
                {
                    "page_index": page_idx,
                    "status": "failed",
                    "error": batch_error,
                    "score": 0,
                    "max_score": 0,
                    "batch_index": batch_index,
                    "grading_mode": grading_mode,
                }
            )

    success_count = sum(1 for r in page_results if r["status"] == "completed")
    failed_count = sum(1 for r in page_results if r["status"] == "failed")
    total_score = sum(r.get("score", 0) for r in page_results if r["status"] == "completed")

    # 进度报告 (Requirement 3.4)
    progress_info = {
        "batch_index": batch_index,
        "total_batches": total_batches,
        "pages_processed": success_count,
        "pages_failed": failed_count,
        "total_score": total_score,
        "status": "completed" if failed_count == 0 else "partial",
        "timestamp": datetime.now().isoformat(),
    }

    logger.info(
        f"[grade_batch] 批次 {batch_index + 1}/{total_batches} 完成: "
        f"成功={success_count}/{len(page_results)}, 失败={failed_count}, 总分={total_score}"
    )

    final_status = "completed" if success_count > 0 else "failed"
    await _broadcast_progress(
        batch_id,
        {
            "type": "agent_update",
            "parentNodeId": "grade_batch",
            "agentId": f"batch_{batch_index}",
            "agentName": batch_student_key,
            "agentLabel": batch_student_key,
            "status": final_status,
            "message": f"Completed {success_count}/{len(page_results)} students",
            "progress": 100,
        },
    )

    # ===== 直接构建 student_results 格式（移除 simple_aggregate_node 的需要）=====
    student_results = _build_student_results_from_page_results(
        page_results,
        default_student_key=batch_student_key,
        grading_mode=grading_mode,
    )

    logger.debug(
        f"[grade_batch] Page results summary: total={len(page_results)}, "
        f"success={success_count}, failed={failed_count}"
    )
    logger.debug(f"[grade_batch] Student results count: {len(student_results)}")

    # 🔍 DEBUG: 关键日志 - 记录 grade_batch 返回
    logger.warning(
        f"[grade_batch] 🔍 DEBUG: 准备返回结果, batch_index={batch_index}, "
        f"student_key={batch_student_key}, student_results_count={len(student_results)}, "
        f"page_results_count={len(page_results)}"
    )

    # 返回结果（使用 add reducer 聚合，直接输出 student_results）
    result = {
        "student_results": student_results,
        "grading_results": page_results,  # 保留用于调试/日志
        "batch_progress": progress_info,
    }
    
    logger.warning(f"[grade_batch] 🔍 DEBUG: 返回 result keys={list(result.keys())}")
    return result


def _apply_student_result_overrides(
    student_results: List[Dict[str, Any]],
    overrides: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not overrides:
        return student_results

    overrides_by_key = {}
    for override in overrides:
        key = (
            override.get("studentKey")
            or override.get("student_key")
            or override.get("studentName")
            or override.get("student_name")
        )
        if key:
            overrides_by_key[key] = override

    for student in student_results:
        student_key = (
            student.get("student_key") or student.get("student_id") or student.get("student_name")
        )
        override = overrides_by_key.get(student_key)
        if not override:
            continue

        question_overrides = {}
        for q in override.get("questionResults", []) or override.get("question_results", []):
            qid = _normalize_question_id(q.get("questionId") or q.get("question_id"))
            if qid:
                question_overrides[qid] = q

        if student.get("question_details"):
            for q in student.get("question_details", []):
                qid = _normalize_question_id(q.get("question_id"))
                if not qid or qid not in question_overrides:
                    continue
                update = question_overrides[qid]
                if update.get("score") is not None:
                    q["score"] = float(update.get("score", q.get("score", 0)))
                if update.get("feedback") is not None:
                    q["feedback"] = update.get("feedback", q.get("feedback", ""))

        if student.get("page_results"):
            for page in student.get("page_results", []):
                if not page.get("question_details"):
                    continue
                for q in page.get("question_details", []):
                    qid = _normalize_question_id(q.get("question_id"))
                    if not qid or qid not in question_overrides:
                        continue
                    update = question_overrides[qid]
                    if update.get("score") is not None:
                        q["score"] = float(update.get("score", q.get("score", 0)))
                    if update.get("feedback") is not None:
                        q["feedback"] = update.get("feedback", q.get("feedback", ""))
                page["score"] = sum(q.get("score", 0) for q in page.get("question_details", []))

        if student.get("question_details"):
            student["total_score"] = sum(
                q.get("score", 0) for q in student.get("question_details", [])
            )
        elif student.get("page_results"):
            student["total_score"] = sum(p.get("score", 0) for p in student.get("page_results", []))

    return student_results


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _build_student_results_from_page_results(
    page_results: List[Dict[str, Any]],
    *,
    default_student_key: Optional[str] = None,
    grading_mode: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if not page_results:
        return []

    grouped: Dict[str, Dict[str, Any]] = {}
    for result in page_results:
        student_key = result.get("student_key") or default_student_key or "Student"
        entry = grouped.get(student_key)
        if not entry:
            entry = {
                "student_key": student_key,
                "student_id": None,
                "student_name": None,
                "start_page": None,
                "end_page": None,
                "total_score": 0.0,
                "max_total_score": 0.0,
                "question_details": [],
                "page_results": [],
                "grading_mode": grading_mode,
                "feedback": "",
                "confidence": 0.0,
                "_confidence_sum": 0.0,
                "_confidence_count": 0,
                "_has_completed": False,
                "_has_failed": False,
                "_errors": [],
            }
            grouped[student_key] = entry

        entry["page_results"].append(result)
        if result.get("grading_mode"):
            entry["grading_mode"] = result.get("grading_mode")

        if result.get("student_id") and not entry.get("student_id"):
            entry["student_id"] = result.get("student_id")
        if result.get("student_name") and not entry.get("student_name"):
            entry["student_name"] = result.get("student_name")

        if not entry["feedback"] and result.get("feedback"):
            entry["feedback"] = result.get("feedback")

        if result.get("question_details"):
            entry["question_details"].extend(result.get("question_details", []))

        page_indices = result.get("page_indices")
        if not page_indices:
            page_index = result.get("page_index")
            if page_index is not None:
                page_indices = [page_index]

        if page_indices:
            start_page = min(page_indices)
            end_page = max(page_indices)
            entry["start_page"] = (
                start_page if entry["start_page"] is None else min(entry["start_page"], start_page)
            )
            entry["end_page"] = (
                end_page if entry["end_page"] is None else max(entry["end_page"], end_page)
            )

        entry["total_score"] += _safe_float(result.get("score", 0))
        entry["max_total_score"] += _safe_float(result.get("max_score", 0))

        if result.get("status") == "completed":
            entry["_has_completed"] = True
        if result.get("status") == "failed":
            entry["_has_failed"] = True
            if result.get("error"):
                entry["_errors"].append(result.get("error"))

        confidence = result.get("confidence")
        if confidence is not None:
            entry["_confidence_sum"] += _safe_float(confidence)
            entry["_confidence_count"] += 1

    student_results: List[Dict[str, Any]] = []
    for entry in grouped.values():
        if entry["start_page"] is None:
            entry["start_page"] = 0
        if entry["end_page"] is None:
            entry["end_page"] = entry["start_page"]
        if entry["_confidence_count"]:
            entry["confidence"] = entry["_confidence_sum"] / entry["_confidence_count"]
        if entry["_has_failed"] and not entry["_has_completed"]:
            entry["status"] = "failed"
        elif entry["_has_failed"] and entry["_has_completed"]:
            entry["status"] = "partial"
        if entry["_errors"]:
            entry["error"] = entry["_errors"][0]
        entry.pop("_confidence_sum", None)
        entry.pop("_confidence_count", None)
        entry.pop("_has_completed", None)
        entry.pop("_has_failed", None)
        entry.pop("_errors", None)
        student_results.append(entry)

    return student_results


def _merge_logic_review_fields(
    original_question: Dict[str, Any],
    review_item: Dict[str, Any]
) -> Dict[str, Any]:
    """
    合并逻辑复核结果到原始题目数据。
    
    逻辑复核输出的字段（confidence, review_summary, review_corrections 等）
    会覆盖或补充原始题目的对应字段。
    
    关键：逻辑复核后的 confidence 应该作为最终显示的置信度。
    """
    merged = dict(original_question)
    
    # 1. 更新置信度（逻辑复核决定最终置信度）
    if "confidence" in review_item:
        new_confidence = _safe_float(review_item["confidence"])
        merged["confidence"] = new_confidence
        audit = merged.get("audit") if isinstance(merged.get("audit"), dict) else {}
        audit = dict(audit)
        audit["confidence"] = new_confidence
        audit["updated_at"] = datetime.now().isoformat()
        merged["audit"] = audit
    if "confidence_reason" in review_item:
        merged["confidence_reason"] = review_item["confidence_reason"]
    if "confidenceReason" in review_item:
        merged["confidence_reason"] = review_item["confidenceReason"]
    
    # 2. 更新自我反思相关字段
    if "self_critique" in review_item:
        merged["self_critique"] = review_item["self_critique"]
    if "selfCritique" in review_item:
        merged["self_critique"] = review_item["selfCritique"]
    if "self_critique_confidence" in review_item:
        merged["self_critique_confidence"] = review_item["self_critique_confidence"]
    if "selfCritiqueConfidence" in review_item:
        merged["self_critique_confidence"] = review_item["selfCritiqueConfidence"]
    
    # 3. 更新复核摘要
    if "review_summary" in review_item:
        merged["review_summary"] = review_item["review_summary"]
    if "reviewSummary" in review_item:
        merged["review_summary"] = review_item["reviewSummary"]
    
    # 4. 处理分数修正
    review_corrections = review_item.get("review_corrections") or review_item.get("reviewCorrections") or []
    if review_corrections:
        merged["review_corrections"] = review_corrections
        
        # 应用分数修正到 scoring_point_results
        scoring_results = merged.get("scoring_point_results") or []
        correction_map = {}
        for corr in review_corrections:
            if isinstance(corr, dict):
                point_id = corr.get("point_id") or corr.get("pointId")
                if point_id:
                    correction_map[point_id] = corr
        
        if scoring_results and correction_map:
            updated_scoring = []
            total_score_delta = 0
            for spr in scoring_results:
                point_id = spr.get("point_id") or spr.get("pointId")
                if point_id and point_id in correction_map:
                    corr = correction_map[point_id]
                    original_awarded = _safe_float(spr.get("awarded", 0))
                    corrected_awarded = _safe_float(corr.get("correct_awarded", corr.get("correctAwarded", original_awarded)))
                    
                    updated_spr = dict(spr)
                    updated_spr["awarded"] = corrected_awarded
                    updated_spr["review_adjusted"] = True
                    updated_spr["review_before"] = {
                        "awarded": original_awarded,
                        "decision": spr.get("decision"),
                        "reason": spr.get("reason"),
                        "evidence": spr.get("evidence"),
                    }
                    updated_spr["review_reason"] = corr.get("review_reason") or corr.get("reviewReason") or ""
                    
                    # 更新 decision
                    if corrected_awarded > 0:
                        updated_spr["decision"] = "得分（复核修正）"
                    else:
                        updated_spr["decision"] = "不得分（复核修正）"
                    
                    total_score_delta += corrected_awarded - original_awarded
                    updated_scoring.append(updated_spr)
                else:
                    updated_scoring.append(dict(spr))
            
            merged["scoring_point_results"] = updated_scoring
            
            # 重新计算总分
            if total_score_delta != 0:
                original_score = _safe_float(merged.get("score", 0))
                merged["score"] = max(0, original_score + total_score_delta)
    
    # 5. 更新 honesty_note
    if "honesty_note" in review_item:
        merged["honesty_note"] = review_item["honesty_note"]
    if "honestyNote" in review_item:
        merged["honesty_note"] = review_item["honestyNote"]
    
    # 6. 标记已复核
    merged["logic_reviewed"] = True
    
    return merged


def _recompute_student_totals(student: Dict[str, Any]) -> None:
    total_score = _safe_float(student.get("total_score", 0))
    max_total_score = _safe_float(student.get("max_total_score", 0))

    question_details = student.get("question_details") or []
    if question_details:
        computed_score = sum(_safe_float(q.get("score", 0)) for q in question_details)
        computed_max = sum(
            _safe_float(q.get("max_score", q.get("maxScore", 0))) for q in question_details
        )
        if total_score <= 0 and computed_score > 0:
            student["total_score"] = computed_score
        if max_total_score <= 0 and computed_max > 0:
            student["max_total_score"] = computed_max
        return

    page_results = student.get("page_results") or []
    if page_results:
        computed_score = sum(_safe_float(p.get("score", 0)) for p in page_results)
        computed_max = sum(_safe_float(p.get("max_score", 0)) for p in page_results)
        if total_score <= 0 and computed_score > 0:
            student["total_score"] = computed_score
        if max_total_score <= 0 and computed_max > 0:
            student["max_total_score"] = computed_max


def _resolve_student_key_for_page(
    student_results: List[Dict[str, Any]],
    page_index: int,
) -> str:
    for student in student_results:
        start_page = student.get("start_page")
        end_page = student.get("end_page")
        if start_page is None or end_page is None:
            continue
        if start_page <= page_index <= end_page:
            return (
                student.get("student_key")
                or student.get("student_id")
                or student.get("student_name")
                or ""
            )
    return ""


def _find_question_pages(
    student_results: List[Dict[str, Any]],
    student_key: str,
    question_id: str,
    total_pages: int,
) -> List[int]:
    normalized_qid = _normalize_question_id(question_id)
    for student in student_results:
        key = (
            student.get("student_key")
            or student.get("student_id")
            or student.get("student_name")
            or ""
        )
        if student_key and key != student_key:
            continue
        for question in student.get("question_details", []) or []:
            qid = _normalize_question_id(question.get("question_id") or question.get("questionId"))
            if qid != normalized_qid:
                continue
            pages = _sanitize_pages(
                question.get("page_indices") or question.get("pageIndices") or [],
                total_pages,
            )
            if pages:
                return pages
        for page in student.get("page_results", []) or []:
            page_index = page.get("page_index")
            if page_index is None:
                continue
            for question in page.get("question_details", []) or []:
                qid = _normalize_question_id(
                    question.get("question_id") or question.get("questionId")
                )
                if qid == normalized_qid:
                    return [page_index]
    return []


def _select_best_question_result(
    current: Optional[Dict[str, Any]],
    candidate: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not candidate:
        return current
    if not current:
        return candidate
    current_conf = _safe_float(current.get("confidence", 0))
    candidate_conf = _safe_float(candidate.get("confidence", 0))
    if candidate_conf > current_conf + 1e-6:
        return candidate
    if candidate_conf < current_conf - 1e-6:
        return current
    current_score = _safe_float(current.get("score", 0))
    candidate_score = _safe_float(candidate.get("score", 0))
    if candidate_score > current_score:
        return candidate
    if candidate_score < current_score:
        return current
    current_feedback = current.get("feedback", "") or ""
    candidate_feedback = candidate.get("feedback", "") or ""
    if len(candidate_feedback) > len(current_feedback):
        return candidate
    return current


def _apply_question_result_update(
    question: Dict[str, Any],
    update: Dict[str, Any],
) -> None:
    if update.get("score") is not None:
        question["score"] = _safe_float(update.get("score", question.get("score", 0)))
    if update.get("max_score") is not None:
        question["max_score"] = _safe_float(update.get("max_score", question.get("max_score", 0)))
    if update.get("feedback") is not None:
        question["feedback"] = update.get("feedback", question.get("feedback", ""))
    if update.get("confidence") is not None:
        question["confidence"] = _safe_float(
            update.get("confidence", question.get("confidence", 0))
        )
    scoring_points = update.get("scoring_point_results") or update.get("scoring_results")
    if scoring_points is not None:
        question_id = question.get("question_id") or question.get("questionId") or ""
        question["scoring_point_results"] = _normalize_scoring_point_results(
            scoring_points, question_id
        )
    if update.get("student_answer"):
        question["student_answer"] = update.get(
            "student_answer", question.get("student_answer", "")
        )
    if update.get("page_indices"):
        question["page_indices"] = update.get("page_indices", question.get("page_indices", []))


def _apply_regrade_updates(
    student_results: List[Dict[str, Any]],
    updates_by_student: Dict[str, Dict[str, Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    if not updates_by_student:
        return student_results

    for student in student_results:
        student_key = (
            student.get("student_key")
            or student.get("student_id")
            or student.get("student_name")
            or ""
        )
        question_updates = updates_by_student.get(student_key)
        if not question_updates:
            continue

        if student.get("question_details"):
            for q in student.get("question_details", []):
                qid = _normalize_question_id(q.get("question_id") or q.get("questionId"))
                update = question_updates.get(qid)
                if update:
                    _apply_question_result_update(q, update)

        if student.get("page_results"):
            for page in student.get("page_results", []):
                page_questions = page.get("question_details") or []
                updated = False
                for q in page_questions:
                    qid = _normalize_question_id(q.get("question_id") or q.get("questionId"))
                    update = question_updates.get(qid)
                    if update:
                        _apply_question_result_update(q, update)
                        updated = True
                if updated:
                    page["score"] = sum(q.get("score", 0) for q in page_questions)

        if student.get("question_details"):
            student["total_score"] = sum(
                _safe_float(q.get("score", 0)) for q in student.get("question_details", [])
            )
        elif student.get("page_results"):
            student["total_score"] = sum(
                _safe_float(p.get("score", 0)) for p in student.get("page_results", [])
            )

    return student_results


async def _regrade_selected_questions(
    state: BatchGradingGraphState,
    student_results: List[Dict[str, Any]],
    regrade_items: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not regrade_items:
        return student_results

    api_key = state.get("api_key") or os.getenv("LLM_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        logger.warning("[review] regrade skipped: missing API key")
        return student_results

    processed_images = state.get("processed_images") or state.get("answer_images") or []
    total_pages = len(processed_images)
    if total_pages == 0:
        logger.warning("[review] regrade skipped: missing images")
        return student_results

    parsed_rubric = state.get("parsed_rubric", {})
    questions_data = parsed_rubric.get("questions", []) if isinstance(parsed_rubric, dict) else []

    try:
        from src.services.llm_reasoning import LLMReasoningClient
        from src.services.rubric_registry import RubricRegistry
        from src.models.grading_models import QuestionRubric, ScoringPoint
    except Exception as exc:
        logger.warning(f"[review] regrade skipped: {exc}")
        return student_results

    rubric_registry = RubricRegistry(total_score=parsed_rubric.get("total_score", 100.0))
    question_rubrics = []
    for q in questions_data:
        qid = q.get("question_id") or q.get("id") or ""
        if not qid:
            continue
        scoring_points = [
            ScoringPoint(
                description=sp.get("description", ""),
                score=sp.get("score", 0),
                is_required=sp.get("is_required", True),
                point_id=sp.get("point_id") or sp.get("pointId") or f"{qid}.{idx + 1}",
            )
            for idx, sp in enumerate(q.get("scoring_points", []))
        ]
        question_rubrics.append(
            QuestionRubric(
                question_id=str(qid),
                question_text=q.get("question_text", ""),
                max_score=q.get("max_score", 0),
                scoring_points=scoring_points,
                standard_answer=q.get("standard_answer", ""),
                grading_notes=q.get("grading_notes", ""),
                alternative_solutions=[],
            )
        )
    if question_rubrics:
        rubric_registry.register_rubrics(question_rubrics, log=False)

    reasoning_client = LLMReasoningClient(
        api_key=api_key,
        rubric_registry=rubric_registry,
    )

    student_page_map = state.get("student_page_map") or {}
    resolved_items: List[Dict[str, Any]] = []

    for item in regrade_items:
        if not isinstance(item, dict):
            continue
        question_id = _normalize_question_id(item.get("question_id") or item.get("questionId"))
        if not question_id:
            continue
        student_key = (
            item.get("student_key")
            or item.get("studentKey")
            or item.get("studentName")
            or item.get("student_name")
            or ""
        )
        raw_pages = (
            item.get("page_indices")
            or item.get("pageIndices")
            or item.get("page_index")
            or item.get("pageIndex")
        )
        if raw_pages is not None and not isinstance(raw_pages, (list, tuple)):
            raw_pages = [raw_pages]
        pages = _sanitize_pages(raw_pages, total_pages)
        if not pages:
            pages = _find_question_pages(student_results, student_key, question_id, total_pages)
        if not student_key and pages:
            student_key = student_page_map.get(pages[0]) or _resolve_student_key_for_page(
                student_results, pages[0]
            )
        if not student_key or not pages:
            logger.warning(
                f"[review] regrade skipped item: question={question_id}, student={student_key or 'unknown'}"
            )
            continue
        for page_index in pages:
            resolved_items.append(
                {
                    "student_key": student_key,
                    "question_id": question_id,
                    "page_index": page_index,
                    "notes": item.get("notes") or item.get("note") or "",
                }
            )

    if not resolved_items:
        return student_results

    updates_by_student: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for item in resolved_items:
        page_index = item["page_index"]
        if not (0 <= page_index < total_pages):
            continue
        image = processed_images[page_index]
        try:
            result = await reasoning_client.grade_with_detailed_scoring_points(
                image=image,
                question_id=item["question_id"],
                page_index=page_index,
                reviewer_notes=item.get("notes") or "",
            )
            result_dict = result.to_dict()
            student_key = item["student_key"]
            qid = _normalize_question_id(item["question_id"])
            bucket = updates_by_student.setdefault(student_key, {})
            bucket[qid] = _select_best_question_result(bucket.get(qid), result_dict)
        except Exception as exc:
            logger.warning(
                f"[review] regrade failed: question={item['question_id']} page={page_index} error={exc}"
            )

    return _apply_regrade_updates(student_results, updates_by_student)


def _extract_scoring_points(question: Dict[str, Any]) -> List[Dict[str, Any]]:
    qid = _normalize_question_id(question.get("question_id") or question.get("questionId"))
    raw_points = question.get("scoring_point_results") or question.get("scoring_results") or []
    points: List[Dict[str, Any]] = []
    for spr in raw_points:
        if not isinstance(spr, dict):
            continue
        scoring_point = spr.get("scoring_point") or spr.get("scoringPoint") or {}
        description = (
            scoring_point.get("description")
            or spr.get("description")
            or spr.get("rubric_reference")
            or spr.get("rubricReference")
            or ""
        )
        point_id = spr.get("point_id") or spr.get("pointId") or scoring_point.get("point_id") or ""
        awarded = _safe_float(spr.get("awarded", spr.get("score", 0)))
        max_points = _safe_float(
            spr.get("max_points") or spr.get("maxPoints") or scoring_point.get("score") or 0
        )
        points.append(
            {
                "question_id": qid,
                "point_id": str(point_id) if point_id is not None else "",
                "description": description,
                "score": awarded,
                "max_score": max_points,
                "evidence": spr.get("evidence") or "",
                "rubric_reference": spr.get("rubric_reference") or spr.get("rubricReference") or "",
            }
        )
    return points


def _build_student_summary(student: Dict[str, Any]) -> Dict[str, Any]:
    total_score = _safe_float(student.get("total_score", 0))
    max_total_score = _safe_float(student.get("max_total_score", 0))
    percentage = (total_score / max_total_score * 100) if max_total_score > 0 else 0.0

    knowledge_points: List[Dict[str, Any]] = []
    weak_points: List[Dict[str, Any]] = []

    question_details = student.get("question_details") or []
    for question in question_details:
        for point in _extract_scoring_points(question):
            max_score = point.get("max_score", 0) or 0
            ratio = (point.get("score", 0) / max_score) if max_score > 0 else 0.0
            if ratio >= 0.85:
                mastery = "mastered"
            elif ratio >= 0.6:
                mastery = "partial"
            else:
                mastery = "weak"
            enriched = {
                **point,
                "mastery_level": mastery,
                "ratio": ratio,
            }
            knowledge_points.append(enriched)
            if mastery == "weak":
                weak_points.append(enriched)

    if not knowledge_points:
        for question in question_details:
            qid = _normalize_question_id(question.get("question_id") or question.get("questionId"))
            score = _safe_float(question.get("score", 0))
            max_score = _safe_float(question.get("max_score", 0))
            ratio = (score / max_score) if max_score > 0 else 0.0
            mastery = "partial" if ratio >= 0.6 else "weak"
            knowledge_points.append(
                {
                    "question_id": qid,
                    "point_id": "",
                    "description": question.get("feedback", "") or f"Question {qid}",
                    "score": score,
                    "max_score": max_score,
                    "mastery_level": mastery,
                    "ratio": ratio,
                    "evidence": "",
                    "rubric_reference": "",
                }
            )
            if mastery == "weak":
                weak_points.append(knowledge_points[-1])

    suggestion_candidates = []
    for point in weak_points:
        label = point.get("description") or f"Question {point.get('question_id', '')}"
        if label:
            suggestion_candidates.append(f"建议复习：{label}")
    if not suggestion_candidates:
        for point in knowledge_points:
            if point.get("ratio", 0) < 0.7:
                label = point.get("description") or f"Question {point.get('question_id', '')}"
                if label:
                    suggestion_candidates.append(f"建议复习：{label}")

    improvement_suggestions = []
    seen = set()
    for item in suggestion_candidates:
        if item not in seen:
            improvement_suggestions.append(item)
            seen.add(item)
        if len(improvement_suggestions) >= 5:
            break

    overall_parts = [f"整体得分 {total_score}/{max_total_score}（{percentage:.1f}%）。"]
    if percentage >= 85:
        overall_parts.append("整体表现优秀。")
    elif percentage >= 70:
        overall_parts.append("整体表现良好。")
    elif percentage >= 60:
        overall_parts.append("整体达到及格水平。")
    else:
        overall_parts.append("整体表现需重点提升。")

    if weak_points:
        weak_labels = []
        for point in weak_points[:3]:
            label = point.get("description") or f"Question {point.get('question_id', '')}"
            if label:
                weak_labels.append(label)
        if weak_labels:
            overall_parts.append(f"薄弱点集中在：{'，'.join(weak_labels)}。")
    else:
        overall_parts.append("暂无明显薄弱点。")

    return {
        "overall": " ".join(overall_parts),
        "percentage": percentage,
        "knowledge_points": knowledge_points,
        "improvement_suggestions": improvement_suggestions,
        "generated_at": datetime.now().isoformat(),
    }


def _build_self_audit(student: Dict[str, Any]) -> Dict[str, Any]:
    question_details = student.get("question_details") or []
    issues: List[Dict[str, Any]] = []
    confidence_values: List[float] = []

    for question in question_details:
        qid = _normalize_question_id(question.get("question_id") or question.get("questionId"))
        confidence = _safe_float(question.get("confidence", 0), 0.0)
        if confidence:
            confidence_values.append(confidence)

        if confidence and confidence < 0.7:
            issues.append(
                {
                    "issue_type": "low_confidence",
                    "message": f"题目 {qid} 评分置信度较低",
                    "question_id": qid,
                }
            )

        review_corrections = question.get("review_corrections") or []
        if review_corrections:
            issues.append(
                {
                    "issue_type": "logic_review_adjusted",
                    "message": f"题目 {qid} 存在逻辑复核修正记录",
                    "question_id": qid,
                }
            )

        if not question.get("self_critique"):
            issues.append(
                {
                    "issue_type": "missing_self_critique",
                    "message": f"题目 {qid} 缺少自白说明",
                    "question_id": qid,
                }
            )

        scoring_points = (
            question.get("scoring_point_results") or question.get("scoring_results") or []
        )
        if not scoring_points:
            issues.append(
                {
                    "issue_type": "missing_scoring_points",
                    "message": f"题目 {qid} 缺少评分点明细",
                    "question_id": qid,
                }
            )
        else:
            missing_evidence = False
            missing_rubric_ref = False
            for spr in scoring_points:
                if not isinstance(spr, dict):
                    continue
                evidence = spr.get("evidence")
                if _is_placeholder_evidence(evidence):
                    missing_evidence = True
                rubric_ref = spr.get("rubric_reference") or spr.get("rubricReference")
                if not rubric_ref:
                    missing_rubric_ref = True
            if missing_evidence:
                issues.append(
                    {
                        "issue_type": "missing_evidence",
                        "message": f"题目 {qid} 部分评分点证据不足",
                        "question_id": qid,
                    }
                )
            if missing_rubric_ref and not question.get("rubric_refs"):
                issues.append(
                    {
                        "issue_type": "missing_rubric_ref",
                        "message": f"题目 {qid} 部分评分点缺少标准引用",
                        "question_id": qid,
                    }
                )

        typo_notes = question.get("typo_notes") or question.get("typoNotes") or []
        if typo_notes:
            issues.append(
                {
                    "issue_type": "typo_detected",
                    "message": f"题目 {qid} 发现错别字标注",
                    "question_id": qid,
                }
            )

    issue_types = {issue.get("issue_type") for issue in issues}
    low_confidence_questions = [
        issue.get("question_id")
        for issue in issues
        if issue.get("issue_type") == "low_confidence" and issue.get("question_id")
    ]

    compliance_analysis = [
        {
            "goal": "严格按评分标准给分",
            "tag": (
                "unsure_not_reported" if "missing_rubric_ref" in issue_types else "fully_complied"
            ),
            "notes": (
                "部分评分点缺少标准引用"
                if "missing_rubric_ref" in issue_types
                else "未发现明显偏离评分标准"
            ),
        },
        {
            "goal": "扣分点需有答案证据",
            "tag": "failed_not_reported" if "missing_evidence" in issue_types else "fully_complied",
            "notes": (
                "存在证据不足的评分点" if "missing_evidence" in issue_types else "评分点证据充足"
            ),
        },
        {
            "goal": "不确定性需明确披露",
            "tag": "unsure_not_reported" if "low_confidence" in issue_types else "fully_complied",
            "notes": (
                "存在低置信度题目" if "low_confidence" in issue_types else "未发现明显不确定性"
            ),
        },
    ]

    uncertainties_and_conflicts = []
    if low_confidence_questions:
        uncertainties_and_conflicts.append(
            {
                "issue": "部分题目评分置信度不足",
                "impact": "可能导致评分偏差",
                "question_ids": low_confidence_questions,
                "reported_to_user": False,
            }
        )

    avg_confidence = sum(confidence_values) / len(confidence_values) if confidence_values else 0.7
    penalty = min(0.4, 0.05 * len(issues))
    audit_confidence = max(0.1, min(1.0, avg_confidence - penalty))
    base_grade = 7
    if "missing_evidence" in issue_types:
        base_grade -= 2
    if "missing_rubric_ref" in issue_types:
        base_grade -= 1
    if "low_confidence" in issue_types:
        base_grade -= 1
    if "missing_self_critique" in issue_types:
        base_grade -= 1
    overall_compliance_grade = max(1, min(7, base_grade))

    if issues:
        issue_labels = [issue.get("message", "") for issue in issues[:3] if issue.get("message")]
        summary = f"发现 {len(issues)} 项可疑点，建议复核：{'；'.join(issue_labels)}。"
    else:
        summary = "未发现明显可疑点，结果一致性良好。"

    return {
        "summary": summary,
        "confidence": audit_confidence,
        "issues": issues,
        "compliance_analysis": compliance_analysis,
        "uncertainties_and_conflicts": uncertainties_and_conflicts,
        "overall_compliance_grade": overall_compliance_grade,
        "generated_at": datetime.now().isoformat(),
    }


def _collect_review_reasons(
    question: Dict[str, Any],
    confidence_threshold: float,
) -> List[str]:
    reasons: List[str] = []
    confidence = _safe_float(question.get("confidence", 0))
    if confidence < confidence_threshold:
        reasons.append("low_confidence")

    audit_flags = question.get("audit_flags") or []
    for flag in audit_flags:
        if flag not in reasons:
            reasons.append(flag)

    if question.get("review_corrections"):
        reasons.append("logic_review_adjusted")

    return reasons


def _apply_review_flags_and_queue(
    student_results: List[Dict[str, Any]],
    confidence_threshold: float,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    queue_map: Dict[str, Dict[str, Any]] = {}
    low_confidence_questions: List[Dict[str, Any]] = []

    for student in student_results:
        student_key = (
            student.get("student_key")
            or student.get("student_id")
            or student.get("student_name")
            or ""
        )

        if student.get("needs_confirmation"):
            key = f"boundary:{student_key}"
            queue_map.setdefault(
                key,
                {
                    "type": "boundary",
                    "student_key": student_key,
                    "start_page": student.get("start_page"),
                    "end_page": student.get("end_page"),
                    "confidence": _safe_float(student.get("confidence", 0)),
                    "reasons": ["boundary_needs_confirmation"],
                },
            )

        self_audit = student.get("self_audit") or {}
        compliance_grade = _safe_float(self_audit.get("overall_compliance_grade"))
        if compliance_grade and compliance_grade <= 3:
            key = f"confession:{student_key}"
            queue_map.setdefault(
                key,
                {
                    "type": "confession",
                    "student_key": student_key,
                    "confidence": _safe_float(self_audit.get("confidence", 0)),
                    "compliance_grade": compliance_grade,
                    "reasons": ["confession_low_grade"],
                },
            )

        for question in student.get("question_details", []) or []:
            qid = _normalize_question_id(question.get("question_id") or question.get("questionId"))
            if not qid:
                continue
            reasons = _collect_review_reasons(question, confidence_threshold)
            if not reasons:
                continue
            question["needs_review"] = True
            question["review_reasons"] = reasons

            if "low_confidence" in reasons:
                low_confidence_questions.append(
                    {
                        "student_key": student_key,
                        "question_id": qid,
                        "confidence": _safe_float(question.get("confidence", 0)),
                    }
                )

            page_indices = question.get("page_indices") or question.get("pageIndices") or []
            key = f"question:{student_key}:{qid}"
            existing = queue_map.get(key)
            if existing:
                merged_reasons = set(existing.get("reasons") or [])
                merged_reasons.update(reasons)
                existing["reasons"] = list(merged_reasons)
                if page_indices:
                    existing_pages = set(existing.get("page_indices") or [])
                    existing_pages.update(page_indices)
                    existing["page_indices"] = sorted(existing_pages)
                continue

            queue_map[key] = {
                "type": "question",
                "student_key": student_key,
                "question_id": qid,
                "page_indices": page_indices,
                "confidence": _safe_float(question.get("confidence", 0)),
                "reasons": reasons,
            }

        for page in student.get("page_results", []) or []:
            page_confidence = _safe_float(page.get("confidence", 1.0))
            if page_confidence < confidence_threshold:
                page["needs_review"] = True
                page["review_reasons"] = ["low_confidence"]

    return list(queue_map.values()), low_confidence_questions


def _build_class_report(student_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_students = len(student_results)
    if total_students == 0:
        return {
            "total_students": 0,
            "generated_at": datetime.now().isoformat(),
        }

    total_scores = []
    total_percentages = []
    distribution = {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0}
    knowledge_aggregate: Dict[str, Dict[str, Any]] = {}

    for student in student_results:
        total_score = _safe_float(student.get("total_score", 0))
        max_score = _safe_float(student.get("max_total_score", 0))
        percentage = (total_score / max_score * 100) if max_score > 0 else 0.0
        total_scores.append(total_score)
        total_percentages.append(percentage)

        if percentage >= 85:
            distribution["A"] += 1
        elif percentage >= 70:
            distribution["B"] += 1
        elif percentage >= 60:
            distribution["C"] += 1
        elif percentage >= 50:
            distribution["D"] += 1
        else:
            distribution["E"] += 1

        summary = student.get("student_summary") or _build_student_summary(student)
        for point in summary.get("knowledge_points", []):
            key = point.get("point_id") or point.get("description") or ""
            if not key:
                continue
            entry = knowledge_aggregate.setdefault(
                key,
                {
                    "point_id": point.get("point_id") or "",
                    "description": point.get("description") or "",
                    "total_score": 0.0,
                    "total_max_score": 0.0,
                },
            )
            entry["total_score"] += _safe_float(point.get("score", 0))
            entry["total_max_score"] += _safe_float(point.get("max_score", 0))

    average_score = sum(total_scores) / total_students if total_students else 0.0
    average_percentage = sum(total_percentages) / total_students if total_students else 0.0
    pass_rate = (
        sum(1 for pct in total_percentages if pct >= 60) / total_students if total_students else 0.0
    )

    weak_points = []
    strong_points = []
    for entry in knowledge_aggregate.values():
        max_score = entry.get("total_max_score", 0) or 0
        ratio = (entry.get("total_score", 0) / max_score) if max_score > 0 else 0.0
        record = {
            "point_id": entry.get("point_id"),
            "description": entry.get("description"),
            "mastery_ratio": ratio,
        }
        if ratio < 0.6:
            weak_points.append(record)
        elif ratio >= 0.85:
            strong_points.append(record)

    weak_points.sort(key=lambda x: x.get("mastery_ratio", 0))
    strong_points.sort(key=lambda x: x.get("mastery_ratio", 0), reverse=True)

    summary_parts = [
        f"班级平均分 {average_score:.1f}，平均得分率 {average_percentage:.1f}%。",
        f"及格率 {pass_rate * 100:.1f}%。",
    ]
    if weak_points:
        weak_labels = [p.get("description", "") for p in weak_points[:3] if p.get("description")]
        if weak_labels:
            summary_parts.append(f"主要薄弱知识点：{'，'.join(weak_labels)}。")
    if strong_points:
        strong_labels = [
            p.get("description", "") for p in strong_points[:3] if p.get("description")
        ]
        if strong_labels:
            summary_parts.append(f"优势知识点：{'，'.join(strong_labels)}。")

    return {
        "total_students": total_students,
        "average_score": average_score,
        "average_percentage": average_percentage,
        "pass_rate": pass_rate,
        "score_distribution": distribution,
        "weak_points": weak_points[:10],
        "strong_points": strong_points[:10],
        "summary": " ".join(summary_parts),
        "generated_at": datetime.now().isoformat(),
    }


def _apply_student_result_overrides(
    student_results: List[Dict[str, Any]],
    overrides: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """应用学生结果覆盖"""
    if not overrides:
        return student_results

    # 构建覆盖映射
    override_map = {}
    for item in overrides:
        key = item.get("student_key") or item.get("studentKey")
        if key:
            override_map[key] = item

    updated_results = []
    for student in student_results:
        student_key = student.get("student_key")
        if student_key not in override_map:
            updated_results.append(student)
            continue

        override = override_map[student_key]
        updated_student = student.copy()

        # 构建题目覆盖映射
        q_override_map = {}
        for q in override.get("questionResults") or override.get("question_results") or []:
            qid = _normalize_question_id(q.get("questionId") or q.get("question_id"))
            if qid:
                q_override_map[qid] = q

        # 更新 question_details
        current_details = student.get("question_details") or []
        updated_details = []
        for q in current_details:
            qid = _normalize_question_id(q.get("question_id"))
            if qid in q_override_map:
                logger.info(f"[review] applying override for student={student_key} question={qid}")
                q_override = q_override_map[qid]
                updated_q = q.copy()

                # 更新分数
                if "score" in q_override:
                    updated_q["score"] = float(q_override["score"])

                # 更新反馈
                if "feedback" in q_override:
                    updated_q["feedback"] = q_override["feedback"]

                updated_details.append(updated_q)
            else:
                updated_details.append(q)

        updated_student["question_details"] = updated_details

        # 重新计算总分
        updated_student["total_score"] = sum(float(q.get("score", 0)) for q in updated_details)

        updated_results.append(updated_student)

    return updated_results


def _collect_question_details(student: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Collect question details from student or page_results with page index fallback."""
    details = student.get("question_details") or []
    if not isinstance(details, list) or not details:
        fallback: List[Dict[str, Any]] = []
        for page in student.get("page_results", []) or []:
            for q in page.get("question_details", []) or []:
                merged = dict(q)
                if not merged.get("page_indices") and page.get("page_index") is not None:
                    merged["page_indices"] = [page.get("page_index")]
                fallback.append(merged)
        details = fallback
    return details if isinstance(details, list) else []


# _extract_confession_questions 函数已删除（批改和审计一体化改造）


def _extract_logic_review_questions(student: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract questions that require logic review based on audit signals.
    
    改造说明：
    - 不再依赖 confession 数据（已删除）
    - 改为基于题目的 audit 信息（risk_flags, needs_review, confidence）
    - 如果 audit 信息为空，则使用启发式规则
    """
    details = _collect_question_details(student)

    if not details:
        return []

    flagged_question_ids: set = set()
    confidence_threshold = float(os.getenv("LOGIC_REVIEW_CONFIDENCE_THRESHOLD", "0.7"))

    # 基于 audit 信息筛选需要复核的题目
    for q in details:
        qid = _normalize_question_id(q.get("question_id") or q.get("questionId") or "")
        audit = q.get("audit") or {}
        
        # 1. 检查是否标记为需要复核
        if audit.get("needs_review"):
            flagged_question_ids.add(qid)
            continue
        
        # 2. 检查置信度
        confidence = audit.get("confidence")
        if confidence is not None:
            try:
                if float(confidence) < confidence_threshold:
                    flagged_question_ids.add(qid)
                    continue
            except (ValueError, TypeError):
                pass
        
        # 3. 检查风险标记
        risk_flags = audit.get("risk_flags") or []
        high_risk_flags = ["full_marks", "zero_marks", "boundary_score", "low_confidence", "evidence_gap"]
        if isinstance(risk_flags, list) and any(flag in high_risk_flags for flag in risk_flags):
            flagged_question_ids.add(qid)
            continue
        
        # 4. 检查不确定点
        uncertainties = audit.get("uncertainties") or []
        if isinstance(uncertainties, list) and len(uncertainties) > 0:
            flagged_question_ids.add(qid)

    # 如果没有标记任何题目，使用启发式规则
    if not flagged_question_ids:
        force_all = os.getenv("LOGIC_REVIEW_FORCE_ALL", "true").lower() in ("1", "true", "yes")
        if not force_all:
            logger.debug("[_extract_logic_review_questions] no flagged questions, skipping logic review")
            return []
        
        # 强制全部复核模式：基于启发式规则选择高风险题目
        for q in details:
            qid = _normalize_question_id(q.get("question_id") or q.get("questionId") or "")
            score = q.get("score", 0)
            max_score = q.get("max_score", 0)
            confidence = q.get("confidence", 1.0)
            
            # 满分或零分
            if max_score > 0 and (score >= max_score or score == 0):
                flagged_question_ids.add(qid)
            # 低置信度
            elif confidence < confidence_threshold:
                flagged_question_ids.add(qid)

    max_questions = int(os.getenv("LOGIC_REVIEW_MAX_QUESTIONS", "0"))
    
    # 如果仍然没有标记任何题目，返回空列表或全部题目
    if not flagged_question_ids:
        if max_questions > 0:
            return details[:max_questions]
        return details if force_all else []

    # 收集被标记的题目
    review_questions: List[Dict[str, Any]] = []
    for q in details:
        qid = _normalize_question_id(q.get("question_id") or q.get("questionId") or "")
        if qid in flagged_question_ids:
            review_questions.append(q)

    if max_questions > 0:
        return review_questions[:max_questions]
    return review_questions


# _build_confession_prompt 函数已删除（批改和审计一体化改造）


def _extract_json_from_response(text: str) -> str:
    """
    从 LLM 响应中提取 JSON 内容
    
    支持以下格式：
    1. ```json ... ```
    2. 纯 JSON（以 { 开头）
    3. 包含其他文本的混合内容
    """
    if not text:
        return "{}"
    
    # 尝试提取 ```json ... ``` 块
    json_match = re.search(r'```json\s*\n(.*?)\n```', text, re.DOTALL)
    if json_match:
        return json_match.group(1).strip()
    
    # 尝试提取 ``` ... ``` 块（不带 json 标记）
    code_match = re.search(r'```\s*\n(.*?)\n```', text, re.DOTALL)
    if code_match:
        content = code_match.group(1).strip()
        if content.startswith('{') or content.startswith('['):
            return content
    
    # 尝试提取 { ... } 或 [ ... ]
    start = text.find('{')
    if start == -1:
        start = text.find('[')
    
    if start != -1:
        # 找到匹配的结束括号
        bracket_count = 0
        is_array = text[start] == '['
        end_char = ']' if is_array else '}'
        start_char = '[' if is_array else '{'
        
        for i in range(start, len(text)):
            if text[i] == start_char:
                bracket_count += 1
            elif text[i] == end_char:
                bracket_count -= 1
                if bracket_count == 0:
                    return text[start:i+1]
    
    # 如果都失败了，返回原文本
    return text.strip()


# confession_node 函数已删除（批改和审计一体化改造）
# 原 confession 节点的功能已合并到 grade_batch 节点中


def _build_logic_review_prompt(
    student: Dict[str, Any],
    question_details: List[Dict[str, Any]],
    rubric_map: Dict[str, Dict[str, Any]],
    limits: Dict[str, int],
) -> str:
    """
    构建逻辑复核 (Logic Review) LLM 提示词
    
    改造说明（批改和审计一体化）：
    - 移除了 confession 参数（已删除 confession 节点）
    - 改为直接使用题目中的 audit 信息进行复核决策
    - audit 信息包含：confidence, uncertainties, risk_flags, needs_review

    逻辑复核的核心功能：验证/审计 + 一致性修复
    - 只能基于批改结果、评分标准解析结果和审计信息
    - 不允许引入新事实/新推理
    - 要有批判性思维，查漏补缺
    - 具备有限的修正能力（明显错误）

    ⚠️ 重要：逻辑复核独立性原则 (P3)
    =========================================
    此函数构建的 prompt 不能包含任何记忆系统的数据！

    逻辑复核必须是"无状态"的：
    1. 不能引用历史批改经验或记忆
    2. 评分决策完全基于当前评分标准和学生答案
    3. audit 信息仅用于确定复核重点，不直接影响评分

    允许的输入：
    - student: 当前学生的批改结果
    - question_details: 当前批改的题目详情（含 audit 信息）
    - rubric_map: 评分标准（从 parsed_rubric 构建）
    =========================================
    """
    student_key = student.get("student_key") or student.get("student_name") or "Unknown"
    max_questions = limits.get("max_questions", 20)
    if max_questions <= 0:
        max_questions = len(question_details)
    max_answer_chars = limits.get("max_answer_chars", 400)
    max_feedback_chars = limits.get("max_feedback_chars", 200)
    max_rubric_chars = limits.get("max_rubric_chars", 240)
    max_points = limits.get("max_scoring_points", 4)
    max_evidence_chars = limits.get("max_evidence_chars", 120)

    lines = [
        "# 角色：逻辑复核审计员 (Logic Review Auditor)",
        "",
        "你是一位严谨的逻辑复核审计员，专门负责审计批改结果中的**明显错误**。",
        "",
        "## 核心原则（必须严格遵守）",
        "",
        "### ⚠️ 最高优先级：只纠正明显错误",
        "1. **只修正明显的、无可争议的错误**",
        "   - 证据明确说正确但给了 0 分",
        "   - 证据明确说错误但给了分",
        "   - 分数超出满分或为负数",
        "   - 得分点分数累加错误",
        "",
        "2. **绝对禁止酌情给分**",
        '   - 不得因为"学生可能理解了"而给分',
        '   - 不得因为"答案接近正确"而给部分分（除非评分标准明确允许）',
        '   - 不得因为"解题思路正确"而给分（除非评分标准明确允许）',
        "",
        "3. **严格基于评分标准**",
        "   - 所有修正必须有评分标准中的明确依据",
        "   - 如果评分标准未覆盖某种情况，**保留原判**",
        "   - 不得自行解释或扩展评分标准",
        "",
        "4. **批判性思维**",
        "   - 对自白中披露的风险点持怀疑态度，独立验证",
        '   - 不要轻信任何"可能"、"应该"的推测',
        "   - 宁可漏纠也不可错纠",
        "",
        "### 🔴 无法判断时的处理",
        "当遇到以下情况时，**不修正**，但必须：",
        "- 降低该题的 `confidence` 值（设为 0.3-0.5）",
        "- 在 `honesty_note` 中详细说明无法判断的原因",
        "- 标记 `self_critique_confidence` 为低值",
        "",
        "无法判断的情况包括：",
        "- 评分标准不够清晰",
        "- 学生答案表述模糊",
        "- 证据与评分标准的对应关系不明确",
        "- 存在多种合理解释",
        "",
        "## 检查维度",
        "1. **证据一致性**：evidence 与 awarded 是否一致？",
        "2. **数学正确性**：分数累加是否正确？是否溢出？",
        "3. **标准符合性**：评分是否符合评分标准的字面要求？",
        "",
        "## 修正决策（严格按此执行）",
        "```",
        "if 证据【明确且无歧义地】说正确 and awarded == 0:",
        "    → 修正为得分",
        "elif 证据【明确且无歧义地】说错误 and awarded > 0:",
        "    → 修正为扣分",
        "elif 得分超出满分 or 得分为负:",
        "    → 修正为合理边界值",
        "elif 分数累加明显错误:",
        "    → 修正累加结果",
        "elif 存在任何不确定性:",
        "    → 保留原判 + 降低置信度 + 写明 honesty_note",
        "else:",
        "    → 保留原判",
        "```",
        "",
        "## 可用信息源（仅限这些）",
        "- 批改结果（评分、证据、反馈）",
        "- 评分标准（rubric）—— **修正的唯一依据**",
        "- 审计信息（仅供参考，不作为修正依据）",
        "",
        "## 输出内容",
        "- **review_corrections**：只包含明显错误的修正",
        "- **confidence**：评分置信度（无法判断时设为 0.3-0.5）",
        "- **honesty_note**：无法判断时的详细说明",
        "",
        f"## 学生标识: {student_key}",
        "",
    ]

    # 添加审计信息摘要（基于 audit 字段）
    high_risk_count = 0
    low_confidence_count = 0
    needs_review_count = 0
    risk_summary = []
    
    for q in question_details[:max_questions]:
        audit = q.get("audit") or {}
        qid = _normalize_question_id(q.get("question_id") or q.get("questionId")) or "?"
        
        # 统计风险
        if audit.get("needs_review"):
            needs_review_count += 1
        
        confidence = audit.get("confidence", 1.0)
        if confidence < 0.6:
            low_confidence_count += 1
        
        risk_flags = audit.get("risk_flags") or []
        if any(flag in ["full_marks", "zero_marks", "evidence_gap"] for flag in risk_flags):
            high_risk_count += 1
            risk_summary.append(f"Q{qid}: {', '.join(risk_flags)}")
    
    if high_risk_count > 0 or low_confidence_count > 0 or needs_review_count > 0:
        lines.append("## 审计风险摘要（供你重点关注）")
        lines.append(f"- 需要复核题目数: {needs_review_count}")
        lines.append(f"- 低置信度题目数: {low_confidence_count}")
        lines.append(f"- 高风险题目数: {high_risk_count}")
        
        if risk_summary:
            lines.append("- 具体风险标记:")
            for summary in risk_summary[:5]:
                lines.append(f"  - {summary}")
        lines.append("")

    lines.append("## 题目摘要（供你做一致性检查）")

    for idx, question in enumerate(question_details[:max_questions]):
        qid = _normalize_question_id(
            question.get("question_id") or question.get("questionId")
        ) or str(idx + 1)
        rubric = rubric_map.get(qid, {})
        score = question.get("score", 0)
        max_score = question.get("max_score", rubric.get("max_score", 0))
        question_text = _trim_text(rubric.get("question_text", ""), max_rubric_chars)
        standard_answer = _trim_text(rubric.get("standard_answer", ""), max_rubric_chars)
        student_answer = _trim_text(question.get("student_answer", ""), max_answer_chars)
        feedback = _trim_text(question.get("feedback", ""), max_feedback_chars)

        lines.append(f"- Q{qid}: score {score}/{max_score}")
        if question_text:
            lines.append(f"  prompt: {question_text}")
        if standard_answer:
            lines.append(f"  standard_answer: {standard_answer}")
        if student_answer:
            lines.append(f"  student_answer: {student_answer}")
        if feedback:
            lines.append(f"  feedback: {feedback}")

        scoring_points = (
            question.get("scoring_point_results") or question.get("scoring_results") or []
        )
        if scoring_points:
            lines.append("  scoring_points:")
            for sp in scoring_points[:max_points]:
                if not isinstance(sp, dict):
                    continue
                point_id = (
                    sp.get("point_id")
                    or sp.get("pointId")
                    or (sp.get("scoring_point") or {}).get("point_id")
                    or ""
                )
                awarded = sp.get("awarded", sp.get("score", 0))
                max_points_val = (
                    sp.get("max_points")
                    or sp.get("maxPoints")
                    or (sp.get("scoring_point") or {}).get("score")
                    or 0
                )
                evidence = _trim_text(sp.get("evidence", ""), max_evidence_chars)
                rubric_ref = _trim_text(
                    sp.get("rubric_reference") or sp.get("rubricReference") or "",
                    max_rubric_chars,
                )
                decision = sp.get("decision") or sp.get("result") or ""
                lines.append(
                    f"    - {point_id}: {awarded}/{max_points_val} decision: {decision} "
                    f"evidence: {evidence} rubric_ref: {rubric_ref}"
                )
        lines.append("")

    schema_hint = {
        "student_key": student_key,
        "question_reviews": [
            {
                "question_id": "1",
                "confidence": 0.0,
                "confidence_reason": "string",
                "self_critique": "string",
                "self_critique_confidence": 0.0,
                "review_summary": "string",
                "review_corrections": [
                    {
                        "point_id": "1.1",
                        "correct_awarded": 1,
                        "correct_decision": "得分",
                        "review_reason": "string",
                    }
                ],
                "honesty_note": "string",
            }
        ],
        "self_audit": {
            "summary": "string",
            "confidence": 0.0,
            "issues": [{"issue_type": "string", "message": "string", "question_id": "1"}],
            "compliance_analysis": [{"goal": "string", "tag": "fully_complied", "notes": "string"}],
            "uncertainties_and_conflicts": [
                {
                    "issue": "string",
                    "impact": "string",
                    "question_ids": ["1"],
                    "reported_to_user": True,
                }
            ],
            "overall_compliance_grade": 4,
            "honesty_note": "string",
        },
    }

    lines.append("输出 JSON 模板：")
    lines.append(json.dumps(schema_hint, ensure_ascii=False, indent=2))
    return "\n".join(lines)


async def logic_review_node(state: BatchGradingGraphState) -> Dict[str, Any]:
    """
    逻辑复核节点（文本输入）

    每个学生进行一次纯文本 LLM 复核，输出题目置信度与自白说明。

    ⚠️ 重要：逻辑复核独立性原则 (P3)
    =========================================
    逻辑复核必须是"无状态"的，即：
    1. 评分决策不能依赖记忆系统中的任何数据
    2. LLM prompt 不能包含历史记忆上下文
    3. 复核结果完全基于当前评分标准和学生答案

    记忆系统在此节点的使用仅限于：
    - 记录修正历史（用于未来的批改改进）
    - 整合批次记忆到长期记忆

    这些操作发生在评分决策之后，不影响评分结果。
    =========================================
    """
    batch_id = state["batch_id"]
    # 直接读取 student_results（confession 节点已移除）
    student_results_raw = state.get("student_results", []) or []
    
    # 🔧 去重：由于 Send 并行任务可能导致重复，使用 student_key 去重
    seen_keys = set()
    student_results = []
    for result in reversed(student_results_raw):
        student_key = result.get("student_key") or result.get("student_name") or f"unknown_{len(seen_keys)}"
        if student_key not in seen_keys:
            seen_keys.add(student_key)
            student_results.append(result)
    student_results = list(reversed(student_results))
    
    if len(student_results) != len(student_results_raw):
        logger.info(
            f"[logic_review] 去重: {len(student_results_raw)} → {len(student_results)} 学生"
        )
    
    parsed_rubric = state.get("parsed_rubric", {}) or {}
    api_key = state.get("api_key") or os.getenv("LLM_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    grading_mode = _resolve_grading_mode(state.get("inputs", {}), parsed_rubric)

    def _log_logic_review_done(reason: str, count: int, reviewed: int = 0) -> None:
        message = (
            f"[logic_review] OK completed ({reason}): batch_id={batch_id}, "
            f"students={count}, reviewed={reviewed}"
        )
        logger.info(message)
        logger.info(
            f"[logic_review_done] batch_id={batch_id}, students={count}, reviewed={reviewed}, reason={reason}"
        )
        workflow_logger.info(message)
        workflow_logger.info(
            f"[logic_review_done] batch_id={batch_id}, students={count}, reviewed={reviewed}"
        )

    def _build_logic_review_skip_results(reason: str) -> List[Dict[str, Any]]:
        if not student_results:
            return []
        now_ts = datetime.now().isoformat()
        skipped_results: List[Dict[str, Any]] = []
        for student in student_results:
            updated = dict(student)
            updated.setdefault("self_audit", _build_self_audit(updated))
            updated["logic_reviewed_at"] = now_ts
            updated["logic_review"] = {
                "reviewed_at": now_ts,
                "review_summary": f"logic review skipped ({reason})",
                "question_reviews": [],
                "self_audit": updated.get("self_audit"),
                "skipped": True,
                "skip_reason": reason,
            }
            skipped_results.append(updated)
        return skipped_results

    if grading_mode.startswith("assist"):
        logger.info(f"[logic_review] skip (assist mode): batch_id={batch_id}")
        _log_logic_review_done("assist mode", len(student_results), 0)
        skipped_results = _build_logic_review_skip_results("assist mode")
        return {
            "reviewed_results": skipped_results,
            "student_results": skipped_results,
            "logic_review_results": [],
            "current_stage": "logic_review_completed",
            "percentage": 85.0,
            "timestamps": {
                **state.get("timestamps", {}),
                "logic_review_at": datetime.now().isoformat(),
            },
        }

    if not student_results:
        _log_logic_review_done("no student_results", 0, 0)
        return {
            "reviewed_results": [],
            "student_results": [],
            "logic_review_results": [],
            "current_stage": "logic_review_completed",
            "percentage": 85.0,
            "timestamps": {
                **state.get("timestamps", {}),
                "logic_review_at": datetime.now().isoformat(),
            },
        }

    rubric_map = _build_rubric_question_map(parsed_rubric)
    limits = {
        "max_questions": int(os.getenv("LOGIC_REVIEW_MAX_QUESTIONS", "0")),
        "max_answer_chars": int(os.getenv("LOGIC_REVIEW_MAX_ANSWER_CHARS", "4000")),
        "max_feedback_chars": int(os.getenv("LOGIC_REVIEW_MAX_FEEDBACK_CHARS", "200")),
        "max_rubric_chars": int(os.getenv("LOGIC_REVIEW_MAX_RUBRIC_CHARS", "240")),
        "max_scoring_points": int(os.getenv("LOGIC_REVIEW_MAX_SCORING_POINTS", "4")),
        "max_evidence_chars": int(os.getenv("LOGIC_REVIEW_MAX_EVIDENCE_CHARS", "120")),
    }

    if not api_key:
        updated_results = []
        for student in student_results:
            updated = dict(student)
            updated.setdefault("self_audit", _build_self_audit(updated))
            updated["logic_reviewed_at"] = datetime.now().isoformat()
            updated["logic_review"] = {
                "reviewed_at": updated["logic_reviewed_at"],
                "review_summary": _build_logic_review_summary(
                    updated.get("question_details") or []
                ),
                "question_reviews": [],
                "self_audit": updated.get("self_audit"),
            }
            updated_results.append(updated)
        _log_logic_review_done("rule-based", len(updated_results), 0)
        return {
            "reviewed_results": updated_results,
            "student_results": updated_results,
            "logic_review_results": [],
            "current_stage": "logic_review_completed",
            "percentage": 85.0,
            "timestamps": {
                **state.get("timestamps", {}),
                "logic_review_at": datetime.now().isoformat(),
            },
        }

    from src.services.llm_reasoning import LLMReasoningClient

    reasoning_client = LLMReasoningClient(api_key=api_key, rubric_registry=None)
    max_workers = int(os.getenv("LOGIC_REVIEW_MAX_WORKERS", "3"))

    logic_review_results: List[Dict[str, Any]] = []
    updated_results: List[Optional[Dict[str, Any]]] = [None] * len(student_results)

    async def review_student(payload: Dict[str, Any]) -> Dict[str, Any]:
        index = payload["index"]
        student = payload["student"]
        student_key = (
            student.get("student_key") or student.get("student_name") or f"Student {index + 1}"
        )
        agent_id = f"review-worker-{index}"

        try:
            await _broadcast_progress(
                batch_id,
                {
                    "type": "agent_update",
                    "agentId": agent_id,
                    "agentName": student_key,
                    "agentLabel": student_key,
                    "parentNodeId": "logic_review",
                    "status": "running",
                    "progress": 0,
                    "message": "Logic review running...",
                },
            )

            question_details = _extract_logic_review_questions(student)
            if not question_details:
                updated_student = dict(student)
                _recompute_student_totals(updated_student)
                updated_student["self_audit"] = _build_self_audit(updated_student)
                updated_student["logic_reviewed_at"] = datetime.now().isoformat()
                review_summary = _build_logic_review_summary(question_details)
                updated_student["logic_review"] = {
                    "reviewed_at": updated_student["logic_reviewed_at"],
                    "review_summary": review_summary,
                    "question_reviews": [],
                    "self_audit": updated_student.get("self_audit"),
                }
                await _broadcast_progress(
                    batch_id,
                {
                    "type": "agent_update",
                    "agentId": agent_id,
                    "agentLabel": student_key,
                    "parentNodeId": "logic_review",
                    "status": "completed",
                    "progress": 100,
                    "message": "Logic review skipped (no questions)",
                    "output": {
                        "reviewSummary": review_summary,
                        "selfAudit": updated_student.get("self_audit"),
                    },
                },
                )
                return {"index": index, "result": updated_student, "review": None}
            prompt = _build_logic_review_prompt(
                student,
                question_details,
                rubric_map,
                limits,
            )

            response_text = ""
            try:
                async for chunk in reasoning_client._call_text_api_stream(prompt):
                    output_text, thinking_text = split_thinking_content(chunk)
                    if thinking_text:
                        await _broadcast_progress(
                            batch_id,
                            {
                                "type": "llm_stream_chunk",
                                "nodeId": "logic_review",
                                "nodeName": "Logic Review",
                                "agentId": agent_id,
                                "agentLabel": student_key,
                                "streamType": "thinking",
                                "chunk": thinking_text,
                            },
                        )
                    if output_text:
                        await _broadcast_progress(
                            batch_id,
                            {
                                "type": "llm_stream_chunk",
                                "nodeId": "logic_review",
                                "nodeName": "Logic Review",
                                "agentId": agent_id,
                                "agentLabel": student_key,
                                "streamType": "output",
                                "chunk": output_text,
                            },
                        )
                        response_text += output_text
                    elif thinking_text:
                        response_text += thinking_text
            except Exception as exc:
                logger.warning(f"[logic_review] LLM failed student={student_key}: {exc}")

            payload_data: Dict[str, Any] = {}
            if response_text:
                try:
                    json_text = reasoning_client._extract_json_from_text(response_text)
                    payload_data = json.loads(json_text)
                    
                    # 输出完整 logic_review JSON（用于调试）
                    logger.info(f"🔍 Logic Review 完整JSON (学生={student_key}):\n{json.dumps(payload_data, ensure_ascii=False, indent=2)}")
                    
                except Exception as exc:
                    logger.warning(f"[logic_review] parse failed student={student_key}: {exc}")

            question_reviews = (
                payload_data.get("question_reviews")
                or payload_data.get("questionReviews")
                or payload_data.get("questions")
                or payload_data.get("reviews")
                or []
            )
            review_map: Dict[str, Dict[str, Any]] = {}
            for item in _normalize_logic_review_items(question_reviews):
                qid = _normalize_question_id(item.get("question_id") or item.get("questionId"))
                if not qid:
                    continue
                review_map[qid] = item

            updated_student = dict(student)
            import copy

            updated_student["draft_question_details"] = copy.deepcopy(question_details)
            updated_student["draft_total_score"] = sum(
                _safe_float(q.get("score", 0)) for q in question_details
            )
            updated_student["draft_max_score"] = sum(
                _safe_float(q.get("max_score", 0)) for q in question_details
            )
            updated_details = []
            for q in question_details:
                qid = _normalize_question_id(q.get("question_id") or q.get("questionId"))
                if qid and qid in review_map:
                    merged = _merge_logic_review_fields(q, review_map[qid])
                    updated_details.append(merged)

                    # 记录修正到记忆系统
                    try:
                        original_score = _safe_float(q.get("score", 0))
                        new_score = _safe_float(merged.get("score", 0))
                        if abs(new_score - original_score) >= 0.5:
                            logger.info(f"[logic_review] 题目 {qid} 分数修正: {original_score} -> {new_score}")
                    except Exception as mem_exc:
                        logger.debug(f"[logic_review] 分数修正失败: {mem_exc}")
                else:
                    updated_details.append(dict(q))
            updated_student["question_details"] = updated_details
            _recompute_student_totals(updated_student)

            self_audit = _normalize_logic_review_self_audit(
                payload_data.get("self_audit") or payload_data.get("selfAudit")
            )
            if not self_audit:
                self_audit = _build_self_audit(updated_student)
            updated_student["self_audit"] = self_audit
            updated_student["logic_reviewed_at"] = datetime.now().isoformat()

            review_summary = _build_logic_review_summary(updated_details)
            logic_review_payload = {
                "reviewed_at": updated_student["logic_reviewed_at"],
                "review_summary": review_summary,
                "question_reviews": list(review_map.values()) if payload_data else [],
                "self_audit": self_audit,
            }
            updated_student["logic_review"] = logic_review_payload

            review_payload = {
                "student_key": student_key,
                "student_id": updated_student.get("student_id"),
                **logic_review_payload,
            }
            await _broadcast_progress(
                batch_id,
                {
                    "type": "agent_update",
                    "agentId": agent_id,
                    "agentLabel": student_key,
                    "parentNodeId": "logic_review",
                    "status": "completed",
                    "progress": 100,
                    "message": "Logic review completed",
                    "output": {
                        "reviewSummary": review_summary,
                        "selfAudit": self_audit,
                    },
                },
            )
            return {"index": index, "result": updated_student, "review": review_payload}
        except Exception as exc:
            logger.warning(f"[logic_review] worker failed student={student_key}: {exc}")
            return {"index": index, "result": dict(student), "review": None}

    review_runner = RunnableLambda(review_student)
    inputs = [{"index": idx, "student": student} for idx, student in enumerate(student_results)]
    config = RunnableConfig(max_concurrency=max_workers) if max_workers > 0 else RunnableConfig()
    results = await review_runner.abatch(inputs, config=config)
    for result in results:
        if not result:
            continue
        updated_results[result["index"]] = result["result"]
        review_payload = result.get("review")
        if review_payload:
            logic_review_results.append(review_payload)

    final_results = [r for r in updated_results if r is not None]

    _log_logic_review_done("llm", len(final_results), len(logic_review_results))
    return {
        "reviewed_results": final_results,  # 使用新字段，避免 operator.add 问题
        "student_results": final_results,
        "logic_review_results": logic_review_results,
        "current_stage": "logic_review_completed",
        "percentage": 85.0,
        "timestamps": {
            **state.get("timestamps", {}),
            "logic_review_at": datetime.now().isoformat(),
        },
    }

async def review_node(state: BatchGradingGraphState) -> Dict[str, Any]:
    """
    结果审核节点

    汇总审核批改结果，标记需要人工确认的项目。
    """
    batch_id = state["batch_id"]
    # 优先读取 reviewed_results，回退到 confessed_results，再回退到 student_results
    student_results = state.get("reviewed_results") or state.get("confessed_results") or state.get("student_results", [])
    student_boundaries = state.get("student_boundaries", [])
    enable_review = state.get("inputs", {}).get("enable_review", True)
    grading_mode = _resolve_grading_mode(state.get("inputs", {}), state.get("parsed_rubric", {}))

    logger.info(f"[review] 开始结果审核: batch_id={batch_id}")

    review_threshold = float(os.getenv("GRADING_REVIEW_CONFIDENCE_THRESHOLD", "0.7"))
    max_queue_items = int(os.getenv("GRADING_REVIEW_QUEUE_MAX_ITEMS", "200"))

    # 统计需要确认的边界
    needs_confirmation = [b for b in student_boundaries if b.get("needs_confirmation")]

    review_queue, low_confidence_questions = _apply_review_flags_and_queue(
        student_results, review_threshold
    )

    # 统计低置信度结果（按页）
    low_confidence_results = []
    for student in student_results:
        for page_result in student.get("page_results", []):
            if page_result.get("confidence", 1.0) < review_threshold:
                low_confidence_results.append(
                    {
                        "student_key": student["student_key"],
                        "page_index": page_result.get("page_index"),
                        "confidence": page_result.get("confidence"),
                    }
                )

    review_summary = {
        "total_students": len(student_results),
        "boundaries_need_confirmation": len(needs_confirmation),
        "low_confidence_count": len(low_confidence_results),
        "low_confidence_results": low_confidence_results[:10],  # 最多显示10个
        "low_confidence_question_count": len(low_confidence_questions),
        "low_confidence_questions": low_confidence_questions[:10],
        "review_threshold": review_threshold,
        "review_queue_count": len(review_queue),
        "review_queue": review_queue[:max_queue_items],
    }

    logger.info(
        f"[review] 审核完成: batch_id={batch_id}, "
        f"学生数={review_summary['total_students']}, "
        f"待确认边界={review_summary['boundaries_need_confirmation']}"
    )

    if grading_mode.startswith("assist"):
        logger.info(f"[review] skip (assist mode): batch_id={batch_id}")
        return {
            "review_summary": review_summary,
            "review_result": {"action": "skip", "reason": "assist_mode"},
            "student_results": student_results,
            "current_stage": "review_completed",
            "percentage": 90.0,
            "timestamps": {**state.get("timestamps", {}), "review_at": datetime.now().isoformat()},
        }

    if not enable_review:
        logger.info(f"[review] skip (review disabled): batch_id={batch_id}")
        return {
            "review_summary": review_summary,
            "review_result": {"action": "skip"},
            "student_results": student_results,
            "current_stage": "review_completed",
            "percentage": 90.0,
            "timestamps": {**state.get("timestamps", {}), "review_at": datetime.now().isoformat()},
        }

    review_request = {
        "type": "results_review_required",
        "batch_id": batch_id,
        "summary": review_summary,
        "review_queue": review_queue[:max_queue_items],
        "message": "Results review required",
        "requested_at": datetime.now().isoformat(),
    }
    review_response = interrupt(review_request)

    action = (review_response or {}).get("action", "approve").lower()
    regrade_items = (
        (review_response or {}).get("regrade_items")
        or (review_response or {}).get("regradeItems")
        or []
    )

    updated_results = student_results
    if action == "regrade" and regrade_items:
        updated_results = await _regrade_selected_questions(state, updated_results, regrade_items)

    overrides = (
        (review_response or {}).get("results")
        or (review_response or {}).get("student_results")
        or []
    )
    updated_results = _apply_student_result_overrides(updated_results, overrides)

    return {
        "review_summary": review_summary,
        "review_result": review_response,
        "student_results": updated_results,
        "current_stage": "review_completed",
        "percentage": 90.0,
        "timestamps": {**state.get("timestamps", {}), "review_at": datetime.now().isoformat()},
    }


async def export_node(state: BatchGradingGraphState) -> Dict[str, Any]:
    """
    导出结果节点

    持久化结果并准备导出数据。
    支持无数据库模式下导出结果为 JSON 文件。
    支持部分结果保存：不可恢复错误时保存已完成结果。

    Requirements: 9.4, 11.4
    """
    import os
    
    batch_id = state["batch_id"]
    
    # 🔍 DEBUG: 关键日志 - 记录 export_node 入口
    logger.warning(
        f"[export] 🔍 DEBUG: 进入 export_node, batch_id={batch_id}, "
        f"student_results={len(state.get('student_results', []))}, "
        f"confessed_results={len(state.get('confessed_results', []))}, "
        f"reviewed_results={len(state.get('reviewed_results', []))}"
    )
    # 优先读取 reviewed_results，回退到 confessed_results，再回退到 student_results
    student_results = state.get("reviewed_results") or state.get("confessed_results") or state.get("student_results", [])
    cross_page_questions = state.get("cross_page_questions", [])
    merged_questions = state.get("merged_questions", [])
    grading_results = state.get("grading_results", [])

    logger.info(f"[export] 开始导出结果: batch_id={batch_id}, 学生数={len(student_results)}")

    # 检查是否有失败的页面
    failed_pages = [r for r in grading_results if r.get("status") == "failed"]
    has_failures = len(failed_pages) > 0

    if has_failures:
        logger.warning(f"[export] 检测到 {len(failed_pages)} 个失败页面，" f"将保存部分结果")

    # 检查数据库可用性并实现持久化逻辑
    persisted = False
    try:
        from src.utils.database import db

        # 使用 db.is_available 检查数据库可用性
        if db.is_available:
            logger.info("[export] 数据库连接可用，开始持久化批改结果...")
            
            try:
                from src.db.postgres_grading import (
                    GradingHistory,
                    StudentGradingResult,
                    get_grading_history,
                    save_grading_history,
                    save_student_result,
                )
                import uuid
                
                # 1. 保存批改历史
                total_students = len(student_results)

                # 计算平均分
                total_scores = [s.get("total_score", 0) for s in student_results]
                average_score = sum(total_scores) / total_students if total_students > 0 else 0

                existing_history = None
                try:
                    existing_history = await get_grading_history(batch_id)
                except Exception as e:
                    logger.debug(f"[export] Failed to check existing grading history: {e}")

                if existing_history:
                    history_id = existing_history.id
                    created_at = existing_history.created_at or datetime.now().isoformat()
                    logger.info(f"[export] Reusing grading_history id={history_id} for batch_id={batch_id}")
                else:
                    history_id = str(uuid.uuid4())
                    created_at = datetime.now().isoformat()

                class_ids = None
                state_class_id = state.get("class_id") or state.get("classId")
                if state_class_id:
                    class_ids = [state_class_id]

                # 从 state 中获取 parsed_rubric
                parsed_rubric = state.get("parsed_rubric")
                current_stage = state.get("current_stage")
                teacher_id = state.get("teacher_id") or state.get("inputs", {}).get("teacher_id")
                
                grading_history = GradingHistory(
                    id=history_id,
                    batch_id=batch_id,
                    teacher_id=teacher_id,
                    status="completed" if not has_failures else "partial",
                    class_ids=class_ids,
                    created_at=created_at,
                    completed_at=datetime.now().isoformat(),
                    total_students=total_students,
                    average_score=average_score,
                    rubric_data=parsed_rubric,  # 保存到 rubric_data 字段
                    current_stage=current_stage,  # 保存当前阶段
                    result_data={
                        "teacher_id": teacher_id,
                        "has_failures": has_failures,
                        "failed_pages_count": len(failed_pages),
                        "cross_page_questions": cross_page_questions,
                        "merged_questions": merged_questions,
                    },
                )

                await save_grading_history(grading_history)
                logger.info(f"[export] Grading history saved: history_id={history_id}, batch_id={batch_id}")
                
                # 2. 保存每个学生的批改结果和页面图像
                saved_students = 0
                saved_images = 0

                from src.db.postgres_grading import GradingPageImage, save_page_image

                confession_by_student: Dict[str, Any] = {}
                for item in state.get("confessed_results") or []:
                    if not isinstance(item, dict):
                        continue
                    key = (
                        item.get("student_key")
                        or item.get("student_name")
                        or item.get("studentName")
                    )
                    if not key:
                        continue
                    confession_value = item.get("confession")
                    if confession_value:
                        confession_by_student[key] = confession_value

                logic_review_by_student: Dict[str, Any] = {}
                for item in state.get("logic_review_results") or []:
                    if not isinstance(item, dict):
                        continue
                    key = item.get("student_key") or item.get("studentKey")
                    if key:
                        logic_review_by_student[key] = item

                # 预先构建文件存储索引（仅保存 file_id，不存图片内容）
                file_index_by_page: Dict[int, Any] = {}
                state_file_index = state.get("file_index_by_page") or {}
                if isinstance(state_file_index, dict) and state_file_index:
                    for raw_idx, stored in state_file_index.items():
                        try:
                            file_index_by_page[int(raw_idx)] = stored
                        except Exception:
                            continue
                if os.getenv("ENABLE_FILE_STORAGE", "true").lower() == "true":
                    try:
                        from src.services.file_storage import get_file_storage_service

                        file_storage = get_file_storage_service()
                        stored_files = await file_storage.list_batch_files(batch_id)
                        for item in stored_files:
                            meta = item.metadata or {}
                            if meta.get("type") == "answer" or item.filename.startswith("answer_page"):
                                page_idx = meta.get("page_index")
                                if page_idx is not None:
                                    file_index_by_page.setdefault(int(page_idx), item)
                        if file_index_by_page:
                            logger.info(
                                f"[export] 文件索引已准备: batch_id={batch_id}, pages={len(file_index_by_page)}"
                            )
                    except Exception as e:
                        logger.warning(f"[export] 构建文件索引失败: {e}")

                def _sanitize_question_details(raw_details: Any) -> List[Dict[str, Any]]:
                    if not isinstance(raw_details, list):
                        return []
                    sanitized: List[Dict[str, Any]] = []
                    for item in raw_details:
                        if not isinstance(item, dict):
                            continue
                        cleaned = {
                            k: v
                            for k, v in item.items()
                            if k
                            not in (
                                "image",
                                "image_bytes",
                                "annotations",
                                "annotation",
                                "grading_annotations",
                                "gradingAnnotations",
                            )
                            and not isinstance(v, (bytes, bytearray))
                        }
                        sanitized.append(cleaned)
                    return sanitized

                for student in student_results:
                    try:
                        # 获取学生标识，优先使用 student_key，然后是 student_name
                        student_key = (
                            student.get("student_key") 
                            or student.get("student_name") 
                            or f"student_{saved_students + 1}"
                        )
                        
                        confession_payload = student.get("confession")
                        if not confession_payload:
                            confession_payload = confession_by_student.get(student_key)

                        logic_review_payload = student.get("logic_review") or student.get("logicReview")
                        if not logic_review_payload:
                            logic_review_payload = logic_review_by_student.get(student_key)
                        logic_reviewed_at = (
                            student.get("logic_reviewed_at")
                            or student.get("logicReviewedAt")
                        )
                        if not logic_reviewed_at and isinstance(logic_review_payload, dict):
                            logic_reviewed_at = logic_review_payload.get("reviewed_at")
                        self_audit_payload = student.get("self_audit") or student.get("selfAudit")

                        question_details = _sanitize_question_details(
                            student.get("question_details") or student.get("question_results") or []
                        )

                        result_payload = {
                            "student_name": student.get("student_name") or student.get("studentName"),
                            "student_key": student_key,
                            "student_id": student.get("student_id") or student.get("studentId"),
                            "total_score": student.get("total_score") or student.get("score"),
                            "max_total_score": student.get("max_total_score") or student.get("max_score"),
                            "percentage": student.get("percentage", 0),
                            "grading_mode": student.get("grading_mode") or student.get("gradingMode"),
                            "start_page": student.get("start_page") or student.get("startPage"),
                            "end_page": student.get("end_page") or student.get("endPage"),
                            "question_details": question_details,
                            "question_results": question_details,
                            "confession": confession_payload,
                            "self_audit": self_audit_payload,
                            "logic_review": logic_review_payload,
                            "logicReview": logic_review_payload,
                            "logic_reviewed_at": logic_reviewed_at,
                            "logicReviewedAt": logic_reviewed_at,
                            "draft_question_details": student.get("draft_question_details")
                            or student.get("draftQuestionDetails"),
                            "draft_total_score": student.get("draft_total_score")
                            or student.get("draftTotalScore"),
                            "draft_max_score": student.get("draft_max_score")
                            or student.get("draftMaxScore"),
                        }

                        student_result = StudentGradingResult(
                            id=str(uuid.uuid4()),
                            grading_history_id=history_id,
                            student_key=student_key,
                            score=student.get("total_score"),
                            max_score=student.get("max_total_score"),
                            class_id=None,  # 可以从 state 中获取
                            student_id=student.get("student_id"),
                            summary=student.get("student_summary"),
                            confession=confession_payload,
                            result_data=result_payload,
                            imported_at=datetime.now().isoformat(),
                        )
                        
                        logger.info(f"[export] 准备保存学生结果: student_key={student_key}, history_id={history_id}")
                        await save_student_result(student_result)
                        logger.info(f"[export] 成功保存学生结果: student_key={student_key}")
                        saved_students += 1
                        
                        # 3. 保存该学生的页面图像
                        page_results = student.get("page_results", [])
                        logger.info(f"[export] 学生 {student_key} 有 {len(page_results)} 个页面结果")
                        
                        for page_result in page_results:
                            page_index = page_result.get("page_index", 0)

                            stored_file = file_index_by_page.get(page_index)
                            logger.debug(f"[export] 页面 {page_index}: stored_file={stored_file is not None}")
                            file_id = ""
                            file_url = None
                            content_type = None

                            if stored_file:
                                if isinstance(stored_file, dict):
                                    file_id = (
                                        stored_file.get("file_id")
                                        or stored_file.get("id")
                                        or ""
                                    )
                                    content_type = (
                                        stored_file.get("content_type")
                                        or stored_file.get("contentType")
                                    )
                                else:
                                    file_id = stored_file.file_id
                                    content_type = stored_file.content_type

                            if not file_id:
                                logger.debug(
                                    f"[export] Skip page image without file_id: student={student_key}, page={page_index}"
                                )
                                continue

                            try:
                                page_image = GradingPageImage(
                                    id=str(uuid.uuid4()),
                                    grading_history_id=history_id,
                                    student_key=student_key,
                                    page_index=page_index,
                                    file_id=file_id,
                                    file_url=file_url,
                                    content_type=content_type,
                                    created_at=datetime.now().isoformat(),
                                )

                                await save_page_image(page_image)
                                saved_images += 1
                            except Exception as e:
                                logger.error(
                                    f"[export] Failed to save page image index (student={student_key}, page={page_index}): {e}"
                                )
                    except Exception as e:
                        logger.error(f"[export] 保存学生结果失败: {e}")
                
                logger.info(f"[export] 已保存 {saved_students}/{total_students} 个学生结果到数据库")
                logger.info(f"[export] 已保存 {saved_images} 张页面图像到数据库")
                persisted = True
                
            except Exception as e:
                logger.error(f"[export] 数据库持久化失败: {e}", exc_info=True)
                persisted = False
        else:
            logger.info("[export] 数据库不可用，跳过持久化")
    except Exception as e:
        logger.warning(f"[export] 数据库连接检查失败（离线模式）: {e}")

    # 准备导出数据

    if not persisted:
        try:
            from src.db.postgres_store import GradingHistory as SyncGradingHistory
            from src.db.postgres_store import save_grading_history as save_grading_history_sync
            import uuid

            total_students = len(student_results)
            total_scores = [s.get("total_score", 0) for s in student_results]
            average_score = sum(total_scores) / total_students if total_students > 0 else 0
            teacher_id = state.get("teacher_id") or state.get("inputs", {}).get("teacher_id")
            state_class_id = state.get("class_id") or state.get("classId")
            class_ids = [state_class_id] if state_class_id else None

            history_id = str(uuid.uuid4())
            created_at = datetime.now().isoformat()

            sync_history = SyncGradingHistory(
                id=history_id,
                batch_id=batch_id,
                teacher_id=teacher_id,
                status="completed" if not has_failures else "partial",
                class_ids=class_ids,
                created_at=created_at,
                completed_at=datetime.now().isoformat(),
                total_students=total_students,
                average_score=average_score,
                result_data={
                    "teacher_id": teacher_id,
                    "has_failures": has_failures,
                    "failed_pages_count": len(failed_pages),
                    "cross_page_questions": cross_page_questions,
                    "merged_questions": merged_questions,
                },
            )

            await asyncio.to_thread(save_grading_history_sync, sync_history)
            logger.info(f"[export] Fallback grading history saved: batch_id={batch_id}")
            persisted = True
        except Exception as exc:
            logger.warning(f"[export] fallback grading history persist failed: {exc}")


    export_data = {
        "batch_id": batch_id,
        "export_time": datetime.now().isoformat(),
        "persisted": persisted,
        "has_failures": has_failures,
        "failed_pages_count": len(failed_pages),
        "cross_page_questions": cross_page_questions,
        "merged_questions": merged_questions,
        "students": [],
    }

    # 添加失败页面信息（用于部分结果保存）
    if has_failures:
        export_data["failed_pages"] = [
            {
                "page_index": p.get("page_index"),
                "error": p.get("error"),
                "batch_index": p.get("batch_index"),
            }
            for p in failed_pages
        ]

    for student in student_results:
        _recompute_student_totals(student)
        # 计算百分比
        total_score = student.get("total_score", 0)
        max_score = student.get("max_total_score", 0)
        percentage = (total_score / max_score * 100) if max_score > 0 else 0

        summary = student.get("student_summary") or _build_student_summary(student)
        audit = student.get("self_audit") or _build_self_audit(student)
        student["student_summary"] = summary
        student["self_audit"] = audit

        # 收集题目结果
        question_results = []

        # 优先使用 question_details
        if student.get("question_details"):
            for q in student["question_details"]:
                question_results.append(
                    {
                        "question_id": q.get("question_id", ""),
                        "score": q.get("score", 0),
                        "max_score": q.get("max_score", 0),
                        "feedback": q.get("feedback", ""),
                        "student_answer": q.get("student_answer", ""),
                        "is_correct": q.get("is_correct", False),
                        "is_cross_page": q.get("is_cross_page", False),
                        "page_indices": q.get("page_indices", []),
                        "confidence": q.get("confidence", 1.0),
                        "confidence_reason": q.get("confidence_reason")
                        or q.get("confidenceReason"),
                        "self_critique": q.get("self_critique") or q.get("selfCritique"),
                        "self_critique_confidence": (
                            q.get("self_critique_confidence") or q.get("selfCritiqueConfidence")
                        ),
                        "review_summary": q.get("review_summary") or q.get("reviewSummary"),
                        "review_corrections": q.get("review_corrections")
                        or q.get("reviewCorrections")
                        or [],
                        "review_reasons": q.get("review_reasons") or q.get("reviewReasons") or [],
                        "needs_review": (
                            q.get("needs_review")
                            if q.get("needs_review") is not None
                            else q.get("needsReview")
                        ),
                        "audit_flags": q.get("audit_flags") or q.get("auditFlags") or [],
                        "typo_notes": q.get("typo_notes") or q.get("typoNotes") or [],
                        "rubric_refs": q.get("rubric_refs") or q.get("rubricRefs") or [],
                        "honesty_note": q.get("honesty_note") or q.get("honestyNote"),
                        "question_type": q.get("question_type") or q.get("questionType"),
                        "merge_source": q.get("merge_source") or q.get("mergeSource"),
                        "scoring_point_results": (
                            q.get("scoring_point_results") or q.get("scoring_results") or []
                        ),
                    }
                )
        # 否则从 page_results 提取
        elif student.get("page_results"):
            for page in student["page_results"]:
                if page.get("status") == "completed" and not page.get("is_blank_page", False):
                    for q in page.get("question_details", []):
                        question_results.append(
                            {
                                "question_id": q.get("question_id", ""),
                                "score": q.get("score", 0),
                                "max_score": q.get("max_score", 0),
                                "feedback": q.get("feedback", ""),
                                "student_answer": q.get("student_answer", ""),
                                "is_correct": q.get("is_correct", False),
                                "confidence": q.get("confidence", 1.0),
                                "confidence_reason": q.get("confidence_reason")
                                or q.get("confidenceReason"),
                                "self_critique": q.get("self_critique") or q.get("selfCritique"),
                                "self_critique_confidence": (
                                    q.get("self_critique_confidence")
                                    or q.get("selfCritiqueConfidence")
                                ),
                                "review_summary": q.get("review_summary") or q.get("reviewSummary"),
                                "review_corrections": q.get("review_corrections")
                                or q.get("reviewCorrections")
                                or [],
                                "review_reasons": q.get("review_reasons")
                                or q.get("reviewReasons")
                                or [],
                                "needs_review": (
                                    q.get("needs_review")
                                    if q.get("needs_review") is not None
                                    else q.get("needsReview")
                                ),
                                "audit_flags": q.get("audit_flags") or q.get("auditFlags") or [],
                                "typo_notes": q.get("typo_notes") or q.get("typoNotes") or [],
                                "rubric_refs": q.get("rubric_refs") or q.get("rubricRefs") or [],
                                "honesty_note": q.get("honesty_note") or q.get("honestyNote"),
                                "question_type": q.get("question_type") or q.get("questionType"),
                                "is_cross_page": q.get("is_cross_page", False),
                                "page_indices": q.get("page_indices") or [page.get("page_index")],
                                "merge_source": q.get("merge_source") or q.get("mergeSource"),
                                "scoring_point_results": (
                                    q.get("scoring_point_results") or q.get("scoring_results") or []
                                ),
                            }
                        )

        export_data["students"].append(
            {
                "student_name": student["student_key"],
                "student_id": student.get("student_id"),
                "score": total_score,
                "max_score": max_score,
                "percentage": round(percentage, 1),
                "question_results": question_results,
                "confidence": student.get("confidence", 0),
                "needs_confirmation": student.get("needs_confirmation", False),
                "start_page": student.get("start_page", 0),
                "end_page": student.get("end_page", 0),
                "student_summary": summary,
                "self_audit": audit,
                "draft_question_details": student.get("draft_question_details"),
                "draft_total_score": student.get("draft_total_score"),
                "draft_max_score": student.get("draft_max_score"),
                "missing_question_ids": student.get("missing_question_ids"),
            }
        )

    class_report = _build_class_report(student_results)
    export_data["class_report"] = class_report

    # 导出为 JSON 文件 (Requirements: 9.4, 11.4)
    # 无数据库模式或有失败时都导出
    if not persisted or has_failures:
        try:
            import os

            # 创建导出目录
            export_dir = os.getenv("EXPORT_DIR", "./exports")
            os.makedirs(export_dir, exist_ok=True)

            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # 如果有失败，标记为部分结果 (Requirement 9.4)
            if has_failures:
                filename = f"partial_result_{batch_id}_{timestamp}.json"
                logger.info(f"[export] 保存部分结果（{len(failed_pages)} 个页面失败）: {filename}")
            else:
                filename = f"grading_result_{batch_id}_{timestamp}.json"

            filepath = os.path.join(export_dir, filename)

            # 写入 JSON 文件
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)

            export_data["json_file"] = filepath

            if has_failures:
                logger.warning(
                    f"[export] 部分结果已保存: {filepath}. "
                    f"完成={len(grading_results) - len(failed_pages)}/{len(grading_results)} 页"
                )
            else:
                logger.info(f"[export] 结果已导出为 JSON: {filepath}")

        except Exception as e:
            logger.error(f"[export] JSON 导出失败: {e}", exc_info=True)
            export_data["json_export_error"] = str(e)

            # 记录错误
            from src.utils.error_handling import get_error_manager

            error_manager = get_error_manager()
            error_manager.add_error(
                exc=e,
                context={
                    "batch_id": batch_id,
                    "function": "export_node",
                    "export_type": "json",
                },
                batch_id=batch_id,
            )

    # 导出错误日志（如果有错误）
    try:
        from src.utils.error_handling import get_error_manager

        error_manager = get_error_manager()

        batch_errors = error_manager.get_errors_by_batch(batch_id)
        if batch_errors:
            import os

            export_dir = os.getenv("EXPORT_DIR", "./exports")
            os.makedirs(export_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            error_log_file = os.path.join(export_dir, f"error_log_{batch_id}_{timestamp}.json")

            error_manager.export_to_file(error_log_file)
            export_data["error_log_file"] = error_log_file

            logger.info(
                f"[export] 错误日志已导出: {error_log_file} " f"({len(batch_errors)} 个错误)"
            )
    except Exception as e:
        logger.error(f"[export] 错误日志导出失败: {e}", exc_info=True)

    logger.info(
        f"[export] 导出完成: batch_id={batch_id}, "
        f"学生数={len(export_data['students'])}, "
        f"跨页题目数={len(cross_page_questions)}, "
        f"失败页面数={len(failed_pages)}"
    )

    return {
        "export_data": export_data,
        "student_results": student_results,
        "class_report": class_report,
        "current_stage": "completed",
        "percentage": 100.0,
        "timestamps": {
            **state.get("timestamps", {}),
            "export_at": datetime.now().isoformat(),
            "completed_at": datetime.now().isoformat(),
        },
    }


# ==================== Graph 编译 ====================


def create_batch_grading_graph(
    checkpointer: Optional[AsyncPostgresSaver] = None,
    batch_config: Optional[BatchConfig] = None,
) -> StateGraph:
    """创建批量批改 Graph（简化版）

    工作流：
    1. intake: 接收文件
    2. preprocess: 图像预处理
    3. rubric_parse: 解析评分标准（含自白/confession 生成）
    4. rubric_self_review: 自动复核（基于自白，LLM 自动修正）
    5. rubric_review: 人工审核（可跳过）
    6. grade_batch (并行): 按学生或批次大小并行批改（含审计信息）
    7. logic_review: 逻辑复核（基于审计信息）
    8. review: 结果审核
    9. export: 导出结果

    流程图：
    ```
    intake
      ↓
    preprocess
      ↓
    rubric_parse  ← 解析评分标准 + 生成自白（confession）
      ↓
    rubric_self_review  ← 自动复核（基于自白和原图修正）
      ↓
    rubric_review (可跳过)  ← 人工复核
      ↓
    ┌─────────────────┐
    │ grade_batch (N) │  ← 并行批改（按学生分批，含审计信息）
    └─────────────────┘
      ↓
    logic_review  ← 逻辑复核（基于审计信息）
      ↓
    review
      ↓
    export
      ↓
    END
    ```

    特性：
    - 按学生分批批改（前端提供 student_mapping）
    - Worker 独立性保证 (Requirements: 3.2)
    - 批次失败重试 (Requirements: 3.3, 9.3)
    - 实时进度报告 (Requirements: 3.4)
    - 记忆系统集成（科目隔离）

    已移除：
    - index 节点（不再需要索引层）
    - cross_page_merge 节点（不再需要跨页合并）
    - index_merge 节点（不再需要索引聚合）

    Args:
        checkpointer: PostgreSQL Checkpointer（可选）
        batch_config: 批次配置（可选，默认从环境变量加载）

    Returns:
        编译后的 Graph
    """
    # 设置批次配置
    if batch_config:
        set_batch_config(batch_config)

    config = get_batch_config()
    logger.info(
        f"创建批量批改 Graph: batch_size={config.batch_size}, "
        f"max_workers={config.max_concurrent_workers}, "
        f"max_retries={config.max_retries}"
    )

    graph = StateGraph(BatchGradingGraphState)

    # 添加节点
    graph.add_node("intake", intake_node)
    graph.add_node("preprocess", preprocess_node)
    # graph.add_node("index", index_node)  # 已移除：不再需要索引层
    graph.add_node("rubric_parse", rubric_parse_node)
    graph.add_node("rubric_self_review", rubric_self_review_node)  # 自动复核节点（基于自白）
    graph.add_node("rubric_review", rubric_review_node)
    graph.add_node("grade_batch", grade_batch_node)
    # graph.add_node("simple_aggregate", simple_aggregate_node)  # 已移除：grade_batch 直接输出 student_results
    # graph.add_node("cross_page_merge", cross_page_merge_node)  # 已移除：不再需要跨页合并
    # graph.add_node("index_merge", index_merge_node)  # 已移除：不再需要索引聚合
    # graph.add_node("confession", confession_node)  # 已移除：批改和审计一体化改造
    graph.add_node("logic_review", logic_review_node)

    graph.add_node("review", review_node)
    graph.add_node("export", export_node)

    # 入口点
    graph.set_entry_point("intake")

    # 简化流程：intake → preprocess → rubric_parse → rubric_self_review → rubric_review (可选)
    graph.add_edge("intake", "preprocess")
    graph.add_edge("preprocess", "rubric_parse")
    graph.add_edge("rubric_parse", "rubric_self_review")  # 解析后先进行自动复核
    
    # ✅ 先添加占位节点,用于跳过 review 时的路由
    async def grading_fanout_placeholder_node(state: BatchGradingGraphState) -> Dict[str, Any]:
        """占位节点,用于跳过 review 时直接进入 grading_fanout"""
        batch_id = state.get("batch_id", "unknown")
        logger.info(f"[grading_fanout_placeholder] 跳过 review,准备进入批改: batch_id={batch_id}")
        return {
            "current_stage": "grading_fanout_placeholder",
            "percentage": 20.0,
        }
    
    graph.add_node("grading_fanout_placeholder", grading_fanout_placeholder_node)
    
    # ✅ 修复:添加条件路由,根据 enable_review 决定是否需要 rubric_review
    def should_review_rubric(state: BatchGradingGraphState) -> str:
        """决定是否需要 rubric review（在自动复核之后）"""
        batch_id = state.get("batch_id", "unknown")
        enable_review = state.get("inputs", {}).get("enable_review", True)
        parsed_rubric = state.get("parsed_rubric", {})
        grading_mode = _resolve_grading_mode(state.get("inputs", {}), parsed_rubric)
        
        # 如果是 assist 模式或 review 被禁用,直接跳到 grading_fanout
        if grading_mode.startswith("assist") or not enable_review:
            logger.info(f"[should_review_rubric] 跳过 review,直接进入批改: batch_id={batch_id}, mode={grading_mode}, enable_review={enable_review}")
            return "skip_review"
        
        # 如果没有 rubric,也跳过
        if not parsed_rubric or not parsed_rubric.get("questions"):
            logger.info(f"[should_review_rubric] 没有 rubric,跳过 review: batch_id={batch_id}")
            return "skip_review"
        
        logger.info(f"[should_review_rubric] 需要 review: batch_id={batch_id}")
        return "do_review"
    
    # rubric_self_review 后进行条件路由（决定是否需要人工复核）
    graph.add_conditional_edges(
        "rubric_self_review",
        should_review_rubric,
        {
            "do_review": "rubric_review",
            "skip_review": "grading_fanout_placeholder",
        },
    )

    # rubric_review 后也进入 grading_fanout
    graph.add_conditional_edges(
        "rubric_review",
        grading_fanout_router,
        [
            "grade_batch",
            "logic_review",  # 跳过 confession，直接到 logic_review
        ],
    )
    
    # grading_fanout_placeholder 也使用相同的路由
    graph.add_conditional_edges(
        "grading_fanout_placeholder",
        grading_fanout_router,
        [
            "grade_batch",
            "logic_review",  # 跳过 confession，直接到 logic_review
        ],
    )

    # 🔥 修复：移除有问题的 grading_merge_gate 条件边
    # 问题：并行 Send 任务完成时，每个任务都会独立触发条件边，
    # 导致状态聚合前就检查 student_results 数量，产生竞态条件。
    # 
    # 解决方案：直接使用普通边，LangGraph 会自动等待所有 Send 任务完成、
    # 状态聚合后，再进入下一个节点（logic_review）。
    # confession 节点已移除，批改和审计一体化
    graph.add_edge("grade_batch", "logic_review")

    # 简化流程：logic_review → review → export → END
    # （confession 节点已移除）
    graph.add_edge("logic_review", "review")
    graph.add_edge("review", "export")
    graph.add_edge("export", END)

    # 编译
    compile_kwargs = {}
    if checkpointer:
        compile_kwargs["checkpointer"] = checkpointer

    compiled_graph = graph.compile(**compile_kwargs)

    logger.info("批量批改 Graph 已编译")

    return compiled_graph


def _count_graded_pages(grading_results: List[Dict[str, Any]]) -> int:
    """Count unique graded pages from grading_results (supports multi-page student batches)."""
    if not grading_results:
        return 0
    pages = set()
    for result in grading_results:
        page_indices = result.get("page_indices") if isinstance(result, dict) else None
        if isinstance(page_indices, list) and page_indices:
            for idx in page_indices:
                if idx is None:
                    continue
                pages.add(idx)
            continue
        page_index = result.get("page_index") if isinstance(result, dict) else None
        if page_index is None:
            continue
        pages.add(page_index)
    return len(pages)


def grading_merge_gate(state: BatchGradingGraphState) -> str:
    """
    批改汇聚门控（已弃用）

    ⚠️ 此函数当前未被使用！
    
    原问题：当使用 Send 进行并行批改时，每个并行任务完成后都会独立触发此条件边，
    但此时状态聚合可能还未完成，导致 student_results 数量检查失败，返回 "wait" → END，
    整个图被提前标记为 "completed"，跳过了 confession 和 logic_review。
    
    修复方案：移除条件边，改为直接使用普通边 (add_edge)，让 LangGraph 自动等待
    所有 Send 任务完成并聚合状态后，再进入下一个节点。
    
    保留此函数以便未来调试或参考。
    """
    batch_id = state.get("batch_id", "unknown")
    grading_results = state.get("grading_results") or []
    student_results = state.get("student_results") or []
    student_boundaries = state.get("student_boundaries") or []
    
    total_students = len(student_boundaries) if student_boundaries else 0
    completed_students = len(student_results)
    
    # 🔍 DEBUG: 详细日志记录每次调用的状态
    logger.warning(
        f"[grading_merge] 🔍 DEBUG entry: batch_id={batch_id}, "
        f"completed={completed_students}, total={total_students}, "
        f"student_keys={[s.get('student_key') for s in student_results]}, "
        f"boundary_keys={[b.get('student_key') for b in student_boundaries]}, "
        f"state_keys={sorted(list(state.keys()))}"
    )
    
    logger.info(
        f"[grading_merge] 诊断: batch_id={batch_id}, "
        f"completed_students={completed_students}, total_students={total_students}, "
        f"student_results={len(student_results)}, grading_results={len(grading_results)}"
    )

    # 🔧 修复：优先检查 student_results（grade_student 模式）
    # 如果有 student_boundaries，就按学生数量判断
    if total_students > 0:
        if completed_students >= total_students:
            logger.info(f"[grading_merge] ✅ 所有 {total_students} 个学生批改完成，进入自白阶段")
            logger.warning(f"[grading_merge] 🔍 DEBUG: returning 'continue' - all students done")
            return "continue"
        else:
            logger.info(f"[grading_merge] ⏳ 学生批改进度: {completed_students}/{total_students}")
            logger.warning(f"[grading_merge] 🔍 DEBUG: returning 'wait' - {completed_students}/{total_students} students")
            return "wait"
    
    # 🔧 Fallback：如果没有 student_boundaries，检查是否有任何批改结果
    if student_results:
        logger.info(f"[grading_merge] ✅ 有 {len(student_results)} 个学生结果（无边界信息），进入自白阶段")
        logger.warning(f"[grading_merge] 🔍 DEBUG: returning 'continue' - fallback with {len(student_results)} results")
        return "continue"
    
    if grading_results:
        logger.info(f"[grading_merge] ✅ 有 {len(grading_results)} 个页面结果，进入自白阶段")
        return "continue"
    
    # 没有任何结果，继续等待（可能还在处理中）
    logger.warning("[grading_merge] ⚠️ 没有批改结果，继续等待")
    logger.warning(f"[grading_merge] 🔍 DEBUG: returning 'wait' - no results at all")
    return "wait"


# ==================== 导出 ====================

__all__ = [
    # 配置类
    "BatchConfig",
    "get_batch_config",
    "set_batch_config",
    # 进度类
    "BatchProgress",
    "BatchTaskState",
    # 节点函数
    "intake_node",
    "preprocess_node",
    "rubric_parse_node",
    "grade_batch_node",
    "confession_node",  # 原 confession_node
    "logic_review_node",

    "review_node",
    "export_node",
    # 路由函数
    "grading_fanout_router",
    # Graph 创建
    "create_batch_grading_graph",
]
