"""批改日志数据模型

用于记录批改过程的完整上下文，支持后续分析和规则升级。
验证：需求 8.1, 8.2, 8.3, 8.4
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, ConfigDict
from decimal import Decimal


class GradingLog(BaseModel):
    """批改日志模型
    
    记录批改过程各阶段的详细信息：
    - 提取阶段：extracted_answer, extraction_confidence, evidence_snippets
    - 规范化阶段：normalized_answer, normalization_rules_applied
    - 匹配阶段：match_result, match_failure_reason
    - 评分阶段：score, max_score, confidence, reasoning_trace
    - 改判信息：was_overridden, override_score, override_reason, override_teacher_id
    
    验证：需求 8.1, 8.2, 8.3
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "log_id": "550e8400-e29b-41d4-a716-446655440000",
                "submission_id": "660e8400-e29b-41d4-a716-446655440000",
                "question_id": "q1",
                "extracted_answer": "x = 5",
                "extraction_confidence": 0.95,
                "evidence_snippets": ["在第3行找到答案", "计算过程清晰"],
                "normalized_answer": "x=5",
                "normalization_rules_applied": ["remove_spaces", "lowercase"],
                "match_result": True,
                "match_failure_reason": None,
                "score": 8.5,
                "max_score": 10.0,
                "confidence": 0.92,
                "reasoning_trace": ["步骤1：识别公式", "步骤2：验证计算"],
                "was_overridden": False,
                "override_score": None,
                "override_reason": None,
                "override_teacher_id": None,
                "override_at": None,
                "created_at": "2025-12-20T14:00:00Z"
            }
        }
    )
    
    # 基本信息
    log_id: str = Field(default_factory=lambda: str(uuid4()), description="日志唯一标识")
    submission_id: str = Field(..., description="提交ID")
    question_id: str = Field(..., description="题目ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="日志时间戳")
    
    # 提取阶段
    extracted_answer: Optional[str] = Field(None, description="提取的答案文本")
    extraction_confidence: Optional[float] = Field(None, description="提取置信度（0.0-1.0）", ge=0.0, le=1.0)
    evidence_snippets: Optional[List[str]] = Field(default_factory=list, description="证据片段列表")
    
    # 规范化阶段
    normalized_answer: Optional[str] = Field(None, description="规范化后的答案")
    normalization_rules_applied: Optional[List[str]] = Field(default_factory=list, description="应用的规范化规则列表")
    
    # 匹配阶段
    match_result: Optional[bool] = Field(None, description="匹配结果（True/False）")
    match_failure_reason: Optional[str] = Field(None, description="匹配失败原因")
    
    # 评分阶段
    score: Optional[float] = Field(None, description="评分结果", ge=0)
    max_score: Optional[float] = Field(None, description="满分值", ge=0)
    confidence: Optional[float] = Field(None, description="评分置信度（0.0-1.0）", ge=0.0, le=1.0)
    reasoning_trace: Optional[List[str]] = Field(default_factory=list, description="推理过程追踪")
    
    # 改判信息
    was_overridden: bool = Field(default=False, description="是否被改判")
    override_score: Optional[float] = Field(None, description="改判后的分数", ge=0)
    override_reason: Optional[str] = Field(None, description="改判原因")
    override_teacher_id: Optional[str] = Field(None, description="改判教师ID")
    override_at: Optional[datetime] = Field(None, description="改判时间")
    
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")


class GradingLogCreate(BaseModel):
    """创建批改日志的请求模型"""
    submission_id: str
    question_id: str
    extracted_answer: Optional[str] = None
    extraction_confidence: Optional[float] = None
    evidence_snippets: Optional[List[str]] = None
    normalized_answer: Optional[str] = None
    normalization_rules_applied: Optional[List[str]] = None
    match_result: Optional[bool] = None
    match_failure_reason: Optional[str] = None
    score: Optional[float] = None
    max_score: Optional[float] = None
    confidence: Optional[float] = None
    reasoning_trace: Optional[List[str]] = None


class GradingLogOverride(BaseModel):
    """改判信息模型
    
    验证：需求 8.4
    """
    override_score: float = Field(..., description="改判后的分数", ge=0)
    override_reason: str = Field(..., description="改判原因", min_length=1)
    override_teacher_id: str = Field(..., description="改判教师ID")
