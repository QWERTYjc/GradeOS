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
请仔细解析以下评分标准，提取每个评分点的具体要求和分值。

【评分标准】
{rubric_content}

【输出要求】
请以JSON格式输出评分标准理解结果，包含以下字段：
{{
  "rubric_id": "标准唯一标识",
  "total_points": 总分（数字）,
  "criteria": [
    {{
      "criterion_id": "C1",
      "description": "评分点描述",
      "points": 分值（数字）,
      "evaluation_method": "评估方法（exact_match/semantic/calculation/step_check等）",
      "keywords": ["关键词1", "关键词2", ...],
      "required_elements": ["必需元素1", "必需元素2", ...]
    }},
    ...
  ],
  "grading_rules": {{
    "partial_credit": "是否允许部分分（yes/no）",
    "deduction_rules": ["扣分规则1", "扣分规则2", ...]
  }},
  "strictness_guidance": "严格程度指导"
}}

【注意事项】
1. 准确提取每个评分点的分值
2. 识别评分点的具体要求和评估方法
3. 提取关键词和必需元素，便于后续评分
4. 确保所有评分点的分值之和等于总分
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
