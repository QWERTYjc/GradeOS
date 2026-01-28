# 辅助批改系统 - 实现计划

**版本**: 1.0  
**日期**: 2026-01-28  
**预计工期**: 8-10 天

## 📋 实现阶段

```
阶段 1: 基础架构 (2 天)
    ├── 状态定义
    ├── 数据模型
    ├── 数据库表
    └── 工作流框架

阶段 2: 核心服务 (3 天)
    ├── 分析引擎
    ├── 错误检测器
    ├── 建议生成器
    └── 报告构建器

阶段 3: API 实现 (2 天)
    ├── REST API
    ├── WebSocket
    └── 进度推送

阶段 4: 测试与优化 (2-3 天)
    ├── 单元测试
    ├── 集成测试
    ├── 性能优化
    └── 文档完善
```

---

## 🎯 阶段 1: 基础架构 (Day 1-2)

### Task 1.1: 扩展状态定义

**文件**: `src/graphs/state.py`

**任务**: 在现有文件中添加 `AssistantGradingState`

```python
# 在 src/graphs/state.py 末尾添加

class AssistantGradingState(TypedDict, total=False):
    """辅助批改状态定义
    
    用于深度分析学生作业，不依赖评分标准。
    """
    
    # ===== 基础信息 =====
    analysis_id: str                          # 分析任务 ID
    submission_id: Optional[str]              # 关联的提交 ID
    student_id: Optional[str]                 # 学生 ID
    subject: Optional[str]                    # 科目
    
    # ===== 输入数据 =====
    inputs: Dict[str, Any]                    # 输入数据
    image_paths: List[str]                    # 作业图片路径
    image_base64_list: List[str]              # 图片 Base64 列表
    context_info: Optional[Dict[str, Any]]    # 上下文信息
    
    # ===== 理解分析结果 =====
    understanding: Dict[str, Any]
    
    # ===== 错误识别结果 =====
    errors: List[Dict[str, Any]]
    
    # ===== 改进建议结果 =====
    suggestions: List[Dict[str, Any]]
    
    # ===== 深度分析结果 =====
    deep_analysis: Dict[str, Any]
    
    # ===== 最终报告 =====
    report: Dict[str, Any]
    report_url: Optional[str]
    
    # ===== 进度信息 =====
    progress: Dict[str, Any]
    current_stage: str
    percentage: float
    
    # ===== 错误处理 =====
    processing_errors: List[Dict[str, Any]]
    retry_count: int
    
    # ===== 时间戳 =====
    timestamps: Dict[str, str]


def create_initial_assistant_state(
    analysis_id: str,
    images: List[str],
    submission_id: Optional[str] = None,
    student_id: Optional[str] = None,
    subject: Optional[str] = None,
    context_info: Optional[Dict[str, Any]] = None,
) -> AssistantGradingState:
    """创建初始辅助分析状态
    
    Args:
        analysis_id: 分析 ID
        images: 图片 Base64 列表
        submission_id: 提交 ID（可选）
        student_id: 学生 ID（可选）
        subject: 科目（可选）
        context_info: 上下文信息（可选）
        
    Returns:
        初始化的 AssistantGradingState
    """
    return AssistantGradingState(
        analysis_id=analysis_id,
        submission_id=submission_id,
        student_id=student_id,
        subject=subject,
        inputs={
            "images": images,
            "context_info": context_info,
        },
        image_base64_list=images,
        context_info=context_info or {},
        understanding={},
        errors=[],
        suggestions=[],
        deep_analysis={},
        report={},
        report_url=None,
        progress={},
        current_stage="initialized",
        percentage=0.0,
        processing_errors=[],
        retry_count=0,
        timestamps={
            "created_at": datetime.now().isoformat()
        },
    )
```

**验收标准**:
- [x] 类型定义完整
- [x] 字段注释清晰
- [x] 初始化函数正确

---

### Task 1.2: 创建数据模型

**文件**: `src/models/assistant_models.py` (新建)

