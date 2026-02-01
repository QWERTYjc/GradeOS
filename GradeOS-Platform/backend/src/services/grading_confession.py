"""批改忏悔生成服务

按照 implementation_plan.md 实现：
在人机交互之前生成，辅助用户查漏补缺，标记可疑位置。

扩展功能（评分标准引用与记忆系统优化）：
- 自白驱动的记忆更新
- 记忆冲突审查
- 另类解法检测

Requirements: Phase 4, 评分标准引用与记忆系统优化
"""

import logging
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from datetime import datetime
from dataclasses import dataclass, field, asdict

if TYPE_CHECKING:
    from src.services.grading_memory import GradingMemoryService, MemoryType


logger = logging.getLogger(__name__)


@dataclass
class ConfessionIssue:
    """
    忏悔问题条目

    扩展字段（评分标准引用与记忆系统优化）：
    - should_create_memory: 是否应创建记忆
    - memory_type: 记忆类型
    - memory_pattern: 记忆模式
    - memory_lesson: 记忆教训
    """

    issue_id: str
    type: (
        str  # low_confidence, missing_evidence, alternative_solution, memory_conflict, no_citation
    )
    severity: str  # info, warning, error
    question_id: str
    point_id: Optional[str] = None
    message: str = ""
    suggestion: str = ""
    details: Optional[Any] = None

    # 新增字段：记忆创建标记
    should_create_memory: bool = False
    memory_type: Optional[str] = None  # error_pattern, calibration, etc.
    memory_pattern: Optional[str] = None
    memory_lesson: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConfessionIssue":
        return cls(**data)


