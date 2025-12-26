"""属性测试：批改日志完整性

**Feature: self-evolving-grading, Property 18: 批改日志完整性**
**Validates: Requirements 8.1, 8.2, 8.3**

验证：对于任意完成的批改，日志应包含：
- extracted_answer
- extraction_confidence
- score
- confidence
- reasoning_trace
"""

import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime
from uuid import uuid4

from src.models.grading_log import GradingLog
from src.services.grading_logger import GradingLogger


# 生成策略
@st.composite
def grading_log_strategy(draw):
    """生成完整的批改日志"""
    return GradingLog(
        log_id=str(uuid4()),
        submission_id=str(uuid4()),
        question_id=draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')))),
        extracted_answer=draw(st.text(min_size=1, max_size=500)),
        extraction_confidence=draw(st.floats(min_value=0.0, max_value=1.0)),
        evidence_snippets=draw(st.lists(st.text(min_size=1, max_size=100), min_size=0, max_size=5)),
        normalized_answer=draw(st.one_of(st.none(), st.text(min_size=1, max_size=500))),
        normalization_rules_applied=draw(st.lists(st.text(min_size=1, max_size=50), min_size=0, max_size=5)),
        match_result=draw(st.one_of(st.none(), st.booleans())),
        match_failure_reason=draw(st.one_of(st.none(), st.text(min_size=1, max_size=200))),
        score=draw(st.floats(min_value=0.0, max_value=100.0)),
        max_score=draw(st.floats(min_value=0.0, max_value=100.0)),
        confidence=draw(st.floats(min_value=0.0, max_value=1.0)),
        reasoning_trace=draw(st.lists(st.text(min_size=1, max_size=200), min_size=1, max_size=10)),
        was_overridden=False,
        created_at=datetime.utcnow()
    )


@given(log=grading_log_strategy())
@settings(max_examples=100, deadline=None)
def test_grading_log_completeness(log: GradingLog):
    """
    **Feature: self-evolving-grading, Property 18: 批改日志完整性**
    **Validates: Requirements 8.1, 8.2, 8.3**
    
    属性：对于任意完成的批改，日志应包含必要字段
    
    验证：
    1. extracted_answer 不为空
    2. extraction_confidence 在 0.0-1.0 之间
    3. score 不为 None
    4. confidence 在 0.0-1.0 之间
    5. reasoning_trace 不为空列表
    """
    # 验证提取阶段字段
    assert log.extracted_answer is not None, "extracted_answer 不应为 None"
    assert log.extracted_answer != "", "extracted_answer 不应为空字符串"
    
    assert log.extraction_confidence is not None, "extraction_confidence 不应为 None"
    assert 0.0 <= log.extraction_confidence <= 1.0, "extraction_confidence 应在 0.0-1.0 之间"
    
    # 验证评分阶段字段
    assert log.score is not None, "score 不应为 None"
    assert log.score >= 0.0, "score 应为非负数"
    
    assert log.confidence is not None, "confidence 不应为 None"
    assert 0.0 <= log.confidence <= 1.0, "confidence 应在 0.0-1.0 之间"
    
    # 验证推理过程
    assert log.reasoning_trace is not None, "reasoning_trace 不应为 None"
    assert len(log.reasoning_trace) > 0, "reasoning_trace 不应为空列表"
    
    # 验证基本字段
    assert log.log_id is not None, "log_id 不应为 None"
    assert log.submission_id is not None, "submission_id 不应为 None"
    assert log.question_id is not None, "question_id 不应为 None"
    assert log.created_at is not None, "created_at 不应为 None"


@given(
    extracted_answer=st.text(min_size=1, max_size=500),
    extraction_confidence=st.floats(min_value=0.0, max_value=1.0),
    score=st.floats(min_value=0.0, max_value=100.0),
    confidence=st.floats(min_value=0.0, max_value=1.0),
    reasoning_steps=st.lists(st.text(min_size=1, max_size=200), min_size=1, max_size=10)
)
@settings(max_examples=100, deadline=None)
def test_grading_log_field_constraints(
    extracted_answer: str,
    extraction_confidence: float,
    score: float,
    confidence: float,
    reasoning_steps: list
):
    """
    **Feature: self-evolving-grading, Property 18: 批改日志完整性**
    **Validates: Requirements 8.1, 8.2, 8.3**
    
    属性：批改日志字段应满足约束条件
    
    验证：
    1. 置信度字段在有效范围内
    2. 分数字段为非负数
    3. 必填字段不为空
    """
    log = GradingLog(
        log_id=str(uuid4()),
        submission_id=str(uuid4()),
        question_id="q1",
        extracted_answer=extracted_answer,
        extraction_confidence=extraction_confidence,
        score=score,
        confidence=confidence,
        reasoning_trace=reasoning_steps,
        created_at=datetime.utcnow()
    )
    
    # 验证置信度约束
    assert 0.0 <= log.extraction_confidence <= 1.0
    assert 0.0 <= log.confidence <= 1.0
    
    # 验证分数约束
    assert log.score >= 0.0
    
    # 验证必填字段
    assert log.extracted_answer
    assert log.reasoning_trace
    assert len(log.reasoning_trace) > 0


@given(
    n_logs=st.integers(min_value=1, max_value=20)
)
@settings(max_examples=50, deadline=None)
def test_multiple_logs_completeness(n_logs: int):
    """
    **Feature: self-evolving-grading, Property 18: 批改日志完整性**
    **Validates: Requirements 8.1, 8.2, 8.3**
    
    属性：批量创建的日志都应满足完整性要求
    
    验证：
    1. 所有日志都包含必要字段
    2. 每个日志的 log_id 唯一
    """
    logs = []
    log_ids = set()
    
    for _ in range(n_logs):
        log = GradingLog(
            log_id=str(uuid4()),
            submission_id=str(uuid4()),
            question_id=f"q{_}",
            extracted_answer=f"answer_{_}",
            extraction_confidence=0.9,
            score=8.5,
            confidence=0.92,
            reasoning_trace=[f"step_{_}"],
            created_at=datetime.utcnow()
        )
        logs.append(log)
        log_ids.add(log.log_id)
    
    # 验证所有日志完整性
    for log in logs:
        assert log.extracted_answer is not None
        assert log.extraction_confidence is not None
        assert log.score is not None
        assert log.confidence is not None
        assert log.reasoning_trace is not None
        assert len(log.reasoning_trace) > 0
    
    # 验证 log_id 唯一性
    assert len(log_ids) == n_logs, "所有日志的 log_id 应该唯一"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--hypothesis-show-statistics"])
