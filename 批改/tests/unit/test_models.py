"""测试核心数据模型"""

import pytest
from src.models import (
    FileType,
    SubmissionStatus,
    ReviewAction,
    SubmissionRequest,
    SubmissionResponse,
    BoundingBox,
    QuestionRegion,
    GradingResult,
    GradingState,
    Rubric,
    ScoringPoint,
    ReviewSignal,
)


def test_file_type_enum():
    """测试文件类型枚举"""
    assert FileType.PDF == "pdf"
    assert FileType.IMAGE == "image"


def test_submission_status_enum():
    """测试提交状态枚举"""
    assert SubmissionStatus.UPLOADED == "UPLOADED"
    assert SubmissionStatus.COMPLETED == "COMPLETED"


def test_review_action_enum():
    """测试审核操作枚举"""
    assert ReviewAction.APPROVE == "APPROVE"
    assert ReviewAction.OVERRIDE == "OVERRIDE"
    assert ReviewAction.REJECT == "REJECT"


def test_bounding_box_creation():
    """测试边界框创建"""
    bbox = BoundingBox(ymin=100, xmin=50, ymax=300, xmax=400)
    assert bbox.ymin == 100
    assert bbox.xmin == 50
    assert bbox.ymax == 300
    assert bbox.xmax == 400


def test_bounding_box_validation():
    """测试边界框验证"""
    # ymax 必须大于 ymin
    with pytest.raises(ValueError, match="ymax 必须大于 ymin"):
        BoundingBox(ymin=300, xmin=50, ymax=100, xmax=400)
    
    # xmax 必须大于 xmin
    with pytest.raises(ValueError, match="xmax 必须大于 xmin"):
        BoundingBox(ymin=100, xmin=400, ymax=300, xmax=50)


def test_submission_request():
    """测试提交请求模型"""
    request = SubmissionRequest(
        exam_id="exam_001",
        student_id="student_001",
        file_type=FileType.PDF,
        file_data=b"test_data"
    )
    assert request.exam_id == "exam_001"
    assert request.file_type == FileType.PDF


def test_submission_response():
    """测试提交响应模型"""
    response = SubmissionResponse(
        submission_id="sub_001",
        status=SubmissionStatus.UPLOADED,
        estimated_completion_time=120
    )
    assert response.submission_id == "sub_001"
    assert response.status == SubmissionStatus.UPLOADED


def test_question_region():
    """测试题目区域模型"""
    bbox = BoundingBox(ymin=100, xmin=50, ymax=300, xmax=400)
    region = QuestionRegion(
        question_id="q1",
        page_index=0,
        bounding_box=bbox
    )
    assert region.question_id == "q1"
    assert region.bounding_box.ymin == 100


def test_grading_result():
    """测试批改结果模型"""
    result = GradingResult(
        question_id="q1",
        score=8.5,
        max_score=10.0,
        confidence=0.92,
        feedback="解题思路正确"
    )
    assert result.score == 8.5
    assert result.confidence == 0.92
    assert 0.0 <= result.confidence <= 1.0


def test_grading_state():
    """测试批改状态模型"""
    state: GradingState = {
        "question_image": "base64_image",
        "rubric": "评分细则",
        "max_score": 10.0,
        "revision_count": 0,
        "is_finalized": False
    }
    assert state["max_score"] == 10.0
    assert state["is_finalized"] is False


def test_rubric():
    """测试评分细则模型"""
    scoring_points = [
        ScoringPoint(description="正确列出公式", score=3.0, required=True),
        ScoringPoint(description="计算过程正确", score=5.0, required=True),
    ]
    rubric = Rubric(
        exam_id="exam_001",
        question_id="q1",
        rubric_text="评分细则文本",
        max_score=10.0,
        scoring_points=scoring_points
    )
    assert rubric.max_score == 10.0
    assert len(rubric.scoring_points) == 2


def test_review_signal():
    """测试审核信号模型"""
    signal = ReviewSignal(
        submission_id="sub_001",
        question_id="q1",
        action=ReviewAction.OVERRIDE,
        override_score=9.0,
        reviewer_id="teacher_001"
    )
    assert signal.action == ReviewAction.OVERRIDE
    assert signal.override_score == 9.0
