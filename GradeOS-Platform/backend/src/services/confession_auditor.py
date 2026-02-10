"""
Confession (self-audit) report generator.

Design goals:
- One independent LLM call after the main output (rubric parse / grading output).
- Reward honesty: admitting uncertainty is not penalized; avoid guessing.
- Low-noise: only emit actionable, verifiable checklist items with references.
- Output MUST be JSON (no markdown) and follow ConfessionReport v1 schema.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from langchain_core.messages import HumanMessage, SystemMessage

from src.services.chat_model_factory import get_chat_model

logger = logging.getLogger(__name__)


CONFESSION_REPORT_VERSION = "confession_report_v1"

_ALLOWED_SEVERITIES = {"info", "warning", "error"}
_ALLOWED_IMPACT_AREAS = {"score", "rubric_parse", "evidence", "reference", "format"}
_ALLOWED_OBJECTIVE_TAGS = {"fully_complied", "partially_complied", "violated", "unsure"}

# Rubric parse issue types currently produced by rubric_parser._generate_parse_confession
_RUBRIC_ISSUE_TYPES = {
    "question_count_mismatch",
    "score_mismatch",
    "total_score_mismatch",
    "missing_scoring_points",
    "invalid_score",
    "scoring_points_mismatch",
    "low_confidence",
    "missing_standard_answer",
    "rubric_risk",
    "rubric_uncertainty",
    "rubric_blind_spot",
}

# Grading issue types (used by the confession report for post-grading triage)
_GRADING_ISSUE_TYPES = {
    "missing_evidence_awarded_positive",
    "missing_evidence",
    "missing_rubric_reference",
    "score_out_of_bounds",
    "point_sum_mismatch",
    "low_confidence",
    "full_marks_low_confidence",
    "zero_marks_low_confidence",
    "alternative_solution_used",
    "missing_scoring_points",
    "score_adjusted",
    "missing_point_id",
}


def _clamp01(value: Any, default: float = 0.0) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def _trim_text(value: Any, limit: int) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\r\n", "\n").strip()
    if limit <= 0:
        return text
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def _severity_rank(sev: str) -> int:
    if sev == "error":
        return 3
    if sev == "warning":
        return 2
    return 1


def _is_placeholder_evidence(evidence: Any) -> bool:
    if evidence is None:
        return True
    text = str(evidence).strip()
    if not text:
        return True
    lowered = text.lower()
    placeholders = [
        "未找到",
        "找不到",
        "n/a",
        "null",
        "none",
        "无法",
        "看不清",
        "不清楚",
    ]
    return any(p in lowered for p in placeholders) or "【原文引用】未找到" in text


def _extract_json_block(text: str) -> str:
    if not text:
        return "{}"
    t = str(text).strip()
    # ```json ... ```
    m = re.search(r"```json\s*\n(.*?)\n```", t, re.DOTALL)
    if m:
        return m.group(1).strip()
    # ``` ... ``` (may still contain JSON)
    m = re.search(r"```\s*\n(.*?)\n```", t, re.DOTALL)
    if m:
        candidate = m.group(1).strip()
        if candidate.startswith("{") or candidate.startswith("["):
            return candidate
    # Heuristic: first balanced object/array.
    start = t.find("{")
    if start == -1:
        start = t.find("[")
    if start == -1:
        return "{}"
    start_char = t[start]
    end_char = "}" if start_char == "{" else "]"
    depth = 0
    for i in range(start, len(t)):
        ch = t[i]
        if ch == start_char:
            depth += 1
        elif ch == end_char:
            depth -= 1
            if depth == 0:
                return t[start : i + 1].strip()
    return t[start:].strip()


def _escape_invalid_backslashes(text: str) -> str:
    return re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", text)


def _strip_control_chars(text: str) -> str:
    cleaned = re.sub(r"[\x00-\x1F]", " ", text)
    return re.sub(r"[\u2028\u2029]", " ", cleaned)


def _load_json_with_repair(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    raw = text.strip()
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        repaired = _escape_invalid_backslashes(raw)
        repaired = _strip_control_chars(repaired)
        # Drop trailing commas before closing brackets/braces.
        repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
        try:
            parsed = json.loads(repaired, strict=False)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None


def _allowed_issue_types(scope: str) -> set[str]:
    if scope == "rubric":
        return set(_RUBRIC_ISSUE_TYPES)
    return set(_GRADING_ISSUE_TYPES)


def _postprocess_items(
    items: Iterable[Any],
    *,
    scope: str,
    max_items: int,
) -> List[Dict[str, Any]]:
    allowed_types = _allowed_issue_types(scope)
    seen: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

    def normalize_item(raw: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(raw, dict):
            return None
        issue_type = str(raw.get("issue_type") or raw.get("issueType") or "").strip()
        if issue_type not in allowed_types:
            return None
        severity = str(raw.get("severity") or "").strip().lower()
        if severity not in _ALLOWED_SEVERITIES:
            return None

        question_id = raw.get("question_id") or raw.get("questionId") or ""
        point_id = raw.get("point_id") or raw.get("pointId") or ""
        question_id = str(question_id).strip() if question_id is not None else ""
        point_id = str(point_id).strip() if point_id is not None else ""

        refs_raw = raw.get("refs") or {}
        if not isinstance(refs_raw, dict):
            refs_raw = {}
        page_indices = refs_raw.get("page_indices") or refs_raw.get("pageIndices") or []
        normalized_pages: List[int] = []
        if isinstance(page_indices, (list, tuple)):
            for p in page_indices:
                try:
                    pv = int(p)
                except (TypeError, ValueError):
                    continue
                if pv < 0:
                    continue
                normalized_pages.append(pv)
        evidence_excerpt = _trim_text(
            refs_raw.get("evidence_excerpt") or refs_raw.get("evidenceExcerpt"), 160
        )
        rubric_ref_excerpt = _trim_text(
            refs_raw.get("rubric_ref_excerpt") or refs_raw.get("rubricRefExcerpt"),
            160,
        )
        if not normalized_pages and not evidence_excerpt and not rubric_ref_excerpt:
            return None

        impact_raw = raw.get("impact") or {}
        if not isinstance(impact_raw, dict):
            impact_raw = {}
        impact_area = str(impact_raw.get("impact_area") or impact_raw.get("impactArea") or "").strip()
        if impact_area not in _ALLOWED_IMPACT_AREAS:
            # Default to a conservative area to avoid dropping useful items.
            impact_area = "format"
        max_delta_points = impact_raw.get("max_delta_points") or impact_raw.get("maxDeltaPoints")
        try:
            max_delta_points = float(max_delta_points) if max_delta_points is not None else None
        except (TypeError, ValueError):
            max_delta_points = None

        action = _trim_text(raw.get("action"), 240)
        action = action.replace("\n", " ").strip()
        if not action:
            return None

        return {
            "issue_type": issue_type,
            "severity": severity,
            "question_id": question_id or None,
            "point_id": point_id or None,
            "refs": {
                **({"page_indices": sorted(set(normalized_pages))} if normalized_pages else {}),
                **({"evidence_excerpt": evidence_excerpt} if evidence_excerpt else {}),
                **({"rubric_ref_excerpt": rubric_ref_excerpt} if rubric_ref_excerpt else {}),
            },
            "impact": {
                **({"max_delta_points": max_delta_points} if max_delta_points is not None else {}),
                "impact_area": impact_area,
            },
            "action": action,
        }

    for raw in items or []:
        normalized = normalize_item(raw)
        if not normalized:
            continue
        key = (
            normalized["issue_type"],
            normalized.get("question_id") or "",
            normalized.get("point_id") or "",
        )
        prev = seen.get(key)
        if prev is None or _severity_rank(normalized["severity"]) > _severity_rank(prev["severity"]):
            seen[key] = normalized

    merged = list(seen.values())
    merged.sort(
        key=lambda x: (
            -_severity_rank(x.get("severity", "info")),
            -float((x.get("impact", {}) or {}).get("max_delta_points") or 0.0),
        )
    )
    if max_items > 0:
        merged = merged[:max_items]
    return merged


def _compute_risk_score(items: List[Dict[str, Any]]) -> float:
    errors = sum(1 for i in items if i.get("severity") == "error")
    warnings = sum(1 for i in items if i.get("severity") == "warning")
    if errors:
        return min(1.0, 0.35 + 0.12 * errors + 0.04 * warnings)
    if warnings:
        return min(1.0, 0.10 + 0.06 * warnings)
    return 0.05 if items else 0.0


def postprocess_confession_report(
    raw: Any,
    *,
    scope: str,
    subject_id: str,
    max_items: int,
) -> Dict[str, Any]:
    """
    Normalize and hard-filter a raw model output into ConfessionReport v1.
    Never raises.
    """
    data = raw if isinstance(raw, dict) else {}
    objectives_raw = data.get("objectives") or []
    objectives: List[Dict[str, Any]] = []
    if isinstance(objectives_raw, list):
        for idx, obj in enumerate(objectives_raw[:12]):
            if isinstance(obj, str):
                objectives.append(
                    {
                        "id": f"obj_{idx+1:02d}",
                        "objective": _trim_text(obj, 160),
                        "tag": "unsure",
                        "notes": "",
                        "refs": [],
                    }
                )
                continue
            if not isinstance(obj, dict):
                continue
            tag = str(obj.get("tag") or "").strip()
            if tag not in _ALLOWED_OBJECTIVE_TAGS:
                tag = "unsure"
            objectives.append(
                {
                    "id": str(obj.get("id") or f"obj_{idx+1:02d}"),
                    "objective": _trim_text(obj.get("objective") or obj.get("goal") or "", 200),
                    "tag": tag,
                    "notes": _trim_text(obj.get("notes") or "", 240),
                    "refs": obj.get("refs") if isinstance(obj.get("refs"), list) else [],
                }
            )

    items = _postprocess_items(data.get("items") or [], scope=scope, max_items=max_items)

    risk_score = _clamp01(
        data.get("risk_score") or data.get("riskScore"),
        default=_compute_risk_score(items),
    )
    overall_confidence = _clamp01(
        data.get("overall_confidence") or data.get("overallConfidence"),
        default=max(0.1, 1.0 - min(0.9, risk_score)),
    )
    if items and overall_confidence > 0.95:
        overall_confidence = 0.95

    report = {
        "version": CONFESSION_REPORT_VERSION,
        "scope": scope,
        "subject_id": subject_id,
        "overall_confidence": overall_confidence,
        "risk_score": risk_score,
        "objectives": objectives,
        "items": items,
        "budget": {"max_items": max_items, "emitted_items": len(items)},
        "generated_at": datetime.now().isoformat(),
    }
    return report


def should_trigger_logic_review_from_confession(report: Any) -> bool:
    if not isinstance(report, dict):
        return True  # conservative default: if missing, allow downstream review
    risk_score = _clamp01(report.get("risk_score") or report.get("riskScore"), default=0.0)
    items = report.get("items") if isinstance(report.get("items"), list) else []
    has_error = any(isinstance(i, dict) and i.get("severity") == "error" for i in items)
    warnings = sum(1 for i in items if isinstance(i, dict) and i.get("severity") == "warning")
    risk_th = float(os.getenv("CONFESSION_LOGIC_REVIEW_RISK_THRESHOLD", "0.30"))
    warn_th = int(os.getenv("CONFESSION_LOGIC_REVIEW_WARNING_THRESHOLD", "3"))
    return risk_score >= risk_th or has_error or warnings >= warn_th


def _confession_schema_hint() -> str:
    # Keep this short: it will be embedded in the prompt.
    schema = {
        "version": CONFESSION_REPORT_VERSION,
        "scope": "grading",
        "subject_id": "student_key_or_batch_id",
        "overall_confidence": 0.0,
        "risk_score": 0.0,
        "objectives": [
            {
                "id": "obj_01",
                "objective": "string",
                "tag": "fully_complied|partially_complied|violated|unsure",
                "notes": "string",
                "refs": [],
            }
        ],
        "items": [
            {
                "issue_type": "missing_evidence_awarded_positive",
                "severity": "error|warning|info",
                "question_id": "string",
                "point_id": "string",
                "refs": {
                    "page_indices": [1, 2],
                    "evidence_excerpt": "string",
                    "rubric_ref_excerpt": "string",
                },
                "impact": {"max_delta_points": 1, "impact_area": "evidence"},
                "action": "one actionable sentence",
            }
        ],
        "budget": {"max_items": 25, "emitted_items": 3},
        "generated_at": "2026-02-10T00:00:00",
    }
    return json.dumps(schema, ensure_ascii=False, indent=2)


_CONFESSION_SYSTEM_PROMPT = """你是 Confession Auditor（自白审计员）。
你的唯一目标：生成“诚实披露 + 复核清单”的自白报告（confession_report）。

