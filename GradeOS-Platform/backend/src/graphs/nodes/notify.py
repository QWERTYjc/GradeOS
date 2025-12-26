"""通知 Node - 将 Temporal Activity 重写为 LangGraph Node"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from src.graphs.state import GradingGraphState


logger = logging.getLogger(__name__)


async def notify_node(state: GradingGraphState) -> GradingGraphState:
    """
    通知节点
    
    当工作流完成或需要人工介入时发送通知。
    
    Args:
        state: 当前 Graph 状态
        
    Returns:
        更新后的 Graph 状态
        
    验证：需求 2.2, 2.3
    """
    submission_id = state["submission_id"]
    exam_id = state.get("exam_id", "")
    student_id = state.get("student_id", "")
    needs_review = state.get("needs_review", False)
    grading_results = state.get("grading_results", [])
    
    logger.info(
        f"开始通知节点: submission_id={submission_id}, "
        f"exam_id={exam_id}, student_id={student_id}, "
        f"needs_review={needs_review}"
    )
    
    try:
        # 确定通知类型
        if needs_review:
            notification_type = "review_required"
            
            # 收集低置信度题目
            low_confidence_questions = []
            for result in grading_results:
                if result.get("confidence", 1.0) < 0.7:
                    low_confidence_questions.append({
                        "question_id": result.get("question_id"),
                        "score": result.get("score"),
                        "confidence": result.get("confidence"),
                        "feedback": result.get("feedback", "")
                    })
            
            logger.info(
                f"需要人工审核: submission_id={submission_id}, "
                f"低置信度题目数={len(low_confidence_questions)}"
            )
        else:
            notification_type = "grading_completed"
            low_confidence_questions = []
            
            logger.info(
                f"批改完成通知: submission_id={submission_id}"
            )
        
        # 构建通知内容
        notification_content = {
            "submission_id": submission_id,
            "exam_id": exam_id,
            "student_id": student_id,
            "type": notification_type,
            "total_score": state.get("total_score", 0.0),
            "max_total_score": state.get("max_total_score", 0.0),
            "completed_questions": len(grading_results),
            "low_confidence_questions": low_confidence_questions,
            "timestamp": datetime.now().isoformat()
        }
        
        # TODO: 实现实际的通知机制
        # 可以集成：
        # - 邮件服务（SMTP）
        # - 短信服务（Twilio）
        # - 推送通知（Firebase Cloud Messaging）
        # - WebSocket 实时推送
        # - 数据库通知表
        
        logger.info(
            f"通知已发送: submission_id={submission_id}, "
            f"type={notification_type}, "
            f"content={notification_content}"
        )
        
        # 更新状态
        updated_state = {
            **state,
            "progress": {
                **state.get("progress", {}),
                "notification_sent": True
            },
            "current_stage": "notification_sent",
            "percentage": 100.0,  # 通知完成占 100%
            "timestamps": {
                **state.get("timestamps", {}),
                "notification_sent_at": datetime.now()
            },
            "artifacts": {
                **state.get("artifacts", {}),
                "notification": notification_content
            }
        }
        
        logger.info(
            f"通知节点完成: submission_id={submission_id}"
        )
        
        return updated_state
        
    except Exception as e:
        logger.error(
            f"通知节点发生错误: submission_id={submission_id}, "
            f"error={str(e)}",
            exc_info=True
        )
        
        # 通知失败不应该中断工作流，记录错误但继续
        errors = state.get("errors", [])
        errors.append({
            "node": "notify",
            "error_type": "notification_failed",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
            "severity": "warning"  # 标记为警告级别
        })
        
        # 返回状态，标记通知失败但不抛出异常
        return {
            **state,
            "errors": errors,
            "progress": {
                **state.get("progress", {}),
                "notification_sent": False
            },
            "current_stage": "notification_failed",
            "percentage": 100.0  # 即使通知失败，流程也算完成
        }


async def notify_teacher_node(state: GradingGraphState) -> GradingGraphState:
    """
    教师通知节点（专门用于人工审核场景）
    
    当批改置信度较低时，发送审核通知给教师。
    
    Args:
        state: 当前 Graph 状态
        
    Returns:
        更新后的 Graph 状态
    """
    submission_id = state["submission_id"]
    exam_id = state.get("exam_id", "")
    student_id = state.get("student_id", "")
    grading_results = state.get("grading_results", [])
    
    logger.info(
        f"发送教师审核通知: submission_id={submission_id}, "
        f"exam_id={exam_id}, student_id={student_id}"
    )
    
    try:
        # 收集低置信度题目
        low_confidence_questions = []
        for result in grading_results:
            if result.get("confidence", 1.0) < 0.7:
                low_confidence_questions.append({
                    "question_id": result.get("question_id"),
                    "score": result.get("score"),
                    "max_score": result.get("max_score"),
                    "confidence": result.get("confidence"),
                    "feedback": result.get("feedback", ""),
                    "visual_annotations": result.get("visual_annotations", [])
                })
        
        # 构建通知内容
        notification_content = {
            "submission_id": submission_id,
            "exam_id": exam_id,
            "student_id": student_id,
            "type": "low_confidence_review",
            "reason": "AI 批改置信度较低，需要人工审核",
            "low_confidence_questions": low_confidence_questions,
            "total_questions": len(grading_results),
            "low_confidence_count": len(low_confidence_questions),
            "timestamp": datetime.now().isoformat()
        }
        
        # TODO: 实现实际的通知机制
        logger.info(
            f"教师审核通知已发送: submission_id={submission_id}, "
            f"低置信度题目数={len(low_confidence_questions)}"
        )
        
        # 更新状态
        updated_state = {
            **state,
            "artifacts": {
                **state.get("artifacts", {}),
                "teacher_notification": notification_content
            },
            "timestamps": {
                **state.get("timestamps", {}),
                "teacher_notified_at": datetime.now()
            }
        }
        
        return updated_state
        
    except Exception as e:
        logger.error(
            f"发送教师审核通知失败: submission_id={submission_id}, "
            f"error={str(e)}",
            exc_info=True
        )
        
        # 通知失败不应该中断工作流
        errors = state.get("errors", [])
        errors.append({
            "node": "notify_teacher",
            "error_type": "teacher_notification_failed",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
            "severity": "warning"
        })
        
        return {
            **state,
            "errors": errors
        }
