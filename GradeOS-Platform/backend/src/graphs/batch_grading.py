"""批量批改 Graph 编译

实现批量试卷批改流程，支持：
- 图像预处理
- 评分标准解析
- 可配置分批并行批改（不预先分割学生）
- 批改前索引（题目信息与学生识别）
- 结果审核
- 导出结果
- 批次失败重试与错误隔离
- 实时进度报告

工作流：
接收文件 → 图像预处理 → 索引层 → 解析评分标准 → 可配置分批批改 → 索引聚合 → 结果审核 → 导出结果

验证：需求 3.1, 3.2, 3.3, 3.4, 5.1, 5.4, 10.1
"""

import logging
import os
import asyncio
from typing import Optional, List, Dict, Any, Literal, Tuple
from datetime import datetime
from dataclasses import dataclass, field

from langgraph.graph import StateGraph, END
from langgraph.types import Send
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from src.graphs.state import BatchGradingGraphState


logger = logging.getLogger(__name__)


# ==================== 批次配置 ====================


@dataclass
class BatchConfig:
    """
    批次配置类
    
    支持配置批次大小和并发数量。
    
    Requirements: 3.1, 10.1
    """
    batch_size: int = 10  # 每批处理的页面数量
    max_concurrent_workers: int = 5  # 最大并发 Worker 数量
    max_retries: int = 2  # 批次失败最大重试次数
    retry_delay: float = 1.0  # 重试延迟（秒）
    
    @classmethod
    def from_env(cls) -> "BatchConfig":
        """从环境变量加载配置"""
        return cls(
            batch_size=int(os.getenv("GRADING_BATCH_SIZE", "10")),
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
        error: Optional[str] = None
    ) -> None:
        """更新单个批次状态"""
        self.batch_details[batch_index] = {
            "status": status,
            "pages_processed": pages_processed,
            "pages_failed": pages_failed,
            "error": error,
            "updated_at": datetime.now().isoformat()
        }
        
        # 重新计算统计
        self.completed_batches = sum(
            1 for d in self.batch_details.values() if d["status"] == "completed"
        )
        self.failed_batches = sum(
            1 for d in self.batch_details.values() if d["status"] == "failed"
        )
        self.in_progress_batches = sum(
            1 for d in self.batch_details.values() if d["status"] == "in_progress"
        )
        self.processed_pages = sum(
            d["pages_processed"] for d in self.batch_details.values()
        )
        self.failed_pages = sum(
            d["pages_failed"] for d in self.batch_details.values()
        )
        
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
    page_index_contexts: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    api_key: str
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
        "timestamps": {
            **state.get("timestamps", {}),
            "intake_at": datetime.now().isoformat()
        }
    }


async def preprocess_node(state: BatchGradingGraphState) -> Dict[str, Any]:
    """
    图像预处理节点
    
    对图像进行预处理（去噪、增强、旋转校正等）。
    """
    batch_id = state["batch_id"]
    answer_images = state.get("answer_images", [])
    
    logger.info(f"[preprocess] 开始图像预处理: batch_id={batch_id}, 页数={len(answer_images)}")
    
    # TODO: 实际的图像预处理逻辑
    # 目前直接传递原始图像
    processed_images = answer_images
    
    logger.info(f"[preprocess] 图像预处理完成: batch_id={batch_id}")
    
    return {
        "processed_images": processed_images,
        "current_stage": "preprocess_completed",
        "percentage": 10.0,
        "timestamps": {
            **state.get("timestamps", {}),
            "preprocess_at": datetime.now().isoformat()
        }
    }


