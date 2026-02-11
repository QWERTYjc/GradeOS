import uuid
import asyncio
from datetime import datetime
from types import SimpleNamespace

import pytest

from src.db.postgres_grading import GradingPageImage
from src.db.postgres_grading import GradingAnnotation
from src.services import annotation_generator as ag
from src.services.annotation_generator import (
    generate_annotations_for_student,
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


def test_generate_annotations_student_strict_keeps_success_and_reports_failed_pages(monkeypatch):
    page_images = [
        GradingPageImage(
            id=str(uuid.uuid4()),
            grading_history_id="history-1",
            student_key="student-1",
            page_index=0,
            file_id="",
            file_url="https://example.com/p0.jpg",
            content_type="image/jpeg",
            created_at=datetime.now().isoformat(),
        ),
        GradingPageImage(
            id=str(uuid.uuid4()),
            grading_history_id="history-1",
            student_key="student-1",
            page_index=1,
            file_id="",
            file_url="https://example.com/p1.jpg",
            content_type="image/jpeg",
            created_at=datetime.now().isoformat(),
        ),
    ]
    student_result = SimpleNamespace(
        result_data={
            "question_results": [
                {"question_id": "1", "page_indices": [0], "score": 1, "max_score": 1},
                {"question_id": "2", "page_indices": [1], "score": 1, "max_score": 1},
            ]
        }
    )

    async def _fake_fetch_image_data(_page_image, fallback_images=None):
        return b"fake-image"

    calls: list[int] = []

    async def _fake_call_vlm_for_student_annotations(page_payloads):
        calls.append(len(page_payloads))
        return [
            {
                "page_index": 1,
                "type": "score",
                "question_id": "2",
                "bounding_box": {"x_min": 0.72, "y_min": 0.1, "x_max": 0.9, "y_max": 0.17},
                "text": "1/1",
                "color": "#00AA00",
            }
        ]

    monkeypatch.setattr(ag, "_fetch_image_data", _fake_fetch_image_data)
    monkeypatch.setattr(ag, "_call_vlm_for_student_annotations", _fake_call_vlm_for_student_annotations)

    failed_pages: list[int] = []

    async def _run():
        return await generate_annotations_for_student(
            grading_history_id="history-1",
            student_key="student-1",
            student_result=student_result,
            page_images=page_images,
            strict_vlm=True,
            failed_pages=failed_pages,
        )

    annotations = asyncio.run(_run())
    assert len(annotations) == 1
    assert annotations[0].page_index == 1
    assert failed_pages == [0]
    assert calls == [2]


def test_generate_annotations_page_falls_back_to_question_wise_vlm(monkeypatch):
    page_image = GradingPageImage(
        id=str(uuid.uuid4()),
        grading_history_id="history-1",
        student_key="student-1",
        page_index=0,
        file_id="",
        file_url="https://example.com/p0.jpg",
        content_type="image/jpeg",
        created_at=datetime.now().isoformat(),
    )

    async def _fake_fetch_image_data(_page_image, fallback_images=None):
        return b"fake-image"

    calls: list[int] = []

    async def _fake_call_vlm_for_annotations(*, image_data, page_index, questions):
        calls.append(len(questions))
        if len(questions) > 1:
            raise RuntimeError("VLM returned empty annotations")
        qid = str(questions[0].get("question_id") or "")
        return [
            {
                "type": "score",
                "question_id": qid,
                "bounding_box": {"x_min": 0.72, "y_min": 0.1, "x_max": 0.9, "y_max": 0.17},
                "text": "1/1",
                "color": "#00AA00",
            }
        ]

    monkeypatch.setattr(ag, "_fetch_image_data", _fake_fetch_image_data)
    monkeypatch.setattr(ag, "_call_vlm_for_annotations", _fake_call_vlm_for_annotations)

    question_results = [
        {"question_id": "1", "page_indices": [0], "score": 1, "max_score": 1},
        {"question_id": "2", "page_indices": [0], "score": 1, "max_score": 1},
    ]

    async def _run():
        return await _generate_annotations_for_page(
            grading_history_id="history-1",
            student_key="student-1",
            page_index=0,
            question_page_index=0,
            page_image=page_image,
            question_results=question_results,
            strict_vlm=True,
        )

    annotations = asyncio.run(_run())
    assert len(annotations) == 2
    assert calls[0] == 2
    assert calls.count(1) == 2
