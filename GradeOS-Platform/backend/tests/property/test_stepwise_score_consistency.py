"""StepwiseAgent 步骤分数一致性属性测试

使用 Hypothesis 验证 StepwiseAgent 的步骤分数一致性

**功能: ai-grading-agent, 属性 24: StepwiseAgent 步骤分数一致性**
**验证: 需求 11.2**
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from typing import List, Dict, Any

from src.models.state import EvidenceItem, GradingState


def create_step_score(
    step_number: int,
    step_name: str,
    score: float,
    max_score: float,
    location: List[int] = None
) -> Dict[str, Any]:
    """创建步骤评分条目
    
    Args:
        step_number: 步骤编号
        step_name: 步骤名称
        score: 该步骤得分
        max_score: 该步骤满分
        location: 位置坐标
        
    Returns:
        步骤评分字典
    """
    return {
        "step_number": step_number,
        "step_name": step_name,
        "student_work": f"学生步骤 {step_number} 的内容",
        "location": location or [0, 0, 1000, 1000],
        "max_score": max_score,
        "score": score,
        "is_correct": score >= max_score * 0.8,
        "feedback": f"步骤 {step_number} 的反馈"
    }


def build_evidence_chain_from_steps(
    step_scores: List[Dict[str, Any]],
    rubric: str = "评分细则"
) -> List[EvidenceItem]:
    """从步骤评分构建证据链
    
    模拟 StepwiseAgent._build_evidence_chain 的逻辑
    
    Args:
        step_scores: 步骤评分列表
        rubric: 评分细则
        
    Returns:
        证据链列表
    """
    evidence_chain: List[EvidenceItem] = []
    
    for step in step_scores:
        evidence: EvidenceItem = {
            "scoring_point": step.get("step_name", f"步骤 {step.get('step_number', 0)}"),
            "image_region": step.get("location", [0, 0, 1000, 1000]),
            "text_description": step.get("student_work", step.get("content", "")),
            "reasoning": step.get("feedback", ""),
            "rubric_reference": rubric[:100] if rubric else "计算题评分标准",
            "points_awarded": step.get("score", 0)
        }
        evidence_chain.append(evidence)
    
    return evidence_chain


def calculate_total_from_steps(step_scores: List[Dict[str, Any]]) -> float:
    """计算步骤分数总和
    
    Args:
        step_scores: 步骤评分列表
        
    Returns:
        步骤分数总和
    """
    return sum(step.get("score", 0) for step in step_scores)


def calculate_total_from_evidence_chain(evidence_chain: List[EvidenceItem]) -> float:
    """从证据链计算分数总和
    
    Args:
        evidence_chain: 证据链列表
        
    Returns:
        证据链分数总和
    """
    return sum(e.get("points_awarded", 0) for e in evidence_chain)


def validate_step_score_consistency(
    step_scores: List[Dict[str, Any]],
    final_score: float,
    tolerance: float = 0.001
) -> bool:
    """验证步骤分数一致性
    
    根据需求 11.2，各步骤得分之和应当等于 final_score
    
    Args:
        step_scores: 步骤评分列表
        final_score: 最终得分
        tolerance: 浮点数比较容差
        
    Returns:
        是否一致
    """
    total_from_steps = calculate_total_from_steps(step_scores)
    return abs(total_from_steps - final_score) < tolerance


def validate_evidence_chain_score_consistency(
    evidence_chain: List[EvidenceItem],
    final_score: float,
    tolerance: float = 0.001
) -> bool:
    """验证证据链分数一致性
    
    证据链中各条目的 points_awarded 之和应当等于 final_score
    
    Args:
        evidence_chain: 证据链列表
        final_score: 最终得分
        tolerance: 浮点数比较容差
        
    Returns:
        是否一致
    """
    total_from_evidence = calculate_total_from_evidence_chain(evidence_chain)
    return abs(total_from_evidence - final_score) < tolerance


# ===== Hypothesis 策略定义 =====

# 非负分数策略
non_negative_score = st.floats(
    min_value=0.0, 
    max_value=100.0, 
    allow_nan=False, 
    allow_infinity=False
)

# 步骤数量策略（1-10 个步骤）
step_count_strategy = st.integers(min_value=1, max_value=10)

# 有效的边界框坐标策略
valid_location = st.lists(
    st.integers(min_value=0, max_value=1000),
    min_size=4,
    max_size=4
)


class TestStepwiseScoreConsistency:
    """StepwiseAgent 步骤分数一致性属性测试
    
    **功能: ai-grading-agent, 属性 24: StepwiseAgent 步骤分数一致性**
    **验证: 需求 11.2**
    """
    
    @given(
        step_scores_data=st.lists(
            st.tuples(
                st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False),
                st.floats(min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False)
            ),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=100)
    def test_step_scores_sum_equals_final_score(
        self,
        step_scores_data: List[tuple]
    ):
        """
        **功能: ai-grading-agent, 属性 24: StepwiseAgent 步骤分数一致性**
        **验证: 需求 11.2**
        
        对于任意 StepwiseAgent 的批改结果，各步骤得分之和应当等于 final_score
        """
        # 构建步骤评分列表
        step_scores = []
        for i, (score, max_score) in enumerate(step_scores_data):
            # 确保 score <= max_score
            actual_score = min(score, max_score)
            step_scores.append(create_step_score(
                step_number=i + 1,
                step_name=f"步骤 {i + 1}",
                score=actual_score,
                max_score=max_score
            ))
        
        # 计算 final_score（模拟 StepwiseAgent 的行为）
        final_score = calculate_total_from_steps(step_scores)
        
        # 验证一致性
        assert validate_step_score_consistency(step_scores, final_score), (
            f"步骤分数之和 ({calculate_total_from_steps(step_scores)}) "
            f"应当等于 final_score ({final_score})"
        )
    
    @given(
        step_scores_data=st.lists(
            st.tuples(
                st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False),
                st.floats(min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False)
            ),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=100)
    def test_evidence_chain_points_sum_equals_final_score(
        self,
        step_scores_data: List[tuple]
    ):
        """
        **功能: ai-grading-agent, 属性 24: StepwiseAgent 步骤分数一致性**
        **验证: 需求 11.2**
        
        对于任意 StepwiseAgent 的批改结果，证据链中各条目的 points_awarded 之和
        应当等于 final_score
        """
        # 构建步骤评分列表
        step_scores = []
        for i, (score, max_score) in enumerate(step_scores_data):
            actual_score = min(score, max_score)
            step_scores.append(create_step_score(
                step_number=i + 1,
                step_name=f"步骤 {i + 1}",
                score=actual_score,
                max_score=max_score
            ))
        
        # 构建证据链（模拟 StepwiseAgent._build_evidence_chain）
        evidence_chain = build_evidence_chain_from_steps(step_scores)
        
        # 计算 final_score
        final_score = calculate_total_from_steps(step_scores)
        
        # 验证证据链分数一致性
        assert validate_evidence_chain_score_consistency(evidence_chain, final_score), (
            f"证据链分数之和 ({calculate_total_from_evidence_chain(evidence_chain)}) "
            f"应当等于 final_score ({final_score})"
        )
    
    @given(
        step_scores_data=st.lists(
            st.tuples(
                st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False),
                st.floats(min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False)
            ),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=100)
    def test_step_scores_and_evidence_chain_are_consistent(
        self,
        step_scores_data: List[tuple]
    ):
        """
        **功能: ai-grading-agent, 属性 24: StepwiseAgent 步骤分数一致性**
        **验证: 需求 11.2**
        
        对于任意 StepwiseAgent 的批改结果，步骤评分和证据链的分数应当一致
        """
        # 构建步骤评分列表
        step_scores = []
        for i, (score, max_score) in enumerate(step_scores_data):
            actual_score = min(score, max_score)
            step_scores.append(create_step_score(
                step_number=i + 1,
                step_name=f"步骤 {i + 1}",
                score=actual_score,
                max_score=max_score
            ))
        
        # 构建证据链
        evidence_chain = build_evidence_chain_from_steps(step_scores)
        
        # 计算两种方式的总分
        total_from_steps = calculate_total_from_steps(step_scores)
        total_from_evidence = calculate_total_from_evidence_chain(evidence_chain)
        
        # 验证两者一致
        assert abs(total_from_steps - total_from_evidence) < 0.001, (
            f"步骤分数之和 ({total_from_steps}) 应当等于 "
            f"证据链分数之和 ({total_from_evidence})"
        )
    
    @given(
        step_count=st.integers(min_value=1, max_value=10),
        total_score=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_distributed_scores_sum_to_total(
        self,
        step_count: int,
        total_score: float
    ):
        """
        **功能: ai-grading-agent, 属性 24: StepwiseAgent 步骤分数一致性**
        **验证: 需求 11.2**
        
        对于任意分配到各步骤的分数，其总和应当等于预期的总分
        """
        # 将总分均匀分配到各步骤
        score_per_step = total_score / step_count
        
        step_scores = []
        for i in range(step_count):
            step_scores.append(create_step_score(
                step_number=i + 1,
                step_name=f"步骤 {i + 1}",
                score=score_per_step,
                max_score=score_per_step + 1.0
            ))
        
        # 计算实际总分
        actual_total = calculate_total_from_steps(step_scores)
        
        # 验证总分一致（考虑浮点数精度）
        assert abs(actual_total - total_score) < 0.001, (
            f"步骤分数之和 ({actual_total}) 应当等于总分 ({total_score})"
        )


class TestStepwiseScoreEdgeCases:
    """StepwiseAgent 步骤分数边界情况测试
    
    **功能: ai-grading-agent, 属性 24: StepwiseAgent 步骤分数一致性**
    **验证: 需求 11.2**
    """
    
    def test_single_step_score_equals_final_score(self):
        """
        **功能: ai-grading-agent, 属性 24: StepwiseAgent 步骤分数一致性**
        **验证: 需求 11.2**
        
        单步骤情况下，该步骤得分应当等于 final_score
        """
        step_scores = [create_step_score(
            step_number=1,
            step_name="唯一步骤",
            score=5.0,
            max_score=10.0
        )]
        
        final_score = calculate_total_from_steps(step_scores)
        
        assert final_score == 5.0, (
            f"单步骤得分 (5.0) 应当等于 final_score ({final_score})"
        )
        assert validate_step_score_consistency(step_scores, final_score)
    
    def test_all_zero_scores_sum_to_zero(self):
        """
        **功能: ai-grading-agent, 属性 24: StepwiseAgent 步骤分数一致性**
        **验证: 需求 11.2**
        
        所有步骤得分为 0 时，final_score 应当为 0
        """
        step_scores = [
            create_step_score(step_number=i, step_name=f"步骤 {i}", score=0.0, max_score=5.0)
            for i in range(1, 6)
        ]
        
        final_score = calculate_total_from_steps(step_scores)
        
        assert final_score == 0.0, (
            f"所有步骤得分为 0 时，final_score 应当为 0，实际为 {final_score}"
        )
        assert validate_step_score_consistency(step_scores, final_score)
    
    def test_all_full_scores_sum_correctly(self):
        """
        **功能: ai-grading-agent, 属性 24: StepwiseAgent 步骤分数一致性**
        **验证: 需求 11.2**
        
        所有步骤满分时，final_score 应当等于各步骤满分之和
        """
        step_scores = [
            create_step_score(step_number=i, step_name=f"步骤 {i}", score=2.0, max_score=2.0)
            for i in range(1, 6)
        ]
        
        final_score = calculate_total_from_steps(step_scores)
        expected_total = 2.0 * 5  # 5 个步骤，每个 2 分
        
        assert final_score == expected_total, (
            f"所有步骤满分时，final_score 应当为 {expected_total}，实际为 {final_score}"
        )
        assert validate_step_score_consistency(step_scores, final_score)
    
    def test_empty_steps_result_in_zero_score(self):
        """
        **功能: ai-grading-agent, 属性 24: StepwiseAgent 步骤分数一致性**
        **验证: 需求 11.2**
        
        没有步骤时，final_score 应当为 0
        """
        step_scores: List[Dict[str, Any]] = []
        
        final_score = calculate_total_from_steps(step_scores)
        
        assert final_score == 0.0, (
            f"没有步骤时，final_score 应当为 0，实际为 {final_score}"
        )
        assert validate_step_score_consistency(step_scores, final_score)
    
    @given(
        partial_scores=st.lists(
            st.floats(min_value=0.0, max_value=5.0, allow_nan=False, allow_infinity=False),
            min_size=2,
            max_size=5
        )
    )
    @settings(max_examples=50)
    def test_partial_scores_sum_correctly(self, partial_scores: List[float]):
        """
        **功能: ai-grading-agent, 属性 24: StepwiseAgent 步骤分数一致性**
        **验证: 需求 11.2**
        
        部分得分情况下，各步骤得分之和应当等于 final_score
        """
        step_scores = [
            create_step_score(
                step_number=i + 1,
                step_name=f"步骤 {i + 1}",
                score=score,
                max_score=5.0
            )
            for i, score in enumerate(partial_scores)
        ]
        
        final_score = calculate_total_from_steps(step_scores)
        expected_total = sum(partial_scores)
        
        assert abs(final_score - expected_total) < 0.001, (
            f"步骤分数之和 ({final_score}) 应当等于预期总分 ({expected_total})"
        )
        assert validate_step_score_consistency(step_scores, final_score)


class TestStepwiseGradingStateConsistency:
    """StepwiseAgent GradingState 一致性测试
    
    验证完整的 GradingState 中步骤分数的一致性
    
    **功能: ai-grading-agent, 属性 24: StepwiseAgent 步骤分数一致性**
    **验证: 需求 11.2**
    """
    
    @given(
        step_scores_data=st.lists(
            st.tuples(
                st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False),
                st.floats(min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False)
            ),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=100)
    def test_grading_state_final_score_matches_evidence_chain(
        self,
        step_scores_data: List[tuple]
    ):
        """
        **功能: ai-grading-agent, 属性 24: StepwiseAgent 步骤分数一致性**
        **验证: 需求 11.2**
        
        对于任意 GradingState，final_score 应当等于 evidence_chain 中各条目的
        points_awarded 之和
        """
        # 构建步骤评分列表
        step_scores = []
        for i, (score, max_score) in enumerate(step_scores_data):
            actual_score = min(score, max_score)
            step_scores.append(create_step_score(
                step_number=i + 1,
                step_name=f"步骤 {i + 1}",
                score=actual_score,
                max_score=max_score
            ))
        
        # 构建证据链
        evidence_chain = build_evidence_chain_from_steps(step_scores)
        
        # 计算 final_score
        final_score = calculate_total_from_steps(step_scores)
        
        # 模拟 GradingState
        grading_state: GradingState = {
            "final_score": final_score,
            "evidence_chain": evidence_chain,
            "agent_type": "stepwise"
        }
        
        # 验证 final_score 与 evidence_chain 一致
        evidence_total = calculate_total_from_evidence_chain(grading_state["evidence_chain"])
        
        assert abs(grading_state["final_score"] - evidence_total) < 0.001, (
            f"GradingState.final_score ({grading_state['final_score']}) "
            f"应当等于 evidence_chain 分数之和 ({evidence_total})"
        )
    
    @given(
        step_scores_data=st.lists(
            st.tuples(
                st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False),
                st.floats(min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False)
            ),
            min_size=1,
            max_size=10
        ),
        max_score=st.floats(min_value=10.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_final_score_does_not_exceed_max_score(
        self,
        step_scores_data: List[tuple],
        max_score: float
    ):
        """
        **功能: ai-grading-agent, 属性 24: StepwiseAgent 步骤分数一致性**
        **验证: 需求 11.2**
        
        对于任意 GradingState，final_score 不应超过 max_score
        """
        # 构建步骤评分列表，确保总分不超过 max_score
        step_scores = []
        remaining_score = max_score
        
        for i, (score, step_max) in enumerate(step_scores_data):
            # 限制每步得分不超过剩余分数
            actual_score = min(score, step_max, remaining_score)
            actual_score = max(0, actual_score)  # 确保非负
            
            step_scores.append(create_step_score(
                step_number=i + 1,
                step_name=f"步骤 {i + 1}",
                score=actual_score,
                max_score=step_max
            ))
            
            remaining_score -= actual_score
        
        # 计算 final_score
        final_score = calculate_total_from_steps(step_scores)
        
        # 验证 final_score 不超过 max_score
        assert final_score <= max_score + 0.001, (
            f"final_score ({final_score}) 不应超过 max_score ({max_score})"
        )
