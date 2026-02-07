"""LangGraph state definitions used by grading workflows."""

from __future__ import annotations

from datetime import datetime
import operator
from typing import Annotated, Any, Dict, List, Optional, TypedDict


def last_value(current: Any, new: Any) -> Any:
    """Reducer for concurrent updates where the latest non-None value wins."""
    return new if new is not None else current


class GradingGraphState(TypedDict, total=False):
    # Identity
    job_id: str
    submission_id: str
    exam_id: str
    student_id: str

    # Inputs
    inputs: Dict[str, Any]
    grading_mode: Optional[str]
    file_paths: List[str]
    rubric: str

    # Progress
    progress: Dict[str, Any]
    current_stage: str
    percentage: float

    # Outputs
    artifacts: Dict[str, Any]
    grading_results: List[Dict[str, Any]]
    total_score: float
    max_total_score: float

    # Error handling
    errors: List[Dict[str, Any]]
    retry_count: int

    # Metadata
    timestamps: Dict[str, str]

    # Human-in-the-loop
    needs_review: bool
    review_result: Optional[Dict[str, Any]]
    external_event: Optional[Dict[str, Any]]

    # Agent data
    pending_questions: List[Dict[str, Any]]
    completed_questions: List[str]
    active_agent: Optional[str]
    agent_results: Dict[str, Any]


class BatchGradingGraphState(TypedDict, total=False):
    # Identity
    batch_id: str
    exam_id: str
    api_key: str
    subject: str

    # Inputs
    inputs: Dict[str, Any]
    grading_mode: Annotated[Optional[str], last_value]
    pdf_path: str
    rubric: str
    answer_images: List[str]
    rubric_images: List[str]
    answer_image_refs: List[Dict[str, Any]]
    rubric_image_refs: List[Dict[str, Any]]
    student_mapping: List[Dict[str, Any]]

    # Pre-processing
    processed_images: List[str]
    processed_image_refs: List[Dict[str, Any]]
    parsed_rubric: Dict[str, Any]

    # Index output
    index_results: Dict[str, Any]
    student_page_map: Dict[int, str]
    indexed_students: List[Dict[str, Any]]
    index_unidentified_pages: List[int]
    file_index_by_page: Dict[int, Dict[str, Any]]

    # Page grading
    grading_results: Annotated[List[Dict[str, Any]], operator.add]

    # Cross page merge
    merged_questions: List[Dict[str, Any]]
    cross_page_questions: List[Dict[str, Any]]

    # Batch controls
    batch_config: Dict[str, Any]
    batch_progress: Annotated[Dict[str, Any], last_value]
    batch_retry_needed: Annotated[Dict[str, Any], last_value]

    # Student aggregation
    student_boundaries: List[Dict[str, Any]]
    student_results: Annotated[List[Dict[str, Any]], operator.add]
    confessed_results: Annotated[List[Dict[str, Any]], last_value]
    reviewed_results: Annotated[List[Dict[str, Any]], last_value]

    # Review and report
    review_summary: Dict[str, Any]
    review_result: Optional[Dict[str, Any]]
    rubric_review_result: Optional[Dict[str, Any]]
    logic_review_results: List[Dict[str, Any]]
    class_report: Dict[str, Any]
    export_data: Dict[str, Any]

    # Legacy compatibility
    detected_students: List[str]
    submission_jobs: Annotated[List[Dict[str, Any]], operator.add]
    completed_submissions: List[str]
    failed_submissions: List[Dict[str, Any]]
    batch_results: List[Dict[str, Any]]

    # Progress and status
    progress: Dict[str, Any]
    current_stage: str
    percentage: float
    artifacts: Dict[str, Any]
    errors: List[Dict[str, Any]]
    retry_count: int
    timestamps: Dict[str, str]


class RuleUpgradeGraphState(TypedDict, total=False):
    upgrade_id: str
    trigger_type: str

    inputs: Dict[str, Any]
    time_window: Dict[str, str]

    mined_rules: List[Dict[str, Any]]
    rule_candidates: List[Dict[str, Any]]

    generated_patches: List[Dict[str, Any]]
    patch_metadata: Dict[str, Any]

    test_results: List[Dict[str, Any]]
    regression_detected: bool

    deployment_status: str
    deployed_version: Optional[str]
    rollback_triggered: bool

    progress: Dict[str, Any]
    current_stage: str
    percentage: float

    artifacts: Dict[str, Any]
    errors: List[Dict[str, Any]]
    retry_count: int
    timestamps: Dict[str, str]


