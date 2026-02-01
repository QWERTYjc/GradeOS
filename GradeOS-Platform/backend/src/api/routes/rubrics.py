"""评分细则相关 API 端点"""

from fastapi import APIRouter, HTTPException, status
from typing import Optional

from src.models.rubric import Rubric, RubricCreateRequest, RubricUpdateRequest
from src.services.rubric import RubricService
from src.repositories.rubric import RubricRepository
from src.utils.database import get_db_pool

router = APIRouter(prefix="/api/v1/rubrics", tags=["rubrics"])


@router.post("", response_model=Rubric, status_code=status.HTTP_201_CREATED)
async def create_rubric(request: RubricCreateRequest) -> Rubric:
    """
    创建评分细则

    - **exam_id**: 考试 ID
    - **question_id**: 题目 ID
    - **rubric_text**: 评分细则文本
    - **max_score**: 满分
    - **scoring_points**: 评分点列表
    - **standard_answer**: 标准答案（可选）

    返回创建的评分细则

    **需求：9.1**
    """
    try:
        # 获取数据库连接池
        pool = await get_db_pool()

        # 创建服务实例
        rubric_repo = RubricRepository(pool)
        rubric_service = RubricService(rubric_repo)

        # 创建评分细则
        rubric = await rubric_service.create_rubric(
            exam_id=request.exam_id,
            question_id=request.question_id,
            rubric_text=request.rubric_text,
            max_score=request.max_score,
            scoring_points=[point.model_dump() for point in request.scoring_points],
            standard_answer=request.standard_answer,
        )

        return rubric

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"创建评分细则失败: {str(e)}"
        )


@router.get("/{exam_id}/{question_id}", response_model=Rubric)
async def get_rubric(exam_id: str, question_id: str) -> Rubric:
    """
    获取评分细则

    - **exam_id**: 考试 ID
    - **question_id**: 题目 ID

    返回指定题目的评分细则

    **需求：9.2**
    """
    try:
        # 获取数据库连接池
        pool = await get_db_pool()

        # 创建仓储实例
        rubric_repo = RubricRepository(pool)

        # 查询评分细则
        rubric = await rubric_repo.get_by_exam_and_question(exam_id, question_id)

        if not rubric:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到考试 {exam_id} 题目 {question_id} 的评分细则",
            )

        # 构建响应
        from src.models.rubric import ScoringPoint

        scoring_points = [ScoringPoint(**point) for point in rubric.get("scoring_points", [])]

        return Rubric(
            rubric_id=rubric["rubric_id"],
            exam_id=rubric["exam_id"],
            question_id=rubric["question_id"],
            rubric_text=rubric["rubric_text"],
            max_score=float(rubric["max_score"]),
            scoring_points=scoring_points,
            standard_answer=rubric.get("standard_answer"),
            created_at=rubric["created_at"].isoformat() if rubric.get("created_at") else None,
            updated_at=rubric["updated_at"].isoformat() if rubric.get("updated_at") else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"查询评分细则失败: {str(e)}"
        )


@router.put("/{rubric_id}", response_model=Rubric)
async def update_rubric(rubric_id: str, request: RubricUpdateRequest) -> Rubric:
    """
    更新评分细则

    - **rubric_id**: 评分细则 ID
    - **rubric_text**: 评分细则文本（可选）
    - **max_score**: 满分（可选）
    - **scoring_points**: 评分点列表（可选）
    - **standard_answer**: 标准答案（可选）

    返回更新后的评分细则

    **需求：9.2**
    """
    try:
        # 获取数据库连接池
        pool = await get_db_pool()

        # 创建服务实例
        rubric_repo = RubricRepository(pool)
        rubric_service = RubricService(rubric_repo)

        # 准备更新数据
        update_data = {}
        if request.rubric_text is not None:
            update_data["rubric_text"] = request.rubric_text
        if request.max_score is not None:
            update_data["max_score"] = request.max_score
        if request.scoring_points is not None:
            update_data["scoring_points"] = [point.model_dump() for point in request.scoring_points]
        if request.standard_answer is not None:
            update_data["standard_answer"] = request.standard_answer

        # 更新评分细则
        rubric = await rubric_service.update_rubric(rubric_id, update_data)

        if not rubric:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"评分细则 {rubric_id} 不存在"
            )

        return rubric

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"更新评分细则失败: {str(e)}"
        )
