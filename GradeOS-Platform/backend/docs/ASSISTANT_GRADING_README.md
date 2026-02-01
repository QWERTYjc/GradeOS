# 辅助批改系统 - 文档导航

**系统名称**: Assistant Grading System  
**版本**: 1.0  
**状态**: 设计完成，待实现  
**日期**: 2026-01-28

---

## 📚 文档索引

### 1. [架构设计文档](./ASSISTANT_GRADING_DESIGN.md)

**内容**:
- 系统概述和定位
- 整体架构设计
- 目录结构规划
- 与主系统的集成边界
- 性能和安全考虑

**适合阅读人群**: 架构师、技术负责人、产品经理

---

### 2. [工作流详细设计](./ASSISTANT_GRADING_WORKFLOW.md)

**内容**:
- LangGraph 工作流完整流程图
- 每个节点的详细设计
- Prompt 模板设计
- 错误处理和重试机制
- 性能优化策略
- 监控和测试方案

**适合阅读人群**: 后端开发工程师、AI 工程师

---

### 3. [实现计划](./ASSISTANT_GRADING_IMPLEMENTATION.md)

**内容**:
- 4 个阶段的详细任务拆解
- 每个文件的代码框架
- 验收标准和清单
- 开发工期估算

**适合阅读人群**: 开发工程师、项目经理

---

## 🎯 快速开始

### 第一步：阅读架构设计

```bash
阅读: ./ASSISTANT_GRADING_DESIGN.md
重点关注: 
- 第 2 节：架构设计
- 第 3 节：LangGraph 工作流设计
- 第 7 节：与主系统集成边界
```

### 第二步：理解工作流

```bash
阅读: ./ASSISTANT_GRADING_WORKFLOW.md
重点关注:
- 第 2 节：节点详细设计
- Prompt 模板设计
```

### 第三步：开始实现

```bash
阅读: ./ASSISTANT_GRADING_IMPLEMENTATION.md
开始: 阶段 1 - Task 1.1
```

---

## 🏗️ 系统架构一览

```
辅助批改系统 (Assistant Grading System)
│
├── API 层
│   └── /api/assistant/*                   # REST API + WebSocket
│
├── 编排层 (LangGraph)
│   ├── 理解分析节点 (25%)
│   ├── 错误识别节点 (50%)
│   ├── 建议生成节点 (75%)
│   ├── 深度分析节点 (90%)
│   └── 报告生成节点 (100%)
│
├── 服务层
│   ├── AssistantAnalyzer        # 核心分析引擎
│   ├── ErrorDetector            # 错误检测器
│   ├── SuggestionGenerator      # 建议生成器
│   └── ReportBuilder            # 报告构建器
│
└── 数据层
    ├── assistant_analysis_reports     # 分析报告表
    ├── assistant_error_records        # 错误记录表
    └── assistant_suggestions          # 建议记录表
```

---

## 🌟 核心特性

### ✅ 不依赖评分标准
AI 通过深度理解作业内容本身，无需 Rubric

### ✅ 智能错误识别
识别计算错误、逻辑错误、概念错误、书写错误

### ✅ 深度分析评估
- 理解程度评分 (0-100)
- 逻辑连贯性评分 (0-100)
- 完整性评分 (0-100)

### ✅ 个性化建议
提供纠正建议、改进建议、替代方案

### ✅ 独立运行
不干扰主批改系统，可以异步执行

---

## 📊 数据模型

### 核心模型

```python
# 理解分析结果
UnderstandingResult {
  knowledge_points: List[KnowledgePoint]
  question_types: List[str]
  solution_approaches: List[str]
  difficulty_level: "easy|medium|hard"
}

# 错误记录
ErrorRecord {
  error_id: str
  error_type: "calculation|logic|concept|writing"
  description: str
  severity: "high|medium|low"
  location: ErrorLocation
}

# 改进建议
Suggestion {
  suggestion_id: str
  suggestion_type: "correction|improvement|alternative"
  description: str
  priority: "high|medium|low"
}

# 深度分析结果
DeepAnalysisResult {
  understanding_score: float (0-100)
  logic_coherence: float (0-100)
  completeness: float (0-100)
  strengths: List[str]
  weaknesses: List[str]
  learning_recommendations: List[LearningRecommendation]
}
```

---

## 🔄 工作流状态流转

```
initialized (0%)
    ↓
understanding (25%)
    ↓
identifying_errors (50%)
    ↓
generating_suggestions (75%)
    ↓
deep_analyzing (90%)
    ↓
generating_report (100%)
    ↓
completed
```

---

## 🚀 实现路线图

### 阶段 1: 基础架构 (2 天)
- [x] 状态定义
- [x] 数据模型
- [x] 数据库表
- [x] 工作流框架

### 阶段 2: 核心服务 (3 天)
- [ ] 分析引擎
- [ ] 错误检测器
- [ ] 建议生成器
- [ ] 报告构建器

