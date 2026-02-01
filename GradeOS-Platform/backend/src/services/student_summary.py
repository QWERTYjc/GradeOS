"""学生总结生成服务

按照 implementation_plan.md 实现：
在人机确认后生成学生总结，包含知识点掌握情况和改进建议。

Requirements: Phase 4
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime


logger = logging.getLogger(__name__)


def generate_student_summary(
    student_key: str,
    page_results: List[Dict[str, Any]],
    parsed_rubric: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    生成学生学习总结

    包含：
    1. 整体得分和表现评价
    2. 知识点掌握情况
    3. 薄弱点分析
    4. 改进建议

    Args:
        student_key: 学生标识
        page_results: 该学生的批改结果
        parsed_rubric: 解析的评分标准（用于知识点映射）

    Returns:
        学生总结结构
    """
    # 计算总分
    total_score = sum(_safe_float(p.get("score", 0)) for p in page_results)
    total_max_score = sum(_safe_float(p.get("max_score", 0)) for p in page_results)
    percentage = (total_score / total_max_score * 100) if total_max_score > 0 else 0.0

    # 收集所有题目详情
    all_questions: List[Dict[str, Any]] = []
    for page in page_results:
        for q in page.get("question_details", []):
            all_questions.append(q)

    # 分析知识点掌握情况
    knowledge_points = _analyze_knowledge_points(all_questions)

    # 识别薄弱点
    weak_points = [kp for kp in knowledge_points if kp.get("mastery_level") == "weak"]

    # 生成改进建议
    improvement_suggestions = _generate_suggestions(weak_points, knowledge_points)

    # 生成整体评价
    overall_text = _generate_overall_assessment(percentage, weak_points)

    return {
        "student_key": student_key,
        "total_score": total_score,
        "max_total_score": total_max_score,
        "percentage": percentage,
        "overall": overall_text,
        "knowledge_points": knowledge_points,
        "weak_points": weak_points,
        "improvement_suggestions": improvement_suggestions,
        "generated_at": datetime.now().isoformat(),
    }


