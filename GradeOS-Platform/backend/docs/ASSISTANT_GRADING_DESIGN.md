# 辅助批改系统架构设计

**版本**: 1.0  
**日期**: 2026-01-28  
**状态**: 设计阶段

## 1. 概述

### 1.1 系统定位

辅助批改系统（Assistant Grading System）是一个与主批改系统并行运行的**智能分析系统**，专注于深度理解学生作业、发现错误并提供改进建议。

**核心特点**：
- ✅ **不依赖评分标准（Rubric）**：通过 AI 理解作业本身
- ✅ **深度分析**：识别知识点、解题思路、逻辑链条
- ✅ **智能纠错**：发现计算错误、逻辑错误、概念错误
- ✅ **独立运行**：不干扰主批改系统性能
- ✅ **可选功能**：教师可以选择是否启用

### 1.2 与主系统的关系

```
┌─────────────────────────────────────────────────────┐
│                  GradeOS 平台                        │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌──────────────────┐      ┌──────────────────┐   │
│  │  主批改系统       │      │  辅助批改系统     │   │
│  │  (Standard)      │      │  (Assistant)     │   │
│  │                  │      │                  │   │
│  │ • 依赖 Rubric    │      │ • 不依赖 Rubric  │   │
│  │ • 打分为主       │ 独立  │ • 深度分析为主   │   │
│  │ • 实时反馈       │ 并行  │ • 纠错建议       │   │
│  │ • 高性能要求     │      │ • 可以异步       │   │
│  └──────────────────┘      └──────────────────┘   │
│          │                         │                │
│          └─────────┬───────────────┘                │
│                    │                                │
│            ┌───────▼────────┐                       │
│            │  共享服务层     │                       │
│            │ • LLM Client   │                       │
│            │ • Storage      │                       │
│            │ • Cache        │                       │
│            └────────────────┘                       │
└─────────────────────────────────────────────────────┘
```

### 1.3 使用场景

1. **教师视角**：
   - 主批改完成后，查看详细的分析报告
   - 了解学生的理解程度和思维方式
   - 发现主批改可能遗漏的问题

2. **学生视角**：
   - 获得比传统批改更详细的反馈
   - 理解错误原因和改进方向
   - 提升学习效果

3. **系统管理员**：
   - 独立的性能监控
   - 不影响主系统稳定性
   - 可以单独升级和维护

---

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      API 层                                  │
│  /api/assistant/analyze        - 单份作业分析               │
│  /api/assistant/analyze/batch  - 批量分析                   │
│  /api/assistant/report/{id}    - 获取分析报告               │
│  /ws/assistant/{batch_id}      - WebSocket 进度推送         │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  LangGraph 编排层                            │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  assistant_grading.py - 辅助批改工作流                │  │
│  │                                                        │  │
│  │  Entry                                                │  │
│  │    ↓                                                  │  │
│  │  [理解分析]  understand_assignment_node               │  │
│  │    ↓                                                  │  │
│  │  [错误识别]  identify_errors_node                     │  │
│  │    ↓                                                  │  │
│  │  [改进建议]  generate_suggestions_node                │  │
│  │    ↓                                                  │  │
│  │  [深度分析]  deep_analysis_node                       │  │
│  │    ↓                                                  │  │
│  │  [报告生成]  generate_report_node                     │  │
│  │    ↓                                                  │  │
│  │  END                                                  │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      服务层                                  │
│  • AssistantAnalyzer      - 核心分析引擎                    │
│  • ErrorDetector          - 错误检测器                      │
│  • SuggestionGenerator    - 建议生成器                      │
│  • ReportBuilder          - 报告构建器                      │
│  • LLMClient (复用)       - 大模型客户端                    │
│  • Storage (复用)         - 存储服务                        │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      数据层                                  │
│  • assistant_analysis_reports   - 分析报告表                │
│  • assistant_error_records      - 错误记录表                │
│  • assistant_suggestions        - 建议记录表                │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 目录结构

```
GradeOS-Platform/backend/src/
├── api/
│   └── routes/
│       └── assistant_grading.py          # 新增：辅助批改 API
│
├── graphs/
│   ├── assistant_grading.py              # 新增：辅助批改工作流
│   └── state.py                          # 更新：添加 AssistantGradingState
│
├── services/
│   ├── assistant_analyzer.py             # 新增：核心分析引擎
│   ├── error_detector.py                 # 新增：错误检测器
│   ├── suggestion_generator.py           # 新增：建议生成器
│   └── report_builder.py                 # 新增：报告构建器
│
├── models/
│   └── assistant_models.py               # 新增：辅助批改数据模型
│
└── db/
    └── assistant_tables.py               # 新增：数据库表定义
```

---

## 3. LangGraph 工作流设计

### 3.1 状态定义