### 阶段 3: API 实现 (2 天)
- [ ] REST API
- [ ] WebSocket
- [ ] 进度推送

### 阶段 4: 测试与优化 (2-3 天)
- [ ] 单元测试
- [ ] 集成测试
- [ ] 性能优化
- [ ] 文档完善

**总计**: 8-10 天

---

## 📦 新增文件清单

```
backend/
├── src/
│   ├── graphs/
│   │   ├── assistant_grading.py          # 新增：LangGraph 工作流
│   │   └── state.py                      # 修改：添加 AssistantGradingState
│   │
│   ├── api/routes/
│   │   └── assistant_grading.py          # 新增：API 路由
│   │
│   ├── models/
│   │   └── assistant_models.py           # 新增：数据模型
│   │
│   ├── db/
│   │   └── assistant_tables.py           # 新增：数据库表
│   │
│   └── services/
│       ├── assistant_analyzer.py         # 新增：分析引擎
│       ├── error_detector.py             # 新增：错误检测器
│       ├── suggestion_generator.py       # 新增：建议生成器
│       └── report_builder.py             # 新增：报告构建器
│
├── tests/
│   ├── unit/
│   │   ├── test_assistant_analyzer.py    # 新增
│   │   ├── test_error_detector.py        # 新增
│   │   └── test_suggestion_generator.py  # 新增
│   │
│   └── integration/
│       └── test_assistant_grading_workflow.py  # 新增
│
└── docs/
    ├── ASSISTANT_GRADING_README.md       # 新增：本文件
    ├── ASSISTANT_GRADING_DESIGN.md       # 新增：架构设计
    ├── ASSISTANT_GRADING_WORKFLOW.md     # 新增：工作流设计
    └── ASSISTANT_GRADING_IMPLEMENTATION.md  # 新增：实现计划
```

---

## 🔧 技术栈

- **编排**: LangGraph (与主系统一致)
- **API**: FastAPI (与主系统一致)
- **数据库**: PostgreSQL (与主系统一致)
- **数据验证**: Pydantic (与主系统一致)
- **类型检查**: Mypy (与主系统一致)
- **AI 模型**: Google Gemini 3.0 Flash (与主系统一致)

---

## 🎓 学习资源

### LangGraph 相关
- [LangGraph 官方文档](https://langchain-ai.github.io/langgraph/)
- [LangGraph StateGraph 教程](https://langchain-ai.github.io/langgraph/tutorials/introduction/)

### Prompt Engineering
- [OpenAI Prompt Engineering Guide](https://platform.openai.com/docs/guides/prompt-engineering)
- [Google Gemini Best Practices](https://ai.google.dev/docs/prompting_guide)

### GradeOS 现有代码
- `backend/src/graphs/batch_grading.py` - 参考主批改工作流
- `backend/src/services/annotation_grading.py` - 参考批注生成逻辑

---

## ❓ FAQ

### Q1: 辅助批改和主批改有什么区别？

**主批改**:
- 依赖评分标准 (Rubric)
- 专注于打分
- 实时反馈
- 高性能要求

**辅助批改**:
- 不依赖评分标准
- 专注于深度分析和纠错
- 可以异步执行
- 提供更详细的改进建议

---

### Q2: 辅助批改会影响主系统性能吗？

**不会**。设计上已经确保：
- 独立的 LangGraph 工作流
- 独立的并发控制 (max_workers = 2)
- 低优先级队列
- 异步执行，不阻塞主流程

---

### Q3: 辅助批改需要多长时间？

预计 **2-5 分钟** 完成一份作业的分析，取决于：
- 作业长度
- 图片数量
- LLM 响应速度

---

### Q4: 如何启用辅助批改？

在主批改 API 请求中添加参数：

```json
{
  "enable_assistant_analysis": true
}
```

或单独调用辅助批改 API：

```bash
POST /api/assistant/analyze
```

---

### Q5: 分析报告包含哪些内容？

- **理解分析**: 知识点、题目类型、解题思路
- **错误列表**: 计算/逻辑/概念/书写错误
- **改进建议**: 纠正/改进/替代方案
- **深度分析**: 理解程度、逻辑连贯性、完整性评分
- **行动计划**: 即时行动、短期目标、长期目标

---

## 📞 联系方式

如有疑问，请联系：
- **架构设计**: Backend Architect Team
- **开发实现**: Backend Development Team
- **产品需求**: Product Manager

---

## 🎉 开始实现

准备好了吗？从阶段 1 的第一个任务开始：

```bash
# 1. 阅读完整设计文档
cd backend/docs
cat ASSISTANT_GRADING_DESIGN.md

# 2. 开始实现第一个任务
# 修改 src/graphs/state.py，添加 AssistantGradingState

# 3. 运行测试
pytest tests/unit/test_assistant_*.py
```

**祝你实现顺利！** 🚀
