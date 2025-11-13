# LangGraph 批改系统完整设计与实施方案

## 0. 综合版本综述
- **设计来源整合**：融合 `DESIGN_SUMMARY.md`、`production_system_architecture.md`、`agent_design_details.md` 与历次 LangGraph 方案的优点，形成“平台级 + LangGraph 流程”双层架构。前者保障数据、监控、持久化；后者聚焦 Prompt、Agent、策略。
- **交付对象**：
  - **产品/业务**：可直接引用的模式对比、实施计划、验收指标。
  - **架构/后端**：统一的 `GradingState`、Agent 责任表、节点间数据契约。
  - **Prompt/LLM 工程师**：成体系的模板、控制开关、回退策略。
- **落地策略**：沿用旧版 6 Agent 主流程，叠加 LangGraph 8 Agent 精细化角色。通过“映射表 + 模块化 Prompt”实现渐进式迁移，避免一次性大改导致的交付风险。


## 1. 设计目标与范围
- 面向理科作业批改的 LangGraph 流程，覆盖题目/答案/评分标准三类输入。
- 通过多智能体协同，完成题目解析、评分标准理解、批改、反馈生成和数据沉淀。
- 输出可落地的提示词（Prompt）与实施计划，方便快速集成至 `ai_correction` 现有代码。

---

## 2. LangGraph 工作流拓扑
```
┌───────────────┐    ┌────────────────┐    ┌──────────────────────┐
│ Intake Router │──▶│ Rubric Builder │──▶│ Evaluation Coordinator │
└───────────────┘    └────────────────┘    └──────┬───────────────┘
        │                                         │
        │                                         ├─────────▶ Question Grader Pool (并行)
        │                                         │
        ▼                                         ▼
┌───────────────────────┐                ┌────────────────────┐
│ Context Synthesizer   │                │ Feedback Composer  │
└──────────┬────────────┘                └──────────┬─────────┘
           │                                         │
           ▼                                         ▼
      ┌──────────────┐                         ┌───────────────┐
      │ QA Sentinel  │◀───────────────────────▶│ Report Weaver │
      └──────────────┘                         └───────────────┘
```
- **State 管理**：统一在 `GradingState`（Python dataclass）中维护，LangGraph 节点仅操作必要字段。
- **内存策略**：Rubric Builder 与 Context Synthesizer 共享 `SharedMemory`，减少重复解析成本。

---

### 2.1 多版本架构融合与职责映射
| 旧版 6 Agent（`production_system_architecture.md`） | LangGraph 8 Agent | 迁移策略 | 技术备注 |
|---|---|---|---|
| InputParser | Intake Router | 直接替换，沿用原正则/分段逻辑；新增文件校验与多学生批次识别。 | `functions/input_parser.py` 中的解析函数抽象为 `router.transform()`，便于在 LangGraph 节点复用。 |
| QuestionAnalyzer | Context Synthesizer + Evaluation Coordinator | QuestionAnalyzer 的题型特征分析拆分为“上下文压缩”与“执行策略”两段，避免单点臃肿。 | Coordinator 中追加旧版题型标签，保证历史统计字段不丢失。 |
| RubricInterpreter | Rubric Builder | 维持 JSON Schema，一并补齐示例答案与扣分项。 | 通过 `rubric_cache` 与 Redis 共享。 |
| QuestionGrader | Question Grader Pool | LangGraph map 节点承接旧版串行批改逻辑，支持“策略 + 置信度”扩展。 | 旧版链式思维 prompt 迁移为 `strategy=reasoning` 子模板。 |
| ResultAggregator | Feedback Composer + QA Sentinel | ResultAggregator 输出拆成“生成反馈”与“质量控制”两步；原统计指标移至 Composer。 | QA Sentinel 负责打回异常分，替代旧版脚本化校验。 |
| DataPersistence | Report Weaver | Report Weaver 除了写 DB，还输出富文本、Webhook，兼容旧版 `DataPersistence` 的 upsert 操作。 | 建议保留原 DAO 作为 Report Weaver 的调用依赖。 |

- **渐进式上线建议**：先在 B（极速）模式中替换 Intake/Context/Rubric 三节点，验证数据契约，再逐步引入 Coordinator/Grader 池与 QA Sentinel，确保监控指标连续可比。
- **回退方案**：每个 LangGraph 节点保持幂等输入输出（JSON Schema），如遇严重问题，可在 `graph.py` 中临时切换回旧版函数调用。

