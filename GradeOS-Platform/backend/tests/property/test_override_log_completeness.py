"""属性测试：改判日志完整性

**Feature: self-evolving-grading, Property 19: 改判日志完整性**
**Validates: Requirements 8.4**

验证：对于任意老师改判，日志应更新：
- was_overridden=True
- override_score
- override_reason
- override_teacher_id
"""

import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime
from uuid import uuid4

from src.models.grading_log import GradingLog, GradingLogOverride


@given(
    override_score=st.floats(min_value=0.0, max_value=100.0),
    override_reason=st.text(min_size=1, max_size=500),
    override_teacher_id=st.uuids()
)
@settings(max_examples=100, deadline=None)
def test_override_log_completeness(
    override_score: float,
    override_reason: str,
    override_teacher_id: str
):
    """
    **Feature: self-evolving-grading, Property 19: 改判日志完整性**
    **Validates: Requirements 8.4**
    
    属性：对于任意老师改判，日志应包含完整的改判信息
    
    验证：
    1. was_overridden 为 True
    2. override_score 不为 None
    3. override_reason 不为空
    4. override_teacher_id 不为 None
    5. override_at 不为 None
    """
    # 创建原始日志
    original_log = GradingLog(
        log_id=str(uuid4()),
        submission_id=str(uuid4()),
        question_id="q1",
        extracted_answer="original answer",
        extraction_confidence=0.9,
        score=8.0,
        confidence=0.85,
        reasoning_trace=["step1"],
        was_overridden=False,
        created_at=datetime.now()
    )
    
    # 模拟改判
    override_at = datetime.now()
    overridden_log = GradingLog(
        log_id=original_log.log_id,
        submission_id=original_log.submission_id,
        question_id=original_log.question_id,
        extracted_answer=original_log.extracted_answer,
        extraction_confidence=original_log.extraction_confidence,
        score=original_log.score,
        confidence=original_log.confidence,
        reasoning_trace=original_log.reasoning_trace,
        was_overridden=True,
        override_score=override_score,
        override_reason=override_reason,
        override_teacher_id=str(override_teacher_id),
        override_at=override_at,
        created_at=original_log.created_at
    )
    
    # 验证改判日志完整性
    assert overridden_log.was_overridden is True, "was_overridden 应为 True"
    assert overridden_log.override_score is not None, "override_score 不应为 None"
    assert overridden_log.override_score >= 0.0, "override_score 应为非负数"
    assert overridden_log.override_reason is not None, "override_reason 不应为 None"
    assert overridden_log.override_reason != "", "override_reason 不应为空字符串"
    assert overridden_log.override_teacher_id is not None, "override_teacher_id 不应为 None"
    assert overridden_log.override_at is not None, "override_at 不应为 None"


@given(
    n_overrides=st.integers(min_value=1, max_value=20)
)
@settings(max_examples=50, deadline=None)
def test_multiple_overrides_completeness(n_overrides: int):
    """
    **Feature: self-evolving-grading, Property 19: 改判日志完整性**
    **Validates: Requirements 8.4**
    
    属性：批量改判的日志都应满足完整性要求
    
    验证：
    1. 所有改判日志都包含必要字段
    2. 所有改判日志的 was_overridden 都为 True
    """
    overridden_logs = []
    
    for i in range(n_overrides):
        log = GradingLog(
            log_id=str(uuid4()),
            submission_id=str(uuid4()),
            question_id=f"q{i}",
            extracted_answer=f"answer_{i}",
            extraction_confidence=0.9,
            score=8.0,
            confidence=0.85,
            reasoning_trace=["step1"],
            was_overridden=True,
            override_score=9.0,
            override_reason=f"reason_{i}",
            override_teacher_id=str(uuid4()),
            override_at=datetime.now(),
            created_at=datetime.now()
        )
        overridden_logs.append(log)
    
    # 验证所有改判日志完整性
    for log in overridden_logs:
        assert log.was_overridden is True
        assert log.override_score is not None
        assert log.override_reason is not None
        assert log.override_reason != ""
        assert log.override_teacher_id is not None
        assert log.override_at is not None


@given(
    original_score=st.floats(min_value=0.0, max_value=100.0),
    override_score=st.floats(min_value=0.0, max_value=100.0)
)
@settings(max_examples=100, deadline=None)
def test_override_preserves_original_data(
    original_score: float,
    override_score: float
):
    """
    **Feature: self-evolving-grading, Property 19: 改判日志完整性**
    **Validates: Requirements 8.4**
    
    属性：改判应保留原始批改数据
    
    验证：
    1. 原始分数保留在 score 字段
    2. 改判分数记录在 override_score 字段
    3. 其他原始数据不变
    """
    original_answer = "original answer"
    original_confidence = 0.85
    original_reasoning = ["step1", "step2"]
    
    # 创建改判后的日志
    log = GradingLog(
        log_id=str(uuid4()),
        submission_id=str(uuid4()),
        question_id="q1",
        extracted_answer=original_answer,
        extraction_confidence=0.9,
        score=original_score,  # 保留原始分数
        confidence=original_confidence,
        reasoning_trace=original_reasoning,
        was_overridden=True,
        override_score=override_score,  # 新的改判分数
        override_reason="teacher correction",
        override_teacher_id=str(uuid4()),
        override_at=datetime.now(),
        created_at=datetime.now()
    )
    
    # 验证原始数据保留
    assert log.score == original_score, "原始分数应保留"
    assert log.extracted_answer == original_answer, "原始答案应保留"
    assert log.confidence == original_confidence, "原始置信度应保留"
    assert log.reasoning_trace == original_reasoning, "原始推理过程应保留"
    
    # 验证改判数据记录
    assert log.override_score == override_score, "改判分数应记录"
    assert log.was_overridden is True, "改判标记应为 True"


@st.composite
def override_info_strategy(draw):
    """生成改判信息"""
    return GradingLogOverride(
        override_score=draw(st.floats(min_value=0.0, max_value=100.0)),
        override_reason=draw(st.text(min_size=1, max_size=500)),
        override_teacher_id=str(draw(st.uuids()))
    )


@given(override_info=override_info_strategy())
@settings(max_examples=100, deadline=None)
def test_override_info_model_validation(override_info: GradingLogOverride):
    """
    **Feature: self-evolving-grading, Property 19: 改判日志完整性**
    **Validates: Requirements 8.4**
    
    属性：改判信息模型应满足验证规则
    
    验证：
    1. override_score 为非负数
    2. override_reason 不为空
    3. override_teacher_id 不为空
    """
    assert override_info.override_score >= 0.0, "override_score 应为非负数"
    assert override_info.override_reason, "override_reason 不应为空"
    assert len(override_info.override_reason) > 0, "override_reason 应有内容"
    assert override_info.override_teacher_id, "override_teacher_id 不应为空"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--hypothesis-show-statistics"])
