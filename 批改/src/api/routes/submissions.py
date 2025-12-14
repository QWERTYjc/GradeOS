"""提交相关 API 端点"""

from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form
from typing import Optional
import base64

from src.models.submission import (
    SubmissionRequest,
    SubmissionResponse,
    SubmissionStatusResponse
)
from src.models.grading import ExamPaperResult
from src.services.submission import SubmissionService
from src.repositories.submission import SubmissionRepository
from src.repositories.grading_result import GradingResultRepository
from src.utils.database import get_db_pool

router = APIRouter(prefix="/api/v1/submissions", tags=["submissions"])


@router.post("", response_model=SubmissionResponse, status_code=status.HTTP_201_CREATED)
async def submit_for_grading(
    exam_id: str = Form(..., description="考试 ID"),
    student_id: str = Form(..., description="学生 ID"),
    file: UploadFile = File(..., description="试卷文件（PDF 或图像）")
) -> SubmissionResponse:
    """
    上传并提交批改
    
    - **exam_id**: 考试 ID
    - **student_id**: 学生 ID
    - **file**: 试卷文件（支持 PDF、JPEG、PNG、WEBP）
    
    返回提交 ID 和预计完成时间
    
    **需求：1.3**
    """
    try:
        # 读取文件数据
        file_data = await file.read()
        
        # 确定文件类型
        file_type = "pdf" if file.filename.lower().endswith(".pdf") else "image"
        
        # 创建提交请求
        request = SubmissionRequest(
            exam_id=exam_id,
            student_id=student_id,
            file_type=file_type,
            file_data=file_data
        )
        
        # 获取数据库连接池
        pool = await get_db_pool()
        
        if pool is None:
            import uuid
            import datetime
            # Offline Mode: Return mock response
            mock_id = str(uuid.uuid4())
            return SubmissionResponse(
                submission_id=mock_id,
                exam_id=exam_id,
                student_id=student_id,
                status="UPLOADED",
                created_at=datetime.datetime.now(),
                estimated_completion_time=30
            )

        # 创建服务实例
        submission_repo = SubmissionRepository(pool)
        submission_service = SubmissionService(submission_repo)
        
        # 处理提交
        response = await submission_service.submit(request)
        
        return response
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"提交处理失败: {str(e)}"
        )


@router.get("/{submission_id}", response_model=SubmissionStatusResponse)
async def get_submission_status(submission_id: str) -> SubmissionStatusResponse:
    """
    获取提交状态
    
    - **submission_id**: 提交 ID
    
    返回提交的当前状态和基本信息
    
    **需求：7.4**
    """
    try:
        # 获取数据库连接池
        pool = await get_db_pool()
        
        # 创建仓储实例
        submission_repo = SubmissionRepository(pool)
        
        # 查询提交状态
        submission = await submission_repo.get_by_id(submission_id)
        
        if not submission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"提交 {submission_id} 不存在"
            )
        
        return SubmissionStatusResponse(
            submission_id=submission["submission_id"],
            exam_id=submission["exam_id"],
            student_id=submission["student_id"],
            status=submission["status"],
            total_score=submission.get("total_score"),
            max_total_score=submission.get("max_total_score"),
            created_at=submission["created_at"].isoformat(),
            updated_at=submission["updated_at"].isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询提交状态失败: {str(e)}"
        )


@router.get("/{submission_id}/results", response_model=ExamPaperResult)
async def get_grading_results(submission_id: str) -> ExamPaperResult:
    """
    获取批改结果
    
    - **submission_id**: 提交 ID
    
    返回完整的批改结果，包括各题目的详细评分和反馈
    
    **需求：7.4**
    """
    try:
        # 获取数据库连接池
        pool = await get_db_pool()
        
        # 创建仓储实例
        submission_repo = SubmissionRepository(pool)
        grading_result_repo = GradingResultRepository(pool)
        
        # 查询提交信息
        submission = await submission_repo.get_by_id(submission_id)
        
        if not submission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"提交 {submission_id} 不存在"
            )
        
        # 检查批改是否完成
        if submission["status"] not in ["COMPLETED", "REVIEWING"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"批改尚未完成，当前状态: {submission['status']}"
            )
        
        # 查询批改结果
        results = await grading_result_repo.get_by_submission_id(submission_id)
        
        if not results:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到提交 {submission_id} 的批改结果"
            )
        
        # 构建响应
        from src.models.grading import GradingResult
        
        question_results = []
        for result in results:
            question_results.append(GradingResult(
                question_id=result["question_id"],
                score=float(result["score"]),
                max_score=float(result["max_score"]),
                confidence=float(result["confidence_score"]),
                feedback=result.get("student_feedback", {}).get("text", ""),
                visual_annotations=result.get("visual_annotations", []),
                agent_trace=result.get("agent_trace", {})
            ))
        
        return ExamPaperResult(
            submission_id=submission_id,
            exam_id=submission["exam_id"],
            student_id=submission["student_id"],
            total_score=float(submission.get("total_score", 0)),
            max_total_score=float(submission.get("max_total_score", 0)),
            question_results=question_results,
            overall_feedback=None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询批改结果失败: {str(e)}"
        )
