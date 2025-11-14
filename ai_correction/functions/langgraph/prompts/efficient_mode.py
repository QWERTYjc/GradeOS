#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高效模式（Efficient Mode）评分提示词模板
节省Token，只返回核心评分信息
符合设计文档: AI批改LangGraph Agent架构设计文档 - 第5.1节
"""

EFFICIENT_MODE_SYSTEM_PROMPT = """你是一个专业的作业批改助手。你的任务是快速、准确地评分学生答案。

**重要指示:**
1. 只返回核心评分信息，不需要详细解释
2. 使用简洁的JSON格式输出
3. 识别错误位置并标记对应的token_id
4. 判断答案正确性：correct, partially_correct, wrong

**输出格式:**
```json
{
  "qid": "题目ID",
  "score": 实际得分（数字）,
  "max_score": 满分（数字）,
  "label": "correct/partially_correct/wrong",
  "error_token_ids": ["错误token的ID列表"],
  "brief_comment": "一句话简评（不超过20字）"
}
```

**评分原则:**
- 严格按照评分标准（rubric）打分
- 每个rubric条目要么得分，要么不得分
- 准确标记错误位置的token_id
"""

EFFICIENT_MODE_USER_TEMPLATE = """请批改以下题目：

**题目信息:**
题号: {qid}
满分: {max_score}分

**评分标准:**
{rubric_items}

**学生答案（带token_id）:**
{student_answer_with_tokens}

请严格按照JSON格式返回评分结果。
"""


def build_efficient_prompt(question: dict, rubric_struct: dict, mm_tokens: list) -> dict:
    """
    构建高效模式的评分提示词
    
    参数:
        question: 题目信息，包含qid, token_ids等
        rubric_struct: 评分标准结构化数据
        mm_tokens: 多模态token列表
    
    返回:
        包含system和user消息的字典
    """
    qid = question['qid']
    
    # 查找对应的评分标准
    rubric_items = []
    for q in rubric_struct.get('questions', []):
        if q['qid'] == qid:
            rubric_items = q.get('rubric_items', [])
            break
    
    # 格式化评分标准（简洁版）
    rubric_text = "\n".join([
        f"{i+1}. [{item.get('score_if_fulfilled', 0)}分] {item.get('description', '')}"
        for i, item in enumerate(rubric_items)
    ])
    
    # 提取学生答案文本（带token_id）
    token_map = {t['id']: t for t in mm_tokens}
    answer_parts = []
    for token_id in question.get('token_ids', []):
        if token_id in token_map:
            token = token_map[token_id]
            answer_parts.append(f"[{token_id}] {token.get('text', '')}")
    
    student_answer = " ".join(answer_parts)
    
    # 构建用户消息
    user_message = EFFICIENT_MODE_USER_TEMPLATE.format(
        qid=qid,
        max_score=question.get('max_score', 0),
        rubric_items=rubric_text,
        student_answer_with_tokens=student_answer
    )
    
    return {
        "system": EFFICIENT_MODE_SYSTEM_PROMPT,
        "user": user_message
    }


def format_rubric_items_efficient(rubric_items: list) -> str:
    """格式化评分标准（高效模式）"""
    lines = []
    for i, item in enumerate(rubric_items, 1):
        score = item.get('score_if_fulfilled', 0)
        desc = item.get('description', '')
        lines.append(f"{i}. [{score}分] {desc}")
    return "\n".join(lines)


def format_student_answer_with_tokens(question: dict, mm_tokens: list) -> str:
    """格式化学生答案（附带token_id）"""
    token_map = {t['id']: t for t in mm_tokens}
    parts = []
    
    for token_id in question.get('token_ids', []):
        if token_id in token_map:
            token = token_map[token_id]
            # 格式: [token_id] text
            parts.append(f"[{token_id}] {token.get('text', '')}")
    
    return " ".join(parts)
