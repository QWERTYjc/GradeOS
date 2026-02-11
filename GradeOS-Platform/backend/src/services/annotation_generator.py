"""批注坐标生成服务

使用 VLM (Gemini) 分析答题图片，为批改结果生成精确的批注坐标。
"""

import base64
import json
import logging
import os
import uuid
import httpx
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime

from src.db.postgres_grading import GradingAnnotation, GradingPageImage, StudentGradingResult
from src.db.postgres_images import get_batch_images_as_bytes_list


logger = logging.getLogger(__name__)

_ALLOWED_ANNOTATION_TYPES = {
    "score",
    "error_circle",
    "error_underline",
    "correct_check",
    "partial_check",
    "wrong_cross",
    "comment",
    "highlight",
    "arrow",
    "a_mark",
    "m_mark",
    "step_check",
    "step_cross",
}

_ANNOTATION_TYPE_ALIASES = {
    "error": "error_circle",
    "underline": "error_underline",
    "check": "correct_check",
    "tick": "correct_check",
    "cross": "wrong_cross",
    "note": "comment",
    "text": "comment",
    "a": "a_mark",
    "m": "m_mark",
}

_SMALL_ANNOTATION_TYPES = {
    "score",
    "a_mark",
    "m_mark",
    "correct_check",
    "partial_check",
    "wrong_cross",
    "step_check",
    "step_cross",
}

_LARGE_ANNOTATION_TYPES = {"error_circle", "highlight"}


def _env_truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes", "y", "on")


def _clamp01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _coerce_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_bbox(raw_bbox: Any, *, min_size: float = 0.002) -> Optional[Dict[str, float]]:
    if not isinstance(raw_bbox, dict):
        return None

    def pick(*keys: str) -> Optional[float]:
        for key in keys:
            if key in raw_bbox and raw_bbox[key] is not None:
                v = _coerce_float(raw_bbox[key])
                if v is not None:
                    return v
        return None

    x_min = pick("x_min", "xMin", "xmin", "left", "x1")
    y_min = pick("y_min", "yMin", "ymin", "top", "y1")
    x_max = pick("x_max", "xMax", "xmax", "right", "x2")
    y_max = pick("y_max", "yMax", "ymax", "bottom", "y2")

    if x_min is None or y_min is None or x_max is None or y_max is None:
        return None

    # If the model accidentally returned pixel coordinates, drop them (we don't know image size here).
    if max(x_min, y_min, x_max, y_max) > 1.5:
        return None

    x0 = _clamp01(min(x_min, x_max))
    x1 = _clamp01(max(x_min, x_max))
    y0 = _clamp01(min(y_min, y_max))
    y1 = _clamp01(max(y_min, y_max))

    # Ensure a minimal size so the frontend renderer won't degenerate.
    if (x1 - x0) < min_size:
        cx = (x0 + x1) / 2
        x0 = _clamp01(cx - min_size / 2)
        x1 = _clamp01(cx + min_size / 2)
    if (y1 - y0) < min_size:
        cy = (y0 + y1) / 2
        y0 = _clamp01(cy - min_size / 2)
        y1 = _clamp01(cy + min_size / 2)

    if x1 <= x0 or y1 <= y0:
        return None

    return {"x_min": x0, "y_min": y0, "x_max": x1, "y_max": y1}


def _bbox_area(bbox: Dict[str, float]) -> float:
    return max(0.0, bbox["x_max"] - bbox["x_min"]) * max(0.0, bbox["y_max"] - bbox["y_min"])


def _bbox_center(bbox: Dict[str, float]) -> Tuple[float, float]:
    return ((bbox["x_min"] + bbox["x_max"]) / 2.0, (bbox["y_min"] + bbox["y_max"]) / 2.0)


def _bbox_center_distance(a: Dict[str, float], b: Dict[str, float]) -> float:
    ax, ay = _bbox_center(a)
    bx, by = _bbox_center(b)
    dx = ax - bx
    dy = ay - by
    return (dx * dx + dy * dy) ** 0.5


def _bbox_iou(a: Dict[str, float], b: Dict[str, float]) -> float:
    ix0 = max(a["x_min"], b["x_min"])
    iy0 = max(a["y_min"], b["y_min"])
    ix1 = min(a["x_max"], b["x_max"])
    iy1 = min(a["y_max"], b["y_max"])
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    inter = (ix1 - ix0) * (iy1 - iy0)
    union = _bbox_area(a) + _bbox_area(b) - inter
    if union <= 0:
        return 0.0
    return inter / union


def _blend_bbox(
    base_bbox: Dict[str, float],
    anchor_bbox: Dict[str, float],
    *,
    anchor_weight: float,
) -> Optional[Dict[str, float]]:
    weight = max(0.0, min(1.0, anchor_weight))
    merged = {
        "x_min": base_bbox["x_min"] * (1.0 - weight) + anchor_bbox["x_min"] * weight,
        "y_min": base_bbox["y_min"] * (1.0 - weight) + anchor_bbox["y_min"] * weight,
        "x_max": base_bbox["x_max"] * (1.0 - weight) + anchor_bbox["x_max"] * weight,
        "y_max": base_bbox["y_max"] * (1.0 - weight) + anchor_bbox["y_max"] * weight,
    }
    return _normalize_bbox(merged)


