"""批改自白生成服务

按照 implementation_plan.md 实现：
在人机交互之前生成，辅助用户查漏补缺，标记可疑位置。

Requirements: Phase 4
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime


logger = logging.getLogger(__name__)


def generate_self_report(
    evidence: Dict[str, Any],
    score_result: Dict[str, Any],
    page_index: int,
) -> Dict[str, Any]:
    """
    生成单页批改自白
    
    批改自白用于辅助人工核查，标记：
    1. 低置信度评分点
    2. 缺失证据的评分
    3. 逻辑复核修正记录
    4. 可能的识别错误
    
    Args:
        evidence: 证据提取结果
        score_result: 评分结果
        page_index: 页面索引
        
    Returns:
        批改自白结构
    """
    issues: List[Dict[str, Any]] = []
    warnings: List[str] = []
    
    # 检查证据中的警告
    if evidence.get("warnings"):
        for warning in evidence["warnings"]:
            warnings.append(f"证据提取警告: {warning}")
    
    # 检查各题目的评分点
    for q in score_result.get("question_details", []):
        question_id = q.get("question_id", "?")
        confidence = q.get("confidence", 0.0)
        
        # 低置信度检查
        if confidence and confidence < 0.7:
            issues.append({
                "type": "low_confidence",
                "severity": "warning",
                "question_id": question_id,
                "message": f"题目 {question_id} 评分置信度较低 ({confidence:.2f})",
                "suggestion": "建议人工复核",
            })
        
        # 检查评分点证据
        for spr in q.get("scoring_point_results", []):
            point_id = spr.get("point_id", "")
            evidence_text = spr.get("evidence", "")
            
            # 缺失证据
            if not evidence_text or evidence_text.strip() in ["", "无", "N/A", "null"]:
                issues.append({
                    "type": "missing_evidence",
                    "severity": "error",
                    "question_id": question_id,
                    "point_id": point_id,
                    "message": f"评分点 {point_id} 缺少证据引用",
                    "suggestion": "请核实该评分点的给分依据",
                })
            
            # 检查 rubric_reference
            rubric_ref = spr.get("rubric_reference", "")
            if not rubric_ref:
                warnings.append(f"评分点 {point_id} 未引用评分标准")
        
        # 拼写错误检查
        typo_notes = q.get("typo_notes", [])
        if typo_notes:
            issues.append({
                "type": "typo_detected",
                "severity": "info",
                "question_id": question_id,
                "message": f"题目 {question_id} 存在拼写/书写问题",
                "details": typo_notes,
            })
    
    # 检查学生信息识别
    student_info = evidence.get("student_info") or score_result.get("student_info")
    if student_info:
        info_confidence = student_info.get("confidence", 0.0)
        if info_confidence and info_confidence < 0.8:
            warnings.append(f"学生信息识别置信度较低 ({info_confidence:.2f})")
    else:
        warnings.append("未能识别学生信息")
    
    # 计算整体可信度
    total_issues = len(issues)
    error_count = sum(1 for i in issues if i.get("severity") == "error")
    warning_count = sum(1 for i in issues if i.get("severity") == "warning")
    
    if error_count > 0:
        overall_status = "needs_review"
    elif warning_count > 2:
        overall_status = "caution"
    else:
        overall_status = "ok"
    
    return {
        "page_index": page_index,
        "overall_status": overall_status,
        "issues": issues,
        "warnings": warnings,
        "summary": _generate_summary(issues, warnings, score_result),
        "generated_at": datetime.now().isoformat(),
    }


def _generate_summary(
    issues: List[Dict[str, Any]],
    warnings: List[str],
    score_result: Dict[str, Any],
) -> str:
    """生成自白总结文本"""
    parts = []
    
    score = score_result.get("score", 0)
    max_score = score_result.get("max_score", 0)
    confidence = score_result.get("confidence", 0)
    
    parts.append(f"评分 {score}/{max_score}，置信度 {confidence:.1%}。")
    
    error_issues = [i for i in issues if i.get("severity") == "error"]
    if error_issues:
        parts.append(f"发现 {len(error_issues)} 处需要核查的问题。")
    
    if warnings:
        parts.append(f"有 {len(warnings)} 条提醒信息。")
    
    if not error_issues and not warnings:
        parts.append("评分过程无异常。")
    
    return " ".join(parts)


def generate_student_self_report(
    student_key: str,
    page_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    生成学生级别的批改自白
    
    汇总该学生所有页面的批改自白。
    
    Args:
        student_key: 学生标识
        page_results: 该学生的所有页面批改结果
        
    Returns:
        学生批改自白
    """
    all_issues: List[Dict[str, Any]] = []
    all_warnings: List[str] = []
    
    for page_result in page_results:
        self_report = page_result.get("self_report")
        if self_report:
            all_issues.extend(self_report.get("issues", []))
            all_warnings.extend(self_report.get("warnings", []))
    
    # 去重 warnings
    unique_warnings = list(set(all_warnings))
    
    # 计算整体状态
    error_count = sum(1 for i in all_issues if i.get("severity") == "error")
    if error_count > 0:
        overall_status = "needs_review"
    elif len(all_issues) > 3:
        overall_status = "caution"
    else:
        overall_status = "ok"
    
    # 生成总结
    total_score = sum(p.get("score", 0) for p in page_results)
    total_max = sum(p.get("max_score", 0) for p in page_results)
    
    summary_parts = [f"学生 {student_key}: 总分 {total_score}/{total_max}。"]
    if error_count > 0:
        summary_parts.append(f"共 {error_count} 处需核查。")
    if not all_issues:
        summary_parts.append("批改过程无异常标记。")
    
    return {
        "student_key": student_key,
        "overall_status": overall_status,
        "issues": all_issues,
        "warnings": unique_warnings,
        "summary": " ".join(summary_parts),
        "generated_at": datetime.now().isoformat(),
    }
