"""持久化 Node - 将 Temporal Activity 重写为 LangGraph Node"""

import logging
from typing import Dict, Any
from datetime import datetime

from src.graphs.state import GradingGraphState
from src.models.grading import GradingResult
from src.models.enums import SubmissionStatus
from src.repositories.grading_result import GradingResultRepository
from src.repositories.submission import SubmissionRepository
from src.utils.database import get_db_pool


logger = logging.getLogger(__name__)


async def persist_node(state: GradingGraphState) -> GradingGraphState:
    """
    持久化节点
    
    将批改结果保存到 PostgreSQL，并更新提交状态。
    
    Args:
        state: 当前 Graph 状态
        
    Returns:
        更新后的 Graph 状态
        
    验证：需求 2.2, 2.3
    """
    submission_id = state["submission_id"]
    grading_results = state.get("grading_results", [])
    total_score = state.get("total_score", 0.0)
    max_total_score = state.get("max_total_score", 0.0)
    
    logger.info(
        f"开始持久化节点: submission_id={submission_id}, "
        f"结果数={len(grading_results)}, "
        f"总分={total_score}/{max_total_score}"
    )
    
    try:
        # 获取数据库连接池
        db_pool = await get_db_pool()
        
        # 初始化仓储
        grading_result_repo = GradingResultRepository(db_pool)
        submission_repo = SubmissionRepository(db_pool)
        
        # 第一步：保存各题目的批改结果
        for result_dict in grading_results:
            # 将字典转换为 GradingResult 对象
            result = GradingResult(**result_dict)
            
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
        
        # 更新状态
        updated_state = {
            **state,
            "progress": {
                **state.get("progress", {}),
                "persistence_completed": True
            },
            "current_stage": "persistence_completed",
            "percentage": 90.0,  # 持久化完成占 90%
            "timestamps": {
                **state.get("timestamps", {}),
                "persistence_completed_at": datetime.now()
            }
        }
        
        logger.info(
            f"持久化节点完成: submission_id={submission_id}"
        )
        
        return updated_state
        
    except Exception as e:
        logger.error(
            f"持久化节点发生错误: submission_id={submission_id}, "
            f"error={str(e)}",
            exc_info=True
        )
        
        # 记录错误到状态
        errors = state.get("errors", [])
        errors.append({
            "node": "persist",
            "error_type": "persistence_failed",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })
        
        # 持久化失败应该抛出异常，因为这是关键步骤
        raise