重要原则（必须遵守）：
0) 本报告不会用于惩罚主输出：不自动改分、不补写答案/标准；只用于触发复核与队列排序。
1) 奖励诚实：承认不确定/证据不足不会被惩罚；不要为了显得确定而猜测。
2) 惩罚不诚实：如果输入事实显示存在明显问题而你未披露/轻描淡写，将被视为不诚实（风险分将上调，复核优先级提高）。
3) 禁止臆测：只能基于输入的结构化事实与摘录，不能补写学生答案或补全评分标准。
4) 低噪音：只输出可核验、可定位、可执行的一句话复核动作；避免空泛表述。
5) 输出格式：只能输出 JSON（不要 markdown / 不要代码块 / 不要额外文本）。
"""


def _build_rubric_context(parsed_rubric: Dict[str, Any]) -> str:
    max_questions = int(os.getenv("CONFESSION_RUBRIC_MAX_QUESTIONS", "30"))
    max_points_per_q = int(os.getenv("CONFESSION_RUBRIC_MAX_POINTS_PER_QUESTION", "6"))

    questions = parsed_rubric.get("questions") or []
    if not isinstance(questions, list):
        questions = []
    total_questions = parsed_rubric.get("total_questions") or len(questions)
    total_score = parsed_rubric.get("total_score") or 0

    lines: List[str] = []
    lines.append("## Rubric Summary")
    lines.append(f"- total_questions: {total_questions}")
    lines.append(f"- total_score: {total_score}")

    parse_confession = parsed_rubric.get("parse_confession") or {}
    if isinstance(parse_confession, dict) and parse_confession:
        lines.append("")
        lines.append("## Rule-Based Parse Report (parse_confession)")
        lines.append(
            f"- overallStatus: {parse_confession.get('overallStatus') or parse_confession.get('overall_status')}"
        )
        lines.append(
            f"- overallConfidence: {parse_confession.get('overallConfidence') or parse_confession.get('overall_confidence')}"
        )
        summary = parse_confession.get("summary") or ""
        if summary:
            lines.append(f"- summary: {_trim_text(summary, 260)}")

        issues = parse_confession.get("issues") or []
        if isinstance(issues, list) and issues:
            lines.append("")
            lines.append("### issues (top)")
            for issue in issues[:12]:
                if not isinstance(issue, dict):
                    continue
                lines.append(
                    f"- type={issue.get('type')} severity={issue.get('severity')} "
                    f"Q={issue.get('questionId') or issue.get('question_id') or ''} "
                    f"msg={_trim_text(issue.get('message') or '', 220)}"
                )

    lines.append("")
    lines.append("## Questions (abridged)")
    for q in questions[:max_questions]:
        if not isinstance(q, dict):
            continue
        qid = str(q.get("question_id") or q.get("id") or "?")
        max_score = q.get("max_score")
        scoring_points = q.get("scoring_points") or []
        if not isinstance(scoring_points, list):
            scoring_points = []
        lines.append(f"- Q{qid}: max_score={max_score} scoring_points={len(scoring_points)}")
        for sp in scoring_points[:max_points_per_q]:
            if not isinstance(sp, dict):
                continue
            pid = sp.get("point_id") or sp.get("pointId") or ""
            desc = _trim_text(sp.get("description") or "", 80)
            score = sp.get("score")
            lines.append(f"  - [{pid}] {desc} ({score})")
    return "\n".join(lines)


def _build_grading_context(
    student: Dict[str, Any],
    *,
    batch_id: Optional[str] = None,
    subject: Optional[str] = None,
) -> str:
    """
    Build a compact, facts-only context for the grading confession report.
    Must not rely on (or require) legacy audit/self_critique fields.
    """

    max_questions = int(os.getenv("CONFESSION_GRADING_MAX_QUESTIONS", "12"))
    max_points = int(os.getenv("CONFESSION_GRADING_MAX_POINTS", "12"))
    max_excerpt = int(os.getenv("CONFESSION_GRADING_MAX_EXCERPT_CHARS", "120"))
    conf_th = float(os.getenv("CONFESSION_GRADING_FLAG_CONFIDENCE_THRESHOLD", "0.7"))

    student_key = student.get("student_key") or student.get("student_name") or "Student"
    total_score = student.get("total_score") or student.get("score") or 0
    max_total = student.get("max_total_score") or student.get("max_score") or 0
    grading_mode = student.get("grading_mode") or student.get("gradingMode") or ""

    details = student.get("question_details") or []
    if not isinstance(details, list):
        details = []

    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _iter_points(q: Dict[str, Any]) -> List[Dict[str, Any]]:
        spr_list = q.get("scoring_point_results") or q.get("scoring_results") or []
        return spr_list if isinstance(spr_list, list) else []

    def _question_flags(q: Dict[str, Any]) -> List[str]:
        flags: List[str] = []
        score = _safe_float(q.get("score"), 0.0)
        max_score = _safe_float(q.get("max_score") or q.get("maxScore"), 0.0)
        confidence = _safe_float(q.get("confidence"), 1.0)

        if max_score > 0 and score >= max_score:
            flags.append("full_marks")
        if max_score > 0 and score <= 0:
            flags.append("zero_marks")
        if confidence < conf_th:
            flags.append("low_confidence")
        if max_score > 0 and (score < -1e-6 or score - max_score > 1e-6):
            flags.append("score_out_of_bounds")

        points = _iter_points(q)
        if max_score > 0 and not points:
            flags.append("missing_scoring_points")

        missing_evidence_awarded = 0
        missing_rubric_ref = 0
        point_sum = 0.0
        for spr in points:
            if not isinstance(spr, dict):
                continue
            awarded = _safe_float(spr.get("awarded", spr.get("score", 0)) or 0, 0.0)
            point_sum += awarded
            evidence = spr.get("evidence") or ""
            rubric_ref = spr.get("rubric_reference") or spr.get("rubricReference") or ""
            if awarded > 0 and _is_placeholder_evidence(evidence):
                missing_evidence_awarded += 1
            if not str(rubric_ref).strip():
                missing_rubric_ref += 1
            if not str(spr.get("point_id") or spr.get("pointId") or "").strip():
                flags.append("missing_point_id")

        if missing_evidence_awarded:
            flags.append("missing_evidence_awarded_positive")
        if missing_rubric_ref:
            flags.append("missing_rubric_reference")
        if points and abs(point_sum - score) > 0.1:
            flags.append("point_sum_mismatch")

        if q.get("used_alternative_solution") or q.get("usedAlternativeSolution"):
            flags.append("alternative_solution_used")

        # De-dupe but keep order
        seen = set()
        ordered: List[str] = []
        for f in flags:
            if f in seen:
                continue
            ordered.append(f)
            seen.add(f)
        return ordered

    def is_flagged(q: Dict[str, Any]) -> bool:
        flags = _question_flags(q)
        watch = {
            "missing_evidence_awarded_positive",
            "missing_scoring_points",
            "missing_rubric_reference",
            "score_out_of_bounds",
            "point_sum_mismatch",
            "low_confidence",
            "missing_point_id",
            "alternative_solution_used",
            "full_marks",
            "zero_marks",
        }
        return any(f in watch for f in flags)

    flagged = [q for q in details if isinstance(q, dict) and is_flagged(q)]

    def sort_key(q: Dict[str, Any]) -> Tuple[float, int]:
        c = _safe_float(q.get("confidence"), 1.0)
        flags = _question_flags(q)
        # Lower confidence first; more flags first.
        return (c, -len(flags))

    flagged.sort(key=sort_key)

    # Aggregate quick stats (low-noise; helps the auditor pick priorities).
    stats = {
        "questions": 0,
        "flagged_questions": 0,
        "low_confidence": 0,
        "missing_evidence_awarded_positive": 0,
        "missing_rubric_reference": 0,
        "point_sum_mismatch": 0,
        "score_out_of_bounds": 0,
    }
    for q in details:
        if not isinstance(q, dict):
            continue
        stats["questions"] += 1
        flags = _question_flags(q)
        if any(flags):
            pass
        if is_flagged(q):
            stats["flagged_questions"] += 1
        if "low_confidence" in flags:
            stats["low_confidence"] += 1
        if "missing_evidence_awarded_positive" in flags:
            stats["missing_evidence_awarded_positive"] += 1
        if "missing_rubric_reference" in flags:
            stats["missing_rubric_reference"] += 1
        if "point_sum_mismatch" in flags:
            stats["point_sum_mismatch"] += 1
        if "score_out_of_bounds" in flags:
            stats["score_out_of_bounds"] += 1

    lines: List[str] = []
    lines.append("## Student Summary")
    lines.append(f"- student_key: {student_key}")
    lines.append(f"- total_score: {total_score}")
    lines.append(f"- max_total_score: {max_total}")
    if grading_mode:
        lines.append(f"- grading_mode: {grading_mode}")
    if batch_id:
        lines.append(f"- batch_id: {batch_id}")
    if subject:
        lines.append(f"- subject: {subject}")

    lines.append("")
    lines.append("## Quick Stats (rule-based)")
    lines.append(json.dumps(stats, ensure_ascii=False))

    # Optional: memory hints (historical patterns). Keep it short and non-prescriptive.
    try:
        if batch_id:
            from src.services.grading_memory import get_memory_service

            memory_service = get_memory_service()
            memory_context = memory_service.generate_confession_context(
                [q for q in details if isinstance(q, dict)],
                batch_id=batch_id,
                subject=subject,
            )
            memory_prompt = memory_service.format_confession_memory_prompt(memory_context)
            if memory_prompt:
                lines.append("")
                lines.append(memory_prompt)
    except Exception as exc:
        logger.debug(f"[confession_auditor] memory hint skipped: {exc}")

    lines.append("")
    lines.append("## Flagged Questions (facts only; abridged)")
    emitted_points = 0
    for q in flagged[:max_questions]:
        qid = str(q.get("question_id") or q.get("questionId") or "?")
        score = q.get("score")
        max_score = q.get("max_score") or q.get("maxScore")
        confidence = q.get("confidence")
        page_indices = q.get("page_indices") or q.get("pageIndices") or q.get("source_pages") or q.get("sourcePages") or []
        if not isinstance(page_indices, list):
            page_indices = [page_indices] if page_indices is not None else []
        try:
            pages = sorted(set(int(p) for p in page_indices if p is not None))
        except Exception:
            pages = []

        flags = _question_flags(q)
        lines.append(f"- Q{qid}: score={score}/{max_score} confidence={confidence}")
        if pages:
            lines.append(f"  page_indices: {pages}")
        if flags:
            lines.append(f"  flags: {', '.join(flags[:10])}")

        spr_list = _iter_points(q)
        selected_spr: List[Dict[str, Any]] = []
        for spr in spr_list:
            if not isinstance(spr, dict):
                continue
            awarded = _safe_float(spr.get("awarded", spr.get("score", 0)) or 0, 0.0)
            rubric_ref = spr.get("rubric_reference") or spr.get("rubricReference") or ""
            evidence = spr.get("evidence") or ""
            if awarded > 0 or _is_placeholder_evidence(evidence) or not str(rubric_ref).strip():
                selected_spr.append(spr)
        if selected_spr:
            lines.append("  scoring_point_results:")
            for spr in selected_spr:
                if emitted_points >= max_points:
                    break
                emitted_points += 1
                pid = spr.get("point_id") or spr.get("pointId") or ""
                awarded = spr.get("awarded", spr.get("score", 0))
                max_points_val = spr.get("max_points") or spr.get("maxPoints") or spr.get("max_score") or spr.get("maxScore") or 0
                evidence = _trim_text(spr.get("evidence") or "", max_excerpt)
                rubric_ref = _trim_text(
                    spr.get("rubric_reference") or spr.get("rubricReference") or "",
                    max_excerpt,
                )
                lines.append(
                    f"    - {pid}: {awarded}/{max_points_val} evidence={evidence} rubric_ref={rubric_ref}"
                )
    return "\n".join(lines)


def _build_user_prompt(*, scope: str, subject_id: str, context: str, max_items: int) -> str:
    issue_types = sorted(_RUBRIC_ISSUE_TYPES if scope == "rubric" else _GRADING_ISSUE_TYPES)

    return f"""你将收到一段“结构化事实与摘录”（不含原图）。请生成 confession_report（自白报告），用于复核与排序。

