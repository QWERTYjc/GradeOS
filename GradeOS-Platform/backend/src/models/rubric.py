"""评分细则相关数据模型"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict


class ScoringPoint(BaseModel):
    """评分点"""

    point_id: Optional[str] = Field(None, description="评分点ID")
    description: str = Field(..., description="评分点描述")
    score: float = Field(..., description="该评分点的分值", ge=0)
    required: bool = Field(True, description="是否为必需评分点")


class Rubric(BaseModel):
    """评分细则"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "exam_id": "exam_001",
                "question_id": "q1",
                "rubric_text": "1. 正确列出公式（3分）\n2. 计算过程正确（5分）\n3. 结果正确（2分）",
                "max_score": 10.0,
                "scoring_points": [
                    {"description": "正确列出公式", "score": 3.0, "required": True},
                    {"description": "计算过程正确", "score": 5.0, "required": True},
                    {"description": "结果正确", "score": 2.0, "required": True},
                ],
                "standard_answer": "使用牛顿第二定律 F=ma...",
            }
        }
    )

    rubric_id: Optional[str] = Field(None, description="评分细则 ID")
    exam_id: str = Field(..., description="考试 ID")
    question_id: str = Field(..., description="题目 ID")
    rubric_text: str = Field(..., description="评分细则文本")
    max_score: float = Field(..., description="满分", ge=0)
    scoring_points: List[ScoringPoint] = Field(..., description="评分点列表")
    standard_answer: Optional[str] = Field(None, description="标准答案")
    created_at: Optional[str] = Field(None, description="创建时间")
    updated_at: Optional[str] = Field(None, description="更新时间")


class RubricCreateRequest(BaseModel):
    """创建评分细则请求"""

    exam_id: str = Field(..., description="考试 ID")
    question_id: str = Field(..., description="题目 ID")
    rubric_text: str = Field(..., description="评分细则文本")
    max_score: float = Field(..., description="满分", ge=0)
    scoring_points: List[ScoringPoint] = Field(..., description="评分点列表")
    standard_answer: Optional[str] = Field(None, description="标准答案")


class RubricUpdateRequest(BaseModel):
    """更新评分细则请求"""

    rubric_text: Optional[str] = Field(None, description="评分细则文本")
    max_score: Optional[float] = Field(None, description="满分", ge=0)
    scoring_points: Optional[List[ScoringPoint]] = Field(None, description="评分点列表")
    standard_answer: Optional[str] = Field(None, description="标准答案")
