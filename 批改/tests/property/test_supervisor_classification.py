"""SupervisorAgent 题型分类一致性属性测试

使用 Hypothesis 验证 SupervisorAgent 的题型分类行为

**功能: ai-grading-agent, 属性 18: SupervisorAgent 题型分类一致性**
**验证: 需求 3.1**
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import patch, AsyncMock, MagicMock
import asyncio


def run_async(coro):
    """运行异步协程的辅助函数"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

from src.models.enums import QuestionType
from src.agents.supervisor import SupervisorAgent
from src.agents.pool import AgentPool


# 所有有效的 QuestionType 值
ALL_QUESTION_TYPES = list(QuestionType)

# 模型可能返回的有效题型字符串
VALID_TYPE_STRINGS = ["objective", "stepwise", "essay", "lab_design", "unknown"]

# 模型可能返回的无效/意外字符串（不包括大小写变体，因为代码支持大小写不敏感）
INVALID_TYPE_STRINGS = [
    "multiple_choice",
    "calculation",
    "writing",
    "experiment",
    "other",
    "invalid",
    "",
    "choice",
    "math",
    "composition",
    "lab",
]


def create_mock_supervisor() -> SupervisorAgent:
    """创建一个 mock 的 SupervisorAgent"""
    with patch('src.agents.supervisor.ChatGoogleGenerativeAI'):
        AgentPool.reset()
        supervisor = SupervisorAgent(api_key="test_key")
        return supervisor