## 输出要求（强约束）
- 只能输出 JSON，不要任何额外文本
- 每条 items 必须包含：issue_type, severity, refs(至少一种), impact, action（action 一句话）
- issue_type 必须从允许列表中选择
- 严格控制噪音：最多输出 {max_items} 条 items，优先输出 error/warning

## 允许的 issue_type 列表
{", ".join(issue_types)}

## ConfessionReport JSON Schema Hint
{_confession_schema_hint()}

## Context
scope={scope}
subject_id={subject_id}
max_items={max_items}

{context}
"""


def _normalize_page_indices(value: Any) -> List[int]:
    if value is None:
        return []
    raw = value
    if not isinstance(raw, list):
        raw = [raw]
    pages: List[int] = []
    for item in raw:
        try:
            pv = int(item)
        except (TypeError, ValueError):
            continue
        if pv < 0:
            continue
        pages.append(pv)
    # Dedup while preserving order.
    seen = set()
    ordered: List[int] = []
    for p in pages:
        if p in seen:
            continue
        ordered.append(p)
        seen.add(p)
    return ordered


def _compute_grading_mandatory_items(student: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Deterministic checks for "obvious" issues. Used for:
    - LLM fallback (no API key / model failure)
    - Dishonesty penalty (if the model omitted obvious issues)
    """

    max_excerpt = int(os.getenv("CONFESSION_GRADING_MAX_EXCERPT_CHARS", "120"))
    conf_th = float(os.getenv("CONFESSION_GRADING_FLAG_CONFIDENCE_THRESHOLD", "0.7"))

    details = student.get("question_details") or []
    if not isinstance(details, list):
        details = []

    def safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    mandatory: List[Dict[str, Any]] = []
    for q in details:
        if not isinstance(q, dict):
            continue
        qid = str(q.get("question_id") or q.get("questionId") or "").strip()
        if not qid:
            continue
        score = safe_float(q.get("score"), 0.0)
        max_score = safe_float(q.get("max_score") or q.get("maxScore"), 0.0)
        confidence = _clamp01(q.get("confidence"), default=1.0)

        page_indices = _normalize_page_indices(
            q.get("page_indices")
            or q.get("pageIndices")
            or q.get("source_pages")
            or q.get("sourcePages")
        )

        points = q.get("scoring_point_results") or q.get("scoring_results") or []
        if not isinstance(points, list):
            points = []

        if max_score > 0 and (score < -1e-6 or score - max_score > 1e-6):
            mandatory.append(
                {
                    "issue_type": "score_out_of_bounds",
                    "severity": "error",
                    "question_id": qid,
                    "point_id": None,
                    "refs": {
                        **({"page_indices": page_indices} if page_indices else {}),
                        "evidence_excerpt": f"score={score} max_score={max_score}",
                    },
                    "impact": {
                        "impact_area": "score",
                        "max_delta_points": abs(score - max(0.0, min(max_score, score))),
                    },
                    "action": "核对该题得分是否越界（<0或>满分）；必要时修正为合法范围并记录原因",
                }
            )

        if max_score > 0 and not points:
            mandatory.append(
                {
                    "issue_type": "missing_scoring_points",
                    "severity": "warning",
                    "question_id": qid,
                    "point_id": None,
                    "refs": {
                        **({"page_indices": page_indices} if page_indices else {}),
                        "evidence_excerpt": "question has no scoring_point_results",
                    },
                    "impact": {"impact_area": "format"},
                    "action": "补齐该题的得分点明细（scoring_point_results），缺失部分默认为0分并给出证据占位",
                }
            )

        point_sum = 0.0
        for spr in points:
            if not isinstance(spr, dict):
                continue
            pid = str(spr.get("point_id") or spr.get("pointId") or "").strip()
            awarded = safe_float(spr.get("awarded", spr.get("score", 0)) or 0, 0.0)
            point_sum += awarded
            evidence = spr.get("evidence") or ""
            rubric_ref = spr.get("rubric_reference") or spr.get("rubricReference") or ""

            if awarded > 0 and _is_placeholder_evidence(evidence):
                mandatory.append(
                    {
                        "issue_type": "missing_evidence_awarded_positive",
                        "severity": "error",
                        "question_id": qid,
                        "point_id": pid or None,
                        "refs": {
                            **({"page_indices": page_indices} if page_indices else {}),
                            "evidence_excerpt": _trim_text(evidence, max_excerpt),
                            "rubric_ref_excerpt": _trim_text(rubric_ref, max_excerpt),
                        },
                        "impact": {"impact_area": "evidence", "max_delta_points": awarded},
                        "action": "核对该得分点的原文证据是否真实存在；若不存在则该点不得分",
                    }
                )
            elif _is_placeholder_evidence(evidence):
                mandatory.append(
                    {
                        "issue_type": "missing_evidence",
                        "severity": "warning",
                        "question_id": qid,
                        "point_id": pid or None,
                        "refs": {
                            **({"page_indices": page_indices} if page_indices else {}),
                            "evidence_excerpt": _trim_text(evidence, max_excerpt),
                            "rubric_ref_excerpt": _trim_text(rubric_ref, max_excerpt),
                        },
                        "impact": {"impact_area": "evidence"},
                        "action": "核对该得分点是否有可核验原文证据；若无则保持0分并补充说明",
                    }
                )

            if not str(rubric_ref).strip():
                mandatory.append(
                    {
                        "issue_type": "missing_rubric_reference",
                        "severity": "warning",
                        "question_id": qid,
                        "point_id": pid or None,
                        "refs": {
                            **({"page_indices": page_indices} if page_indices else {}),
                            "evidence_excerpt": _trim_text(evidence, max_excerpt),
                        },
                        "impact": {"impact_area": "reference"},
                        "action": "补充该得分点对应的评分标准引用（rubric_reference）以便复核",
                    }
                )

            if not pid:
                mandatory.append(
                    {
                        "issue_type": "missing_point_id",
                        "severity": "warning",
                        "question_id": qid,
                        "point_id": None,
                        "refs": {
                            **({"page_indices": page_indices} if page_indices else {}),
                            "evidence_excerpt": _trim_text(evidence, max_excerpt),
                        },
                        "impact": {"impact_area": "format"},
                        "action": "为该得分点补齐 point_id（需与评分标准编号一致）以便定位复核",
                    }
                )

        if points and abs(point_sum - score) > 0.1:
            severity = "error" if abs(point_sum - score) >= 1.0 else "warning"
            mandatory.append(
                {
                    "issue_type": "point_sum_mismatch",
                    "severity": severity,
                    "question_id": qid,
                    "point_id": None,
                    "refs": {
                        **({"page_indices": page_indices} if page_indices else {}),
                        "evidence_excerpt": f"point_sum={point_sum:.2f} question_score={score:.2f}",
                    },
                    "impact": {
                        "impact_area": "score",
                        "max_delta_points": abs(point_sum - score),
                    },
                    "action": "核对该题各得分点 awarded 之和是否等于题目总分；必要时按得分点重算总分",
                }
            )

        if confidence < conf_th:
            mandatory.append(
                {
                    "issue_type": "low_confidence",
                    "severity": "warning",
                    "question_id": qid,
                    "point_id": None,
                    "refs": {**({"page_indices": page_indices} if page_indices else {})},
                    "impact": {"impact_area": "score"},
                    "action": "优先复核该题给分与证据引用是否一致；必要时人工确认",
                }
            )
        if max_score > 0 and score >= max_score and confidence < conf_th:
            mandatory.append(
                {
                    "issue_type": "full_marks_low_confidence",
                    "severity": "warning",
                    "question_id": qid,
                    "point_id": None,
                    "refs": {**({"page_indices": page_indices} if page_indices else {})},
                    "impact": {"impact_area": "score"},
                    "action": "该题满分但置信度偏低：请逐点核对证据与标准是否完全匹配",
                }
            )
        if max_score > 0 and score <= 0 and confidence < conf_th:
            mandatory.append(
                {
                    "issue_type": "zero_marks_low_confidence",
                    "severity": "warning",
                    "question_id": qid,
                    "point_id": None,
                    "refs": {**({"page_indices": page_indices} if page_indices else {})},
                    "impact": {"impact_area": "score"},
                    "action": "该题0分但置信度偏低：请核对是否漏判有效步骤或证据位置",
                }
            )

        if q.get("used_alternative_solution") or q.get("usedAlternativeSolution"):
            mandatory.append(
                {
                    "issue_type": "alternative_solution_used",
                    "severity": "info",
                    "question_id": qid,
                    "point_id": None,
                    "refs": {**({"page_indices": page_indices} if page_indices else {})},
                    "impact": {"impact_area": "score"},
                    "action": "确认该题采用的另类解法是否满足评分标准要求并与给分一致",
                }
            )

    return mandatory


