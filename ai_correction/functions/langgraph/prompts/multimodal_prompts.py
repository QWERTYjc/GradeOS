#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多模态批改系统 Prompt 模板
设计原则：
1. 支持文本和Vision两种模态
2. 明确基于标准评分，而非题目对比
3. 结构化输出格式
"""

# ==================== 题目理解 Prompt ====================

QUESTION_UNDERSTANDING_TEXT_PROMPT = """你是一位资深教育专家，擅长理解和分析题目要求。

【任务】
请仔细阅读以下题目，提取关键信息和要求。

【题目内容】
{question_content}

【输出要求】
请以JSON格式输出题目理解结果，包含以下字段：
{{
  "question_id": "题目唯一标识（如Q1）",
  "question_text": "题目文本内容",
  "key_requirements": ["要求1", "要求2", ...],
  "context": {{
    "subject": "学科（如数学、物理等）",
    "difficulty_level": "难度级别（easy/medium/hard）",
    "question_type": "题型（计算题/论述题/分析题等）"
  }},
  "modality_source": "text"
}}

【注意事项】
1. 提取题目的核心要求，而非答案
2. 识别题目涉及的关键概念和知识点
3. 确保理解准确，为后续批改提供上下文
"""

QUESTION_UNDERSTANDING_VISION_PROMPT = """你是一位资深教育专家，擅长理解和分析题目要求。

【任务】
请仔细查看图片中的题目，提取关键信息和要求。

【输出要求】
请以JSON格式输出题目理解结果，包含以下字段：
{{
  "question_id": "题目唯一标识（如Q1）",
  "question_text": "图片中的题目文本内容（完整提取）",
  "key_requirements": ["要求1", "要求2", ...],
  "context": {{
    "subject": "学科（如数学、物理等）",
    "difficulty_level": "难度级别（easy/medium/hard）",
    "question_type": "题型（计算题/论述题/分析题等）"
  }},
  "modality_source": "vision"
}}

【注意事项】
1. 准确识别图片中的所有文字和符号
2. 保留题目的格式和结构
3. 提取题目的核心要求，而非答案
4. 识别题目涉及的关键概念和知识点
"""

# ==================== 答案理解 Prompt ====================

ANSWER_UNDERSTANDING_TEXT_PROMPT = """你是一位资深教育专家，擅长理解和分析学生答案。

【任务】
请仔细阅读以下学生答案，提取关键信息和答题要点。

【学生答案】
{answer_content}

【输出要求】
请以JSON格式输出答案理解结果，包含以下字段：
{{
  "answer_id": "答案唯一标识",
  "answer_text": "答案文本内容",
  "key_points": ["要点1", "要点2", ...],
  "structure": {{
    "has_steps": true/false,
    "has_conclusion": true/false,
    "is_complete": true/false,
    "organization": "答案组织方式描述"
  }},
  "completeness": "完整性评估（complete/partial/incomplete）",
  "modality_source": "text"
}}

【注意事项】
1. 客观提取答案内容，不进行评分
2. 识别答案的结构和组织方式
3. 记录关键答题点，为评分提供依据
"""

ANSWER_UNDERSTANDING_VISION_PROMPT = """你是一位资深教育专家，擅长理解和分析学生答案。

【任务】
请仔细查看图片中的学生答案，提取关键信息和答题要点。

【输出要求】
请以JSON格式输出答案理解结果，包含以下字段：
{{
  "answer_id": "答案唯一标识",
  "answer_text": "图片中的答案文本内容（完整提取）",
  "key_points": ["要点1", "要点2", ...],
  "structure": {{
    "has_steps": true/false,
    "has_conclusion": true/false,
    "is_complete": true/false,
    "organization": "答案组织方式描述"
  }},
  "completeness": "完整性评估（complete/partial/incomplete）",
  "modality_source": "vision"
}}

【注意事项】
1. 准确识别图片中的所有文字、公式和符号
2. 保留答案的格式和结构
3. 客观提取答案内容，不进行评分
4. 识别答案的结构和组织方式
"""

# ==================== 评分标准解析 Prompt ====================

RUBRIC_INTERPRETATION_PROMPT = """你是一位资深教育专家，擅长解析和理解评分标准。

【任务】
请仔细解析以下评分标准，提取每个评分点的具体要求和分值。**极其重要：必须解析所有题目，不能遗漏任何一道题！**