---

## 3. Agent 设计与提示词
下表给出 8 个核心 Agent 的接口设计；后续章节提供完整 Prompt 模板与实现提示。

| Agent | 输入 | 输出 | 关键职责 |
|-------|------|------|----------|
| **Intake Router** | 原始文件、任务配置 | 结构化 `GradingState` | 校验输入、解析元数据、调度分支 |
| **Context Synthesizer** | 结构化题目/答案/评分标准初稿 | LangChain Message | 将题目上下文压缩为低成本提示，生成知识点索引 |
| **Rubric Builder** | 评分标准文件/教师 rubric | JSON rubric schema | 提取得分维度、扣分规则和参考答案 |
| **Evaluation Coordinator** | 题目信息、Rubric、LLM 能力约束 | `WorkItem` 队列 | 将题目拆分、分派到 `Question Grader Pool`，并追踪状态 |
| **Question Grader Agent（Pool）** | 单题上下文、学生答案、Rubric 片段 | 单题评分、错误标签、反馈 | 执行批改逻辑；支持并行/自适应策略 |
| **Feedback Composer** | 所有单题评分、统计需求 | 报告草稿 | 生成学生反馈、知识点建议与教师视图 |
| **QA Sentinel** | 报告草稿、Rubric、业务规则 | 修订后的结果+警示 | 审核一致性、检测缺失项、回滚异常 |
| **Report Weaver** | QA 通过的结果 | JSON + 富文本 + 导出素材 | 统一输出格式，写入 DB/Cache 并回传前端 |

> 注：Question Grader 以池化形式存在，可配置数量（2/4/8）。其余 Agent 在 LangGraph 中为单节点。

### 3.1 Agent 详情与 Prompt
#### 3.1.1 Intake Router Agent
- **输入**：`task_id`, 题目文件、答案文件数组、评分标准文件、教师配置。
- **输出**：`GradingState` 初始化（题目列表、学生元数据、异常列表）。
- **Prompt 模板**：
```
你是 Intake Router。目标：将上传的题目/答案/评分标准转换为结构化 JSON。
步骤：
1. 校验文件完整性与编码。
2. 从文件名/正文中提取学生信息（学号/姓名/班级）。
3. 将题目按题号拆分，保持原始文本与题型猜测。
4. 输出 JSON: {"students":[],"questions":[],"rubric_raw":[],"issues":[]}。
约束：不要批改；检测到缺失文件时写入 issues。
```

#### 3.1.2 Context Synthesizer Agent
- **职责**：对题目与评分标准内容进行摘要，生成低 Token 的上下文块以及知识点索引表。
- **Prompt 模板**：
```
你是 Context Synthesizer。
输入：题目列表、学生答案概览、原始评分标准文本。
任务：
- 为每道题生成 <=120 tokens 的精简描述。
- 识别知识点标签（如「函数单调性」「牛顿第二定律」）。
- 构建 `context_chunks` 数组，每个元素包含 {question_id, summary, key_terms, dependencies}。
输出 JSON，不做任何评分。
```

#### 3.1.3 Rubric Builder Agent
- **职责**：将评分标准转换为机器可读的 schema，包含分值、扣分依据、示例答案。
- **Prompt 模板**：
```
你是 Rubric Builder。
请从教师提供的评分说明中提取：
- score_items: [{question_id, sub_id, description, max_score}]
- deduction_rules: [{question_id, trigger, deduction, rationale}]
- exemplar_answers: [{question_id, key_steps, common_errors}]
若无子题，以 question_id 作为 key。
确保 JSON 可被 `json.loads` 解析。
```

#### 3.1.4 Evaluation Coordinator Agent
- **职责**：融合题目上下文、Rubric schema 与 LLM 资源限制，将题目拆分为 `WorkItem` 队列，决定执行策略（串行/并行/重试）。
- **Prompt 模板**：
```
你是 Evaluation Coordinator。
根据输入的 questions、context_chunks、rubric_schema，生成 work_items 列表。
每个 work_item 至少包含 {question_id, context_chunk, rubric_slice, student_answer, priority, strategy}。
策略枚举："keyword", "reasoning", "math_step", "code_exec"。
额外字段：`confidence_gate` (0-1) 约束最低可信度；`retry_policy` 指定失败重试上限。
输出 JSON: {"work_items": [...], "notes": ["..." ]}。
```

