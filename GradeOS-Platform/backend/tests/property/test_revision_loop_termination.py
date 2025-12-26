"""修正循环终止属性测试

使用 Hypothesis 验证批改智能体的修正循环终止逻辑

**功能: ai-grading-agent, 属性 3: 智能体修正循环终止**
**验证: 需求 3.5**
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from typing import Optional

from src.models.state import GradingState
from src.agents.grading_agent import GradingAgent


# 生成有效的 critique_feedback 策略
# 非空字符串表示有反馈，None 表示无反馈
critique_feedback_strategy = st.one_of(
    st.none(),
    st.text(min_size=1, max_size=200)
)

# 生成 revision_count 策略（0-10 范围，覆盖边界情况）
revision_count_strategy = st.integers(min_value=0, max_value=10)


def create_test_state(
    critique_feedback: Optional[str],
    revision_count: int,
    has_error: bool = False
) -> GradingState:
    """创建测试用的 GradingState
    
    Args:
        critique_feedback: 反思反馈（None 表示无反馈）
        revision_count: 修正次数
        has_error: 是否有错误
        
    Returns:
        GradingState: 测试状态
    """
    state = GradingState(
        question_image="dGVzdF9pbWFnZQ==",
        rubric="评分细则",
        max_score=10.0,
        vision_analysis="视觉分析结果",
        rubric_mapping=[{"rubric_point": "评分点", "evidence": "证据", "score_awarded": 8.0}],
        initial_score=8.0,
        reasoning_trace=["步骤1", "步骤2"],
        critique_feedback=critique_feedback,
        evidence_chain=[],
        final_score=8.0,
        confidence=0.85,
        visual_annotations=[],
        student_feedback="反馈",
        agent_type="objective",
        revision_count=revision_count,
        is_finalized=False,
        needs_secondary_review=False
    )
    
    if has_error:
        state["error"] = "测试错误"
    
    return state


class TestRevisionLoopTermination:
    """修正循环终止属性测试
    
    **功能: ai-grading-agent, 属性 3: 智能体修正循环终止**
    **验证: 需求 3.5**
    """
    
    def setup_method(self):
        """每个测试前创建 GradingAgent 实例"""
        # 创建一个不带 reasoning_client 的 agent 用于测试 _should_revise 方法
        # 我们只测试条件函数，不需要实际的 LLM 调用
        pass
    
    @given(
        critique_feedback=st.text(min_size=1, max_size=200),
        revision_count=st.integers(min_value=0, max_value=2)
    )
    @settings(max_examples=100)
    def test_revise_when_feedback_and_count_below_threshold(
        self,
        critique_feedback: str,
        revision_count: int
    ):
        """
        **功能: ai-grading-agent, 属性 3: 智能体修正循环终止**
        **验证: 需求 3.5**
        
        对于任意非空 critique_feedback 且 revision_count < 3 的状态，
        _should_revise 应当返回 "revise"
        """
        # 确保 revision_count < 3
        assume(revision_count < 3)
        
        state = create_test_state(
            critique_feedback=critique_feedback,
            revision_count=revision_count
        )
        
        # 创建 agent 并测试条件函数
        agent = GradingAgent.__new__(GradingAgent)
        result = agent._should_revise(state)
        
        assert result == "revise", (
            f"当 critique_feedback 非空且 revision_count ({revision_count}) < 3 时，"
            f"应当返回 'revise'，但返回了 '{result}'"
        )
    
    @given(
        critique_feedback=st.text(min_size=1, max_size=200),
        revision_count=st.integers(min_value=3, max_value=10)
    )
    @settings(max_examples=100)
    def test_finalize_when_count_at_or_above_threshold(
        self,
        critique_feedback: str,
        revision_count: int
    ):
        """
        **功能: ai-grading-agent, 属性 3: 智能体修正循环终止**
        **验证: 需求 3.5**
        
        对于任意 revision_count >= 3 的状态，无论 critique_feedback 如何，
        _should_revise 应当返回 "finalize"
        """
        # 确保 revision_count >= 3
        assume(revision_count >= 3)
        
        state = create_test_state(
            critique_feedback=critique_feedback,
            revision_count=revision_count
        )
        
        agent = GradingAgent.__new__(GradingAgent)
        result = agent._should_revise(state)
        
        assert result == "finalize", (
            f"当 revision_count ({revision_count}) >= 3 时，"
            f"应当返回 'finalize'，但返回了 '{result}'"
        )
    
    @given(
        revision_count=st.integers(min_value=0, max_value=10)
    )
    @settings(max_examples=100)
    def test_finalize_when_no_feedback(self, revision_count: int):
        """
        **功能: ai-grading-agent, 属性 3: 智能体修正循环终止**
        **验证: 需求 3.5**
        
        对于任意 critique_feedback 为 None 的状态，无论 revision_count 如何，
        _should_revise 应当返回 "finalize"
        """
        state = create_test_state(
            critique_feedback=None,
            revision_count=revision_count
        )
        
        agent = GradingAgent.__new__(GradingAgent)
        result = agent._should_revise(state)
        
        assert result == "finalize", (
            f"当 critique_feedback 为 None 时，"
            f"应当返回 'finalize'，但返回了 '{result}'"
        )
    
    @given(
        revision_count=st.integers(min_value=0, max_value=10)
    )
    @settings(max_examples=100)
    def test_finalize_when_empty_feedback(self, revision_count: int):
        """
        **功能: ai-grading-agent, 属性 3: 智能体修正循环终止**
        **验证: 需求 3.5**
        
        对于任意 critique_feedback 为空字符串的状态，无论 revision_count 如何，
        _should_revise 应当返回 "finalize"
        """
        state = create_test_state(
            critique_feedback="",
            revision_count=revision_count
        )
        
        agent = GradingAgent.__new__(GradingAgent)
        result = agent._should_revise(state)
        
        assert result == "finalize", (
            f"当 critique_feedback 为空字符串时，"
            f"应当返回 'finalize'，但返回了 '{result}'"
        )
    
    @given(
        critique_feedback=critique_feedback_strategy,
        revision_count=revision_count_strategy
    )
    @settings(max_examples=100)
    def test_finalize_when_error_present(
        self,
        critique_feedback: Optional[str],
        revision_count: int
    ):
        """
        **功能: ai-grading-agent, 属性 3: 智能体修正循环终止**
        **验证: 需求 3.5**
        
        对于任意存在 error 的状态，无论其他条件如何，
        _should_revise 应当返回 "finalize"
        """
        state = create_test_state(
            critique_feedback=critique_feedback,
            revision_count=revision_count,
            has_error=True
        )
        
        agent = GradingAgent.__new__(GradingAgent)
        result = agent._should_revise(state)
        
        assert result == "finalize", (
            f"当存在 error 时，应当返回 'finalize'，但返回了 '{result}'"
        )


class TestRevisionLoopBoundaryConditions:
    """修正循环边界条件测试
    
    **功能: ai-grading-agent, 属性 3: 智能体修正循环终止**
    **验证: 需求 3.5**
    """
    
    @given(
        critique_feedback=st.text(min_size=1, max_size=200)
    )
    @settings(max_examples=100)
    def test_boundary_revision_count_2(self, critique_feedback: str):
        """
        **功能: ai-grading-agent, 属性 3: 智能体修正循环终止**
        **验证: 需求 3.5**
        
        当 revision_count = 2 且有反馈时，应当返回 "revise"（边界条件）
        """
        state = create_test_state(
            critique_feedback=critique_feedback,
            revision_count=2
        )
        
        agent = GradingAgent.__new__(GradingAgent)
        result = agent._should_revise(state)
        
        assert result == "revise", (
            f"当 revision_count = 2 且有反馈时，应当返回 'revise'，但返回了 '{result}'"
        )
    
    @given(
        critique_feedback=st.text(min_size=1, max_size=200)
    )
    @settings(max_examples=100)
    def test_boundary_revision_count_3(self, critique_feedback: str):
        """
        **功能: ai-grading-agent, 属性 3: 智能体修正循环终止**
        **验证: 需求 3.5**
        
        当 revision_count = 3 时，无论是否有反馈，应当返回 "finalize"（边界条件）
        """
        state = create_test_state(
            critique_feedback=critique_feedback,
            revision_count=3
        )
        
        agent = GradingAgent.__new__(GradingAgent)
        result = agent._should_revise(state)
        
        assert result == "finalize", (
            f"当 revision_count = 3 时，应当返回 'finalize'，但返回了 '{result}'"
        )
    
    @given(
        critique_feedback=st.text(min_size=1, max_size=200)
    )
    @settings(max_examples=100)
    def test_boundary_revision_count_0(self, critique_feedback: str):
        """
        **功能: ai-grading-agent, 属性 3: 智能体修正循环终止**
        **验证: 需求 3.5**
        
        当 revision_count = 0 且有反馈时，应当返回 "revise"（初始状态）
        """
        state = create_test_state(
            critique_feedback=critique_feedback,
            revision_count=0
        )
        
        agent = GradingAgent.__new__(GradingAgent)
        result = agent._should_revise(state)
        
        assert result == "revise", (
            f"当 revision_count = 0 且有反馈时，应当返回 'revise'，但返回了 '{result}'"
        )


class TestRevisionLoopInvariants:
    """修正循环不变量测试
    
    **功能: ai-grading-agent, 属性 3: 智能体修正循环终止**
    **验证: 需求 3.5**
    """
    
    @given(
        critique_feedback=critique_feedback_strategy,
        revision_count=revision_count_strategy
    )
    @settings(max_examples=100)
    def test_should_revise_returns_valid_value(
        self,
        critique_feedback: Optional[str],
        revision_count: int
    ):
        """
        **功能: ai-grading-agent, 属性 3: 智能体修正循环终止**
        **验证: 需求 3.5**
        
        _should_revise 应当始终返回 "revise" 或 "finalize"
        """
        state = create_test_state(
            critique_feedback=critique_feedback,
            revision_count=revision_count
        )
        
        agent = GradingAgent.__new__(GradingAgent)
        result = agent._should_revise(state)
        
        assert result in ["revise", "finalize"], (
            f"_should_revise 应当返回 'revise' 或 'finalize'，但返回了 '{result}'"
        )
    
    @given(
        critique_feedback=critique_feedback_strategy,
        revision_count=revision_count_strategy
    )
    @settings(max_examples=100)
    def test_revision_loop_eventually_terminates(
        self,
        critique_feedback: Optional[str],
        revision_count: int
    ):
        """
        **功能: ai-grading-agent, 属性 3: 智能体修正循环终止**
        **验证: 需求 3.5**
        
        修正循环最终会终止（revision_count >= 3 时必定终止）
        """
        # 模拟循环执行
        current_count = revision_count
        max_iterations = 10  # 防止无限循环
        iterations = 0
        
        agent = GradingAgent.__new__(GradingAgent)
        
        while iterations < max_iterations:
            state = create_test_state(
                critique_feedback=critique_feedback,
                revision_count=current_count
            )
            
            result = agent._should_revise(state)
            
            if result == "finalize":
                break
            
            # 模拟修正：增加 revision_count
            current_count += 1
            iterations += 1
        
        # 验证循环最终终止
        assert iterations < max_iterations, (
            f"修正循环未能在 {max_iterations} 次迭代内终止"
        )
        
        # 验证终止时 revision_count >= 3 或无反馈
        if critique_feedback:
            assert current_count >= 3, (
                f"有反馈时，循环应在 revision_count >= 3 时终止，"
                f"但在 revision_count = {current_count} 时终止"
            )
    
    @given(
        critique_feedback=st.text(min_size=1, max_size=200)
    )
    @settings(max_examples=100)
    def test_max_three_revisions_with_feedback(self, critique_feedback: str):
        """
        **功能: ai-grading-agent, 属性 3: 智能体修正循环终止**
        **验证: 需求 3.5**
        
        当有反馈时，最多进行 3 次修正
        """
        agent = GradingAgent.__new__(GradingAgent)
        revision_count = 0
        revisions_made = 0
        
        while revision_count < 10:  # 安全上限
            state = create_test_state(
                critique_feedback=critique_feedback,
                revision_count=revision_count
            )
            
            result = agent._should_revise(state)
            
            if result == "finalize":
                break
            
            revisions_made += 1
            revision_count += 1
        
        # 验证最多进行 3 次修正
        assert revisions_made <= 3, (
            f"最多应进行 3 次修正，但进行了 {revisions_made} 次"
        )
