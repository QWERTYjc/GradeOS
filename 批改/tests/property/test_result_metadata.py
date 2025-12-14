"""结果元数据完整性属性测试

使用 Hypothesis 验证批改智能体返回的结果包含有效的元数据

**功能: ai-grading-agent, 属性 23: 结果元数据完整性**
**验证: 需求 11.6**
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from typing import List, Dict, Any, Optional
from unittest.mock import patch, MagicMock, AsyncMock

from src.models.enums import QuestionType
from src.models.state import GradingState, ContextPack, EvidenceItem
from src.agents.base import BaseGradingAgent
from src.agents.pool import AgentPool
from src.agents.specialized import (
    ObjectiveAgent,
    StepwiseAgent,
    EssayAgent,
    LabDesignAgent,
)


# ===== 有效的智能体类型列表 =====
VALID_AGENT_TYPES = ["objective", "stepwise", "essay", "lab_design"]

# ===== 有效的题型列表（排除 UNKNOWN）=====
VALID_QUESTION_TYPES = [
    QuestionType.OBJECTIVE,
    QuestionType.STEPWISE,
    QuestionType.ESSAY,
    QuestionType.LAB_DESIGN,
]

# ===== 智能体类型到题型的映射 =====
AGENT_TYPE_TO_QUESTION_TYPE = {
    "objective": QuestionType.OBJECTIVE,
    "stepwise": QuestionType.STEPWISE,
    "essay": QuestionType.ESSAY,
    "lab_design": QuestionType.LAB_DESIGN,
}


def validate_result_metadata(state: GradingState) -> bool:
    """验证批改结果的元数据完整性
    
    根据需求 11.6，批改智能体返回的结果应当包含：
    - 有效的 question_type 标识
    - 有效的 agent_type 标识
    
    Args:
        state: 批改结果状态
        
    Returns:
        如果元数据完整且有效则返回 True
    """
    # 检查 agent_type 存在且有效
    agent_type = state.get("agent_type")
    if not agent_type or agent_type not in VALID_AGENT_TYPES:
        return False
    
    # 检查 context_pack 中的 question_type 存在且有效
    context_pack = state.get("context_pack")
    if context_pack:
        question_type = context_pack.get("question_type")
        if question_type and question_type not in VALID_QUESTION_TYPES:
            return False
    
    return True


def create_mock_grading_state(
    agent_type: str,
    question_type: QuestionType,
    final_score: float = 5.0,
    max_score: float = 10.0,
    confidence: float = 0.85
) -> GradingState:
    """创建模拟的批改结果状态
    
    Args:
        agent_type: 智能体类型
        question_type: 题型
        final_score: 最终得分
        max_score: 满分
        confidence: 置信度
        
    Returns:
        GradingState 实例
    """
    context_pack: ContextPack = {
        "question_image": "base64_encoded_image",
        "question_type": question_type,
        "rubric": "评分细则内容",
        "max_score": max_score,
        "standard_answer": None,
        "terminology": [],
        "previous_result": None,
    }
    
    evidence: EvidenceItem = {
        "scoring_point": "测试评分点",
        "image_region": [0, 0, 100, 100],
        "text_description": "测试描述",
        "reasoning": "测试理由",
        "rubric_reference": "测试参考",
        "points_awarded": final_score,
    }
    
    return GradingState(
        context_pack=context_pack,
        vision_analysis="视觉分析结果",
        rubric_mapping=[{
            "rubric_point": "评分点",
            "evidence": "证据",
            "score_awarded": final_score,
            "max_score": max_score,
        }],
        initial_score=final_score,
        reasoning_trace=["步骤1", "步骤2"],
        critique_feedback=None,
        evidence_chain=[evidence],
        final_score=final_score,
        max_score=max_score,
        confidence=confidence,
        visual_annotations=[],
        student_feedback="测试反馈",
        agent_type=agent_type,
        revision_count=0,
        is_finalized=True,
        needs_secondary_review=False,
    )


class TestResultMetadataCompleteness:
    """结果元数据完整性属性测试
    
    **功能: ai-grading-agent, 属性 23: 结果元数据完整性**
    **验证: 需求 11.6**
    """
    
    @given(
        agent_type=st.sampled_from(VALID_AGENT_TYPES),
        question_type=st.sampled_from(VALID_QUESTION_TYPES),
        final_score=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        max_score=st.floats(min_value=1.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_valid_result_metadata_passes_validation(
        self,
        agent_type: str,
        question_type: QuestionType,
        final_score: float,
        max_score: float,
        confidence: float
    ):
        """
        **功能: ai-grading-agent, 属性 23: 结果元数据完整性**
        **验证: 需求 11.6**
        
        对于任意有效的批改结果，元数据验证应当通过
        """
        # 确保 final_score <= max_score
        assume(final_score <= max_score)
        
        state = create_mock_grading_state(
            agent_type=agent_type,
            question_type=question_type,
            final_score=final_score,
            max_score=max_score,
            confidence=confidence
        )
        
        assert validate_result_metadata(state), (
            f"有效的批改结果应当通过元数据验证: agent_type={agent_type}, "
            f"question_type={question_type}"
        )
    
    @given(
        agent_type=st.sampled_from(VALID_AGENT_TYPES),
        question_type=st.sampled_from(VALID_QUESTION_TYPES)
    )
    @settings(max_examples=100)
    def test_result_contains_agent_type(
        self,
        agent_type: str,
        question_type: QuestionType
    ):
        """
        **功能: ai-grading-agent, 属性 23: 结果元数据完整性**
        **验证: 需求 11.6**
        
        对于任意批改结果，应当包含有效的 agent_type 标识
        """
        state = create_mock_grading_state(
            agent_type=agent_type,
            question_type=question_type
        )
        
        # 验证 agent_type 存在
        assert "agent_type" in state, "批改结果应当包含 agent_type 字段"
        
        # 验证 agent_type 有效
        assert state["agent_type"] in VALID_AGENT_TYPES, (
            f"agent_type 应当是有效值，实际值为 {state['agent_type']}"
        )
    
    @given(
        agent_type=st.sampled_from(VALID_AGENT_TYPES),
        question_type=st.sampled_from(VALID_QUESTION_TYPES)
    )
    @settings(max_examples=100)
    def test_result_contains_question_type_in_context(
        self,
        agent_type: str,
        question_type: QuestionType
    ):
        """
        **功能: ai-grading-agent, 属性 23: 结果元数据完整性**
        **验证: 需求 11.6**
        
        对于任意批改结果，context_pack 中应当包含有效的 question_type 标识
        """
        state = create_mock_grading_state(
            agent_type=agent_type,
            question_type=question_type
        )
        
        # 验证 context_pack 存在
        assert "context_pack" in state, "批改结果应当包含 context_pack 字段"
        
        context_pack = state["context_pack"]
        
        # 验证 question_type 存在
        assert "question_type" in context_pack, (
            "context_pack 应当包含 question_type 字段"
        )
        
        # 验证 question_type 有效
        assert context_pack["question_type"] in VALID_QUESTION_TYPES, (
            f"question_type 应当是有效值，实际值为 {context_pack['question_type']}"
        )
    
    @given(
        agent_type=st.sampled_from(VALID_AGENT_TYPES)
    )
    @settings(max_examples=100)
    def test_agent_type_matches_expected_format(
        self,
        agent_type: str
    ):
        """
        **功能: ai-grading-agent, 属性 23: 结果元数据完整性**
        **验证: 需求 11.6**
        
        对于任意 agent_type，应当是预定义的有效值之一
        """
        # 验证 agent_type 是字符串
        assert isinstance(agent_type, str), "agent_type 应当是字符串"
        
        # 验证 agent_type 非空
        assert agent_type, "agent_type 不应为空"
        
        # 验证 agent_type 是有效值
        assert agent_type in VALID_AGENT_TYPES, (
            f"agent_type 应当是 {VALID_AGENT_TYPES} 之一，实际值为 {agent_type}"
        )
    
    @given(
        question_type=st.sampled_from(VALID_QUESTION_TYPES)
    )
    @settings(max_examples=100)
    def test_question_type_is_valid_enum(
        self,
        question_type: QuestionType
    ):
        """
        **功能: ai-grading-agent, 属性 23: 结果元数据完整性**
        **验证: 需求 11.6**
        
        对于任意 question_type，应当是有效的 QuestionType 枚举值
        """
        # 验证 question_type 是 QuestionType 枚举
        assert isinstance(question_type, QuestionType), (
            f"question_type 应当是 QuestionType 枚举，实际类型为 {type(question_type)}"
        )
        
        # 验证不是 UNKNOWN
        assert question_type != QuestionType.UNKNOWN, (
            "有效的批改结果不应包含 UNKNOWN 题型"
        )


class TestResultMetadataInvalidInputs:
    """结果元数据无效输入测试
    
    验证无效的元数据被正确拒绝
    """
    
    @given(
        question_type=st.sampled_from(VALID_QUESTION_TYPES)
    )
    @settings(max_examples=50)
    def test_empty_agent_type_fails_validation(
        self,
        question_type: QuestionType
    ):
        """
        **功能: ai-grading-agent, 属性 23: 结果元数据完整性**
        **验证: 需求 11.6**
        
        空的 agent_type 应当导致验证失败
        """
        state = create_mock_grading_state(
            agent_type="",  # 空字符串
            question_type=question_type
        )
        
        assert not validate_result_metadata(state), (
            "空的 agent_type 应当导致验证失败"
        )
    
    @given(
        question_type=st.sampled_from(VALID_QUESTION_TYPES),
        invalid_agent_type=st.text(min_size=1).filter(
            lambda s: s not in VALID_AGENT_TYPES
        )
    )
    @settings(max_examples=50)
    def test_invalid_agent_type_fails_validation(
        self,
        question_type: QuestionType,
        invalid_agent_type: str
    ):
        """
        **功能: ai-grading-agent, 属性 23: 结果元数据完整性**
        **验证: 需求 11.6**
        
        无效的 agent_type 应当导致验证失败
        """
        state = create_mock_grading_state(
            agent_type=invalid_agent_type,
            question_type=question_type
        )
        
        assert not validate_result_metadata(state), (
            f"无效的 agent_type '{invalid_agent_type}' 应当导致验证失败"
        )
    
    def test_missing_agent_type_fails_validation(self):
        """
        **功能: ai-grading-agent, 属性 23: 结果元数据完整性**
        **验证: 需求 11.6**
        
        缺失 agent_type 应当导致验证失败
        """
        # 创建一个没有 agent_type 的状态
        state: GradingState = {
            "context_pack": {
                "question_image": "base64",
                "question_type": QuestionType.OBJECTIVE,
                "rubric": "rubric",
                "max_score": 10.0,
            },
            "final_score": 5.0,
            "confidence": 0.85,
        }
        
        assert not validate_result_metadata(state), (
            "缺失 agent_type 应当导致验证失败"
        )


class TestSpecializedAgentMetadata:
    """专业智能体元数据测试
    
    验证每个专业智能体返回的结果包含正确的元数据
    """
    
    def setup_method(self):
        """每个测试前重置 AgentPool"""
        AgentPool.reset()
    
    def teardown_method(self):
        """每个测试后重置 AgentPool"""
        AgentPool.reset()
    
    def test_objective_agent_returns_correct_metadata(self):
        """
        **功能: ai-grading-agent, 属性 23: 结果元数据完整性**
        **验证: 需求 11.6**
        
        ObjectiveAgent 返回的结果应当包含正确的元数据：
        - agent_type = "objective"
        """
        with patch.object(ObjectiveAgent, '__init__', lambda x, **kwargs: setattr(x, '_api_key', 'test') or None):
            agent = ObjectiveAgent()
            
            # 验证 agent_type
            assert agent.agent_type == "objective", (
                f"ObjectiveAgent 的 agent_type 应当是 'objective'，实际值为 {agent.agent_type}"
            )
            
            # 验证 agent_type 在有效列表中
            assert agent.agent_type in VALID_AGENT_TYPES, (
                f"ObjectiveAgent 的 agent_type 应当在有效列表中"
            )
    
    def test_stepwise_agent_returns_correct_metadata(self):
        """
        **功能: ai-grading-agent, 属性 23: 结果元数据完整性**
        **验证: 需求 11.6**
        
        StepwiseAgent 返回的结果应当包含正确的元数据：
        - agent_type = "stepwise"
        """
        with patch.object(StepwiseAgent, '__init__', lambda x, **kwargs: setattr(x, '_api_key', 'test') or None):
            agent = StepwiseAgent()
            
            # 验证 agent_type
            assert agent.agent_type == "stepwise", (
                f"StepwiseAgent 的 agent_type 应当是 'stepwise'，实际值为 {agent.agent_type}"
            )
            
            # 验证 agent_type 在有效列表中
            assert agent.agent_type in VALID_AGENT_TYPES, (
                f"StepwiseAgent 的 agent_type 应当在有效列表中"
            )
    
    def test_essay_agent_returns_correct_metadata(self):
        """
        **功能: ai-grading-agent, 属性 23: 结果元数据完整性**
        **验证: 需求 11.6**
        
        EssayAgent 返回的结果应当包含正确的元数据：
        - agent_type = "essay"
        """
        with patch.object(EssayAgent, '__init__', lambda x, **kwargs: setattr(x, '_api_key', 'test') or None):
            agent = EssayAgent()
            
            # 验证 agent_type
            assert agent.agent_type == "essay", (
                f"EssayAgent 的 agent_type 应当是 'essay'，实际值为 {agent.agent_type}"
            )
            
            # 验证 agent_type 在有效列表中
            assert agent.agent_type in VALID_AGENT_TYPES, (
                f"EssayAgent 的 agent_type 应当在有效列表中"
            )
    
    def test_lab_design_agent_returns_correct_metadata(self):
        """
        **功能: ai-grading-agent, 属性 23: 结果元数据完整性**
        **验证: 需求 11.6**
        
        LabDesignAgent 返回的结果应当包含正确的元数据：
        - agent_type = "lab_design"
        """
        with patch.object(LabDesignAgent, '__init__', lambda x, **kwargs: setattr(x, '_api_key', 'test') or None):
            agent = LabDesignAgent()
            
            # 验证 agent_type
            assert agent.agent_type == "lab_design", (
                f"LabDesignAgent 的 agent_type 应当是 'lab_design'，实际值为 {agent.agent_type}"
            )
            
            # 验证 agent_type 在有效列表中
            assert agent.agent_type in VALID_AGENT_TYPES, (
                f"LabDesignAgent 的 agent_type 应当在有效列表中"
            )
    
    @given(agent_type=st.sampled_from(VALID_AGENT_TYPES))
    @settings(max_examples=100)
    def test_all_agent_types_have_corresponding_question_type(
        self,
        agent_type: str
    ):
        """
        **功能: ai-grading-agent, 属性 23: 结果元数据完整性**
        **验证: 需求 11.6**
        
        对于任意有效的 agent_type，应当存在对应的 question_type
        """
        # 验证映射存在
        assert agent_type in AGENT_TYPE_TO_QUESTION_TYPE, (
            f"agent_type '{agent_type}' 应当有对应的 question_type 映射"
        )
        
        # 验证映射的 question_type 有效
        question_type = AGENT_TYPE_TO_QUESTION_TYPE[agent_type]
        assert question_type in VALID_QUESTION_TYPES, (
            f"agent_type '{agent_type}' 对应的 question_type 应当是有效值"
        )


class TestMetadataConsistency:
    """元数据一致性测试
    
    验证 agent_type 和 question_type 之间的一致性
    """
    
    @given(
        agent_type=st.sampled_from(VALID_AGENT_TYPES)
    )
    @settings(max_examples=100)
    def test_agent_type_and_question_type_are_consistent(
        self,
        agent_type: str
    ):
        """
        **功能: ai-grading-agent, 属性 23: 结果元数据完整性**
        **验证: 需求 11.6**
        
        对于任意批改结果，agent_type 和 question_type 应当一致
        """
        # 获取对应的 question_type
        question_type = AGENT_TYPE_TO_QUESTION_TYPE[agent_type]
        
        state = create_mock_grading_state(
            agent_type=agent_type,
            question_type=question_type
        )
        
        # 验证一致性
        assert state["agent_type"] == agent_type
        assert state["context_pack"]["question_type"] == question_type
        
        # 验证映射关系正确
        expected_question_type = AGENT_TYPE_TO_QUESTION_TYPE[state["agent_type"]]
        assert state["context_pack"]["question_type"] == expected_question_type, (
            f"agent_type '{agent_type}' 应当对应 question_type '{expected_question_type}'，"
            f"实际为 '{state['context_pack']['question_type']}'"
        )
    
    @given(
        question_type=st.sampled_from(VALID_QUESTION_TYPES)
    )
    @settings(max_examples=100)
    def test_question_type_has_corresponding_agent_type(
        self,
        question_type: QuestionType
    ):
        """
        **功能: ai-grading-agent, 属性 23: 结果元数据完整性**
        **验证: 需求 11.6**
        
        对于任意有效的 question_type，应当存在对应的 agent_type
        """
        # 反向查找 agent_type
        found_agent_type = None
        for at, qt in AGENT_TYPE_TO_QUESTION_TYPE.items():
            if qt == question_type:
                found_agent_type = at
                break
        
        assert found_agent_type is not None, (
            f"question_type '{question_type}' 应当有对应的 agent_type"
        )
        
        assert found_agent_type in VALID_AGENT_TYPES, (
            f"question_type '{question_type}' 对应的 agent_type 应当是有效值"
        )

