"""提示词相关数据模型"""

from typing import Dict, List
from enum import Enum
from pydantic import BaseModel, Field


class PromptSection(str, Enum):
    """提示词区段类型"""
    SYSTEM = "system"
    RUBRIC = "rubric"
    EXEMPLARS = "exemplars"
    ERROR_GUIDANCE = "error_guidance"
    DETAILED_REASONING = "detailed_reasoning"
    CALIBRATION = "calibration"


class AssembledPrompt(BaseModel):
    """拼装后的提示词
    
    验证：需求 5.4, 5.5
    """
    sections: Dict[PromptSection, str] = Field(
        ...,
        description="各区段内容"
    )
    total_tokens: int = Field(
        ...,
        description="总 token 数",
        ge=0
    )
    truncated_sections: List[PromptSection] = Field(
        default_factory=list,
        description="被截断的区段列表"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "sections": {
                    "system": "你是一个批改助手...",
                    "rubric": "## 评分细则\n...",
                    "exemplars": "## 参考判例\n..."
                },
                "total_tokens": 1500,
                "truncated_sections": []
            }
        }
