"""提交处理服务

负责文件上传预处理、验证、存储和工作流触发
"""

import uuid
import logging
from typing import List, Optional, Dict, Any

from src.models.submission import SubmissionRequest, SubmissionResponse, SubmissionStatusResponse
from src.models.enums import FileType, SubmissionStatus
from src.repositories.submission import SubmissionRepository
from src.services.storage import StorageService
from src.utils.pdf import convert_pdf_to_images, PDFProcessingError
from src.utils.validation import validate_file, FileValidationError
from src.orchestration.base import Orchestrator


logger = logging.getLogger(__name__)


class SubmissionServiceError(Exception):
    """提交服务错误"""
    pass


class SubmissionService:
    """
    提交处理服务
    
    验证：需求 1.1, 1.2, 1.3, 1.4, 1.5
    """
    
    def __init__(
        self,
        repository: SubmissionRepository,
        storage: StorageService,
        orchestrator: Optional[Orchestrator] = None
    ):
        """
        初始化提交服务
        
        Args:
            repository: 提交记录仓储
            storage: 对象存储服务
            orchestrator: 编排器实例（可选，用于启动工作流）
        """
        self.repository = repository
        self.storage = storage
        self.orchestrator = orchestrator
    
    async def submit(self, request: SubmissionRequest) -> SubmissionResponse:
        """
        处理提交请求
        
        Args:
            request: 提交请求
            
        Returns:
            提交响应
            
        Raises:
            SubmissionServiceError: 处理失败时抛出
            
        验证：需求 1.1, 1.2, 1.3, 1.4
        """
        try:
            # 生成提交 ID
            submission_id = str(uuid.uuid4())
            
            logger.info(
                f"开始处理提交: "
                f"submission_id={submission_id}, "
                f"exam_id={request.exam_id}, "
                f"student_id={request.student_id}, "
                f"file_type={request.file_type}"
            )
            
            # ===== 第一步：文件验证 =====
            logger.info(f"验证文件: submission_id={submission_id}")
            
            # 验证文件大小
            is_image = request.file_type == FileType.IMAGE
            try:
                validate_file(request.file_data, is_image=is_image)
            except FileValidationError as e:
                logger.error(
                    f"文件验证失败: "
                    f"submission_id={submission_id}, "
                    f"error={str(e)}"
                )
                raise SubmissionServiceError(str(e)) from e
            
            # ===== 第二步：文件预处理 =====
            logger.info(f"预处理文件: submission_id={submission_id}")
            
            images_data: List[bytes] = []
            
            if request.file_type == FileType.PDF:
                # PDF 转图像（300 DPI）
                logger.info(
                    f"转换 PDF 为图像: "
                    f"submission_id={submission_id}"
                )
                try:
                    images_data = await convert_pdf_to_images(
                        request.file_data,
                        dpi=300
                    )
                    logger.info(
                        f"PDF 转换完成: "
                        f"submission_id={submission_id}, "
                        f"页数={len(images_data)}"
                    )
                except PDFProcessingError as e:
                    logger.error(
                        f"PDF 转换失败: "
                        f"submission_id={submission_id}, "
                        f"error={str(e)}"
                    )
                    raise SubmissionServiceError(f"PDF 转换失败: {str(e)}") from e
            
            elif request.file_type == FileType.IMAGE:
                # 直接使用图像
                images_data = [request.file_data]
                logger.info(
                    f"使用图像文件: "
                    f"submission_id={submission_id}"
                )
            
            else:
                raise SubmissionServiceError(
                    f"不支持的文件类型: {request.file_type}"
                )
            
            # ===== 第三步：保存到对象存储 =====
            logger.info(
                f"保存文件到存储: "
                f"submission_id={submission_id}, "
                f"文件数={len(images_data)}"
            )
            
            try:
                file_paths = await self.storage.save_files(
                    images_data,
                    submission_id,
                    extension="png"
                )
                logger.info(
                    f"文件保存完成: "
                    f"submission_id={submission_id}, "
                    f"文件路径={file_paths}"
                )
            except Exception as e:
                logger.error(
                    f"文件保存失败: "
                    f"submission_id={submission_id}, "
                    f"error={str(e)}"
                )
                raise SubmissionServiceError(f"文件保存失败: {str(e)}") from e
            
            # ===== 第四步：创建数据库记录 =====
            logger.info(
                f"创建提交记录: "
                f"submission_id={submission_id}"
            )
            
            try:
                submission_data = await self.repository.create(
                    exam_id=request.exam_id,
                    student_id=request.student_id,
                    file_paths=file_paths,
                    status=SubmissionStatus.UPLOADED
                )
                logger.info(
                    f"提交记录创建完成: "
                    f"submission_id={submission_data['submission_id']}"
                )
            except Exception as e:
                logger.error(
                    f"创建提交记录失败: "
                    f"submission_id={submission_id}, "
                    f"error={str(e)}"
                )
                # 清理已保存的文件
                try:
                    await self.storage.delete_files(submission_id)
                except Exception:
                    pass
                raise SubmissionServiceError(f"创建提交记录失败: {str(e)}") from e
            
            # ===== 第五步：异步启动工作流 =====
            if self.orchestrator:
                logger.info(
                    f"启动工作流: "
                    f"submission_id={submission_id}"
                )
                
                try:
                    # 准备工作流输入
                    workflow_input = {
                        "submission_id": submission_data["submission_id"],
                        "student_id": request.student_id,
                        "exam_id": request.exam_id,
                        "file_paths": file_paths
                    }
                    
                    # 启动工作流（异步，不等待结果）
                    run_id = await self.orchestrator.start_run(
                        graph_name="exam_paper",
                        payload=workflow_input,
                        idempotency_key=submission_id
                    )
                    
                    logger.info(
                        f"工作流已启动: "
                        f"submission_id={submission_id}, "
                        f"run_id={run_id}"
                    )
                    
                except Exception as e:
                    logger.error(
                        f"启动工作流失败: "
                        f"submission_id={submission_id}, "
                        f"error={str(e)}",
                        exc_info=True
                    )
                    # 工作流启动失败不影响提交成功
                    # 可以通过后台任务重试
            else:
                logger.warning(
                    f"编排器未配置，跳过工作流启动: "
                    f"submission_id={submission_id}"
                )
            
            # ===== 第六步：返回响应 =====
            # 估算完成时间（每道题 30 秒，假设平均 4 道题）
            estimated_time = len(images_data) * 4 * 30
            
            response = SubmissionResponse(
                submission_id=submission_data["submission_id"],
                status=SubmissionStatus.UPLOADED,
                estimated_completion_time=estimated_time
            )
            
            logger.info(
                f"提交处理完成: "
                f"submission_id={submission_id}, "
                f"estimated_time={estimated_time}s"
            )
            
            return response
            
        except SubmissionServiceError:
            raise
        except Exception as e:
            logger.error(
                f"提交处理失败: "
                f"error={str(e)}",
                exc_info=True
            )
            raise SubmissionServiceError(f"提交处理失败: {str(e)}") from e
    
    async def get_status(self, submission_id: str) -> Optional[SubmissionStatusResponse]:
        """
        查询提交状态
        
        Args:
            submission_id: 提交 ID
            
        Returns:
            提交状态响应，如果不存在则返回 None
            
        验证：需求 7.4
        """
        try:
            submission_data = await self.repository.get_by_id(submission_id)
            
            if not submission_data:
                return None
            
            return SubmissionStatusResponse(
                submission_id=submission_data["submission_id"],
                exam_id=submission_data["exam_id"],
                student_id=submission_data["student_id"],
                status=SubmissionStatus(submission_data["status"]),
                total_score=submission_data.get("total_score"),
                max_total_score=submission_data.get("max_total_score"),
                created_at=submission_data["created_at"],
                updated_at=submission_data["updated_at"]
            )
            
        except Exception as e:
            logger.error(
                f"查询提交状态失败: "
                f"submission_id={submission_id}, "
                f"error={str(e)}"
            )
            raise SubmissionServiceError(f"查询提交状态失败: {str(e)}") from e
