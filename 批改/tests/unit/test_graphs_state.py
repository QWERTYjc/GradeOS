"""Graph State 单元测试"""

import pytest
from datetime import datetime
from src.graphs.state import (
    GradingGraphState,
    BatchGradingGraphState,
    RuleUpgradeGraphState,
    create_initial_grading_state,
    create_initial_batch_state,
    create_initial_upgrade_state,
)


def test_create_initial_grading_state():
    """测试创建初始批改状态"""
    state = create_initial_grading_state(
        job_id="job_001",
        submission_id="sub_001",
        exam_id="exam_001",
        student_id="student_001",
        file_paths=["path/to/file1.pdf", "path/to/file2.pdf"],
        rubric="评分细则内容"
    )
    
    # 验证基础字段
    assert state["job_id"] == "job_001"
    assert state["submission_id"] == "sub_001"
    assert state["exam_id"] == "exam_001"
    assert state["student_id"] == "student_001"
    assert state["file_paths"] == ["path/to/file1.pdf", "path/to/file2.pdf"]
    assert state["rubric"] == "评分细则内容"
    
    # 验证初始化字段
    assert state["current_stage"] == "initialized"
    assert state["percentage"] == 0.0
    assert state["grading_results"] == []
    assert state["errors"] == []
    assert state["retry_count"] == 0
    assert state["needs_review"] is False
    assert state["review_result"] is None
    assert "created_at" in state["timestamps"]


def test_create_initial_batch_state():
    """测试创建初始批量批改状态"""
    state = create_initial_batch_state(
        batch_id="batch_001",
        exam_id="exam_001",
        pdf_path="path/to/batch.pdf",
        rubric="评分细则"
    )
    
    assert state["batch_id"] == "batch_001"
    assert state["exam_id"] == "exam_001"
    assert state["pdf_path"] == "path/to/batch.pdf"
    assert state["rubric"] == "评分细则"
    assert state["current_stage"] == "initialized"
    assert state["student_boundaries"] == []
    assert state["submission_jobs"] == []


def test_create_initial_upgrade_state():
    """测试创建初始规则升级状态"""
    time_window = {"start": "2024-01-01", "end": "2024-01-31"}
    state = create_initial_upgrade_state(
        upgrade_id="upgrade_001",
        trigger_type="scheduled",
        time_window=time_window
    )
    
    assert state["upgrade_id"] == "upgrade_001"
    assert state["trigger_type"] == "scheduled"
    assert state["time_window"] == time_window
    assert state["current_stage"] == "initialized"
    assert state["deployment_status"] == "pending"
    assert state["regression_detected"] is False


def test_grading_state_type_hints():
    """测试 GradingGraphState 类型提示"""
    # 这个测试主要验证 TypedDict 定义是否正确
    state: GradingGraphState = {
        "job_id": "test",
        "submission_id": "test",
        "exam_id": "test",
        "student_id": "test",
        "current_stage": "test",
        "percentage": 50.0,
    }
    
    assert state["job_id"] == "test"
    assert state["percentage"] == 50.0


def test_state_incremental_update():
    """测试状态增量更新"""
    state = create_initial_grading_state(
        job_id="job_001",
        submission_id="sub_001",
        exam_id="exam_001",
        student_id="student_001",
        file_paths=["file.pdf"],
        rubric="rubric"
    )
    
    # 增量更新
    updated_state = {
        **state,
        "current_stage": "segmenting",
        "percentage": 25.0,
        "artifacts": {"segments": [1, 2, 3]}
    }
    
    assert updated_state["current_stage"] == "segmenting"
    assert updated_state["percentage"] == 25.0
    assert updated_state["artifacts"]["segments"] == [1, 2, 3]
    # 原有字段保持不变
    assert updated_state["job_id"] == "job_001"
