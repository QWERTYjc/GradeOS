"""人工审核相关 API 端点"""

from fastapi import APIRouter, HTTPException, status
from typing import List

from src.models.review import ReviewSignal, PendingReview
from src.repositories.submission import SubmissionRepository
from src.repositories.grading_result import GradingResultRepository
from src.utils.database import get_db_pool

router = APIRouter(prefix="/api/v1/reviews", tags=["reviews"])


@router.post("/{submission_id}/signal", status_code=status.HTTP_200_OK)
async def send_review_signal(submission_id: str, signal: ReviewSignal) -> dict:
    """
    发送审核信号

    - **submission_id**: 提交 ID
    - **signal**: 审核信号，包含操作类型和相关数据

    支持的操作：
    - APPROVE: 批准 AI 评分结果
    - OVERRIDE: 覆盖 AI 评分，使用人工评分
    - REJECT: 拒绝该提交

    **需求：5.3, 5.4, 5.5**
    """
    try:
        # 验证 submission_id 匹配
        if signal.submission_id != submission_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="路径中的 submission_id 与请求体中的不一致",
            )

        # 获取数据库连接池
        pool = await get_db_pool()

        # 创建仓储实例
        submission_repo = SubmissionRepository(pool)
        grading_result_repo = GradingResultRepository(pool)

        # 查询提交状态
        submission = await submission_repo.get_by_id(submission_id)

        if not submission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"提交 {submission_id} 不存在"
            )

        # 检查是否处于审核状态
        if submission["status"] != "REVIEWING":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"提交 {submission_id} 不在审核状态，当前状态: {submission['status']}",
            )

        # 根据操作类型处理
        if signal.action == "APPROVE":
            # 批准 AI 评分，更新状态为 COMPLETED
            await submission_repo.update_status(submission_id, "COMPLETED")

            return {
                "message": "审核已批准，使用 AI 评分结果",
                "submission_id": submission_id,
                "action": "APPROVE",
            }

        elif signal.action == "OVERRIDE":
            # 覆盖评分
            if signal.override_score is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="OVERRIDE 操作需要提供 override_score",
                )

            # 如果指定了 question_id，只覆盖该题目
            if signal.question_id:
                # 更新指定题目的评分
                await grading_result_repo.update_score(
                    submission_id=submission_id,
                    question_id=signal.question_id,
                    score=signal.override_score,
                    feedback=signal.override_feedback or "人工审核覆盖评分",
                )

                # 重新计算总分
                results = await grading_result_repo.get_by_submission_id(submission_id)
                total_score = sum(float(r["score"]) for r in results)
                max_total_score = sum(float(r["max_score"]) for r in results)

                await submission_repo.update_scores(
                    submission_id=submission_id,
                    total_score=total_score,
                    max_total_score=max_total_score,
                )
            else:
                # 覆盖整份试卷的总分
                await submission_repo.update_scores(
                    submission_id=submission_id,
                    total_score=signal.override_score,
                    max_total_score=submission.get("max_total_score", signal.override_score),
                )

            # 更新状态为 COMPLETED
            await submission_repo.update_status(submission_id, "COMPLETED")

            return {
                "message": "审核已完成，使用人工覆盖评分",
                "submission_id": submission_id,
                "action": "OVERRIDE",
                "override_score": signal.override_score,
            }

        elif signal.action == "REJECT":
            # 拒绝提交
            await submission_repo.update_status(submission_id, "REJECTED")

            return {
                "message": "提交已被拒绝",
                "submission_id": submission_id,
                "action": "REJECT",
                "reason": signal.review_comment,
            }

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"不支持的审核操作: {signal.action}"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"发送审核信号失败: {str(e)}"
        )


@router.get("/{submission_id}/pending", response_model=List[PendingReview])
async def get_pending_reviews(submission_id: str) -> List[PendingReview]:
    """
    获取待审核项

    - **submission_id**: 提交 ID

    返回该提交中所有需要人工审核的题目列表

    **需求：5.3, 5.4, 5.5**
    """
    try:
        # 获取数据库连接池
        pool = await get_db_pool()

        # 创建仓储实例
        submission_repo = SubmissionRepository(pool)
        grading_result_repo = GradingResultRepository(pool)

        # 查询提交状态
        submission = await submission_repo.get_by_id(submission_id)

        if not submission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"提交 {submission_id} 不存在"
            )

        # 查询批改结果
        results = await grading_result_repo.get_by_submission_id(submission_id)

        if not results:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到提交 {submission_id} 的批改结果",
            )

        # 筛选低置信度的题目（置信度 < 0.75）
        pending_reviews = []
        for result in results:
            confidence = float(result["confidence_score"])
            if confidence < 0.75:
                pending_reviews.append(
                    PendingReview(
                        submission_id=submission_id,
                        exam_id=submission["exam_id"],
                        student_id=submission["student_id"],
                        question_id=result["question_id"],
                        ai_score=float(result["score"]),
                        confidence=confidence,
                        reason=f"置信度低于阈值 0.75 (当前: {confidence:.2f})",
                        created_at=result["created_at"].isoformat(),
                    )
                )

        return pending_reviews

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"查询待审核项失败: {str(e)}"
        )