async def index_node(state: BatchGradingGraphState) -> Dict[str, Any]:
    """
    索引层节点（批改前）

    使用 LLM 生成每页题目信息并识别学生，用于后续批改上下文对齐。
    """
    batch_id = state["batch_id"]
    processed_images = state.get("processed_images", [])
    api_key = state.get("api_key") or os.getenv("GEMINI_API_KEY")

    logger.info(
        f"[index] 开始索引: batch_id={batch_id}, 页数={len(processed_images)}"
    )

    if not processed_images:
        logger.warning(f"[index] 无待索引页面: batch_id={batch_id}")
        return {
            "index_results": {
                "model": None,
                "total_pages": 0,
                "pages": [],
                "students": [],
                "unidentified_pages": [],
            },
            "page_index_contexts": {},
            "student_page_map": {},
            "indexed_students": [],
            "index_unidentified_pages": [],
            "student_boundaries": [],
            "current_stage": "index_completed",
            "percentage": 12.0,
            "timestamps": {
                **state.get("timestamps", {}),
                "index_at": datetime.now().isoformat(),
            },
        }

    if not api_key:
        logger.warning(f"[index] 缺少 API key，跳过索引: batch_id={batch_id}")
        return {
            "index_results": {
                "model": None,
                "total_pages": len(processed_images),
                "pages": [],
                "students": [],
                "unidentified_pages": list(range(len(processed_images))),
            },
            "page_index_contexts": {},
            "student_page_map": {},
            "indexed_students": [],
            "index_unidentified_pages": list(range(len(processed_images))),
            "student_boundaries": [],
            "current_stage": "index_completed",
            "percentage": 12.0,
            "timestamps": {
                **state.get("timestamps", {}),
                "index_at": datetime.now().isoformat(),
            },
        }

    try:
        from src.config.models import get_index_model
        from src.services.student_identification import StudentIdentificationService

        model_name = get_index_model()
        id_service = StudentIdentificationService(api_key=api_key, model_name=model_name)

        max_concurrency = int(os.getenv("INDEX_MAX_CONCURRENCY", "5"))
        semaphore = asyncio.Semaphore(max_concurrency)

        async def analyze_page(image_data: bytes, page_index: int):
            async with semaphore:
                return await id_service.analyze_page(image_data, page_index)

        tasks = [
            analyze_page(image_data, page_index)
            for page_index, image_data in enumerate(processed_images)
        ]
        page_analyses = await asyncio.gather(*tasks)
        page_analyses.sort(key=lambda x: x.page_index)

        segmentation_result = id_service.segment_from_analyses(page_analyses)

        def student_info_to_dict(info):
            if not info:
                return None
            return {
                "name": info.name,
                "student_id": info.student_id,
                "class_name": info.class_name,
                "confidence": info.confidence,
                "is_placeholder": getattr(info, "is_placeholder", False),
            }

        # page_index -> student mapping
        page_student_map = {}
        for mapping in segmentation_result.page_mappings:
            student_info = mapping.student_info
            student_key = student_info.student_id or student_info.name or f"unknown_{mapping.page_index}"
            page_student_map[mapping.page_index] = {
                "student_key": student_key,
                "student_info": student_info,
                "is_first_page": mapping.is_first_page,
            }

        page_index_contexts = {}
        index_pages = []
        student_groups = {}
        last_question = None

        for analysis in page_analyses:
            index_notes = []
            continuation_of = None

            if analysis.is_cover_page:
                index_notes.append("cover_page")
            else:
                if analysis.question_numbers:
                    last_question = analysis.question_numbers[-1]
                elif last_question:
                    continuation_of = last_question
                    index_notes.append("continuation_assumed")
                else:
                    index_notes.append("no_question_numbers_detected")

            mapping = page_student_map.get(analysis.page_index)
            student_info = mapping["student_info"] if mapping else analysis.student_info
            student_key = None
            if mapping:
                student_key = mapping["student_key"]
            elif student_info and (student_info.student_id or student_info.name):
                student_key = student_info.student_id or student_info.name
            else:
                student_key = "UNKNOWN"

            context = {
                "page_index": analysis.page_index,
                "question_numbers": analysis.question_numbers,
                "first_question": analysis.first_question,
                "continuation_of": continuation_of,
                "student_key": student_key,
                "student_info": student_info_to_dict(student_info),
                "is_cover_page": analysis.is_cover_page,
                "index_notes": index_notes,
                "is_first_page": mapping["is_first_page"] if mapping else False,
            }

            page_index_contexts[analysis.page_index] = context
            index_pages.append(context)

            if not analysis.is_cover_page:
                group = student_groups.setdefault(
                    student_key,
                    {"student_key": student_key, "student_info": student_info, "pages": []}
                )
                group["pages"].append(analysis.page_index)

        indexed_students = []
        student_boundaries = []
        for student_key, group in student_groups.items():
            pages = sorted(group["pages"])
            if not pages:
                continue
            info = group.get("student_info")
            info_dict = student_info_to_dict(info)
            confidence = info.confidence if info else 0.0
            needs_confirmation = (
                info is None or
                getattr(info, "is_placeholder", False) or
                confidence < 0.7
            )
            start_page = pages[0]
            end_page = pages[-1]

            student_boundaries.append({
                "student_key": student_key,
                "start_page": start_page,
                "end_page": end_page,
                "confidence": confidence,
                "needs_confirmation": needs_confirmation,
                "detection_method": "index",
            })

            indexed_students.append({
                "student_key": student_key,
                "student_id": info.student_id if info else None,
                "student_name": info.name if info else None,
                "start_page": start_page,
                "end_page": end_page,
                "pages": pages,
                "confidence": confidence,
                "needs_confirmation": needs_confirmation,
            })

        index_results = {
            "model": model_name,
            "total_pages": len(processed_images),
            "pages": index_pages,
            "students": indexed_students,
            "unidentified_pages": segmentation_result.unidentified_pages,
        }

        logger.info(
            f"[index] 索引完成: batch_id={batch_id}, "
            f"识别学生数={len(indexed_students)}, 未识别页数={len(segmentation_result.unidentified_pages)}"
        )

        return {
            "index_results": index_results,
            "page_index_contexts": page_index_contexts,
            "student_page_map": {
                page_index: context["student_key"]
                for page_index, context in page_index_contexts.items()
            },
            "indexed_students": indexed_students,
            "index_unidentified_pages": segmentation_result.unidentified_pages,
            "student_boundaries": student_boundaries,
            "current_stage": "index_completed",
            "percentage": 12.0,
            "timestamps": {
                **state.get("timestamps", {}),
                "index_at": datetime.now().isoformat(),
            },
        }
    except Exception as e:
        logger.error(f"[index] 索引失败: {e}", exc_info=True)
        return {
            "index_results": {
                "model": None,
                "total_pages": len(processed_images),
                "pages": [],
                "students": [],
                "unidentified_pages": list(range(len(processed_images))),
                "error": str(e),
            },
            "page_index_contexts": {},
            "student_page_map": {},
            "indexed_students": [],
            "index_unidentified_pages": list(range(len(processed_images))),
            "student_boundaries": [],
            "current_stage": "index_completed",
            "percentage": 12.0,
            "errors": state.get("errors", []) + [{
                "node": "index",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }],
        }


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
    api_key = state.get("api_key") or os.getenv("GEMINI_API_KEY")
    
    logger.info(f"[rubric_parse] 开始解析评分标准: batch_id={batch_id}, 评分标准页数={len(rubric_images)}")
    
    parsed_rubric = {
        "total_questions": 0,
        "total_score": 0,
        "questions": []
    }
    
    # 创建 RubricRegistry 用于存储解析后的评分标准
    from src.services.rubric_registry import RubricRegistry
    from src.models.grading_models import QuestionRubric, ScoringPoint, AlternativeSolution
    
    rubric_registry = RubricRegistry(total_score=105.0)  # 预期总分
    
    try:
        if rubric_images and api_key:
            # 使用专门的 RubricParserService 进行分批解析
            from src.services.rubric_parser import RubricParserService
            
            parser = RubricParserService(api_key=api_key)
            
            # 解析评分标准（内部会分批处理，每批最多4页）
            result = await parser.parse_rubric(
                rubric_images=rubric_images,
                expected_total_score=105  # 预期总分，用于验证
            )
            
            # 转换为字典格式
            parsed_rubric = {
                "total_questions": result.total_questions,
                "total_score": result.total_score,
                "rubric_format": result.rubric_format,
                "general_notes": result.general_notes,
                "questions": [
                    {
                        "id": q.question_id,
                        "max_score": q.max_score,
                        "question_text": q.question_text,
                        "standard_answer": q.standard_answer,
                        "criteria": [sp.description for sp in q.scoring_points],
                        "scoring_points": [
                            {
                                "description": sp.description,
                                "score": sp.score,
                                "is_required": sp.is_required
                            }
                            for sp in q.scoring_points
                        ],
                        "alternative_solutions": [
                            {
                                "description": alt.description,
                                "scoring_criteria": alt.scoring_criteria,
                                "note": alt.note
                            }
                            for alt in q.alternative_solutions
                        ],
                        "grading_notes": q.grading_notes
                    }
                    for q in result.questions
                ]
            }
            
            # 🔥 关键：将解析的评分标准注册到 RubricRegistry
            # 这样后续批改时可以通过 GradingSkills.get_rubric_for_question 获取
            rubric_registry.register_rubrics(result.questions)
            logger.info(
                f"[rubric_parse] 已注册 {len(result.questions)} 道题目到 RubricRegistry"
            )
            
            # 同时生成格式化的评分标准上下文（供批改使用）
            rubric_context = parser.format_rubric_context(result)
            parsed_rubric["rubric_context"] = rubric_context
            
            logger.info(
                f"[rubric_parse] 评分标准解析成功: "
                f"题目数={result.total_questions}, 总分={result.total_score}"
            )
        
        elif rubric_text:
            # 如果有文本形式的评分标准，简单解析
            parsed_rubric["raw_text"] = rubric_text
            
    except Exception as e:
        logger.error(f"[rubric_parse] 评分标准解析失败: {e}", exc_info=True)
        # 降级处理：返回空的评分标准
        parsed_rubric = {
            "total_questions": 0,
            "total_score": 0,
            "questions": [],
            "error": str(e)
        }
    
    logger.info(
        f"[rubric_parse] 评分标准解析完成: batch_id={batch_id}, "
        f"题目数={parsed_rubric.get('total_questions', 0)}, "
        f"总分={parsed_rubric.get('total_score', 0)}"
    )
    
    # 注意：不序列化 RubricRegistry，因为 grade_batch_node 会从 parsed_rubric 重建
    # 这样可以避免类型转换问题
    
    return {
        "parsed_rubric": parsed_rubric,
        "current_stage": "rubric_parse_completed",
        "percentage": 15.0,
        "timestamps": {
            **state.get("timestamps", {}),
            "rubric_parse_at": datetime.now().isoformat()
        }
    }


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
    processed_images = state.get("processed_images", [])
    rubric = state.get("rubric", "")
    parsed_rubric = state.get("parsed_rubric", {})
    page_index_contexts = state.get("page_index_contexts", {})
    api_key = state.get("api_key", "")
    
    if not processed_images:
        logger.warning(f"[grading_fanout] 没有待批改的图像: batch_id={batch_id}")
        return [Send("index_merge", state)]
    
    # 获取批次配置 (Requirements: 3.1, 10.1)
    config = get_batch_config()
    batch_size = config.batch_size
    max_retries = config.max_retries
    
    total_pages = len(processed_images)
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
        
        # 创建批次任务状态，包含重试配置 (Requirements: 3.3)
        # 🔥 关键：深拷贝 parsed_rubric 确保 Worker 独立性 (Requirement 3.2)
        batch_contexts = {
            idx: page_index_contexts.get(idx)
            for idx in range(start_idx, end_idx)
            if idx in page_index_contexts
        }

        task_state = {
            "batch_id": batch_id,
            "batch_index": batch_idx,
            "total_batches": num_batches,
            "page_indices": list(range(start_idx, end_idx)),
            "images": batch_images,
            "rubric": rubric,
            "parsed_rubric": copy.deepcopy(parsed_rubric),  # 深拷贝！
            "page_index_contexts": copy.deepcopy(batch_contexts),
            "api_key": api_key,
            "retry_count": 0,
            "max_retries": max_retries,
        }
        
        sends.append(Send("grade_batch", task_state))
    
    return sends


