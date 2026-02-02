"""批注管理 API 路由

独立的批注功能：
- POST /api/annotations/generate - AI 生成批注坐标
- GET /api/annotations/{history_id}/{student_key} - 获取批注列表
- POST /api/annotations - 添加批注
- PUT /api/annotations/{annotation_id} - 更新批注
- DELETE /api/annotations/{annotation_id} - 删除批注
- POST /api/annotations/export/pdf - 导出带批注的 PDF
"""

import base64
import io
import json
import logging
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.db.postgres_grading import (
    GradingAnnotation,
    save_annotation,
    save_annotations_batch,
    get_annotations,
    delete_annotation,
    delete_annotations_for_student,
    update_annotation,
    get_grading_history,
    get_student_result,
    get_page_images_for_student,
)
from src.db.postgres_images import get_batch_images_as_bytes_list


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/annotations", tags=["批注管理"])


# ==================== 请求/响应模型 ====================


class BoundingBoxInput(BaseModel):
    """边界框坐标"""
    x_min: float = Field(..., ge=0, le=1, description="左边界 (0.0-1.0)")
    y_min: float = Field(..., ge=0, le=1, description="上边界 (0.0-1.0)")
    x_max: float = Field(..., ge=0, le=1, description="右边界 (0.0-1.0)")
    y_max: float = Field(..., ge=0, le=1, description="下边界 (0.0-1.0)")


class AnnotationInput(BaseModel):
    """批注输入"""
    annotation_type: str = Field(..., description="批注类型: score, error_circle, comment, m_mark, a_mark, etc.")
    bounding_box: BoundingBoxInput = Field(..., description="位置坐标")
    text: str = Field(default="", description="批注文字")
    color: str = Field(default="#FF0000", description="颜色")
    question_id: str = Field(default="", description="关联题目 ID")
    scoring_point_id: str = Field(default="", description="关联得分点 ID")


class CreateAnnotationRequest(BaseModel):
    """创建批注请求"""
    grading_history_id: str = Field(..., description="批改历史 ID")
    student_key: str = Field(..., description="学生标识")
    page_index: int = Field(..., ge=0, description="页码")
    annotation: AnnotationInput = Field(..., description="批注数据")


class UpdateAnnotationRequest(BaseModel):
    """更新批注请求"""
    bounding_box: Optional[BoundingBoxInput] = None
    text: Optional[str] = None
    color: Optional[str] = None
    annotation_type: Optional[str] = None


class GenerateAnnotationsRequest(BaseModel):
    """生成批注请求"""
    grading_history_id: str = Field(..., description="批改历史 ID")
    student_key: str = Field(..., description="学生标识")
    page_indices: Optional[List[int]] = Field(None, description="指定页码列表，None 表示所有页")
    overwrite: bool = Field(default=False, description="是否覆盖已有批注")


class ExportPdfRequest(BaseModel):
    """导出 PDF 请求"""
    grading_history_id: str = Field(..., description="批改历史 ID")
    student_key: str = Field(..., description="学生标识")
    include_summary: bool = Field(default=True, description="是否包含评分摘要页")


class AnnotationResponse(BaseModel):
    """批注响应"""
    id: str
    grading_history_id: str
    student_key: str
    page_index: int
    annotation_type: str
    bounding_box: Dict[str, float]
    text: str
    color: str
    question_id: str
    scoring_point_id: str
    created_by: str
    created_at: str
    updated_at: str


class AnnotationsListResponse(BaseModel):
    """批注列表响应"""
    success: bool
    annotations: List[AnnotationResponse]
    total: int


class GenerateAnnotationsResponse(BaseModel):
    """生成批注响应"""
    success: bool
    message: str
    generated_count: int
    annotations: List[AnnotationResponse]


# ==================== API 路由 ====================


