# LangGraph 批改系统完整设计（含提示词与实施方案）

## 1. 文档目标
- 给出一份覆盖 **LangGraph 节点结构、Agent 交互、提示词模版、数据流** 的完整蓝图。
- 定义如何把设计集成进 `ai_correction` 目录，便于工程落地。
- 提供 **实施计划** 与 **多种架构选项**，帮助团队挑选合适的批改系统模式。

---

## 2. 业务背景 & 设计约束
| 维度 | 要点 |
| --- | --- |
| 用户目标 | 上传题目 & 学生答案 → 获得客观分数与可执行反馈，支持课堂即时批改。 |
| 题型范围 | 选择题、填空题、解答题、主观题（可扩展到编程题/多步推导）。 |
| 质量诉求 | - 对齐教案、权重、容错；<br>- 反馈可直接发给学生；<br>- 支持 AI 与人工复核并存。 |
| 技术栈 | LangGraph + OpenAI/Anthropic 系列模型，配合已有 `ai_correction` Python 服务。 |
| 运维约束 | 需支持离线批量、实时单次以及生产监控（日志、评分分布、异常样本）。 |

---

## 3. LangGraph 节点拓扑概览
```
         ┌──────────────┐        ┌──────────────────┐
 Upload ─▶ InputIntake  ├─data──▶ RubricCompiler    │
         └─────┬────────┘        └───────┬──────────┘
               │                         │
               │meta                     │rubric
               ▼                         ▼
        ┌──────────────┐        ┌──────────────────┐
        │ Response      │ norm  │ AutoGrader        │
        │ Normalizer    ├──────▶│ (Reason+Score)    │
        └─────┬────────┘        └───────┬──────────┘
              │                         │scores
              │features                 ▼
              ▼                   ┌──────────────┐
        ┌──────────────┐          │ Feedback     │
        │ Evidence      │context  │ Generator    │
        │ Collector     ├────────▶│ + Coach      │
        └─────┬────────┘          └───────┬──────┘
              │                         │report
              ▼                         ▼
        ┌──────────────┐        ┌──────────────────┐
        │ Consistency  │──────▶ │ ReportAssembler   │
        │ Auditor      │alerts  │ + API Adapter     │
        └──────────────┘        └──────────────────┘
```
- **边**：均为 LangGraph 中的 `State` 更新，关键字段：`questions`, `responses`, `rubric`, `scores`, `feedback`, `alerts`。
- **失败分支**：任一 Agent 抛出异常 → `Fallback Router`（可选）执行兜底，如退化为模板评分或请求人工。此处可借助 LangGraph `ConditionNode`。

---

## 4. Agent 级完整设计（含提示词）

### 4.1 InputIntake Agent
| 项目 | 说明 |
| --- | --- |
| 职责 | 解析上传文件，抽取题目、标准答案、评分规则、学生信息。 |
| 输入 | `files`, `metadata`（来源、课程、年级），`user_overrides`。 |
| 输出 | 结构化 `questions`, `canonical_answers`, `student_profile`。 |
| 工具 | Python 解析函数、正则、OCR（可选）。 |
| 关键提示词 | 见下方 Prompt。 |

**Prompt 模板**
```text
你是 InputIntake Agent。任务：
1. 阅读提供的题目/答案文本。
2. 解析出题号、题干、题型、分值、标准答案，必要时推断题型。
3. 如果文档中给出评分细则或权重，转换成结构化字段。
4. 严格使用 JSON 返回：{"questions": [...], "rubric": [...], "warnings": [...]}。
如遇不支持的格式，要写入 warnings 并尽可能提取可识别内容。
```

### 4.2 RubricCompiler Agent
| 项目 | 说明 |
| --- | --- |
| 职责 | 将标准答案与课程大纲合成评分 Rubric，补全容错规则。 |
| 输入 | `questions`, `canonical_answers`, `teacher_config`。 |
| 输出 | `rubric`（包含评分项、容错、分值、典型错误）。 |
| 工具 | 课程知识库（向量库检索），Rubric 模板库。 |
| 提示词 |
```text
你是 RubricCompiler Agent，需要将题目与标准答案映射为评分规约。
- 对每题生成 rubric_items：{"criterion", "ideal_answer", "misconceptions", "score", "tolerance"}。
- 若 teacher_config 给出权重、术语或知识点顺序，务必保留。
- 输出 JSON，并在 extra_notes 中记录需人工确认的部分。
```

