"""规则补丁数据模型

用于表示从失败模式生成的规则补丁。
验证：需求 9.2, 9.3, 9.4
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from uuid import uuid4
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class PatchType(str, Enum):
    """补丁类型"""
    RULE = "rule"  # 规则补丁
    PROMPT = "prompt"  # 提示词补丁
    EXEMPLAR = "exemplar"  # 示例补丁


class PatchStatus(str, Enum):
    """补丁状态"""
    CANDIDATE = "candidate"  # 候选状态
    TESTING = "testing"  # 测试中
    DEPLOYED = "deployed"  # 已部署
    ROLLED_BACK = "rolled_back"  # 已回滚


class RulePatch(BaseModel):
    """规则补丁模型
    
    表示从失败模式生成的规则补丁。
    验证：需求 9.2
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "patch_id": "patch_001",
                "patch_type": "rule",
                "version": "v1.0.0",
                "description": "添加单位换算规则：cm -> m",
                "content": {
                    "rule_type": "unit_conversion",
                    "from_unit": "cm",
                    "to_unit": "m",
                    "conversion_factor": 0.01
                },
                "source_pattern_id": "pattern_001",
                "status": "candidate",
                "created_at": "2025-12-20T14:00:00Z"
            }
        }
    )
    
    patch_id: str = Field(
        default_factory=lambda: f"patch_{uuid4().hex[:8]}",
        description="补丁唯一标识"
    )
    patch_type: PatchType = Field(..., description="补丁类型")
    version: str = Field(..., description="版本号", min_length=1)
    description: str = Field(..., description="补丁描述", min_length=1)
    content: Dict[str, Any] = Field(..., description="补丁内容（具体格式取决于补丁类型）")
    source_pattern_id: str = Field(..., description="来源失败模式ID")
    status: PatchStatus = Field(default=PatchStatus.CANDIDATE, description="补丁状态")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    
    # 部署信息
    deployed_at: Optional[datetime] = Field(None, description="部署时间")
    deployment_scope: Optional[str] = Field(None, description="部署范围（canary/full）")
    rolled_back_at: Optional[datetime] = Field(None, description="回滚时间")
    
    # 测试结果
    regression_result: Optional[Dict[str, Any]] = Field(None, description="回归测试结果")
    
    # 依赖关系
    dependencies: List[str] = Field(default_factory=list, description="依赖的其他补丁版本")


class RegressionResult(BaseModel):
    """回归测试结果模型
    
    记录补丁在评测集上的测试结果。
    验证：需求 9.3, 9.4
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "patch_id": "patch_001",
                "passed": True,
                "old_error_rate": 0.15,
                "new_error_rate": 0.08,
                "old_miss_rate": 0.10,
                "new_miss_rate": 0.05,
                "old_review_rate": 0.20,
                "new_review_rate": 0.12,
                "total_samples": 100,
                "improved_samples": 25,
                "degraded_samples": 3,
                "eval_set_id": "eval_001",
                "tested_at": "2025-12-20T14:00:00Z"
            }
        }
    )
    
    patch_id: str = Field(..., description="补丁ID")
    passed: bool = Field(..., description="是否通过测试")
    
    # 指标对比
    old_error_rate: float = Field(..., description="旧版本误判率", ge=0.0, le=1.0)
    new_error_rate: float = Field(..., description="新版本误判率", ge=0.0, le=1.0)
    old_miss_rate: float = Field(..., description="旧版本漏判率", ge=0.0, le=1.0)
    new_miss_rate: float = Field(..., description="新版本漏判率", ge=0.0, le=1.0)
    old_review_rate: float = Field(..., description="旧版本复核率", ge=0.0, le=1.0)
    new_review_rate: float = Field(..., description="新版本复核率", ge=0.0, le=1.0)
    
    # 测试详情
    total_samples: int = Field(..., description="总样本数", ge=0)
    improved_samples: int = Field(..., description="改进的样本数", ge=0)
    degraded_samples: int = Field(..., description="退化的样本数", ge=0)
    
    # 测试元信息
    eval_set_id: str = Field(..., description="评测集ID")
    tested_at: datetime = Field(default_factory=datetime.utcnow, description="测试时间")
    
    # 可选的详细信息
    sample_details: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="样本详情列表（用于调试）"
    )
    error_analysis: Optional[str] = Field(
        None,
        description="错误分析报告"
    )

