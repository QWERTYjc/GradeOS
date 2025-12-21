"""
校准配置数据模型

定义教师/学校的个性化评分配置，包括扣分规则、容差设置和措辞模板。
验证：需求 6.1, 6.2
"""

from typing import Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class ToleranceRule(BaseModel):
    """
    容差规则
    
    定义答案匹配时的容差范围，如数值误差、单位换算、同义表达等。
    """
    rule_type: str = Field(..., description="规则类型：numeric（数值）、unit（单位）、synonym（同义词）")
    tolerance_value: float = Field(..., description="容差值")
    description: str = Field(..., description="规则描述")
    
    @field_validator('rule_type')
    @classmethod
    def validate_rule_type(cls, v: str) -> str:
        """验证规则类型"""
        allowed_types = ['numeric', 'unit', 'synonym']
        if v not in allowed_types:
            raise ValueError(f"规则类型必须是 {allowed_types} 之一")
        return v


class CalibrationProfile(BaseModel):
    """
    校准配置
    
    存储特定教师或学校的评分风格配置。
    验证：需求 6.1, 6.2
    """
    profile_id: str = Field(..., description="配置唯一标识")
    teacher_id: str = Field(..., description="教师ID")
    school_id: Optional[str] = Field(None, description="学校ID（可选）")
    
    # 扣分规则：错误类型 -> 扣分值
    deduction_rules: Dict[str, float] = Field(
        default_factory=dict,
        description="扣分规则，如 {'spelling_error': 0.5, 'logic_error': 2.0}"
    )
    
    # 容差设置
    tolerance_rules: List[ToleranceRule] = Field(
        default_factory=list,
        description="容差规则列表"
    )
    
    # 措辞模板：场景 -> 模板
    feedback_templates: Dict[str, str] = Field(
        default_factory=dict,
        description="评语模板，如 {'partial_correct': '答案部分正确，{reason}'}"
    )
    
    # 严格程度（0.0-1.0）
    strictness_level: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="严格程度，0.0 最宽松，1.0 最严格"
    )
    
    created_at: Optional[datetime] = Field(None, description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")
    
    class Config:
        json_schema_extra = {
            "example": {
                "profile_id": "550e8400-e29b-41d4-a716-446655440000",
                "teacher_id": "660e8400-e29b-41d4-a716-446655440000",
                "school_id": "770e8400-e29b-41d4-a716-446655440000",
                "deduction_rules": {
                    "spelling_error": 0.5,
                    "calculation_error": 1.0,
                    "logic_error": 2.0
                },
                "tolerance_rules": [
                    {
                        "rule_type": "numeric",
                        "tolerance_value": 0.01,
                        "description": "数值误差容差 ±0.01"
                    }
                ],
                "feedback_templates": {
                    "partial_correct": "答案部分正确，{reason}",
                    "incorrect": "答案错误，{reason}"
                },
                "strictness_level": 0.5
            }
        }


class CalibrationProfileCreateRequest(BaseModel):
    """创建校准配置请求"""
    teacher_id: str = Field(..., description="教师ID")
    school_id: Optional[str] = Field(None, description="学校ID（可选）")
    deduction_rules: Optional[Dict[str, float]] = Field(None, description="扣分规则")
    tolerance_rules: Optional[List[ToleranceRule]] = Field(None, description="容差规则")
    feedback_templates: Optional[Dict[str, str]] = Field(None, description="评语模板")
    strictness_level: Optional[float] = Field(None, ge=0.0, le=1.0, description="严格程度")


class CalibrationProfileUpdateRequest(BaseModel):
    """更新校准配置请求"""
    deduction_rules: Optional[Dict[str, float]] = Field(None, description="扣分规则")
    tolerance_rules: Optional[List[ToleranceRule]] = Field(None, description="容差规则")
    feedback_templates: Optional[Dict[str, str]] = Field(None, description="评语模板")
    strictness_level: Optional[float] = Field(None, ge=0.0, le=1.0, description="严格程度")

