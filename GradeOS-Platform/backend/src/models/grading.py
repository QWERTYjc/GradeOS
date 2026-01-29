"""批改相关数据模型"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict


class GradingResult(BaseModel):
    """批改结果"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "question_id": "q1",
                "score": 8.5,
                "max_score": 10.0,
                "confidence": 0.92,
                "feedback": "解题思路正确，但计算过程有小错误",
                "visual_annotations": [
                    {
                        "type": "error",
                        "bounding_box": {"ymin": 150, "xmin": 100, "ymax": 180, "xmax": 300},
                        "message": "计算错误",
                    }
                ],
                "agent_trace": {
                    "vision_analysis": "学生使用了正确的公式...",
                    "reasoning_steps": ["步骤1", "步骤2"],
                    "critique_feedback": "需要检查计算精度",
                },
            }
        }
    )

    question_id: str = Field(..., description="题目 ID")
    score: float = Field(..., description="得分", ge=0)
    max_score: float = Field(..., description="满分", ge=0)
    confidence: float = Field(..., description="置信度分数", ge=0.0, le=1.0)
    feedback: str = Field(..., description="学生反馈")
    visual_annotations: List[Dict[str, Any]] = Field(
        default_factory=list, description="视觉标注（用于前端高亮错误）"
    )
    agent_trace: Dict[str, Any] = Field(default_factory=dict, description="智能体推理轨迹")


class RubricMappingItem(BaseModel):
    """评分点映射项"""

    rubric_point: str = Field(..., description="评分点描述")
    evidence: str = Field(..., description="在学生答案中找到的证据")
    score_awarded: float = Field(..., description="该评分点获得的分数", ge=0)
    max_score: float = Field(..., description="该评分点的满分", ge=0)


class ExamPaperResult(BaseModel):
    """整份试卷批改结果"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "submission_id": "sub_001",
                "exam_id": "exam_001",
                "student_id": "student_001",
                "total_score": 85.5,
                "max_total_score": 100.0,
                "question_results": [],
                "overall_feedback": "整体表现良好",
            }
        }
    )

    submission_id: str = Field(..., description="提交 ID")
    exam_id: str = Field(..., description="考试 ID")
    student_id: str = Field(..., description="学生 ID")
    total_score: float = Field(..., description="总分", ge=0)
    max_total_score: float = Field(..., description="满分", ge=0)
    question_results: List[GradingResult] = Field(..., description="各题目批改结果")
    overall_feedback: Optional[str] = Field(None, description="整体反馈")
