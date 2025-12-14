"""二次评估触发条件属性测试

使用 Hypothesis 验证 SupervisorAgent 的二次评估触发逻辑

**功能: ai-grading-agent, 属性 20: 二次评估触发条件**
**验证: 需求 3.8**
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import patch, AsyncMock, MagicMock
import asyncio
from typing import Dict, Any

from src.models.enums import QuestionType
from src.models.state import ContextPack, GradingState
from src.agents.supervisor import SupervisorAgent, CONFIDENCE_THRESHOLD
from src.agents.pool import AgentPool
from src.agents.base import BaseGradingAgent


def run_async(coro):
    """运行异步协程的辅助函数"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def create_mock_supervisor() -> SupervisorAgent:
    """创建一个 mock 的 SupervisorAgent"""
    with patch('src.agents.supervisor.ChatGoogleGenerativeAI'):
        AgentPool.reset()
        supervisor = SupervisorAgent(api_key="test_key")
        return supervisor


def create_mock_grading_result(confidence: float, max_score: float = 10.0) -> GradingState:
    """创建一个 mock 的批改结果
    
    Args:
        confidence: 置信度分数
        max_score: 满分
        
    Returns:
        模拟的批改结果状态
    """
    return GradingState(
        context_pack={
            "question_image": "base64_image",
            "question_type": QuestionType.OBJECTIVE,
            "rubric": "评分细则",
            "max_score": max_score,
        },
        vision_analysis="视觉分析结果",
        rubric_mapping=[{"point": "得分点1", "score": 5.0}],
        initial_score=5.0,
        reasoning_trace=["推理步骤1", "推理步骤2"],
        critique_feedback=None,
        evidence_chain=[{
            "scoring_point": "得分点1",
            "image_region": [0, 0, 100, 100],
            "text_description": "描述",
            "reasoning": "理由",
            "rubric_reference": "评分条目",
            "points_awarded": 5.0,
        }],
        final_score=5.0,
        max_score=max_score,
        confidence=confidence,
        visual_annotations=[],
        student_feedback="反馈",
        agent_type="objective",
        revision_count=0,
        is_finalized=True,
        needs_secondary_review=False,
    )


class MockGradingAgent(BaseGradingAgent):
    """用于测试的 Mock 批改智能体"""
    
    def __init__(self, confidence: float):
        self._confidence = confidence
        self._grade_call_count = 0
    
    @property
    def agent_type(self) -> str:
        return "mock_agent"
    
    @property
    def supported_question_types(self):
        return [QuestionType.OBJECTIVE, QuestionType.STEPWISE, 
                QuestionType.ESSAY, QuestionType.LAB_DESIGN, QuestionType.UNKNOWN]
    
    async def grade(self, context_pack: ContextPack) -> GradingState:
        self._grade_call_count += 1
        return create_mock_grading_result(
            confidence=self._confidence,
            max_score=context_pack.get("max_score", 10.0)
        )


