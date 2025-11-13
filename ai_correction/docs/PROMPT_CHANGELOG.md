# Prompt 变更日志（示例）

> 用于记录 LangGraph 批改系统所有 Prompt 的改动原因、影响范围与回滚策略。提交新的 Prompt 前，请复制“模版”并追加到顶部。

## 2024-XX-XX - 模板示例
- **涉及 Agent**：Question Grader（strategy=reasoning）、QA Sentinel
- **变更说明**：强化“逐步复查公式”指令，要求输出额外的 `formula_trace` 字段。
- **触发原因**：模拟考试出现多起符号抄写错误未捕获。
- **影响面**：平均 Token +4%，高年级理科班；预计准确率 +2%。
- **监控指标**：`score_drift <= ±0.5`、`confidence_low_ratio < 10%`。
- **回滚策略**：若 24 小时内 QA Sentinel issue > 5，则恢复到 `prompt_version=v20240301`。

---

## 2024-03-01 - v20240301（历史记录示例）
- **涉及 Agent**：Rubric Builder
- **变更说明**：补充示例答案字段 `exemplar_answers`，覆盖 80% 常见题型。
- **监控指标**：`rubric_parse_error` 必须 <= 1% 。
- **状态**：已上线，无需回滚。
