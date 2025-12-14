"""Context Pack 结构完整性属性测试

使用 Hypothesis 验证 SupervisorAgent 构建的 Context Pack 结构完整性

**功能: ai-grading-agent, 属性 19: Context Pack 结构完整性**
**验证: 需求 3.2**
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import patch
from typing import Optional, List, Dict, Any

from src.models.enums import QuestionType
from src.agents.supervisor import SupervisorAgent
from src.agents.pool import AgentPool
from src.models.state import ContextPack


# 所有有效的 QuestionType 值
ALL_QUESTION_TYPES = list(QuestionType)


def create_mock_supervisor() -> SupervisorAgent:
    """创建一个 mock 的 SupervisorAgent"""
    with patch('src.agents.supervisor.ChatGoogleGenerativeAI'):
        AgentPool.reset()
        supervisor = SupervisorAgent(api_key="test_key")
        return supervisor


# 生成有效的 Base64 图像数据的策略
valid_image_data_strategy = st.text(
    alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='+/='),
    min_size=10,
    max_size=1000
)

# 生成有效的评分细则文本的策略
valid_rubric_strategy = st.text(min_size=1, max_size=500)

# 生成有效的满分值的策略
valid_max_score_strategy = st.floats(min_value=0.1, max_value=100.0, allow_nan=False, allow_infinity=False)

# 生成可选的标准答案的策略
optional_standard_answer_strategy = st.one_of(st.none(), st.text(min_size=1, max_size=200))

# 生成可选的术语列表的策略
optional_terminology_strategy = st.one_of(
    st.none(),
    st.lists(st.text(min_size=1, max_size=50), min_size=0, max_size=10)
)


class TestContextPackCompleteness:
    """Context Pack 结构完整性属性测试
    
    **功能: ai-grading-agent, 属性 19: Context Pack 结构完整性**
    **验证: 需求 3.2**
    """
    
    def setup_method(self):
        """每个测试前重置 AgentPool"""
        AgentPool.reset()
    
    def teardown_method(self):
        """每个测试后重置 AgentPool"""
        AgentPool.reset()
    
    @given(
        question_image=valid_image_data_strategy,
        question_type=st.sampled_from(ALL_QUESTION_TYPES),
        rubric=valid_rubric_strategy,
        max_score=valid_max_score_strategy
    )
    @settings(max_examples=100)
    def test_required_fields_present(
        self,
        question_image: str,
        question_type: QuestionType,
        rubric: str,
        max_score: float
    ):
        """
        **功能: ai-grading-agent, 属性 19: Context Pack 结构完整性**
        **验证: 需求 3.2**
        
        对于任意 SupervisorAgent 构建的 Context Pack，应当包含所有必需字段：
        - 非空的 question_image
        - 有效的 question_type
        - 非空的 rubric
        - 正数的 max_score
        """
        supervisor = create_mock_supervisor()
        
        # 构建 Context Pack
        context_pack = supervisor.build_context_pack(
            question_image=question_image,
            question_type=question_type,
            rubric=rubric,
            max_score=max_score
        )
        
        # 验证必需字段存在且非空
        assert "question_image" in context_pack, "Context Pack 缺少 question_image 字段"
        assert context_pack["question_image"], "question_image 不能为空"
        assert context_pack["question_image"] == question_image, "question_image 值不匹配"
        
        assert "question_type" in context_pack, "Context Pack 缺少 question_type 字段"
        assert context_pack["question_type"] in ALL_QUESTION_TYPES, (
            f"question_type {context_pack['question_type']} 不是有效的 QuestionType"
        )
        assert context_pack["question_type"] == question_type, "question_type 值不匹配"
        
        assert "rubric" in context_pack, "Context Pack 缺少 rubric 字段"
        assert context_pack["rubric"], "rubric 不能为空"
        assert context_pack["rubric"] == rubric, "rubric 值不匹配"
        
        assert "max_score" in context_pack, "Context Pack 缺少 max_score 字段"
        assert context_pack["max_score"] > 0, f"max_score 必须为正数，但得到 {context_pack['max_score']}"
        assert context_pack["max_score"] == max_score, "max_score 值不匹配"
    
    @given(
        question_image=valid_image_data_strategy,
        question_type=st.sampled_from(ALL_QUESTION_TYPES),
        rubric=valid_rubric_strategy,
        max_score=valid_max_score_strategy,
        standard_answer=optional_standard_answer_strategy,
        terminology=optional_terminology_strategy
    )
    @settings(max_examples=100)
    def test_optional_fields_handling(
        self,
        question_image: str,
        question_type: QuestionType,
        rubric: str,
        max_score: float,
        standard_answer: Optional[str],
        terminology: Optional[List[str]]
    ):
        """
        **功能: ai-grading-agent, 属性 19: Context Pack 结构完整性**
        **验证: 需求 3.2**
        
        对于任意可选字段，Context Pack 应当正确处理：
        - standard_answer 可以为 None 或非空字符串
        - terminology 可以为 None 或列表（为 None 时默认为空列表）
        """
        supervisor = create_mock_supervisor()
        
        # 构建 Context Pack
        context_pack = supervisor.build_context_pack(
            question_image=question_image,
            question_type=question_type,
            rubric=rubric,
            max_score=max_score,
            standard_answer=standard_answer,
            terminology=terminology
        )
        
        # 验证必需字段仍然存在
        assert context_pack["question_image"] == question_image
        assert context_pack["question_type"] == question_type
        assert context_pack["rubric"] == rubric
        assert context_pack["max_score"] == max_score
        
        # 验证可选字段处理
        if standard_answer is not None:
            assert "standard_answer" in context_pack, "提供了 standard_answer 但未包含在 Context Pack 中"
            assert context_pack["standard_answer"] == standard_answer
        
        # terminology 为 None 时应该默认为空列表
        assert "terminology" in context_pack, "Context Pack 缺少 terminology 字段"
        if terminology is not None:
            assert context_pack["terminology"] == terminology
        else:
            assert context_pack["terminology"] == [], "terminology 为 None 时应该默认为空列表"
    
    @given(
        question_image=valid_image_data_strategy,
        question_type=st.sampled_from(ALL_QUESTION_TYPES),
        rubric=valid_rubric_strategy,
        max_score=valid_max_score_strategy,
        previous_score=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        previous_confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_previous_result_handling(
        self,
        question_image: str,
        question_type: QuestionType,
        rubric: str,
        max_score: float,
        previous_score: float,
        previous_confidence: float
    ):
        """
        **功能: ai-grading-agent, 属性 19: Context Pack 结构完整性**
        **验证: 需求 3.2**
        
        对于二次评估场景，Context Pack 应当正确包含 previous_result 字段
        """
        supervisor = create_mock_supervisor()
        
        previous_result = {
            "score": previous_score,
            "confidence": previous_confidence,
            "vision_analysis": "测试视觉分析",
            "rubric_mapping": [],
            "reasoning_trace": ["步骤1", "步骤2"]
        }
        
        # 构建 Context Pack
        context_pack = supervisor.build_context_pack(
            question_image=question_image,
            question_type=question_type,
            rubric=rubric,
            max_score=max_score,
            previous_result=previous_result
        )
        
        # 验证必需字段仍然存在
        assert context_pack["question_image"] == question_image
        assert context_pack["question_type"] == question_type
        assert context_pack["rubric"] == rubric
        assert context_pack["max_score"] == max_score
        
        # 验证 previous_result 字段
        assert "previous_result" in context_pack, "提供了 previous_result 但未包含在 Context Pack 中"
        assert context_pack["previous_result"] == previous_result
        assert context_pack["previous_result"]["score"] == previous_score
        assert context_pack["previous_result"]["confidence"] == previous_confidence
    
    @given(
        question_type=st.sampled_from(ALL_QUESTION_TYPES),
        rubric=valid_rubric_strategy,
        max_score=valid_max_score_strategy
    )
    @settings(max_examples=100)
    def test_question_type_is_valid_enum(
        self,
        question_type: QuestionType,
        rubric: str,
        max_score: float
    ):
        """
        **功能: ai-grading-agent, 属性 19: Context Pack 结构完整性**
        **验证: 需求 3.2**
        
        对于任意 Context Pack，question_type 必须是有效的 QuestionType 枚举值
        """
        supervisor = create_mock_supervisor()
        
        # 构建 Context Pack
        context_pack = supervisor.build_context_pack(
            question_image="test_image_data",
            question_type=question_type,
            rubric=rubric,
            max_score=max_score
        )
        
        # 验证 question_type 是有效的枚举值
        assert isinstance(context_pack["question_type"], QuestionType), (
            f"question_type 应该是 QuestionType 枚举，但得到 {type(context_pack['question_type'])}"
        )
        assert context_pack["question_type"] in ALL_QUESTION_TYPES, (
            f"question_type {context_pack['question_type']} 不是有效的 QuestionType"
        )
    
    @given(
        max_score=st.floats(min_value=0.1, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_max_score_is_positive(self, max_score: float):
        """
        **功能: ai-grading-agent, 属性 19: Context Pack 结构完整性**
        **验证: 需求 3.2**
        
        对于任意 Context Pack，max_score 必须是正数
        """
        supervisor = create_mock_supervisor()
        
        # 构建 Context Pack
        context_pack = supervisor.build_context_pack(
            question_image="test_image_data",
            question_type=QuestionType.OBJECTIVE,
            rubric="测试评分细则",
            max_score=max_score
        )
        
        # 验证 max_score 是正数
        assert context_pack["max_score"] > 0, (
            f"max_score 必须为正数，但得到 {context_pack['max_score']}"
        )
        assert context_pack["max_score"] == max_score, "max_score 值不匹配"


class TestContextPackTypeConsistency:
    """Context Pack 类型一致性测试
    
    **功能: ai-grading-agent, 属性 19: Context Pack 结构完整性**
    **验证: 需求 3.2**
    """
    
    def setup_method(self):
        """每个测试前重置 AgentPool"""
        AgentPool.reset()
    
    def teardown_method(self):
        """每个测试后重置 AgentPool"""
        AgentPool.reset()
    
    @given(
        question_image=valid_image_data_strategy,
        question_type=st.sampled_from(ALL_QUESTION_TYPES),
        rubric=valid_rubric_strategy,
        max_score=valid_max_score_strategy
    )
    @settings(max_examples=100)
    def test_context_pack_is_dict(
        self,
        question_image: str,
        question_type: QuestionType,
        rubric: str,
        max_score: float
    ):
        """
        **功能: ai-grading-agent, 属性 19: Context Pack 结构完整性**
        **验证: 需求 3.2**
        
        对于任意输入，build_context_pack 应当返回一个字典类型
        """
        supervisor = create_mock_supervisor()
        
        # 构建 Context Pack
        context_pack = supervisor.build_context_pack(
            question_image=question_image,
            question_type=question_type,
            rubric=rubric,
            max_score=max_score
        )
        
        # 验证返回类型是字典
        assert isinstance(context_pack, dict), (
            f"Context Pack 应该是字典类型，但得到 {type(context_pack)}"
        )
    
    @given(
        question_image=valid_image_data_strategy,
        question_type=st.sampled_from(ALL_QUESTION_TYPES),
        rubric=valid_rubric_strategy,
        max_score=valid_max_score_strategy
    )
    @settings(max_examples=100)
    def test_field_types_are_correct(
        self,
        question_image: str,
        question_type: QuestionType,
        rubric: str,
        max_score: float
    ):
        """
        **功能: ai-grading-agent, 属性 19: Context Pack 结构完整性**
        **验证: 需求 3.2**
        
        对于任意 Context Pack，各字段的类型应当正确：
        - question_image: str
        - question_type: QuestionType
        - rubric: str
        - max_score: float
        - terminology: List[str]
        """
        supervisor = create_mock_supervisor()
        
        # 构建 Context Pack
        context_pack = supervisor.build_context_pack(
            question_image=question_image,
            question_type=question_type,
            rubric=rubric,
            max_score=max_score
        )
        
        # 验证字段类型
        assert isinstance(context_pack["question_image"], str), (
            f"question_image 应该是 str，但得到 {type(context_pack['question_image'])}"
        )
        assert isinstance(context_pack["question_type"], QuestionType), (
            f"question_type 应该是 QuestionType，但得到 {type(context_pack['question_type'])}"
        )
        assert isinstance(context_pack["rubric"], str), (
            f"rubric 应该是 str，但得到 {type(context_pack['rubric'])}"
        )
        assert isinstance(context_pack["max_score"], float), (
            f"max_score 应该是 float，但得到 {type(context_pack['max_score'])}"
        )
        assert isinstance(context_pack["terminology"], list), (
            f"terminology 应该是 list，但得到 {type(context_pack['terminology'])}"
        )


class TestContextPackIdempotence:
    """Context Pack 构建幂等性测试
    
    **功能: ai-grading-agent, 属性 19: Context Pack 结构完整性**
    **验证: 需求 3.2**
    """
    
    def setup_method(self):
        """每个测试前重置 AgentPool"""
        AgentPool.reset()
    
    def teardown_method(self):
        """每个测试后重置 AgentPool"""
        AgentPool.reset()
    
    @given(
        question_image=valid_image_data_strategy,
        question_type=st.sampled_from(ALL_QUESTION_TYPES),
        rubric=valid_rubric_strategy,
        max_score=valid_max_score_strategy,
        num_calls=st.integers(min_value=2, max_value=5)
    )
    @settings(max_examples=100)
    def test_build_is_deterministic(
        self,
        question_image: str,
        question_type: QuestionType,
        rubric: str,
        max_score: float,
        num_calls: int
    ):
        """
        **功能: ai-grading-agent, 属性 19: Context Pack 结构完整性**
        **验证: 需求 3.2**
        
        对于相同的输入，多次调用 build_context_pack 应当返回相同的结果
        """
        supervisor = create_mock_supervisor()
        
        # 多次构建 Context Pack
        results = []
        for _ in range(num_calls):
            context_pack = supervisor.build_context_pack(
                question_image=question_image,
                question_type=question_type,
                rubric=rubric,
                max_score=max_score
            )
            results.append(context_pack)
        
        # 验证所有结果相同
        first_result = results[0]
        for i, result in enumerate(results[1:], start=2):
            assert result == first_result, (
                f"第 {i} 次调用结果与第 1 次调用结果不一致"
            )