```python
# src/graphs/state.py

class AssistantGradingState(TypedDict, total=False):
    """辅助批改状态定义
    
    用于深度分析学生作业，不依赖评分标准。
    """
    
    # ===== 基础信息 =====
    analysis_id: str                          # 分析任务 ID
    submission_id: Optional[str]              # 关联的提交 ID（如果是在主批改后运行）
    student_id: Optional[str]                 # 学生 ID
    subject: Optional[str]                    # 科目
    
    # ===== 输入数据 =====
    inputs: Dict[str, Any]                    # 输入数据
    image_paths: List[str]                    # 作业图片路径
    image_base64_list: List[str]              # 图片 Base64 列表
    context_info: Optional[Dict[str, Any]]    # 上下文信息（题目描述、章节等）
    
    # ===== 理解分析结果 =====
    understanding: Dict[str, Any]             # 作业理解结果
    # {
    #   "knowledge_points": [...],           # 涉及的知识点
    #   "question_types": [...],             # 题目类型
    #   "solution_approaches": [...],        # 解题思路
    #   "difficulty_level": "...",           # 难度评估
    # }
    
    # ===== 错误识别结果 =====
    errors: List[Dict[str, Any]]              # 识别出的错误列表
    # [
    #   {
    #     "error_id": "...",
    #     "error_type": "calculation|logic|concept|writing",
    #     "location": {"page": 0, "region": "..."},
    #     "description": "...",
    #     "severity": "high|medium|low",
    #     "affected_steps": [...],
    #   }
    # ]
    
    # ===== 改进建议结果 =====
    suggestions: List[Dict[str, Any]]         # 改进建议列表
    # [
    #   {
    #     "suggestion_id": "...",
    #     "related_error_id": "...",          # 关联的错误 ID
    #     "suggestion_type": "correction|improvement|alternative",
    #     "description": "...",
    #     "example": "...",                   # 示例
    #     "priority": "high|medium|low",
    #   }
    # ]
    
    # ===== 深度分析结果 =====
    deep_analysis: Dict[str, Any]             # 深度分析结果
    # {
    #   "understanding_score": 0-100,         # 理解程度评分
    #   "logic_coherence": 0-100,             # 逻辑连贯性
    #   "completeness": 0-100,                # 完整性
    #   "strengths": [...],                   # 优点
    #   "weaknesses": [...],                  # 不足
    #   "learning_recommendations": [...],    # 学习建议
    # }
    
    # ===== 最终报告 =====
    report: Dict[str, Any]                    # 分析报告
    report_url: Optional[str]                 # 报告存储 URL
    
    # ===== 进度信息 =====
    progress: Dict[str, Any]                  # 进度详情
    current_stage: str                        # 当前阶段
    percentage: float                         # 完成百分比 (0.0-100.0)
    
    # ===== 错误处理 =====
    processing_errors: List[Dict[str, Any]]   # 处理错误列表
    retry_count: int                          # 重试次数
    
    # ===== 时间戳 =====
    timestamps: Dict[str, str]                # 各阶段时间戳
```

### 3.2 节点设计

#### 节点 1: 理解分析节点

```python
async def understand_assignment_node(state: AssistantGradingState) -> Dict[str, Any]:
    """
    理解作业内容
    
    功能：
    1. 识别作业中的知识点
    2. 分析题目类型（计算题、证明题、应用题等）
    3. 推断学生的解题思路
    4. 评估题目难度
    
    不需要：
    - 评分标准
    - 标准答案
    
    AI Prompt 策略：
    - 要求 AI 作为"学科专家"角色
    - 从作业本身推断题目意图
    - 识别学生的解题步骤和逻辑
    """
    analysis_id = state["analysis_id"]
    images = state["image_base64_list"]
    context = state.get("context_info", {})
    
    logger.info(f"[understand] 开始理解分析: analysis_id={analysis_id}")
    
    # 调用 LLM 进行理解分析
    analyzer = AssistantAnalyzer()
    understanding = await analyzer.understand_assignment(
        images=images,
        context=context,
        subject=state.get("subject"),
    )
    
    return {
        "understanding": understanding,
        "current_stage": "understood",
        "percentage": 25.0,
        "timestamps": {
            **state.get("timestamps", {}),
            "understood_at": datetime.now().isoformat()
        }
    }
```

#### 节点 2: 错误识别节点

```python
async def identify_errors_node(state: AssistantGradingState) -> Dict[str, Any]:
    """
    识别作业中的错误
    
    功能：
    1. 检测计算错误（数值错误、单位错误等）
    2. 检测逻辑错误（推理不当、前后矛盾等）
    3. 检测概念错误（理解偏差、公式误用等）
    4. 检测书写错误（符号错误、格式不规范等）
    
    输出：
    - 错误列表（带位置、类型、严重程度）
    """
    analysis_id = state["analysis_id"]
    images = state["image_base64_list"]
    understanding = state["understanding"]
    
    logger.info(f"[identify_errors] 开始错误识别: analysis_id={analysis_id}")
    
    # 调用错误检测器
    detector = ErrorDetector()
    errors = await detector.detect_errors(
        images=images,
        understanding=understanding,
    )
    
    return {
        "errors": errors,
        "current_stage": "errors_identified",
        "percentage": 50.0,
        "timestamps": {
            **state.get("timestamps", {}),
            "errors_identified_at": datetime.now().isoformat()
        }
    }
```

#### 节点 3: 改进建议节点