def _apply_honesty_penalty(
    report: Dict[str, Any],
    *,
    student: Dict[str, Any],
    max_items: int,
) -> Dict[str, Any]:
    """
    Ensure "reward honesty / penalize dishonesty" without changing grades:
    - Add obvious missing issues the model should have disclosed (mandatory items)
    - Increase risk_score when omissions are detected
    - Emit a compact honesty summary for review queue sorting
    """
    if not isinstance(report, dict):
        return report

    mandatory = _compute_grading_mandatory_items(student)
    mandatory_norm = _postprocess_items(mandatory, scope="grading", max_items=max_items * 4)

    existing_items = report.get("items") if isinstance(report.get("items"), list) else []
    existing_norm = _postprocess_items(existing_items, scope="grading", max_items=max_items * 4)

    def key(item: Dict[str, Any]) -> Tuple[str, str, str]:
        return (
            str(item.get("issue_type") or ""),
            str(item.get("question_id") or ""),
            str(item.get("point_id") or ""),
        )

    existing_keys = {key(i) for i in existing_norm if isinstance(i, dict)}
    omitted = [i for i in mandatory_norm if key(i) not in existing_keys]

    merged_items = existing_norm + omitted
    final_items = _postprocess_items(merged_items, scope="grading", max_items=max_items)

    total_weight = 0.0
    omitted_weight = 0.0
    omitted_errors = 0
    for i in mandatory_norm:
        if not isinstance(i, dict):
            continue
        sev = i.get("severity") or "info"
        w = 2.0 if sev == "error" else 1.0 if sev == "warning" else 0.5
        total_weight += w
        if key(i) in {key(x) for x in omitted}:
            omitted_weight += w
            if sev == "error":
                omitted_errors += 1

    honesty_score = 1.0
    if total_weight > 0:
        honesty_score = max(0.0, min(1.0, 1.0 - (omitted_weight / total_weight)))

    if honesty_score >= 0.95:
        honesty_grade = "A"
    elif honesty_score >= 0.85:
        honesty_grade = "B"
    elif honesty_score >= 0.70:
        honesty_grade = "C"
    elif honesty_score >= 0.55:
        honesty_grade = "D"
    else:
        honesty_grade = "F"

    base_risk = _compute_risk_score(final_items)
    # Dishonesty penalty: small but meaningful; prioritise omitted errors.
    penalty = min(0.35, 0.05 * len(omitted) + 0.08 * omitted_errors)
    risk_score = _clamp01(max(base_risk, report.get("risk_score") or 0.0) + penalty, default=base_risk)
    overall_confidence = _clamp01(
        report.get("overall_confidence") or report.get("overallConfidence"),
        default=max(0.1, 1.0 - min(0.9, risk_score)),
    )
    if final_items and overall_confidence > 0.95:
        overall_confidence = 0.95

    omitted_keys_preview = []
    for item in omitted[:5]:
        omitted_keys_preview.append(
            {
                "issue_type": item.get("issue_type"),
                "question_id": item.get("question_id"),
                "point_id": item.get("point_id"),
                "severity": item.get("severity"),
            }
        )

    report = dict(report)
    report["items"] = final_items
    report["budget"] = {"max_items": max_items, "emitted_items": len(final_items)}
    report["risk_score"] = risk_score
    report["overall_confidence"] = overall_confidence
    report["honesty"] = {
        "score": honesty_score,
        "grade": honesty_grade,
        "mandatory_issue_count": len(mandatory_norm),
        "omitted_mandatory_issue_count": len(omitted),
        "omitted_keys_preview": omitted_keys_preview,
        "penalty_risk_score_delta": penalty,
    }

    # Ensure at least one objective reflecting honesty/disclosure.
    objectives = report.get("objectives") if isinstance(report.get("objectives"), list) else []
    if not objectives:
        objectives = []
    objectives = list(objectives)[:11]
    objectives.append(
        {
            "id": "obj_honesty",
            "objective": "如存在明显问题/不确定性，必须披露并给出可执行复核动作（不披露视为不诚实）",
            "tag": "violated" if omitted else "fully_complied",
            "notes": (
                f"omitted_mandatory={len(omitted)}/{len(mandatory_norm)}"
                if mandatory_norm
                else "no mandatory issues detected"
            ),
            "refs": [],
        }
    )
    report["objectives"] = objectives[:12]
    return report


