"""批改 Activity - 调用 LangGraph 智能体进行题目批改"""

import logging
from typing import Optional

from temporalio import activity

from src.models.grading import GradingResult
from src.services.cache import CacheService
from src.agents.grading_agent import GradingAgent


logger = logging.getLogger(__name__)


@activity.defn
async def grade_question_activity(
    submission_id: str,
    question_id: str,
    image_b64: str,
    rubric: str,
    max_score: float,
    standard_answer: Optional[str] = None,
    cache_service: Optional[CacheService] = None,
    grading_agent: Optional[GradingAgent] = None
) -> GradingResult:
    """
    批改题目 Activity
    
    首先检查语义缓存，缓存未命中时调用 LangGraph 智能体进行批改。
    对于高置信度结果（> 0.9），将其缓存到 Redis。
    
    Args:
        submission_id: 提交 ID
        question_id: 题目 ID
        image_b64: Base64 编码的题目图像
        rubric: 评分细则文本
        max_score: 满分
        standard_answer: 标准答案（可选）
        cache_service: 缓存服务实例
        grading_agent: 批改智能体实例
        
    Returns:
        GradingResult: 批改结果
        
    Raises:
        ValueError: 当必要的服务实例为 None 时
        
    验证：需求 3.1, 6.2, 6.3
    """
    if grading_agent is None:
        raise ValueError("grading_agent 不能为 None")
    
    logger.info(
        f"开始批改题目: submission_id={submission_id}, "
        f"question_id={question_id}"
    )
    
    try:
        # 将 Base64 图像转换为字节（用于缓存查询）
        import base64
        image_bytes = base64.b64decode(image_b64)
        
        # 第一步：检查语义缓存
        if cache_service:
            logger.debug(f"检查缓存: question_id={question_id}")
            cached_result = await cache_service.get_cached_result(
                rubric_text=rubric,
                image_data=image_bytes
            )
            
            if cached_result:
                logger.info(
                    f"缓存命中: submission_id={submission_id}, "
                    f"question_id={question_id}, "
                    f"score={cached_result.score}"
                )
                return cached_result
        
        # 第二步：缓存未命中，调用 LangGraph 智能体
        logger.debug(f"缓存未命中，调用智能体: question_id={question_id}")
        
        # 生成线程 ID（用于检查点持久化）
        thread_id = f"{submission_id}_{question_id}"
        
        # 运行智能体
        final_state = await grading_agent.run(
            question_image=image_b64,
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
            f"question_id={question_id}, "
            f"score={result.score}, "
            f"confidence={result.confidence}"
        )
        
        # 第三步：缓存高置信度结果
        if cache_service and result.confidence > 0.9:
            logger.debug(
                f"缓存高置信度结果: question_id={question_id}, "
                f"confidence={result.confidence}"
            )
            await cache_service.cache_result(
                rubric_text=rubric,
                image_data=image_bytes,
                result=result
            )
        
        return result
        
    except Exception as e:
        logger.error(
            f"批改题目发生错误: submission_id={submission_id}, "
            f"question_id={question_id}, error={str(e)}",
            exc_info=True
        )
        raise