```python
"""辅助批改数据模型

定义辅助批改系统使用的 Pydantic 模型。
"""

from pydantic import BaseModel, Field, validator
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
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "极限的定义",
                "category": "微积分",
                "confidence": 0.95
            }
        }


class UnderstandingResult(BaseModel):
    """理解分析结果"""
    knowledge_points: List[KnowledgePoint] = Field(default_factory=list)
    question_types: List[str] = Field(default_factory=list)
    solution_approaches: List[str] = Field(default_factory=list)
    difficulty_level: DifficultyLevel = Field(DifficultyLevel.MEDIUM)
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
    
    class Config:
        json_schema_extra = {
            "example": {
                "error_id": "err_001",
                "error_type": "calculation",
                "description": "分母应该是 (x-1)² 而不是 (x-1)",
                "severity": "high",
                "location": {"page": 0, "region": "middle", "step_number": 3},
                "affected_steps": ["步骤3", "步骤4"],
                "correct_approach": "应用求导法则时，分母应该是 (x-1)²"
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
    
    class Config:
        json_schema_extra = {
            "example": {
                "metadata": {
                    "analysis_id": "ana_abc123",
                    "student_id": "stu_67890",
                    "subject": "mathematics",
                    "created_at": "2026-01-28T10:00:00Z",
                    "version": "1.0"
                },
                "summary": {
                    "overall_score": 75.0,
                    "total_errors": 3,
                    "high_severity_errors": 1,
                    "total_suggestions": 5,
                    "estimated_completion_time_minutes": 20,
                    "actual_difficulty": "medium"
                }
            }
        }
```

**验收标准**:
- [x] 所有模型定义完整
- [x] 字段验证正确
- [x] 示例数据完整

---

### Task 1.3: 创建数据库表

**文件**: `src/db/assistant_tables.py` (新建)

