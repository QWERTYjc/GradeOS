"""信号处理状态转换属性测试

使用 Hypothesis 验证工作流信号处理的状态转换行为

**功能: ai-grading-agent, 属性 8: 信号处理状态转换**
**验证: 需求 5.3, 5.4, 5.5**
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from src.models.grading import GradingResult
from src.models.enums import SubmissionStatus, ReviewAction


# ===== 常量定义 =====
CONFIDENCE_THRESHOLD = 0.75  # 置信度阈值


# ===== 数据类定义 =====

@dataclass
class SignalProcessingResult:
    """信号处理结果"""
    final_status: SubmissionStatus
    final_results: List[GradingResult]
    is_terminated: bool
    error_message: Optional[str] = None


# ===== 策略定义 =====

# 生成有效的题目 ID
question_id_strategy = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789_",
    min_size=1,
    max_size=20
).map(lambda s: f"q_{s}")


@st.composite
def grading_result_strategy(draw, question_id: str = None, confidence: float = None):
    """生成有效的批改结果"""
    if question_id is None:
        question_id = draw(question_id_strategy)
    
    max_score = draw(st.floats(min_value=1.0, max_value=100.0, 
                               allow_nan=False, allow_infinity=False))
    score = draw(st.floats(min_value=0.0, max_value=max_score, 
                           allow_nan=False, allow_infinity=False))
    
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
def low_confidence_results_strategy(draw, min_count: int = 1, max_count: int = 10):
    """生成低置信度的批改结果列表（需要审核的场景）"""
    count = draw(st.integers(min_value=min_count, max_value=max_count))
    results = []
    
    for i in range(count):
        question_id = f"q_{i+1}"
        # 至少有一个低置信度
        if i == 0:
            confidence = draw(st.floats(
                min_value=0.0, 
                max_value=CONFIDENCE_THRESHOLD - 0.001,
                allow_nan=False, 
                allow_infinity=False
            ))
        else:
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
def override_data_strategy(draw, question_ids: List[str]):
    """生成覆盖数据"""
    override_data = {}
    
    # 随机选择要覆盖的题目
    num_overrides = draw(st.integers(min_value=1, max_value=len(question_ids)))
    selected_ids = draw(st.sampled_from(
        [tuple(sorted(question_ids[:num_overrides]))]
    ))
    
    for qid in selected_ids:
        override_score = draw(st.floats(
            min_value=0.0, 
            max_value=100.0,
            allow_nan=False, 
            allow_infinity=False
        ))
        override_data[qid] = {"score": override_score}
    
    return override_data


# ===== 信号处理逻辑（与 exam_paper.py 一致）=====

def process_review_signal(
    action: ReviewAction,
    grading_results: List[GradingResult],
    override_data: Optional[Dict[str, Any]] = None
) -> SignalProcessingResult:
    """
    处理审核信号（模拟 ExamPaperWorkflow 中的信号处理逻辑）
    
    Args:
        action: 审核操作
        grading_results: 原始批改结果
        override_data: 覆盖数据（仅 OVERRIDE 操作使用）
        
    Returns:
        SignalProcessingResult: 信号处理结果
    """
    # 复制结果列表以避免修改原始数据
    final_results = [
        GradingResult(
            question_id=r.question_id,
            score=r.score,
            max_score=r.max_score,
            confidence=r.confidence,
            feedback=r.feedback,
            visual_annotations=r.visual_annotations,
            agent_trace=r.agent_trace
        )
        for r in grading_results
    ]
    
    if action == ReviewAction.APPROVE:
        # 批准：使用原始 AI 结果，状态变为 COMPLETED
        return SignalProcessingResult(
            final_status=SubmissionStatus.COMPLETED,
            final_results=final_results,
            is_terminated=False
        )
    
    elif action == ReviewAction.OVERRIDE:
        # 覆盖：应用教师的手动评分，状态变为 COMPLETED
        if override_data:
            for result in final_results:
                if result.question_id in override_data:
                    override_score = override_data[result.question_id].get("score")
                    if override_score is not None:
                        result.score = override_score
        
        return SignalProcessingResult(
            final_status=SubmissionStatus.COMPLETED,
            final_results=final_results,
            is_terminated=False
        )
    
    elif action == ReviewAction.REJECT:
        # 拒绝：状态变为 REJECTED，工作流终止
        return SignalProcessingResult(
            final_status=SubmissionStatus.REJECTED,
            final_results=final_results,
            is_terminated=True,
            error_message="审核拒绝"
        )
    
    else:
        raise ValueError(f"未知的审核操作: {action}")


def calculate_total_score(results: List[GradingResult]) -> float:
    """计算总分"""
    return sum(r.score for r in results)


# ===== 属性测试类 =====

class TestApproveSignalHandling:
    """APPROVE 信号处理测试
    
    **功能: ai-grading-agent, 属性 8: 信号处理状态转换**
    **验证: 需求 5.3**
    
    需求 5.3：当教师发送带有批准操作的审核信号时，工作流应当继续使用 AI 生成的结果
    """
    
    @given(grading_results=low_confidence_results_strategy(min_count=1, max_count=10))
    @settings(max_examples=100)
    def test_approve_signal_uses_original_results(self, grading_results: List[GradingResult]):
        """
        **功能: ai-grading-agent, 属性 8: 信号处理状态转换**
        **验证: 需求 5.3**
        
        对于任意处于 REVIEWING 状态的工作流，APPROVE 信号应使工作流继续使用原始 AI 结果
        """
        # 记录原始分数
        original_scores = {r.question_id: r.score for r in grading_results}
        original_total = calculate_total_score(grading_results)
        
        # 处理 APPROVE 信号
        result = process_review_signal(
            action=ReviewAction.APPROVE,
            grading_results=grading_results
        )
        
        # 验证：状态变为 COMPLETED
        assert result.final_status == SubmissionStatus.COMPLETED, (
            f"APPROVE 信号后状态应为 COMPLETED，但实际为 {result.final_status}"
        )
        
        # 验证：使用原始 AI 结果（分数不变）
        for final_result in result.final_results:
            original_score = original_scores[final_result.question_id]
            assert final_result.score == original_score, (
                f"APPROVE 信号后分数应保持不变，"
                f"题目 {final_result.question_id} 原始分数 {original_score}，"
                f"实际分数 {final_result.score}"
            )
        
        # 验证：总分不变
        final_total = calculate_total_score(result.final_results)
        assert abs(final_total - original_total) < 0.0001, (
            f"APPROVE 信号后总分应保持不变，"
            f"原始总分 {original_total}，实际总分 {final_total}"
        )
        
        # 验证：工作流未终止
        assert result.is_terminated is False, (
            "APPROVE 信号后工作流不应终止"
        )
    
    @given(grading_results=low_confidence_results_strategy(min_count=1, max_count=10))
    @settings(max_examples=100)
    def test_approve_signal_status_is_completed(self, grading_results: List[GradingResult]):
        """
        **功能: ai-grading-agent, 属性 8: 信号处理状态转换**
        **验证: 需求 5.3**
        
        对于任意 APPROVE 信号，最终状态应为 COMPLETED
        """
        result = process_review_signal(
            action=ReviewAction.APPROVE,
            grading_results=grading_results
        )
        
        assert result.final_status == SubmissionStatus.COMPLETED, (
            f"APPROVE 信号后状态应为 COMPLETED，但实际为 {result.final_status}"
        )


class TestOverrideSignalHandling:
    """OVERRIDE 信号处理测试
    
    **功能: ai-grading-agent, 属性 8: 信号处理状态转换**
    **验证: 需求 5.4**
    
    需求 5.4：当教师发送带有覆盖操作的审核信号时，工作流应当应用教师的手动评分
    """
    
    @given(
        grading_results=low_confidence_results_strategy(min_count=1, max_count=5),
        override_score=st.floats(min_value=0.0, max_value=100.0, 
                                  allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_override_signal_applies_manual_score(
        self, grading_results: List[GradingResult], override_score: float
    ):
        """
        **功能: ai-grading-agent, 属性 8: 信号处理状态转换**
        **验证: 需求 5.4**
        
        对于任意 OVERRIDE 信号带分数，最终结果应反映覆盖分数
        """
        # 选择第一个题目进行覆盖
        target_question_id = grading_results[0].question_id
        override_data = {target_question_id: {"score": override_score}}
        
        # 处理 OVERRIDE 信号
        result = process_review_signal(
            action=ReviewAction.OVERRIDE,
            grading_results=grading_results,
            override_data=override_data
        )
        
        # 验证：状态变为 COMPLETED
        assert result.final_status == SubmissionStatus.COMPLETED, (
            f"OVERRIDE 信号后状态应为 COMPLETED，但实际为 {result.final_status}"
        )
        
        # 验证：覆盖分数已应用
        for final_result in result.final_results:
            if final_result.question_id == target_question_id:
                assert final_result.score == override_score, (
                    f"OVERRIDE 信号后题目 {target_question_id} 分数应为 {override_score}，"
                    f"但实际为 {final_result.score}"
                )
        
        # 验证：工作流未终止
        assert result.is_terminated is False, (
            "OVERRIDE 信号后工作流不应终止"
        )
    
    @given(grading_results=low_confidence_results_strategy(min_count=2, max_count=5))
    @settings(max_examples=100)
    def test_override_signal_only_affects_specified_questions(
        self, grading_results: List[GradingResult]
    ):
        """
        **功能: ai-grading-agent, 属性 8: 信号处理状态转换**
        **验证: 需求 5.4**
        
        OVERRIDE 信号只应影响指定的题目，其他题目分数保持不变
        """
        assume(len(grading_results) >= 2)
        
        # 只覆盖第一个题目
        target_question_id = grading_results[0].question_id
        override_score = 99.0
        override_data = {target_question_id: {"score": override_score}}
        
        # 记录其他题目的原始分数
        other_original_scores = {
            r.question_id: r.score 
            for r in grading_results 
            if r.question_id != target_question_id
        }
        
        # 处理 OVERRIDE 信号
        result = process_review_signal(
            action=ReviewAction.OVERRIDE,
            grading_results=grading_results,
            override_data=override_data
        )
        
        # 验证：其他题目分数保持不变
        for final_result in result.final_results:
            if final_result.question_id != target_question_id:
                original_score = other_original_scores[final_result.question_id]
                assert final_result.score == original_score, (
                    f"OVERRIDE 信号不应影响未指定的题目，"
                    f"题目 {final_result.question_id} 原始分数 {original_score}，"
                    f"实际分数 {final_result.score}"
                )
    
    @given(grading_results=low_confidence_results_strategy(min_count=1, max_count=5))
    @settings(max_examples=100)
    def test_override_signal_with_empty_data_keeps_original(
        self, grading_results: List[GradingResult]
    ):
        """
        **功能: ai-grading-agent, 属性 8: 信号处理状态转换**
        **验证: 需求 5.4**
        
        OVERRIDE 信号带空覆盖数据时，应保持原始分数
        """
        # 记录原始分数
        original_scores = {r.question_id: r.score for r in grading_results}
        
        # 处理 OVERRIDE 信号（空覆盖数据）
        result = process_review_signal(
            action=ReviewAction.OVERRIDE,
            grading_results=grading_results,
            override_data={}
        )
        
        # 验证：状态变为 COMPLETED
        assert result.final_status == SubmissionStatus.COMPLETED, (
            f"OVERRIDE 信号后状态应为 COMPLETED，但实际为 {result.final_status}"
        )
        
        # 验证：分数保持不变
        for final_result in result.final_results:
            original_score = original_scores[final_result.question_id]
            assert final_result.score == original_score, (
                f"空覆盖数据时分数应保持不变，"
                f"题目 {final_result.question_id} 原始分数 {original_score}，"
                f"实际分数 {final_result.score}"
            )


class TestRejectSignalHandling:
    """REJECT 信号处理测试
    
    **功能: ai-grading-agent, 属性 8: 信号处理状态转换**
    **验证: 需求 5.5**
    
    需求 5.5：当教师发送带有拒绝操作的审核信号时，工作流应当终止并将提交标记为已拒绝
    """
    
    @given(grading_results=low_confidence_results_strategy(min_count=1, max_count=10))
    @settings(max_examples=100)
    def test_reject_signal_terminates_workflow(self, grading_results: List[GradingResult]):
        """
        **功能: ai-grading-agent, 属性 8: 信号处理状态转换**
        **验证: 需求 5.5**
        
        对于任意 REJECT 信号，工作流应当终止
        """
        result = process_review_signal(
            action=ReviewAction.REJECT,
            grading_results=grading_results
        )
        
        # 验证：工作流终止
        assert result.is_terminated is True, (
            "REJECT 信号后工作流应终止"
        )
    
    @given(grading_results=low_confidence_results_strategy(min_count=1, max_count=10))
    @settings(max_examples=100)
    def test_reject_signal_status_is_rejected(self, grading_results: List[GradingResult]):
        """
        **功能: ai-grading-agent, 属性 8: 信号处理状态转换**
        **验证: 需求 5.5**
        
        对于任意 REJECT 信号，状态应变为 REJECTED
        """
        result = process_review_signal(
            action=ReviewAction.REJECT,
            grading_results=grading_results
        )
        
        # 验证：状态变为 REJECTED
        assert result.final_status == SubmissionStatus.REJECTED, (
            f"REJECT 信号后状态应为 REJECTED，但实际为 {result.final_status}"
        )
    
    @given(grading_results=low_confidence_results_strategy(min_count=1, max_count=10))
    @settings(max_examples=100)
    def test_reject_signal_has_error_message(self, grading_results: List[GradingResult]):
        """
        **功能: ai-grading-agent, 属性 8: 信号处理状态转换**
        **验证: 需求 5.5**
        
        对于任意 REJECT 信号，应包含错误消息
        """
        result = process_review_signal(
            action=ReviewAction.REJECT,
            grading_results=grading_results
        )
        
        # 验证：包含错误消息
        assert result.error_message is not None, (
            "REJECT 信号后应包含错误消息"
        )
        assert len(result.error_message) > 0, (
            "REJECT 信号后错误消息不应为空"
        )


class TestSignalActionCompleteness:
    """信号操作完整性测试
    
    **功能: ai-grading-agent, 属性 8: 信号处理状态转换**
    **验证: 需求 5.3, 5.4, 5.5**
    """
    
    @given(
        action=st.sampled_from(list(ReviewAction)),
        grading_results=low_confidence_results_strategy(min_count=1, max_count=5)
    )
    @settings(max_examples=100)
    def test_all_actions_produce_valid_status(
        self, action: ReviewAction, grading_results: List[GradingResult]
    ):
        """
        **功能: ai-grading-agent, 属性 8: 信号处理状态转换**
        **验证: 需求 5.3, 5.4, 5.5**
        
        对于任意有效的审核操作，应产生有效的最终状态
        """
        override_data = {}
        if action == ReviewAction.OVERRIDE:
            # 为 OVERRIDE 操作提供覆盖数据
            override_data = {grading_results[0].question_id: {"score": 50.0}}
        
        result = process_review_signal(
            action=action,
            grading_results=grading_results,
            override_data=override_data
        )
        
        # 验证：最终状态是有效的
        assert result.final_status in [SubmissionStatus.COMPLETED, SubmissionStatus.REJECTED], (
            f"信号处理后状态应为 COMPLETED 或 REJECTED，但实际为 {result.final_status}"
        )
        
        # 验证：APPROVE 和 OVERRIDE 产生 COMPLETED
        if action in [ReviewAction.APPROVE, ReviewAction.OVERRIDE]:
            assert result.final_status == SubmissionStatus.COMPLETED, (
                f"{action.value} 信号后状态应为 COMPLETED，但实际为 {result.final_status}"
            )
            assert result.is_terminated is False, (
                f"{action.value} 信号后工作流不应终止"
            )
        
        # 验证：REJECT 产生 REJECTED
        if action == ReviewAction.REJECT:
            assert result.final_status == SubmissionStatus.REJECTED, (
                f"REJECT 信号后状态应为 REJECTED，但实际为 {result.final_status}"
            )
            assert result.is_terminated is True, (
                "REJECT 信号后工作流应终止"
            )
    
    def test_all_review_actions_are_handled(self):
        """
        **功能: ai-grading-agent, 属性 8: 信号处理状态转换**
        **验证: 需求 5.3, 5.4, 5.5**
        
        验证所有 ReviewAction 枚举值都被处理
        """
        grading_results = [
            GradingResult(
                question_id="q_1",
                score=5.0,
                max_score=10.0,
                confidence=0.5,
                feedback="测试",
                visual_annotations=[],
                agent_trace={}
            )
        ]
        
        for action in ReviewAction:
            override_data = {}
            if action == ReviewAction.OVERRIDE:
                override_data = {"q_1": {"score": 8.0}}
            
            # 不应抛出异常
            result = process_review_signal(
                action=action,
                grading_results=grading_results,
                override_data=override_data
            )
            
            assert result.final_status is not None, (
                f"操作 {action.value} 应产生有效的最终状态"
            )


class TestStateTransitionConsistency:
    """状态转换一致性测试
    
    **功能: ai-grading-agent, 属性 8: 信号处理状态转换**
    **验证: 需求 5.3, 5.4, 5.5**
    """
    
    @given(grading_results=low_confidence_results_strategy(min_count=1, max_count=5))
    @settings(max_examples=100)
    def test_approve_then_override_consistency(self, grading_results: List[GradingResult]):
        """
        **功能: ai-grading-agent, 属性 8: 信号处理状态转换**
        **验证: 需求 5.3, 5.4**
        
        APPROVE 和 OVERRIDE 都应产生 COMPLETED 状态
        """
        approve_result = process_review_signal(
            action=ReviewAction.APPROVE,
            grading_results=grading_results
        )
        
        override_result = process_review_signal(
            action=ReviewAction.OVERRIDE,
            grading_results=grading_results,
            override_data={}
        )
        
        # 两者都应产生 COMPLETED 状态
        assert approve_result.final_status == SubmissionStatus.COMPLETED
        assert override_result.final_status == SubmissionStatus.COMPLETED
        
        # 两者都不应终止工作流
        assert approve_result.is_terminated is False
        assert override_result.is_terminated is False
    
    @given(
        grading_results=low_confidence_results_strategy(min_count=1, max_count=5),
        override_score=st.floats(min_value=0.0, max_value=100.0,
                                  allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_override_score_reflects_in_total(
        self, grading_results: List[GradingResult], override_score: float
    ):
        """
        **功能: ai-grading-agent, 属性 8: 信号处理状态转换**
        **验证: 需求 5.4**
        
        OVERRIDE 信号的覆盖分数应正确反映在总分中
        """
        # 选择第一个题目进行覆盖
        target_question_id = grading_results[0].question_id
        original_score = grading_results[0].score
        override_data = {target_question_id: {"score": override_score}}
        
        # 计算原始总分
        original_total = calculate_total_score(grading_results)
        
        # 处理 OVERRIDE 信号
        result = process_review_signal(
            action=ReviewAction.OVERRIDE,
            grading_results=grading_results,
            override_data=override_data
        )
        
        # 计算最终总分
        final_total = calculate_total_score(result.final_results)
        
        # 验证：总分变化等于覆盖分数与原始分数的差值
        expected_total = original_total - original_score + override_score
        assert abs(final_total - expected_total) < 0.0001, (
            f"覆盖后总分应为 {expected_total}，但实际为 {final_total}"
        )


class TestInvalidActionHandling:
    """无效操作处理测试
    
    **功能: ai-grading-agent, 属性 8: 信号处理状态转换**
    **验证: 需求 5.3, 5.4, 5.5**
    """
    
    def test_invalid_action_raises_error(self):
        """
        **功能: ai-grading-agent, 属性 8: 信号处理状态转换**
        **验证: 需求 5.3, 5.4, 5.5**
        
        无效的审核操作应抛出错误
        """
        grading_results = [
            GradingResult(
                question_id="q_1",
                score=5.0,
                max_score=10.0,
                confidence=0.5,
                feedback="测试",
                visual_annotations=[],
                agent_trace={}
            )
        ]
        
        # 尝试使用无效的操作（通过直接传递字符串模拟）
        with pytest.raises(ValueError):
            # 这里我们无法直接传递无效的 ReviewAction，
            # 因为枚举会在创建时验证
            # 但我们可以测试处理函数对未知值的处理
            class FakeAction:
                value = "INVALID"
            
            process_review_signal(
                action=FakeAction(),  # type: ignore
                grading_results=grading_results
            )
