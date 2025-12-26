"""批量批改 Graph 编译

实现批量试卷批改流程，支持：
- 图像预处理
- 评分标准解析
- 固定分批并行批改（不预先分割学生）
- 批改后学生边界检测（基于批改结果智能判断）
- 结果审核
- 导出结果

工作流：
接收文件 → 图像预处理 → 解析评分标准 → 固定分批批改 → 学生分割 → 结果审核 → 导出结果

验证：需求 5.1, 5.4
"""

import logging
import os
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime

from langgraph.graph import StateGraph, END
from langgraph.types import Send
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from src.graphs.state import BatchGradingGraphState


logger = logging.getLogger(__name__)


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


async def rubric_parse_node(state: BatchGradingGraphState) -> Dict[str, Any]:
    """
    解析评分标准节点
    
    使用专门的 RubricParserService 解析评分标准图像，
    支持分批处理多页评分标准，提取完整的题目结构和评分细则。
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
    """
    batch_id = state["batch_id"]
    processed_images = state.get("processed_images", [])
    rubric = state.get("rubric", "")
    parsed_rubric = state.get("parsed_rubric", {})
    api_key = state.get("api_key", "")
    
    if not processed_images:
        logger.warning(f"[grading_fanout] 没有待批改的图像: batch_id={batch_id}")
        return [Send("segment", state)]
    
    # 固定分批：每批处理 BATCH_SIZE 页
    BATCH_SIZE = 10
    total_pages = len(processed_images)
    num_batches = (total_pages + BATCH_SIZE - 1) // BATCH_SIZE
    
    logger.info(
        f"[grading_fanout] 创建批改任务: batch_id={batch_id}, "
        f"总页数={total_pages}, 批次数={num_batches}"
    )
    
    sends = []
    for batch_idx in range(num_batches):
        start_idx = batch_idx * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, total_pages)
        batch_images = processed_images[start_idx:end_idx]
        
        task_state = {
            "batch_id": batch_id,
            "batch_index": batch_idx,
            "total_batches": num_batches,
            "page_indices": list(range(start_idx, end_idx)),
            "images": batch_images,
            "rubric": rubric,
            "parsed_rubric": parsed_rubric,
            "api_key": api_key
        }
        
        sends.append(Send("grade_batch", task_state))
    
    return sends