**关键要求（必须严格遵守）：**
1. **必须识别所有题目编号**：仔细检查评分标准文本，找出所有题目编号（如Q1, Q2, Q3, ..., Q17, Q18, Q19等）
   - 如果评分标准包含19道题，必须全部识别并解析
   - 题目编号格式可能是：Q1, Q2, 题目1, 题目2, Question 1, Question 2, 1., 2. 等
   - **每个评分点的question_id字段必须填写正确的题目编号（如"Q1", "Q2"等），不能填写"UNKNOWN"或空值**
2. **必须提取每道题的所有评分点**，包括主要得分点和步骤得分点
3. 详细说明每个得分点的要求、标准答案、得分条件
4. 识别是否存在多种解法
5. **确保不遗漏任何评分点，特别是前面的题目（Q1-Q16）**
6. 如果评分标准很长，请仔细阅读完整内容，不要只解析后面的题目
7. **criterion_id格式**：必须使用"题目编号_评分点编号"格式，如"Q1_C1", "Q2_C1", "Q17_C1"等

【评分标准】
{rubric_content}

【输出要求】
请以JSON格式输出评分标准理解结果，包含以下字段：
{{
  "rubric_id": "标准唯一标识",
  "total_points": 总分（数字）,
  "criteria": [
    {{
      "criterion_id": "C1" 或 "Q1_C1"（如果是第1题的评分点）,
      "question_id": "Q1"（题目编号，必填）,
      "description": "评分点描述（详细说明评分要求）",
      "detailed_requirements": "详细要求（具体说明需要什么才能得分）",
      "points": 分值（数字）,
      "standard_answer": "标准答案或标准步骤（如果有）",
      "evaluation_method": "评估方法（exact_match/semantic/calculation/step_check等）",
      "scoring_criteria": {{
        "full_credit": "满分条件（什么情况下得满分）",
        "partial_credit": "部分分条件（什么情况下得部分分）",
        "no_credit": "不得分条件（什么情况下不得分）"
      }},
      "alternative_methods": ["另类解法1", "另类解法2", ...],
      "keywords": ["关键词1", "关键词2", ...],
      "required_elements": ["必需元素1", "必需元素2", ...],
      "common_mistakes": ["常见错误1", "常见错误2", ...]
    }},
    ...
  ],
  "grading_rules": {{
    "partial_credit": "是否允许部分分（yes/no）",
    "deduction_rules": ["扣分规则1", "扣分规则2", ...],
    "step_scoring": "是否按步骤给分（yes/no）"
  }},
  "strictness_guidance": "严格程度指导"
}}

【注意事项】
1. **重要**：必须提取所有题目和所有评分点，包括主要得分点和步骤得分点
2. **详细要求**：每个评分点都要说明：
   - 具体要考察什么知识点或能力
   - 标准答案是什么（如果有）
   - 得满分需要满足什么条件
   - 得部分分需要满足什么条件
   - 是否接受其他解法
3. **另类解法**：如果标准中提到或者根据题目性质可以推断出存在多种解法，请列出
4. **常见错误**：如果标准中提到或可以预见的常见错误，请列出
5. 如果评分标准包含多道题，每道题的评分点都要单独列出
6. 准确提取每个评分点的分值
7. 确保所有评分点的分值之和等于总分

【示例】
如果评分标准是：
题目1（10分）：计算 (a²)³ × a⁴ ÷ a⁵
- 正确应用指数运算法则（5分）：a⁶ × a⁴ = a¹⁰
- 正确化简最终答案（3分）：a¹⁰ ÷ a⁵ = a⁵
- 答案格式规范（2分）：使用正指数表示