### 4.3 ResponseNormalizer Agent
| 项目 | 说明 |
| --- | --- |
| 职责 | 清洗学生答案：纠正 OCR 错误、统一单位、拆分多解题步骤。 |
| 输入 | `student_raw_answers`, `questions`, `rubric`. |
| 输出 | `normalized_responses`（含 tokens、步骤、推断语言）。 |
| 工具 | 词法纠错、单位换算、语言检测。 |
| 提示词 |
```text
以审稿人身份重写学生答案：
1. 保留原始意思，不得改变结论。
2. 如果答案包含多个思路，拆分为 steps 列表，并记录 evidence（引用原句）。
3. 标记语言、单位、是否存在空白。
输出 JSON: {"responses": [{"question_id", "steps", "language", "flags"}]}。
```

### 4.4 EvidenceCollector Agent
| 职责 | 根据 Rubric 自动搜集教材/知识库佐证，用于判分 & 解释。
| 输入 | `questions`, `rubric`, `normalized_responses`。
| 输出 | `evidence_bundle`（知识点、出处、引用片段）。
| 提示词 |
```text
请为每题匹配 1-3 条知识点引用：
- 来源于提供的知识库片段（如为空则返回 "source": "N/A"）。
- 解释为何该知识与评分标准相关。
- 结果需包含 citation_id，方便反馈引用。
```

### 4.5 AutoGrader Agent（Reasoner + Scorer）
| 职责 | 逐题推理 → 打分 → 生成得分解释。
| 输入 | `normalized_responses`, `rubric`, `evidence_bundle`。
| 输出 | `scores`（含过程 reasoning、得分、置信度、扣分原因）。
| 工具 | 可调用数学求解、代码执行、策略评估函数。
| 提示词 |
```text
你是 AutoGrader。
流程：
1. 使用 Chain-of-Thought（隐藏）判断学生答案是否满足 rubric。
2. 列出匹配/不匹配点，引用 evidence_bundle 的 citation_id。
3. 给出 0-分值 的得分，并评估置信度（high/medium/low）。
输出 JSON: {"question_id", "score_awarded", "max_score", "reasoning", "confidence", "citations"}。
```

### 4.6 FeedbackCoach Agent
| 职责 | 把评分结果转换成学生可理解的反馈 & 下一步建议。
| 输入 | `scores`, `normalized_responses`, `rubric`。
| 输出 | `student_feedback`（表扬、问题、提升建议、练习链接）。
| 提示词 |
```text
角色：学生辅导老师。
- 针对每题列出 “得分原因 + 改进建议”。
- 保持鼓励语气，使用二级标题 + bullet。
- 如果 confidence = low，提示需要老师复核。
- 支持多语言输出，默认使用学生答题语言，否则 fallback 中文。
```

### 4.7 ConsistencyAuditor Agent
| 职责 | 横向检查分数是否异常，是否存在 rubric 不一致或模型自相矛盾。
| 输入 | `scores`, `questions`, `rubric`, `normalized_responses`。
| 输出 | `alerts`（如：疑似漏判、超时、异常高分）。
| 提示词 |
```text
对每题执行校验：
- 如果 reasoning 与得分矛盾（如扣分但给满分）→ raise alert。
- 如果多题答案完全相同却得分差距 > 30% → raise alert。
- 输出 alerts: {"severity", "question_id", "message", "action"}。
```

### 4.8 ReportAssembler Agent + API Adapter
| 职责 | 整合所有信息，生成对老师 & 系统友好的输出，推送至现有 API。
| 输入 | 全局 `state`（scores, feedback, alerts, student_profile）。
| 输出 | `final_report`（JSON + Markdown），并返回 `api_payload`。
| 提示词 |
```text
以产品运营视角生成总结：
1. 统计分数、正确率、易错点排名。
2. 合并 FeedbackCoach 内容，按题型分组。
3. 若存在 alerts，放在报告开头，并指明建议操作。
4. 输出 {"summary_md", "teacher_brief", "api_payload"}。
```