```python
async def generate_suggestions_node(state: AssistantGradingState) -> Dict[str, Any]:
    """
    生成改进建议
    
    功能：
    1. 针对每个错误生成纠正建议
    2. 提供改进建议（更好的解题方法）
    3. 提供替代方案（其他解题思路）
    4. 提供学习资源建议
    
    输出：
    - 建议列表（带优先级、示例）
    """
    analysis_id = state["analysis_id"]
    errors = state["errors"]
    understanding = state["understanding"]
    
    logger.info(f"[generate_suggestions] 开始生成建议: analysis_id={analysis_id}")
    
    # 调用建议生成器
    generator = SuggestionGenerator()
    suggestions = await generator.generate_suggestions(
        errors=errors,
        understanding=understanding,
    )
    
    return {
        "suggestions": suggestions,
        "current_stage": "suggestions_generated",
        "percentage": 75.0,
        "timestamps": {
            **state.get("timestamps", {}),
            "suggestions_generated_at": datetime.now().isoformat()
        }
    }
```

#### 节点 4: 深度分析节点

```python
async def deep_analysis_node(state: AssistantGradingState) -> Dict[str, Any]:
    """
    深度分析
    
    功能：
    1. 评估学生的理解程度（0-100 分）
    2. 评估逻辑连贯性
    3. 评估答案完整性
    4. 总结优点和不足
    5. 生成学习建议
    
    输出：
    - 深度分析结果
    """
    analysis_id = state["analysis_id"]
    understanding = state["understanding"]
    errors = state["errors"]
    suggestions = state["suggestions"]
    
    logger.info(f"[deep_analysis] 开始深度分析: analysis_id={analysis_id}")
    
    # 调用分析器
    analyzer = AssistantAnalyzer()
    deep_analysis = await analyzer.deep_analyze(
        understanding=understanding,
        errors=errors,
        suggestions=suggestions,
    )
    
    return {
        "deep_analysis": deep_analysis,
        "current_stage": "deep_analyzed",
        "percentage": 90.0,
        "timestamps": {
            **state.get("timestamps", {}),
            "deep_analyzed_at": datetime.now().isoformat()
        }
    }
```

#### 节点 5: 报告生成节点

```python
async def generate_report_node(state: AssistantGradingState) -> Dict[str, Any]:
    """
    生成分析报告
    
    功能：
    1. 汇总所有分析结果
    2. 生成结构化报告
    3. 生成可视化图表（可选）
    4. 存储报告到数据库/对象存储
    
    输出：
    - 报告对象
    - 报告 URL
    """
    analysis_id = state["analysis_id"]
    understanding = state["understanding"]
    errors = state["errors"]
    suggestions = state["suggestions"]
    deep_analysis = state["deep_analysis"]
    
    logger.info(f"[generate_report] 开始生成报告: analysis_id={analysis_id}")
    
    # 调用报告构建器
    builder = ReportBuilder()
    report = await builder.build_report(
        analysis_id=analysis_id,
        understanding=understanding,
        errors=errors,
        suggestions=suggestions,
        deep_analysis=deep_analysis,
    )
    
    # 存储报告
    report_url = await builder.save_report(analysis_id, report)
    
    return {
        "report": report,
        "report_url": report_url,
        "current_stage": "completed",
        "percentage": 100.0,
        "timestamps": {
            **state.get("timestamps", {}),
            "completed_at": datetime.now().isoformat()
        }
    }
```

### 3.3 工作流图

```python
# src/graphs/assistant_grading.py

def create_assistant_grading_graph(checkpointer=None) -> CompiledGraph:
    """创建辅助批改工作流图"""
    
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
        # 可以设置独立的递归限制
        recursion_limit=20,
    )
```

### 3.4 工作流状态流转图

```
              ┌───────────┐
              │   Entry   │
              └─────┬─────┘
                    │
                    ▼
         ┌────────────────────┐
         │  understand        │  25%
         │  理解分析节点       │
         └────────┬───────────┘
                  │
                  ▼
         ┌────────────────────┐
         │  identify_errors   │  50%
         │  错误识别节点       │
         └────────┬───────────┘
                  │
                  ▼
    ┌─────────────────────────────┐
    │  generate_suggestions       │  75%
    │  改进建议节点                │
    └─────────────┬───────────────┘
                  │
                  ▼
         ┌────────────────────┐
         │  deep_analysis     │  90%
         │  深度分析节点       │
         └────────┬───────────┘
                  │
                  ▼
         ┌────────────────────┐
         │  generate_report   │  100%
         │  报告生成节点       │
         └────────┬───────────┘
                  │
                  ▼
              ┌───────┐
              │  END  │
              └───────┘
```

---

## 4. API 接口设计

### 4.1 API 路由

```python
# src/api/routes/assistant_grading.py

router = APIRouter(prefix="/assistant", tags=["辅助批改"])

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_assignment(request: AnalyzeRequest)
    """单份作业分析"""

@router.post("/analyze/batch", response_model=BatchAnalyzeResponse)
async def analyze_batch(request: BatchAnalyzeRequest)
    """批量作业分析"""

@router.get("/report/{analysis_id}", response_model=ReportResponse)
async def get_analysis_report(analysis_id: str)
    """获取分析报告"""

@router.get("/status/{analysis_id}", response_model=StatusResponse)
async def get_analysis_status(analysis_id: str)
    """获取分析状态"""

@router.post("/cancel/{analysis_id}")
async def cancel_analysis(analysis_id: str)
    """取消分析任务"""

@router.websocket("/ws/{analysis_id}")
async def analysis_progress_ws(websocket: WebSocket, analysis_id: str)
    """WebSocket 进度推送"""
```

