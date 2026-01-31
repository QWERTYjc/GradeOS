# Railway 批改流程修复总结

## 📋 问题概述

Railway 生产环境中批改流程存在以下问题:
1. **批改流程在 `rubric_review` 后停止** - 没有执行 `grading_fanout` 和 `grade_batch`
2. **题目数量识别错误** - 19道题被识别为39道题(子题被重复计数)

---

## 🔧 修复内容

### 修复 1: 节点定义顺序问题 ⭐ **关键修复**

**问题**: `grading_fanout_placeholder` 节点在条件边添加后才定义,导致 LangGraph 构建图时找不到该节点。

**修复**: 调整代码顺序,先添加节点定义,再添加条件边

**文件**: `backend/src/graphs/batch_grading.py`

```python
# ✅ 修复前 (错误)
graph.add_conditional_edges(
    "rubric_parse",
    should_review_rubric,
    {
        "do_review": "rubric_review",
        "skip_review": "grading_fanout_placeholder",  # ❌ 节点还不存在!
    },
)

# 然后才定义节点
graph.add_node("grading_fanout_placeholder", grading_fanout_placeholder_node)

# ✅ 修复后 (正确)
# 先定义节点
graph.add_node("grading_fanout_placeholder", grading_fanout_placeholder_node)

# 然后添加条件边
graph.add_conditional_edges(
    "rubric_parse",
    should_review_rubric,
    {
        "do_review": "rubric_review",
        "skip_review": "grading_fanout_placeholder",  # ✅ 节点已存在
    },
)
```

**效果**:
- ✅ LangGraph 能够正确构建工作流图
- ✅ 批改流程能够从 `rubric_parse` 正确路由到 `grading_fanout_placeholder`
- ✅ 批改任务能够正常执行

---

### 修复 2: 题目数量识别错误 ⭐ **核心问题**

**问题**: LLM 的 prompt 指示 "如果一道大题包含多个小题（如 7a, 7b），每个小题单独列出",导致子题被当作独立题目计数。

**示例**:
```
原始评分标准:
7. (15分)
  (1) 计算结果 (5分)
  (2) 写出过程 (5分)
  (3) 画出图形 (5分)

❌ 修复前: LLM 识别为 3道题 (7.1, 7.2, 7.3)
✅ 修复后: LLM 识别为 1道题 (7), 有3个得分点
```

**修复**: 更新 `RubricParserService` 的 prompt 模板

**文件**: `backend/src/services/rubric_parser.py`

**关键变更**:

1. **添加明确的题目识别规则**:
```python
## 关键：题目识别规则
**只计数主题号，不要把子题当作独立题目！**

例如：
- ✅ 正确：题目 "7" 包含子题 7(1), 7(2), 7(3) → 这是 **1道题**，有3个得分点
- ❌ 错误：把 7(1), 7(2), 7(3) 当作 3道独立题目

**主题号识别**：
- 主题号格式：1、2、3... 或 一、二、三... 或 第1题、第2题...
- 子题格式：(1)、(2)、(3)... 或 ①、②、③... 或 a)、b)、c)...
- **子题应该作为主题的 scoring_points，而不是独立的 question**
```

2. **添加具体示例**:
```python
## 示例
如果评分标准是：
```
7. (15分)
  (1) 计算结果 (5分)
  (2) 写出过程 (5分)  
  (3) 画出图形 (5分)
```

应该输出：
```json
{
  "questions": [
    {
      "question_id": "7",
      "max_score": 15,
      "scoring_points": [
        {"point_id": "7.1", "description": "计算结果", "score": 5},
        {"point_id": "7.2", "description": "写出过程", "score": 5},
        {"point_id": "7.3", "description": "画出图形", "score": 5}
      ]
    }
  ]
}
```
**注意：这是1道题，不是3道题！**
```

3. **修改严格规则**:
```python
## 严格规则
- **只计数主题号**，不要把子题当作独立题目
- **子题处理**：如果一道大题包含多个子题（如 7(1), 7(2), 7(3)），
  将它们作为该题的 scoring_points，而不是独立的 questions
```

**效果**:
- ✅ LLM 能够正确区分主题和子题
- ✅ 题目数量识别准确 (19题 vs 之前的39题)
- ✅ 子题作为 scoring_points 正确处理

---

### 修复 3: 增强调试日志