#### 3.1.5 Question Grader Agent（Pool）
- **职责**：逐题批改。根据 `strategy` 选择提示模版分支，支持链式思考与子步骤评分。
- **Prompt 基础模板**：
```
你是 Question Grader，擅长严谨数学与理科批改。
上下文：{{context_chunk}}
评分标准：{{rubric_slice}}
学生答案：{{student_answer}}
执行：
1. 逐步复述关键条件。
2. 对照评分点给出得分，输出 `score_breakdown`。
3. 标注错误位置与原因，提供可执行改进建议。
4. 计算总分（不超过 max_score）。
输出 JSON: {
  "question_id": "",
  "earned_score": number,
  "max_score": number,
  "score_breakdown": [{"sub_id":"","score":0,"reason":""}],
  "error_tags": ["概念混淆","计算错误"],
  "next_steps": "...",
  "confidence": 0-1
}
若输入缺失，设置 `status: blocked` 并解释原因。
```
- **并行策略**：LangGraph 中 `QuestionGrader` 设为 `map` 节点，消费 `work_items` 队列。

#### 3.1.6 Feedback Composer Agent
- **职责**：汇总单题结果，为学生和教师生成差异化反馈，并给出班级级别的可选摘要。
- **Prompt 模板**：
```
你是 Feedback Composer。
输入：question_results、student_profile、knowledge_tags。
输出两个部分：
- student_report：分数总览、优势、待提升点、建议练习题型。
- teacher_digest：异常题目、群体趋势、建议讲评顺序。
格式：Markdown，关键数据使用表格；同时返回 `json_summary`（结构见附录）。
```

#### 3.1.7 QA Sentinel Agent
- **职责**：审查反馈草稿与原始 Rubric 是否一致，检测异常分数、缺失题目或 JSON schema 错误。
- **Prompt 模板**：
```
你是 QA Sentinel。
任务：
1. 校验所有 question_id 是否覆盖。
2. 检查 earned_score 是否 <= 对应 max_score。
3. 标记低置信度 (<0.6) 的题目并建议复查。
4. 输出 {"status": "pass|revise", "issues": [], "corrected_payload": {...}}
仅在发现错误时修改 payload，并在 issues 内写明原因和修正。
```

#### 3.1.8 Report Weaver Agent
- **职责**：将 QA 通过的结果写入数据库/缓存，生成最终 JSON+富文本+导出任务。
- **Prompt 模板**：
```
你是 Report Weaver。
输入：qa_payload、导出配置、历史任务ID。
输出：
- `final_json`: 满足前端渲染 schema。
- `render_blocks`: Markdown/HTML 片段。
- `persistence_plan`: [{"table":"grading_results","operation":"upsert","payload":{...}}]
- `webhooks`: 需要回调的任务列表。
确保引用 QA 审核后的数据，不自行改分。
```

### 3.2 Prompt 配置与版本管理
- **分层模板**：
  - `base_prompt`：记录在仓库 `ai_correction/prompts/base/*.md`，承载通用步骤与约束。
  - `strategy_patch`：依据 `strategy`（keyword/reasoning/math_step/code_exec）加载差异化补丁，例如加入“展示关键字匹配结果”或“逐步列式计算”。
  - `client_override`：面向大客户/考试局的专属追加提示，通过数据库或环境变量动态注入。
- **版本控制**：
  - 每次 Prompt 改动需在 `PROMPT_CHANGELOG.md`（新增文件，参考 `agent_design_details.md` 格式）记录目的、影响 Agent、回滚方式。
  - 在 LangGraph 节点配置 `prompt_version` 字段，落地到 `GradingState.metadata`，方便回溯测试结果。
- **自动回归**：复用 `test_langgraph.py`，读取最近两版 Prompt，执行 A/B 对比，监控得分波动与 Token 成本，低于阈值时触发 QA Sentinel 强制复查。

---