def _safe_float(value: Any) -> float:
    """安全转换为浮点数"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _analyze_knowledge_points(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """分析知识点掌握情况"""
    knowledge_points: List[Dict[str, Any]] = []
    seen_points: Dict[str, Dict[str, Any]] = {}

    for q in questions:
        question_id = q.get("question_id", "")
        score = _safe_float(q.get("score", 0))
        max_score = _safe_float(q.get("max_score", 0))

        # 从评分点结果中提取知识点
        for spr in q.get("scoring_point_results", []):
            point_id = spr.get("point_id", "")
            description = spr.get("description", "") or spr.get("rubric_reference", "")
            awarded = _safe_float(spr.get("awarded", 0))
            max_points = _safe_float(spr.get("max_points", 0) or spr.get("max_score", 0))

            if not point_id:
                point_id = f"{question_id}.{len(seen_points) + 1}"

            key = point_id
            if key in seen_points:
                # 合并重复知识点
                seen_points[key]["score"] += awarded
                seen_points[key]["max_score"] += max_points
            else:
                seen_points[key] = {
                    "point_id": point_id,
                    "question_id": question_id,
                    "description": description,
                    "score": awarded,
                    "max_score": max_points,
                }

    # 计算掌握等级
    for point in seen_points.values():
        max_score = point.get("max_score", 0)
        if max_score > 0:
            ratio = point["score"] / max_score
        else:
            ratio = 0.0

        if ratio >= 0.85:
            mastery = "mastered"
        elif ratio >= 0.6:
            mastery = "partial"
        else:
            mastery = "weak"

        knowledge_points.append(
            {
                **point,
                "mastery_ratio": ratio,
                "mastery_level": mastery,
            }
        )

    # 如果没有评分点，按题目生成
    if not knowledge_points:
        for q in questions:
            question_id = q.get("question_id", "")
            score = _safe_float(q.get("score", 0))
            max_score = _safe_float(q.get("max_score", 0))
            ratio = (score / max_score) if max_score > 0 else 0.0

            mastery = "mastered" if ratio >= 0.85 else ("partial" if ratio >= 0.6 else "weak")

            knowledge_points.append(
                {
                    "point_id": "",
                    "question_id": question_id,
                    "description": q.get("feedback", "") or f"题目 {question_id}",
                    "score": score,
                    "max_score": max_score,
                    "mastery_ratio": ratio,
                    "mastery_level": mastery,
                }
            )

    return knowledge_points


def _generate_suggestions(
    weak_points: List[Dict[str, Any]],
    all_points: List[Dict[str, Any]],
) -> List[str]:
    """生成改进建议"""
    suggestions = []
    seen = set()

    # 针对薄弱点生成建议
    for point in weak_points[:5]:
        desc = point.get("description", "")
        if desc and desc not in seen:
            suggestions.append(f"建议复习：{desc}")
            seen.add(desc)

    # 如果没有明显薄弱点，检查 partial 掌握的知识点
    if not suggestions:
        partial_points = [p for p in all_points if p.get("mastery_level") == "partial"]
        for point in partial_points[:3]:
            desc = point.get("description", "")
            if desc and desc not in seen:
                suggestions.append(f"可加强：{desc}")
                seen.add(desc)

    if not suggestions:
        suggestions.append("继续保持良好的学习状态")

    return suggestions


def _generate_overall_assessment(percentage: float, weak_points: List[Dict[str, Any]]) -> str:
    """生成整体评价文本"""
    parts = []

    parts.append(f"得分率 {percentage:.1f}%。")

    if percentage >= 90:
        parts.append("表现优秀，各知识点掌握扎实。")
    elif percentage >= 80:
        parts.append("表现良好，整体掌握情况较好。")
    elif percentage >= 70:
        parts.append("表现中等，部分知识点需要加强。")
    elif percentage >= 60:
        parts.append("达到及格线，建议重点复习薄弱环节。")
    else:
        parts.append("需要重点提升，建议系统复习相关知识。")

    if weak_points:
        weak_labels = [
            p.get("description", "")[:20] for p in weak_points[:3] if p.get("description")
        ]
        if weak_labels:
            parts.append(f"主要薄弱点：{'、'.join(weak_labels)}。")

    return " ".join(parts)


def generate_class_summary(
    student_summaries: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    生成班级级别的总结

    Args:
        student_summaries: 所有学生的总结

    Returns:
        班级总结结构
    """
    if not student_summaries:
        return {
            "total_students": 0,
            "average_score": 0.0,
            "average_percentage": 0.0,
            "pass_rate": 0.0,
            "generated_at": datetime.now().isoformat(),
        }

    total_students = len(student_summaries)

    total_scores = [s.get("total_score", 0) for s in student_summaries]
    percentages = [s.get("percentage", 0) for s in student_summaries]

    average_score = sum(total_scores) / total_students
    average_percentage = sum(percentages) / total_students
    pass_rate = sum(1 for p in percentages if p >= 60) / total_students

    # 统计分数分布
    distribution = {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0}
    for pct in percentages:
        if pct >= 85:
            distribution["A"] += 1
        elif pct >= 70:
            distribution["B"] += 1
        elif pct >= 60:
            distribution["C"] += 1
        elif pct >= 50:
            distribution["D"] += 1
        else:
            distribution["E"] += 1

    # 汇总班级薄弱点
    weak_point_counts: Dict[str, int] = {}
    for summary in student_summaries:
        for wp in summary.get("weak_points", []):
            desc = wp.get("description", "")
            if desc:
                weak_point_counts[desc] = weak_point_counts.get(desc, 0) + 1

    # 排序找出最常见的薄弱点
    common_weak_points = sorted(weak_point_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    summary_text = (
        f"班级共 {total_students} 人，平均分 {average_score:.1f}，"
        f"平均得分率 {average_percentage:.1f}%，及格率 {pass_rate * 100:.1f}%。"
    )
    if common_weak_points:
        weak_labels = [wp[0][:20] for wp in common_weak_points[:3]]
        summary_text += f" 班级常见薄弱点：{'、'.join(weak_labels)}。"

    return {
        "total_students": total_students,
        "average_score": average_score,
        "average_percentage": average_percentage,
        "pass_rate": pass_rate,
        "score_distribution": distribution,
        "common_weak_points": [{"description": wp[0], "count": wp[1]} for wp in common_weak_points],
        "summary": summary_text,
        "generated_at": datetime.now().isoformat(),
    }
