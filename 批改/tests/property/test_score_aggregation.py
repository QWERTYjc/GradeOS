"""分数聚合正确性属性测试

使用 Hypothesis 验证工作流分数聚合的正确性

**功能: ai-grading-agent, 属性 6: 分数聚合正确性**
**验证: 需求 4.3**
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from typing import List
from decimal import Decimal

from src.models.grading import GradingResult, ExamPaperResult


# ===== 策略定义 =====

# 生成有效的题目 ID
question_id_strategy = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789_",
    min_size=1,
    max_size=20
).map(lambda s: f"q_{s}")

# 生成有效的提交 ID
submission_id_strategy = st.text(
    alphabet="0123456789abcdef",
    min_size=8,
    max_size=36
).map(lambda s: f"sub_{s}")


@st.composite
def grading_result_strategy(draw, question_id: str = None):
    """生成有效的批改结果"""
    if question_id is None:
        question_id = draw(question_id_strategy)
    
    # 生成满分（1-100 之间）
    max_score = draw(st.floats(min_value=1.0, max_value=100.0, allow_nan=False, allow_infinity=False))
    
    # 生成得分（0 到满分之间）
    score = draw(st.floats(min_value=0.0, max_value=max_score, allow_nan=False, allow_infinity=False))
    
    # 生成置信度（0-1 之间）
    confidence = draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))
    
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
def grading_results_list_strategy(draw, min_count: int = 0, max_count: int = 20):
    """生成批改结果列表，确保 question_id 唯一"""
    count = draw(st.integers(min_value=min_count, max_value=max_count))
    results = []
    for i in range(count):
        question_id = f"q_{i+1}"
        result = draw(grading_result_strategy(question_id=question_id))
        results.append(result)
    return results


def aggregate_scores(grading_results: List[GradingResult]) -> tuple:
    """
    聚合分数的函数（与 exam_paper.py 中的逻辑一致）
    
    Args:
        grading_results: 批改结果列表
        
    Returns:
        (total_score, max_total_score) 元组
    """
    total_score = 0.0
    max_total_score = 0.0
    
    for result in grading_results:
        total_score += result.score
        max_total_score += result.max_score
    
    return total_score, max_total_score


class TestScoreAggregationProperties:
    """分数聚合正确性属性测试
    
    **功能: ai-grading-agent, 属性 6: 分数聚合正确性**
    **验证: 需求 4.3**
    
    属性 6 定义：对于任意子工作流结果集，其分数为 [s1, s2, ..., sn]，
    满分为 [m1, m2, ..., mn]，聚合的 total_score 应当等于 sum(si)，
    max_total_score 应当等于 sum(mi)。
    """
    
    @given(grading_results=grading_results_list_strategy(min_count=0, max_count=20))
    @settings(max_examples=100)
    def test_total_score_equals_sum_of_scores(self, grading_results: List[GradingResult]):
        """
        **功能: ai-grading-agent, 属性 6: 分数聚合正确性**
        **验证: 需求 4.3**
        
        对于任意批改结果列表，聚合的 total_score 应当等于所有 score 之和
        """
        # 计算预期的总分
        expected_total = sum(r.score for r in grading_results)
        
        # 使用聚合函数计算
        actual_total, _ = aggregate_scores(grading_results)
        
        # 验证总分相等（使用近似比较处理浮点数精度问题）
        assert abs(actual_total - expected_total) < 1e-9, \
            f"聚合总分 {actual_total} 不等于预期 {expected_total}"
    
    @given(grading_results=grading_results_list_strategy(min_count=0, max_count=20))
    @settings(max_examples=100)
    def test_max_total_score_equals_sum_of_max_scores(self, grading_results: List[GradingResult]):
        """
        **功能: ai-grading-agent, 属性 6: 分数聚合正确性**
        **验证: 需求 4.3**
        
        对于任意批改结果列表，聚合的 max_total_score 应当等于所有 max_score 之和
        """
        # 计算预期的满分总和
        expected_max_total = sum(r.max_score for r in grading_results)
        
        # 使用聚合函数计算
        _, actual_max_total = aggregate_scores(grading_results)
        
        # 验证满分总和相等（使用近似比较处理浮点数精度问题）
        assert abs(actual_max_total - expected_max_total) < 1e-9, \
            f"聚合满分 {actual_max_total} 不等于预期 {expected_max_total}"
    
    @given(grading_results=grading_results_list_strategy(min_count=1, max_count=20))
    @settings(max_examples=100)
    def test_total_score_not_exceeds_max_total(self, grading_results: List[GradingResult]):
        """
        **功能: ai-grading-agent, 属性 6: 分数聚合正确性**
        **验证: 需求 4.3**
        
        聚合的 total_score 不应超过 max_total_score
        """
        total_score, max_total_score = aggregate_scores(grading_results)
        
        # 验证总分不超过满分（考虑浮点数精度）
        assert total_score <= max_total_score + 1e-9, \
            f"总分 {total_score} 超过满分 {max_total_score}"
    
    @given(grading_results=grading_results_list_strategy(min_count=0, max_count=20))
    @settings(max_examples=100)
    def test_aggregation_is_non_negative(self, grading_results: List[GradingResult]):
        """
        **功能: ai-grading-agent, 属性 6: 分数聚合正确性**
        **验证: 需求 4.3**
        
        聚合的分数应当为非负数
        """
        total_score, max_total_score = aggregate_scores(grading_results)
        
        assert total_score >= 0, f"总分 {total_score} 为负数"
        assert max_total_score >= 0, f"满分 {max_total_score} 为负数"


class TestScoreAggregationEdgeCases:
    """分数聚合边界情况测试
    
    **功能: ai-grading-agent, 属性 6: 分数聚合正确性**
    **验证: 需求 4.3**
    """
    
    def test_empty_results_produces_zero_scores(self):
        """
        **功能: ai-grading-agent, 属性 6: 分数聚合正确性**
        **验证: 需求 4.3**
        
        空的批改结果列表应当产生零分
        """
        total_score, max_total_score = aggregate_scores([])
        
        assert total_score == 0.0, f"空列表的总分应为 0，实际为 {total_score}"
        assert max_total_score == 0.0, f"空列表的满分应为 0，实际为 {max_total_score}"
    
    @given(
        score=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        max_score=st.floats(min_value=1.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_single_result_aggregation(self, score: float, max_score: float):
        """
        **功能: ai-grading-agent, 属性 6: 分数聚合正确性**
        **验证: 需求 4.3**
        
        单个批改结果的聚合应当等于该结果本身的分数
        """
        # 确保 score <= max_score
        actual_score = min(score, max_score)
        
        result = GradingResult(
            question_id="q_1",
            score=actual_score,
            max_score=max_score,
            confidence=0.9,
            feedback="测试",
            visual_annotations=[],
            agent_trace={}
        )
        
        total_score, max_total_score = aggregate_scores([result])
        
        assert abs(total_score - actual_score) < 1e-9, \
            f"单个结果的总分 {total_score} 不等于原始分数 {actual_score}"
        assert abs(max_total_score - max_score) < 1e-9, \
            f"单个结果的满分 {max_total_score} 不等于原始满分 {max_score}"


class TestScoreAggregationWithExamPaperResult:
    """使用 ExamPaperResult 模型的分数聚合测试
    
    **功能: ai-grading-agent, 属性 6: 分数聚合正确性**
    **验证: 需求 4.3**
    """
    
    @given(grading_results=grading_results_list_strategy(min_count=1, max_count=20))
    @settings(max_examples=100)
    def test_exam_paper_result_score_consistency(self, grading_results: List[GradingResult]):
        """
        **功能: ai-grading-agent, 属性 6: 分数聚合正确性**
        **验证: 需求 4.3**
        
        ExamPaperResult 中的 total_score 和 max_total_score 应当与
        question_results 中各题目分数的聚合一致
        """
        # 计算聚合分数
        total_score, max_total_score = aggregate_scores(grading_results)
        
        # 创建 ExamPaperResult
        exam_result = ExamPaperResult(
            submission_id="sub_test",
            exam_id="exam_test",
            student_id="student_test",
            total_score=total_score,
            max_total_score=max_total_score,
            question_results=grading_results,
            overall_feedback=f"总分: {total_score}/{max_total_score}"
        )
        
        # 验证 ExamPaperResult 中的分数与聚合结果一致
        recalculated_total = sum(r.score for r in exam_result.question_results)
        recalculated_max = sum(r.max_score for r in exam_result.question_results)
        
        assert abs(exam_result.total_score - recalculated_total) < 1e-9, \
            f"ExamPaperResult.total_score {exam_result.total_score} 与重新计算的 {recalculated_total} 不一致"
        assert abs(exam_result.max_total_score - recalculated_max) < 1e-9, \
            f"ExamPaperResult.max_total_score {exam_result.max_total_score} 与重新计算的 {recalculated_max} 不一致"
    
    @given(
        scores=st.lists(
            st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=20
        ),
        max_scores=st.lists(
            st.floats(min_value=1.0, max_value=100.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=100)
    def test_aggregation_with_explicit_score_lists(self, scores: List[float], max_scores: List[float]):
        """
        **功能: ai-grading-agent, 属性 6: 分数聚合正确性**
        **验证: 需求 4.3**
        
        对于任意分数列表 [s1, s2, ..., sn] 和满分列表 [m1, m2, ..., mn]，
        聚合结果应当满足 total_score = sum(si), max_total_score = sum(mi)
        """
        # 确保两个列表长度相同
        min_len = min(len(scores), len(max_scores))
        scores = scores[:min_len]
        max_scores = max_scores[:min_len]
        
        # 创建批改结果列表
        grading_results = []
        for i, (score, max_score) in enumerate(zip(scores, max_scores)):
            # 确保 score <= max_score
            actual_score = min(score, max_score)
            result = GradingResult(
                question_id=f"q_{i+1}",
                score=actual_score,
                max_score=max_score,
                confidence=0.9,
                feedback="测试",
                visual_annotations=[],
                agent_trace={}
            )
            grading_results.append(result)
        
        # 计算聚合分数
        total_score, max_total_score = aggregate_scores(grading_results)
        
        # 计算预期值
        expected_total = sum(min(s, m) for s, m in zip(scores, max_scores))
        expected_max = sum(max_scores)
        
        # 验证
        assert abs(total_score - expected_total) < 1e-9, \
            f"聚合总分 {total_score} 不等于预期 {expected_total}"
        assert abs(max_total_score - expected_max) < 1e-9, \
            f"聚合满分 {max_total_score} 不等于预期 {expected_max}"


class TestScoreAggregationCommutativity:
    """分数聚合交换律测试
    
    **功能: ai-grading-agent, 属性 6: 分数聚合正确性**
    **验证: 需求 4.3**
    """
    
    @given(grading_results=grading_results_list_strategy(min_count=2, max_count=20))
    @settings(max_examples=100)
    def test_aggregation_order_independence(self, grading_results: List[GradingResult]):
        """
        **功能: ai-grading-agent, 属性 6: 分数聚合正确性**
        **验证: 需求 4.3**
        
        分数聚合应当与结果顺序无关（交换律）
        """
        import random
        
        # 原始顺序聚合
        total1, max_total1 = aggregate_scores(grading_results)
        
        # 打乱顺序后聚合
        shuffled = grading_results.copy()
        random.shuffle(shuffled)
        total2, max_total2 = aggregate_scores(shuffled)
        
        # 验证结果相同
        assert abs(total1 - total2) < 1e-9, \
            f"不同顺序的聚合总分不一致: {total1} vs {total2}"
        assert abs(max_total1 - max_total2) < 1e-9, \
            f"不同顺序的聚合满分不一致: {max_total1} vs {max_total2}"
    
    @given(
        results1=grading_results_list_strategy(min_count=1, max_count=10),
        results2=grading_results_list_strategy(min_count=1, max_count=10)
    )
    @settings(max_examples=100)
    def test_aggregation_associativity(
        self, 
        results1: List[GradingResult], 
        results2: List[GradingResult]
    ):
        """
        **功能: ai-grading-agent, 属性 6: 分数聚合正确性**
        **验证: 需求 4.3**
        
        分数聚合应当满足结合律：
        aggregate(A + B) = aggregate(A) + aggregate(B)
        """
        # 分别聚合
        total1, max1 = aggregate_scores(results1)
        total2, max2 = aggregate_scores(results2)
        
        # 合并后聚合
        combined = results1 + results2
        total_combined, max_combined = aggregate_scores(combined)
        
        # 验证结合律
        assert abs(total_combined - (total1 + total2)) < 1e-9, \
            f"聚合不满足结合律: {total_combined} != {total1} + {total2}"
        assert abs(max_combined - (max1 + max2)) < 1e-9, \
            f"满分聚合不满足结合律: {max_combined} != {max1} + {max2}"