### 4.2 请求/响应模型

```python
# src/api/routes/assistant_grading.py

class AnalyzeRequest(BaseModel):
    """单份作业分析请求"""
    
    images_base64: List[str] = Field(..., description="作业图片 Base64 列表")
    submission_id: Optional[str] = Field(None, description="关联的提交 ID")
    student_id: Optional[str] = Field(None, description="学生 ID")
    subject: Optional[str] = Field(None, description="科目")
    context_info: Optional[Dict[str, Any]] = Field(
        None,
        description="上下文信息（题目描述、章节等）"
    )


class AnalyzeResponse(BaseModel):
    """分析响应"""
    
    success: bool
    analysis_id: str = Field(..., description="分析任务 ID")
    message: Optional[str] = None
    error: Optional[str] = None


class BatchAnalyzeRequest(BaseModel):
    """批量分析请求"""
    
    submissions: List[Dict[str, Any]] = Field(
        ...,
        description="提交列表，每个提交包含 images_base64, student_id 等字段"
    )
    subject: Optional[str] = Field(None, description="科目")
    context_info: Optional[Dict[str, Any]] = Field(None, description="上下文信息")


class BatchAnalyzeResponse(BaseModel):
    """批量分析响应"""
    
    success: bool
    batch_id: str = Field(..., description="批次 ID")
    analysis_ids: List[str] = Field(..., description="各分析任务 ID")
    message: Optional[str] = None
    error: Optional[str] = None


class ReportResponse(BaseModel):
    """报告响应"""
    
    success: bool
    report: Optional[Dict[str, Any]] = Field(None, description="分析报告")
    report_url: Optional[str] = Field(None, description="报告存储 URL")
    error: Optional[str] = None


class StatusResponse(BaseModel):
    """状态响应"""
    
    analysis_id: str
    status: str = Field(..., description="pending|processing|completed|failed")
    current_stage: str
    percentage: float
    error: Optional[str] = None
```

### 4.3 API 使用示例

#### 单份作业分析

```bash
POST /api/assistant/analyze
Content-Type: application/json

{
  "images_base64": ["base64_string_1", "base64_string_2"],
  "submission_id": "sub_12345",
  "student_id": "stu_67890",
  "subject": "mathematics",
  "context_info": {
    "chapter": "微积分基础",
    "topic": "导数与极限"
  }
}
```

响应：

```json
{
  "success": true,
  "analysis_id": "ana_abc123",
  "message": "分析任务已启动"
}
```

#### 获取分析报告

```bash
GET /api/assistant/report/ana_abc123
```

响应：

```json
{
  "success": true,
  "report": {
    "analysis_id": "ana_abc123",
    "student_id": "stu_67890",
    "understanding": {
      "knowledge_points": [
        "极限的定义",
        "导数的几何意义",
        "链式法则"
      ],
      "solution_approaches": [
        "通过定义求极限",
        "使用洛必达法则"
      ],
      "difficulty_level": "medium"
    },
    "errors": [
      {
        "error_id": "err_001",
        "error_type": "calculation",
        "description": "在第三步计算中，分母应该是 (x-1)² 而不是 (x-1)",
        "severity": "high",
        "location": {"page": 0, "region": "middle"}
      }
    ],
    "suggestions": [
      {
        "suggestion_id": "sug_001",
        "related_error_id": "err_001",
        "description": "建议检查平方运算的步骤...",
        "example": "正确的计算应该是...",
        "priority": "high"
      }
    ],
    "deep_analysis": {
      "understanding_score": 75,
      "logic_coherence": 80,
      "completeness": 70,
      "strengths": ["解题思路清晰", "步骤完整"],
      "weaknesses": ["计算粗心", "符号使用不规范"],
      "learning_recommendations": [
        "加强基础运算练习",
        "注意符号书写规范"
      ]
    }
  },
  "report_url": "https://storage.example.com/reports/ana_abc123.json"
}
```

#### WebSocket 进度推送

```javascript
// 前端代码示例
const ws = new WebSocket('ws://localhost:8000/api/assistant/ws/ana_abc123');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('进度更新:', data);
  // {
  //   "type": "progress",
  //   "analysis_id": "ana_abc123",
  //   "current_stage": "identify_errors",
  //   "percentage": 50.0,
  //   "message": "正在识别错误..."
  // }
};
```

---

## 5. 数据模型设计

### 5.1 Pydantic 模型

