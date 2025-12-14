"""试卷级父工作流 - ExamPaperWorkflow

管理整份试卷的批改生命周期，包括文档分割、扇出子工作流、结果聚合、
置信度检查、人工审核处理和结果持久化。

集成增强型工作流混入，支持进度查询和状态同步。
"""

import asyncio
import logging
from datetime import timedelta
from typing import List, Dict, Any, Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

from src.models.grading import GradingResult, ExamPaperResult
from src.models.enums import SubmissionStatus, ReviewAction
from src.models.region import SegmentationResult, QuestionRegion
from src.models.state import WorkflowInput, QuestionGradingInput
from src.activities.segment import segment_document_activity
from src.activities.persist import persist_results_activity
from src.activities.notify import notify_teacher_activity
from src.workflows.question_grading import QuestionGradingChildWorkflow
from src.workflows.enhanced_workflow import EnhancedWorkflowMixin


logger = logging.getLogger(__name__)


# 定义重试策略
SEGMENT_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=1),
    maximum_attempts=2,
    non_retryable_error_types=["ValueError"]
)

PERSIST_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=1),
    maximum_attempts=3
)


@workflow.defn
class ExamPaperWorkflow(EnhancedWorkflowMixin):
    """
    试卷级父工作流
    
    管理整份试卷的批改生命周期：
    1. 文档分割：识别题目边界
    2. 扇出：为每道题目启动子工作流
    3. 扇入：聚合结果并计算总分
    4. 置信度检查：如果低置信度则转入审核状态
    5. 审核处理：处理人工审核信号
    6. 持久化：保存最终结果
    
    集成增强型工作流混入，支持进度查询和状态同步。
    
    验证：需求 4.1, 4.2, 4.3, 5.1, 5.3, 5.4, 5.5, 10.2
    """
    
    def __init__(self):
        """初始化工作流"""
        # 初始化增强型工作流混入
        EnhancedWorkflowMixin.__init__(self)
        
        # 审核信号
        self._review_signal: Optional[Dict[str, Any]] = None
        self._review_received = False
    
    @workflow.signal
    def review_signal(self, action: str, override_data: Optional[Dict[str, Any]] = None):
        """
        接收人工审核信号
        
        Args:
            action: 审核操作 (APPROVE, OVERRIDE, REJECT)
            override_data: 覆盖数据（当 action=OVERRIDE 时使用）
        """
        logger.info(f"收到审核信号: action={action}")
        self._review_signal = {
            "action": action,
            "override_data": override_data or {}
        }
        self._review_received = True
    
    @workflow.run
    async def run(self, input_data: WorkflowInput) -> ExamPaperResult:
        """
        运行试卷批改工作流
        
        Args:
            input_data: 工作流输入
            
        Returns:
            ExamPaperResult: 整份试卷的批改结果
            
        Raises:
            Exception: 当工作流执行失败时
        """
        submission_id = input_data["submission_id"]
        student_id = input_data["student_id"]
        exam_id = input_data["exam_id"]
        file_paths = input_data["file_paths"]
        
        logger.info(
            f"启动试卷批改工作流: "
            f"submission_id={submission_id}, "
            f"exam_id={exam_id}, "
            f"student_id={student_id}, "
            f"file_count={len(file_paths)}"
        )
        
        # 更新进度：初始化
        self.update_progress(
            stage="initialized",
            percentage=0.0,
            details={
                "submission_id": submission_id,
                "exam_id": exam_id,
                "file_count": len(file_paths)
            }
        )
        
        try:
            # ===== 第一步：文档分割 =====
            logger.info(f"开始文档分割: submission_id={submission_id}")
            
            # 更新进度：文档分割
            self.update_progress(
                stage="document_segmentation",
                percentage=10.0,
                details={"file_count": len(file_paths)}
            )
            
            segmentation_results: List[SegmentationResult] = []
            for page_index, file_path in enumerate(file_paths):
                # 读取图像数据（在实际应用中应从对象存储读取）
                # 这里假设 file_path 是可以读取的路径
                try:
                    with open(file_path, "rb") as f:
                        image_data = f.read()
                except Exception as e:
                    logger.error(f"无法读取文件: {file_path}, error={str(e)}")
                    raise
                
                # 执行分割 Activity
                result = await workflow.execute_activity(
                    segment_document_activity,
                    submission_id,
                    image_data,
                    page_index,
                    retry_policy=SEGMENT_RETRY_POLICY,
                    start_to_close_timeout=timedelta(minutes=2),
                    heartbeat_timeout=timedelta(seconds=30)
                )
                
                segmentation_results.append(result)
                logger.info(
                    f"页面分割完成: page_index={page_index}, "
                    f"识别题目数={len(result.regions)}"
                )
            
            # 收集所有题目区域
            all_regions: List[QuestionRegion] = []
            for seg_result in segmentation_results:
                all_regions.extend(seg_result.regions)
            
            logger.info(
                f"文档分割完成: submission_id={submission_id}, "
                f"总题目数={len(all_regions)}"
            )
            
            # 更新进度：文档分割完成
            self.update_progress(
                stage="segmentation_complete",
                percentage=20.0,
                details={"total_questions": len(all_regions)}
            )
            
            # ===== 第二步：扇出子工作流 =====
            logger.info(
                f"启动题目批改子工作流: "
                f"submission_id={submission_id}, "
                f"题目数={len(all_regions)}"
            )
            
            # 更新进度：启动子工作流
            self.update_progress(
                stage="starting_child_workflows",
                percentage=25.0,
                details={"total_questions": len(all_regions)}
            )
            
            # 为每道题目创建子工作流任务
            child_workflow_tasks = []
            for region in all_regions:
                # 从图像数据中裁剪题目区域
                # 这里假设 region.image_data 已经是 Base64 编码
                if not region.image_data:
                    logger.warning(
                        f"题目区域缺少图像数据: "
                        f"question_id={region.question_id}"
                    )
                    continue
                
                # 创建子工作流输入
                child_input = QuestionGradingInput(
                    submission_id=submission_id,
                    question_id=region.question_id,
                    image_b64=region.image_data,
                    rubric="",  # 在实际应用中应从数据库获取
                    max_score=10.0,  # 在实际应用中应从数据库获取
                    standard_answer=None
                )
                
                # 启动子工作流
                child_handle = await workflow.start_child_workflow(
                    QuestionGradingChildWorkflow,
                    child_input,
                    id=f"{submission_id}_{region.question_id}",
                    task_queue="vision-compute-queue"
                )
                
                child_workflow_tasks.append(child_handle)
            
            logger.info(
                f"所有子工作流已启动: "
                f"submission_id={submission_id}, "
                f"子工作流数={len(child_workflow_tasks)}"
            )
            
            # 更新进度：等待子工作流
            self.update_progress(
                stage="waiting_for_child_workflows",
                percentage=30.0,
                details={
                    "total_questions": len(child_workflow_tasks),
                    "completed": 0
                }
            )
            
            # ===== 第三步：扇入 - 等待所有子工作流完成 =====
            logger.info(
                f"等待子工作流完成: "
                f"submission_id={submission_id}"
            )
            
            grading_results: List[GradingResult] = []
            total_workflows = len(child_workflow_tasks)
            
            for idx, child_handle in enumerate(child_workflow_tasks):
                try:
                    result = await child_handle.result()
                    grading_results.append(result)
                    logger.debug(
                        f"子工作流完成: "
                        f"question_id={result.question_id}, "
                        f"score={result.score}"
                    )
                    
                    # 更新进度：子工作流完成
                    completed = idx + 1
                    progress_percentage = 30.0 + (completed / total_workflows) * 40.0
                    self.update_progress(
                        stage="grading_questions",
                        percentage=progress_percentage,
                        details={
                            "total_questions": total_workflows,
                            "completed": completed
                        }
                    )
                    
                except Exception as e:
                    logger.error(
                        f"子工作流失败: "
                        f"submission_id={submission_id}, "
                        f"error={str(e)}",
                        exc_info=True
                    )
                    raise
            
            logger.info(
                f"所有子工作流完成: "
                f"submission_id={submission_id}, "
                f"完成数={len(grading_results)}"
            )
            
            # ===== 第四步：聚合结果并计算总分 =====
            logger.info(
                f"聚合批改结果: "
                f"submission_id={submission_id}"
            )
            
            total_score = 0.0
            max_total_score = 0.0
            min_confidence = 1.0
            
            for result in grading_results:
                total_score += result.score
                max_total_score += result.max_score
                min_confidence = min(min_confidence, result.confidence)
            
            logger.info(
                f"结果聚合完成: "
                f"submission_id={submission_id}, "
                f"total_score={total_score}/{max_total_score}, "
                f"min_confidence={min_confidence}"
            )
            
            # 更新进度：结果聚合完成
            self.update_progress(
                stage="aggregation_complete",
                percentage=75.0,
                details={
                    "total_score": total_score,
                    "max_total_score": max_total_score,
                    "min_confidence": min_confidence
                }
            )
            
            # ===== 第五步：置信度检查 =====
            logger.info(
                f"检查置信度阈值: "
                f"submission_id={submission_id}, "
                f"min_confidence={min_confidence}"
            )
            
            needs_review = min_confidence < 0.75
            
            if needs_review:
                logger.info(
                    f"置信度低于阈值，转入审核状态: "
                    f"submission_id={submission_id}, "
                    f"min_confidence={min_confidence}"
                )
                
                # 发送通知给教师
                await workflow.execute_activity(
                    notify_teacher_activity,
                    submission_id,
                    exam_id,
                    student_id,
                    "low_confidence",
                    retry_policy=RetryPolicy(maximum_attempts=2),
                    start_to_close_timeout=timedelta(minutes=1)
                )
                
                # ===== 第六步：等待人工审核信号 =====
                logger.info(
                    f"等待人工审核信号: "
                    f"submission_id={submission_id}"
                )
                
                # 更新进度：等待审核
                self.update_progress(
                    stage="waiting_for_review",
                    percentage=80.0,
                    details={"min_confidence": min_confidence}
                )
                
                # 等待审核信号（最多等待 24 小时）
                await workflow.wait_condition(
                    lambda: self._review_received,
                    timeout=timedelta(hours=24)
                )
                
                if not self._review_signal:
                    logger.warning(
                        f"审核信号超时: "
                        f"submission_id={submission_id}"
                    )
                    raise Exception("审核信号超时")
                
                # 处理审核信号
                action = self._review_signal["action"]
                logger.info(
                    f"收到审核信号: "
                    f"submission_id={submission_id}, "
                    f"action={action}"
                )
                
                if action == ReviewAction.APPROVE.value:
                    # 批准：使用 AI 结果
                    logger.info(
                        f"审核批准: "
                        f"submission_id={submission_id}"
                    )
                    pass  # 继续使用原始结果
                
                elif action == ReviewAction.OVERRIDE.value:
                    # 覆盖：应用教师的手动评分
                    logger.info(
                        f"审核覆盖: "
                        f"submission_id={submission_id}"
                    )
                    override_data = self._review_signal.get("override_data", {})
                    
                    # 应用覆盖数据到结果
                    for result in grading_results:
                        question_id = result.question_id
                        if question_id in override_data:
                            override_score = override_data[question_id].get("score")
                            if override_score is not None:
                                # 重新计算总分
                                total_score -= result.score
                                result.score = override_score
                                total_score += override_score
                                logger.info(
                                    f"应用覆盖分数: "
                                    f"question_id={question_id}, "
                                    f"score={override_score}"
                                )
                
                elif action == ReviewAction.REJECT.value:
                    # 拒绝：终止工作流
                    logger.info(
                        f"审核拒绝: "
                        f"submission_id={submission_id}"
                    )
                    raise Exception("审核拒绝")
                
                else:
                    logger.error(
                        f"未知的审核操作: "
                        f"submission_id={submission_id}, "
                        f"action={action}"
                    )
                    raise ValueError(f"未知的审核操作: {action}")
            
            # ===== 第七步：持久化最终结果 =====
            logger.info(
                f"持久化批改结果: "
                f"submission_id={submission_id}"
            )
            
            # 更新进度：持久化
            self.update_progress(
                stage="persisting_results",
                percentage=90.0,
                details={"total_questions": len(grading_results)}
            )
            
            await workflow.execute_activity(
                persist_results_activity,
                submission_id,
                grading_results,
                retry_policy=PERSIST_RETRY_POLICY,
                start_to_close_timeout=timedelta(minutes=2)
            )
            
            logger.info(
                f"批改结果已持久化: "
                f"submission_id={submission_id}"
            )
            
            # ===== 返回最终结果 =====
            exam_result = ExamPaperResult(
                submission_id=submission_id,
                exam_id=exam_id,
                student_id=student_id,
                total_score=total_score,
                max_total_score=max_total_score,
                question_results=grading_results,
                overall_feedback=f"总分: {total_score}/{max_total_score}"
            )
            
            # 更新进度：完成
            self.update_progress(
                stage="completed",
                percentage=100.0,
                details={
                    "total_score": total_score,
                    "max_total_score": max_total_score
                }
            )
            
            logger.info(
                f"试卷批改工作流完成: "
                f"submission_id={submission_id}, "
                f"total_score={total_score}/{max_total_score}"
            )
            
            return exam_result
            
        except Exception as e:
            logger.error(
                f"试卷批改工作流失败: "
                f"submission_id={submission_id}, "
                f"error={str(e)}",
                exc_info=True
            )
            raise
