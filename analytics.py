"""Deterministic reporting functions extracted from GradeOS; no services or score writes.

Source hashes and exact extracted symbols: docs/provenance/analytics.json.
"""


from __future__ import annotations


import math
import re
import unicodedata
from datetime import datetime
from typing import Any, Dict, List


def safe_float(value: Any, default: float = 0.0) -> float:
    """Best-effort float conversion with fallback."""
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(converted):
        return default
    return converted


_PLACEHOLDER_EVIDENCE_VALUES = frozenset(
    {
        "not found",
        "unable to find",
        "missing",
        "n/a",
        "null",
        "未找到",
        "找不到",
        "未识别",
        "无法辨认",
    }
)


_EVIDENCE_PREFIX_RE = re.compile(r"^\s*(?:【[^】]+】|\[[^\]]+\]|<[^>]+>)\s*")


def strip_evidence_prefix(evidence: Any) -> str:
    if evidence is None:
        return ""
    text = str(evidence).strip()
    if not text:
        return ""
    stripped = _EVIDENCE_PREFIX_RE.sub("", text)
    stripped = re.sub(
        r"^(?:evidence|quote|citation)\s*[:：]\s*",
        "",
        stripped,
        flags=re.IGNORECASE,
    )
    return stripped.strip()


def normalize_evidence_text(evidence: Any) -> str:
    return strip_evidence_prefix(evidence)


def is_placeholder_evidence(evidence: Any) -> bool:
    text = normalize_evidence_text(evidence)
    if not text:
        return True
    normalized = re.sub(r"\s+", " ", text.strip().lower()).rstrip(".。")
    return normalized in _PLACEHOLDER_EVIDENCE_VALUES


def evidence_fields_indicate_missing(
    evidence: Any,
    *,
    status: Any = None,
    missing: Any = None,
) -> bool:
    if isinstance(missing, bool):
        explicit_missing = missing
    elif missing is None:
        explicit_missing = False
    else:
        explicit_missing = str(missing).strip().lower() in {"1", "true", "yes", "on"}

    normalized_status = str(status or "").strip().lower()
    if explicit_missing or normalized_status in {
        "missing",
        "none",
        "insufficient",
        "unverifiable",
    }:
        return True
    if normalized_status in {"found", "present"}:
        return False
    return is_placeholder_evidence(evidence)


def _normalize_question_id(value: Any) -> str:
    """Remove only an explicit question label, preserving opaque identities."""

    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).strip()
    if not text:
        return ""
    text = re.sub(
        r"^(?:question|ques|q)(?:\s*(?:no\.?|number|#))?[\s:：#._-]+",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"^[Qq](?=\d|\()", "", text)
    text = re.sub(r"^(?:题目|題目|题|題)\s*[:：#._-]?\s*", "", text)
    if re.match(r"^第\s*\d", text):
        text = re.sub(r"^第\s*", "", text)
        text = re.sub(r"\s*(?:题|題)$", "", text)
    return text.strip().rstrip(".:：")


def _rubric_question_maps(
    parsed_rubric: Dict[str, Any],
) -> tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, float]]]:
    question_by_id: Dict[str, Dict[str, Any]] = {}
    point_max_by_question: Dict[str, Dict[str, float]] = {}
    if not isinstance(parsed_rubric, dict):
        return question_by_id, point_max_by_question
    for question in parsed_rubric.get("questions") or []:
        if not isinstance(question, dict):
            continue
        qid = _normalize_question_id(
            question.get("question_id") or question.get("questionId") or question.get("id")
        )
        if not qid:
            continue
        question_by_id[qid] = question
        point_map: Dict[str, float] = {}
        for index, point in enumerate(question.get("scoring_points") or [], 1):
            if not isinstance(point, dict):
                continue
            point_id = str(
                point.get("point_id") or point.get("pointId") or f"{qid}.{index}"
            ).strip()
            if point_id:
                point_map[point_id] = _safe_float(
                    point.get("max_score", point.get("maxScore", point.get("score", 0.0))),
                    0.0,
                )
        point_max_by_question[qid] = point_map
    return question_by_id, point_max_by_question