```python
# src/models/assistant_models.py

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime


class KnowledgePoint(BaseModel):
    """知识点"""
    name: str = Field(..., description="知识点名称")
    category: str = Field(..., description="分类")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="置信度")


class UnderstandingResult(BaseModel):
    """理解分析结果"""
    knowledge_points: List[KnowledgePoint] = Field(default_factory=list)
    question_types: List[str] = Field(default_factory=list)
    solution_approaches: List[str] = Field(default_factory=list)
    difficulty_level: Literal["easy", "medium", "hard"] = Field("medium")
    estimated_time_minutes: Optional[int] = None


class ErrorLocation(BaseModel):
    """错误位置"""
    page: int = Field(..., description="页码")
    region: Optional[str] = Field(None, description="区域描述")
    coordinates: Optional[Dict[str, float]] = Field(None, description="坐标")


class ErrorRecord(BaseModel):
    """错误记录"""
    error_id: str
    error_type: Literal["calculation", "logic", "concept", "writing"]
    description: str
    severity: Literal["high", "medium", "low"]
    location: ErrorLocation
    affected_steps: List[str] = Field(default_factory=list)
    context: Optional[str] = None


class Suggestion(BaseModel):
    """改进建议"""
    suggestion_id: str
    related_error_id: Optional[str] = None
    suggestion_type: Literal["correction", "improvement", "alternative"]
    description: str
    example: Optional[str] = None
    priority: Literal["high", "medium", "low"]
    resources: List[str] = Field(default_factory=list)


class DeepAnalysisResult(BaseModel):
    """深度分析结果"""
    understanding_score: float = Field(..., ge=0.0, le=100.0)
    logic_coherence: float = Field(..., ge=0.0, le=100.0)
    completeness: float = Field(..., ge=0.0, le=100.0)
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    learning_recommendations: List[str] = Field(default_factory=list)


class AnalysisReport(BaseModel):
    """分析报告"""
    analysis_id: str
    submission_id: Optional[str] = None
    student_id: Optional[str] = None
    subject: Optional[str] = None
    understanding: UnderstandingResult
    errors: List[ErrorRecord]
    suggestions: List[Suggestion]
    deep_analysis: DeepAnalysisResult
    created_at: datetime
    completed_at: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "analysis_id": "ana_abc123",
                "student_id": "stu_67890",
                "understanding": {
                    "knowledge_points": [
                        {"name": "极限", "category": "微积分", "confidence": 0.9}
                    ],
                    "difficulty_level": "medium"
                },
                "errors": [],
                "suggestions": [],
                "deep_analysis": {
                    "understanding_score": 75.0,
                    "logic_coherence": 80.0,
                    "completeness": 70.0,
                    "strengths": [],
                    "weaknesses": [],
                    "learning_recommendations": []
                }
            }
        }
```

### 5.2 数据库表定义

```python
# src/db/assistant_tables.py

from sqlalchemy import Column, String, Integer, Float, JSON, DateTime, Text, Enum
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class AssistantAnalysisReport(Base):
    """辅助分析报告表"""
    __tablename__ = "assistant_analysis_reports"
    
    analysis_id = Column(String(64), primary_key=True, comment="分析 ID")
    submission_id = Column(String(64), nullable=True, index=True, comment="关联提交 ID")
    student_id = Column(String(64), nullable=True, index=True, comment="学生 ID")
    subject = Column(String(64), nullable=True, comment="科目")
    
    # 分析结果（JSON 格式）
    understanding = Column(JSON, nullable=True, comment="理解分析结果")
    errors = Column(JSON, nullable=True, comment="错误列表")
    suggestions = Column(JSON, nullable=True, comment="建议列表")
    deep_analysis = Column(JSON, nullable=True, comment="深度分析结果")
    
    # 报告信息
    report_url = Column(String(512), nullable=True, comment="报告存储 URL")
    status = Column(
        Enum("pending", "processing", "completed", "failed", name="analysis_status"),
        default="pending",
        comment="分析状态"
    )
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    started_at = Column(DateTime, nullable=True, comment="开始时间")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")
    
    # 错误信息
    error_message = Column(Text, nullable=True, comment="错误信息")


class AssistantErrorRecord(Base):
    """错误记录表（细粒度存储）"""
    __tablename__ = "assistant_error_records"
    
    error_id = Column(String(64), primary_key=True, comment="错误 ID")
    analysis_id = Column(String(64), nullable=False, index=True, comment="关联分析 ID")
    
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
    context = Column(Text, nullable=True, comment="上下文")
    
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")


class AssistantSuggestion(Base):
    """建议记录表（细粒度存储）"""
    __tablename__ = "assistant_suggestions"
    
    suggestion_id = Column(String(64), primary_key=True, comment="建议 ID")
    analysis_id = Column(String(64), nullable=False, index=True, comment="关联分析 ID")
    related_error_id = Column(String(64), nullable=True, comment="关联错误 ID")
    
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
    
    resources = Column(JSON, nullable=True, comment="学习资源列表")
    
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
```

---

## 6. 服务层设计

### 6.1 核心分析引擎