## 4. LangGraph 实施计划（4 周）
| 周次 | 目标 | 关键产出 | 负责人建议 |
|------|------|----------|------------|
| 第1周 | 完成 Intake Router、Context Synthesizer、Rubric Builder | Python 节点 + Prompt 单元测试 + 假数据集 | 后端工程师 + Prompt 工程师 |
| 第2周 | 实现 Evaluation Coordinator 与 Question Grader 池，接入 LangGraph Runtime | `graph.py` 原型、LLM 适配层、并行配置 | LangGraph 专家 |
| 第3周 | 完成 Feedback Composer、QA Sentinel、Report Weaver，并连通数据库/缓存 | Streamlit 演示、DB Schema、导出适配 | 全栈工程师 |
| 第4周 | 压测 & 优化，编写运维脚本与监控面板 | 负载报告、容错策略、警报规则、部署文档 | DevOps |

### 配套任务
1. **提示词回归测试**：使用 `test_langgraph.py` 模拟 20 份答卷，对比得分波动。
2. **Token 成本控制**：Context Synthesizer 限制平均 1.2k tokens/任务，Rubric Builder 缓存结果。
3. **风险缓解**：
   - LLM API 抖动 → Evaluation Coordinator 设定重试策略。
   - 数据不一致 → QA Sentinel 强制校验。
   - 大文件处理 → Intake Router 分块上传 + 断点续传。

### 4.1 周度任务拆解与验收标准
| 周次 | 任务拆解 | 验收口径 | 依赖/备注 |
|------|----------|----------|-----------|
| 第1周 | (1) 提交 `router.py`, `context_synthesizer.py`, `rubric_builder.py`；(2) Prompt PR 审批；(3) 构建假数据集 `fixtures/week1/*.json` | 单元测试通过率 ≥ 90%，Rubric Schema JSON 校验 100% | 需要 QA 准备 5 套标准答案；DevOps 搭建测试 Redis/PG |
| 第2周 | (1) 交付 `evaluation_coordinator.py` 与 `question_grader_pool.py`；(2) LangGraph Runtime 部署；(3) map 并行压测 | `work_items` 平均排队 < 3s，P95 单题耗时 < 4s | 依赖 LLM 密钥白名单；需要并发监控面板 |
| 第3周 | (1) 上线 Feedback/QA/Report 三节点；(2) 打通数据库写入和 Report API；(3) 前端 Demo 接入 | 端到端任务成功率 ≥ 95%，QA issue rate < 5% | 前端需更新报告展示；DB 需提供 staging 数据 |
| 第4周 | (1) 完成容量/容错压测；(2) 发布运维 runbook；(3) 输出上线评审材料 | 压测报告覆盖 3 档并发，报警/回滚演练完成 | On-call 编排完成值班表；安全组复核密钥管理 |

### 4.2 发布节奏与资源准备
- **环境准备**：提前 3 天在 Dev/Stage/Prod 注入 LangGraph 环境变量，包含 LLM key、Redis、Postgres、对象存储桶名。
- **人力配置**：
  - Prompt Owner（1 人）：负责 Prompt 版本合规与 `PROMPT_CHANGELOG.md` 更新。
  - LangGraph Maintainer（1 人）：维护 `graph.py` 与节点状态。
  - DevOps（1 人）：负责部署脚本、指标/报警接入。
- **工具链**：引入 `pre-commit` hook 验证 JSON schema、`ruff`/`pytest` 组合校验逻辑；使用 `make langgraph-demo` 快速回归样例任务。
- **上线门槛**：需要完成以下清单方可提交变更评审：
  1. `test_langgraph.py` 通过，附上最新运行截图或日志。
  2. Prometheus 仪表有 Intake/QG/QA 3 类指标可视化。
  3. QA Sentinel issue 样本库更新，覆盖最新 2 个 Prompt 版本。

### 4.3 与既有计划（`production_implementation_plan.md`）的协作
- **里程碑对齐**：把原 5 周计划中的 Phase1/2（核心功能、数据库）压缩映射到上述第 1-3 周，将 Phase3/4（前端联调、优化部署）与第 4 周对齐。
- **责任矩阵**：沿用原文档的 RACI 表，新增 LangGraph Owner（负责 Prompt/Graph 质量）和 Prompt Reviewer（审批 Prompt 变更）。
- **验收准则**：上线前需同步满足旧版 KPI（批改准确率 ≥95%）与新 KPI（QA Sentinel issue 率 <2%、Token 成本下降 15%）。