def create_initial_grading_state(
    job_id: str,
    submission_id: str,
    exam_id: str,
    student_id: str,
    file_paths: List[str],
    rubric: str,
) -> GradingGraphState:
    return GradingGraphState(
        job_id=job_id,
        submission_id=submission_id,
        exam_id=exam_id,
        student_id=student_id,
        inputs={"file_paths": file_paths, "rubric": rubric},
        file_paths=file_paths,
        rubric=rubric,
        progress={},
        current_stage="initialized",
        percentage=0.0,
        artifacts={},
        grading_results=[],
        total_score=0.0,
        max_total_score=0.0,
        errors=[],
        retry_count=0,
        timestamps={"created_at": datetime.now().isoformat()},
        needs_review=False,
        review_result=None,
        external_event=None,
        pending_questions=[],
        completed_questions=[],
        active_agent=None,
        agent_results={},
    )


def create_initial_batch_state(
    batch_id: str,
    exam_id: str,
    pdf_path: str,
    rubric: str,
) -> BatchGradingGraphState:
    return BatchGradingGraphState(
        batch_id=batch_id,
        exam_id=exam_id,
        inputs={"pdf_path": pdf_path, "rubric": rubric},
        pdf_path=pdf_path,
        rubric=rubric,
        answer_image_refs=[],
        rubric_image_refs=[],
        processed_image_refs=[],
        index_results={},
        student_page_map={},
        indexed_students=[],
        index_unidentified_pages=[],
        file_index_by_page={},
        student_boundaries=[],
        detected_students=[],
        submission_jobs=[],
        completed_submissions=[],
        failed_submissions=[],
        progress={},
        current_stage="initialized",
        percentage=0.0,
        artifacts={},
        batch_results=[],
        errors=[],
        retry_count=0,
        timestamps={"created_at": datetime.now().isoformat()},
    )


def create_initial_upgrade_state(
    upgrade_id: str,
    trigger_type: str,
    time_window: Dict[str, str],
) -> RuleUpgradeGraphState:
    return RuleUpgradeGraphState(
        upgrade_id=upgrade_id,
        trigger_type=trigger_type,
        inputs={"time_window": time_window},
        time_window=time_window,
        mined_rules=[],
        rule_candidates=[],
        generated_patches=[],
        patch_metadata={},
        test_results=[],
        regression_detected=False,
        deployment_status="pending",
        deployed_version=None,
        rollback_triggered=False,
        progress={},
        current_stage="initialized",
        percentage=0.0,
        artifacts={},
        errors=[],
        retry_count=0,
        timestamps={"created_at": datetime.now().isoformat()},
    )


class AssistantGradingState(TypedDict, total=False):
    analysis_id: str
    submission_id: Optional[str]
    student_id: Optional[str]
    subject: Optional[str]

    inputs: Dict[str, Any]
    image_paths: List[str]
    image_base64_list: List[str]
    context_info: Optional[Dict[str, Any]]

    understanding: Dict[str, Any]
    errors: List[Dict[str, Any]]
    suggestions: List[Dict[str, Any]]
    deep_analysis: Dict[str, Any]

    report: Dict[str, Any]
    report_url: Optional[str]

    progress: Dict[str, Any]
    current_stage: str
    percentage: float

    processing_errors: List[Dict[str, Any]]
    retry_count: int
    timestamps: Dict[str, str]


def create_initial_assistant_state(
    analysis_id: str,
    images: List[str],
    submission_id: Optional[str] = None,
    student_id: Optional[str] = None,
    subject: Optional[str] = None,
    context_info: Optional[Dict[str, Any]] = None,
) -> AssistantGradingState:
    return AssistantGradingState(
        analysis_id=analysis_id,
        submission_id=submission_id,
        student_id=student_id,
        subject=subject,
        inputs={"images": images, "context_info": context_info or {}},
        image_paths=[],
        image_base64_list=images,
        context_info=context_info,
        understanding={},
        errors=[],
        suggestions=[],
        deep_analysis={},
        report={},
        report_url=None,
        progress={},
        current_stage="initialized",
        percentage=0.0,
        processing_errors=[],
        retry_count=0,
        timestamps={"created_at": datetime.now().isoformat()},
    )
