"""题目级子工作流 - QuestionGradingChildWorkflow

单道题目的精细化批改工作流，包含重试策略和检查点持久化。
"""

import logging
from datetime import timedelta
from typing import Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

from src.models.grading import GradingResult
from src.models.state import QuestionGradingInput
from src.activities.grade import grade_question_activity


logger = logging.getLogger(__name__)


# 定义重试策略
GRADING_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=1),
    maximum_attempts=3,
    non_retryable_error_types=["ValueError"]  # 参数错误不重试
)


@workflow.defn
class QuestionGradingChildWorkflow:
    """
    题目级子工作流
    
    执行单道题目的批改 Activity，配置重试策略。
    
    验证：需求 4.4
    """
    
    @workflow.run
    async def run(self, input_data: QuestionGradingInput) -> GradingResult:
        """
        运行题目批改工作流
        
        Args:
            input_data: 题目批改输入
            
        Returns:
            GradingResult: 批改结果
            
        Raises:
            Exception: 当批改失败时
        """
        logger.info(
            f"启动题目批改子工作流: "
            f"submission_id={input_data['submission_id']}, "
            f"question_id={input_data['question_id']}"
        )
        
        try:
            # 执行批改 Activity，配置重试策略
            result = await workflow.execute_activity(
                grade_question_activity,
                input_data["submission_id"],
                input_data["question_id"],
                input_data["image_b64"],
                input_data["rubric"],
                input_data["max_score"],
                input_data.get("standard_answer"),
                retry_policy=GRADING_RETRY_POLICY,
                start_to_close_timeout=timedelta(minutes=5),
                heartbeat_timeout=timedelta(seconds=30)
            )
            
            logger.info(
                f"题目批改完成: "
                f"submission_id={input_data['submission_id']}, "
                f"question_id={input_data['question_id']}, "
                f"score={result.score}, "
                f"confidence={result.confidence}"
            )
            
            return result
            
        except Exception as e:
            logger.error(
                f"题目批改失败: "
                f"submission_id={input_data['submission_id']}, "
                f"question_id={input_data['question_id']}, "
                f"error={str(e)}",
                exc_info=True
            )
            raise