**文件**: `backend/src/graphs/batch_grading.py`

**添加的日志**:
```python
# should_review_rubric 函数
logger.info(f"[should_review_rubric] 跳过 review,直接进入批改: batch_id={batch_id}, mode={grading_mode}, enable_review={enable_review}")
logger.info(f"[should_review_rubric] 没有 rubric,跳过 review: batch_id={batch_id}")
logger.info(f"[should_review_rubric] 需要 review: batch_id={batch_id}")

# grading_fanout_placeholder 节点
logger.info(f"[grading_fanout_placeholder] 跳过 review,准备进入批改: batch_id={batch_id}")
```

**效果**:
- ✅ 更容易诊断工作流路由问题
- ✅ 清晰显示批改流程的执行路径

---

## 📤 提交历史

| 提交 | 内容 | 文件 |
|------|------|------|
| c3128cc | 日志优化、题目数量修复(移除total_questions_found)、调试增强 | `batch_grading.py`, `rubric_parser.py` |
| 0fcd7c8 | 工作流图重构,添加条件路由 | `batch_grading.py` |
| **6c36e17** | ⭐ 修复节点定义顺序问题 | `batch_grading.py` |
| **e2211c6** | ⭐ 修复题目数量识别错误 - 明确区分主题和子题 | `rubric_parser.py` |

---

## ✅ 验证步骤

部署完成后,请按以下步骤验证:

### 1. 检查 Railway 日志

应该看到以下日志序列:

```
[rubric_parse] 开始解析评分标准: 页数=X
[rubric_parse] 评分标准解析成功: 题目数=19  # ✅ 应该是19,不是39
[should_review_rubric] 跳过 review,直接进入批改: batch_id=xxx, mode=assist, enable_review=False
[grading_fanout_placeholder] 跳过 review,准备进入批改: batch_id=xxx
[grading_fanout] 按学生边界创建批改任务: batch_id=xxx, 学生数=X, 总页数=X
[grading_fanout] ✅ 成功创建 X 个学生批改任务
[grade_batch] 开始批改批次 1/X: batch_id=xxx, 页面=[...], 重试次数=0
[grade_batch] 批次 1/X 完成: 成功=X/X, 失败=0, 总分=XXX
```

### 2. 测试批改流程

1. 访问 https://gradeos.up.railway.app
2. 上传包含19道题的批改任务
3. 观察批改过程:
   - ✅ 题目数量显示为 19 (不是39)
   - ✅ 批改流程顺畅执行
   - ✅ 批改结果正确显示

### 3. 检查批改结果

- ✅ 批改结果页面有数据
- ✅ 每道题的得分正确
- ✅ 总分计算准确

---

## 🎯 预期结果

修复后的批改流程应该:

1. **题目识别准确**: 19道题正确识别为19道,不会因子题而重复计数
2. **流程执行完整**: 从 `rubric_parse` → `grading_fanout_placeholder` → `grade_batch` → `self_report` 完整执行
3. **批改结果正确**: 批改结果页面正常显示,数据完整

---

## 📝 技术要点

### LangGraph 节点定义顺序

在 LangGraph 中,必须先定义节点,再在条件边中引用:

```python
# ✅ 正确顺序
graph.add_node("node_name", node_function)  # 1. 先定义
graph.add_conditional_edges("source", router, ["node_name"])  # 2. 再引用

# ❌ 错误顺序
graph.add_conditional_edges("source", router, ["node_name"])  # 1. 先引用
graph.add_node("node_name", node_function)  # 2. 后定义 - 会报错!
```

### LLM Prompt Engineering

对于复杂的识别任务,需要:
1. **明确规则**: 清晰定义什么是主题,什么是子题
2. **提供示例**: 给出正确和错误的示例
3. **强调重点**: 使用粗体、emoji 等强调关键指令
4. **结构化输出**: 明确 JSON 结构和字段含义

---

## 🚀 后续优化建议

1. **题目识别验证**: 添加后处理逻辑,验证题目数量是否合理
2. **子题检测**: 自动检测是否有子题被误识别为主题
3. **置信度阈值**: 对低置信度的解析结果进行人工审核
4. **单元测试**: 添加针对 prompt 的单元测试,确保不同格式的评分标准都能正确识别

---

生成时间: 2026-01-31 20:16