class TestSupervisorClassificationConsistency:
    """SupervisorAgent 题型分类一致性属性测试
    
    **功能: ai-grading-agent, 属性 18: SupervisorAgent 题型分类一致性**
    **验证: 需求 3.1**
    """
    
    def setup_method(self):
        """每个测试前重置 AgentPool"""
        AgentPool.reset()
    
    def teardown_method(self):
        """每个测试后重置 AgentPool"""
        AgentPool.reset()
    
    @given(model_response=st.sampled_from(VALID_TYPE_STRINGS))
    @settings(max_examples=100)
    def test_valid_response_returns_valid_question_type(self, model_response: str):
        """
        **功能: ai-grading-agent, 属性 18: SupervisorAgent 题型分类一致性**
        **验证: 需求 3.1**
        
        对于任意有效的模型响应字符串，analyze_question_type 应当返回有效的 QuestionType 枚举值
        """
        supervisor = create_mock_supervisor()
        
        # Mock LLM 响应
        mock_response = MagicMock()
        mock_response.content = model_response
        supervisor.llm.ainvoke = AsyncMock(return_value=mock_response)
        
        # 执行分析
        result = run_async(supervisor.analyze_question_type("base64_image_data"))
        
        # 验证返回值是有效的 QuestionType
        assert isinstance(result, QuestionType), (
            f"返回值应该是 QuestionType 枚举，但得到 {type(result)}"
        )
        assert result in ALL_QUESTION_TYPES, (
            f"返回值 {result} 不是有效的 QuestionType"
        )
    
    @given(model_response=st.sampled_from(INVALID_TYPE_STRINGS))
    @settings(max_examples=100)
    def test_invalid_response_returns_unknown(self, model_response: str):
        """
        **功能: ai-grading-agent, 属性 18: SupervisorAgent 题型分类一致性**
        **验证: 需求 3.1**
        
        对于任意无效的模型响应字符串，analyze_question_type 应当返回 QuestionType.UNKNOWN
        """
        supervisor = create_mock_supervisor()
        
        # Mock LLM 响应
        mock_response = MagicMock()
        mock_response.content = model_response
        supervisor.llm.ainvoke = AsyncMock(return_value=mock_response)
        
        # 执行分析
        result = run_async(supervisor.analyze_question_type("base64_image_data"))
        
        # 验证返回值是 UNKNOWN（因为无法识别）
        assert isinstance(result, QuestionType), (
            f"返回值应该是 QuestionType 枚举，但得到 {type(result)}"
        )
        # 无效响应应该映射到 UNKNOWN
        assert result == QuestionType.UNKNOWN, (
            f"无效响应 '{model_response}' 应该返回 UNKNOWN，但得到 {result}"
        )
    
    @given(
        model_response=st.sampled_from(VALID_TYPE_STRINGS),
        num_calls=st.integers(min_value=2, max_value=5)
    )
    @settings(max_examples=100)
    def test_classification_is_deterministic(self, model_response: str, num_calls: int):
        """
        **功能: ai-grading-agent, 属性 18: SupervisorAgent 题型分类一致性**
        **验证: 需求 3.1**
        
        对于任意图像，多次分析同一图像（模型返回相同响应）应当返回相同的题型
        """
        supervisor = create_mock_supervisor()
        
        # Mock LLM 响应 - 每次返回相同的响应
        mock_response = MagicMock()
        mock_response.content = model_response
        supervisor.llm.ainvoke = AsyncMock(return_value=mock_response)
        
        # 多次执行分析
        results = []
        for _ in range(num_calls):
            result = run_async(supervisor.analyze_question_type("base64_image_data"))
            results.append(result)
        
        # 验证所有结果相同
        first_result = results[0]
        for i, result in enumerate(results[1:], start=2):
            assert result == first_result, (
                f"第 {i} 次调用返回 {result}，与第 1 次调用返回 {first_result} 不一致"
            )
    
    @given(image_data=st.text(min_size=1, max_size=100))
    @settings(max_examples=100)
    def test_any_image_data_returns_valid_type(self, image_data: str):
        """
        **功能: ai-grading-agent, 属性 18: SupervisorAgent 题型分类一致性**
        **验证: 需求 3.1**
        
        对于任意图像数据输入，analyze_question_type 应当返回有效的 QuestionType 枚举值
        """
        supervisor = create_mock_supervisor()
        
        # Mock LLM 响应 - 返回一个有效的题型
        mock_response = MagicMock()
        mock_response.content = "objective"
        supervisor.llm.ainvoke = AsyncMock(return_value=mock_response)
        
        # 执行分析
        result = run_async(supervisor.analyze_question_type(image_data))
        
        # 验证返回值是有效的 QuestionType
        assert isinstance(result, QuestionType), (
            f"返回值应该是 QuestionType 枚举，但得到 {type(result)}"
        )
        assert result in ALL_QUESTION_TYPES, (
            f"返回值 {result} 不是有效的 QuestionType"
        )
    
    def test_api_error_returns_unknown(self):
        """
        **功能: ai-grading-agent, 属性 18: SupervisorAgent 题型分类一致性**
        **验证: 需求 3.1**
        
        当 API 调用失败时，analyze_question_type 应当返回 QuestionType.UNKNOWN
        """
        supervisor = create_mock_supervisor()
        
        # Mock LLM 抛出异常
        supervisor.llm.ainvoke = AsyncMock(side_effect=Exception("API Error"))
        
        # 执行分析
        result = run_async(supervisor.analyze_question_type("base64_image_data"))
        
        # 验证返回值是 UNKNOWN
        assert result == QuestionType.UNKNOWN, (
            f"API 错误时应该返回 UNKNOWN，但得到 {result}"
        )