def _scoring_point_evidence_missing(point: Dict[str, Any]) -> bool:
    return _evidence_fields_indicate_missing(
        point.get("evidence", point.get("evidenceText")),
        status=point.get("evidence_status", point.get("evidenceStatus")),
        missing=point.get("evidence_missing", point.get("evidenceMissing")),
    )


def _extract_scoring_points(question: Dict[str, Any]) -> List[Dict[str, Any]]:
    qid = _normalize_question_id(question.get("question_id") or question.get("questionId"))
    raw_points = question.get("scoring_point_results") or question.get("scoring_results") or []
    points: List[Dict[str, Any]] = []
    for spr in raw_points:
        if not isinstance(spr, dict):
            continue
        scoring_point = spr.get("scoring_point") or spr.get("scoringPoint") or {}
        description = (
            scoring_point.get("description")
            or spr.get("description")
            or spr.get("rubric_reference")
            or spr.get("rubricReference")
            or ""
        )
        point_id = spr.get("point_id") or spr.get("pointId") or scoring_point.get("point_id") or ""
        awarded = _safe_float(spr.get("awarded", spr.get("score", 0)))
        max_points = _safe_float(
            spr.get("max_points") or spr.get("maxPoints") or scoring_point.get("score") or 0
        )
        points.append(
            {
                "question_id": qid,
                "point_id": str(point_id) if point_id is not None else "",
                "description": description,
                "score": awarded,
                "max_score": max_points,
                "evidence": spr.get("evidence") or "",
                "rubric_reference": spr.get("rubric_reference") or spr.get("rubricReference") or "",
            }
        )
    return points


def _build_student_summary(student: Dict[str, Any]) -> Dict[str, Any]:
    score_unavailable = bool(
        student.get("total_score") is None
        or str(student.get("score_status") or "").strip().lower() == "unavailable"
    )
    if score_unavailable:
        return {
            "overall": "评分暂不可用，证据或评分契约需要教师复核。",
            "percentage": None,
            "knowledge_points": [],
            "improvement_suggestions": [],
            "generated_at": datetime.now().isoformat(),
        }

    total_score = _safe_float(student.get("total_score", 0))
    max_total_score = _safe_float(student.get("max_total_score", 0))
    percentage = (total_score / max_total_score * 100) if max_total_score > 0 else 0.0

    knowledge_points: List[Dict[str, Any]] = []
    weak_points: List[Dict[str, Any]] = []

    question_details = student.get("question_details") or []
    for question in question_details:
        for point in _extract_scoring_points(question):
            max_score = point.get("max_score", 0) or 0
            ratio = (point.get("score", 0) / max_score) if max_score > 0 else 0.0
            if ratio >= 0.85:
                mastery = "mastered"
            elif ratio >= 0.6:
                mastery = "partial"
            else:
                mastery = "weak"
            enriched = {
                **point,
                "mastery_level": mastery,
                "ratio": ratio,
            }
            knowledge_points.append(enriched)
            if mastery == "weak":
                weak_points.append(enriched)

    if not knowledge_points:
        for question in question_details:
            qid = _normalize_question_id(question.get("question_id") or question.get("questionId"))
            score = _safe_float(question.get("score", 0))
            max_score = _safe_float(question.get("max_score", 0))
            ratio = (score / max_score) if max_score > 0 else 0.0
            mastery = "partial" if ratio >= 0.6 else "weak"
            knowledge_points.append(
                {
                    "question_id": qid,
                    "point_id": "",
                    "description": question.get("feedback", "") or f"Question {qid}",
                    "score": score,
                    "max_score": max_score,
                    "mastery_level": mastery,
                    "ratio": ratio,
                    "evidence": "",
                    "rubric_reference": "",
                }
            )
            if mastery == "weak":
                weak_points.append(knowledge_points[-1])

    suggestion_candidates = []
    for point in weak_points:
        label = point.get("description") or f"Question {point.get('question_id', '')}"
        if label:
            suggestion_candidates.append(f"建议复习：{label}")
    if not suggestion_candidates:
        for point in knowledge_points:
            if point.get("ratio", 0) < 0.7:
                label = point.get("description") or f"Question {point.get('question_id', '')}"
                if label:
                    suggestion_candidates.append(f"建议复习：{label}")

    improvement_suggestions = []
    seen = set()
    for item in suggestion_candidates:
        if item not in seen:
            improvement_suggestions.append(item)
            seen.add(item)
        if len(improvement_suggestions) >= 5:
            break

    overall_parts = [f"整体得分 {total_score}/{max_total_score}（{percentage:.1f}%）。"]
    if percentage >= 85:
        overall_parts.append("整体表现优秀。")
    elif percentage >= 70:
        overall_parts.append("整体表现良好。")
    elif percentage >= 60:
        overall_parts.append("整体达到及格水平。")
    else:
        overall_parts.append("整体表现需重点提升。")

    if weak_points:
        weak_labels = []
        for point in weak_points[:3]:
            label = point.get("description") or f"Question {point.get('question_id', '')}"
            if label:
                weak_labels.append(label)
        if weak_labels:
            overall_parts.append(f"薄弱点集中在：{'，'.join(weak_labels)}。")
    else:
        overall_parts.append("暂无明显薄弱点。")

    return {
        "overall": " ".join(overall_parts),
        "percentage": percentage,
        "knowledge_points": knowledge_points,
        "improvement_suggestions": improvement_suggestions,
        "generated_at": datetime.now().isoformat(),
    }


