"""判例记忆相关数据模型"""

from typing import List, Optional
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


class Exemplar(BaseModel):
    """判例模型

    存储老师确认的正确批改示例，用于 few-shot 学习。
    验证：需求 4.1, 4.2
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "exemplar_id": "550e8400-e29b-41d4-a716-446655440000",
                "question_type": "objective",
                "question_image_hash": "abc123def456",
                "student_answer_text": "答案：C",
                "score": 5.0,
                "max_score": 5.0,
                "teacher_feedback": "答案正确",
                "teacher_id": "teacher_001",
                "confirmed_at": "2025-12-20T08:00:00Z",
                "usage_count": 10,
                "embedding": [0.1, 0.2, 0.3],
            }
        }
    )

    exemplar_id: str = Field(..., description="判例唯一标识")
    question_type: str = Field(..., description="题目类型（objective/stepwise/essay）")
    question_image_hash: str = Field(..., description="题目图片哈希值")
    student_answer_text: str = Field(..., description="学生答案文本")
    score: float = Field(..., description="得分", ge=0)
    max_score: float = Field(..., description="满分", ge=0)
    teacher_feedback: str = Field(..., description="教师评语")
    teacher_id: str = Field(..., description="确认教师ID")
    confirmed_at: datetime = Field(..., description="确认时间")
    usage_count: int = Field(default=0, description="使用次数", ge=0)
    embedding: Optional[List[float]] = Field(None, description="向量嵌入")


class ExemplarCreateRequest(BaseModel):
    """创建判例请求"""

    question_type: str = Field(..., description="题目类型")
    question_image_hash: str = Field(..., description="题目图片哈希值")
    student_answer_text: str = Field(..., description="学生答案文本")
    score: float = Field(..., description="得分", ge=0)
    max_score: float = Field(..., description="满分", ge=0)
    teacher_feedback: str = Field(..., description="教师评语")
    teacher_id: str = Field(..., description="确认教师ID")


class ExemplarSearchRequest(BaseModel):
    """判例检索请求"""

    question_image_hash: str = Field(..., description="题目图片哈希值")
    question_type: str = Field(..., description="题目类型")
    top_k: int = Field(default=5, description="返回数量", ge=1, le=10)
    min_similarity: float = Field(default=0.7, description="最小相似度阈值", ge=0.0, le=1.0)


class ExemplarSearchResult(BaseModel):
    """判例检索结果"""

    exemplars: List[Exemplar] = Field(..., description="检索到的判例列表")
    total_count: int = Field(..., description="总数量", ge=0)