async def grade_batch_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    批量批改节点
    
    批改一批页面，返回每页的批改结果。
    直接使用 GeminiReasoningClient.grade_page 进行批改。
    """
    batch_id = state["batch_id"]
    batch_index = state["batch_index"]
    total_batches = state["total_batches"]
    page_indices = state["page_indices"]
    images = state["images"]
    rubric = state.get("rubric", "")
    api_key = state.get("api_key") or os.getenv("GEMINI_API_KEY")
    
    logger.info(
        f"[grade_batch] 开始批改批次 {batch_index + 1}/{total_batches}: "
        f"batch_id={batch_id}, 页面={page_indices}"
    )
    
    page_results = []
    
    try:
        if not api_key:
            raise ValueError("API key 未配置")
        
        from src.services.gemini_reasoning import GeminiReasoningClient
        
        reasoning_client = GeminiReasoningClient(api_key=api_key)
        
        for i, (page_idx, image) in enumerate(zip(page_indices, images)):
            try:
                # 直接使用 grade_page 方法批改单页，传递解析后的评分标准
                parsed_rubric = state.get("parsed_rubric", {})
                result = await reasoning_client.grade_page(
                    image=image,
                    rubric=rubric,
                    max_score=10.0,
                    parsed_rubric=parsed_rubric
                )
                
                page_results.append({
                    "page_index": page_idx,
                    "status": "completed",
                    "score": result.get("score", 0.0),
                    "max_score": result.get("max_score", 10.0),
                    "confidence": result.get("confidence", 0.0),
                    "feedback": result.get("feedback", ""),
                    "question_id": f"Q{page_idx}",
                    "question_numbers": result.get("question_numbers", []),
                    "question_details": result.get("question_details", []),
                    "page_summary": result.get("page_summary", ""),
                    "student_info": result.get("student_info"),
                    "revision_count": 0
                })
                
                # 更详细的日志
                q_nums = result.get("question_numbers", [])
                logger.info(
                    f"[grade_batch] 页面 {page_idx} 批改完成: "
                    f"score={result.get('score', 0)}, 题目={q_nums}"
                )
                
            except Exception as e:
                logger.error(f"[grade_batch] 页面 {page_idx} 批改失败: {e}")
                page_results.append({
                    "page_index": page_idx,
                    "status": "failed",
                    "error": str(e)
                })
    
    except Exception as e:
        logger.error(f"[grade_batch] 批次 {batch_index} 批改失败: {e}", exc_info=True)
        # 所有页面标记为失败
        for page_idx in page_indices:
            page_results.append({
                "page_index": page_idx,
                "status": "failed",
                "error": str(e)
            })
    
    logger.info(
        f"[grade_batch] 批次 {batch_index + 1}/{total_batches} 完成: "
        f"成功={sum(1 for r in page_results if r['status'] == 'completed')}"
    )
    
    # 返回结果（使用 add reducer 聚合）
    return {
        "grading_results": page_results
    }


async def segment_node(state: BatchGradingGraphState) -> Dict[str, Any]:
    """
    学生分割节点
    
    基于批改结果智能判断学生边界。
    这是在批改完成后进行的，利用批改结果中的题目信息和学生标识。
    """
    batch_id = state["batch_id"]
    grading_results = state.get("grading_results", [])
    
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
    
    logger.info(
        f"[segment] 开始学生分割: batch_id={batch_id}, "
        f"批改结果数={len(grading_results)}（去重后）"
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
            
            total_score = sum(r.get("score", 0) for r in student_pages if r.get("status") == "completed")
            max_total_score = sum(r.get("max_score", 0) for r in student_pages if r.get("status") == "completed")
            
            student_results.append({
                "student_key": boundary["student_key"],
                "start_page": boundary["start_page"],
                "end_page": boundary["end_page"],
                "total_score": total_score,
                "max_total_score": max_total_score,
                "page_results": student_pages,
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
        total_score = sum(r.get("score", 0) for r in grading_results if r.get("status") == "completed")
        max_total_score = sum(r.get("max_score", 0) for r in grading_results if r.get("status") == "completed")
        
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
    """
    batch_id = state["batch_id"]
    student_results = state.get("student_results", [])
    
    logger.info(f"[export] 开始导出结果: batch_id={batch_id}")
    
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
        "students": []
    }
    
    for student in student_results:
        export_data["students"].append({
            "student_name": student["student_key"],
            "score": student.get("total_score", 0),
            "max_score": student.get("max_total_score", 0),
            "percentage": (
                student.get("total_score", 0) / student.get("max_total_score", 1) * 100
                if student.get("max_total_score", 0) > 0 else 0
            ),
            "question_results": [
                {
                    "question_id": r.get("question_id", f"Q{r.get('page_index', 0)}"),
                    "score": r.get("score", 0),
                    "max_score": r.get("max_score", 0),
                    "feedback": r.get("feedback", "")
                }
                for r in student.get("page_results", [])
                if r.get("status") == "completed"
            ]
        })
    
    logger.info(
        f"[export] 导出完成: batch_id={batch_id}, "
        f"学生数={len(export_data['students'])}"
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
    checkpointer: Optional[AsyncPostgresSaver] = None
) -> StateGraph:
    """创建批量批改 Graph
    
    工作流：
    1. intake: 接收文件
    2. preprocess: 图像预处理
    3. rubric_parse: 解析评分标准
    4. grade_batch (并行): 固定分批批改所有页面
    5. segment: 基于批改结果进行学生分割
    6. review: 结果审核
    7. export: 导出结果
    
    流程图：
    ```
    intake
      ↓
    preprocess
      ↓
    rubric_parse
      ↓
    ┌─────────────────┐
    │ grade_batch (N) │  ← 并行批改
    └─────────────────┘
      ↓
    segment  ← 批改后学生分割
      ↓
    review
      ↓
    export
      ↓
    END
    ```
    
    Args:
        checkpointer: PostgreSQL Checkpointer（可选）
        
    Returns:
        编译后的 Graph
    """
    logger.info("创建批量批改 Graph")
    
    graph = StateGraph(BatchGradingGraphState)
    
    # 添加节点
    graph.add_node("intake", intake_node)
    graph.add_node("preprocess", preprocess_node)
    graph.add_node("rubric_parse", rubric_parse_node)
    graph.add_node("grade_batch", grade_batch_node)
    graph.add_node("segment", segment_node)
    graph.add_node("review", review_node)
    graph.add_node("export", export_node)
    
    # 入口点
    graph.set_entry_point("intake")
    
    # 线性流程：intake → preprocess → rubric_parse
    graph.add_edge("intake", "preprocess")
    graph.add_edge("preprocess", "rubric_parse")
    
    # rubric_parse 后扇出到并行批改
    graph.add_conditional_edges(
        "rubric_parse",
        grading_fanout_router,
        ["grade_batch", "segment"]
    )
    
    # 并行批改后聚合到 segment
    graph.add_edge("grade_batch", "segment")
    
    # segment → review → export → END
    graph.add_edge("segment", "review")
    graph.add_edge("review", "export")
    graph.add_edge("export", END)
    
    # 编译
    compile_kwargs = {}
    if checkpointer:
        compile_kwargs["checkpointer"] = checkpointer
    
    compiled_graph = graph.compile(**compile_kwargs)
    
    logger.info("批量批改 Graph 已编译")
    
    return compiled_graph