```python
# src/services/assistant_analyzer.py

class AssistantAnalyzer:
    """辅助分析引擎
    
    负责深度理解和分析学生作业。
    """
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()
    
    async def understand_assignment(
        self,
        images: List[str],
        context: Optional[Dict[str, Any]] = None,
        subject: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        理解作业内容
        
        Args:
            images: 作业图片（Base64）
            context: 上下文信息（章节、题目描述等）
            subject: 科目
            
        Returns:
            理解分析结果
        """
        # 构建 Prompt
        prompt = self._build_understanding_prompt(context, subject)
        
        # 调用 LLM
        response = await self.llm_client.analyze_images(
            prompt=prompt,
            images=images,
        )
        
        # 解析响应
        understanding = self._parse_understanding_response(response)
        
        return understanding
    
    async def deep_analyze(
        self,
        understanding: Dict[str, Any],
        errors: List[Dict[str, Any]],
        suggestions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        深度分析
        
        Args:
            understanding: 理解分析结果
            errors: 错误列表
            suggestions: 建议列表
            
        Returns:
            深度分析结果
        """
        # 构建 Prompt
        prompt = self._build_deep_analysis_prompt(understanding, errors, suggestions)
        
        # 调用 LLM
        response = await self.llm_client.chat(prompt=prompt)
        
        # 解析响应
        deep_analysis = self._parse_deep_analysis_response(response)
        
        return deep_analysis
    
    def _build_understanding_prompt(
        self,
        context: Optional[Dict[str, Any]],
        subject: Optional[str],
    ) -> str:
        """构建理解分析 Prompt"""
        prompt = f"""
你是一位经验丰富的{subject or ''}学科专家和教育心理学家。
请深入分析这份学生作业，重点关注：

1. **知识点识别**：作业涉及哪些核心知识点？
2. **题目类型**：这是什么类型的题目？（计算题、证明题、应用题等）
3. **解题思路**：学生采用了什么解题方法和逻辑？
4. **难度评估**：题目的难度如何？（简单/中等/困难）

"""
        if context:
            prompt += f"\n**上下文信息**：\n{json.dumps(context, ensure_ascii=False, indent=2)}\n"
        
        prompt += """
请以 JSON 格式输出，格式如下：
{
  "knowledge_points": [
    {"name": "知识点名称", "category": "分类", "confidence": 0.9}
  ],
  "question_types": ["题目类型1", "题目类型2"],
  "solution_approaches": ["解题方法1", "解题方法2"],
  "difficulty_level": "easy|medium|hard",
  "estimated_time_minutes": 30
}
"""
        return prompt
    
    def _build_deep_analysis_prompt(
        self,
        understanding: Dict[str, Any],
        errors: List[Dict[str, Any]],
        suggestions: List[Dict[str, Any]],
    ) -> str:
        """构建深度分析 Prompt"""
        prompt = f"""
基于以下信息，对学生的作业进行深度分析：

**理解分析**：
{json.dumps(understanding, ensure_ascii=False, indent=2)}

**识别的错误**：
{json.dumps(errors, ensure_ascii=False, indent=2)}

**改进建议**：
{json.dumps(suggestions, ensure_ascii=False, indent=2)}

请从以下维度进行评估（0-100 分）：

1. **理解程度**：学生对知识点的理解程度如何？
2. **逻辑连贯性**：解题逻辑是否连贯？
3. **完整性**：答案是否完整？

并总结：
- **优点**：学生做得好的地方
- **不足**：需要改进的地方
- **学习建议**：具体的学习建议

请以 JSON 格式输出。
"""
        return prompt
```

### 6.2 错误检测器

```python
# src/services/error_detector.py

class ErrorDetector:
    """错误检测器
    
    负责识别作业中的各类错误。
    """
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()
    
    async def detect_errors(
        self,
        images: List[str],
        understanding: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        检测错误
        
        Args:
            images: 作业图片（Base64）
            understanding: 理解分析结果
            
        Returns:
            错误列表
        """
        # 构建 Prompt
        prompt = self._build_error_detection_prompt(understanding)
        
        # 调用 LLM
        response = await self.llm_client.analyze_images(
            prompt=prompt,
            images=images,
        )
        
        # 解析响应
        errors = self._parse_error_response(response)
        
        return errors
    
    def _build_error_detection_prompt(self, understanding: Dict[str, Any]) -> str:
        """构建错误检测 Prompt"""
        prompt = f"""
基于以下理解分析结果，请仔细检查作业中的错误：

{json.dumps(understanding, ensure_ascii=False, indent=2)}

请识别以下类型的错误：

1. **计算错误**：数值计算错误、单位错误等
2. **逻辑错误**：推理不当、前后矛盾、步骤缺失等
3. **概念错误**：理解偏差、公式误用、定义错误等
4. **书写错误**：符号错误、格式不规范等

对于每个错误，请提供：
- 错误类型
- 具体描述
- 严重程度（high/medium/low）
- 位置（页码、区域）
- 受影响的步骤

请以 JSON 数组格式输出。
"""
        return prompt
```

### 6.3 建议生成器

```python
# src/services/suggestion_generator.py

class SuggestionGenerator:
    """建议生成器
    
    负责生成改进建议。
    """
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()
    
    async def generate_suggestions(
        self,
        errors: List[Dict[str, Any]],
        understanding: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        生成建议
        
        Args:
            errors: 错误列表
            understanding: 理解分析结果
            
        Returns:
            建议列表
        """
        # 构建 Prompt
        prompt = self._build_suggestion_prompt(errors, understanding)
        
        # 调用 LLM
        response = await self.llm_client.chat(prompt=prompt)
        
        # 解析响应
        suggestions = self._parse_suggestion_response(response)
        
        return suggestions
```