class TestQuestionTypeMapping:
    """题型字符串到枚举的映射测试
    
    **功能: ai-grading-agent, 属性 18: SupervisorAgent 题型分类一致性**
    **验证: 需求 3.1**
    """
    
    @given(question_type=st.sampled_from(ALL_QUESTION_TYPES))
    @settings(max_examples=100)
    def test_type_value_maps_back_to_type(self, question_type: QuestionType):
        """
        **功能: ai-grading-agent, 属性 18: SupervisorAgent 题型分类一致性**
        **验证: 需求 3.1**
        
        对于任意 QuestionType，其 value 字符串应当能够映射回相同的 QuestionType
        """
        AgentPool.reset()
        supervisor = create_mock_supervisor()
        
        # Mock LLM 响应 - 返回题型的 value
        mock_response = MagicMock()
        mock_response.content = question_type.value
        supervisor.llm.ainvoke = AsyncMock(return_value=mock_response)
        
        # 执行分析
        result = run_async(supervisor.analyze_question_type("base64_image_data"))
        
        # 验证映射回相同的类型
        assert result == question_type, (
            f"题型值 '{question_type.value}' 应该映射回 {question_type}，但得到 {result}"
        )
    
    @given(
        whitespace_prefix=st.text(alphabet=" \t\n", max_size=3),
        whitespace_suffix=st.text(alphabet=" \t\n", max_size=3),
        question_type=st.sampled_from(VALID_TYPE_STRINGS)
    )
    @settings(max_examples=100)
    def test_whitespace_handling(
        self, whitespace_prefix: str, whitespace_suffix: str, question_type: str
    ):
        """
        **功能: ai-grading-agent, 属性 18: SupervisorAgent 题型分类一致性**
        **验证: 需求 3.1**
        
        对于任意带有前后空白的题型字符串，应当正确处理并返回有效的 QuestionType
        """
        AgentPool.reset()
        supervisor = create_mock_supervisor()
        
        # Mock LLM 响应 - 带有空白的题型字符串
        mock_response = MagicMock()
        mock_response.content = f"{whitespace_prefix}{question_type}{whitespace_suffix}"
        supervisor.llm.ainvoke = AsyncMock(return_value=mock_response)
        
        # 执行分析
        result = run_async(supervisor.analyze_question_type("base64_image_data"))
        
        # 验证返回值是有效的 QuestionType
        assert isinstance(result, QuestionType), (
            f"返回值应该是 QuestionType 枚举，但得到 {type(result)}"
        )
        
        # 验证映射正确
        expected_mapping = {
            "objective": QuestionType.OBJECTIVE,
            "stepwise": QuestionType.STEPWISE,
            "essay": QuestionType.ESSAY,
            "lab_design": QuestionType.LAB_DESIGN,
            "unknown": QuestionType.UNKNOWN,
        }
        expected = expected_mapping.get(question_type, QuestionType.UNKNOWN)
        assert result == expected, (
            f"带空白的 '{question_type}' 应该映射到 {expected}，但得到 {result}"
        )
    
    @given(
        case_variant=st.sampled_from([
            "OBJECTIVE", "Objective", "OBJective",
            "STEPWISE", "Stepwise", "STEPwise",
            "ESSAY", "Essay", "ESSay",
            "LAB_DESIGN", "Lab_Design", "lab_DESIGN",
            "UNKNOWN", "Unknown", "UNknown",
        ])
    )
    @settings(max_examples=100)
    def test_case_insensitive_mapping(self, case_variant: str):
        """
        **功能: ai-grading-agent, 属性 18: SupervisorAgent 题型分类一致性**
        **验证: 需求 3.1**
        
        对于任意大小写变体的题型字符串，应当正确映射到对应的 QuestionType
        """
        AgentPool.reset()
        supervisor = create_mock_supervisor()
        
        # Mock LLM 响应
        mock_response = MagicMock()
        mock_response.content = case_variant
        supervisor.llm.ainvoke = AsyncMock(return_value=mock_response)
        
        # 执行分析
        result = run_async(supervisor.analyze_question_type("base64_image_data"))
        
        # 验证返回值是有效的 QuestionType
        assert isinstance(result, QuestionType), (
            f"返回值应该是 QuestionType 枚举，但得到 {type(result)}"
        )
        
        # 验证映射正确（大小写不敏感）
        expected_mapping = {
            "objective": QuestionType.OBJECTIVE,
            "stepwise": QuestionType.STEPWISE,
            "essay": QuestionType.ESSAY,
            "lab_design": QuestionType.LAB_DESIGN,
            "unknown": QuestionType.UNKNOWN,
        }
        expected = expected_mapping.get(case_variant.lower(), QuestionType.UNKNOWN)
        assert result == expected, (
            f"大小写变体 '{case_variant}' 应该映射到 {expected}，但得到 {result}"
        )