@router.get(
    "/{grading_history_id}/{student_key}",
    response_model=AnnotationsListResponse,
    summary="获取学生的批注列表"
)
async def list_annotations(
    grading_history_id: str,
    student_key: str,
    page_index: Optional[int] = None,
):
    """获取指定学生的批注列表"""
    try:
        annotations = await get_annotations(grading_history_id, student_key, page_index)
        return AnnotationsListResponse(
            success=True,
            annotations=[
                AnnotationResponse(
                    id=ann.id,
                    grading_history_id=ann.grading_history_id,
                    student_key=ann.student_key,
                    page_index=ann.page_index,
                    annotation_type=ann.annotation_type,
                    bounding_box=ann.bounding_box,
                    text=ann.text,
                    color=ann.color,
                    question_id=ann.question_id,
                    scoring_point_id=ann.scoring_point_id,
                    created_by=ann.created_by,
                    created_at=ann.created_at,
                    updated_at=ann.updated_at,
                )
                for ann in annotations
            ],
            total=len(annotations),
        )
    except Exception as e:
        logger.error(f"获取批注失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "",
    response_model=AnnotationResponse,
    summary="添加批注"
)
async def create_annotation(request: CreateAnnotationRequest):
    """教师手动添加批注"""
    try:
        annotation_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        
        annotation = GradingAnnotation(
            id=annotation_id,
            grading_history_id=request.grading_history_id,
            student_key=request.student_key,
            page_index=request.page_index,
            annotation_type=request.annotation.annotation_type,
            bounding_box=request.annotation.bounding_box.model_dump(),
            text=request.annotation.text,
            color=request.annotation.color,
            question_id=request.annotation.question_id,
            scoring_point_id=request.annotation.scoring_point_id,
            created_by="teacher",
            created_at=now,
            updated_at=now,
        )
        
        success = await save_annotation(annotation)
        if not success:
            raise HTTPException(status_code=500, detail="保存批注失败")
        
        return AnnotationResponse(
            id=annotation.id,
            grading_history_id=annotation.grading_history_id,
            student_key=annotation.student_key,
            page_index=annotation.page_index,
            annotation_type=annotation.annotation_type,
            bounding_box=annotation.bounding_box,
            text=annotation.text,
            color=annotation.color,
            question_id=annotation.question_id,
            scoring_point_id=annotation.scoring_point_id,
            created_by=annotation.created_by,
            created_at=annotation.created_at,
            updated_at=annotation.updated_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"添加批注失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put(
    "/{annotation_id}",
    response_model=dict,
    summary="更新批注"
)
async def update_annotation_endpoint(
    annotation_id: str,
    request: UpdateAnnotationRequest,
):
    """更新批注（位置、文字、颜色等）"""
    try:
        updates = {}
        if request.bounding_box:
            updates["bounding_box"] = request.bounding_box.model_dump()
        if request.text is not None:
            updates["text"] = request.text
        if request.color is not None:
            updates["color"] = request.color
        if request.annotation_type is not None:
            updates["annotation_type"] = request.annotation_type
        
        if not updates:
            raise HTTPException(status_code=400, detail="没有提供更新字段")
        
        success = await update_annotation(annotation_id, updates)
        if not success:
            raise HTTPException(status_code=500, detail="更新批注失败")
        
        return {"success": True, "message": "批注已更新"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新批注失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/{annotation_id}",
    response_model=dict,
    summary="删除批注"
)
async def delete_annotation_endpoint(annotation_id: str):
    """删除单个批注"""
    try:
        success = await delete_annotation(annotation_id)
        if not success:
            raise HTTPException(status_code=500, detail="删除批注失败")
        return {"success": True, "message": "批注已删除"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除批注失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/{grading_history_id}/{student_key}/all",
    response_model=dict,
    summary="删除学生的所有批注"
)
async def delete_student_annotations(
    grading_history_id: str,
    student_key: str,
    page_index: Optional[int] = None,
):
    """删除学生的所有批注（可指定页码）"""
    try:
        count = await delete_annotations_for_student(grading_history_id, student_key, page_index)
        return {"success": True, "deleted_count": count}
    except Exception as e:
        logger.error(f"删除批注失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/generate",
    response_model=GenerateAnnotationsResponse,
    summary="AI 生成批注坐标"
)
async def generate_annotations(request: GenerateAnnotationsRequest):
    """
    使用 AI（VLM）分析图片，生成批注坐标
    
    基于已有的批改结果，为每个得分点定位坐标位置
    """
    try:
        # 1. 获取批改历史和学生结果
        history = await get_grading_history(request.grading_history_id)
        if not history:
            raise HTTPException(status_code=404, detail="批改历史不存在")
        
        student_result = await get_student_result(request.grading_history_id, request.student_key)
        if not student_result:
            raise HTTPException(status_code=404, detail="学生批改结果不存在")
        
        # 2. 获取页面图片
        page_images = await get_page_images_for_student(request.grading_history_id, request.student_key)
        if not page_images:
            logger.warning("未找到学生答题图片，尝试使用 batch_images 兜底")
        
        # 3. 如果不覆盖，先检查是否已有批注
        if not request.overwrite:
            existing = await get_annotations(request.grading_history_id, request.student_key)
            if existing:
                return GenerateAnnotationsResponse(
                    success=True,
                    message=f"已存在 {len(existing)} 个批注，跳过生成。设置 overwrite=true 可覆盖。",
                    generated_count=0,
                    annotations=[
                        AnnotationResponse(
                            id=ann.id,
                            grading_history_id=ann.grading_history_id,
                            student_key=ann.student_key,
                            page_index=ann.page_index,
                            annotation_type=ann.annotation_type,
                            bounding_box=ann.bounding_box,
                            text=ann.text,
                            color=ann.color,
                            question_id=ann.question_id,
                            scoring_point_id=ann.scoring_point_id,
                            created_by=ann.created_by,
                            created_at=ann.created_at,
                            updated_at=ann.updated_at,
                        )
                        for ann in existing
                    ],
                )
        else:
            # 覆盖模式：先删除已有批注
            await delete_annotations_for_student(request.grading_history_id, request.student_key)
        
        # 4. 调用 VLM 生成批注坐标
        from src.services.annotation_generator import generate_annotations_for_student
        
        generated = await generate_annotations_for_student(
            grading_history_id=request.grading_history_id,
            student_key=request.student_key,
            student_result=student_result,
            page_images=page_images,
            batch_id=history.batch_id if history else None,
            page_indices=request.page_indices,
        )
        
        # 5. 保存生成的批注
        saved_count = await save_annotations_batch(generated)
        
        return GenerateAnnotationsResponse(
            success=True,
            message=f"成功生成 {saved_count} 个批注",
            generated_count=saved_count,
            annotations=[
                AnnotationResponse(
                    id=ann.id,
                    grading_history_id=ann.grading_history_id,
                    student_key=ann.student_key,
                    page_index=ann.page_index,
                    annotation_type=ann.annotation_type,
                    bounding_box=ann.bounding_box,
                    text=ann.text,
                    color=ann.color,
                    question_id=ann.question_id,
                    scoring_point_id=ann.scoring_point_id,
                    created_by=ann.created_by,
                    created_at=ann.created_at,
                    updated_at=ann.updated_at,
                )
                for ann in generated
            ],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成批注失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/export/pdf",
    summary="导出带批注的 PDF"
)
async def export_annotated_pdf(request: ExportPdfRequest):
    """
    导出带批注的 PDF 文件
    
    将批注渲染到答题图片上，生成 PDF 文件
    """
    try:
        # 1. 获取批改结果
        student_result = await get_student_result(request.grading_history_id, request.student_key)
        if not student_result:
            raise HTTPException(status_code=404, detail="学生批改结果不存在")

        history = await get_grading_history(request.grading_history_id)
        
        # 2. 获取页面图片
        page_images = await get_page_images_for_student(request.grading_history_id, request.student_key)
        fallback_images = None
        if not page_images:
            if history:
                fallback_list = await get_batch_images_as_bytes_list(history.batch_id, "answer")
                if fallback_list:
                    fallback_images = {idx: img for idx, img in enumerate(fallback_list)}
                    logger.warning("未找到学生答题图片，使用 batch_images 兜底导出 PDF")
            if not fallback_images:
                raise HTTPException(status_code=404, detail="未找到学生答题图片")
        
        # 3. 获取批注
        annotations = await get_annotations(request.grading_history_id, request.student_key)
        
        # 4. 生成带批注的 PDF
        from src.services.pdf_exporter import export_annotated_pdf as generate_pdf
        
        pdf_bytes = await generate_pdf(
            student_result=student_result,
            page_images=page_images,
            annotations=annotations,
            include_summary=request.include_summary,
            fallback_images=fallback_images,
        )
        
        # 5. 返回 PDF 文件
        filename = f"grading_{request.student_key}_{request.grading_history_id[:8]}.pdf"
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(pdf_bytes)),
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"导出 PDF 失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