def generate_confession(
    evidence: Dict[str, Any],
    score_result: Dict[str, Any],
    page_index: int,
) -> Dict[str, Any]:
    """
    生成单页批改忏悔

    批改忏悔用于辅助人工核查，标记：
    1. 低置信度评分点
    2. 缺失证据的评分
    3. 逻辑复核修正记录
    4. 可能的识别错误
    5. 另类解法检测（新增）
    6. 评分标准引用缺失（新增）

    Args:
        evidence: 证据提取结果
        score_result: 评分结果
        page_index: 页面索引

    Returns:
        批改忏悔结构
    """
    issues: List[ConfessionIssue] = []
    warnings: List[str] = []
    issue_counter = 0

    def next_issue_id() -> str:
        nonlocal issue_counter
        issue_counter += 1
        return f"issue_{page_index}_{issue_counter:03d}"

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
            issues.append(
                ConfessionIssue(
                    issue_id=next_issue_id(),
                    type="low_confidence",
                    severity="warning",
                    question_id=question_id,
                    message=f"题目 {question_id} 评分置信度较低 ({confidence:.2f})",
                    suggestion="建议人工复核",
                    should_create_memory=True,
                    memory_type="calibration",
                    memory_pattern=f"题目 {question_id} 置信度低于 0.7",
                    memory_lesson="该类型题目可能需要更多关注",
                )
            )

        # 检查是否使用了另类解法
        if q.get("used_alternative_solution"):
            alt_ref = q.get("alternative_solution_ref", "")
            issues.append(
                ConfessionIssue(
                    issue_id=next_issue_id(),
                    type="alternative_solution",
                    severity="info",
                    question_id=question_id,
                    message=f"题目 {question_id} 使用了另类解法",
                    suggestion="建议人工确认解法是否有效",
                    details={"alternative_solution_ref": alt_ref},
                    should_create_memory=True,
                    memory_type="scoring_insight",
                    memory_pattern=f"另类解法: {alt_ref[:50] if alt_ref else '未知'}",
                    memory_lesson="学生可能使用非标准解法，需要特别关注",
                )
            )

        # 检查评分点证据
        for spr in q.get("scoring_point_results", []):
            point_id = spr.get("point_id", "")
            evidence_text = spr.get("evidence", "")
            rubric_ref = spr.get("rubric_reference", "")
            citation_quality = spr.get("citation_quality", "exact")
            is_alt_solution = spr.get("is_alternative_solution", False)

            # 缺失证据
            if not evidence_text or evidence_text.strip() in [
                "",
                "无",
                "N/A",
                "null",
                "【原文引用】未找到",
            ]:
                issues.append(
                    ConfessionIssue(
                        issue_id=next_issue_id(),
                        type="missing_evidence",
                        severity="error",
                        question_id=question_id,
                        point_id=point_id,
                        message=f"评分点 {point_id} 缺少证据引用",
                        suggestion="请核实该评分点的给分依据",
                        should_create_memory=True,
                        memory_type="error_pattern",
                        memory_pattern=f"评分点 {point_id} 证据缺失",
                        memory_lesson="该评分点可能难以找到明确证据",
                    )
                )

            # 检查 rubric_reference
            if not rubric_ref:
                issues.append(
                    ConfessionIssue(
                        issue_id=next_issue_id(),
                        type="no_citation",
                        severity="warning",
                        question_id=question_id,
                        point_id=point_id,
                        message=f"评分点 {point_id} 未引用评分标准",
                        suggestion="请确认评分依据",
                    )
                )

            # 检查引用质量
            if citation_quality == "none":
                warnings.append(f"评分点 {point_id} 引用质量为 none，置信度已降低")
            elif citation_quality == "partial":
                warnings.append(f"评分点 {point_id} 仅有部分引用")

            # 检查另类解法
            if is_alt_solution:
                alt_desc = spr.get("alternative_description", "")
                issues.append(
                    ConfessionIssue(
                        issue_id=next_issue_id(),
                        type="alternative_solution",
                        severity="info",
                        question_id=question_id,
                        point_id=point_id,
                        message=f"评分点 {point_id} 使用了另类解法",
                        suggestion="建议人工确认",
                        details={"alternative_description": alt_desc},
                        should_create_memory=True,
                        memory_type="scoring_insight",
                        memory_pattern=f"另类解法: {alt_desc[:50] if alt_desc else '未知'}",
                        memory_lesson="该评分点可能有多种正确解法",
                    )
                )

        # 拼写错误检查
        typo_notes = q.get("typo_notes", [])
        if typo_notes:
            issues.append(
                ConfessionIssue(
                    issue_id=next_issue_id(),
                    type="typo_detected",
                    severity="info",
                    question_id=question_id,
                    message=f"题目 {question_id} 存在拼写/书写问题",
                    details=typo_notes,
                )
            )

    # 检查学生信息识别
    student_info = evidence.get("student_info") or score_result.get("student_info")
    if student_info:
        info_confidence = student_info.get("confidence", 0.0)
        if info_confidence and info_confidence < 0.8:
            warnings.append(f"学生信息识别置信度较低 ({info_confidence:.2f})")
    else:
        warnings.append("未能识别学生信息")

    # 计算整体可信度
    error_count = sum(1 for i in issues if i.severity == "error")
    warning_count = sum(1 for i in issues if i.severity == "warning")

    if error_count > 0:
        overall_status = "needs_review"
    elif warning_count > 2:
        overall_status = "caution"
    else:
        overall_status = "ok"

    return {
        "page_index": page_index,
        "overall_status": overall_status,
        "issues": [i.to_dict() for i in issues],
        "warnings": warnings,
        "summary": _generate_summary([i.to_dict() for i in issues], warnings, score_result),
        "generated_at": datetime.now().isoformat(),
        # 新增：记忆更新标记
        "memory_candidates": [
            {
                "issue_id": i.issue_id,
                "memory_type": i.memory_type,
                "memory_pattern": i.memory_pattern,
                "memory_lesson": i.memory_lesson,
            }
            for i in issues
            if i.should_create_memory
        ],
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


# ==================== 忏悔驱动的记忆更新 (任务 7) ====================


async def update_memory_from_confession(
    confession: Dict[str, Any],
    memory_service: "GradingMemoryService",
    batch_id: str,
    subject: str = "general",
) -> Dict[str, Any]:
    """
    从忏悔结果更新记忆系统

    根据忏悔中标记的 should_create_memory 问题，创建或更新记忆。

    属性 P4: 自白-记忆一致性
    - 对于自白中标记 should_create_memory=true 的问题
    - 必须在 memory_updates 中有对应的记录
    - 记录的 action 为 "created" 或 "confirmed"

    Args:
        confession: 忏悔结果
        memory_service: 记忆服务实例
        batch_id: 批次ID
        subject: 科目标识

    Returns:
        Dict: 包含 memory_updates 列表
    """
    from src.services.grading_memory import MemoryType, MemoryImportance

    memory_updates: List[Dict[str, Any]] = []

    # 获取需要创建记忆的候选项
    memory_candidates = confession.get("memory_candidates", [])

    for candidate in memory_candidates:
        issue_id = candidate.get("issue_id")
        memory_type_str = candidate.get("memory_type")
        pattern = candidate.get("memory_pattern")
        lesson = candidate.get("memory_lesson")

        if not pattern or not memory_type_str:
            continue

        # 映射记忆类型
        type_mapping = {
            "error_pattern": MemoryType.ERROR_PATTERN,
            "calibration": MemoryType.CALIBRATION,
            "scoring_insight": MemoryType.SCORING_INSIGHT,
            "risk_signal": MemoryType.RISK_SIGNAL,
        }
        memory_type = type_mapping.get(memory_type_str, MemoryType.SCORING_INSIGHT)

        # 检查是否已存在相似记忆
        existing = memory_service.retrieve_relevant_memories(
            memory_types=[memory_type],
            subject=subject,
            max_results=5,
        )

        # 简单的相似度检查（基于模式字符串）
        similar_memory = None
        for mem in existing:
            if _is_similar_pattern(mem.pattern, pattern):
                similar_memory = mem
                break

        if similar_memory:
            # 更新已有记忆
            memory_service.confirm_memory(similar_memory.memory_id)
            memory_updates.append(
                {
                    "issue_id": issue_id,
                    "memory_id": similar_memory.memory_id,
                    "action": "confirmed",
                    "pattern": similar_memory.pattern,
                }
            )
            logger.info(f"[Confession] 确认已有记忆: {similar_memory.memory_id}")
        else:
            # 创建新记忆（待验证状态）
            memory_id = await memory_service.save_memory_async(
                memory_type=memory_type,
                pattern=pattern,
                lesson=lesson or "从自白中学习到的经验",
                context={
                    "source": "confession",
                    "issue_id": issue_id,
                    "batch_id": batch_id,
                },
                importance=MemoryImportance.MEDIUM,
                batch_id=batch_id,
                subject=subject,
            )
            memory_updates.append(
                {
                    "issue_id": issue_id,
                    "memory_id": memory_id,
                    "action": "created",
                    "pattern": pattern,
                }
            )
            logger.info(f"[Confession] 创建新记忆: {memory_id}")

    return {
        "memory_updates": memory_updates,
        "total_created": sum(1 for u in memory_updates if u["action"] == "created"),
        "total_confirmed": sum(1 for u in memory_updates if u["action"] == "confirmed"),
    }


def _is_similar_pattern(pattern1: str, pattern2: str, threshold: float = 0.6) -> bool:
    """
    简单的模式相似度检查

    基于词汇重叠度判断两个模式是否相似。

    Args:
        pattern1: 第一个模式
        pattern2: 第二个模式
        threshold: 相似度阈值

    Returns:
        bool: 是否相似
    """
    if not pattern1 or not pattern2:
        return False

    # 简单的词汇重叠度计算
    words1 = set(pattern1.lower().split())
    words2 = set(pattern2.lower().split())

    if not words1 or not words2:
        return False

    intersection = words1 & words2
    union = words1 | words2

    jaccard = len(intersection) / len(union)
    return jaccard >= threshold


# ==================== 记忆审查机制 (任务 8) ====================


def review_memory_conflict(
    memory_entry: "MemoryEntry",
    logic_review_result: Dict[str, Any],
    grading_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    当逻辑复核与记忆建议冲突时，进行记忆审查

    逻辑复核是"无记忆"的，它的判断更客观。
    当逻辑复核结果与记忆建议冲突时，需要审查记忆的可靠性。

    Args:
        memory_entry: 记忆条目
        logic_review_result: 逻辑复核结果
        grading_result: 评分结果

    Returns:
        Dict: 审查结果
    """
    # 逻辑复核置信度
    logic_confidence = logic_review_result.get("confidence", 0.8)

    # 记忆置信度
    memory_confidence = memory_entry.confidence

    # 判断冲突类型和建议操作
    if logic_confidence > memory_confidence + 0.1:
        # 逻辑复核置信度显著更高，记忆可能有误
        action = "contradict"
        reason = "逻辑复核置信度更高，记忆可能有误"
        suggested_memory_action = "mark_suspicious"
    elif memory_confidence > logic_confidence + 0.2:
        # 记忆置信度显著更高，保持记忆
        action = "confirm"
        reason = "记忆置信度显著更高，保持记忆"
        suggested_memory_action = "verify"
    else:
        # 置信度接近，需要人工审查
        action = "flag_for_review"
        reason = "置信度接近，需要人工审查"
        suggested_memory_action = None

    return {
        "action": action,
        "reason": reason,
        "memory_id": memory_entry.memory_id,
        "memory_pattern": memory_entry.pattern,
        "logic_confidence": logic_confidence,
        "memory_confidence": memory_confidence,
        "confidence_diff": logic_confidence - memory_confidence,
        "suggested_memory_action": suggested_memory_action,
        "reviewed_at": datetime.now().isoformat(),
    }


def apply_memory_review_result(
    review_result: Dict[str, Any],
    memory_service: "GradingMemoryService",
) -> bool:
    """
    应用记忆审查结果

    根据审查结果更新记忆状态。

    Args:
        review_result: 审查结果
        memory_service: 记忆服务实例

    Returns:
        bool: 是否成功应用
    """
    memory_id = review_result.get("memory_id")
    suggested_action = review_result.get("suggested_memory_action")
    reason = review_result.get("reason", "")

    if not memory_id or not suggested_action:
        return False

    if suggested_action == "mark_suspicious":
        return memory_service.mark_suspicious(
            memory_id=memory_id,
            marked_by="logic_review",
            reason=reason,
        )
    elif suggested_action == "verify":
        return memory_service.verify_memory(
            memory_id=memory_id,
            verified_by="logic_review",
            reason=reason,
        )

    return False


# 导出
__all__ = [
    "ConfessionIssue",
    "generate_confession",
    "update_memory_from_confession",
    "review_memory_conflict",
    "apply_memory_review_result",
]
