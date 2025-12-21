"""增强版批量批改工作流 - 集成自我成长组件

集成以下新组件：
1. StreamingService: 实时推送批改进度（需求 1.1）
2. BatchProcessor: 固定分批并行处理（需求 2.1）
3. StudentBoundaryDetector: 批改后学生分割（需求 3.1）

验证：需求 1.1, 2.1, 3.1
"""

import logging
import asyncio
from datetime import timedelta, datetime
from typing import List, Dict, Any, Optional
from uuid import uuid4

from temporalio import workflow
from temporalio.common import RetryPolicy
import redis.asyncio as redis

from src.models.grading import ExamPaperResult
from src.workflows.exam_paper import ExamPaperWorkflow
from src.services.streaming import StreamingService, StreamEvent, EventType
from src.services.student_boundary_detector import StudentBoundaryDetector
from src.utils.pool_manager import UnifiedPoolManager


logger = logging.getLogger(__name__)


# 固定批次大小
BATCH_SIZE = 10

GRADING_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=1),
    maximum_attempts=3
)


@workflow.defn
class EnhancedBatchGradingWorkflow:
    """
    增强版批量批改工作流
    
    核心流程：
    1. 创建流式连接，推送 BATCH_START 事件
    2. 按 10 张图片一批进行分批
    3. 并行批改每个批次内的所有页面
    4. 推送 PAGE_COMPLETE 和 BATCH_COMPLETE 事件
    5. 基于批改结果检测学生边界
    6. 推送 STUDENT_IDENTIFIED 事件
    7. 汇总结果，推送 COMPLETE 事件
    
    验证：需求 1.1, 2.1, 3.1
    """
    
    def __init__(self):
        self._progress: Dict[str, Any] = {}
        self._grading_results: List[Dict[str, Any]] = []
        self._stream_id: Optional[str] = None
        self._sequence_number: int = 0
    
    @workflow.query
    def get_progress(self) -> Dict[str, Any]:
        """查询批改进度"""
        return self._progress
    
    @workflow.run
    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        运行增强版批量批改工作流
        
        Args:
            input_data: {
                "batch_id": str,           # 批次 ID
                "exam_id": str,            # 考试 ID
                "file_paths": List[str],   # 所有页面文件路径
                "rubric": str,             # 评分细则
                "teacher_id": str,         # 教师 ID
                "enable_streaming": bool,  # 是否启用流式推送（默认 True）
            }
            
        Returns:
            dict: {
                "batch_id": str,
                "total_pages": int,
                "total_batches": int,
                "total_students": int,
                "student_boundaries": List[StudentBoundary],
                "grading_results": List[Dict],
                "unassigned_pages": List[int],
                "errors": List[str]
            }
        """
        batch_id = input_data["batch_id"]
        exam_id = input_data["exam_id"]
        file_paths = input_data["file_paths"]
        rubric = input_data.get("rubric", "")
        teacher_id = input_data.get("teacher_id", "default_teacher")
        enable_streaming = input_data.get("enable_streaming", True)
        
        total_pages = len(file_paths)
        
        logger.info(
            f"启动增强版批量批改工作流: "
            f"batch_id={batch_id}, "
            f"exam_id={exam_id}, "
            f"页数={total_pages}"
        )
        
        # 初始化进度
        self._progress = {
            "stage": "initializing",
            "total_pages": total_pages,
            "pages_completed": 0,
            "batches_completed": 0,
            "students_identified": 0
        }
        
        # 初始化服务（在 Activity 中执行）
        streaming_service = None
        boundary_detector = None
        
        try:
            # ===== 第一步：创建流式连接 =====
            if enable_streaming:
                self._stream_id = batch_id
                # 注意：在 Temporal Workflow 中不能直接创建外部连接
                # 需要通过 Activity 来执行
                await self._push_stream_event(
                    EventType.BATCH_START,
                    {
                        "batch_id": batch_id,
                        "total_pages": total_pages,
                        "started_at": datetime.now().isoformat()
                    }
                )
                logger.info(f"流式连接已创建: stream_id={self._stream_id}")
            
            # ===== 第二步：固定分批 =====
            self._progress["stage"] = "batching"
            batches = self._create_batches(file_paths)
            total_batches = len(batches)
            
            logger.info(f"分批完成: 共 {total_batches} 个批次")
            
            # ===== 第三步：并行批改每个批次 =====
            self._progress["stage"] = "grading"
            all_grading_results = []
            errors = []
            
            for batch_index, batch_file_paths in enumerate(batches):
                logger.info(f"开始批改批次 {batch_index + 1}/{total_batches}")
                
                # 并行批改批次内的所有页面
                batch_results = await self._process_batch_parallel(
                    batch_index=batch_index,
                    batch_file_paths=batch_file_paths,
                    exam_id=exam_id,
                    rubric=rubric,
                    teacher_id=teacher_id
                )
                
                # 收集结果
                for result in batch_results:
                    if "error" in result:
                        errors.append(result["error"])
                    else:
                        all_grading_results.append(result)
                        self._progress["pages_completed"] += 1
                        
                        # 推送页面完成事件
                        if enable_streaming:
                            await self._push_stream_event(
                                EventType.PAGE_COMPLETE,
                                {
                                    "page_index": result.get("page_index"),
                                    "score": result.get("score"),
                                    "confidence": result.get("confidence")
                                }
                            )
                
                # 推送批次完成事件
                self._progress["batches_completed"] += 1
                if enable_streaming:
                    await self._push_stream_event(
                        EventType.BATCH_COMPLETE,
                        {
                            "batch_index": batch_index,
                            "pages_in_batch": len(batch_file_paths),
                            "success_count": len([r for r in batch_results if "error" not in r]),
                            "failure_count": len([r for r in batch_results if "error" in r])
                        }
                    )
                
                logger.info(
                    f"批次 {batch_index + 1} 完成: "
                    f"成功 {len([r for r in batch_results if 'error' not in r])}, "
                    f"失败 {len([r for r in batch_results if 'error' in r])}"
                )
            
            # ===== 第四步：学生边界检测 =====
            self._progress["stage"] = "boundary_detection"
            
            # 通过 Activity 执行边界检测
            boundary_result = await self._detect_student_boundaries(all_grading_results)
            
            student_boundaries = boundary_result.get("boundaries", [])
            unassigned_pages = boundary_result.get("unassigned_pages", [])
            
            self._progress["students_identified"] = len(student_boundaries)
            
            # 推送学生识别事件
            if enable_streaming:
                for boundary in student_boundaries:
                    await self._push_stream_event(
                        EventType.STUDENT_IDENTIFIED,
                        {
                            "student_key": boundary.get("student_key"),
                            "start_page": boundary.get("start_page"),
                            "end_page": boundary.get("end_page"),
                            "confidence": boundary.get("confidence"),
                            "needs_confirmation": boundary.get("needs_confirmation")
                        }
                    )
            
            logger.info(
                f"学生边界检测完成: "
                f"识别到 {len(student_boundaries)} 个学生, "
                f"未分配页面 {len(unassigned_pages)} 页"
            )
            
            # ===== 第五步：汇总结果 =====
            self._progress["stage"] = "completed"
            
            final_result = {
                "batch_id": batch_id,
                "exam_id": exam_id,
                "total_pages": total_pages,
                "total_batches": total_batches,
                "total_students": len(student_boundaries),
                "student_boundaries": student_boundaries,
                "grading_results": all_grading_results,
                "unassigned_pages": unassigned_pages,
                "errors": errors,
                "completed_at": datetime.now().isoformat()
            }
            
            # 推送完成事件
            if enable_streaming:
                await self._push_stream_event(
                    EventType.COMPLETE,
                    {
                        "total_students": len(student_boundaries),
                        "total_pages": total_pages,
                        "success_count": len(all_grading_results),
                        "failure_count": len(errors)
                    }
                )
            
            logger.info(
                f"批量批改完成: "
                f"batch_id={batch_id}, "
                f"学生数={len(student_boundaries)}, "
                f"成功页数={len(all_grading_results)}, "
                f"失败页数={len(errors)}"
            )
            
            return final_result
            
        except Exception as e:
            logger.error(
                f"批量批改工作流失败: "
                f"batch_id={batch_id}, "
                f"error={str(e)}",
                exc_info=True
            )
            
            # 推送错误事件
            if enable_streaming and self._stream_id:
                await self._push_stream_event(
                    EventType.ERROR,
                    {
                        "error": "workflow_failed",
                        "message": str(e),
                        "retry_suggestion": "请检查输入数据后重试"
                    }
                )
            
            raise
    
    def _create_batches(self, file_paths: List[str]) -> List[List[str]]:
        """
        将文件路径按固定批次大小分批
        
        验证：需求 2.1
        属性 1：分批正确性
        
        Args:
            file_paths: 文件路径列表
            
        Returns:
            批次列表，每个批次最多包含 BATCH_SIZE 个文件路径
        """
        batches = []
        for i in range(0, len(file_paths), BATCH_SIZE):
            batch = file_paths[i:i + BATCH_SIZE]
            batches.append(batch)
        
        logger.debug(f"创建了 {len(batches)} 个批次，每批最多 {BATCH_SIZE} 张图片")
        return batches
    
    async def _process_batch_parallel(
        self,
        batch_index: int,
        batch_file_paths: List[str],
        exam_id: str,
        rubric: str,
        teacher_id: str
    ) -> List[Dict[str, Any]]:
        """
        并行处理单个批次内的所有页面
        
        验证：需求 2.3
        属性 2：并行执行完整性
        
        Args:
            batch_index: 批次索引
            batch_file_paths: 批次内的文件路径列表
            exam_id: 考试 ID
            rubric: 评分细则
            teacher_id: 教师 ID
            
        Returns:
            批改结果列表
        """
        # 创建并行任务
        tasks = []
        for page_index_in_batch, file_path in enumerate(batch_file_paths):
            global_page_index = batch_index * BATCH_SIZE + page_index_in_batch
            
            # 启动子工作流批改单个页面
            task = workflow.start_child_workflow(
                "GradePageWorkflow",  # 假设有一个单页批改工作流
                {
                    "page_index": global_page_index,
                    "file_path": file_path,
                    "exam_id": exam_id,
                    "rubric": rubric,
                    "teacher_id": teacher_id
                },
                id=f"page_{global_page_index}_{uuid4()}",
                task_queue="vision-compute-queue",
                retry_policy=GRADING_RETRY_POLICY
            )
            tasks.append(task)
        
        # 等待所有任务完成
        results = []
        for i, task in enumerate(tasks):
            try:
                handle = await task
                result = await handle.result()
                results.append(result)
            except Exception as e:
                global_page_index = batch_index * BATCH_SIZE + i
                logger.error(f"页面 {global_page_index} 批改失败: {e}")
                results.append({
                    "page_index": global_page_index,
                    "error": str(e),
                    "status": "failed"
                })
        
        return results
    
    async def _detect_student_boundaries(
        self,
        grading_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        检测学生边界
        
        验证：需求 3.1
        属性 5：学生边界检测触发
        
        Args:
            grading_results: 批改结果列表
            
        Returns:
            边界检测结果
        """
        # 通过 Activity 执行边界检测
        # 注意：在 Temporal Workflow 中不能直接调用外部服务
        # 需要通过 Activity 来执行
        
        result = await workflow.execute_activity(
            "detect_student_boundaries_activity",
            grading_results,
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1),
                maximum_attempts=3
            )
        )
        
        return result
    
    async def _push_stream_event(
        self,
        event_type: EventType,
        data: Dict[str, Any]
    ) -> None:
        """
        推送流式事件
        
        验证：需求 1.2
        
        Args:
            event_type: 事件类型
            data: 事件数据
        """
        if not self._stream_id:
            return
        
        # 通过 Activity 推送事件
        # 注意：在 Temporal Workflow 中不能直接调用外部服务
        try:
            await workflow.execute_activity(
                "push_stream_event_activity",
                {
                    "stream_id": self._stream_id,
                    "event_type": event_type.value,
                    "data": data,
                    "sequence_number": self._sequence_number
                },
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(milliseconds=100),
                    maximum_attempts=3
                )
            )
            
            self._sequence_number += 1
            
        except Exception as e:
            logger.warning(f"推送流式事件失败: {e}")
            # 不抛出异常，避免影响主流程