### 6.4 报告构建器

```python
# src/services/report_builder.py

class ReportBuilder:
    """报告构建器
    
    负责生成和存储分析报告。
    """
    
    def __init__(self, storage: Optional[Storage] = None):
        self.storage = storage or Storage()
    
    async def build_report(
        self,
        analysis_id: str,
        understanding: Dict[str, Any],
        errors: List[Dict[str, Any]],
        suggestions: List[Dict[str, Any]],
        deep_analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        构建报告
        
        Args:
            analysis_id: 分析 ID
            understanding: 理解分析结果
            errors: 错误列表
            suggestions: 建议列表
            deep_analysis: 深度分析结果
            
        Returns:
            报告对象
        """
        report = {
            "analysis_id": analysis_id,
            "understanding": understanding,
            "errors": errors,
            "suggestions": suggestions,
            "deep_analysis": deep_analysis,
            "created_at": datetime.now().isoformat(),
        }
        
        return report
    
    async def save_report(
        self,
        analysis_id: str,
        report: Dict[str, Any],
    ) -> str:
        """
        保存报告
        
        Args:
            analysis_id: 分析 ID
            report: 报告对象
            
        Returns:
            报告 URL
        """
        # 序列化为 JSON
        report_json = json.dumps(report, ensure_ascii=False, indent=2)
        
        # 上传到对象存储
        object_key = f"assistant_reports/{analysis_id}.json"
        url = await self.storage.upload_text(
            content=report_json,
            object_key=object_key,
            content_type="application/json",
        )
        
        return url
```

---

## 7. 与主系统集成边界

### 7.1 独立性保证

```python
# 配置独立的并发限制
ASSISTANT_MAX_CONCURRENT_WORKERS = int(os.getenv("ASSISTANT_MAX_WORKERS", "2"))

# 配置独立的优先级队列
ASSISTANT_QUEUE_PRIORITY = int(os.getenv("ASSISTANT_QUEUE_PRIORITY", "10"))  # 低于主系统

# 配置独立的超时设置
ASSISTANT_TIMEOUT_SECONDS = int(os.getenv("ASSISTANT_TIMEOUT_SECONDS", "300"))
```

### 7.2 可选功能控制

```python
# src/api/routes/batch_langgraph.py

class BatchGradingRequest(BaseModel):
    """批量批改请求"""
    # ... 现有字段 ...
    
    # 新增：是否启用辅助分析
    enable_assistant_analysis: bool = Field(
        default=False,
        description="是否启用辅助分析（可选）"
    )


async def submit_batch(...):
    """提交批量批改任务"""
    # ... 现有逻辑 ...
    
    # 主批改完成后，如果启用了辅助分析，则启动辅助分析
    if request.enable_assistant_analysis:
        # 异步启动辅助分析（不阻塞主流程）
        asyncio.create_task(
            start_assistant_analysis(batch_id, student_results)
        )
    
    return response
```

### 7.3 数据隔离

- **数据库表**：独立的表（`assistant_analysis_reports`）
- **对象存储**：独立的路径前缀（`assistant_reports/`）
- **缓存键**：独立的前缀（`assistant:analysis:`）
- **日志**：独立的日志前缀（`[AssistantGrading]`）

### 7.4 监控隔离

```python
# 独立的监控指标
ASSISTANT_METRICS = {
    "analyses_started": 0,
    "analyses_completed": 0,
    "analyses_failed": 0,
    "average_duration_seconds": 0.0,
}
```

---

## 8. 实现计划

### 8.1 第一阶段：基础架构（1-2 天）

**任务**：
1. ✅ 创建状态定义（`AssistantGradingState`）
2. ✅ 创建基础 LangGraph 工作流框架
3. ✅ 创建 API 路由框架
4. ✅ 创建数据模型（Pydantic + SQLAlchemy）

**文件**：
- `src/graphs/state.py` - 添加 `AssistantGradingState`
- `src/graphs/assistant_grading.py` - 新建（基础框架）
- `src/api/routes/assistant_grading.py` - 新建（基础路由）
- `src/models/assistant_models.py` - 新建（数据模型）
- `src/db/assistant_tables.py` - 新建（数据库表）

### 8.2 第二阶段：核心功能（3-4 天）

**任务**：
1. ✅ 实现理解分析节点
2. ✅ 实现错误识别节点
3. ✅ 实现建议生成节点
4. ✅ 实现深度分析节点
5. ✅ 实现报告生成节点

**文件**：
- `src/services/assistant_analyzer.py` - 新建
- `src/services/error_detector.py` - 新建
- `src/services/suggestion_generator.py` - 新建
- `src/services/report_builder.py` - 新建

**Prompt 工程**：
- 设计理解分析 Prompt
- 设计错误检测 Prompt
- 设计建议生成 Prompt
- 设计深度分析 Prompt

### 8.3 第三阶段：集成与测试（2-3 天）

**任务**：
1. ✅ 完整的 API 实现
2. ✅ WebSocket 进度推送
3. ✅ 数据库集成
4. ✅ 单元测试
5. ✅ 集成测试