def _canonical_annotation_type(raw_type: Any, text: str = "") -> str:
    token = str(raw_type or "").strip().lower()
    token = _ANNOTATION_TYPE_ALIASES.get(token, token)
    if token in _ALLOWED_ANNOTATION_TYPES:
        return token

    upper_text = text.strip().upper()
    if upper_text.startswith("A"):
        return "a_mark"
    if upper_text.startswith("M"):
        return "m_mark"
    return "comment"


def _is_bbox_plausible_for_type(annotation_type: str, bbox: Dict[str, float]) -> bool:
    area = _bbox_area(bbox)
    if area < 0.00002:
        return False
    if annotation_type in _SMALL_ANNOTATION_TYPES:
        return area <= 0.12
    if annotation_type in _LARGE_ANNOTATION_TYPES:
        return area <= 0.65
    if annotation_type == "comment":
        return area <= 0.3
    return area <= 0.45


def _question_identifier(question: Dict[str, Any], index: int) -> str:
    raw = question.get("question_id") or question.get("questionId")
    if raw is None or str(raw).strip() == "":
        return str(index + 1)
    return str(raw).strip()


def _build_question_lookups(
    page_questions: List[Dict[str, Any]],
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, List[str]]]:
    question_lookup: Dict[str, Dict[str, Any]] = {}
    point_to_questions: Dict[str, List[str]] = {}

    for idx, q in enumerate(page_questions):
        if not isinstance(q, dict):
            continue
        qid = _question_identifier(q, idx)
        question_lookup[qid] = q

        scoring_points = q.get("scoring_point_results") or q.get("scoringPointResults") or []
        if not isinstance(scoring_points, list):
            continue
        for sp in scoring_points:
            if not isinstance(sp, dict):
                continue
            point_id = (
                sp.get("point_id")
                or sp.get("pointId")
                or sp.get("scoring_point_id")
                or sp.get("scoringPointId")
            )
            if point_id is None:
                continue
            point_key = str(point_id).strip()
            if not point_key:
                continue
            point_to_questions.setdefault(point_key, [])
            if qid not in point_to_questions[point_key]:
                point_to_questions[point_key].append(qid)

    return question_lookup, point_to_questions


def _select_questions_for_page(
    question_results: List[Dict[str, Any]],
    *,
    page_index: int,
    question_page_index: int,
) -> List[Dict[str, Any]]:
    matched_questions: List[Dict[str, Any]] = []
    unassigned_questions: List[Dict[str, Any]] = []

    for q in question_results:
        q_pages = q.get("page_indices") or q.get("pageIndices") or []
        if q_pages:
            if question_page_index in q_pages or page_index in q_pages:
                matched_questions.append(q)
        else:
            unassigned_questions.append(q)

    return matched_questions if matched_questions else unassigned_questions


def _collect_hint_regions(question: Dict[str, Any], scoring_point_id: str = "") -> List[Dict[str, float]]:
    hints: List[Dict[str, float]] = []

    answer_region = _normalize_bbox(question.get("answer_region") or question.get("answerRegion") or {})
    if answer_region:
        hints.append(answer_region)

    steps = question.get("steps") or []
    if isinstance(steps, list):
        for step in steps[:20]:
            if not isinstance(step, dict):
                continue
            step_region = _normalize_bbox(step.get("step_region") or step.get("stepRegion") or {})
            if step_region:
                hints.append(step_region)

    scoring_points = question.get("scoring_point_results") or question.get("scoringPointResults") or []
    if isinstance(scoring_points, list):
        for sp in scoring_points:
            if not isinstance(sp, dict):
                continue
            if scoring_point_id:
                point_id = (
                    sp.get("point_id")
                    or sp.get("pointId")
                    or sp.get("scoring_point_id")
                    or sp.get("scoringPointId")
                )
                if str(point_id or "").strip() != scoring_point_id:
                    continue
            for key in ("evidence_region", "evidenceRegion", "error_region", "errorRegion"):
                hint = _normalize_bbox(sp.get(key) or {})
                if hint:
                    hints.append(hint)

    return hints


def _resolve_question_id_for_annotation(
    ann_data: Dict[str, Any],
    question_lookup: Dict[str, Dict[str, Any]],
    point_to_questions: Dict[str, List[str]],
) -> str:
    qid = str(ann_data.get("question_id") or "").strip()
    if qid and qid in question_lookup:
        return qid

    point_id = str(ann_data.get("scoring_point_id") or "").strip()
    if point_id:
        matched_questions = point_to_questions.get(point_id) or []
        if len(matched_questions) == 1:
            return matched_questions[0]

    if len(question_lookup) == 1:
        return next(iter(question_lookup))
    return ""


