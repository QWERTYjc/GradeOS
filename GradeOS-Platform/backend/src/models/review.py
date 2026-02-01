"""人工审核相关数据模型"""

from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from .enums import ReviewAction


class ReviewSignal(BaseModel):
    """审核信号"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "submission_id": "sub_001",
                "question_id": "q1",
                "action": "OVERRIDE",
                "override_score": 9.0,
                "override_feedback": "经人工审核，学生答案基本正确",
                "review_comment": "AI 评分偏低",
                "reviewer_id": "teacher_001",
            }
        }
    )

    submission_id: str = Field(..., description="提交 ID")
    question_id: Optional[str] = Field(None, description="题目 ID（可选，为空表示整份试卷）")
    action: ReviewAction = Field(..., description="审核操作")
    override_score: Optional[float] = Field(None, description="覆盖分数（仅 OVERRIDE 操作需要）")
    override_feedback: Optional[str] = Field(None, description="覆盖反馈（仅 OVERRIDE 操作需要）")
    review_comment: Optional[str] = Field(None, description="审核备注")
    reviewer_id: str = Field(..., description="审核人 ID")


class PendingReview(BaseModel):
    """待审核项"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "submission_id": "sub_001",
                "exam_id": "exam_001",
                "student_id": "student_001",
                "question_id": "q1",
                "ai_score": 7.5,
                "confidence": 0.68,
                "reason": "置信度低于阈值 0.75",
                "created_at": "2024-01-01T12:00:00Z",
            }
        }
    )

    submission_id: str = Field(..., description="提交 ID")
    exam_id: str = Field(..., description="考试 ID")
    student_id: str = Field(..., description="学生 ID")
    question_id: str = Field(..., description="题目 ID")
    ai_score: float = Field(..., description="AI 评分")
    confidence: float = Field(..., description="置信度")
    reason: str = Field(..., description="需要审核的原因")
    created_at: str = Field(..., description="创建时间")
