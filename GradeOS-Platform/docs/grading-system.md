# GradeOS 批改系统：技术与流程说明

> 目标：不是“判定对/错（0/1）”，而是“理解评分标准 → 逐条对齐评分点 → 证据与得分绑定”。  
> 也就是说：系统先理解 rubric，再判断每个评分点是否满足并给出证据，最后由评分点汇总总分。

---

## 1. 核心设计原则（避免二元化）

1) **评分点驱动（point-first）**  
每道题都被拆成多个评分点（Scoring Points），每个评分点有分值、必要性和描述。  
系统输出 `scoring_point_results`，每一条包含：
- `point_id` / `description`
- `awarded` / `max_points`
- `evidence`（原文证据或图像证据）
- `decision`（得分 / 未得分）

2) **总分由评分点汇总**  
总分不依赖 `is_correct`，而是严格等于评分点得分之和。  
即使学生解法是变体或另类解法，只要满足评分点或替代评分条件，也会得分。

3) **证据必填**  
每个评分点必须给出证据引用；证据不足时必须标记不确定或不给分。

4) **另类解法支持**  
若 rubric 提供 `alternative_solutions`，模型会检测并匹配另类解法，按其评分条件计分。

---

## 2. 评分标准（Rubric）结构

评分标准由解析器从 PDF 中抽取并结构化，核心字段：

- `questions[]`
  - `question_id`
  - `max_score`
  - `question_text`
  - `standard_answer`
  - `scoring_points[]`
    - `point_id`
    - `description`
    - `score`
    - `is_required`
  - `alternative_solutions[]`（可选）
    - `description`
    - `scoring_criteria`
    - `max_score`

> 要点：每道题的 `max_score` 必须等于评分点之和或 rubric 指定总分。

---

## 3. 批改流程总览

1) **文件接收 / 预处理**
   - 接收标准答案 PDF + 学生作答 PDF。
   - 图像转码、统一格式（JPEG）、保序。

2) **评分标准解析（Rubric Parse）**
   - 对标准答案做分批解析（单次 LLM 调用有图片上限）。
   - 输出评分点列表、标准答案、可能的另类解法。
   - 生成 `rubric_context`，供后续批改使用。

3) **学生分割 / 索引（Index & Segment）**
   - 识别每页题号和学生边界，必要时人工校正。
   - 生成 `page_index_contexts`，为 LLM 提供页码与题号提示。

4) **批改（Batch Grading）**
   - 以学生为单位进行批改。
   - 每名学生的所有页面 + rubric 一次性提交给模型。
   - 模型输出：
     - 每题 `score / max_score`
     - `scoring_point_results[]`
     - `student_answer` 原文摘录
     - `source_pages` 页码引用

5) **跨页合并（Cross-Page Merge）**
   - 若同一题跨页作答，合并评分点与证据。
   - 统一汇总后重新计算该题总分。

6) **逻辑复核（Logic Review）**
   - 使用 “自白 / 逻辑审计” 审查评分合理性。
   - 若评分点证据不足或评分不一致，触发重评或标记人工复核。

7) **导出与分析**
   - 最终输出学生结果、评分点证据、统计报告。
   - 支持导出到班级系统并绑定学生。

---

## 4. “评分点驱动”如何执行

### 4.1 评分点结果结构（核心）

```json
{
  "question_id": "1",
  "score": 8,
  "max_score": 10,
  "student_answer": "学生原文...",
  "scoring_point_results": [
    {
      "point_id": "1.1",
      "description": "列出正确方程",
      "max_points": 3,
      "awarded": 3,
      "evidence": "【原文引用】x + y = 10",
      "decision": "得分"
    },
    {
      "point_id": "1.2",
      "description": "计算无误",
      "max_points": 7,
      "awarded": 5,
      "evidence": "【原文引用】...步骤中有误差",
      "decision": "部分得分"
    }
  ]
}
```

### 4.2 得分规则

- **题目总分 = 评分点 awarded 之和**
- **总分 = 所有题目的分数之和**
- `is_correct` 仅用于展示，不参与评分。

---

## 5. 另类解法支持策略

当 rubric 中出现 `alternative_solutions` 时：

1) 先检测学生是否采用另类解法  
2) 若满足另类解法评分条件，使用其评分上限与条件评分  
3) 如果满足部分条件，也允许给部分分  

这样可以覆盖：  
- 同解法不同变形  
- 等价推导路径  
- 教师认可但不是标准答案的策略  

---

## 6. 证据绑定与不确定性处理

评分点输出要求：

- `evidence` 必须来自学生原文，不得臆造  
- 若无法确定，必须输出 `awarded=0` 并注明“不确定/未找到证据”
- 自白模块会记录“不确定但未披露”的违规情况

---

## 7. 复核与纠错

系统支持“逻辑复核 + 自白”：

1) **自白输出**  
   - compliance_analysis（逐目标合规）  
   - uncertainties_and_conflicts（不确定项）  
   - overall_compliance_grade（1-7，≤3 视为失败）

2) **推理时干预**  
   - 若评分点缺失或证据不足，可触发重评  
   - 若仍不确定，进入人工复核  

---

## 8. 为什么不是 0/1？

传统做法是：
> 学生答案 == 标准答案 → 得分  
> 否则 → 0 分  

这种方式会错杀：
- 合理的等价变形  
- 另类解法  
- 部分正确的步骤  

GradeOS 的设计是：
> 先理解评分标准  
> 再逐点对照  
> 最后汇总得分  

这样才符合真实考试评分逻辑。

---

## 9. 总结

GradeOS 以“评分点驱动 + 证据绑定 + 另类解法支持”为核心。  
它不是一个“答对/答错”的判别器，而是一个“评分规则执行器”。  

这正是你提出的关键问题：  
**评分应该基于对 rubric 的理解与逐点匹配，而不是对答案做二元判断。**  