def _refine_annotation_with_hints(
    ann_data: Dict[str, Any],
    question_lookup: Dict[str, Dict[str, Any]],
    point_to_questions: Dict[str, List[str]],
) -> Optional[Dict[str, Any]]:
    refined = dict(ann_data)
    refined["question_id"] = _resolve_question_id_for_annotation(refined, question_lookup, point_to_questions)
    refined["text"] = str(refined.get("text") or "").strip()[:120]
    ann_type = str(refined.get("type") or "comment")
    current_bbox = refined["bounding_box"]
    plausible_bbox = _is_bbox_plausible_for_type(ann_type, current_bbox)

    qid = refined.get("question_id") or ""
    question = question_lookup.get(qid) if qid else None
    if not question:
        return refined if plausible_bbox else None

    point_id = str(refined.get("scoring_point_id") or "").strip()
    hints = _collect_hint_regions(question, scoring_point_id=point_id)
    if not hints:
        return refined if plausible_bbox else None

    best_hint = max(hints, key=lambda h: _bbox_iou(current_bbox, h))
    iou = _bbox_iou(current_bbox, best_hint)
    center_distance = _bbox_center_distance(current_bbox, best_hint)

    adjusted_bbox: Optional[Dict[str, float]]
    if not plausible_bbox:
        adjusted_bbox = best_hint
    elif iou < 0.01 and center_distance > 0.32:
        anchor_weight = 0.8 if ann_type in _SMALL_ANNOTATION_TYPES else 0.65
        adjusted_bbox = _blend_bbox(current_bbox, best_hint, anchor_weight=anchor_weight)
    else:
        adjusted_bbox = current_bbox

    if not adjusted_bbox:
        return None
    refined["bounding_box"] = adjusted_bbox
    return refined


