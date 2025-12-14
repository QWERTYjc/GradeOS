"""持久化 Activity - 将批改结果保存到 PostgreSQL"""

import logging
from typing import List, Optional

from temporalio import activity

from src.models.grading import GradingResult
from src.models.enums import SubmissionStatus
from src.repositories.grading_result import GradingResultRepository
from src.repositories.submission import SubmissionRepository


logger = logging.getLogger(__name__)


@activity.defn
async def persist_results_activity(
    submission_id: str,
    grading_results: List[GradingResult],
    grading_result_repo: Optional[GradingResultRepository] = None,
    submission_repo: Optional[SubmissionRepository] = None
) -> bool:
    """
    持久化批改结果 Activity
    
    将批改结果保存到 PostgreSQL，并更新提交状态。
    
    Args:
        submission_id: 提交 ID
        grading_results: 批改结果列表
        grading_result_repo: 批改结果仓储实例
        submission_repo: 提交仓储实例
        
    Returns:
        bool: 持久化是否成功
        
    Raises:
        ValueError: 当必要的仓储实例为 None 时
        
    验证：需求 7.1, 4.6
    """
    if grading_result_repo is None or submission_repo is None:
        raise ValueError("grading_result_repo 和 submission_repo 不能为 None")
    
    logger.info(
        f"开始持久化批改结果: submission_id={submission_id}, "
        f"结果数={len(grading_results)}"
    )
    
    try:
        # 第一步：保存各题目的批改结果
        total_score = 0.0
        max_total_score = 0.0
        
        for result in grading_results:
            logger.debug(
                f"保存批改结果: submission_id={submission_id}, "
                f"question_id={result.question_id}, "
                f"score={result.score}/{result.max_score}"
            )
            
            # 保存到数据库
            await grading_result_repo.create(
                submission_id=submission_id,
                question_id=result.question_id,
                score=result.score,
                max_score=result.max_score,
                confidence_score=result.confidence,
                visual_annotations=result.visual_annotations,
                agent_trace=result.agent_trace,
                student_feedback={
                    "feedback": result.feedback
                }
            )
            
            # 累计总分
            total_score += result.score
            max_total_score += result.max_score
        
        logger.info(
            f"所有批改结果已保存: submission_id={submission_id}, "
            f"总分={total_score}/{max_total_score}"
        )
        
        # 第二步：更新提交的总分和状态
        await submission_repo.update_scores(
            submission_id=submission_id,
            total_score=total_score,
            max_total_score=max_total_score
        )
        
        # 第三步：更新提交状态为 COMPLETED
        await submission_repo.update_status(
            submission_id=submission_id,
            status=SubmissionStatus.COMPLETED
        )
        
        logger.info(
            f"提交状态已更新: submission_id={submission_id}, "
            f"status=COMPLETED, total_score={total_score}"
        )
        
        return True
        
    except Exception as e:
        logger.error(
            f"持久化批改结果失败: submission_id={submission_id}, "
            f"error={str(e)}",
            exc_info=True
        )
        raise
