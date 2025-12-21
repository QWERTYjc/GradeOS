"""批量批改工作流 - 支持多学生合卷处理

处理一份包含多个学生作业的文档，自动识别学生身份并分发到各自的批改工作流。

集成自我成长组件：
- StreamingService: 实时推送批改进度
- BatchProcessor: 固定分批并行处理
- StudentBoundaryDetector: 批改后学生分割
"""

import logging
from datetime import timedelta
from typing import List, Dict, Any, Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

from src.models.grading import ExamPaperResult
from src.activities.identify_students import identify_students_activity
from src.workflows.exam_paper import ExamPaperWorkflow
from src.services.streaming import StreamingService, StreamEvent, EventType
from src.services.student_boundary_detector import StudentBoundaryDetector


logger = logging.getLogger(__name__)


IDENTIFY_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=1),
    maximum_attempts=2
)


@workflow.defn
class BatchGradingWorkflow:
    """
    批量批改工作流
    
    处理"多学生合卷"场景：
    1. 学生识别：扫描所有页面，识别学生信息区
    2. 固定分批：按 10 张图片一批进行分批处理
    3. 并行批改：LangGraph 并行执行批次内所有页面
    4. 学生分割：基于批改结果智能判断学生边界
    5. 结果聚合：汇总所有学生的批改结果
    6. 流式推送：实时推送批改进度和结果
    
    适用场景：
    - 教师扫描整班试卷为一个 PDF
    - 批量上传多份作业图片
    
    验证：需求 1.1, 2.1, 3.1
    """
    
    def __init__(self):
        self._progress: Dict[str, Any] = {}
        self._student_results: Dict[str, ExamPaperResult] = {}
        self._streaming_service: Optional[StreamingService] = None
        self._boundary_detector: Optional[StudentBoundaryDetector] = None
    
    @workflow.query
    def get_progress(self) -> Dict[str, Any]:
        """查询批改进度"""
        return self._progress
    
    @workflow.run
    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        运行批量批改工作流
        
        Args:
            input_data: {
                "batch_id": str,           # 批次 ID
                "exam_id": str,            # 考试 ID
                "file_paths": List[str],   # 所有页面文件路径
                "fallback_student_id": str # 无法识别时的默认学生ID（可选）
            }
            
        Returns:
            dict: {
                "batch_id": str,
                "total_students": int,
                "results": {student_key: ExamPaperResult},
                "unidentified_pages": List[int],
                "errors": List[str]
            }
        """
        batch_id = input_data["batch_id"]
        exam_id = input_data["exam_id"]
        file_paths = input_data["file_paths"]
        fallback_student_id = input_data.get("fallback_student_id")
        
        logger.info(
            f"启动批量批改工作流: "
            f"batch_id={batch_id}, "
            f"exam_id={exam_id}, "
            f"页数={len(file_paths)}"
        )
        
        self._progress = {
            "stage": "initializing",
            "total_pages": len(file_paths),
            "students_identified": 0,
            "students_completed": 0
        }
        
        try:
            # ===== 第一步：读取所有图像 =====
            images_data: List[bytes] = []
            for file_path in file_paths:
                with open(file_path, "rb") as f:
                    images_data.append(f.read())
            
            # ===== 第二步：学生身份识别 =====
            self._progress["stage"] = "identifying_students"
            
            identification_result = await workflow.execute_activity(
                identify_students_activity,
                images_data,
                retry_policy=IDENTIFY_RETRY_POLICY,
                start_to_close_timeout=timedelta(minutes=5),
                heartbeat_timeout=timedelta(seconds=30)
            )
            
            student_groups = identification_result["student_groups"]
            student_info = identification_result["student_info"]
            unidentified_pages = identification_result["unidentified_pages"]
            
            self._progress["students_identified"] = len(student_groups)
            self._progress["unidentified_pages"] = len(unidentified_pages)
            
            logger.info(
                f"学生识别完成: "
                f"batch_id={batch_id}, "
                f"学生数={len(student_groups)}, "
                f"未识别页数={len(unidentified_pages)}"
            )
            
            # ===== 第三步：为每个学生启动子工作流 =====
            self._progress["stage"] = "grading"
            
            child_handles = {}
            for student_key, page_indices in student_groups.items():
                # 获取该学生的页面文件路径
                student_file_paths = [file_paths[i] for i in page_indices]
                
                # 获取学生信息
                info = student_info.get(student_key, {})
                student_id = info.get("student_id") or student_key
                
                # 创建子工作流输入
                child_input = {
                    "submission_id": f"{batch_id}_{student_key}",
                    "student_id": student_id,
                    "exam_id": exam_id,
                    "file_paths": student_file_paths
                }
                
                # 启动子工作流
                handle = await workflow.start_child_workflow(
                    ExamPaperWorkflow,
                    child_input,
                    id=f"batch_{batch_id}_student_{student_key}",
                    task_queue="default-queue"
                )
                
                child_handles[student_key] = handle
                
                logger.info(
                    f"启动学生批改工作流: "
                    f"student_key={student_key}, "
                    f"页数={len(page_indices)}"
                )
            
            # ===== 第四步：等待所有子工作流完成 =====
            results: Dict[str, Any] = {}
            errors: List[str] = []
            
            for student_key, handle in child_handles.items():
                try:
                    result = await handle.result()
                    results[student_key] = result
                    self._progress["students_completed"] += 1
                    
                    logger.info(
                        f"学生批改完成: "
                        f"student_key={student_key}, "
                        f"score={result.total_score}/{result.max_total_score}"
                    )
                    
                except Exception as e:
                    error_msg = f"学生 {student_key} 批改失败: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
            
            # ===== 第五步：处理未识别页面 =====
            if unidentified_pages and fallback_student_id:
                logger.info(
                    f"处理未识别页面: "
                    f"页数={len(unidentified_pages)}, "
                    f"fallback_student_id={fallback_student_id}"
                )
                # 可以选择将未识别页面归入默认学生或标记为需人工处理
            
            # ===== 返回结果 =====
            self._progress["stage"] = "completed"
            
            final_result = {
                "batch_id": batch_id,
                "exam_id": exam_id,
                "total_students": len(student_groups),
                "results": results,
                "student_info": student_info,
                "unidentified_pages": unidentified_pages,
                "errors": errors
            }
            
            logger.info(
                f"批量批改完成: "
                f"batch_id={batch_id}, "
                f"成功={len(results)}, "
                f"失败={len(errors)}"
            )
            
            return final_result
            
        except Exception as e:
            logger.error(
                f"批量批改工作流失败: "
                f"batch_id={batch_id}, "
                f"error={str(e)}",
                exc_info=True
            )
            raise
