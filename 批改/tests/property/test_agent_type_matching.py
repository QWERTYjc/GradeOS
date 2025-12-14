"""智能体类型与题型匹配属性测试

使用 Hypothesis 验证 SupervisorAgent 选择的智能体类型与题型匹配
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import patch

from src.models.enums import QuestionType
from src.agents.pool import AgentPool, AgentNotFoundError
from src.agents.base import BaseGradingAgent
from src.agents.specialized import (
    ObjectiveAgent,
    StepwiseAgent,
    EssayAgent,
    LabDesignAgent,
)


# 定义题型到智能体类型的预期映射
EXPECTED_AGENT_MAPPING = {
    QuestionType.OBJECTIVE: "objective",
    QuestionType.STEPWISE: "stepwise",
    QuestionType.ESSAY: "essay",
    QuestionType.LAB_DESIGN: "lab_design",
}

# 支持的题型（排除 UNKNOWN）
SUPPORTED_QUESTION_TYPES = [
    QuestionType.OBJECTIVE,
    QuestionType.STEPWISE,
    QuestionType.ESSAY,
    QuestionType.LAB_DESIGN,
]


def create_mock_agent_pool() -> AgentPool:
    """创建并注册所有智能体的 AgentPool"""
    AgentPool.reset()
    pool = AgentPool()
    
    # 使用 mock 避免实际初始化 LLM
    with patch.object(ObjectiveAgent, '__init__', lambda x, **kwargs: setattr(x, '_api_key', 'test') or None):
        pool.register_agent(ObjectiveAgent())
    
    with patch.object(StepwiseAgent, '__init__', lambda x, **kwargs: setattr(x, '_api_key', 'test') or None):
        pool.register_agent(StepwiseAgent())
    
    with patch.object(EssayAgent, '__init__', lambda x, **kwargs: setattr(x, '_api_key', 'test') or None):
        pool.register_agent(EssayAgent())
    
    with patch.object(LabDesignAgent, '__init__', lambda x, **kwargs: setattr(x, '_api_key', 'test') or None):
        pool.register_agent(LabDesignAgent())
    
    return pool


class TestAgentTypeMatchingProperties:
    """智能体类型与题型匹配属性测试
    
    **功能: ai-grading-agent, 属性 21: 智能体类型与题型匹配**
    **验证: 需求 11.1, 11.2, 11.3, 11.4**
    """
    
    def setup_method(self):
        """每个测试前重置 AgentPool"""
        AgentPool.reset()
    
    def teardown_method(self):
        """每个测试后重置 AgentPool"""
        AgentPool.reset()
    
    @given(question_type=st.sampled_from(SUPPORTED_QUESTION_TYPES))
    @settings(max_examples=100)
    def test_agent_type_matches_question_type(self, question_type: QuestionType):
        """
        **功能: ai-grading-agent, 属性 21: 智能体类型与题型匹配**
        **验证: 需求 11.1, 11.2, 11.3, 11.4**
        
        对于任意支持的题型，AgentPool 选择的智能体类型应当与题型匹配：
        - OBJECTIVE → ObjectiveAgent (agent_type="objective")
        - STEPWISE → StepwiseAgent (agent_type="stepwise")
        - ESSAY → EssayAgent (agent_type="essay")
        - LAB_DESIGN → LabDesignAgent (agent_type="lab_design")
        """
        pool = create_mock_agent_pool()
        
        # 获取智能体
        agent = pool.get_agent(question_type)
        
        # 验证智能体类型匹配
        expected_agent_type = EXPECTED_AGENT_MAPPING[question_type]
        assert agent.agent_type == expected_agent_type, (
            f"题型 {question_type.value} 应该由 {expected_agent_type} 智能体处理，"
            f"但实际获取到 {agent.agent_type}"
        )
    
    @given(question_type=st.sampled_from(SUPPORTED_QUESTION_TYPES))
    @settings(max_examples=100)
    def test_agent_supports_its_question_type(self, question_type: QuestionType):
        """
        **功能: ai-grading-agent, 属性 21: 智能体类型与题型匹配**
        **验证: 需求 11.1, 11.2, 11.3, 11.4**
        
        对于任意支持的题型，获取到的智能体应当声明支持该题型
        """
        pool = create_mock_agent_pool()
        
        # 获取智能体
        agent = pool.get_agent(question_type)
        
        # 验证智能体声明支持该题型
        assert question_type in agent.supported_question_types, (
            f"智能体 {agent.agent_type} 应该声明支持题型 {question_type.value}，"
            f"但其 supported_question_types 为 {agent.supported_question_types}"
        )
    
    @given(question_type=st.sampled_from(SUPPORTED_QUESTION_TYPES))
    @settings(max_examples=100)
    def test_agent_can_handle_question_type(self, question_type: QuestionType):
        """
        **功能: ai-grading-agent, 属性 21: 智能体类型与题型匹配**
        **验证: 需求 11.1, 11.2, 11.3, 11.4**
        
        对于任意支持的题型，获取到的智能体的 can_handle 方法应当返回 True
        """
        pool = create_mock_agent_pool()
        
        # 获取智能体
        agent = pool.get_agent(question_type)
        
        # 验证 can_handle 返回 True
        assert agent.can_handle(question_type), (
            f"智能体 {agent.agent_type} 的 can_handle({question_type.value}) 应该返回 True"
        )
    
    @given(question_type=st.sampled_from(SUPPORTED_QUESTION_TYPES))
    @settings(max_examples=100)
    def test_agent_selection_is_deterministic(self, question_type: QuestionType):
        """
        **功能: ai-grading-agent, 属性 21: 智能体类型与题型匹配**
        **验证: 需求 11.1, 11.2, 11.3, 11.4**
        
        对于任意支持的题型，多次调用 get_agent 应当返回相同类型的智能体
        """
        pool = create_mock_agent_pool()
        
        # 多次获取智能体
        agent1 = pool.get_agent(question_type)
        agent2 = pool.get_agent(question_type)
        agent3 = pool.get_agent(question_type)
        
        # 验证返回相同类型
        assert agent1.agent_type == agent2.agent_type == agent3.agent_type, (
            f"对于题型 {question_type.value}，多次调用 get_agent 应该返回相同类型的智能体"
        )
    
    def test_unknown_question_type_raises_error(self):
        """
        **功能: ai-grading-agent, 属性 21: 智能体类型与题型匹配**
        **验证: 需求 11.1, 11.2, 11.3, 11.4**
        
        对于 UNKNOWN 题型，AgentPool 应当抛出 AgentNotFoundError
        """
        pool = create_mock_agent_pool()
        
        # 验证 UNKNOWN 题型抛出异常
        with pytest.raises(AgentNotFoundError):
            pool.get_agent(QuestionType.UNKNOWN)
    
    @given(
        question_type1=st.sampled_from(SUPPORTED_QUESTION_TYPES),
        question_type2=st.sampled_from(SUPPORTED_QUESTION_TYPES)
    )
    @settings(max_examples=100)
    def test_different_question_types_get_different_agents(
        self, question_type1: QuestionType, question_type2: QuestionType
    ):
        """
        **功能: ai-grading-agent, 属性 21: 智能体类型与题型匹配**
        **验证: 需求 11.1, 11.2, 11.3, 11.4**
        
        对于不同的题型，应当获取到不同类型的智能体
        """
        # 只在题型不同时测试
        assume(question_type1 != question_type2)
        
        pool = create_mock_agent_pool()
        
        agent1 = pool.get_agent(question_type1)
        agent2 = pool.get_agent(question_type2)
        
        # 验证智能体类型不同
        assert agent1.agent_type != agent2.agent_type, (
            f"题型 {question_type1.value} 和 {question_type2.value} "
            f"应该由不同类型的智能体处理"
        )


class TestSpecializedAgentProperties:
    """专业智能体属性测试
    
    验证每个专业智能体的 agent_type 和 supported_question_types 属性
    """
    
    def test_objective_agent_properties(self):
        """
        **功能: ai-grading-agent, 属性 21: 智能体类型与题型匹配**
        **验证: 需求 11.1**
        
        ObjectiveAgent 应当：
        - agent_type 为 "objective"
        - 支持 QuestionType.OBJECTIVE
        """
        with patch.object(ObjectiveAgent, '__init__', lambda x, **kwargs: setattr(x, '_api_key', 'test') or None):
            agent = ObjectiveAgent()
            
            assert agent.agent_type == "objective"
            assert QuestionType.OBJECTIVE in agent.supported_question_types
            assert agent.can_handle(QuestionType.OBJECTIVE)
            assert not agent.can_handle(QuestionType.STEPWISE)
            assert not agent.can_handle(QuestionType.ESSAY)
            assert not agent.can_handle(QuestionType.LAB_DESIGN)
    
    def test_stepwise_agent_properties(self):
        """
        **功能: ai-grading-agent, 属性 21: 智能体类型与题型匹配**
        **验证: 需求 11.2**
        
        StepwiseAgent 应当：
        - agent_type 为 "stepwise"
        - 支持 QuestionType.STEPWISE
        """
        with patch.object(StepwiseAgent, '__init__', lambda x, **kwargs: setattr(x, '_api_key', 'test') or None):
            agent = StepwiseAgent()
            
            assert agent.agent_type == "stepwise"
            assert QuestionType.STEPWISE in agent.supported_question_types
            assert agent.can_handle(QuestionType.STEPWISE)
            assert not agent.can_handle(QuestionType.OBJECTIVE)
            assert not agent.can_handle(QuestionType.ESSAY)
            assert not agent.can_handle(QuestionType.LAB_DESIGN)
    
    def test_essay_agent_properties(self):
        """
        **功能: ai-grading-agent, 属性 21: 智能体类型与题型匹配**
        **验证: 需求 11.3**
        
        EssayAgent 应当：
        - agent_type 为 "essay"
        - 支持 QuestionType.ESSAY
        """
        with patch.object(EssayAgent, '__init__', lambda x, **kwargs: setattr(x, '_api_key', 'test') or None):
            agent = EssayAgent()
            
            assert agent.agent_type == "essay"
            assert QuestionType.ESSAY in agent.supported_question_types
            assert agent.can_handle(QuestionType.ESSAY)
            assert not agent.can_handle(QuestionType.OBJECTIVE)
            assert not agent.can_handle(QuestionType.STEPWISE)
            assert not agent.can_handle(QuestionType.LAB_DESIGN)
    
    def test_lab_design_agent_properties(self):
        """
        **功能: ai-grading-agent, 属性 21: 智能体类型与题型匹配**
        **验证: 需求 11.4**
        
        LabDesignAgent 应当：
        - agent_type 为 "lab_design"
        - 支持 QuestionType.LAB_DESIGN
        """
        with patch.object(LabDesignAgent, '__init__', lambda x, **kwargs: setattr(x, '_api_key', 'test') or None):
            agent = LabDesignAgent()
            
            assert agent.agent_type == "lab_design"
            assert QuestionType.LAB_DESIGN in agent.supported_question_types
            assert agent.can_handle(QuestionType.LAB_DESIGN)
            assert not agent.can_handle(QuestionType.OBJECTIVE)
            assert not agent.can_handle(QuestionType.STEPWISE)
            assert not agent.can_handle(QuestionType.ESSAY)