```python
"""辅助批改数据库表定义"""

from sqlalchemy import Column, String, Integer, Float, JSON, DateTime, Text, Enum, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()


class AnalysisStatus(enum.Enum):
    """分析状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AssistantAnalysisReport(Base):
    """辅助分析报告表"""
    __tablename__ = "assistant_analysis_reports"
    
    # 主键
    analysis_id = Column(String(64), primary_key=True, comment="分析 ID")
    
    # 关联信息
    submission_id = Column(String(64), nullable=True, index=True, comment="关联提交 ID")
    student_id = Column(String(64), nullable=True, index=True, comment="学生 ID")
    subject = Column(String(64), nullable=True, index=True, comment="科目")
    
    # 分析结果（JSON 格式）
    understanding = Column(JSON, nullable=True, comment="理解分析结果")
    errors = Column(JSON, nullable=True, comment="错误列表")
    suggestions = Column(JSON, nullable=True, comment="建议列表")
    deep_analysis = Column(JSON, nullable=True, comment="深度分析结果")
    report = Column(JSON, nullable=True, comment="完整报告")
    
    # 报告信息
    report_url = Column(String(512), nullable=True, comment="报告存储 URL")
    status = Column(
        Enum(AnalysisStatus),
        default=AnalysisStatus.PENDING,
        nullable=False,
        index=True,
        comment="分析状态"
    )
    
    # 进度信息
    current_stage = Column(String(64), nullable=True, comment="当前阶段")
    percentage = Column(Float, default=0.0, comment="完成百分比")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, comment="创建时间")
    started_at = Column(DateTime, nullable=True, comment="开始时间")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")
    
    # 错误信息
    error_message = Column(Text, nullable=True, comment="错误信息")
    retry_count = Column(Integer, default=0, comment="重试次数")
    
    # 索引
    __table_args__ = (
        {"comment": "辅助批改分析报告表"}
    )


class AssistantErrorRecord(Base):
    """错误记录表（细粒度存储）"""
    __tablename__ = "assistant_error_records"
    
    # 主键
    error_id = Column(String(64), primary_key=True, comment="错误 ID")
    
    # 关联
    analysis_id = Column(
        String(64),
        ForeignKey("assistant_analysis_reports.analysis_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="关联分析 ID"
    )
    
    # 错误信息
    error_type = Column(
        Enum("calculation", "logic", "concept", "writing", name="error_type"),
        nullable=False,
        comment="错误类型"
    )
    description = Column(Text, nullable=False, comment="错误描述")
    severity = Column(
        Enum("high", "medium", "low", name="error_severity"),
        nullable=False,
        comment="严重程度"
    )
    
    # 位置信息（JSON 格式）
    location = Column(JSON, nullable=True, comment="错误位置")
    
    # 关联信息
    affected_steps = Column(JSON, nullable=True, comment="影响的步骤")
    correct_approach = Column(Text, nullable=True, comment="正确的做法")
    context = Column(Text, nullable=True, comment="上下文")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, comment="创建时间")
    
    __table_args__ = (
        {"comment": "辅助批改错误记录表"}
    )


class AssistantSuggestion(Base):
    """建议记录表（细粒度存储）"""
    __tablename__ = "assistant_suggestions"
    
    # 主键
    suggestion_id = Column(String(64), primary_key=True, comment="建议 ID")
    
    # 关联
    analysis_id = Column(
        String(64),
        ForeignKey("assistant_analysis_reports.analysis_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="关联分析 ID"
    )
    related_error_id = Column(String(64), nullable=True, comment="关联错误 ID")
    
    # 建议信息
    suggestion_type = Column(
        Enum("correction", "improvement", "alternative", name="suggestion_type"),
        nullable=False,
        comment="建议类型"
    )
    description = Column(Text, nullable=False, comment="建议描述")
    example = Column(Text, nullable=True, comment="示例")
    priority = Column(
        Enum("high", "medium", "low", name="suggestion_priority"),
        nullable=False,
        comment="优先级"
    )
    
    # 扩展信息
    resources = Column(JSON, nullable=True, comment="学习资源列表")
    expected_improvement = Column(Text, nullable=True, comment="预期改进效果")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, comment="创建时间")
    
    __table_args__ = (
        {"comment": "辅助批改建议记录表"}
    )


# 数据库迁移脚本（Alembic）
MIGRATION_SQL = """
-- 创建辅助分析报告表
CREATE TABLE IF NOT EXISTS assistant_analysis_reports (
    analysis_id VARCHAR(64) PRIMARY KEY,
    submission_id VARCHAR(64),
    student_id VARCHAR(64),
    subject VARCHAR(64),
    understanding JSONB,
    errors JSONB,
    suggestions JSONB,
    deep_analysis JSONB,
    report JSONB,
    report_url VARCHAR(512),
    status VARCHAR(20) DEFAULT 'pending',
    current_stage VARCHAR(64),
    percentage FLOAT DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_assistant_reports_submission ON assistant_analysis_reports(submission_id);
CREATE INDEX IF NOT EXISTS idx_assistant_reports_student ON assistant_analysis_reports(student_id);
CREATE INDEX IF NOT EXISTS idx_assistant_reports_subject ON assistant_analysis_reports(subject);
CREATE INDEX IF NOT EXISTS idx_assistant_reports_status ON assistant_analysis_reports(status);

-- 创建错误记录表
CREATE TABLE IF NOT EXISTS assistant_error_records (
    error_id VARCHAR(64) PRIMARY KEY,
    analysis_id VARCHAR(64) NOT NULL REFERENCES assistant_analysis_reports(analysis_id) ON DELETE CASCADE,
    error_type VARCHAR(20) NOT NULL,
    description TEXT NOT NULL,
    severity VARCHAR(10) NOT NULL,
    location JSONB,
    affected_steps JSONB,
    correct_approach TEXT,
    context TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_assistant_errors_analysis ON assistant_error_records(analysis_id);

-- 创建建议记录表
CREATE TABLE IF NOT EXISTS assistant_suggestions (
    suggestion_id VARCHAR(64) PRIMARY KEY,
    analysis_id VARCHAR(64) NOT NULL REFERENCES assistant_analysis_reports(analysis_id) ON DELETE CASCADE,
    related_error_id VARCHAR(64),
    suggestion_type VARCHAR(20) NOT NULL,
    description TEXT NOT NULL,
    example TEXT,
    priority VARCHAR(10) NOT NULL,
    resources JSONB,
    expected_improvement TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_assistant_suggestions_analysis ON assistant_suggestions(analysis_id);
"""
```

**验收标准**:
- [x] 表结构完整
- [x] 索引合理
- [x] 外键约束正确
- [x] 迁移脚本可用

---

### Task 1.4: 创建工作流框架

**文件**: `src/graphs/assistant_grading.py` (新建)

