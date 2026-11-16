"""Posthoc-only official PDF parser extracted unchanged from GradeOS.
See docs/provenance/reference-parser.json.
"""
from __future__ import annotations
import re
from pathlib import Path
from typing import Any

def _as_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None

def _reference_result_summary(path: Path) -> dict[str, Any]:
    from pypdf import PdfReader

    document = PdfReader(path)
    text = "\n".join(page.extract_text() or "" for page in document.pages)
    page_count = int(len(document.pages))

    normalized = re.sub(r"\s+", " ", text)

    def score_after(label: str) -> float | None:
        label_pattern = r"\s+".join(re.escape(part) for part in label.split())
        match = re.search(
            rf"(?i)\b{label_pattern}\s*[:：]\s*([0-9]+(?:\.[0-9]+)?)",
            normalized,
        )
        return _as_float(match.group(1)) if match else None

    subject_mark = score_after("Subject mark")
    paper_adjusted_mark = score_after("Paper adjusted mark")
    paper_group_adjusted_mark = score_after("Paper group adjusted mark")
    weighted_paper_mark = score_after("Weighted paper mark")

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    def is_score(value: str) -> bool:
        return bool(re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value))

    def is_question(value: str) -> bool:
        return bool(re.fullmatch(r"[1-9]\d*", value))

    def is_item(value: str) -> bool:
        return bool(re.fullmatch(r"[1-9]\d*(?:\([a-z]\))?(?:\([ivx]+\))?", value))

    items: list[dict[str, Any]] = []
    i = 0
    while i < len(lines):
        if lines[i] != "M1":
            i += 1
            continue

        i += 1
        current_question = ""
        current_panel = ""
        while i < len(lines):
            value = lines[i]
            if value.startswith("按查") or value in {"Question no.", "Candidate No.:"}:
                break
            row = value.split()
            if (
                len(row) == 5
                and is_question(row[0])
                and row[1] in {"1A", "1B"}
                and is_item(row[2])
                and is_score(row[3])
                and is_score(row[4])
            ):
                current_question = row[0]
                current_panel = row[1]
                items.append(
                    {
                        "question": current_question,
                        "panel": current_panel,
                        "item": row[2],
                        "max_mark": _as_float(row[3]),
                        "mark": _as_float(row[4]),
                    }
                )
                i += 1
                continue
            if (
                current_question
                and current_panel
                and len(row) == 3
                and is_item(row[0])
                and is_score(row[1])
                and is_score(row[2])
            ):
                items.append(
                    {
                        "question": current_question,
                        "panel": current_panel,
                        "item": row[0],
                        "max_mark": _as_float(row[1]),
                        "mark": _as_float(row[2]),
                    }
                )
                i += 1
                continue
            if (
                is_question(value)
                and i + 4 < len(lines)
                and lines[i + 1] in {"1A", "1B"}
                and is_item(lines[i + 2])
                and is_score(lines[i + 3])
                and is_score(lines[i + 4])
            ):
                current_question = value
                current_panel = lines[i + 1]
                items.append(
                    {
                        "question": current_question,
                        "panel": current_panel,
                        "item": lines[i + 2],
                        "max_mark": _as_float(lines[i + 3]),
                        "mark": _as_float(lines[i + 4]),
                    }
                )
                i += 5
                continue
            if (
                current_question
                and current_panel
                and is_item(value)
                and i + 2 < len(lines)
                and is_score(lines[i + 1])
                and is_score(lines[i + 2])
            ):
                items.append(
                    {
                        "question": current_question,
                        "panel": current_panel,
                        "item": value,
                        "max_mark": _as_float(lines[i + 1]),
                        "mark": _as_float(lines[i + 2]),
                    }
                )
                i += 3
                continue
            i += 1

    item_max_total = sum(_as_float(item.get("max_mark")) or 0.0 for item in items)
    item_awarded_total = sum(_as_float(item.get("mark")) or 0.0 for item in items)
    question_max_scores = _sum_items_by_question(items, "max_mark")
    question_awarded_scores = _sum_items_by_question(items, "mark")

    return {
        "pdf": str(path),
        "page_count": page_count,
        "subject_mark": subject_mark,
        "paper_adjusted_mark": paper_adjusted_mark,
        "paper_group_adjusted_mark": paper_group_adjusted_mark,
        "weighted_paper_mark": weighted_paper_mark,
        "item_count": len(items),
        "item_max_total": item_max_total,
        "item_awarded_total": item_awarded_total,
        "question_max_scores": question_max_scores,
        "question_awarded_scores": question_awarded_scores,
        "items": items,
    }

def _sum_items_by_question(items: list[dict[str, Any]], field: str) -> dict[str, float]:
    totals: dict[str, float] = {}
    for item in items:
        qid = _normalize_question_id(item.get("question"))
        value = _as_float(item.get(field))
        if not qid or value is None:
            continue
        totals[qid] = totals.get(qid, 0.0) + value
    return {
        qid: round(score, 6)
        for qid, score in sorted(
            totals.items(), key=lambda pair: _question_sort_key(pair[0])
        )
    }

def _normalize_question_id(value: Any) -> str:
    text = str(value or "").strip()
    match = re.match(r"^0*(\d+)(?:\b|[^0-9])", text)
    if match:
        return str(int(match.group(1)))
    return text

def _question_sort_key(value: Any) -> tuple[int, str]:
    normalized = _normalize_question_id(value)
    try:
        return (int(normalized), "")
    except (TypeError, ValueError):
        return (999, normalized)
