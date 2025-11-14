#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
专业模式（Professional Mode）评分提示词模板
提供详细反馈和教学建议
符合设计文档: AI批改LangGraph Agent架构设计文档 - 第5.2节
"""

PROFESSIONAL_MODE_SYSTEM_PROMPT = """你是一位经验丰富的教师，正在批改学生作业。你的目标是：
1. 准确评分
2. 提供详细、有建设性的反馈
3. 帮助学生理解错误并改进
4. 标注具体的错误位置

**评分要求:**
- 严格按照评分标准（rubric）逐条检查
- 对于每个评分点，明确说明得分或失分的原因
- 识别学生答案中的优点和不足
- 提供具体的改进建议

**反馈要求:**
- 语言友善、鼓励性
- 指出错误时要具体明确
- 提供正确的解题思路或知识点
- 针对性地给出练习建议

**输出格式:**
```json
{
  "qid": "题目ID",
  "score": 实际得分（数字）,
  "max_score": 满分（数字）,
  "label": "correct/partially_correct/wrong",
  "error_token_ids": ["错误token的ID列表"],
  "detailed_feedback": {
    "strengths": ["学生做得好的地方1", "做得好的地方2"],
    "weaknesses": ["需要改进的地方1", "需要改进的地方2"],
    "rubric_analysis": [
      {
        "rubric_id": "评分点ID",
        "achieved": true/false,
        "explanation": "得分/失分的具体原因"
      }
    ],
    "suggestions": ["改进建议1", "建议2"],
    "knowledge_points": ["涉及的知识点1", "知识点2"]
  },
  "teacher_comment": "教师总评（2-3句话）"
}
```
"""

PROFESSIONAL_MODE_USER_TEMPLATE = """请详细批改以下题目：

**题目信息:**
题号: {qid}
满分: {max_score}分
题目描述: {question_text}

**评分标准（Rubric）:**
{detailed_rubric}

**学生答案（带token_id和坐标）:**
{student_answer_with_tokens}

**批改要求:**
1. 逐条检查评分标准，说明每条是否达成
2. 准确标记错误token的ID
3. 分析学生的解题思路
4. 提供详细的改进建议
5. 指出涉及的核心知识点

请返回完整的JSON格式评分结果。
"""


def build_professional_prompt(question: dict, rubric_struct: dict, mm_tokens: list) -> dict:
    """
    构建专业模式的评分提示词
    
    参数:
        question: 题目信息
        rubric_struct: 评分标准结构
        mm_tokens: 多模态token列表
    
    返回:
        包含system和user消息的字典
    """
    qid = question['qid']
    
    # 查找评分标准
    rubric_items = []
    question_text = question.get('description', '')
    for q in rubric_struct.get('questions', []):
        if q['qid'] == qid:
            rubric_items = q.get('rubric_items', [])
            if not question_text:
                question_text = q.get('description', '')
            break
    
    # 格式化评分标准（详细版）
    detailed_rubric = format_rubric_items_professional(rubric_items)
    
    # 提取学生答案（带token_id和位置信息）
    student_answer = format_student_answer_professional(question, mm_tokens)
    
    # 构建用户消息
    user_message = PROFESSIONAL_MODE_USER_TEMPLATE.format(
        qid=qid,
        max_score=question.get('max_score', 0),
        question_text=question_text or '（题目描述未提供）',
        detailed_rubric=detailed_rubric,
        student_answer_with_tokens=student_answer
    )
    
    return {
        "system": PROFESSIONAL_MODE_SYSTEM_PROMPT,
        "user": user_message
    }


def format_rubric_items_professional(rubric_items: list) -> str:
    """格式化评分标准（专业模式 - 详细版）"""
    if not rubric_items:
        return "（无评分标准）"
    
    lines = []
    for i, item in enumerate(rubric_items, 1):
        rubric_id = item.get('id', f'R{i}')
        description = item.get('description', '')
        score = item.get('score_if_fulfilled', 0)
        conditions = item.get('conditions', [])
        
        lines.append(f"\n【评分点 {i}】 (ID: {rubric_id}, {score}分)")
        lines.append(f"要求: {description}")
        
        if conditions:
            lines.append("达成条件:")
            for cond in conditions:
                lines.append(f"  - {cond}")
    
    return "\n".join(lines)


def format_student_answer_professional(question: dict, mm_tokens: list) -> str:
    """格式化学生答案（专业模式 - 包含位置信息）"""
    token_map = {t['id']: t for t in mm_tokens}
    parts = []
    
    for token_id in question.get('token_ids', []):
        if token_id in token_map:
            token = token_map[token_id]
            text = token.get('text', '')
            page = token.get('page', 0)
            bbox = token.get('bbox', {})
            
            # 格式: [token_id | 第X页] text (位置信息)
            location = f"第{page}页" if page else "位置未知"
            parts.append(f"[{token_id} | {location}] {text}")
    
    if not parts:
        return "（学生未作答或答案无法识别）"
    
    return "\n".join(parts)


# 学生评价模板
STUDENT_EVALUATION_TEMPLATE = """
**学生: {student_name}**
**学号: {student_id}**
**总分: {total_score}/{max_score} ({percentage:.1f}%)**
**等级: {grade_level}**

