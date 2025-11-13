#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
结果格式化器 - 美化批改结果输出
"""

from typing import Dict, List, Any


def format_grading_result_v2(grading_results: List[Dict], aggregated_results: Dict) -> str:
    """
    格式化批改结果（V2 版本 - 详细输出）
    
    Args:
        grading_results: 批改结果列表
        aggregated_results: 聚合结果
        
    Returns:
        格式化的 Markdown 文本
    """
    lines = []
    
    # 标题
    lines.append("# 📋 AI 批改结果报告")
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("")
    
    # 总体成绩
    lines.append("## 📊 总体成绩")
    lines.append("")
    total_score = aggregated_results.get('total_score', 0)
    max_score = aggregated_results.get('max_score', 0)
    percentage = aggregated_results.get('score_percentage', 0)
    grade = aggregated_results.get('grade', 'N/A')
    
    lines.append(f"**总分**: {total_score}/{max_score} 分")
    lines.append(f"**得分率**: {percentage:.1f}%")
    lines.append(f"**等级**: {grade}")
    lines.append(f"**答对题数**: {aggregated_results.get('correct_count', 0)}/{aggregated_results.get('total_questions', 0)}")
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("")
    
    # 逐题详情
    lines.append("## 📝 逐题详情")
    lines.append("")
    
    for i, result in enumerate(grading_results, 1):
        lines.extend(_format_single_question_result(i, result))
        lines.append("")
    
    # 总体评价
    if aggregated_results.get('overall_assessment'):
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        lines.append("## 💡 总体评价")
        lines.append("")
        lines.append(aggregated_results['overall_assessment'])
        lines.append("")
    
    # 薄弱知识点
    weak_points = aggregated_results.get('weak_knowledge_points', [])
    if weak_points:
        lines.append("### ⚠️ 薄弱知识点")
        lines.append("")
        for point in weak_points:
            lines.append(f"- **{point.get('name', '')}**: {point.get('description', '')}")
        lines.append("")
    
    # 学习建议
    suggestions = aggregated_results.get('learning_suggestions', [])
    if suggestions:
        lines.append("### 🎯 学习建议")
        lines.append("")
        for i, suggestion in enumerate(suggestions, 1):
            lines.append(f"{i}. {suggestion}")
        lines.append("")
    
    return '\n'.join(lines)


def _format_single_question_result(question_num: int, result: Dict) -> List[str]:
    """
    格式化单个题目的批改结果
    
    Args:
        question_num: 题目编号
        result: 批改结果
        
    Returns:
        格式化的文本行列表
    """
    lines = []
    
    # 题目标题
    question_text = result.get('question', {}).get('text', f'题目 {question_num}')
    lines.append(f"### 📝 题目 {question_num}：{question_text[:100]}...")
    lines.append("")
    
    # 总体成绩
    score = result.get('score', 0)
    max_score = result.get('max_score', 10)
    percentage = (score / max_score * 100) if max_score > 0 else 0
    
    lines.append(f"**📊 总体成绩**: {score}/{max_score} 分 ({percentage:.1f}%)")
    lines.append("")
    
    # 学生答案
    student_answer = result.get('answer', {}).get('text', '')
    if student_answer:
        lines.append("**✍️ 学生答案**:")
        lines.append("```")
        lines.append(student_answer[:500])  # 限制长度
        if len(student_answer) > 500:
            lines.append("... (答案过长，已截断)")
        lines.append("```")
        lines.append("")
    
    # 逐点评分详情（如果有）
    scoring_details = result.get('scoring_details', [])
    if scoring_details:
        lines.append("**📋 逐点评分详情**:")
        lines.append("")
        
        for detail in scoring_details:
            lines.extend(_format_scoring_detail(detail))
            lines.append("")
    
    # 总体反馈
    feedback = result.get('feedback', '')
    if feedback:
        lines.append("**📝 总体评价**:")
        lines.append(f"> {feedback}")
        lines.append("")
    
    # 优点
    strengths = result.get('strengths', [])
    if strengths:
        lines.append("**💪 优点**:")
        for strength in strengths:
            lines.append(f"- {strength}")
        lines.append("")
    
    # 不足
    weaknesses = result.get('weaknesses', [])
    if weaknesses:
        lines.append("**⚠️ 不足**:")
        for weakness in weaknesses:
            lines.append(f"- {weakness}")
        lines.append("")
    
    # 改进建议
    suggestions = result.get('suggestions', [])
    if suggestions:
        lines.append("**🎯 改进建议**:")
        for i, suggestion in enumerate(suggestions, 1):
            lines.append(f"{i}. {suggestion}")
        lines.append("")
    
    lines.append("---")
    
    return lines


def _format_scoring_detail(detail: Dict) -> List[str]:
    """
    格式化单个评分点的详情
    
    Args:
        detail: 评分点详情
        
    Returns:
        格式化的文本行列表
    """
    lines = []
    
    point_id = detail.get('point_id', 0)
    point_name = detail.get('point_name', '')
    score = detail.get('score', 0)
    max_score = detail.get('max_score', 0)
    is_correct = detail.get('is_correct', False)
    
    # 评分点标题
    icon = "✅" if is_correct else "❌"
    lines.append(f"{icon} **评分点 {point_id}**: {point_name} ({max_score}分)")
    lines.append(f"   **得分**: {score}/{max_score} 分")
    lines.append("")
    
    # 分析
    analysis = detail.get('analysis', '')
    if analysis:
        lines.append(f"   📌 **分析**:")
        lines.append(f"   {analysis}")
        lines.append("")
    
    # 证据
    evidence = detail.get('evidence', '')
    if evidence:
        lines.append(f"   📄 **证据**:")
        lines.append(f'   "{evidence}"')
        lines.append("")
    
    # 原因
    reason = detail.get('reason', '')
    if reason:
        lines.append(f"   💡 **原因**:")
        lines.append(f"   {reason}")
        lines.append("")
    
    return lines


def format_grading_result_simple(grading_results: List[Dict], aggregated_results: Dict) -> str:
    """
    格式化批改结果（简洁版本）
    
    Args:
        grading_results: 批改结果列表
        aggregated_results: 聚合结果
        
    Returns:
        格式化的 Markdown 文本
    """
    lines = []
    
    # 总体成绩
    lines.append("## 📊 批改结果")
    lines.append("")
    lines.append(f"**总分**: {aggregated_results.get('total_score', 0)}/{aggregated_results.get('max_score', 0)} 分")
    lines.append(f"**得分率**: {aggregated_results.get('score_percentage', 0):.1f}%")
    lines.append(f"**等级**: {aggregated_results.get('grade', 'N/A')}")
    lines.append("")
    
    # 逐题得分
    lines.append("### 逐题得分")
    lines.append("")
    for i, result in enumerate(grading_results, 1):
        score = result.get('score', 0)
        max_score = result.get('max_score', 10)
        lines.append(f"- 题目 {i}: {score}/{max_score} 分")
    
    return '\n'.join(lines)


def format_agent_outputs(agent_outputs: List[Dict]) -> str:
    """
    格式化 Agent 输出
    
    Args:
        agent_outputs: Agent 输出列表
        
    Returns:
        格式化的文本
    """
    lines = []
    
    lines.append("## 🤖 Agent 执行记录")
    lines.append("")
    
    for i, output in enumerate(agent_outputs, 1):
        agent_name = output.get('agent', 'Unknown')
        status = output.get('status', 'unknown')
        step = output.get('step', 'unknown')
        
        status_icon = "✅" if status == "success" else "❌" if status == "failed" else "⚠️"
        
        lines.append(f"{i}. {status_icon} **{agent_name}** - {step} ({status})")
    
    lines.append("")
    
    return '\n'.join(lines)