```python
"""辅助批改 LangGraph 工作流

提供深度分析和智能纠错功能，不依赖评分标准。
"""

import logging
import os
from typing import Dict, Any
from datetime import datetime

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from src.graphs.state import AssistantGradingState


logger = logging.getLogger(__name__)


# ==================== 节点实现（占位符）====================

async def understand_assignment_node(state: AssistantGradingState) -> Dict[str, Any]:
    """
    理解作业内容节点
    
    TODO: 实现完整逻辑
    """
    analysis_id = state["analysis_id"]
    logger.info(f"[AssistantGrading] 理解分析: analysis_id={analysis_id}")
    
    # 占位实现
    return {
        "understanding": {},
        "current_stage": "understood",
        "percentage": 25.0,
    }


async def identify_errors_node(state: AssistantGradingState) -> Dict[str, Any]:
    """
    错误识别节点
    
    TODO: 实现完整逻辑
    """
    analysis_id = state["analysis_id"]
    logger.info(f"[AssistantGrading] 错误识别: analysis_id={analysis_id}")
    
    # 占位实现
    return {
        "errors": [],
        "current_stage": "errors_identified",
        "percentage": 50.0,
    }


async def generate_suggestions_node(state: AssistantGradingState) -> Dict[str, Any]:
    """
    建议生成节点
    
    TODO: 实现完整逻辑
    """
    analysis_id = state["analysis_id"]
    logger.info(f"[AssistantGrading] 建议生成: analysis_id={analysis_id}")
    
    # 占位实现
    return {
        "suggestions": [],
        "current_stage": "suggestions_generated",
        "percentage": 75.0,
    }


async def deep_analysis_node(state: AssistantGradingState) -> Dict[str, Any]:
    """
    深度分析节点
    
    TODO: 实现完整逻辑
    """
    analysis_id = state["analysis_id"]
    logger.info(f"[AssistantGrading] 深度分析: analysis_id={analysis_id}")
    
    # 占位实现
    return {
        "deep_analysis": {},
        "current_stage": "deep_analyzed",
        "percentage": 90.0,
    }


async def generate_report_node(state: AssistantGradingState) -> Dict[str, Any]:
    """
    报告生成节点
    
    TODO: 实现完整逻辑
    """
    analysis_id = state["analysis_id"]
    logger.info(f"[AssistantGrading] 报告生成: analysis_id={analysis_id}")
    
    # 占位实现
    return {
        "report": {},
        "report_url": None,
        "current_stage": "completed",
        "percentage": 100.0,
    }


# ==================== 工作流构建 ====================

def create_assistant_grading_graph(checkpointer=None):
    """
    创建辅助批改工作流图
    
    Args:
        checkpointer: 检查点保存器（用于持久化和恢复）
        
    Returns:
        编译后的工作流图
    """
    # 创建图
    graph = StateGraph(AssistantGradingState)
    
    # 添加节点
    graph.add_node("understand", understand_assignment_node)
    graph.add_node("identify_errors", identify_errors_node)
    graph.add_node("generate_suggestions", generate_suggestions_node)
    graph.add_node("deep_analysis", deep_analysis_node)
    graph.add_node("generate_report", generate_report_node)
    
    # 设置入口
    graph.set_entry_point("understand")
    
    # 添加边（线性流程）
    graph.add_edge("understand", "identify_errors")
    graph.add_edge("identify_errors", "generate_suggestions")
    graph.add_edge("generate_suggestions", "deep_analysis")
    graph.add_edge("deep_analysis", "generate_report")
    graph.add_edge("generate_report", END)
    
    # 编译图
    return graph.compile(
        checkpointer=checkpointer,
        recursion_limit=20,  # 限制递归深度
    )


# ==================== 工作流测试工具 ====================

async def test_assistant_workflow():
    """测试辅助批改工作流"""
    from src.graphs.state import create_initial_assistant_state
    
    # 创建初始状态
    initial_state = create_initial_assistant_state(
        analysis_id="test_ana_001",
        images=["test_image_base64"],
        subject="mathematics",
    )
    
    # 创建工作流
    graph = create_assistant_grading_graph()
    
    # 执行工作流
    config = {"configurable": {"thread_id": "test_thread_001"}}
    final_state = await graph.ainvoke(initial_state, config)
    
    # 打印结果
    print(f"最终状态: {final_state['current_stage']}")
    print(f"完成进度: {final_state['percentage']}%")
    
    return final_state


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_assistant_workflow())
```

**验收标准**:
- [x] 图结构正确
- [x] 节点占位符完整
- [x] 可以编译和测试运行

---

## 🚀 阶段 2: 核心服务 (Day 3-5)

### Task 2.1: 实现分析引擎

**文件**: `src/services/assistant_analyzer.py` (新建)

**核心功能**:
- 理解作业内容
- 深度分析评估
- LLM Prompt 构建

**代码框架**: 见详细设计文档

---

### Task 2.2: 实现错误检测器

**文件**: `src/services/error_detector.py` (新建)

**核心功能**:
- 检测各类错误
- 错误分类和严重程度评估
- 错误上下文提取

---

### Task 2.3: 实现建议生成器

**文件**: `src/services/suggestion_generator.py` (新建)

**核心功能**:
- 生成纠正建议
- 生成改进建议
- 生成替代方案

---

### Task 2.4: 实现报告构建器

**文件**: `src/services/report_builder.py` (新建)

