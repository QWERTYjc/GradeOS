"""通知 Activity - 向教师发送审核通知"""

import logging
from typing import Optional

from temporalio import activity


logger = logging.getLogger(__name__)


@activity.defn
async def notify_teacher_activity(
    submission_id: str,
    exam_id: str,
    student_id: str,
    notification_type: str = "low_confidence",
    teacher_email: Optional[str] = None,
    low_confidence_questions: Optional[list] = None
) -> bool:
    """
    通知教师 Activity
    
    当工作流进入 REVIEWING 状态时发送通知。
    
    Args:
        submission_id: 提交 ID
        exam_id: 考试 ID
        student_id: 学生 ID
        notification_type: 通知类型（low_confidence, review_required 等）
        teacher_email: 教师邮箱（可选）
        low_confidence_questions: 低置信度题目列表
        
    Returns:
        bool: 通知是否成功发送
        
    验证：需求 5.2
    """
    logger.info(
        f"发送教师审核通知: submission_id={submission_id}, "
        f"exam_id={exam_id}, student_id={student_id}, "
        f"type={notification_type}"
    )
    
    try:
        # 构建通知内容
        notification_content = {
            "submission_id": submission_id,
            "exam_id": exam_id,
            "student_id": student_id,
            "type": notification_type,
            "reason": "AI 批改置信度较低，需要人工审核",
            "low_confidence_questions": low_confidence_questions or []
        }
        
        # TODO: 实现实际的通知机制
        # 可以集成：
        # - 邮件服务（SMTP）
        # - 短信服务（Twilio）
        # - 推送通知（Firebase Cloud Messaging）
        # - 数据库通知表
        
        logger.info(
            f"教师审核通知已发送: submission_id={submission_id}, "
            f"content={notification_content}"
        )
        
        return True
        
    except Exception as e:
        logger.error(
            f"发送教师审核通知失败: submission_id={submission_id}, "
            f"error={str(e)}",
            exc_info=True
        )
        # 通知失败不应该中断工作流，返回 False 但不抛出异常
        return False