class TestSecondaryReviewTrigger:
    """二次评估触发条件属性测试
    
    **功能: ai-grading-agent, 属性 20: 二次评估触发条件**
    **验证: 需求 3.8**
    """
    
    def setup_method(self):
        """每个测试前重置 AgentPool"""
        AgentPool.reset()
    
    def teardown_method(self):
        """每个测试后重置 AgentPool"""
        AgentPool.reset()
    
    @given(confidence=st.floats(min_value=0.0, max_value=CONFIDENCE_THRESHOLD - 0.001, 
                                 allow_nan=False, allow_infinity=False))
    @settings(max_examples=100)
    def test_low_confidence_triggers_secondary_review(self, confidence: float):
        """
        **功能: ai-grading-agent, 属性 20: 二次评估触发条件**
        **验证: 需求 3.8**
        
        对于任意置信度 < 0.75 的批改结果，SupervisorAgent 应当触发二次评估
        """
        # 确保置信度严格小于阈值
        assume(confidence < CONFIDENCE_THRESHOLD)
        
        supervisor = create_mock_supervisor()
        
        # 创建一个返回低置信度结果的 mock 智能体
        mock_agent = MockGradingAgent(confidence=confidence)
        
        # 注册 mock 智能体到 AgentPool
        supervisor.agent_pool.register_agent(mock_agent)
        
        # 创建上下文包
        context_pack: ContextPack = {
            "question_image": "base64_image",
            "question_type": QuestionType.OBJECTIVE,
            "rubric": "评分细则",
            "max_score": 10.0,
        }
        
        # 执行批改
        result = run_async(supervisor.spawn_and_grade(context_pack))
        
        # 验证：低置信度应该触发二次评估（智能体被调用两次）
        assert mock_agent._grade_call_count >= 2, (
            f"置信度 {confidence:.4f} < {CONFIDENCE_THRESHOLD} 时应触发二次评估，"
            f"但智能体只被调用了 {mock_agent._grade_call_count} 次"
        )
    
    @given(confidence=st.floats(min_value=CONFIDENCE_THRESHOLD, max_value=1.0,
                                 allow_nan=False, allow_infinity=False))
    @settings(max_examples=100)
    def test_high_confidence_skips_secondary_review(self, confidence: float):
        """
        **功能: ai-grading-agent, 属性 20: 二次评估触发条件**
        **验证: 需求 3.8**
        
        对于任意置信度 >= 0.75 的批改结果，SupervisorAgent 不应触发二次评估
        """
        # 确保置信度大于等于阈值
        assume(confidence >= CONFIDENCE_THRESHOLD)
        
        supervisor = create_mock_supervisor()
        
        # 创建一个返回高置信度结果的 mock 智能体
        mock_agent = MockGradingAgent(confidence=confidence)
        
        # 注册 mock 智能体到 AgentPool
        supervisor.agent_pool.register_agent(mock_agent)
        
        # 创建上下文包
        context_pack: ContextPack = {
            "question_image": "base64_image",
            "question_type": QuestionType.OBJECTIVE,
            "rubric": "评分细则",
            "max_score": 10.0,
        }
        
        # 执行批改
        result = run_async(supervisor.spawn_and_grade(context_pack))
        
        # 验证：高置信度不应触发二次评估（智能体只被调用一次）
        assert mock_agent._grade_call_count == 1, (
            f"置信度 {confidence:.4f} >= {CONFIDENCE_THRESHOLD} 时不应触发二次评估，"
            f"但智能体被调用了 {mock_agent._grade_call_count} 次"
        )
    
    def test_threshold_boundary_no_secondary_review(self):
        """
        **功能: ai-grading-agent, 属性 20: 二次评估触发条件**
        **验证: 需求 3.8**
        
        当置信度恰好等于阈值 0.75 时，不应触发二次评估
        """
        supervisor = create_mock_supervisor()
        
        # 创建一个返回恰好等于阈值置信度的 mock 智能体
        mock_agent = MockGradingAgent(confidence=CONFIDENCE_THRESHOLD)
        
        # 注册 mock 智能体到 AgentPool
        supervisor.agent_pool.register_agent(mock_agent)
        
        # 创建上下文包
        context_pack: ContextPack = {
            "question_image": "base64_image",
            "question_type": QuestionType.OBJECTIVE,
            "rubric": "评分细则",
            "max_score": 10.0,
        }
        
        # 执行批改
        result = run_async(supervisor.spawn_and_grade(context_pack))
        
        # 验证：恰好等于阈值时不应触发二次评估
        assert mock_agent._grade_call_count == 1, (
            f"置信度恰好等于阈值 {CONFIDENCE_THRESHOLD} 时不应触发二次评估，"
            f"但智能体被调用了 {mock_agent._grade_call_count} 次"
        )
    
    def test_threshold_boundary_just_below_triggers(self):
        """
        **功能: ai-grading-agent, 属性 20: 二次评估触发条件**
        **验证: 需求 3.8**
        
        当置信度略低于阈值时，应触发二次评估
        """
        supervisor = create_mock_supervisor()
        
        # 创建一个返回略低于阈值置信度的 mock 智能体
        just_below_threshold = CONFIDENCE_THRESHOLD - 0.0001
        mock_agent = MockGradingAgent(confidence=just_below_threshold)
        
        # 注册 mock 智能体到 AgentPool
        supervisor.agent_pool.register_agent(mock_agent)
        
        # 创建上下文包
        context_pack: ContextPack = {
            "question_image": "base64_image",
            "question_type": QuestionType.OBJECTIVE,
            "rubric": "评分细则",
            "max_score": 10.0,
        }
        
        # 执行批改
        result = run_async(supervisor.spawn_and_grade(context_pack))
        
        # 验证：略低于阈值时应触发二次评估
        assert mock_agent._grade_call_count >= 2, (
            f"置信度 {just_below_threshold} 略低于阈值 {CONFIDENCE_THRESHOLD} 时应触发二次评估，"
            f"但智能体只被调用了 {mock_agent._grade_call_count} 次"
        )


