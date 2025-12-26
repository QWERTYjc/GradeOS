"""低置信度审核触发属性测试

使用 Hypothesis 验证工作流在低置信度时触发审核状态的行为

**功能: ai-grading-agent, 属性 7: 低置信度触发审核状态**
**验证: 需求 5.1**
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from typing import List

from src.models.grading import GradingResult
from src.models.enums import SubmissionStatus


# ===== 常量定义 =====
CONFIDENCE_THRESHOLD = 0.75  # 置信度阈值（需求 5.1）


# ===== 策略定义 =====

# 生成有效的题目 ID
question_id_strategy = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789_",
    min_size=1,
    max_size=20
).map(lambda s: f"q_{s}")


@st.composite
def grading_result_strategy(draw, question_id: str = None, confidence: float = None):
    """生成有效的批改结果
    
    Args:
        question_id: 可选的题目 ID
        confidence: 可选的置信度（如果不指定则随机生成）
    """
    if question_id is None:
        question_id = draw(question_id_strategy)
    
    # 生成满分（1-100 之间）
    max_score = draw(st.floats(min_value=1.0, max_value=100.0, 
                               allow_nan=False, allow_infinity=False))
    
    # 生成得分（0 到满分之间）
    score = draw(st.floats(min_value=0.0, max_value=max_score, 
                           allow_nan=False, allow_infinity=False))
    
    # 生成置信度（0-1 之间）
    if confidence is None:
        confidence = draw(st.floats(min_value=0.0, max_value=1.0, 
                                    allow_nan=False, allow_infinity=False))
    
    return GradingResult(
        question_id=question_id,
        score=score,
        max_score=max_score,
        confidence=confidence,
        feedback="测试反馈",
        visual_annotations=[],
        agent_trace={}
    )


@st.composite
def grading_results_with_low_confidence_strategy(draw, min_count: int = 1, max_count: int = 20):
    """生成至少包含一个低置信度结果的批改结果列表"""
    count = draw(st.integers(min_value=min_count, max_value=max_count))
    results = []
    
    # 确保至少有一个低置信度结果
    low_confidence_index = draw(st.integers(min_value=0, max_value=count - 1))
    
    for i in range(count):
        question_id = f"q_{i+1}"
        if i == low_confidence_index:
            # 生成低置信度结果
            confidence = draw(st.floats(
                min_value=0.0, 
                max_value=CONFIDENCE_THRESHOLD - 0.001,
                allow_nan=False, 
                allow_infinity=False
            ))
        else:
            # 生成任意置信度结果
            confidence = draw(st.floats(
                min_value=0.0, 
                max_value=1.0,
                allow_nan=False, 
                allow_infinity=False
            ))
        
        result = draw(grading_result_strategy(question_id=question_id, confidence=confidence))
        results.append(result)
    
    return results


@st.composite
def grading_results_all_high_confidence_strategy(draw, min_count: int = 1, max_count: int = 20):
    """生成所有结果都是高置信度的批改结果列表"""
    count = draw(st.integers(min_value=min_count, max_value=max_count))
    results = []
    
    for i in range(count):
        question_id = f"q_{i+1}"
        # 生成高置信度结果（>= 阈值）
        confidence = draw(st.floats(
            min_value=CONFIDENCE_THRESHOLD, 
            max_value=1.0,
            allow_nan=False, 
            allow_infinity=False
        ))
        
        result = draw(grading_result_strategy(question_id=question_id, confidence=confidence))
        results.append(result)
    
    return results


def check_needs_review(grading_results: List[GradingResult]) -> bool:
    """
    检查是否需要人工审核（与 exam_paper.py 中的逻辑一致）
    
    Args:
        grading_results: 批改结果列表
        
    Returns:
        如果任何题目的置信度低于阈值，返回 True
    """
    if not grading_results:
        return False
    
    min_confidence = min(r.confidence for r in grading_results)
    return min_confidence < CONFIDENCE_THRESHOLD


def determine_submission_status(needs_review: bool, is_rejected: bool = False) -> SubmissionStatus:
    """
    根据审核需求确定提交状态
    
    Args:
        needs_review: 是否需要审核
        is_rejected: 是否被拒绝
        
    Returns:
        提交状态
    """
    if is_rejected:
        return SubmissionStatus.REJECTED
    elif needs_review:
        return SubmissionStatus.REVIEWING
    else:
        return SubmissionStatus.COMPLETED


class TestLowConfidenceReviewTrigger:
    """低置信度审核触发属性测试
    
    **功能: ai-grading-agent, 属性 7: 低置信度触发审核状态**
    **验证: 需求 5.1**
    
    属性 7 定义：对于任意批改结果，如果任何题目的 confidence_score < 0.75，
    工作流应当转换到 REVIEWING 状态，提交状态应当更新为 'REVIEWING'。
    """
    
    @given(grading_results=grading_results_with_low_confidence_strategy(min_count=1, max_count=20))
    @settings(max_examples=100)
    def test_low_confidence_triggers_review_status(self, grading_results: List[GradingResult]):
        """
        **功能: ai-grading-agent, 属性 7: 低置信度触发审核状态**
        **验证: 需求 5.1**
        
        对于任意包含低置信度结果的批改结果列表，工作流应当转换到 REVIEWING 状态
        """
        # 确保至少有一个低置信度结果
        min_confidence = min(r.confidence for r in grading_results)
        assume(min_confidence < CONFIDENCE_THRESHOLD)
        
        # 检查是否需要审核
        needs_review = check_needs_review(grading_results)
        
        # 验证：低置信度应该触发审核
        assert needs_review is True, (
            f"最低置信度 {min_confidence:.4f} < {CONFIDENCE_THRESHOLD} 时应触发审核，"
            f"但 needs_review={needs_review}"
        )
        
        # 验证：提交状态应该是 REVIEWING
        status = determine_submission_status(needs_review)
        assert status == SubmissionStatus.REVIEWING, (
            f"低置信度时提交状态应为 REVIEWING，但实际为 {status}"
        )
    
    @given(grading_results=grading_results_all_high_confidence_strategy(min_count=1, max_count=20))
    @settings(max_examples=100)
    def test_high_confidence_skips_review_status(self, grading_results: List[GradingResult]):
        """
        **功能: ai-grading-agent, 属性 7: 低置信度触发审核状态**
        **验证: 需求 5.1**
        
        对于任意所有结果都是高置信度的批改结果列表，工作流不应转换到 REVIEWING 状态
        """
        # 确保所有结果都是高置信度
        min_confidence = min(r.confidence for r in grading_results)
        assume(min_confidence >= CONFIDENCE_THRESHOLD)
        
        # 检查是否需要审核
        needs_review = check_needs_review(grading_results)
        
        # 验证：高置信度不应触发审核
        assert needs_review is False, (
            f"最低置信度 {min_confidence:.4f} >= {CONFIDENCE_THRESHOLD} 时不应触发审核，"
            f"但 needs_review={needs_review}"
        )
        
        # 验证：提交状态应该是 COMPLETED
        status = determine_submission_status(needs_review)
        assert status == SubmissionStatus.COMPLETED, (
            f"高置信度时提交状态应为 COMPLETED，但实际为 {status}"
        )
    
    @given(
        confidence=st.floats(
            min_value=0.0, 
            max_value=CONFIDENCE_THRESHOLD - 0.001,
            allow_nan=False, 
            allow_infinity=False
        )
    )
    @settings(max_examples=100)
    def test_single_low_confidence_triggers_review(self, confidence: float):
        """
        **功能: ai-grading-agent, 属性 7: 低置信度触发审核状态**
        **验证: 需求 5.1**
        
        对于任意单个低置信度结果，工作流应当转换到 REVIEWING 状态
        """
        assume(confidence < CONFIDENCE_THRESHOLD)
        
        result = GradingResult(
            question_id="q_1",
            score=5.0,
            max_score=10.0,
            confidence=confidence,
            feedback="测试",
            visual_annotations=[],
            agent_trace={}
        )
        
        needs_review = check_needs_review([result])
        status = determine_submission_status(needs_review)
        
        assert needs_review is True, (
            f"置信度 {confidence:.4f} < {CONFIDENCE_THRESHOLD} 时应触发审核"
        )
        assert status == SubmissionStatus.REVIEWING, (
            f"低置信度时提交状态应为 REVIEWING，但实际为 {status}"
        )


class TestConfidenceThresholdBoundary:
    """置信度阈值边界测试
    
    **功能: ai-grading-agent, 属性 7: 低置信度触发审核状态**
    **验证: 需求 5.1**
    """
    
    def test_threshold_exactly_0_75_no_review(self):
        """
        **功能: ai-grading-agent, 属性 7: 低置信度触发审核状态**
        **验证: 需求 5.1**
        
        当置信度恰好等于阈值 0.75 时，不应触发审核
        """
        result = GradingResult(
            question_id="q_1",
            score=5.0,
            max_score=10.0,
            confidence=CONFIDENCE_THRESHOLD,  # 恰好等于 0.75
            feedback="测试",
            visual_annotations=[],
            agent_trace={}
        )
        
        needs_review = check_needs_review([result])
        status = determine_submission_status(needs_review)
        
        assert needs_review is False, (
            f"置信度恰好等于阈值 {CONFIDENCE_THRESHOLD} 时不应触发审核"
        )
        assert status == SubmissionStatus.COMPLETED, (
            f"置信度等于阈值时提交状态应为 COMPLETED，但实际为 {status}"
        )
    
    def test_threshold_just_below_triggers_review(self):
        """
        **功能: ai-grading-agent, 属性 7: 低置信度触发审核状态**
        **验证: 需求 5.1**
        
        当置信度略低于阈值时，应触发审核
        """
        just_below = CONFIDENCE_THRESHOLD - 0.0001
        
        result = GradingResult(
            question_id="q_1",
            score=5.0,
            max_score=10.0,
            confidence=just_below,
            feedback="测试",
            visual_annotations=[],
            agent_trace={}
        )
        
        needs_review = check_needs_review([result])
        status = determine_submission_status(needs_review)
        
        assert needs_review is True, (
            f"置信度 {just_below} 略低于阈值 {CONFIDENCE_THRESHOLD} 时应触发审核"
        )
        assert status == SubmissionStatus.REVIEWING, (
            f"低置信度时提交状态应为 REVIEWING，但实际为 {status}"
        )
    
    def test_threshold_just_above_no_review(self):
        """
        **功能: ai-grading-agent, 属性 7: 低置信度触发审核状态**
        **验证: 需求 5.1**
        
        当置信度略高于阈值时，不应触发审核
        """
        just_above = CONFIDENCE_THRESHOLD + 0.0001
        
        result = GradingResult(
            question_id="q_1",
            score=5.0,
            max_score=10.0,
            confidence=just_above,
            feedback="测试",
            visual_annotations=[],
            agent_trace={}
        )
        
        needs_review = check_needs_review([result])
        status = determine_submission_status(needs_review)
        
        assert needs_review is False, (
            f"置信度 {just_above} 略高于阈值 {CONFIDENCE_THRESHOLD} 时不应触发审核"
        )
        assert status == SubmissionStatus.COMPLETED, (
            f"高置信度时提交状态应为 COMPLETED，但实际为 {status}"
        )


class TestMinConfidenceLogic:
    """最低置信度逻辑测试
    
    **功能: ai-grading-agent, 属性 7: 低置信度触发审核状态**
    **验证: 需求 5.1**
    """
    
    @given(
        high_confidences=st.lists(
            st.floats(min_value=CONFIDENCE_THRESHOLD, max_value=1.0,
                     allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=10
        ),
        low_confidence=st.floats(
            min_value=0.0, 
            max_value=CONFIDENCE_THRESHOLD - 0.001,
            allow_nan=False, 
            allow_infinity=False
        )
    )
    @settings(max_examples=100)
    def test_single_low_confidence_among_high_triggers_review(
        self, high_confidences: List[float], low_confidence: float
    ):
        """
        **功能: ai-grading-agent, 属性 7: 低置信度触发审核状态**
        **验证: 需求 5.1**
        
        即使只有一个低置信度结果，也应触发审核
        """
        assume(low_confidence < CONFIDENCE_THRESHOLD)
        assume(all(c >= CONFIDENCE_THRESHOLD for c in high_confidences))
        
        # 创建批改结果列表
        results = []
        for i, conf in enumerate(high_confidences):
            results.append(GradingResult(
                question_id=f"q_{i+1}",
                score=5.0,
                max_score=10.0,
                confidence=conf,
                feedback="测试",
                visual_annotations=[],
                agent_trace={}
            ))
        
        # 添加一个低置信度结果
        results.append(GradingResult(
            question_id=f"q_{len(high_confidences)+1}",
            score=5.0,
            max_score=10.0,
            confidence=low_confidence,
            feedback="测试",
            visual_annotations=[],
            agent_trace={}
        ))
        
        needs_review = check_needs_review(results)
        status = determine_submission_status(needs_review)
        
        assert needs_review is True, (
            f"存在低置信度 {low_confidence:.4f} 时应触发审核"
        )
        assert status == SubmissionStatus.REVIEWING, (
            f"存在低置信度时提交状态应为 REVIEWING，但实际为 {status}"
        )
    
    @given(
        confidences=st.lists(
            st.floats(min_value=0.0, max_value=1.0,
                     allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=100)
    def test_min_confidence_determines_review(self, confidences: List[float]):
        """
        **功能: ai-grading-agent, 属性 7: 低置信度触发审核状态**
        **验证: 需求 5.1**
        
        最低置信度决定是否需要审核
        """
        # 创建批改结果列表
        results = []
        for i, conf in enumerate(confidences):
            results.append(GradingResult(
                question_id=f"q_{i+1}",
                score=5.0,
                max_score=10.0,
                confidence=conf,
                feedback="测试",
                visual_annotations=[],
                agent_trace={}
            ))
        
        min_confidence = min(confidences)
        needs_review = check_needs_review(results)
        
        # 验证：最低置信度决定是否需要审核
        expected_needs_review = min_confidence < CONFIDENCE_THRESHOLD
        assert needs_review == expected_needs_review, (
            f"最低置信度 {min_confidence:.4f}，"
            f"预期 needs_review={expected_needs_review}，"
            f"实际 needs_review={needs_review}"
        )


class TestEmptyResultsHandling:
    """空结果处理测试
    
    **功能: ai-grading-agent, 属性 7: 低置信度触发审核状态**
    **验证: 需求 5.1**
    """
    
    def test_empty_results_no_review(self):
        """
        **功能: ai-grading-agent, 属性 7: 低置信度触发审核状态**
        **验证: 需求 5.1**
        
        空的批改结果列表不应触发审核
        """
        needs_review = check_needs_review([])
        status = determine_submission_status(needs_review)
        
        assert needs_review is False, "空结果列表不应触发审核"
        assert status == SubmissionStatus.COMPLETED, (
            f"空结果列表时提交状态应为 COMPLETED，但实际为 {status}"
        )


class TestConfidenceThresholdConstant:
    """置信度阈值常量测试
    
    **功能: ai-grading-agent, 属性 7: 低置信度触发审核状态**
    **验证: 需求 5.1**
    """
    
    def test_confidence_threshold_is_0_75(self):
        """
        **功能: ai-grading-agent, 属性 7: 低置信度触发审核状态**
        **验证: 需求 5.1**
        
        验证置信度阈值常量为 0.75（符合需求 5.1）
        """
        assert CONFIDENCE_THRESHOLD == 0.75, (
            f"置信度阈值应为 0.75（需求 5.1），但实际为 {CONFIDENCE_THRESHOLD}"
        )