def _normalize_vlm_annotation(item: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(item, dict):
        return None

    raw_ann_type = (
        item.get("type")
        or item.get("annotation_type")
        or item.get("annotationType")
        or "score"
    )
    text = str(item.get("text") or item.get("message") or "")
    ann_type = _canonical_annotation_type(raw_ann_type, text=text)
    bbox = _normalize_bbox(item.get("bounding_box") or item.get("boundingBox") or item.get("bbox") or {})
    if not bbox:
        return None

    return {
        "type": ann_type,
        "bounding_box": bbox,
        "text": text,
        "color": str(item.get("color") or "#FF0000"),
        "question_id": str(item.get("question_id") or item.get("questionId") or ""),
        "scoring_point_id": str(item.get("scoring_point_id") or item.get("scoringPointId") or ""),
    }


def _normalize_vlm_annotations_batch(
    raw_annotations: List[Dict[str, Any]],
    question_lookup: Dict[str, Dict[str, Any]],
    point_to_questions: Dict[str, List[str]],
    seen: Optional[set[str]] = None,
) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    dedup = seen if seen is not None else set()

    for item in raw_annotations:
        ann_data = _normalize_vlm_annotation(item)
        if not ann_data:
            continue
        ann_data = _refine_annotation_with_hints(ann_data, question_lookup, point_to_questions)
        if not ann_data:
            continue
        fingerprint = json.dumps(ann_data, sort_keys=True, ensure_ascii=True)
        if fingerprint in dedup:
            continue
        dedup.add(fingerprint)
        normalized.append(ann_data)

    return normalized


def _resolve_annotation_page_index(
    item: Dict[str, Any],
    *,
    page_order: List[int],
    valid_pages: set[int],
    question_to_pages: Dict[str, List[int]],
) -> Optional[int]:
    if not isinstance(item, dict):
        return None

    raw = (
        item.get("page_index")
        or item.get("pageIndex")
        or item.get("page")
        or item.get("page_idx")
        or item.get("pageIdx")
        or item.get("image_slot")
        or item.get("imageSlot")
        or item.get("image_index")
        or item.get("imageIndex")
    )
    value = _coerce_int(raw)
    if value is not None:
        if value in valid_pages:
            return value
        if 0 <= value < len(page_order):
            return page_order[value]
        if 1 <= value <= len(page_order):
            return page_order[value - 1]

    qid = str(item.get("question_id") or item.get("questionId") or "").strip()
    if qid:
        pages = question_to_pages.get(qid) or []
        if len(pages) == 1:
            return pages[0]

    return None


async def _call_vlm_question_wise(
    image_data: bytes,
    page_index: int,
    page_questions: List[Dict[str, Any]],
    question_lookup: Dict[str, Dict[str, Any]],
    point_to_questions: Dict[str, List[str]],
    seen: Optional[set[str]] = None,
) -> List[Dict[str, Any]]:
    recovered: List[Dict[str, Any]] = []
    dedup = seen if seen is not None else set()

    for question in page_questions:
        qid = str(question.get("question_id") or question.get("questionId") or "")
        try:
            raw = await _call_vlm_for_annotations(
                image_data=image_data,
                page_index=page_index,
                questions=[question],
            )
        except Exception as e:
            logger.warning(
                f"[Annotation] question-wise VLM failed: page={page_index}, question={qid or 'unknown'}, err={e}"
            )
            continue

        if not raw:
            continue
        recovered.extend(
            _normalize_vlm_annotations_batch(
                raw,
                question_lookup=question_lookup,
                point_to_questions=point_to_questions,
                seen=dedup,
            )
        )

    return recovered


async def generate_annotations_for_student(
    grading_history_id: str,
    student_key: str,
    student_result: StudentGradingResult,
    page_images: List[GradingPageImage],
    batch_id: Optional[str] = None,
    page_indices: Optional[List[int]] = None,
    strict_vlm: bool = True,
    failed_pages: Optional[List[int]] = None,
) -> List[GradingAnnotation]:
    """
    为学生生成批注坐标
    
    Args:
        grading_history_id: 批改历史 ID
        student_key: 学生标识
        student_result: 学生批改结果
        page_images: 页面图片列表
        page_indices: 指定页码列表，None 表示所有页
    
    Returns:
        生成的批注列表
    """
    annotations: List[GradingAnnotation] = []
    now = datetime.now().isoformat()
    
    # 解析批改结果
    result_data = student_result.result_data or {}
    question_results = (
        result_data.get("question_results") 
        or result_data.get("questionResults")
        or result_data.get("question_details")
        or []
    )
    
    if not question_results:
        logger.warning(f"学生 {student_key} 没有批改结果数据")
        return annotations
    
    # 按页面分组图片
    page_image_map: Dict[int, GradingPageImage] = {}
    for img in page_images:
        if page_indices is None or img.page_index in page_indices:
            page_image_map[img.page_index] = img

    # 批次图片作为兜底（当未找到页面图片或页面图片缺失URL时）
    fallback_images: Dict[int, bytes] = {}
    needs_fallback = not page_image_map or any(
        not getattr(img, "file_url", None) for img in page_images
    )
    if batch_id and needs_fallback:
        try:
            batch_images = await get_batch_images_as_bytes_list(batch_id, "answer")
            if batch_images:
                fallback_images = {idx: img for idx, img in enumerate(batch_images)}
                logger.info(
                    f"[Annotation] 已加载 batch_images 作为兜底: batch_id={batch_id}, count={len(batch_images)}"
                )
        except Exception as e:
            logger.warning(f"[Annotation] 兜底加载 batch_images 失败: {e}")

    if not page_image_map and fallback_images:
        # When we only have batch-level images, restrict the pages to this student's range.
        start_page = _coerce_int(result_data.get("start_page") or result_data.get("startPage"))
        end_page = _coerce_int(result_data.get("end_page") or result_data.get("endPage"))
        page_keys = sorted(fallback_images.keys())
        if start_page is not None and end_page is not None and page_keys:
            start = max(0, min(start_page, end_page))
            end = max(start, end_page)
            last_idx = page_keys[-1]
            if end > last_idx:
                end = last_idx
            if start > end:
                start = max(0, min(start, last_idx))
            selected_keys = [idx for idx in page_keys if start <= idx <= end]
            logger.info(
                f"[Annotation] using fallback page range for {student_key}: {start}-{end} "
                f"(selected={len(selected_keys)}/{len(page_keys)})"
            )
        else:
            selected_keys = page_keys
            if page_keys:
                logger.warning(
                    f"[Annotation] missing start/end page range for {student_key}; using all fallback pages "
                    f"(count={len(page_keys)})"
                )

        for idx in selected_keys:
            if page_indices is not None and idx not in page_indices:
                continue
            page_image_map[idx] = GradingPageImage(
                id=str(uuid.uuid4()),
                grading_history_id=grading_history_id,
                student_key=student_key,
                page_index=idx,
                file_id="",
                file_url=None,
                content_type="image/jpeg",
                created_at=now,
            )
    
    if not page_image_map:
        logger.warning(f"学生 {student_key} 没有可用的页面图片")
        return annotations

    # Imported grading results often store question.page_indices as 0..N-1 (relative
    # to the student's answer pages) while page_images.page_index may be absolute
    # PDF page numbers (e.g. 26, 27). Build a stable mapping so we can match
    # questions to pages in both cases.
    sorted_page_indices = sorted(page_image_map.keys())
    actual_to_relative: Dict[int, int] = {actual: idx for idx, actual in enumerate(sorted_page_indices)}
    logger.info(
        f"[Annotation] page_index mapping for {student_key}: actual={sorted_page_indices} "
        f"-> relative=0..{len(sorted_page_indices) - 1}"
    )

    # Collect all candidate pages first, then call VLM once for this student.
    candidate_pages: List[Dict[str, Any]] = []
    page_failures: List[int] = []
    for page_idx in sorted_page_indices:
        page_image = page_image_map[page_idx]
        question_page_index = actual_to_relative.get(page_idx, page_idx)
        page_questions = _select_questions_for_page(
            question_results,
            page_index=page_idx,
            question_page_index=question_page_index,
        )
        if not page_questions:
            logger.info(f"页面 {page_idx} 没有关联的题目")
            continue

        image_data = await _fetch_image_data(page_image, fallback_images=fallback_images or None)
        if not image_data:
            logger.warning(f"无法获取页面 {page_idx} 的图片数据")
            if not strict_vlm and _env_truthy("ANNOTATION_ALLOW_ESTIMATED_FALLBACK"):
                annotations.extend(
                    _generate_estimated_annotations(
                        grading_history_id,
                        student_key,
                        page_idx,
                        page_questions,
                        now,
                    )
                )
            else:
                page_failures.append(page_idx)
            continue

        question_lookup, point_to_questions = _build_question_lookups(page_questions)
        candidate_pages.append(
            {
                "page_index": page_idx,
                "question_page_index": question_page_index,
                "image_data": image_data,
                "questions": page_questions,
                "question_lookup": question_lookup,
                "point_to_questions": point_to_questions,
            }
        )

    if not candidate_pages:
        if failed_pages is not None and page_failures:
            failed_pages.extend(page_failures)
        if strict_vlm and page_failures and not annotations:
            failed_joined = ", ".join(str(p) for p in sorted(set(page_failures)))
            raise RuntimeError(
                f"VLM annotation generation failed on all candidate pages for student {student_key}: {failed_joined}"
            )
        return annotations

    valid_pages = {int(p["page_index"]) for p in candidate_pages}
    page_order = [int(p["page_index"]) for p in candidate_pages]
    page_info_map: Dict[int, Dict[str, Any]] = {
        int(p["page_index"]): p for p in candidate_pages
    }
    question_to_pages: Dict[str, List[int]] = {}
    for page in candidate_pages:
        page_idx = int(page["page_index"])
        for qid in page["question_lookup"].keys():
            bucket = question_to_pages.setdefault(str(qid), [])
            if page_idx not in bucket:
                bucket.append(page_idx)

    try:
        vlm_annotations = await _call_vlm_for_student_annotations(candidate_pages)
    except Exception as e:
        logger.error(f"[Annotation] student-level VLM generation failed: student={student_key}, err={e}")
        if not strict_vlm and _env_truthy("ANNOTATION_ALLOW_ESTIMATED_FALLBACK"):
            for page in candidate_pages:
                annotations.extend(
                    _generate_estimated_annotations(
                        grading_history_id,
                        student_key,
                        int(page["page_index"]),
                        page["questions"],
                        now,
                    )
                )
            if failed_pages is not None and page_failures:
                failed_pages.extend(page_failures)
            return annotations
        raise

    normalized_by_page: Dict[int, List[Dict[str, Any]]] = {int(p["page_index"]): [] for p in candidate_pages}
    seen: set[str] = set()

    for item in vlm_annotations:
        page_idx = _resolve_annotation_page_index(
            item,
            page_order=page_order,
            valid_pages=valid_pages,
            question_to_pages=question_to_pages,
        )
        if page_idx is None:
            continue

        ann_data = _normalize_vlm_annotation(item)
        if not ann_data:
            continue

        page_info = page_info_map.get(page_idx)
        if not page_info:
            continue
        ann_data = _refine_annotation_with_hints(
            ann_data,
            page_info["question_lookup"],
            page_info["point_to_questions"],
        )
        if not ann_data:
            continue

        fingerprint = json.dumps(
            {"page_index": page_idx, **ann_data},
            sort_keys=True,
            ensure_ascii=True,
        )
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        normalized_by_page[page_idx].append(ann_data)

    for page in candidate_pages:
        page_idx = int(page["page_index"])
        page_annotations = normalized_by_page.get(page_idx) or []
        if not page_annotations:
            page_failures.append(page_idx)
            if not strict_vlm and _env_truthy("ANNOTATION_ALLOW_ESTIMATED_FALLBACK"):
                annotations.extend(
                    _generate_estimated_annotations(
                        grading_history_id,
                        student_key,
                        page_idx,
                        page["questions"],
                        now,
                    )
                )
            continue

        for ann_data in page_annotations:
            annotations.append(
                GradingAnnotation(
                    id=str(uuid.uuid4()),
                    grading_history_id=grading_history_id,
                    student_key=student_key,
                    page_index=page_idx,
                    annotation_type=ann_data["type"],
                    bounding_box=ann_data["bounding_box"],
                    text=ann_data["text"],
                    color=ann_data["color"],
                    question_id=ann_data["question_id"],
                    scoring_point_id=ann_data["scoring_point_id"],
                    created_by="ai_vlm",
                    created_at=now,
                    updated_at=now,
                )
            )

    page_failures = sorted(set(page_failures))
    if failed_pages is not None and page_failures:
        failed_pages.extend(page_failures)

    if strict_vlm and page_failures and not annotations:
        failed_joined = ", ".join(str(p) for p in page_failures)
        raise RuntimeError(
            f"VLM annotation generation failed on all candidate pages for student {student_key}: {failed_joined}"
        )

    return annotations


async def _generate_annotations_for_page(
    grading_history_id: str,
    student_key: str,
    page_index: int,
    question_page_index: int,
    page_image: GradingPageImage,
    question_results: List[Dict[str, Any]],
    fallback_images: Optional[Dict[int, bytes]] = None,
    strict_vlm: bool = True,
) -> List[GradingAnnotation]:
    """为单个页面生成批注"""
    annotations: List[GradingAnnotation] = []
    now = datetime.now().isoformat()
    
    # 筛选该页面的题目
    matched_questions: List[Dict[str, Any]] = []
    unassigned_questions: List[Dict[str, Any]] = []
    for q in question_results:
        q_pages = q.get("page_indices") or q.get("pageIndices") or []
        # Prefer matching against the "question page index" (usually 0..N-1),
        # but keep compatibility with payloads that store absolute page indices.
        if q_pages:
            if question_page_index in q_pages or page_index in q_pages:
                matched_questions.append(q)
        else:
            unassigned_questions.append(q)

    # If the grading payload provides page mappings, trust them and ignore unassigned
    # questions (otherwise we'd ask the VLM to annotate every question on every page).
    page_questions = matched_questions if matched_questions else unassigned_questions
    
    if not page_questions:
        logger.info(f"页面 {page_index} 没有关联的题目")
        return annotations
    
    # 获取图片数据
    image_data = await _fetch_image_data(page_image, fallback_images=fallback_images)
    if not image_data:
        logger.warning(f"无法获取页面 {page_index} 的图片数据")
        if not strict_vlm and _env_truthy("ANNOTATION_ALLOW_ESTIMATED_FALLBACK"):
            return _generate_estimated_annotations(
                grading_history_id, student_key, page_index, page_questions, now
            )
        raise RuntimeError(f"missing page image bytes for page_index={page_index}")
    
    # 调用 VLM 获取精确坐标
    try:
        question_lookup, point_to_questions = _build_question_lookups(page_questions)
        seen: set[str] = set()
        normalized: List[Dict[str, Any]] = []

        primary_error: Optional[Exception] = None
        try:
            vlm_annotations = await _call_vlm_for_annotations(
                image_data=image_data,
                page_index=page_index,
                questions=page_questions,
            )
        except Exception as e:
            primary_error = e
            vlm_annotations = []

        if vlm_annotations:
            normalized.extend(
                _normalize_vlm_annotations_batch(
                    vlm_annotations,
                    question_lookup=question_lookup,
                    point_to_questions=point_to_questions,
                    seen=seen,
                )
            )

        if not normalized:
            logger.warning(
                f"[Annotation] page-level VLM produced no usable annotations; trying question-wise fallback: "
                f"page={page_index}, questions={len(page_questions)}"
            )
            normalized.extend(
                await _call_vlm_question_wise(
                    image_data=image_data,
                    page_index=page_index,
                    page_questions=page_questions,
                    question_lookup=question_lookup,
                    point_to_questions=point_to_questions,
                    seen=seen,
                )
            )

        if not normalized:
            if primary_error is not None:
                raise primary_error
            raise RuntimeError("VLM returned no usable annotations")

        for ann_data in normalized:
            annotation = GradingAnnotation(
                id=str(uuid.uuid4()),
                grading_history_id=grading_history_id,
                student_key=student_key,
                page_index=page_index,
                annotation_type=ann_data["type"],
                bounding_box=ann_data["bounding_box"],
                text=ann_data["text"],
                color=ann_data["color"],
                question_id=ann_data["question_id"],
                scoring_point_id=ann_data["scoring_point_id"],
                created_by="ai_vlm",
                created_at=now,
                updated_at=now,
            )
            annotations.append(annotation)
        
    except Exception as e:
        logger.error(f"VLM 批注生成失败: page={page_index}, student={student_key}, err={e}")
        if not strict_vlm and _env_truthy("ANNOTATION_ALLOW_ESTIMATED_FALLBACK"):
            annotations = _generate_estimated_annotations(
                grading_history_id, student_key, page_index, page_questions, now
            )
        else:
            raise
    
    return annotations


async def _fetch_image_data(
    page_image: GradingPageImage,
    fallback_images: Optional[Dict[int, bytes]] = None,
) -> Optional[bytes]:
    """获取图片数据"""
    try:
        if page_image.file_url:
            # 从 URL 获取图片
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(page_image.file_url)
                if response.status_code == 200:
                    return response.content
        if fallback_images:
            fallback = fallback_images.get(page_image.page_index)
            if fallback:
                return fallback
        return None
    except Exception as e:
        logger.error(f"获取图片失败: {e}")
        return None


async def _call_vlm_for_annotations(
    image_data: bytes,
    page_index: int,
    questions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """调用 VLM 生成批注坐标"""
    from src.services.llm_reasoning import LLMReasoningClient
    
    # 构建 prompt
    prompt = _build_annotation_prompt(questions, page_index)
    
    # 调用 VLM
    client = LLMReasoningClient()
    
    # 编码图片
    image_b64 = base64.b64encode(image_data).decode("utf-8")
    
    try:
        result = await client.generate_annotations(
            image_base64=image_b64,
            prompt=prompt,
        )
        # LLMReasoningClient.generate_annotations returns {"annotations": [], "error": "..."} on failures
        # (e.g. OpenRouter 403). Treat that as a hard failure so the caller can fall back to
        # deterministic estimated annotations.
        if isinstance(result, dict):
            err = result.get("error")
            anns = result.get("annotations") or []
        elif isinstance(result, list):
            err = None
            anns = result
        else:
            err = None
            anns = []

        if err:
            raise RuntimeError(f"VLM returned error: {err}")
        if not anns:
            raise RuntimeError("VLM returned empty annotations")
        return anns
    except Exception as e:
        logger.error(f"VLM 调用失败: {e}")
        raise


async def _call_vlm_for_student_annotations(
    page_payloads: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Call VLM once for all pages of one student."""
    from src.services.llm_reasoning import LLMReasoningClient

    if not page_payloads:
        return []

    prompt = _build_student_annotation_prompt(page_payloads)
    image_b64_list = [
        base64.b64encode(page["image_data"]).decode("utf-8")
        for page in page_payloads
        if page.get("image_data")
    ]

    if not image_b64_list:
        raise RuntimeError("missing all page image bytes for student-level annotation call")

    client = LLMReasoningClient()
    try:
        result = await client.generate_annotations_multi(
            image_base64_list=image_b64_list,
            prompt=prompt,
        )
        if isinstance(result, dict):
            err = result.get("error")
            anns = result.get("annotations") or []
        elif isinstance(result, list):
            err = None
            anns = result
        else:
            err = None
            anns = []

        if err:
            raise RuntimeError(f"VLM returned error: {err}")
        if not anns:
            raise RuntimeError("VLM returned empty annotations")
        return anns
    except Exception as e:
        logger.error(f"[Annotation] student-level VLM call failed: {e}")
        raise


def _build_questions_prompt_payload(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    questions_info: List[Dict[str, Any]] = []
    for q in questions:
        qid = q.get("question_id") or q.get("questionId") or "unknown"
        score = q.get("score", 0)
        max_score = q.get("max_score") or q.get("maxScore", 0)
        feedback = q.get("feedback", "")
        student_answer = q.get("student_answer") or q.get("studentAnswer", "")
        answer_region = q.get("answer_region") or q.get("answerRegion")

        steps_raw = q.get("steps") or []
        steps_info = []
        if isinstance(steps_raw, list) and steps_raw:
            for step in steps_raw[:12]:
                if not isinstance(step, dict):
                    continue
                step_id = step.get("step_id") or step.get("stepId") or step.get("id") or ""
                step_content = step.get("step_content") or step.get("stepContent") or ""
                step_region = step.get("step_region") or step.get("stepRegion")
                steps_info.append(
                    {
                        "step_id": str(step_id),
                        "step_content_preview": str(step_content)[:160] if step_content else "",
                        "step_region_hint": step_region if isinstance(step_region, dict) else None,
                        "mark_type": str(step.get("mark_type") or step.get("markType") or ""),
                        "mark_value": step.get("mark_value") or step.get("markValue"),
                        "is_correct": step.get("is_correct") if "is_correct" in step else step.get("isCorrect"),
                    }
                )

        scoring_points = q.get("scoring_point_results") or q.get("scoringPointResults") or []
        points_info = []
        for sp in scoring_points:
            point_id = sp.get("point_id") or sp.get("pointId", "")
            description = (
                sp.get("description")
                or (sp.get("scoringPoint") or {}).get("description")
                or (sp.get("scoring_point") or {}).get("description")
                or ""
            )
            mark_type = sp.get("mark_type") or sp.get("markType") or sp.get("markType") or ""
            awarded = sp.get("awarded", 0)
            max_pts = sp.get("max_points") or sp.get("maxPoints", 1)
            evidence = sp.get("evidence", "")
            evidence_region = sp.get("evidence_region") or sp.get("evidenceRegion")
            error_region = sp.get("error_region") or sp.get("errorRegion")
            step_id_hint = sp.get("step_id") or sp.get("stepId")
            step_excerpt_hint = sp.get("step_excerpt") or sp.get("stepExcerpt")
            points_info.append(
                {
                    "point_id": point_id,
                    "mark_type": mark_type,
                    "awarded": awarded,
                    "max_points": max_pts,
                    "description": description[:180] if description else "",
                    "evidence": evidence[:200] if evidence else "",
                    "evidence_region_hint": evidence_region if isinstance(evidence_region, dict) else None,
                    "error_region_hint": error_region if isinstance(error_region, dict) else None,
                    "step_id_hint": str(step_id_hint) if step_id_hint else None,
                    "step_excerpt_hint": str(step_excerpt_hint)[:160] if step_excerpt_hint else None,
                }
            )

        questions_info.append(
            {
                "question_id": qid,
                "score": score,
                "max_score": max_score,
                "feedback": feedback[:200] if feedback else "",
                "student_answer_preview": student_answer[:100] if student_answer else "",
                "answer_region_hint": answer_region if isinstance(answer_region, dict) else None,
                "steps_hint": steps_info,
                "scoring_points": points_info,
            }
        )
    return questions_info


def _build_student_annotation_prompt(page_payloads: List[Dict[str, Any]]) -> str:
    pages_info: List[Dict[str, Any]] = []
    for slot, page in enumerate(page_payloads):
        pages_info.append(
            {
                "image_slot": slot,
                "page_index": int(page["page_index"]),
                "question_page_index": int(page["question_page_index"]),
                "questions": _build_questions_prompt_payload(page.get("questions") or []),
            }
        )

    return f"""# Task: Generate all annotations for one student in one pass

You are given multiple answer page images of the same student. The image order is exactly the `image_slot` order in the payload below.

## Pages payload
{json.dumps(pages_info, ensure_ascii=False, indent=2)}

## Rules
1. Output JSON only. No markdown or explanation.
2. Return annotations for all pages in one JSON payload.
3. Every annotation must include `page_index` (actual page number from payload).
4. `bounding_box` must be normalized in [0,1] and satisfy:
   0 <= x_min < x_max <= 1 and 0 <= y_min < y_max <= 1.
5. Do not guess. If unsure, omit that annotation.

## Output format
```json
{{
  "annotations": [
    {{
      "page_index": 26,
      "type": "score",
      "question_id": "1",
      "scoring_point_id": "1.1",
      "bounding_box": {{"x_min": 0.8, "y_min": 0.1, "x_max": 0.95, "y_max": 0.15}},
      "text": "3/5",
      "color": "#FF8800"
    }}
  ]
}}
```
"""


def _build_annotation_prompt(questions: List[Dict[str, Any]], page_index: int) -> str:
    """构建批注生成 prompt"""
    questions_info = _build_questions_prompt_payload(questions)
    
    prompt = f"""# 任务：为批改结果定位批注坐标

请分析这张答题图片，为以下批改结果定位批注位置。

## 页面信息
- page_index: {page_index}

## 批改结果（需要标注）
{json.dumps(questions_info, ensure_ascii=False, indent=2)}

## 要求

0. **只标注本页可见内容**：只为“本页图片中能看到作答内容”的题目输出批注。列表里但不在本页的题目，不要输出任何批注。
0. **禁止猜测**：如果某题/某得分点在本页找不到对应证据位置，不要猜测位置；可以直接省略该得分点批注。
1. **定位学生答案区域**：找到每道题学生作答的位置
2. **标注分数**：在答案区域右侧或下方放置分数标注
3. **标注错误（可选）**：只有当你能清晰看到错误位置时，才输出 error_circle；否则不要输出。
4. **得分点标注**：为每个得分点的关键位置添加 M/A mark（贴近对应步骤/证据文本旁边）
   - 若提供了 evidence_region_hint / step_region_hint / answer_region_hint，请优先作为定位锚点（仍需在图中核验）。
5. **坐标合法性**：每个 bounding_box 必须满足 0 <= x_min < x_max <= 1 且 0 <= y_min < y_max <= 1。

## 坐标系统
- 使用归一化坐标 (0.0-1.0)
- 原点在左上角
- x 向右增加，y 向下增加

## 输出格式（JSON）
```json
{{
    "annotations": [
        {{
            "type": "score",
            "question_id": "1",
            "bounding_box": {{"x_min": 0.8, "y_min": 0.1, "x_max": 0.95, "y_max": 0.15}},
            "text": "3/5",
            "color": "#FF8800"
        }},
        {{
            "type": "m_mark",
            "question_id": "1",
            "scoring_point_id": "1.1",
            "bounding_box": {{"x_min": 0.75, "y_min": 0.12, "x_max": 0.78, "y_max": 0.15}},
            "text": "M1",
            "color": "#00AA00"
        }},
        {{
            "type": "error_circle",
            "question_id": "1",
            "bounding_box": {{"x_min": 0.3, "y_min": 0.15, "x_max": 0.5, "y_max": 0.2}},
            "text": "计算错误",
            "color": "#FF0000"
        }}
    ]
}}
```

## 批注类型
- `score`: 分数标注（放在答案区域旁边）
- `m_mark`: 方法分标注（M1/M0）
- `a_mark`: 答案分标注（A1/A0）
- `error_circle`: 错误圈选
- `comment`: 文字批注

## 颜色规范
- 绿色 #00AA00: 正确
- 红色 #FF0000: 错误
- 橙色 #FF8800: 部分正确

请仔细观察图片，给出精确的批注坐标。只输出 JSON，不要其他内容。
"""
    return prompt


def _generate_estimated_annotations(
    grading_history_id: str,
    student_key: str,
    page_index: int,
    questions: List[Dict[str, Any]],
    now: str,
) -> List[GradingAnnotation]:
    """
    生成估算位置的批注（当 VLM 不可用时的降级方案）
    
    基于题目数量均匀分布批注位置
    """
    annotations: List[GradingAnnotation] = []
    
    total_questions = len(questions)
    if total_questions == 0:
        return annotations
    
    # 计算每道题的垂直区域
    margin_top = 0.1
    margin_bottom = 0.1
    available_height = 1.0 - margin_top - margin_bottom
    height_per_question = available_height / max(total_questions, 1)
    
    for idx, q in enumerate(questions):
        qid = q.get("question_id") or q.get("questionId") or str(idx + 1)
        score = q.get("score", 0)
        max_score = q.get("max_score") or q.get("maxScore", 0)
        
        # 计算该题的 y 位置
        y_start = margin_top + idx * height_per_question
        y_center = y_start + height_per_question / 2
        
        # 添加分数标注（右侧）
        score_color = (
            "#00AA00" if score >= max_score * 0.8
            else "#FF8800" if score >= max_score * 0.5
            else "#FF0000"
        )
        annotations.append(
            GradingAnnotation(
                id=str(uuid.uuid4()),
                grading_history_id=grading_history_id,
                student_key=student_key,
                page_index=page_index,
                annotation_type="score",
                bounding_box={
                    "x_min": 0.85,
                    "y_min": y_center - 0.02,
                    "x_max": 0.95,
                    "y_max": y_center + 0.02,
                },
                text=f"{score}/{max_score}",
                color=score_color,
                question_id=qid,
                scoring_point_id="",
                created_by="estimated",
                created_at=now,
                updated_at=now,
            )
        )
        
        # 添加得分点标注
        scoring_points = q.get("scoring_point_results") or q.get("scoringPointResults") or []
        for sp_idx, sp in enumerate(scoring_points[:4]):  # 最多显示 4 个得分点
            point_id = sp.get("point_id") or sp.get("pointId", f"{qid}.{sp_idx + 1}")
            awarded = sp.get("awarded", 0)
            max_pts = sp.get("max_points") or sp.get("maxPoints", 1)
            
            mark_type = sp.get("mark_type") or "M"
            mark_text = f"{mark_type}{1 if awarded > 0 else 0}"
            mark_color = "#00AA00" if awarded > 0 else "#FF0000"
            
            y_offset = y_start + (sp_idx + 1) * (height_per_question / (len(scoring_points) + 2))
            
            annotations.append(
                GradingAnnotation(
                    id=str(uuid.uuid4()),
                    grading_history_id=grading_history_id,
                    student_key=student_key,
                    page_index=page_index,
                    annotation_type="m_mark" if mark_type == "M" else "a_mark",
                    bounding_box={
                        "x_min": 0.78,
                        "y_min": y_offset - 0.015,
                        "x_max": 0.83,
                        "y_max": y_offset + 0.015,
                    },
                    text=mark_text,
                    color=mark_color,
                    question_id=qid,
                    scoring_point_id=point_id,
                    created_by="estimated",
                    created_at=now,
                    updated_at=now,
                )
            )
    
    return annotations