应该输出：
{{
  "rubric_id": "R1",
  "total_points": 10,
  "criteria": [
    {{
      "criterion_id": "Q1_C1",
      "question_id": "Q1",
      "description": "正确应用指数运算法则",
      "detailed_requirements": "需要正确应用幂的乘方法则 (a^m)^n = a^(m×n) 和同底数幂相乘法则 a^m × a^n = a^(m+n)，得到 a⁶ × a⁴ = a¹⁰",
      "points": 5,
      "standard_answer": "a⁶ × a⁴ = a¹⁰",
      "evaluation_method": "step_check",
      "scoring_criteria": {{
        "full_credit": "正确计算出 a⁶ × a⁴ = a¹⁰，过程清晰",
        "partial_credit": "应用了法则但计算有误，或只完成了部分步骤（2-4分）",
        "no_credit": "未应用正确法则或完全错误"
      }},
      "alternative_methods": ["可以先计算 a⁴ ÷ a⁵ = a⁻¹，再计算 a⁶ × a⁻¹ = a⁵"],
      "keywords": ["指数运算", "幂的乘方", "同底数幂相乘"],
      "required_elements": ["a⁶", "a¹⁰"],
      "common_mistakes": ["将 (a²)³ 计算为 a⁵", "忘记应用同底数幂相乘法则"]
    }},
    {{
      "criterion_id": "Q1_C2",
      "question_id": "Q1",
      "description": "正确化简最终答案",
      "detailed_requirements": "在得到 a¹⁰ 后，需要继续除以 a⁵，应用同底数幂相除法则 a^m ÷ a^n = a^(m-n)，得到 a⁵",
      "points": 3,
      "standard_answer": "a⁵",
      "evaluation_method": "exact_match",
      "scoring_criteria": {{
        "full_credit": "最终答案为 a⁵，且过程正确",
        "partial_credit": "答案形式不同但等价（如 a^10/a^5）（1-2分）",
        "no_credit": "答案错误"
      }},
      "alternative_methods": [],
      "keywords": ["同底数幂相除", "化简"],
      "required_elements": ["a⁵"],
      "common_mistakes": ["计算为 a¹⁵ (错误地用乘法)", "保留分数形式未化简"]
    }},
    {{
      "criterion_id": "Q1_C3",
      "question_id": "Q1",
      "description": "答案格式规范",
      "detailed_requirements": "最终答案必须使用正指数表示，不能含有负指数或分数形式的指数",
      "points": 2,
      "standard_answer": "a⁵（正指数形式）",
      "evaluation_method": "format_check",
      "scoring_criteria": {{
        "full_credit": "答案使用正指数表示，格式规范",
        "partial_credit": "答案正确但格式不规范（如写成 a^5.0）（1分）",
        "no_credit": "使用负指数或分数形式"
      }},
      "alternative_methods": [],
      "keywords": ["正指数", "格式规范"],
      "required_elements": ["正指数"],
      "common_mistakes": ["写成 1/a⁻⁵", "写成 a^(10-5)"]
    }}
  ],
  "grading_rules": {{
    "partial_credit": "yes",
    "deduction_rules": ["格式错误扣1-2分", "计算错误按步骤扣分"],
    "step_scoring": "yes"
  }},
  "strictness_guidance": "按步骤给分，注重过程和结果的正确性"
}}
"""

# ==================== 基于标准的批改 Prompt（核心）====================

CRITERIA_BASED_GRADING_PROMPT = """你是一位资深批改教师，擅长基于评分标准进行公正、准确的批改。

【核心原则】
⚠️ 重要：你必须基于【评分标准】对【学生答案】进行评分，而不是对比【学生答案】与【题目内容】。
- 题目内容仅用于提供上下文和理解评分点的含义
- 评分标准是评分的唯一依据
- 学生答案是评分的对象

【题目上下文】
{question_context}

【评分标准】
{rubric_criteria}

【学生答案】
{student_answer}

【严格程度】
{strictness_level}

【评分任务】
请逐条评估学生答案是否满足评分标准中的每个评分点：

对于评分点：{criterion_description}（{criterion_points}分）
评估方法：{evaluation_method}
要求：{criterion_requirements}

【评估步骤】
1. 理解评分点的具体要求（从评分标准中获取）
2. 在题目上下文中定位该评分点相关的部分
3. 在学生答案中查找对应该评分点的内容
4. 判断学生答案是否满足评分标准的要求
5. 根据满足程度给予相应分数

【输出格式】
请以JSON格式输出评估结果：
{{
  "criterion_id": "{criterion_id}",
  "is_met": true/false,
  "satisfaction_level": "完全满足/部分满足/不满足",
  "score_earned": 实际得分（数字）,
  "justification": "评分理由（详细说明为何给这个分数）",
  "evidence": ["从答案中提取的证据1", "证据2", ...],
  "suggestions": ["改进建议1", "建议2", ...]（可选）
}}

【评分示例】
假设评分点要求：必须包含关键词"动能定理"（3分）
- 学生答案包含"动能定理"且正确应用 → 完全满足，得3分
- 学生答案包含"动能定理"但应用有误 → 部分满足，得1-2分
- 学生答案未提及"动能定理" → 不满足，得0分