def _default_rule_based_report(
    *,
    scope: str,
    subject_id: str,
    parsed_rubric: Optional[Dict[str, Any]] = None,
    student: Optional[Dict[str, Any]] = None,
    max_items: int,
) -> Dict[str, Any]:
    """
    Deterministic fallback when the LLM call fails.
    Intentionally conservative and low-noise.
    """
    items: List[Dict[str, Any]] = []
    if scope == "rubric" and parsed_rubric:
        parse_confession = parsed_rubric.get("parse_confession") or {}
        issues = parse_confession.get("issues") if isinstance(parse_confession, dict) else None
        if isinstance(issues, list):
            for issue in issues[: max_items * 2]:
                if not isinstance(issue, dict):
                    continue
                issue_type = issue.get("type")
                if issue_type not in _RUBRIC_ISSUE_TYPES:
                    continue
                severity_raw = str(issue.get("severity") or "").lower()
                severity = (
                    "error"
                    if severity_raw in ("high", "error")
                    else "warning"
                    if severity_raw in ("medium", "warn", "warning")
                    else "info"
                )
                qid = str(issue.get("questionId") or issue.get("question_id") or "").strip()
                msg = _trim_text(issue.get("message") or "", 160)
                action = "请复核评分标准解析问题并修正相关字段"
                if issue_type in ("score_mismatch", "total_score_mismatch"):
                    action = "核对总分与各题满分之和是否一致；必要时修正总分或题目满分"
                elif issue_type == "missing_scoring_points":
                    action = "核对该题是否存在得分点列表；缺失则补齐拆分"
                elif issue_type == "scoring_points_mismatch":
                    action = "核对得分点分值之和是否等于题目满分；必要时修正分值"
                items.append(
                    {
                        "issue_type": issue_type,
                        "severity": severity,
                        "question_id": qid or None,
                        "point_id": None,
                        "refs": {"evidence_excerpt": msg},
                        "impact": {"impact_area": "rubric_parse"},
                        "action": action,
                    }
                )

    if scope == "grading" and student:
        items.extend(_compute_grading_mandatory_items(student))

    report = {
        "version": CONFESSION_REPORT_VERSION,
        "scope": scope,
        "subject_id": subject_id,
        "overall_confidence": 0.7,
        "risk_score": 0.35 if items else 0.0,
        "objectives": [],
        "items": _postprocess_items(items, scope=scope, max_items=max_items),
        "budget": {"max_items": max_items, "emitted_items": 0},
        "generated_at": datetime.now().isoformat(),
    }
    report["budget"]["emitted_items"] = len(report.get("items") or [])
    report["risk_score"] = _compute_risk_score(report.get("items") or [])
    report["overall_confidence"] = max(0.1, 1.0 - min(0.9, report["risk_score"]))
    if scope == "grading" and student:
        report = _apply_honesty_penalty(report, student=student, max_items=max_items)
    return report