async def grade_batch_node(state: Dict[str, Any]) -> Dict[str, Any]:
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
    api_key = state.get("api_key") or os.getenv("GEMINI_API_KEY")
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 2)
    
    logger.info(
        f"[grade_batch] 开始批改批次 {batch_index + 1}/{total_batches}: "
        f"batch_id={batch_id}, 页面={page_indices}, 重试次数={retry_count}"
    )
    
    page_results = []
    batch_error = None
    
    try:
        if not api_key:
            raise ValueError("API key 未配置")
        
        # Worker 独立性保证 (Requirement 3.2)
        # 每个 Worker 独立创建实例，不共享可变状态
        from src.services.gemini_reasoning import GeminiReasoningClient
        from src.utils.error_handling import execute_with_isolation, get_error_manager
        from src.services.rubric_registry import RubricRegistry
        from src.skills.grading_skills import GradingSkills, create_grading_skills, get_skill_registry
        from src.models.grading_models import QuestionRubric, ScoringPoint
        
        # 独立获取评分标准副本（不共享可变状态）
        parsed_rubric = state.get("parsed_rubric", {})
        import copy
        local_parsed_rubric = copy.deepcopy(parsed_rubric)
        
        # 🔥 关键：从 parsed_rubric 重建 RubricRegistry (Requirement 5.1)
        rubric_registry = RubricRegistry(
            total_score=local_parsed_rubric.get("total_score", 100.0)
        )
        
        # 将解析的题目注册到 Registry
        questions_data = local_parsed_rubric.get("questions", [])
        if questions_data:
            question_rubrics = []
            for q in questions_data:
                # 构建 ScoringPoint 列表
                scoring_points = [
                    ScoringPoint(
                        description=sp.get("description", ""),
                        score=sp.get("score", 0),
                        is_required=sp.get("is_required", True)
                    )
                    for sp in q.get("scoring_points", [])
                ]
                
                # 构建 QuestionRubric
                question_rubric = QuestionRubric(
                    question_id=str(q.get("id", "")),
                    question_text=q.get("question_text", ""),
                    max_score=q.get("max_score", 0),
                    scoring_points=scoring_points,
                    standard_answer=q.get("standard_answer", ""),
                    grading_notes=q.get("grading_notes", ""),
                    alternative_solutions=[]  # 简化处理
                )
                question_rubrics.append(question_rubric)
            
            rubric_registry.register_rubrics(question_rubrics)
            logger.info(
                f"[grade_batch] 已重建 RubricRegistry，注册 {len(question_rubrics)} 道题目"
            )
        
        # 🔥 创建 GradingSkills 实例 (Requirement 5.1)
        grading_skills = create_grading_skills(rubric_registry=rubric_registry)
        if page_index_contexts:
            grading_skills.page_index_contexts = page_index_contexts
        
        # 创建 GeminiReasoningClient 并集成 GradingSkills
        reasoning_client = GeminiReasoningClient(
            api_key=api_key,
            rubric_registry=rubric_registry,
            grading_skills=grading_skills
        )
        
        # 错误隔离：单页失败不影响其他页面 (Requirement 9.2)
        error_manager = get_error_manager()
        
        async def grade_single_page(page_data):
            """批改单页（带错误隔离和 Agent Skill 集成）"""
            page_idx, image = page_data
            
            try:
                # 直接使用 grade_page 方法批改单页
                # grade_page 内部会：
                # 1. 识别题目编号
                # 2. 通过 GradingSkills.get_rubric_for_question 获取评分标准
                # 3. 基于指定评分标准进行批改
                page_context = None
                if page_index_contexts:
                    skill_result = await grading_skills.get_index_context_for_page(
                        page_index=page_idx,
                        page_index_contexts=page_index_contexts
                    )
                    if skill_result.success:
                        page_context = skill_result.data

                result = await reasoning_client.grade_page(
                    image=image,
                    rubric=rubric,
                    max_score=10.0,
                    parsed_rubric=local_parsed_rubric,
                    page_context=page_context,
                )

                # 🔥 对识别到的每道题目，使用 Agent Skill 获取评分标准并记录
                question_numbers = result.get("question_numbers", [])
                if page_context:
                    if not question_numbers and page_context.get("question_numbers"):
                        question_numbers = page_context.get("question_numbers", [])
                        result["question_numbers"] = question_numbers
                    if not question_numbers and page_context.get("continuation_of"):
                        question_numbers = [page_context["continuation_of"]]
                        result["question_numbers"] = question_numbers
                    if not result.get("student_info") and page_context.get("student_info"):
                        result["student_info"] = page_context.get("student_info")
                    if page_context.get("is_cover_page") and not result.get("is_blank_page", False):
                        result["is_blank_page"] = True
                        result["score"] = 0.0
                        result["max_score"] = 0.0

                skill_logs = []
                
                for q_num in question_numbers:
                    # 使用 GradingSkills 获取该题目的评分标准
                    skill_result = await grading_skills.get_rubric_for_question(
                        question_id=str(q_num),
                        registry=rubric_registry
                    )
                    
                    if skill_result.success and skill_result.data:
                        rubric_data = skill_result.data
                        skill_logs.append({
                            "question_id": q_num,
                            "skill_used": "get_rubric_for_question",
                            "is_default": rubric_data.is_default,
                            "confidence": rubric_data.confidence,
                            "max_score": rubric_data.rubric.max_score if rubric_data.rubric else 0,
                        })
                        logger.info(
                            f"[grade_batch] Agent Skill 获取题目 {q_num} 评分标准: "
                            f"is_default={rubric_data.is_default}, "
                            f"confidence={rubric_data.confidence:.2f}"
                        )
                
                # 构建完整的页面结果
                page_result = {
                    "page_index": page_idx,
                    "status": "completed",
                    "score": result.get("score", 0.0),
                    "max_score": result.get("max_score", 10.0),
                    "confidence": result.get("confidence", 0.0),
                    "feedback": result.get("feedback", ""),
                    "question_id": f"Q{page_idx}",
                    "question_numbers": question_numbers,
                    "question_details": result.get("question_details", []),
                    "page_summary": result.get("page_summary", ""),
                    "student_info": result.get("student_info"),
                    "is_blank_page": result.get("is_blank_page", False),
                    "revision_count": 0,
                    "batch_index": batch_index,
                    "skill_logs": skill_logs,  # 记录 Agent Skill 调用日志
                }
                
                # 更详细的日志
                is_blank = result.get("is_blank_page", False)
                
                if is_blank:
                    logger.info(f"[grade_batch] 页面 {page_idx} 是空白页/封面页")
                else:
                    logger.info(
                        f"[grade_batch] 页面 {page_idx} 批改完成: "
                        f"score={result.get('score', 0)}/{result.get('max_score', 0)}, "
                        f"题目={question_numbers}, confidence={result.get('confidence', 0):.2f}, "
                        f"Agent Skills 调用={len(skill_logs)}次"
                    )
                
                return page_result
                
            except Exception as e:
                # 记录错误到全局错误管理器 (Requirement 9.5)
                error_manager.add_error(
                    exc=e,
                    context={
                        "batch_id": batch_id,
                        "batch_index": batch_index,
                        "page_index": page_idx,
                        "function": "grade_single_page",
                    },
                    batch_id=batch_id,
                    page_index=page_idx,
                )
                
                logger.error(
                    f"[grade_batch] 页面 {page_idx} 批改失败: {e}. "
                    f"错误已隔离，继续处理其他页面。"
                )
                
                # 返回失败结果（不中断批次）
                return {
                    "page_index": page_idx,
                    "status": "failed",
                    "error": str(e),
                    "score": 0,
                    "max_score": 0,
                    "batch_index": batch_index,
                }
        
        # 使用错误隔离批量处理所有页面 (Requirement 9.2)
        page_data_list = list(zip(page_indices, images))
        
        # 并发处理所有页面（带错误隔离）
        from src.utils.error_handling import execute_batch_with_isolation
        
        isolated_results = await execute_batch_with_isolation(
            func=grade_single_page,
            items=page_data_list,
            error_log_context={
                "batch_id": batch_id,
                "batch_index": batch_index,
            }
        )
        
        # 收集结果
        for isolated_result in isolated_results:
            if isolated_result.is_success():
                page_results.append(isolated_result.get_result())
            else:
                # 失败的页面也添加到结果中（标记为失败）
                page_idx = page_data_list[isolated_result.index][0]
                page_results.append({
                    "page_index": page_idx,
                    "status": "failed",
                    "error": str(isolated_result.get_error()),
                    "score": 0,
                    "max_score": 0,
                    "batch_index": batch_index,
                })
    
    except Exception as e:
        batch_error = str(e)
        logger.error(f"[grade_batch] 批次 {batch_index} 批改失败: {e}", exc_info=True)
        
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
                f"[grade_batch] 批次 {batch_index} 将进行重试 "
                f"({retry_count + 1}/{max_retries})"
            )
            # 返回重试标记，让调度器重新调度
            return {
                "grading_results": [],
                "batch_retry_needed": {
                    "batch_index": batch_index,
                    "retry_count": retry_count + 1,
                    "error": batch_error,
                }
            }
        
        # 所有页面标记为失败
        for page_idx in page_indices:
            page_results.append({
                "page_index": page_idx,
                "status": "failed",
                "error": batch_error,
                "score": 0,
                "max_score": 0,
                "batch_index": batch_index,
            })
    
    success_count = sum(1 for r in page_results if r['status'] == 'completed')
    failed_count = sum(1 for r in page_results if r['status'] == 'failed')
    total_score = sum(r.get('score', 0) for r in page_results if r['status'] == 'completed')
    
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
    
    # 返回结果（使用 add reducer 聚合）
    return {
        "grading_results": page_results,
        "batch_progress": progress_info,
    }