【禁止行为】
❌ 禁止：将学生答案与题目内容对比
❌ 禁止：因为"答案与题目一致"就给满分
✅ 正确：将学生答案与评分标准要求对比
✅ 正确：基于评分标准的具体要求给分
"""

# ==================== 详细反馈生成 Prompt ====================

DETAILED_FEEDBACK_PROMPT = """你是一位富有经验且善于鼓励学生的教师，擅长生成详细、有建设性的反馈。

【任务】
基于评分结果，生成结构化的详细反馈报告。

【评分结果】
总分：{total_score} / {max_score}
得分率：{score_percentage}%

【各评分点评估结果】
{criteria_evaluations}

【输出要求】
请以Markdown格式输出详细反馈报告：

```markdown
## 批改结果

### 总体评价
- **总分**：{total_score} / {max_score}
- **得分率**：{score_percentage}%
- **等级**：{grade_level}
- **整体评价**：{overall_comment}

### 逐项评分

#### 评分点1：{criterion_description}
- **分值**：{criterion_points}分
- **得分**：{score_earned}分
- **评价**：{satisfaction_level}
- **理由**：{justification}
- **改进建议**：{suggestions}

#### 评分点2：...
（依次列出所有评分点）

### 优点总结
{strengths_summary}

### 需要改进的地方
{improvements_needed}

### 整体建议
{overall_suggestions}
```

【反馈原则】
1. 客观公正：基于评分标准，实事求是
2. 具体详细：明确指出做得好的地方和需要改进的地方
3. 建设性：提供具体的改进建议
4. 鼓励性：肯定学生的努力和进步
"""

# ==================== 工具函数 ====================

def format_question_understanding_prompt(question_content: str, is_vision: bool = False) -> str:
    """格式化题目理解Prompt"""
    if is_vision:
        return QUESTION_UNDERSTANDING_VISION_PROMPT
    else:
        return QUESTION_UNDERSTANDING_TEXT_PROMPT.format(question_content=question_content)


def format_answer_understanding_prompt(answer_content: str, is_vision: bool = False) -> str:
    """格式化答案理解Prompt"""
    if is_vision:
        return ANSWER_UNDERSTANDING_VISION_PROMPT
    else:
        return ANSWER_UNDERSTANDING_TEXT_PROMPT.format(answer_content=answer_content)


def format_rubric_interpretation_prompt(rubric_content: str) -> str:
    """格式化评分标准解析Prompt"""
    return RUBRIC_INTERPRETATION_PROMPT.format(rubric_content=rubric_content)


def format_criteria_grading_prompt(
    question_context: str,
    rubric_criteria: dict,
    student_answer: str,
    strictness_level: str = "中等"
) -> str:
    """格式化基于标准的批改Prompt"""
    criterion_description = rubric_criteria.get('description', '')
    criterion_points = rubric_criteria.get('points', 0)
    criterion_id = rubric_criteria.get('criterion_id', '')
    evaluation_method = rubric_criteria.get('evaluation_method', 'semantic')
    criterion_requirements = rubric_criteria.get('required_elements', [])
    
    return CRITERIA_BASED_GRADING_PROMPT.format(
        question_context=question_context,
        rubric_criteria=str(rubric_criteria),
        student_answer=student_answer,
        strictness_level=strictness_level,
        criterion_description=criterion_description,
        criterion_points=criterion_points,
        criterion_id=criterion_id,
        evaluation_method=evaluation_method,
        criterion_requirements=", ".join(criterion_requirements) if criterion_requirements else "无特殊要求"
    )


def format_detailed_feedback_prompt(
    total_score: float,
    max_score: float,
    criteria_evaluations: list,
    grade_level: str
) -> str:
    """格式化详细反馈生成Prompt"""
    score_percentage = round((total_score / max_score * 100), 2) if max_score > 0 else 0
    
    # 格式化评分点评估结果
    evaluations_text = ""
    for i, eval_result in enumerate(criteria_evaluations, 1):
        evaluations_text += f"\n评分点{i}：{eval_result.get('criterion_id', '')}\n"
        evaluations_text += f"  得分：{eval_result.get('score_earned', 0)} / {eval_result.get('max_points', 0)}\n"
        evaluations_text += f"  满足程度：{eval_result.get('satisfaction_level', '未知')}\n"
        evaluations_text += f"  理由：{eval_result.get('justification', '')}\n"
    
    return DETAILED_FEEDBACK_PROMPT.format(
        total_score=total_score,
        max_score=max_score,
        score_percentage=score_percentage,
        criteria_evaluations=evaluations_text,
        grade_level=grade_level
    )