**整体表现:**
{overall_performance}

**优势分析:**
{strengths_analysis}

**需要改进:**
{weaknesses_analysis}

**学习建议:**
{learning_suggestions}

**知识点掌握情况:**
{knowledge_mastery}
"""


def format_student_evaluation(evaluation_data: dict) -> str:
    """格式化学生个人评价"""
    return STUDENT_EVALUATION_TEMPLATE.format(
        student_name=evaluation_data.get('student_name', '未知'),
        student_id=evaluation_data.get('student_id', '未知'),
        total_score=evaluation_data.get('total_score', 0),
        max_score=evaluation_data.get('max_score', 0),
        percentage=evaluation_data.get('percentage', 0),
        grade_level=evaluation_data.get('grade_level', 'F'),
        overall_performance=evaluation_data.get('overall_performance', ''),
        strengths_analysis="\n".join(f"- {s}" for s in evaluation_data.get('strengths', [])),
        weaknesses_analysis="\n".join(f"- {w}" for w in evaluation_data.get('weaknesses', [])),
        learning_suggestions="\n".join(f"{i+1}. {s}" for i, s in enumerate(evaluation_data.get('suggestions', []))),
        knowledge_mastery="\n".join(f"- {k}" for k in evaluation_data.get('knowledge_points', []))
    )


# 班级评价模板
CLASS_EVALUATION_TEMPLATE = """
**班级整体评价报告**

**基本信息:**
- 班级: {class_name}
- 参与人数: {student_count}
- 平均分: {average_score:.2f}/{max_score} ({average_percentage:.1f}%)

**分数分布:**
{score_distribution}

**共性问题:**
{common_issues}

**优秀表现:**
{excellent_performances}

**教学建议:**
{teaching_suggestions}

**重点知识点复习:**
{key_knowledge_points}
"""


def format_class_evaluation(class_data: dict) -> str:
    """格式化班级整体评价"""
    score_dist = class_data.get('score_distribution', {})
    dist_text = "\n".join([
        f"- {grade}: {count}人 ({count/class_data.get('student_count', 1)*100:.1f}%)"
        for grade, count in score_dist.items()
    ])
    
    return CLASS_EVALUATION_TEMPLATE.format(
        class_name=class_data.get('class_name', '未知班级'),
        student_count=class_data.get('student_count', 0),
        average_score=class_data.get('average_score', 0),
        max_score=class_data.get('max_score', 0),
        average_percentage=class_data.get('average_percentage', 0),
        score_distribution=dist_text,
        common_issues="\n".join(f"{i+1}. {issue}" for i, issue in enumerate(class_data.get('common_issues', []))),
        excellent_performances="\n".join(f"- {perf}" for perf in class_data.get('excellent_performances', [])),
        teaching_suggestions="\n".join(f"{i+1}. {sug}" for i, sug in enumerate(class_data.get('teaching_suggestions', []))),
        key_knowledge_points="\n".join(f"- {kp}" for kp in class_data.get('key_knowledge_points', []))
    )
