import uuid
import asyncio
from datetime import datetime

import pytest

from src.db.postgres_grading import GradingPageImage
from src.services.annotation_generator import (
    _generate_annotations_for_page,
    _normalize_vlm_annotation,
    _refine_annotation_with_hints,
)


def test_generate_annotations_page_strict_mode_raises_on_missing_image(monkeypatch):
    """Strict mode must fail hard instead of falling back to estimated boxes."""

    monkeypatch.setenv("ANNOTATION_ALLOW_ESTIMATED_FALLBACK", "1")
    page_image = GradingPageImage(
        id=str(uuid.uuid4()),
        grading_history_id="history-1",
        student_key="student-1",
        page_index=0,
        file_id="",
        file_url=None,
        content_type="image/jpeg",
        created_at=datetime.now().isoformat(),
    )

    async def _run() -> None:
        await _generate_annotations_for_page(
            grading_history_id="history-1",
            student_key="student-1",
            page_index=0,
            question_page_index=0,
            page_image=page_image,
            question_results=[{"question_id": "1", "score": 1, "max_score": 1}],
            strict_vlm=True,
        )

    with pytest.raises(RuntimeError, match="missing page image bytes"):
        asyncio.run(_run())


def test_normalize_vlm_annotation_infers_mark_type_from_text():
    ann = _normalize_vlm_annotation(
        {
            "type": "unknown",
            "text": "M1",
            "bbox": {"x_min": 0.2, "y_min": 0.2, "x_max": 0.3, "y_max": 0.3},
            "question_id": "1",
        }
    )
    assert ann is not None
    assert ann["type"] == "m_mark"


def test_refine_annotation_uses_hint_for_implausible_bbox():
    hint_bbox = {"x_min": 0.2, "y_min": 0.2, "x_max": 0.32, "y_max": 0.28}
    ann_data = {
        "type": "score",
        "bounding_box": {"x_min": 0.0, "y_min": 0.0, "x_max": 0.95, "y_max": 0.95},
        "text": "3/5",
        "color": "#FF8800",
        "question_id": "1",
        "scoring_point_id": "1.1",
    }
    question_lookup = {
        "1": {
            "question_id": "1",
            "scoring_point_results": [
                {"point_id": "1.1", "evidence_region": hint_bbox},
            ],
        }
    }
    point_to_questions = {"1.1": ["1"]}

    refined = _refine_annotation_with_hints(ann_data, question_lookup, point_to_questions)
    assert refined is not None
    assert refined["bounding_box"] == hint_bbox