class TestSecondaryReviewBehavior:
    """二次评估行为属性测试
    
    **功能: ai-grading-agent, 属性 20: 二次评估触发条件**
    **验证: 需求 3.8**
    """
    
    def setup_method(self):
        """每个测试前重置 AgentPool"""
        AgentPool.reset()
    
    def teardown_method(self):
        """每个测试后重置 AgentPool"""
        AgentPool.reset()
    
    @given(
        initial_confidence=st.floats(min_value=0.0, max_value=CONFIDENCE_THRESHOLD - 0.001,
                                      allow_nan=False, allow_infinity=False),
        question_type=st.sampled_from([QuestionType.OBJECTIVE, QuestionType.STEPWISE,
                                        QuestionType.ESSAY, QuestionType.LAB_DESIGN])
    )
    @settings(max_examples=100)
    def test_secondary_review_receives_previous_result(
        self, initial_confidence: float, question_type: QuestionType
    ):
        """
        **功能: ai-grading-agent, 属性 20: 二次评估触发条件**
        **验证: 需求 3.8**
        
        当触发二次评估时，二次评估应接收到初次批改的结果作为参考
        """
        assume(initial_confidence < CONFIDENCE_THRESHOLD)
        
        supervisor = create_mock_supervisor()
        
        # 创建一个记录调用参数的 mock 智能体
        call_args = []
        
        class RecordingAgent(BaseGradingAgent):
            @property
            def agent_type(self) -> str:
                return "recording_agent"
            
            @property
            def supported_question_types(self):
                return [QuestionType.OBJECTIVE, QuestionType.STEPWISE,
                        QuestionType.ESSAY, QuestionType.LAB_DESIGN, QuestionType.UNKNOWN]
            
            async def grade(self, context_pack: ContextPack) -> GradingState:
                call_args.append(dict(context_pack))
                return create_mock_grading_result(
                    confidence=initial_confidence,
                    max_score=context_pack.get("max_score", 10.0)
                )
        
        recording_agent = RecordingAgent()
        supervisor.agent_pool.register_agent(recording_agent)
        
        # 创建上下文包
        context_pack: ContextPack = {
            "question_image": "base64_image",
            "question_type": question_type,
            "rubric": "评分细则",
            "max_score": 10.0,
        }
        
        # 执行批改
        result = run_async(supervisor.spawn_and_grade(context_pack))
        
        # 验证：二次评估时应该有 previous_result
        assert len(call_args) >= 2, "应该至少调用两次（初次 + 二次评估）"
        
        # 第二次调用应该包含 previous_result
        second_call = call_args[1]
        assert "previous_result" in second_call, (
            "二次评估的上下文包应包含 previous_result"
        )
        
        previous_result = second_call["previous_result"]
        assert "score" in previous_result, "previous_result 应包含 score"
        assert "confidence" in previous_result, "previous_result 应包含 confidence"
    
    @given(
        initial_confidence=st.floats(min_value=0.0, max_value=CONFIDENCE_THRESHOLD - 0.001,
                                      allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_secondary_review_merges_reasoning_trace(self, initial_confidence: float):
        """
        **功能: ai-grading-agent, 属性 20: 二次评估触发条件**
        **验证: 需求 3.8**
        
        二次评估后，推理轨迹应包含初次和二次评估的内容
        """
        assume(initial_confidence < CONFIDENCE_THRESHOLD)
        
        supervisor = create_mock_supervisor()
        
        # 创建一个返回低置信度结果的 mock 智能体
        mock_agent = MockGradingAgent(confidence=initial_confidence)
        supervisor.agent_pool.register_agent(mock_agent)
        
        # 创建上下文包
        context_pack: ContextPack = {
            "question_image": "base64_image",
            "question_type": QuestionType.OBJECTIVE,
            "rubric": "评分细则",
            "max_score": 10.0,
        }
        
        # 执行批改
        result = run_async(supervisor.spawn_and_grade(context_pack))
        
        # 验证：推理轨迹应包含二次评估标记
        reasoning_trace = result.get("reasoning_trace", [])
        assert "--- 二次评估 ---" in reasoning_trace, (
            "二次评估后的推理轨迹应包含 '--- 二次评估 ---' 标记"
        )


class TestConfidenceThresholdConstant:
    """置信度阈值常量测试
    
    **功能: ai-grading-agent, 属性 20: 二次评估触发条件**
    **验证: 需求 3.8**
    """
    
    def test_confidence_threshold_is_0_75(self):
        """
        **功能: ai-grading-agent, 属性 20: 二次评估触发条件**
        **验证: 需求 3.8**
        
        验证置信度阈值常量为 0.75（符合需求 3.8）
        """
        assert CONFIDENCE_THRESHOLD == 0.75, (
            f"置信度阈值应为 0.75（需求 3.8），但实际为 {CONFIDENCE_THRESHOLD}"
        )
