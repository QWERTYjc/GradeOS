"""失败模式数据模型

用于表示从改判样本中识别出的高频失败模式。
验证：需求 9.1, 9.2
"""

from typing import List, Optional
from datetime import datetime
from uuid import uuid4
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class PatternType(str, Enum):
    """失败模式类型"""

    EXTRACTION = "extraction"  # 提取阶段失败
    NORMALIZATION = "normalization"  # 规范化阶段失败
    MATCHING = "matching"  # 匹配阶段失败
    SCORING = "scoring"  # 评分阶段失败


class FailurePattern(BaseModel):
    """失败模式模型

    表示从改判样本中识别出的高频失败模式。
    验证：需求 9.1, 9.2
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pattern_id": "pattern_001",
                "pattern_type": "normalization",
                "description": "未能识别单位换算：cm -> m",
                "frequency": 15,
                "sample_log_ids": ["log_001", "log_002", "log_003"],
                "confidence": 0.85,
                "is_fixable": True,
                "created_at": "2025-12-20T14:00:00Z",
            }
        }
    )

    pattern_id: str = Field(
        default_factory=lambda: f"pattern_{uuid4().hex[:8]}", description="失败模式唯一标识"
    )
    pattern_type: PatternType = Field(..., description="失败模式类型")
    description: str = Field(..., description="失败模式描述", min_length=1)
    frequency: int = Field(..., description="出现频率", ge=1)
    sample_log_ids: List[str] = Field(
        default_factory=list, description="样本日志ID列表（用于追溯）"
    )
    confidence: float = Field(default=1.0, description="模式识别置信度（0.0-1.0）", ge=0.0, le=1.0)
    is_fixable: bool = Field(default=False, description="是否可通过规则修复")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")

    # 可选的详细信息
    error_signature: Optional[str] = Field(None, description="错误特征签名（用于模式匹配）")
    affected_question_types: Optional[List[str]] = Field(
        default_factory=list, description="受影响的题型列表"
    )
    suggested_fix: Optional[str] = Field(None, description="建议的修复方案")


class FailurePatternSummary(BaseModel):
    """失败模式汇总

    用于展示规则挖掘的整体结果。
    """

    total_overrides: int = Field(..., description="总改判数量")
    total_patterns: int = Field(..., description="识别出的模式数量")
    fixable_patterns: int = Field(..., description="可修复的模式数量")
    patterns: List[FailurePattern] = Field(default_factory=list, description="失败模式列表")
    analysis_time: datetime = Field(default_factory=datetime.utcnow, description="分析时间")
