"""辅助批改数据模型

定义辅助批改系统使用的 Pydantic 模型。
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
from enum import Enum


# ==================== 枚举类型 ====================


class ErrorType(str, Enum):
    """错误类型"""

    CALCULATION = "calculation"
    LOGIC = "logic"
    CONCEPT = "concept"
    WRITING = "writing"


class Severity(str, Enum):
    """严重程度"""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SuggestionType(str, Enum):
    """建议类型"""

    CORRECTION = "correction"
    IMPROVEMENT = "improvement"
    ALTERNATIVE = "alternative"


class DifficultyLevel(str, Enum):
    """难度等级"""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


# ==================== 理解分析模型 ====================


class KnowledgePoint(BaseModel):
    """知识点"""

    name: str = Field(..., description="知识点名称")
    category: str = Field(..., description="分类")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="置信度")

    model_config = {
        "json_schema_extra": {
            "example": {"name": "极限的定义", "category": "微积分", "confidence": 0.95}
        }
    }


class UnderstandingResult(BaseModel):
    """理解分析结果"""

    knowledge_points: List[KnowledgePoint] = Field(default_factory=list)
    question_types: List[str] = Field(default_factory=list)
    solution_approaches: List[str] = Field(default_factory=list)
    difficulty_level: DifficultyLevel = Field(default=DifficultyLevel.MEDIUM)
    estimated_time_minutes: Optional[int] = None
    logic_chain: List[str] = Field(default_factory=list)


# ==================== 错误模型 ====================


class ErrorLocation(BaseModel):
    """错误位置"""

    page: int = Field(..., description="页码")
    region: Optional[str] = Field(None, description="区域描述")
    step_number: Optional[int] = Field(None, description="步骤号")
    coordinates: Optional[Dict[str, float]] = Field(None, description="坐标")


class ErrorRecord(BaseModel):
    """错误记录"""

    error_id: str
    error_type: ErrorType
    description: str
    severity: Severity
    location: ErrorLocation
    affected_steps: List[str] = Field(default_factory=list)
    correct_approach: Optional[str] = None
    context: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "error_id": "err_001",
                "error_type": "calculation",
                "description": "分母应该是 (x-1)² 而不是 (x-1)",
                "severity": "high",
                "location": {"page": 0, "region": "middle", "step_number": 3},
                "affected_steps": ["步骤3", "步骤4"],
                "correct_approach": "应用求导法则时，分母应该是 (x-1)²",
            }
        }
    }


# ==================== 建议模型 ====================


class Suggestion(BaseModel):
    """改进建议"""

    suggestion_id: str
    related_error_id: Optional[str] = None
    suggestion_type: SuggestionType
    description: str
    example: Optional[str] = None
    priority: Severity
    resources: List[str] = Field(default_factory=list)
    expected_improvement: Optional[str] = None


# ==================== 深度分析模型 ====================


class LearningRecommendation(BaseModel):
    """学习建议"""

    category: str = Field(..., description="建议类别")
    description: str = Field(..., description="建议描述")
    action_items: List[str] = Field(default_factory=list, description="行动项")


class DeepAnalysisResult(BaseModel):
    """深度分析结果"""

    understanding_score: float = Field(..., ge=0.0, le=100.0)
    understanding_score_reasoning: str
    logic_coherence: float = Field(..., ge=0.0, le=100.0)
    logic_coherence_reasoning: str
    completeness: float = Field(..., ge=0.0, le=100.0)
    completeness_reasoning: str
    overall_score: float = Field(..., ge=0.0, le=100.0)
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    learning_recommendations: List[LearningRecommendation] = Field(default_factory=list)
    growth_potential: Literal["high", "medium", "low"] = "medium"
    next_steps: List[str] = Field(default_factory=list)


# ==================== 分析报告模型 ====================


class ReportMetadata(BaseModel):
    """报告元数据"""

    analysis_id: str
    submission_id: Optional[str] = None
    student_id: Optional[str] = None
    subject: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    version: str = "1.0"


class ReportSummary(BaseModel):
    """报告摘要"""

    overall_score: float
    total_errors: int
    high_severity_errors: int
    total_suggestions: int
    estimated_completion_time_minutes: int
    actual_difficulty: DifficultyLevel


class ActionPlan(BaseModel):
    """行动计划"""

    immediate_actions: List[str] = Field(default_factory=list)
    short_term_goals: List[str] = Field(default_factory=list)
    long_term_goals: List[str] = Field(default_factory=list)


class AnalysisReport(BaseModel):
    """分析报告"""

    metadata: ReportMetadata
    summary: ReportSummary
    understanding: UnderstandingResult
    errors: List[ErrorRecord]
    suggestions: List[Suggestion]
    deep_analysis: DeepAnalysisResult
    action_plan: Optional[ActionPlan] = None
    visualizations: Optional[Dict[str, str]] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "metadata": {
                    "analysis_id": "ana_abc123",
                    "student_id": "stu_67890",
                    "subject": "mathematics",
                    "created_at": "2026-01-28T10:00:00Z",
                    "version": "1.0",
                },
                "summary": {
                    "overall_score": 75.0,
                    "total_errors": 3,
                    "high_severity_errors": 1,
                    "total_suggestions": 5,
                    "estimated_completion_time_minutes": 20,
                    "actual_difficulty": "medium",
                },
            }
        }
    }


# ==================== API 请求/响应模型 ====================


class AnalyzeRequest(BaseModel):
    """分析请求"""

    images: List[str] = Field(..., description="作业图片 Base64 列表")
    submission_id: Optional[str] = Field(None, description="关联提交 ID")
    student_id: Optional[str] = Field(None, description="学生 ID")
    subject: Optional[str] = Field(None, description="科目")
    context_info: Optional[Dict[str, Any]] = Field(None, description="上下文信息")

    @field_validator("images")
    @classmethod
    def validate_images(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("至少需要一张图片")
        if len(v) > 50:
            raise ValueError("图片数量不能超过 50 张")
        return v


class AnalyzeResponse(BaseModel):
    """分析响应"""

    analysis_id: str
    status: str
    message: str
    estimated_time_seconds: Optional[int] = None


class ReportResponse(BaseModel):
    """报告响应"""

    analysis_id: str
    status: str
    report: Optional[AnalysisReport] = None
    error_message: Optional[str] = None
    progress: Optional[Dict[str, Any]] = None


class BatchAnalyzeRequest(BaseModel):
    """批量分析请求"""

    analyses: List[AnalyzeRequest] = Field(..., description="分析任务列表")

    @field_validator("analyses")
    @classmethod
    def validate_analyses(cls, v: List[AnalyzeRequest]) -> List[AnalyzeRequest]:
        if not v:
            raise ValueError("至少需要一个分析任务")
        if len(v) > 100:
            raise ValueError("批量任务不能超过 100 个")
        return v


class BatchAnalyzeResponse(BaseModel):
    """批量分析响应"""

    batch_id: str
    total_count: int
    analysis_ids: List[str]
    message: str
