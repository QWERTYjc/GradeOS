"""人工审核 Node - 实现 interrupt + resume 机制"""

import logging
from typing import Dict, Any
from datetime import datetime

from langgraph.types import interrupt

from src.graphs.state import GradingGraphState


logger = logging.getLogger(__name__)


async def review_check_node(state: GradingGraphState) -> GradingGraphState:
    """
    审核检查节点
    
    检查批改结果的置信度，决定是否需要人工审核。
    
    Args:
        state: 当前 Graph 状态
        
    Returns:
        更新后的 Graph 状态
        
    验证：需求 5.1
    """
    submission_id = state["submission_id"]
    grading_results = state.get("grading_results", [])
    
    logger.info(
        f"检查是否需要人工审核: submission_id={submission_id}, "
        f"结果数={len(grading_results)}"
    )
    
    if not grading_results:
        logger.warning(f"没有批改结果: submission_id={submission_id}")
        return {
            **state,
            "needs_review": False
        }
    
    # 计算最低置信度
    min_confidence = min(
        result.get("confidence", 0.0) 
        for result in grading_results
    )
    
    # 置信度阈值
    CONFIDENCE_THRESHOLD = 0.75
    needs_review = min_confidence < CONFIDENCE_THRESHOLD
    
    logger.info(
        f"审核检查完成: submission_id={submission_id}, "
        f"min_confidence={min_confidence:.2f}, "
        f"needs_review={needs_review}"
    )
    
    return {
        **state,
        "needs_review": needs_review,
        "progress": {
            **state.get("progress", {}),
            "review_check_completed": True,
            "min_confidence": min_confidence
        },
        "timestamps": {
            **state.get("timestamps", {}),
            "review_check_at": datetime.now().isoformat()
        }
    }


async def review_interrupt_node(state: GradingGraphState) -> GradingGraphState:
    """
    人工审核中断节点
    
    如果需要人工审核，触发 interrupt 暂停执行，等待外部输入。
    
    Args:
        state: 当前 Graph 状态
        
    Returns:
        更新后的 Graph 状态（包含审核结果）
        
    验证：需求 5.2
    """
    submission_id = state["submission_id"]
    needs_review = state.get("needs_review", False)
    
    if not needs_review:
        logger.info(f"无需人工审核，跳过: submission_id={submission_id}")
        return state
    
    logger.info(f"需要人工审核，触发中断: submission_id={submission_id}")
    
    # 准备审核数据
    review_request = {
        "type": "review_required",
        "submission_id": submission_id,
        "grading_results": state.get("grading_results", []),
        "total_score": state.get("total_score", 0.0),
        "max_total_score": state.get("max_total_score", 0.0),
        "min_confidence": state.get("progress", {}).get("min_confidence", 0.0),
        "message": "置信度低于阈值，需要人工审核",
        "requested_at": datetime.now().isoformat()
    }
    
    # 触发 interrupt，等待外部输入
    # 当外部调用 resume 时，review_response 将包含审核结果
    review_response = interrupt(review_request)
    
    logger.info(
        f"收到审核响应: submission_id={submission_id}, "
        f"action={review_response.get('action')}"
    )
    
    return {
        **state,
        "review_result": review_response,
        "external_event": review_response,
        "timestamps": {
            **state.get("timestamps", {}),
            "review_completed_at": datetime.now().isoformat()
        }
    }


async def apply_review_node(state: GradingGraphState) -> GradingGraphState:
    """
    应用审核结果节点
    
    根据审核操作（APPROVE/OVERRIDE/REJECT）处理批改结果。
    
    Args:
        state: 当前 Graph 状态
        
    Returns:
        更新后的 Graph 状态
        
    验证：需求 5.3
    """
    submission_id = state["submission_id"]
    review_result = state.get("review_result")
    
    if not review_result:
        logger.info(f"没有审核结果，跳过: submission_id={submission_id}")
        return state
    
    action = review_result.get("action", "").upper()
    
    logger.info(
        f"应用审核结果: submission_id={submission_id}, "
        f"action={action}"
    )
    
    if action == "APPROVE":
        # 批准：使用 AI 结果
        logger.info(f"审核批准: submission_id={submission_id}")
        return {
            **state,
            "current_stage": "review_approved",
            "progress": {
                **state.get("progress", {}),
                "review_action": "approved"
            }
        }
    
    elif action == "OVERRIDE":
        # 覆盖：应用教师的手动评分
        logger.info(f"审核覆盖: submission_id={submission_id}")
        override_data = review_result.get("override_data", {})
        grading_results = state.get("grading_results", [])
        
        # 应用覆盖数据
        total_score = 0.0
        for result in grading_results:
            question_id = result.get("question_id")
            if question_id in override_data:
                override_score = override_data[question_id].get("score")
                if override_score is not None:
                    result["score"] = override_score
                    result["overridden"] = True
                    logger.info(
                        f"应用覆盖分数: question_id={question_id}, "
                        f"score={override_score}"
                    )
            total_score += result.get("score", 0.0)
        
        return {
            **state,
            "grading_results": grading_results,
            "total_score": total_score,
            "current_stage": "review_overridden",
            "progress": {
                **state.get("progress", {}),
                "review_action": "overridden"
            }
        }
    
    elif action == "REJECT":
        # 拒绝：标记为失败
        logger.info(f"审核拒绝: submission_id={submission_id}")
        
        errors = state.get("errors", [])
        errors.append({
            "node": "apply_review",
            "error_type": "review_rejected",
            "error": "人工审核拒绝",
            "timestamp": datetime.now().isoformat()
        })
        
        return {
            **state,
            "errors": errors,
            "current_stage": "review_rejected",
            "progress": {
                **state.get("progress", {}),
                "review_action": "rejected"
            }
        }
    
    else:
        logger.warning(
            f"未知的审核操作: submission_id={submission_id}, "
            f"action={action}"
        )
        return state


def should_interrupt_for_review(state: GradingGraphState) -> str:
    """
    条件路由：判断是否需要人工审核中断
    
    Returns:
        "review_interrupt" 或 "persist"
    """
    if state.get("needs_review", False):
        return "review_interrupt"
    return "persist"


def should_continue_after_review(state: GradingGraphState) -> str:
    """
    条件路由：判断审核后的下一步
    
    Returns:
        "persist" 或 "end"
    """
    review_result = state.get("review_result", {})
    action = review_result.get("action", "").upper()
    
    if action == "REJECT":
        return "end"
    
    return "persist"