---

## 5. 三套可选的 LangGraph 批改系统模式
| 模式 | 架构特点 | 适用场景 | 优势 | 注意事项 |
|------|----------|----------|------|----------|
| **A. 精准审校模式** | QA Sentinel + 双层 Question Grader（主评分 + 复审） | 高风险考试、需要人工接近一致性 | 准确度最高、可追踪审计 | 成本高、时延较长 |
| **B. 极速批改模式** | 精简为 Intake → Context → Rubric → (并行) Question Grader → Report | 日常作业、批量练习 | 延迟最低、易扩容 | 反馈深度有限，需依赖缓存 |
| **C. 自适应混合模式** | 默认极速流程，低置信度题目自动回流 QA Sentinel + 第二轮 Grader | 标准化考试批改、需要成本/准确度平衡 | 成本与准确度兼顾，可渐进优化 | 需要实现置信度阈值与动态排队 |

### 选型建议
1. **短期上线**：使用 B 模式，确保核心功能跑通。
2. **面向旗舰客户**：升级为 C 模式，引入置信度回流，QA Sentinel 只处理有风险的题目。
3. **考试院/高校合作**：采用 A 模式，并将 QA Sentinel 的结果入库，支持人工抽检。

---

## 6. 与 `ai_correction` 现有代码的集成要点
- `functions/` 目录新增 `langgraph_pipeline.py`，封装 LangGraph 构建与执行。
- `config.py` 添加 LLM、Redis、数据库等配置项，支持多环境切换。
- `run_test_and_save.py` 扩展为可选择不同模式（A/B/C）并导出性能指标。
- `streamlit_simple.py` 调用 Report Weaver 的 `final_json`，原前端无需大改。
- `test_langgraph_performance.py` 增加对 QA Sentinel 的断言，保证题目覆盖。

---

## 7. 附录：JSON Schema 片段
```json
{
  "question_result": {
    "question_id": "Q1",
    "earned_score": 8,
    "max_score": 10,
    "score_breakdown": [
      {"sub_id": "Q1-1", "score": 4, "reason": "定义正确"},
      {"sub_id": "Q1-2", "score": 4, "reason": "推导完整"}
    ],
    "error_tags": ["符号错误"],
    "next_steps": "复习导数定义",
    "confidence": 0.78
  },
  "student_report": {
    "total_score": 86,
    "max_score": 100,
    "strengths": ["解题思路清晰"],
    "improvements": ["计算细节需校对"],
    "recommended_topics": ["三角恒等变形"]
  }
}
```

---

## 8. 统一验收与监控指标
| 维度 | 指标 | 目标值 | 数据来源 | 备注 |
|------|------|--------|----------|------|
| 准确度 | `score_match_rate`（与人工抽检一致率） | ≥ 95% | QA Sentinel + 抽检脚本 | 与 `DESIGN_SUMMARY.md` 定义保持一致。 |
| 质量 | `qa_issue_rate`（QA Sentinel issue / 试卷） | < 2% | LangGraph 运行日志 | 超阈值触发自动回流模式 A。 |
| 成本 | 平均 Token / 试卷 | ≤ 1.2k（Context），≤ 3.8k（全流程） | OpenAI 账单/自建计费器 | 若超过，触发 Prompt 精简任务。 |
| 性能 | 95 分位延迟 | 极速模式 < 90s，自适应 < 150s | `monitoring/latency_dashboard` | 结合 `production_system_architecture.md` 的流式监控。 |
| 可观测性 | `prompt_version` 追踪覆盖率 | 100% | `GradingState.metadata` | 缺失时拒绝上线。 |

- **报警策略**：
  - `qa_issue_rate` 连续 2 天 > 3% → 自动切换至精准模式，并通知 On-call。
  - Token 成本环比 +20% → 触发 Prompt 复盘会，检查 `PROMPT_CHANGELOG.md` 是否缺漏。
  - 延迟超标 → 优先排查 Evaluation Coordinator 的批次设置或 Question Grader 池大小。

- **复盘节奏**：
  - 周会：回顾指标、调整 Prompt 版本。
  - 月度：结合 `production_implementation_plan.md` 里的 KPI，更新 roadmap。
  - 项目结束：沉淀在 `EXECUTIVE_SUMMARY.md`，方便对外汇报。