**核心功能**:
- 汇总分析结果
- 生成结构化报告
- 存储报告到对象存储

---

## 📡 阶段 3: API 实现 (Day 6-7)

### Task 3.1: 实现 REST API

**文件**: `src/api/routes/assistant_grading.py` (新建)

```python
"""辅助批改 API 路由"""

import uuid
import logging
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from src.orchestration.base import Orchestrator
from src.api.dependencies import get_orchestrator
from src.graphs.state import create_initial_assistant_state


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/assistant", tags=["辅助批改"])


# ==================== 请求/响应模型 ====================

class AnalyzeRequest(BaseModel):
    """单份作业分析请求"""
    images_base64: List[str] = Field(..., description="作业图片 Base64 列表")
    submission_id: Optional[str] = Field(None, description="关联的提交 ID")
    student_id: Optional[str] = Field(None, description="学生 ID")
    subject: Optional[str] = Field(None, description="科目")
    context_info: Optional[Dict[str, Any]] = Field(None, description="上下文信息")


class AnalyzeResponse(BaseModel):
    """分析响应"""
    success: bool
    analysis_id: str = Field(..., description="分析任务 ID")
    message: Optional[str] = None
    error: Optional[str] = None


# ==================== API 路由 ====================

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_assignment(
    request: AnalyzeRequest,
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    """
    单份作业分析
    
    启动辅助分析工作流，深度理解作业内容并提供改进建议。
    """
    try:
        # 生成分析 ID
        analysis_id = f"ana_{uuid.uuid4().hex[:12]}"
        
        # 创建初始状态
        initial_state = create_initial_assistant_state(
            analysis_id=analysis_id,
            images=request.images_base64,
            submission_id=request.submission_id,
            student_id=request.student_id,
            subject=request.subject,
            context_info=request.context_info,
        )
        
        # 启动工作流
        run_id = await orchestrator.start_run(
            graph_name="assistant_grading",
            input_data=initial_state,
            run_id=analysis_id,
        )
        
        logger.info(f"[AssistantAPI] 分析任务已启动: analysis_id={analysis_id}")
        
        return AnalyzeResponse(
            success=True,
            analysis_id=analysis_id,
            message="分析任务已启动",
        )
        
    except Exception as e:
        logger.error(f"[AssistantAPI] 启动分析失败: {e}", exc_info=True)
        return AnalyzeResponse(
            success=False,
            analysis_id="",
            error=str(e),
        )


# TODO: 实现其他 API 端点
```

---

### Task 3.2: 实现 WebSocket 进度推送

在 `assistant_grading.py` 中添加 WebSocket 端点

```python
@router.websocket("/ws/{analysis_id}")
async def analysis_progress_ws(
    websocket: WebSocket,
    analysis_id: str,
):
    """WebSocket 进度推送"""
    # TODO: 实现 WebSocket 逻辑
    pass
```

---

## 🧪 阶段 4: 测试与优化 (Day 8-10)

### Task 4.1: 单元测试

**文件**: `tests/unit/test_assistant_analyzer.py` (新建)

```python
import pytest
from src.services.assistant_analyzer import AssistantAnalyzer


@pytest.mark.asyncio
async def test_understand_assignment():
    """测试理解分析功能"""
    analyzer = AssistantAnalyzer()
    
    result = await analyzer.understand_assignment(
        images=["test_image"],
        context={"chapter": "微积分"},
        subject="mathematics",
    )
    
    assert "knowledge_points" in result
    assert len(result["knowledge_points"]) > 0
```

---

### Task 4.2: 集成测试

**文件**: `tests/integration/test_assistant_grading_workflow.py` (新建)

---

### Task 4.3: 性能优化

- 并发控制
- 缓存策略
- 超时设置

---

### Task 4.4: 文档完善

- API 文档
- 部署文档
- 用户指南

---

## ✅ 验收清单

### 功能完整性
- [ ] 所有节点正常工作
- [ ] API 端点可访问
- [ ] WebSocket 正常推送
- [ ] 报告生成正确

### 代码质量
- [ ] 单元测试覆盖率 > 80%
- [ ] 集成测试通过
- [ ] 类型注解完整
- [ ] 日志规范

### 性能指标
- [ ] 单次分析 < 5 分钟
- [ ] 并发数控制有效
- [ ] 不干扰主系统

### 文档完善
- [ ] 架构文档完整
- [ ] API 文档清晰
- [ ] 部署文档可用

---

**开始实施**: 从阶段 1 的 Task 1.1 开始！
