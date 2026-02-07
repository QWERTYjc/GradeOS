"""Unit tests for active core models."""

import pytest
from src.models import (
    FileType,
    SubmissionStatus,
    ReviewAction,
    BoundingBox,
    QuestionRegion,
    GradingResult,
    GradingState,
    Rubric,
    ScoringPoint,
)


def test_file_type_enum():
    assert FileType.PDF == "pdf"
    assert FileType.IMAGE == "image"


def test_submission_status_enum():
    assert SubmissionStatus.UPLOADED == "UPLOADED"
    assert SubmissionStatus.COMPLETED == "COMPLETED"


def test_review_action_enum():
    assert ReviewAction.APPROVE == "APPROVE"
    assert ReviewAction.OVERRIDE == "OVERRIDE"
    assert ReviewAction.REJECT == "REJECT"


def test_bounding_box_creation():
    bbox = BoundingBox(ymin=100, xmin=50, ymax=300, xmax=400)
    assert bbox.ymin == 100
    assert bbox.xmin == 50
    assert bbox.ymax == 300
    assert bbox.xmax == 400


def test_bounding_box_validation():
    with pytest.raises(ValueError):
        BoundingBox(ymin=300, xmin=50, ymax=100, xmax=400)
    with pytest.raises(ValueError):
        BoundingBox(ymin=100, xmin=400, ymax=300, xmax=50)


def test_question_region():
    bbox = BoundingBox(ymin=100, xmin=50, ymax=300, xmax=400)
    region = QuestionRegion(question_id="q1", page_index=0, bounding_box=bbox)
    assert region.question_id == "q1"
    assert region.bounding_box.ymin == 100


def test_grading_result():
    result = GradingResult(
        question_id="q1",
        score=8.5,
        max_score=10.0,
        confidence=0.92,
        feedback="ok",
    )
    assert result.score == 8.5
    assert result.confidence == 0.92
    assert 0.0 <= result.confidence <= 1.0


def test_grading_state():
    state: GradingState = {
        "question_image": "base64_image",
        "rubric": "rubric",
        "max_score": 10.0,
        "revision_count": 0,
        "is_finalized": False,
    }
    assert state["max_score"] == 10.0
    assert state["is_finalized"] is False


def test_rubric():
    scoring_points = [
        ScoringPoint(description="point1", score=3.0, required=True),
        ScoringPoint(description="point2", score=5.0, required=True),
    ]
    rubric = Rubric(
        exam_id="exam_001",
        question_id="q1",
        rubric_text="rubric",
        max_score=10.0,
        scoring_points=scoring_points,
    )
    assert rubric.max_score == 10.0
    assert len(rubric.scoring_points) == 2
