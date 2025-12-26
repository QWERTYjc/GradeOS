"""批改 Node - 将 Temporal Activity 重写为 LangGraph Node"""

import logging
import base64
from typing import Dict, Any, Optional
from datetime import datetime

from src.graphs.state import GradingGraphState
from src.graphs.retry import RetryConfig, create_retryable_node
from src.services.cache import CacheService
from src.agents.grading_agent import GradingAgent
from src.models.grading import GradingResult


logger = logging.getLogger(__name__)


async def _grade_node_impl(state: GradingGraphState) -> GradingGraphState:
    """
    批改节点实现
    
    首先检查语义缓存，缓存未命中时调用 LangGraph 智能体进行批改。
    对于高置信度结果（> 0.9），将其缓存到 Redis。
    
    Args:
        state: 当前 Graph 状态
        
    Returns:
        更新后的 Graph 状态
        
    验证：需求 2.2, 2.3
    """
    submission_id = state["submission_id"]
    rubric = state.get("rubric", "")
    
    # 获取分割结果
    segmentation_results = state.get("artifacts", {}).get("segmentation_results", [])
    
    if not segmentation_results:
        raise ValueError("未找到分割结果，无法进行批改")
    
    logger.info(
        f"开始批改节点: submission_id={submission_id}, "
        f"页面数={len(segmentation_results)}"
    )
    
    # 初始化服务
    cache_service = CacheService()
    grading_agent = GradingAgent()
    
    # 存储所有批改结果
    all_grading_results = []
    total_score = 0.0
    max_total_score = 0.0
    
    try:
        # 遍历所有页面和题目
        question_index = 0
        for page_result in segmentation_results:
            page_index = page_result["page_index"]
            file_path = page_result["file_path"]
            regions = page_result["regions"]
            
            # 读取页面图像
            with open(file_path, 'rb') as f:
                page_image_data = f.read()
            
            # 遍历该页面的所有题目区域
            for region in regions:
                question_id = f"q_{page_index}_{question_index}"
                question_index += 1
                
                logger.debug(
                    f"批改题目: submission_id={submission_id}, "
                    f"question_id={question_id}"
                )
                
                # 提取题目区域图像（这里简化处理，实际应该裁剪区域）
                # TODO: 根据 region 的坐标裁剪图像
                question_image_data = page_image_data
                question_image_b64 = base64.b64encode(question_image_data).decode('utf-8')
                
                # 获取题目的满分（从 region metadata 或默认值）
                max_score = region.get("max_score", 10.0)
                standard_answer = region.get("standard_answer")
                
                # 第一步：检查语义缓存
                cached_result = await cache_service.get_cached_result(
                    rubric_text=rubric,
                    image_data=question_image_data
                )
                
                if cached_result:
                    logger.info(
                        f"缓存命中: submission_id={submission_id}, "
                        f"question_id={question_id}, score={cached_result.score}"
                    )
                    result = cached_result
                else:
                    # 第二步：缓存未命中，调用智能体
                    logger.debug(
                        f"缓存未命中，调用智能体: question_id={question_id}"
                    )
                    
                    # 生成线程 ID（用于检查点持久化）
                    thread_id = f"{submission_id}_{question_id}"
                    
                    # 运行智能体
                    final_state = await grading_agent.run(
                        question_image=question_image_b64,
                        rubric=rubric,
                        max_score=max_score,
                        standard_answer=standard_answer,
                        thread_id=thread_id
                    )
                    
                    # 构建批改结果
                    result = GradingResult(
                        question_id=question_id,
                        score=final_state.get("final_score", 0.0),
                        max_score=max_score,
                        confidence=final_state.get("confidence", 0.0),
                        feedback=final_state.get("student_feedback", ""),
                        visual_annotations=final_state.get("visual_annotations", []),
                        agent_trace={
                            "vision_analysis": final_state.get("vision_analysis", ""),
                            "reasoning_trace": final_state.get("reasoning_trace", []),
                            "rubric_mapping": final_state.get("rubric_mapping", []),
                            "critique_feedback": final_state.get("critique_feedback"),
                            "revision_count": final_state.get("revision_count", 0)
                        }
                    )
                    
                    logger.info(
                        f"智能体批改完成: submission_id={submission_id}, "
                        f"question_id={question_id}, score={result.score}, "
                        f"confidence={result.confidence}"
                    )
                    
                    # 第三步：缓存高置信度结果
                    if result.confidence > 0.9:
                        logger.debug(
                            f"缓存高置信度结果: question_id={question_id}, "
                            f"confidence={result.confidence}"
                        )
                        await cache_service.cache_result(
                            rubric_text=rubric,
                            image_data=question_image_data,
                            result=result
                        )
                
                # 添加到结果列表
                all_grading_results.append(result.dict())
                total_score += result.score
                max_total_score += result.max_score
        
        # 更新状态
        completed_questions = len(all_grading_results)
        total_questions = state.get("progress", {}).get("total_questions", completed_questions)
        progress_percentage = 20.0 + (completed_questions / total_questions * 60.0) if total_questions > 0 else 80.0
        
        updated_state = {
            **state,
            "grading_results": all_grading_results,
            "total_score": total_score,
            "max_total_score": max_total_score,
            "progress": {
                **state.get("progress", {}),
                "grading_completed": True,
                "completed_questions": completed_questions
            },
            "current_stage": "grading_completed",
            "percentage": progress_percentage,
            "timestamps": {
                **state.get("timestamps", {}),
                "grading_completed_at": datetime.now()
            }
        }
        
        logger.info(
            f"批改节点完成: submission_id={submission_id}, "
            f"总分={total_score}/{max_total_score}, "
            f"题目数={completed_questions}"
        )
        
        return updated_state
        
    except Exception as e:
        logger.error(
            f"批改节点发生错误: submission_id={submission_id}, "
            f"error={str(e)}",
            exc_info=True
        )
        raise


# 配置重试策略（针对 API 限流等临时故障）
grade_retry_config = RetryConfig(
    initial_interval=3.0,
    backoff_coefficient=2.0,
    maximum_interval=120.0,
    maximum_attempts=5,
    non_retryable_errors=[ValueError, TypeError]
)


async def grade_fallback(state: GradingGraphState, error: Exception) -> GradingGraphState:
    """
    批改失败的降级处理
    
    当重试耗尽时，记录错误并标记为需要人工介入
    """
    logger.warning(
        f"批改重试耗尽，执行降级: submission_id={state['submission_id']}, "
        f"error={str(error)}"
    )
    
    errors = state.get("errors", [])
    errors.append({
        "node": "grade",
        "error_type": "retry_exhausted",
        "error": str(error),
        "timestamp": datetime.now().isoformat(),
        "fallback_triggered": True
    })
    
    # 如果有部分结果，保留它们
    partial_results = state.get("grading_results", [])
    
    return {
        **state,
        "errors": errors,
        "current_stage": "grading_failed",
        "needs_review": True,  # 标记需要人工介入
        "grading_results": partial_results  # 保留部分结果
    }


# 创建带重试的节点
grade_node = create_retryable_node(
    _grade_node_impl,
    grade_retry_config,
    grade_fallback
)