def _build_class_report(student_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_students = len(student_results)
    if total_students == 0:
        return {
            "total_students": 0,
            "generated_at": datetime.now().isoformat(),
        }

    total_scores = []
    total_percentages = []
    distribution = {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0}
    knowledge_aggregate: Dict[str, Dict[str, Any]] = {}

    for student in student_results:
        score_unavailable = bool(
            student.get("total_score") is None
            or str(student.get("score_status") or "").strip().lower() == "unavailable"
        )
        if score_unavailable:
            continue
        total_score = _safe_float(student.get("total_score", 0))
        max_score = _safe_float(student.get("max_total_score", 0))
        percentage = (total_score / max_score * 100) if max_score > 0 else 0.0
        total_scores.append(total_score)
        total_percentages.append(percentage)

        if percentage >= 85:
            distribution["A"] += 1
        elif percentage >= 70:
            distribution["B"] += 1
        elif percentage >= 60:
            distribution["C"] += 1
        elif percentage >= 50:
            distribution["D"] += 1
        else:
            distribution["E"] += 1

        summary = student.get("student_summary") or _build_student_summary(student)
        for point in summary.get("knowledge_points", []):
            key = point.get("point_id") or point.get("description") or ""
            if not key:
                continue
            entry = knowledge_aggregate.setdefault(
                key,
                {
                    "point_id": point.get("point_id") or "",
                    "description": point.get("description") or "",
                    "total_score": 0.0,
                    "total_max_score": 0.0,
                },
            )
            entry["total_score"] += _safe_float(point.get("score", 0))
            entry["total_max_score"] += _safe_float(point.get("max_score", 0))

    scored_student_count = len(total_scores)
    average_score = sum(total_scores) / scored_student_count if scored_student_count else 0.0
    average_percentage = (
        sum(total_percentages) / scored_student_count if scored_student_count else 0.0
    )
    pass_rate = (
        sum(1 for pct in total_percentages if pct >= 60) / scored_student_count
        if scored_student_count
        else 0.0
    )

    weak_points: List[Dict[str, Any]] = []
    strong_points: List[Dict[str, Any]] = []
    for entry in knowledge_aggregate.values():
        max_score = entry.get("total_max_score", 0) or 0
        ratio = (entry.get("total_score", 0) / max_score) if max_score > 0 else 0.0
        record = {
            "point_id": entry.get("point_id"),
            "description": entry.get("description"),
            "mastery_ratio": ratio,
        }
        if ratio < 0.6:
            weak_points.append(record)
        elif ratio >= 0.85:
            strong_points.append(record)

    weak_points.sort(key=lambda x: _safe_float(x.get("mastery_ratio", 0), 0.0))
    strong_points.sort(key=lambda x: _safe_float(x.get("mastery_ratio", 0), 0.0), reverse=True)

    summary_parts = [
        f"班级平均分 {average_score:.1f}，平均得分率 {average_percentage:.1f}%。",
        f"及格率 {pass_rate * 100:.1f}%。",
    ]
    if weak_points:
        weak_labels = [str(p.get("description")) for p in weak_points[:3] if p.get("description")]
        if weak_labels:
            summary_parts.append(f"主要薄弱知识点：{'，'.join(weak_labels)}。")
    if strong_points:
        strong_labels = [
            str(p.get("description")) for p in strong_points[:3] if p.get("description")
        ]
        if strong_labels:
            summary_parts.append(f"优势知识点：{'，'.join(strong_labels)}。")

    return {
        "total_students": total_students,
        "scored_student_count": scored_student_count,
        "average_score": average_score,
        "average_percentage": average_percentage,
        "pass_rate": pass_rate,
        "score_distribution": distribution,
        "weak_points": weak_points[:10],
        "strong_points": strong_points[:10],
        "summary": " ".join(summary_parts),
        "generated_at": datetime.now().isoformat(),
    }


def build_global_logic_review_audit(
    student_results: List[Dict[str, Any]],
    parsed_rubric: Dict[str, Any],
) -> Dict[str, Any]:
    question_by_id, point_max_by_question = _rubric_question_maps(parsed_rubric)
    total_scores = [
        _safe_float(student.get("total_score", student.get("score", 0.0)), 0.0)
        for student in student_results
        if isinstance(student, dict)
    ]
    max_scores = [
        _safe_float(student.get("max_total_score", student.get("max_score", 0.0)), 0.0)
        for student in student_results
        if isinstance(student, dict)
    ]
    issues: List[Dict[str, Any]] = []
    distributions: Dict[str, Any] = {
        "student_count": len(total_scores),
        "min_total_score": min(total_scores) if total_scores else 0.0,
        "max_total_score": max(total_scores) if total_scores else 0.0,
        "average_total_score": (sum(total_scores) / len(total_scores)) if total_scores else 0.0,
        "average_max_score": (sum(max_scores) / len(max_scores)) if max_scores else 0.0,
    }
    if len(total_scores) >= 3:
        average = distributions["average_total_score"]
        variance = sum((score - average) ** 2 for score in total_scores) / len(total_scores)
        stddev = variance**0.5
        distributions["stddev_total_score"] = stddev
        if stddev > 0:
            outlier_count = sum(1 for score in total_scores if abs(score - average) / stddev >= 2.0)
            distributions["outlier_count"] = outlier_count
            if outlier_count:
                issues.append(
                    {
                        "rule": "class_total_score_outliers",
                        "severity": "warning",
                        "message": f"{outlier_count} student total score(s) are more than 2 standard deviations from the class average.",
                    }
                )

    question_stats: Dict[str, Dict[str, Any]] = {}
    point_stats: Dict[str, Dict[str, Any]] = {}
    for student in student_results:
        if not isinstance(student, dict):
            continue
        seen_qids: set[str] = set()
        for question in student.get("question_details") or []:
            if not isinstance(question, dict):
                continue
            qid = _normalize_question_id(
                question.get("question_id") or question.get("questionId") or question.get("id")
            )
            if not qid:
                continue
            seen_qids.add(qid)
            qscore = _safe_float(question.get("score"), 0.0)
            qmax = _safe_float(question.get("max_score", question.get("maxScore", 0.0)), 0.0)
            qstat = question_stats.setdefault(
                qid,
                {
                    "question_id": qid,
                    "count": 0,
                    "scores": [],
                    "missing_positive_evidence_count": 0,
                    "unknown_question_count": 0,
                },
            )
            qstat["count"] += 1
            qstat["scores"].append(qscore / qmax if qmax > 0 else 0.0)
            if question_by_id and qid not in question_by_id:
                qstat["unknown_question_count"] += 1
            for point in question.get("scoring_point_results") or []:
                if not isinstance(point, dict):
                    continue
                point_id = str(point.get("point_id") or point.get("pointId") or "").strip()
                if not point_id:
                    continue
                awarded = _safe_float(point.get("awarded", point.get("score", 0.0)), 0.0)
                pmax = _safe_float(
                    point.get(
                        "max_points",
                        point.get(
                            "maxPoints", point_max_by_question.get(qid, {}).get(point_id, 0.0)
                        ),
                    ),
                    0.0,
                )
                pkey = f"{qid}:{point_id}"
                pstat = point_stats.setdefault(
                    pkey,
                    {
                        "question_id": qid,
                        "point_id": point_id,
                        "count": 0,
                        "positive_count": 0,
                        "zero_count": 0,
                        "missing_evidence_positive_count": 0,
                    },
                )
                pstat["count"] += 1
                if awarded > 0:
                    pstat["positive_count"] += 1
                    if _scoring_point_evidence_missing(point):
                        pstat["missing_evidence_positive_count"] += 1
                        qstat["missing_positive_evidence_count"] += 1
                elif pmax > 0:
                    pstat["zero_count"] += 1
        for expected_qid in question_by_id:
            if expected_qid not in seen_qids:
                question_stats.setdefault(
                    expected_qid,
                    {
                        "question_id": expected_qid,
                        "count": 0,
                        "scores": [],
                        "missing_positive_evidence_count": 0,
                        "unknown_question_count": 0,
                        "missing_student_count": 0,
                    },
                )
                question_stats[expected_qid]["missing_student_count"] = (
                    question_stats[expected_qid].get("missing_student_count", 0) + 1
                )

    question_audits: List[Dict[str, Any]] = []
    for qid, stat in sorted(question_stats.items()):
        scores = stat.get("scores") or []
        score_range = (max(scores) - min(scores)) if scores else 0.0
        audit = {
            "question_id": qid,
            "student_count": stat.get("count", 0),
            "score_ratio_range": score_range,
            "missing_positive_evidence_count": stat.get("missing_positive_evidence_count", 0),
            "missing_student_count": stat.get("missing_student_count", 0),
            "unknown_question_count": stat.get("unknown_question_count", 0),
        }
        if audit["missing_positive_evidence_count"]:
            issues.append(
                {
                    "rule": "question_positive_award_missing_evidence",
                    "severity": "warning",
                    "question_id": qid,
                    "message": f"Question {qid} has positive awarded scoring points with missing evidence.",
                    "count": audit["missing_positive_evidence_count"],
                }
            )
        if audit["missing_student_count"]:
            issues.append(
                {
                    "rule": "question_missing_for_some_students",
                    "severity": "error",
                    "question_id": qid,
                    "message": f"Question {qid} is missing from {audit['missing_student_count']} student result(s).",
                    "count": audit["missing_student_count"],
                }
            )
        if audit["unknown_question_count"]:
            issues.append(
                {
                    "rule": "question_id_not_in_rubric_global",
                    "severity": "error",
                    "question_id": qid,
                    "message": f"Question {qid} appears in results but not in the rubric.",
                    "count": audit["unknown_question_count"],
                }
            )
        if len(scores) >= 3 and score_range >= 0.9:
            issues.append(
                {
                    "rule": "question_score_distribution_wide",
                    "severity": "info",
                    "question_id": qid,
                    "message": f"Question {qid} has a wide score ratio distribution across students.",
                    "score_ratio_range": score_range,
                }
            )
        question_audits.append(audit)

    point_audits: List[Dict[str, Any]] = []
    for _key, stat in sorted(point_stats.items()):
        missing_positive = stat.get("missing_evidence_positive_count", 0)
        if missing_positive:
            issues.append(
                {
                    "rule": "point_positive_award_missing_evidence_global",
                    "severity": "warning",
                    "question_id": stat.get("question_id"),
                    "point_id": stat.get("point_id"),
                    "message": (
                        f"Point {stat.get('point_id')} has {missing_positive} positive award(s) "
                        "without usable evidence."
                    ),
                    "count": missing_positive,
                }
            )
        if stat.get("positive_count", 0) and stat.get("zero_count", 0) and missing_positive:
            issues.append(
                {
                    "rule": "point_application_consistency_risk",
                    "severity": "warning",
                    "question_id": stat.get("question_id"),
                    "point_id": stat.get("point_id"),
                    "message": (
                        f"Point {stat.get('point_id')} mixes zero awards with positive awards "
                        "that lack evidence; check consistency across students."
                    ),
                }
            )
        point_audits.append(stat)

    return {
        "summary": "Global logic audit completed.",
        "issue_count": len(issues),
        "issues": issues,
        "score_distribution": distributions,
        "question_audits": question_audits,
        "point_audits": point_audits,
    }


_safe_float = safe_float


_evidence_fields_indicate_missing = evidence_fields_indicate_missing