class ConfessionAuditorClient:
    def __init__(
        self,
        *,
        api_key: str,
        model_name: Optional[str] = None,
        purpose: str = "analysis",
        temperature: float = 0.1,
        max_output_tokens: Optional[int] = None,
    ) -> None:
        self._api_key = api_key
        self._model_name = model_name or os.getenv("LLM_CONFESSION_MODEL")
        max_tokens = max_output_tokens
        if max_tokens is None:
            try:
                max_tokens = int(os.getenv("CONFESSION_MAX_OUTPUT_TOKENS", "1800"))
            except ValueError:
                max_tokens = 1800
        self._llm = get_chat_model(
            api_key=self._api_key,
            model_name=self._model_name,
            purpose=purpose,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

    async def _invoke(self, *, user_prompt: str) -> Dict[str, Any]:
        messages = [
            SystemMessage(content=_CONFESSION_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ]
        response = await self._llm.ainvoke(messages)
        content = response.content if hasattr(response, "content") else str(response)
        json_text = _extract_json_block(content)
        data = _load_json_with_repair(json_text)
        return data or {}

    async def rubric_confession_report(
        self,
        *,
        parsed_rubric: Dict[str, Any],
        subject_id: str,
    ) -> Dict[str, Any]:
        max_items = int(os.getenv("CONFESSION_RUBRIC_MAX_ITEMS", "12"))
        context = _build_rubric_context(parsed_rubric)
        user_prompt = _build_user_prompt(
            scope="rubric",
            subject_id=subject_id,
            context=context,
            max_items=max_items,
        )
        try:
            raw = await self._invoke(user_prompt=user_prompt)
            return postprocess_confession_report(
                raw, scope="rubric", subject_id=subject_id, max_items=max_items
            )
        except Exception as exc:
            logger.warning(f"[confession_auditor] rubric report failed: {exc}")
            return _default_rule_based_report(
                scope="rubric",
                subject_id=subject_id,
                parsed_rubric=parsed_rubric,
                max_items=max_items,
            )

    async def grading_confession_report(
        self,
        *,
        student: Dict[str, Any],
        subject_id: str,
        batch_id: Optional[str] = None,
        subject: Optional[str] = None,
    ) -> Dict[str, Any]:
        max_items = int(os.getenv("CONFESSION_GRADING_MAX_ITEMS", "25"))
        context = _build_grading_context(student, batch_id=batch_id, subject=subject)
        user_prompt = _build_user_prompt(
            scope="grading",
            subject_id=subject_id,
            context=context,
            max_items=max_items,
        )
        try:
            raw = await self._invoke(user_prompt=user_prompt)
            report = postprocess_confession_report(
                raw, scope="grading", subject_id=subject_id, max_items=max_items
            )
            return _apply_honesty_penalty(report, student=student, max_items=max_items)
        except Exception as exc:
            logger.warning(f"[confession_auditor] grading report failed: {exc}")
            return _default_rule_based_report(
                scope="grading",
                subject_id=subject_id,
                student=student,
                max_items=max_items,
            )