**文件**：
- `tests/unit/test_assistant_analyzer.py` - 新建
- `tests/unit/test_error_detector.py` - 新建
- `tests/integration/test_assistant_grading_workflow.py` - 新建

### 8.4 第四阶段：优化与文档（1-2 天）

**任务**：
1. ✅ 性能优化
2. ✅ 错误处理完善
3. ✅ API 文档
4. ✅ 部署文档

**文件**：
- `backend/docs/API_ASSISTANT_GRADING.md` - 新建（API 文档）
- `backend/docs/DEPLOYMENT_ASSISTANT.md` - 新建（部署文档）

### 8.5 文件清单

```
新增文件：
- backend/src/graphs/assistant_grading.py          # LangGraph 工作流
- backend/src/api/routes/assistant_grading.py      # API 路由
- backend/src/models/assistant_models.py           # 数据模型
- backend/src/db/assistant_tables.py               # 数据库表
- backend/src/services/assistant_analyzer.py       # 分析引擎
- backend/src/services/error_detector.py           # 错误检测器
- backend/src/services/suggestion_generator.py     # 建议生成器
- backend/src/services/report_builder.py           # 报告构建器
- backend/tests/unit/test_assistant_*.py           # 单元测试
- backend/tests/integration/test_assistant_*.py    # 集成测试
- backend/docs/ASSISTANT_GRADING_DESIGN.md         # 设计文档（本文件）
- backend/docs/API_ASSISTANT_GRADING.md            # API 文档

修改文件：
- backend/src/graphs/state.py                      # 添加 AssistantGradingState
- backend/src/api/main.py                          # 注册新路由
```

---

## 9. 性能考虑

### 9.1 不干扰主系统策略

1. **独立并发控制**：
   ```python
   # 限制辅助分析的并发数
   ASSISTANT_MAX_WORKERS = 2  # 远低于主系统
   ```

2. **低优先级队列**：
   ```python
   # 使用低优先级队列（如果有消息队列）
   queue_priority = 10  # 主系统优先级为 1
   ```

3. **异步执行**：
   ```python
   # 不阻塞主批改流程
   asyncio.create_task(start_assistant_analysis(...))
   ```

4. **资源限制**：
   ```python
   # 限制 LLM 调用频率
   rate_limiter = RateLimiter(max_requests_per_minute=30)
   ```

### 9.2 性能优化策略

1. **缓存策略**：
   - 缓存理解分析结果（相似作业可复用）
   - 缓存知识点识别结果
   
2. **批量处理**：
   - 支持批量分析（一次分析多份作业）
   
3. **增量分析**：
   - 如果主批改已经有部分结果，可以复用

---

## 10. 安全与权限

### 10.1 访问控制

- 只有教师和管理员可以启动辅助分析
- 学生只能查看自己的分析报告
- 敏感信息（如学生 ID）需要脱敏

### 10.2 数据隐私

- 分析报告包含学生作业信息，需要加密存储
- 设置报告访问有效期（如 30 天）
- 定期清理过期报告

---

## 11. 监控与运维

### 11.1 监控指标

```python
# Prometheus 指标
assistant_analyses_total = Counter("assistant_analyses_total", "总分析数")
assistant_analyses_duration = Histogram("assistant_analyses_duration_seconds", "分析耗时")
assistant_analyses_errors = Counter("assistant_analyses_errors", "分析错误数")
assistant_llm_calls = Counter("assistant_llm_calls", "LLM 调用次数")
```

### 11.2 日志规范

```python
logger.info(
    f"[AssistantGrading] 开始分析: analysis_id={analysis_id}, "
    f"student_id={student_id}, stage={stage}"
)
```

### 11.3 告警规则

- 分析失败率 > 10%：发送告警
- 平均分析时长 > 5 分钟：发送告警
- LLM 调用失败率 > 5%：发送告警

---

## 12. 后续扩展

### 12.1 可能的扩展功能

1. **对比分析**：对比学生的历史作业，分析进步情况
2. **班级洞察**：分析整个班级的作业，发现共性问题
3. **自适应建议**：根据学生水平，提供个性化建议
4. **多模态分析**：支持音频、视频等多模态作业分析

### 12.2 技术演进方向

1. **模型优化**：使用更先进的 LLM 模型
2. **知识图谱**：构建学科知识图谱，提升分析精度
3. **强化学习**：通过教师反馈，优化分析模型

---

## 13. 总结

### 13.1 设计亮点

✅ **完全独立**：不干扰主批改系统  
✅ **深度智能**：不依赖评分标准，AI 自主理解  
✅ **可选启用**：教师可以灵活控制  
✅ **易于扩展**：清晰的架构，便于后续功能扩展  

### 13.2 技术栈一致性

✅ **LangGraph**：与主系统一致的工作流编排  
✅ **FastAPI**：与主系统一致的 API 框架  
✅ **PostgreSQL**：与主系统一致的数据库  
✅ **Pydantic**：与主系统一致的数据验证  

### 13.3 开发优先级

1. **P0（核心）**：理解分析、错误识别、报告生成
2. **P1（重要）**：改进建议、深度分析
3. **P2（增强）**：批量分析、WebSocket 进度
4. **P3（优化）**：缓存、性能优化

---

**下一步**：开始实现第一阶段（基础架构）。