### 4.9 Fallback Router（可选）
- 依据 `alerts` 或 Agent 报错自动触发：
  - 退化为关键字匹配评分。
  - 或创建人工复核任务（写入任务队列）。

---

## 5. 状态管理与 LangGraph 实现要点
1. **State Schema** 建议定义在 `ai_correction/config.py` 或新建 `state_schema.py`，包含：
   ```python
   class CorrectionState(TypedDict):
       questions: List[Question]
       rubric: List[RubricItem]
       normalized_responses: List[Response]
       evidence_bundle: List[Evidence]
       scores: List[Score]
       student_feedback: Dict
       alerts: List[Alert]
       final_report: Dict
   ```
2. **Graph 构建**：
   ```python
   from langgraph.graph import StateGraph

   builder = StateGraph(CorrectionState)
   builder.add_node("input", input_agent)
   ...
   builder.add_edge("input", "rubric")
   builder.add_conditional_edges("autograder", route_on_failure, {"ok": "feedback", "retry": "input"})
   graph = builder.compile()
   ```
3. **持久化**：利用 LangGraph `MemorySaver` 保存中间状态，便于回溯。
4. **评测**：复用 `ai_correction/run_test_and_save.py`，新增 `--graph` 选项调用 LangGraph 执行。

---

## 6. 实施计划（建议 3 Sprint）
| Sprint | 时间 | 主要交付 | 关键任务 |
| --- | --- | --- | --- |
| Sprint 1 | Week 1-2 | 完成 State Schema + Input/Rubric/Normalizer Agent | - 梳理题目/答案数据结构；<br>- 接入文件解析 & Teacher 配置；<br>- 编写 Prompt、单测；<br>- LangGraph 基础编译。 |
| Sprint 2 | Week 3-4 | AutoGrader + Feedback + Evidence | - 引入 Reasoning 模型、工具调用；<br>- 构建知识库检索层；<br>- 设计评分可视化；<br>- 自动化评测 200 题对比人工分。 |
| Sprint 3 | Week 5-6 | Auditor + Report + 生产接入 | - 完成 Consistency & 报警；<br>- 对接现有 API / 数据库；<br>- 部署监控（latency、token）；<br>- 编写操作手册与回滚方案。 |

补充：若需更快上线，可按 “核心评分链（Input→Rubric→AutoGrader）” 与 “增值能力（Evidence/Feedback/Auditor）” 分两条流水线并行实现。

---

## 7. LangGraph 批改系统模式选项
| 方案 | 适用场景 | 架构差异 | 优点 | 风险/代价 |
| --- | --- | --- | --- | --- |
| **Option A · 精简评分链** | 小班课、题量少、实时互动 | 仅保留 Input → Rubric → AutoGrader → Feedback；Auditor 只做基础校验。 | 延迟最低，易维护。 | 对 Rubric & 数据质量要求高，缺少证据支撑。 |
| **Option B · 证据增强链** | 需要可解释性、需引用教材 | 在 Option A 基础上加入 EvidenceCollector、ReportAssembler 富文本。 | 反馈说服力强，方便老师审核。 | 需要维护知识库 & 引用准确性。 |
| **Option C · 审核闭环链** | 大规模考试、对公平性要求高 | Option B + ConsistencyAuditor + Fallback Router + 人工任务流。 | 容错最高，可监控偏差并触发人工复核。 | 延迟增加，Graph 复杂度高，需要额外运维。 |

**选择建议**
1. MVP 阶段→ Option A，先跑通核心链路。
2. 若老师反馈 “需要依据/引用”→ 迭代到 Option B。
3. 上线正式考试或需要审计→ 升级到 Option C，并加入日志治理、模型 A/B 对比。

---

## 8. 下一步行动清单
1. 在 `ai_correction/docs` 增加此文档并同步给产品/研发（本次已完成）。
2. 在代码中创建 `CorrectionState`、`agent_registry.py`，将上述 Prompt 以 `PromptTemplate` 形式固化。
3. 为每个 Agent 写独立单测，覆盖：输入缺失、格式异常、模型响应超时等。
4. 结合 `LANGGRAPH_INTEGRATION_GUIDE.md` 里现有脚本，扩充部署/监控章节。
5. 在 README 中更新：如何选择 Option A/B/C，如何启用 Auditor。