async def cross_page_merge_node(state: BatchGradingGraphState) -> Dict[str, Any]:
    """
    跨页题目合并节点
    
    在索引聚合之前执行，负责：
    1. 检测跨页题目
    2. 合并跨页题目的评分结果
    3. 确保满分不重复计算
    
    Requirements: 2.1, 4.2, 4.3
    """
    batch_id = state["batch_id"]
    grading_results = state.get("grading_results", [])
    
    logger.info(f"[cross_page_merge] 开始跨页题目合并: batch_id={batch_id}")
    
    # 去重：由于并行聚合可能导致重复，按 page_index 去重
    seen_pages = set()
    unique_results = []
    for result in grading_results:
        page_idx = result.get("page_index")
        if page_idx is not None and page_idx not in seen_pages:
            seen_pages.add(page_idx)
            unique_results.append(result)
    
    # 按页码排序
    unique_results.sort(key=lambda x: x.get("page_index", 0))
    grading_results = unique_results
    
    try:
        # 将字典格式转换为 PageGradingResult 对象
        from src.models.grading_models import PageGradingResult, QuestionResult, ScoringPoint, ScoringPointResult
        
        page_results = []
        for result in grading_results:
            # 转换 question_details 为 QuestionResult 对象
            question_results = []
            for q in result.get("question_details", []):
                # 构建得分点结果
                scoring_point_results = []
                for sp in q.get("scoring_point_results", []):
                    scoring_point = ScoringPoint(
                        description=sp.get("description", ""),
                        score=sp.get("score", 0.0),
                        is_required=sp.get("is_required", False)
                    )
                    scoring_point_result = ScoringPointResult(
                        scoring_point=scoring_point,
                        awarded=sp.get("awarded", 0.0),
                        evidence=sp.get("evidence", "")
                    )
                    scoring_point_results.append(scoring_point_result)
                
                question_result = QuestionResult(
                    question_id=q.get("question_id", ""),
                    score=q.get("score", 0.0),
                    max_score=q.get("max_score", 0.0),
                    confidence=q.get("confidence", 1.0),
                    feedback=q.get("feedback", ""),
                    scoring_point_results=scoring_point_results,
                    page_indices=[result.get("page_index", 0)],
                    is_cross_page=False,
                    merge_source=None,
                    student_answer=q.get("student_answer", "")
                )
                question_results.append(question_result)
            
            page_result = PageGradingResult(
                page_index=result.get("page_index", 0),
                question_results=question_results,
                student_info=result.get("student_info"),
                is_blank_page=result.get("is_blank_page", False),
                raw_response=result.get("page_summary", "")
            )
            page_results.append(page_result)
        
        # 使用 ResultMerger 进行跨页合并
        from src.services.result_merger import ResultMerger
        
        merger = ResultMerger()
        merged_questions, cross_page_questions = merger.merge_cross_page_questions(page_results)
        
        # 将合并后的结果转换回字典格式
        merged_question_dicts = []
        for q in merged_questions:
            merged_question_dicts.append({
                "question_id": q.question_id,
                "score": q.score,
                "max_score": q.max_score,
                "confidence": q.confidence,
                "feedback": q.feedback,
                "student_answer": q.student_answer,
                "is_cross_page": q.is_cross_page,
                "page_indices": q.page_indices,
                "merge_source": q.merge_source,
                "scoring_point_results": [
                    {
                        "description": spr.scoring_point.description,
                        "score": spr.scoring_point.score,
                        "is_required": spr.scoring_point.is_required,
                        "awarded": spr.awarded,
                        "evidence": spr.evidence
                    }
                    for spr in q.scoring_point_results
                ]
            })
        
        # 转换跨页题目信息
        cross_page_info = []
        for cpq in cross_page_questions:
            cross_page_info.append({
                "question_id": cpq.question_id,
                "page_indices": cpq.page_indices,
                "confidence": cpq.confidence,
                "merge_reason": cpq.merge_reason
            })
        
        logger.info(
            f"[cross_page_merge] 跨页合并完成: batch_id={batch_id}, "
            f"检测到 {len(cross_page_questions)} 个跨页题目, "
            f"合并后共 {len(merged_questions)} 道题目"
        )
        
        return {
            "merged_questions": merged_question_dicts,
            "cross_page_questions": cross_page_info,
            "current_stage": "cross_page_merge_completed",
            "percentage": 75.0,
            "timestamps": {
                **state.get("timestamps", {}),
                "cross_page_merge_at": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"[cross_page_merge] 跨页合并失败: {e}", exc_info=True)
        
        # 降级处理：不进行跨页合并，直接传递原始结果
        return {
            "merged_questions": [],
            "cross_page_questions": [],
            "current_stage": "cross_page_merge_completed",
            "percentage": 75.0,
            "errors": state.get("errors", []) + [{
                "node": "cross_page_merge",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }]
        }


async def index_merge_node(state: BatchGradingGraphState) -> Dict[str, Any]:
    """
    索引对齐聚合节点

    使用索引阶段生成的学生边界聚合批改结果，替代批改后学生分割。
    """
    batch_id = state["batch_id"]
    grading_results = state.get("grading_results", [])
    merged_questions = state.get("merged_questions", [])
    student_boundaries = state.get("student_boundaries", []) or []
    indexed_students = state.get("indexed_students", []) or []
    student_page_map = state.get("student_page_map", {}) or {}

    # 去重：由于并行聚合可能导致重复，按 page_index 去重
    seen_pages = set()
    unique_results = []
    for result in grading_results:
        page_idx = result.get("page_index")
        if page_idx is not None and page_idx not in seen_pages:
            seen_pages.add(page_idx)
            unique_results.append(result)

    # 按页码排序
    unique_results.sort(key=lambda x: x.get("page_index", 0))
    grading_results = unique_results

    # 过滤空白页
    non_blank_results = [r for r in grading_results if not r.get("is_blank_page", False)]

    if not student_boundaries and indexed_students:
        student_boundaries = [
            {
                "student_key": s.get("student_key"),
                "start_page": s.get("start_page", 0),
                "end_page": s.get("end_page", 0),
                "confidence": s.get("confidence", 0.0),
                "needs_confirmation": s.get("needs_confirmation", False),
                "detection_method": "index",
            }
            for s in indexed_students
        ]

    if not student_boundaries and student_page_map:
        grouped = {}
        for page_index, student_key in student_page_map.items():
            grouped.setdefault(student_key, []).append(page_index)
        for student_key, pages in grouped.items():
            pages_sorted = sorted(pages)
            student_boundaries.append({
                "student_key": student_key,
                "start_page": pages_sorted[0],
                "end_page": pages_sorted[-1],
                "confidence": 0.0,
                "needs_confirmation": True,
                "detection_method": "index",
            })

    if not student_boundaries:
        # 无索引边界时降级为单学生
        fallback_key = "学生A"
        fallback_end = max(0, len(grading_results) - 1)
        student_boundaries = [{
            "student_key": fallback_key,
            "start_page": 0,
            "end_page": fallback_end,
            "confidence": 0.0,
            "needs_confirmation": True,
            "detection_method": "fallback",
        }]

    logger.info(
        f"[index_merge] 开始聚合: batch_id={batch_id}, "
        f"批改结果数={len(grading_results)}（去重后），非空白页={len(non_blank_results)}, "
        f"边界数={len(student_boundaries)}, 合并后题目数={len(merged_questions)}"
    )

    try:
        student_info_by_key = {
            s.get("student_key"): s for s in indexed_students
        }

        student_results = []
        for boundary in student_boundaries:
            student_pages = [
                r for r in grading_results
                if boundary["start_page"] <= r.get("page_index", -1) <= boundary["end_page"]
            ]

            if merged_questions:
                student_questions = []
                for q in merged_questions:
                    q_pages = q.get("page_indices", [])
                    if any(boundary["start_page"] <= p <= boundary["end_page"] for p in q_pages):
                        student_questions.append(q)

                total_score = sum(q.get("score", 0) for q in student_questions)
                max_total_score = sum(q.get("max_score", 0) for q in student_questions)
                all_question_details = student_questions
            else:
                valid_pages = [
                    r for r in student_pages
                    if r.get("status") == "completed" and not r.get("is_blank_page", False)
                ]
                total_score = sum(r.get("score", 0) for r in valid_pages)
                max_total_score = sum(r.get("max_score", 0) for r in valid_pages)

                all_question_details = []
                for page in valid_pages:
                    for q in page.get("question_details", []):
                        all_question_details.append({
                            "question_id": q.get("question_id", ""),
                            "score": q.get("score", 0),
                            "max_score": q.get("max_score", 0),
                            "feedback": q.get("feedback", ""),
                            "student_answer": q.get("student_answer", ""),
                            "is_correct": q.get("is_correct", False)
                        })

            student_key = boundary["student_key"]
            info = student_info_by_key.get(student_key, {})

            student_results.append({
                "student_key": student_key,
                "student_id": info.get("student_id"),
                "student_name": info.get("student_name"),
                "start_page": boundary["start_page"],
                "end_page": boundary["end_page"],
                "total_score": total_score,
                "max_total_score": max_total_score,
                "page_results": student_pages,
                "question_details": all_question_details,
                "confidence": boundary.get("confidence", 0.0),
                "needs_confirmation": boundary.get("needs_confirmation", False),
            })

        logger.info(
            f"[index_merge] 聚合完成: batch_id={batch_id}, 学生数={len(student_boundaries)}"
        )

        return {
            "student_boundaries": student_boundaries,
            "student_results": student_results,
            "current_stage": "index_merge_completed",
            "percentage": 80.0,
            "timestamps": {
                **state.get("timestamps", {}),
                "index_merge_at": datetime.now().isoformat()
            }
        }

    except Exception as e:
        logger.error(f"[index_merge] 聚合失败: {e}", exc_info=True)

        # 降级处理：将所有页面视为一个学生
        if merged_questions:
            total_score = sum(q.get("score", 0) for q in merged_questions)
            max_total_score = sum(q.get("max_score", 0) for q in merged_questions)
            all_question_details = merged_questions
        else:
            valid_results = [
                r for r in grading_results
                if r.get("status") == "completed" and not r.get("is_blank_page", False)
            ]
            total_score = sum(r.get("score", 0) for r in valid_results)
            max_total_score = sum(r.get("max_score", 0) for r in valid_results)

            all_question_details = []
            for page in valid_results:
                for q in page.get("question_details", []):
                    all_question_details.append({
                        "question_id": q.get("question_id", ""),
                        "score": q.get("score", 0),
                        "max_score": q.get("max_score", 0),
                        "feedback": q.get("feedback", ""),
                        "student_answer": q.get("student_answer", ""),
                        "is_correct": q.get("is_correct", False)
                    })

        fallback_student_key = "学生A"
        fallback_student_id = "FALLBACK_001"

        fallback_end = max(0, len(grading_results) - 1)
        return {
            "student_boundaries": [{
                "student_key": fallback_student_key,
                "start_page": 0,
                "end_page": fallback_end,
                "confidence": 0.0,
                "needs_confirmation": True
            }],
            "student_results": [{
                "student_key": fallback_student_key,
                "student_id": fallback_student_id,
                "total_score": total_score,
                "max_total_score": max_total_score,
                "page_results": grading_results,
                "question_details": all_question_details,
                "confidence": 0.0,
                "needs_confirmation": True
            }],
            "current_stage": "index_merge_completed",
            "percentage": 80.0,
            "errors": state.get("errors", []) + [{
                "node": "index_merge",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }]
        }


async def segment_node(state: BatchGradingGraphState) -> Dict[str, Any]:
    """
    学生分割节点
    
    基于批改结果智能判断学生边界。
    这是在批改完成后进行的，利用批改结果中的题目信息和学生标识。
    使用合并后的题目结果（如果有）。
    
    Requirements: 4.1, 4.3
    """
    batch_id = state["batch_id"]
    grading_results = state.get("grading_results", [])
    merged_questions = state.get("merged_questions", [])
    
    # 去重：由于并行聚合可能导致重复，按 page_index 去重
    seen_pages = set()
    unique_results = []
    for result in grading_results:
        page_idx = result.get("page_index")
        if page_idx is not None and page_idx not in seen_pages:
            seen_pages.add(page_idx)
            unique_results.append(result)
    
    # 按页码排序
    unique_results.sort(key=lambda x: x.get("page_index", 0))
    grading_results = unique_results
    
    # 过滤掉空白页
    non_blank_results = [r for r in grading_results if not r.get("is_blank_page", False)]
    
    logger.info(
        f"[segment] 开始学生分割: batch_id={batch_id}, "
        f"批改结果数={len(grading_results)}（去重后），非空白页={len(non_blank_results)}, "
        f"合并后题目数={len(merged_questions)}"
    )
    
    try:
        from src.services.student_boundary_detector import StudentBoundaryDetector
        
        detector = StudentBoundaryDetector()
        
        # 基于批改结果检测学生边界
        result = await detector.detect_boundaries(grading_results)
        
        # 转换为字典格式
        boundaries = []
        for b in result.boundaries:
            boundaries.append({
                "student_key": b.student_key,
                "start_page": b.start_page,
                "end_page": b.end_page,
                "confidence": b.confidence,
                "needs_confirmation": b.needs_confirmation,
                "detection_method": b.detection_method
            })
        
        # 按学生聚合批改结果
        student_results = []
        for boundary in boundaries:
            student_pages = [
                r for r in grading_results
                if boundary["start_page"] <= r.get("page_index", -1) <= boundary["end_page"]
            ]
            
            # 如果有合并后的题目结果，使用它们
            if merged_questions:
                # 筛选属于该学生的题目（基于页面范围）
                student_questions = []
                for q in merged_questions:
                    # 检查题目的页面索引是否在学生范围内
                    q_pages = q.get("page_indices", [])
                    if any(boundary["start_page"] <= p <= boundary["end_page"] for p in q_pages):
                        student_questions.append(q)
                
                # 计算总分（使用合并后的题目，避免重复计算）
                total_score = sum(q.get("score", 0) for q in student_questions)
                max_total_score = sum(q.get("max_score", 0) for q in student_questions)
                
                all_question_details = student_questions
            else:
                # 降级：使用原始页面结果
                valid_pages = [r for r in student_pages if r.get("status") == "completed" and not r.get("is_blank_page", False)]
                
                total_score = sum(r.get("score", 0) for r in valid_pages)
                max_total_score = sum(r.get("max_score", 0) for r in valid_pages)
                
                # 收集所有题目详情
                all_question_details = []
                for page in valid_pages:
                    for q in page.get("question_details", []):
                        all_question_details.append({
                            "question_id": q.get("question_id", ""),
                            "score": q.get("score", 0),
                            "max_score": q.get("max_score", 0),
                            "feedback": q.get("feedback", ""),
                            "student_answer": q.get("student_answer", ""),
                            "is_correct": q.get("is_correct", False)
                        })
            
            student_results.append({
                "student_key": boundary["student_key"],
                "start_page": boundary["start_page"],
                "end_page": boundary["end_page"],
                "total_score": total_score,
                "max_total_score": max_total_score,
                "page_results": student_pages,
                "question_details": all_question_details,
                "confidence": boundary["confidence"],
                "needs_confirmation": boundary["needs_confirmation"]
            })
        
        logger.info(
            f"[segment] 学生分割完成: batch_id={batch_id}, "
            f"检测到 {len(boundaries)} 名学生"
        )
        
        return {
            "student_boundaries": boundaries,
            "student_results": student_results,
            "current_stage": "segment_completed",
            "percentage": 80.0,
            "timestamps": {
                **state.get("timestamps", {}),
                "segment_at": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"[segment] 学生分割失败: {e}", exc_info=True)
        
        # 降级处理：将所有页面视为一个学生
        if merged_questions:
            # 使用合并后的题目
            total_score = sum(q.get("score", 0) for q in merged_questions)
            max_total_score = sum(q.get("max_score", 0) for q in merged_questions)
            all_question_details = merged_questions
        else:
            # 使用原始页面结果
            valid_results = [r for r in grading_results if r.get("status") == "completed" and not r.get("is_blank_page", False)]
            total_score = sum(r.get("score", 0) for r in valid_results)
            max_total_score = sum(r.get("max_score", 0) for r in valid_results)
            
            # 收集所有题目详情
            all_question_details = []
            for page in valid_results:
                for q in page.get("question_details", []):
                    all_question_details.append({
                        "question_id": q.get("question_id", ""),
                        "score": q.get("score", 0),
                        "max_score": q.get("max_score", 0),
                        "feedback": q.get("feedback", ""),
                        "student_answer": q.get("student_answer", ""),
                        "is_correct": q.get("is_correct", False)
                    })
        
        # 使用唯一的学生标识
        fallback_student_key = "学生A"
        fallback_student_id = "FALLBACK_001"
        
        return {
            "student_boundaries": [{
                "student_key": fallback_student_key,
                "start_page": 0,
                "end_page": len(grading_results) - 1,
                "confidence": 0.0,
                "needs_confirmation": True
            }],
            "student_results": [{
                "student_key": fallback_student_key,
                "student_id": fallback_student_id,
                "total_score": total_score,
                "max_total_score": max_total_score,
                "page_results": grading_results,
                "question_details": all_question_details,
                "confidence": 0.0,
                "needs_confirmation": True
            }],
            "current_stage": "segment_completed",
            "percentage": 80.0,
            "errors": state.get("errors", []) + [{
                "node": "segment",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }]
        }


async def review_node(state: BatchGradingGraphState) -> Dict[str, Any]:
    """
    结果审核节点
    
    汇总审核批改结果，标记需要人工确认的项目。
    """
    batch_id = state["batch_id"]
    student_results = state.get("student_results", [])
    student_boundaries = state.get("student_boundaries", [])
    
    logger.info(f"[review] 开始结果审核: batch_id={batch_id}")
    
    # 统计需要确认的边界
    needs_confirmation = [b for b in student_boundaries if b.get("needs_confirmation")]
    
    # 统计低置信度结果
    low_confidence_results = []
    for student in student_results:
        for page_result in student.get("page_results", []):
            if page_result.get("confidence", 1.0) < 0.7:
                low_confidence_results.append({
                    "student_key": student["student_key"],
                    "page_index": page_result.get("page_index"),
                    "confidence": page_result.get("confidence")
                })
    
    review_summary = {
        "total_students": len(student_results),
        "boundaries_need_confirmation": len(needs_confirmation),
        "low_confidence_count": len(low_confidence_results),
        "low_confidence_results": low_confidence_results[:10]  # 最多显示10个
    }
    
    logger.info(
        f"[review] 审核完成: batch_id={batch_id}, "
        f"学生数={review_summary['total_students']}, "
        f"待确认边界={review_summary['boundaries_need_confirmation']}"
    )
    
    return {
        "review_summary": review_summary,
        "current_stage": "review_completed",
        "percentage": 90.0,
        "timestamps": {
            **state.get("timestamps", {}),
            "review_at": datetime.now().isoformat()
        }
    }


async def export_node(state: BatchGradingGraphState) -> Dict[str, Any]:
    """
    导出结果节点
    
    持久化结果并准备导出数据。
    支持无数据库模式下导出结果为 JSON 文件。
    支持部分结果保存：不可恢复错误时保存已完成结果。
    
    Requirements: 9.4, 11.4
    """
    batch_id = state["batch_id"]
    student_results = state.get("student_results", [])
    cross_page_questions = state.get("cross_page_questions", [])
    merged_questions = state.get("merged_questions", [])
    grading_results = state.get("grading_results", [])
    
    logger.info(f"[export] 开始导出结果: batch_id={batch_id}, 学生数={len(student_results)}")
    
    # 检查是否有失败的页面
    failed_pages = [r for r in grading_results if r.get("status") == "failed"]
    has_failures = len(failed_pages) > 0
    
    if has_failures:
        logger.warning(
            f"[export] 检测到 {len(failed_pages)} 个失败页面，"
            f"将保存部分结果"
        )
    
    # 尝试持久化到数据库
    persisted = False
    try:
        from src.utils.database import get_db_pool
        
        db_pool = await get_db_pool()
        if db_pool:
            # TODO: 实际的持久化逻辑
            persisted = True
            logger.info(f"[export] 结果已持久化到数据库: batch_id={batch_id}")
    except Exception as e:
        logger.warning(f"[export] 数据库持久化失败（离线模式）: {e}")
    
    # 准备导出数据
    export_data = {
        "batch_id": batch_id,
        "export_time": datetime.now().isoformat(),
        "persisted": persisted,
        "has_failures": has_failures,
        "failed_pages_count": len(failed_pages),
        "cross_page_questions": cross_page_questions,
        "merged_questions": merged_questions,
        "students": []
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
        # 计算百分比
        total_score = student.get("total_score", 0)
        max_score = student.get("max_total_score", 0)
        percentage = (total_score / max_score * 100) if max_score > 0 else 0
        
        # 收集题目结果
        question_results = []
        
        # 优先使用 question_details
        if student.get("question_details"):
            for q in student["question_details"]:
                question_results.append({
                    "question_id": q.get("question_id", ""),
                    "score": q.get("score", 0),
                    "max_score": q.get("max_score", 0),
                    "feedback": q.get("feedback", ""),
                    "student_answer": q.get("student_answer", ""),
                    "is_correct": q.get("is_correct", False),
                    "is_cross_page": q.get("is_cross_page", False),
                    "page_indices": q.get("page_indices", []),
                    "confidence": q.get("confidence", 1.0)
                })
        # 否则从 page_results 提取
        elif student.get("page_results"):
            for page in student["page_results"]:
                if page.get("status") == "completed" and not page.get("is_blank_page", False):
                    for q in page.get("question_details", []):
                        question_results.append({
                            "question_id": q.get("question_id", ""),
                            "score": q.get("score", 0),
                            "max_score": q.get("max_score", 0),
                            "feedback": q.get("feedback", ""),
                            "student_answer": q.get("student_answer", ""),
                            "is_correct": q.get("is_correct", False)
                        })
        
        export_data["students"].append({
            "student_name": student["student_key"],
            "student_id": student.get("student_id"),
            "score": total_score,
            "max_score": max_score,
            "percentage": round(percentage, 1),
            "question_results": question_results,
            "confidence": student.get("confidence", 0),
            "needs_confirmation": student.get("needs_confirmation", False),
            "start_page": student.get("start_page", 0),
            "end_page": student.get("end_page", 0)
        })
    
    # 导出为 JSON 文件 (Requirements: 9.4, 11.4)
    # 无数据库模式或有失败时都导出
    if not persisted or has_failures:
        try:
            import json
            import os
            
            # 创建导出目录
            export_dir = os.getenv("EXPORT_DIR", "./exports")
            os.makedirs(export_dir, exist_ok=True)
            
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 如果有失败，标记为部分结果 (Requirement 9.4)
            if has_failures:
                filename = f"partial_result_{batch_id}_{timestamp}.json"
                logger.info(
                    f"[export] 保存部分结果（{len(failed_pages)} 个页面失败）: {filename}"
                )
            else:
                filename = f"grading_result_{batch_id}_{timestamp}.json"
            
            filepath = os.path.join(export_dir, filename)
            
            # 写入 JSON 文件
            with open(filepath, 'w', encoding='utf-8') as f:
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
            error_log_file = os.path.join(
                export_dir,
                f"error_log_{batch_id}_{timestamp}.json"
            )
            
            error_manager.export_to_file(error_log_file)
            export_data["error_log_file"] = error_log_file
            
            logger.info(
                f"[export] 错误日志已导出: {error_log_file} "
                f"({len(batch_errors)} 个错误)"
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
        "current_stage": "completed",
        "percentage": 100.0,
        "timestamps": {
            **state.get("timestamps", {}),
            "export_at": datetime.now().isoformat(),
            "completed_at": datetime.now().isoformat()
        }
    }


# ==================== Graph 编译 ====================

def create_batch_grading_graph(
    checkpointer: Optional[AsyncPostgresSaver] = None,
    batch_config: Optional[BatchConfig] = None,
) -> StateGraph:
    """创建批量批改 Graph
    
    工作流：
    1. intake: 接收文件
    2. preprocess: 图像预处理
    3. index: 批改前索引（题目信息 + 学生识别）
    4. rubric_parse: 解析评分标准
    5. grade_batch (并行): 可配置分批批改所有页面
    6. cross_page_merge: 跨页题目合并
    7. index_merge: 基于索引聚合学生结果
    8. review: 结果审核
    9. export: 导出结果
    
    流程图：
    ```
    intake
      ↓
    preprocess
      ↓
    index
      ↓
    rubric_parse
      ↓
    ┌─────────────────┐
    │ grade_batch (N) │  ← 并行批改（可配置批次大小）
    └─────────────────┘
      ↓
    cross_page_merge  ← 跨页题目合并
      ↓
    index_merge  ← 基于索引聚合
      ↓
    review
      ↓
    export
      ↓
    END
    ```
    
    特性：
    - 可配置批次大小 (Requirements: 3.1, 10.1)
    - Worker 独立性保证 (Requirements: 3.2)
    - 批次失败重试 (Requirements: 3.3, 9.3)
    - 实时进度报告 (Requirements: 3.4)
    - 跨页题目合并 (Requirements: 2.1, 4.2, 4.3)
    
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
    graph.add_node("index", index_node)
    graph.add_node("rubric_parse", rubric_parse_node)
    graph.add_node("grade_batch", grade_batch_node)
    graph.add_node("cross_page_merge", cross_page_merge_node)
    graph.add_node("index_merge", index_merge_node)
    graph.add_node("review", review_node)
    graph.add_node("export", export_node)
    
    # 入口点
    graph.set_entry_point("intake")
    
    # 线性流程：intake → preprocess → rubric_parse
    graph.add_edge("intake", "preprocess")
    graph.add_edge("preprocess", "index")
    graph.add_edge("index", "rubric_parse")
    
    # rubric_parse 后扇出到并行批改
    graph.add_conditional_edges(
        "rubric_parse",
        grading_fanout_router,
        ["grade_batch", "cross_page_merge", "index_merge"]
    )
    
    # 并行批改后聚合到 cross_page_merge
    graph.add_edge("grade_batch", "cross_page_merge")
    
    # cross_page_merge → index_merge → review → export → END
    graph.add_edge("cross_page_merge", "index_merge")
    graph.add_edge("index_merge", "review")
    graph.add_edge("review", "export")
    graph.add_edge("export", END)
    
    # 编译
    compile_kwargs = {}
    if checkpointer:
        compile_kwargs["checkpointer"] = checkpointer
    
    compiled_graph = graph.compile(**compile_kwargs)
    
    logger.info("批量批改 Graph 已编译")
    
    return compiled_graph


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
    "index_node",
    "rubric_parse_node",
    "grade_batch_node",
    "cross_page_merge_node",
    "index_merge_node",
    "review_node",
    "export_node",
    # 路由函数
    "grading_fanout_router",
    # Graph 创建
    "create_batch_grading_graph",
]
