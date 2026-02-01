"""批注批改 API 路由

提供带坐标批注的批改接口：
- POST /api/grading/annotate - 批改并返回批注坐标
"""

import base64
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.models.grading_models import QuestionRubric, ScoringPoint
from src.services.annotation_grading import AnnotationGradingService


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/grading", tags=["批注批改"])


# ==================== 请求/响应模型 ====================


class ScoringPointInput(BaseModel):
    """得分点输入"""

    description: str = Field(..., description="得分点描述")
    score: float = Field(..., description="分值")
    point_id: str = Field(default="", description="得分点编号")
    is_required: bool = Field(default=True, description="是否必须")


class QuestionRubricInput(BaseModel):
    """题目评分标准输入"""

    question_id: str = Field(..., description="题号")
    max_score: float = Field(..., description="满分")
    question_text: str = Field(default="", description="题目内容")
    standard_answer: str = Field(default="", description="标准答案")
    scoring_points: List[ScoringPointInput] = Field(default_factory=list, description="得分点列表")
    grading_notes: str = Field(default="", description="批改注意事项")


class AnnotateRequest(BaseModel):
    """批注批改请求"""

    image_base64: str = Field(..., description="图片 Base64 编码")
    rubrics: List[QuestionRubricInput] = Field(..., description="评分标准列表")
    page_index: int = Field(default=0, description="页码")


class AnnotateResponse(BaseModel):
    """批注批改响应"""

    success: bool = Field(..., description="是否成功")
    page_annotations: Optional[dict] = Field(None, description="页面批注信息")
    error: Optional[str] = Field(None, description="错误信息")


class BatchAnnotateRequest(BaseModel):
    """批量批注批改请求"""

    images_base64: List[str] = Field(..., description="图片 Base64 列表")
    rubrics: List[QuestionRubricInput] = Field(..., description="评分标准列表")
    submission_id: str = Field(default="", description="提交 ID")


class BatchAnnotateResponse(BaseModel):
    """批量批注批改响应"""

    success: bool
    result: Optional[dict] = None
    error: Optional[str] = None


# ==================== API 路由 ====================


@router.post("/annotate", response_model=AnnotateResponse, summary="批改单页并返回批注坐标")
async def annotate_page(request: AnnotateRequest):
    """
    批改单页图片并返回带坐标的批注信息

    - 输入：图片 Base64 + 评分标准
    - 输出：批注坐标列表（分数位置、错误圈选、讲解位置等）
    """
    raise HTTPException(
        status_code=410,
        detail="后端批注渲染已禁用，请改为前端 Canvas 渲染。",
    )
    try:
        # 解码图片
        try:
            image_data = base64.b64decode(request.image_base64)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"图片 Base64 解码失败: {e}")

        # 转换评分标准
        rubrics = []
        for r in request.rubrics:
            scoring_points = [
                ScoringPoint(
                    description=sp.description,
                    score=sp.score,
                    point_id=sp.point_id,
                    is_required=sp.is_required,
                )
                for sp in r.scoring_points
            ]
            rubrics.append(
                QuestionRubric(
                    question_id=r.question_id,
                    max_score=r.max_score,
                    question_text=r.question_text,
                    standard_answer=r.standard_answer,
                    scoring_points=scoring_points,
                    grading_notes=r.grading_notes,
                )
            )

        # 调用批注批改服务
        service = AnnotationGradingService()
        page_annotations = await service.grade_page_with_annotations(
            image_data=image_data,
            rubrics=rubrics,
            page_index=request.page_index,
        )

        return AnnotateResponse(
            success=True,
            page_annotations=page_annotations.to_dict(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批注批改失败: {e}", exc_info=True)
        return AnnotateResponse(
            success=False,
            error=str(e),
        )


@router.post(
    "/annotate/batch", response_model=BatchAnnotateResponse, summary="批量批改并返回批注坐标"
)
async def annotate_batch(request: BatchAnnotateRequest):
    """
    批量批改多页图片并返回带坐标的批注信息
    """
    raise HTTPException(
        status_code=410,
        detail="后端批注渲染已禁用，请改为前端 Canvas 渲染。",
    )
    try:
        # 解码所有图片
        pages = []
        for i, img_b64 in enumerate(request.images_base64):
            try:
                pages.append(base64.b64decode(img_b64))
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"第 {i+1} 张图片解码失败: {e}")

        # 转换评分标准
        rubrics = []
        for r in request.rubrics:
            scoring_points = [
                ScoringPoint(
                    description=sp.description,
                    score=sp.score,
                    point_id=sp.point_id,
                    is_required=sp.is_required,
                )
                for sp in r.scoring_points
            ]
            rubrics.append(
                QuestionRubric(
                    question_id=r.question_id,
                    max_score=r.max_score,
                    question_text=r.question_text,
                    standard_answer=r.standard_answer,
                    scoring_points=scoring_points,
                    grading_notes=r.grading_notes,
                )
            )

        # 调用批注批改服务
        service = AnnotationGradingService()
        result = await service.grade_submission_with_annotations(
            pages=pages,
            rubrics=rubrics,
            submission_id=request.submission_id,
        )

        return BatchAnnotateResponse(
            success=True,
            result=result.to_dict(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量批注批改失败: {e}", exc_info=True)
        return BatchAnnotateResponse(
            success=False,
            error=str(e),
        )


