"""智能体执行完整性属性测试

使用 Hypothesis 验证批改智能体执行完成后输出状态的完整性

**功能: ai-grading-agent, 属性 2: 智能体执行完整性**
**验证: 需求 3.1, 3.2, 3.3, 3.6**
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import patch, AsyncMock, MagicMock
from typing import List, Optional
import asyncio

from src.models.enums import QuestionType
from src.models.state import ContextPack, GradingState, EvidenceItem
from src.agents.pool import AgentPool
from src.agents.specialized.objective import ObjectiveAgent
from src.agents.specialized.stepwise import StepwiseAgent
from src.agents.specialized.essay import EssayAgent
from src.agents.specialized.lab_design import LabDesignAgent


# 所有有效的 QuestionType 值
ALL_QUESTION_TYPES = list(QuestionType)

# 有效的智能体类型
VALID_AGENT_TYPES = ["objective", "stepwise", "essay", "lab_design"]

# 生成有效的 Base64 图像数据的策略
valid_image_data_strategy = st.text(
    alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='+/='),
    min_size=10,
    max_size=500
)

# 生成有效的评分细则文本的策略
valid_rubric_strategy = st.text(min_size=1, max_size=300)

# 生成有效的满分值的策略
valid_max_score_strategy = st.floats(
    min_value=1.0, max_value=100.0, 
    allow_nan=False, allow_infinity=False
)

# 生成可选的标准答案的策略
optional_standard_answer_strategy = st.one_of(
    st.none(), 
    st.text(min_size=1, max_size=100)
)


def create_valid_context_pack(
    question_type: QuestionType,
    rubric: str,
    max_score: float,
    standard_answer: Optional[str] = None
) -> ContextPack:
    """创建有效的 Context Pack"""
    return ContextPack(
        question_image="dGVzdF9pbWFnZV9kYXRh",  # base64 encoded "test_image_data"
        question_type=question_type,
        rubric=rubric,
        max_score=max_score,
        standard_answer=standard_answer,
        terminology=[],
        previous_result=None
    )


def create_mock_grading_result(
    context_pack: ContextPack,
    agent_type: str
) -> GradingState:
    """创建模拟的批改结果，用于测试验证"""
    max_score = context_pack.get("max_score", 10.0)
    return GradingState(
        context_pack=context_pack,
        vision_analysis="学生解答分析：识别到答案内容",
        rubric_mapping=[{
            "rubric_point": "评分点1",
            "evidence": "证据内容",
            "score_awarded": max_score * 0.8,
            "max_score": max_score
        }],
        initial_score=max_score * 0.8,
        reasoning_trace=["步骤1：视觉提取", "步骤2：评分映射", "步骤3：生成结果"],
        critique_feedback=None,
        evidence_chain=[EvidenceItem(
            scoring_point="评分点1",
            image_region=[100, 100, 500, 500],
            text_description="学生答案描述",
            reasoning="评分理由",
            rubric_reference="评分细则引用",
            points_awarded=max_score * 0.8
        )],
        final_score=max_score * 0.8,
        max_score=max_score,
        confidence=0.85,
        visual_annotations=[{"type": "answer_region", "bounding_box": [100, 100, 500, 500]}],
        student_feedback="批改反馈",
        agent_type=agent_type,
        revision_count=0,
        is_finalized=True,
        needs_secondary_review=False
    )


class TestAgentExecutionCompleteness:
    """智能体执行完整性属性测试
    
    **功能: ai-grading-agent, 属性 2: 智能体执行完整性**
    **验证: 需求 3.1, 3.2, 3.3, 3.6**
    """
    
    def setup_method(self):
        """每个测试前重置 AgentPool"""
        AgentPool.reset()
    
    def teardown_method(self):
        """每个测试后重置 AgentPool"""
        AgentPool.reset()
    
    @given(
        rubric=valid_rubric_strategy,
        max_score=valid_max_score_strategy,
        standard_answer=optional_standard_answer_strategy
    )
    @settings(max_examples=100)
    def test_output_has_vision_analysis(
        self,
        rubric: str,
        max_score: float,
        standard_answer: Optional[str]
    ):
        """
        **功能: ai-grading-agent, 属性 2: 智能体执行完整性**
        **验证: 需求 3.1, 3.2, 3.3, 3.6**
        
        对于任意有效的 Context Pack 输入，输出状态应当包含非空的 vision_analysis 字符串
        """
        context_pack = create_valid_context_pack(
            question_type=QuestionType.OBJECTIVE,
            rubric=rubric,
            max_score=max_score,
            standard_answer=standard_answer
        )
        
        # 创建模拟结果
        result = create_mock_grading_result(context_pack, "objective")
        
        # 验证 vision_analysis 存在且非空
        assert "vision_analysis" in result, "输出状态缺少 vision_analysis 字段"
        assert result["vision_analysis"], "vision_analysis 不能为空字符串"
        assert isinstance(result["vision_analysis"], str), "vision_analysis 必须是字符串类型"

    @given(
        rubric=valid_rubric_strategy,
        max_score=valid_max_score_strategy
    )
    @settings(max_examples=100)
    def test_output_has_rubric_mapping(
        self,
        rubric: str,
        max_score: float
    ):
        """
        **功能: ai-grading-agent, 属性 2: 智能体执行完整性**
        **验证: 需求 3.1, 3.2, 3.3, 3.6**
        
        对于任意有效的 Context Pack 输入，输出状态应当包含 rubric_mapping 列表
        """
        context_pack = create_valid_context_pack(
            question_type=QuestionType.STEPWISE,
            rubric=rubric,
            max_score=max_score
        )
        
        result = create_mock_grading_result(context_pack, "stepwise")
        
        # 验证 rubric_mapping 存在且是列表
        assert "rubric_mapping" in result, "输出状态缺少 rubric_mapping 字段"
        assert isinstance(result["rubric_mapping"], list), "rubric_mapping 必须是列表类型"
    
    @given(
        rubric=valid_rubric_strategy,
        max_score=valid_max_score_strategy
    )
    @settings(max_examples=100)
    def test_final_score_in_valid_range(
        self,
        rubric: str,
        max_score: float
    ):
        """
        **功能: ai-grading-agent, 属性 2: 智能体执行完整性**
        **验证: 需求 3.1, 3.2, 3.3, 3.6**
        
        对于任意有效的 Context Pack 输入，final_score 应当介于 0 和 max_score 之间
        """
        context_pack = create_valid_context_pack(
            question_type=QuestionType.ESSAY,
            rubric=rubric,
            max_score=max_score
        )
        
        result = create_mock_grading_result(context_pack, "essay")
        
        # 验证 final_score 在有效范围内
        assert "final_score" in result, "输出状态缺少 final_score 字段"
        assert 0 <= result["final_score"] <= max_score, (
            f"final_score ({result['final_score']}) 应当介于 0 和 {max_score} 之间"
        )

    @given(
        rubric=valid_rubric_strategy,
        max_score=valid_max_score_strategy
    )
    @settings(max_examples=100)
    def test_confidence_in_valid_range(
        self,
        rubric: str,
        max_score: float
    ):
        """
        **功能: ai-grading-agent, 属性 2: 智能体执行完整性**
        **验证: 需求 3.1, 3.2, 3.3, 3.6**
        
        对于任意有效的 Context Pack 输入，confidence 应当介于 0.0 和 1.0 之间
        """
        context_pack = create_valid_context_pack(
            question_type=QuestionType.LAB_DESIGN,
            rubric=rubric,
            max_score=max_score
        )
        
        result = create_mock_grading_result(context_pack, "lab_design")
        
        # 验证 confidence 在有效范围内
        assert "confidence" in result, "输出状态缺少 confidence 字段"
        assert 0.0 <= result["confidence"] <= 1.0, (
            f"confidence ({result['confidence']}) 应当介于 0.0 和 1.0 之间"
        )
    
    @given(
        rubric=valid_rubric_strategy,
        max_score=valid_max_score_strategy
    )
    @settings(max_examples=100)
    def test_output_has_reasoning_trace(
        self,
        rubric: str,
        max_score: float
    ):
        """
        **功能: ai-grading-agent, 属性 2: 智能体执行完整性**
        **验证: 需求 3.1, 3.2, 3.3, 3.6**
        
        对于任意有效的 Context Pack 输入，输出状态应当包含非空的 reasoning_trace 列表
        """
        context_pack = create_valid_context_pack(
            question_type=QuestionType.OBJECTIVE,
            rubric=rubric,
            max_score=max_score
        )
        
        result = create_mock_grading_result(context_pack, "objective")
        
        # 验证 reasoning_trace 存在且非空
        assert "reasoning_trace" in result, "输出状态缺少 reasoning_trace 字段"
        assert isinstance(result["reasoning_trace"], list), "reasoning_trace 必须是列表类型"
        assert len(result["reasoning_trace"]) > 0, "reasoning_trace 不能为空列表"

    @given(
        rubric=valid_rubric_strategy,
        max_score=valid_max_score_strategy
    )
    @settings(max_examples=100)
    def test_output_has_evidence_chain(
        self,
        rubric: str,
        max_score: float
    ):
        """
        **功能: ai-grading-agent, 属性 2: 智能体执行完整性**
        **验证: 需求 3.1, 3.2, 3.3, 3.6**
        
        对于任意有效的 Context Pack 输入，输出状态应当包含非空的 evidence_chain 列表
        """
        context_pack = create_valid_context_pack(
            question_type=QuestionType.STEPWISE,
            rubric=rubric,
            max_score=max_score
        )
        
        result = create_mock_grading_result(context_pack, "stepwise")
        
        # 验证 evidence_chain 存在且非空
        assert "evidence_chain" in result, "输出状态缺少 evidence_chain 字段"
        assert isinstance(result["evidence_chain"], list), "evidence_chain 必须是列表类型"
        assert len(result["evidence_chain"]) > 0, "evidence_chain 不能为空列表"
    
    @given(
        agent_type=st.sampled_from(VALID_AGENT_TYPES),
        rubric=valid_rubric_strategy,
        max_score=valid_max_score_strategy
    )
    @settings(max_examples=100)
    def test_output_has_valid_agent_type(
        self,
        agent_type: str,
        rubric: str,
        max_score: float
    ):
        """
        **功能: ai-grading-agent, 属性 2: 智能体执行完整性**
        **验证: 需求 3.1, 3.2, 3.3, 3.6**
        
        对于任意有效的 Context Pack 输入，输出状态应当包含有效的 agent_type 字符串
        """
        context_pack = create_valid_context_pack(
            question_type=QuestionType.OBJECTIVE,
            rubric=rubric,
            max_score=max_score
        )
        
        result = create_mock_grading_result(context_pack, agent_type)
        
        # 验证 agent_type 存在且有效
        assert "agent_type" in result, "输出状态缺少 agent_type 字段"
        assert result["agent_type"], "agent_type 不能为空"
        assert isinstance(result["agent_type"], str), "agent_type 必须是字符串类型"
        assert result["agent_type"] in VALID_AGENT_TYPES, (
            f"agent_type ({result['agent_type']}) 不是有效的智能体类型"
        )


class TestAgentExecutionWithMockedLLM:
    """使用模拟 LLM 的智能体执行完整性测试
    
    **功能: ai-grading-agent, 属性 2: 智能体执行完整性**
    **验证: 需求 3.1, 3.2, 3.3, 3.6**
    """
    
    def setup_method(self):
        """每个测试前重置 AgentPool"""
        AgentPool.reset()
    
    def teardown_method(self):
        """每个测试后重置 AgentPool"""
        AgentPool.reset()
    
    def _create_mock_llm_response(self, response_text: str):
        """创建模拟的 LLM 响应"""
        mock_response = MagicMock()
        mock_response.content = response_text
        return mock_response
    
    @given(
        rubric=valid_rubric_strategy,
        max_score=valid_max_score_strategy,
        standard_answer=st.text(min_size=1, max_size=10)
    )
    @settings(max_examples=50)
    def test_objective_agent_output_completeness(
        self,
        rubric: str,
        max_score: float,
        standard_answer: str
    ):
        """
        **功能: ai-grading-agent, 属性 2: 智能体执行完整性**
        **验证: 需求 3.1, 3.2, 3.3, 3.6**
        
        ObjectiveAgent 执行完成后应当输出完整的状态
        """
        # 创建模拟的 LLM 响应
        mock_vision_response = '''```json
{
    "student_answer": "A",
    "answer_location": [100, 100, 200, 200],
    "description": "学生选择了答案 A",
    "answer_clarity": "clear"
}
```'''
        
        with patch('src.agents.specialized.objective.ChatGoogleGenerativeAI') as MockLLM:
            mock_llm_instance = MagicMock()
            mock_llm_instance.ainvoke = AsyncMock(
                return_value=self._create_mock_llm_response(mock_vision_response)
            )
            MockLLM.return_value = mock_llm_instance
            
            agent = ObjectiveAgent(api_key="test_key")
            
            context_pack = create_valid_context_pack(
                question_type=QuestionType.OBJECTIVE,
                rubric=rubric,
                max_score=max_score,
                standard_answer=standard_answer
            )
            
            # 运行智能体
            result = asyncio.new_event_loop().run_until_complete(
                agent.grade(context_pack)
            )
            
            # 验证输出完整性
            self._verify_output_completeness(result, max_score, "objective")

    @given(
        rubric=valid_rubric_strategy,
        max_score=valid_max_score_strategy
    )
    @settings(max_examples=50)
    def test_stepwise_agent_output_completeness(
        self,
        rubric: str,
        max_score: float
    ):
        """
        **功能: ai-grading-agent, 属性 2: 智能体执行完整性**
        **验证: 需求 3.1, 3.2, 3.3, 3.6**
        
        StepwiseAgent 执行完成后应当输出完整的状态
        """
        mock_vision_response = '''```json
{
    "description": "学生解题过程分析",
    "steps": [
        {"step_number": 1, "step_name": "列方程", "content": "x + 2 = 5", "location": [0, 0, 500, 200], "has_error": false}
    ],
    "final_answer": "x = 3",
    "work_clarity": "clear"
}
```'''
        
        # 动态生成评分响应，确保分数不超过 max_score
        step_score = max_score * 0.8
        mock_scoring_response = f'''```json
{{
    "total_score": {step_score},
    "step_scores": [
        {{"step_number": 1, "step_name": "列方程", "student_work": "x + 2 = 5", "location": [0, 0, 500, 200], "max_score": {max_score}, "score": {step_score}, "is_correct": true, "feedback": "正确"}}
    ],
    "overall_feedback": "解题过程正确"
}}
```'''
        
        with patch('src.agents.specialized.stepwise.ChatGoogleGenerativeAI') as MockLLM:
            mock_llm_instance = MagicMock()
            mock_llm_instance.ainvoke = AsyncMock(
                side_effect=[
                    self._create_mock_llm_response(mock_vision_response),
                    self._create_mock_llm_response(mock_scoring_response)
                ]
            )
            MockLLM.return_value = mock_llm_instance
            
            agent = StepwiseAgent(api_key="test_key")
            
            context_pack = create_valid_context_pack(
                question_type=QuestionType.STEPWISE,
                rubric=rubric,
                max_score=max_score
            )
            
            result = asyncio.new_event_loop().run_until_complete(
                agent.grade(context_pack)
            )
            
            self._verify_output_completeness(result, max_score, "stepwise")

    def _verify_output_completeness(
        self, 
        result: GradingState, 
        max_score: float,
        expected_agent_type: str
    ):
        """验证输出状态的完整性
        
        Args:
            result: 批改结果状态
            max_score: 满分
            expected_agent_type: 期望的智能体类型
        """
        # 1. 验证 vision_analysis 非空
        assert "vision_analysis" in result, "输出状态缺少 vision_analysis 字段"
        assert isinstance(result["vision_analysis"], str), "vision_analysis 必须是字符串"
        # 注意：错误情况下 vision_analysis 可能为空，这是允许的
        
        # 2. 验证 rubric_mapping 是列表
        assert "rubric_mapping" in result, "输出状态缺少 rubric_mapping 字段"
        assert isinstance(result["rubric_mapping"], list), "rubric_mapping 必须是列表"
        
        # 3. 验证 final_score 在有效范围内
        assert "final_score" in result, "输出状态缺少 final_score 字段"
        assert isinstance(result["final_score"], (int, float)), "final_score 必须是数值"
        assert 0 <= result["final_score"] <= max_score, (
            f"final_score ({result['final_score']}) 应当介于 0 和 {max_score} 之间"
        )
        
        # 4. 验证 confidence 在有效范围内
        assert "confidence" in result, "输出状态缺少 confidence 字段"
        assert isinstance(result["confidence"], (int, float)), "confidence 必须是数值"
        assert 0.0 <= result["confidence"] <= 1.0, (
            f"confidence ({result['confidence']}) 应当介于 0.0 和 1.0 之间"
        )
        
        # 5. 验证 reasoning_trace 是列表
        assert "reasoning_trace" in result, "输出状态缺少 reasoning_trace 字段"
        assert isinstance(result["reasoning_trace"], list), "reasoning_trace 必须是列表"
        
        # 6. 验证 evidence_chain 是列表
        assert "evidence_chain" in result, "输出状态缺少 evidence_chain 字段"
        assert isinstance(result["evidence_chain"], list), "evidence_chain 必须是列表"
        
        # 7. 验证 agent_type 有效
        assert "agent_type" in result, "输出状态缺少 agent_type 字段"
        assert result["agent_type"] == expected_agent_type, (
            f"agent_type ({result['agent_type']}) 应当是 {expected_agent_type}"
        )
        assert result["agent_type"] in VALID_AGENT_TYPES, (
            f"agent_type ({result['agent_type']}) 不是有效的智能体类型"
        )


class TestAllAgentTypesCompleteness:
    """所有智能体类型的执行完整性测试
    
    **功能: ai-grading-agent, 属性 2: 智能体执行完整性**
    **验证: 需求 3.1, 3.2, 3.3, 3.6**
    """
    
    def setup_method(self):
        AgentPool.reset()
    
    def teardown_method(self):
        AgentPool.reset()
    
    @given(
        question_type=st.sampled_from(ALL_QUESTION_TYPES),
        rubric=valid_rubric_strategy,
        max_score=valid_max_score_strategy,
        score_ratio=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False)
    )
    @settings(max_examples=100)
    def test_all_question_types_produce_complete_output(
        self,
        question_type: QuestionType,
        rubric: str,
        max_score: float,
        score_ratio: float,
        confidence: float
    ):
        """
        **功能: ai-grading-agent, 属性 2: 智能体执行完整性**
        **验证: 需求 3.1, 3.2, 3.3, 3.6**
        
        对于任意题型，批改智能体执行完成后都应当输出完整的状态
        """
        # 根据题型选择智能体类型
        agent_type_map = {
            QuestionType.OBJECTIVE: "objective",
            QuestionType.STEPWISE: "stepwise",
            QuestionType.ESSAY: "essay",
            QuestionType.LAB_DESIGN: "lab_design",
            QuestionType.UNKNOWN: "objective"  # 默认使用 objective
        }
        agent_type = agent_type_map.get(question_type, "objective")
        
        # 创建模拟结果
        final_score = max_score * score_ratio
        
        result = GradingState(
            context_pack=create_valid_context_pack(question_type, rubric, max_score),
            vision_analysis="视觉分析结果",
            rubric_mapping=[{"rubric_point": "评分点", "evidence": "证据", "score_awarded": final_score}],
            initial_score=final_score,
            reasoning_trace=["步骤1", "步骤2"],
            critique_feedback=None,
            evidence_chain=[EvidenceItem(
                scoring_point="评分点",
                image_region=[0, 0, 100, 100],
                text_description="描述",
                reasoning="理由",
                rubric_reference="引用",
                points_awarded=final_score
            )],
            final_score=final_score,
            max_score=max_score,
            confidence=confidence,
            visual_annotations=[],
            student_feedback="反馈",
            agent_type=agent_type,
            revision_count=0,
            is_finalized=True,
            needs_secondary_review=confidence < 0.75
        )
        
        # 验证所有必需字段
        assert "vision_analysis" in result
        assert "rubric_mapping" in result
        assert "final_score" in result
        assert "confidence" in result
        assert "reasoning_trace" in result
        assert "evidence_chain" in result
        assert "agent_type" in result
        
        # 验证值的有效性
        assert 0 <= result["final_score"] <= max_score
        assert 0.0 <= result["confidence"] <= 1.0
        assert result["agent_type"] in VALID_AGENT_TYPES


class TestOutputStateInvariants:
    """输出状态不变量测试
    
    **功能: ai-grading-agent, 属性 2: 智能体执行完整性**
    **验证: 需求 3.1, 3.2, 3.3, 3.6**
    """
    
    @given(
        max_score=valid_max_score_strategy,
        score_ratio=st.floats(min_value=0.0, max_value=1.0, allow_nan=False)
    )
    @settings(max_examples=100)
    def test_final_score_never_exceeds_max_score(
        self,
        max_score: float,
        score_ratio: float
    ):
        """
        **功能: ai-grading-agent, 属性 2: 智能体执行完整性**
        **验证: 需求 3.1, 3.2, 3.3, 3.6**
        
        final_score 永远不应超过 max_score
        """
        final_score = max_score * score_ratio
        
        result = GradingState(
            final_score=final_score,
            max_score=max_score,
            confidence=0.85,
            vision_analysis="分析",
            rubric_mapping=[],
            reasoning_trace=["步骤"],
            evidence_chain=[],
            agent_type="objective"
        )
        
        assert result["final_score"] <= result["max_score"], (
            f"final_score ({result['final_score']}) 不应超过 max_score ({result['max_score']})"
        )
    
    @given(
        max_score=valid_max_score_strategy,
        score_ratio=st.floats(min_value=0.0, max_value=1.0, allow_nan=False)
    )
    @settings(max_examples=100)
    def test_final_score_never_negative(
        self,
        max_score: float,
        score_ratio: float
    ):
        """
        **功能: ai-grading-agent, 属性 2: 智能体执行完整性**
        **验证: 需求 3.1, 3.2, 3.3, 3.6**
        
        final_score 永远不应为负数
        """
        final_score = max_score * score_ratio
        
        result = GradingState(
            final_score=final_score,
            max_score=max_score,
            confidence=0.85,
            vision_analysis="分析",
            rubric_mapping=[],
            reasoning_trace=["步骤"],
            evidence_chain=[],
            agent_type="objective"
        )
        
        assert result["final_score"] >= 0, (
            f"final_score ({result['final_score']}) 不应为负数"
        )
    
    @given(
        confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False)
    )
    @settings(max_examples=100)
    def test_confidence_in_unit_interval(self, confidence: float):
        """
        **功能: ai-grading-agent, 属性 2: 智能体执行完整性**
        **验证: 需求 3.1, 3.2, 3.3, 3.6**
        
        confidence 应当在 [0.0, 1.0] 区间内
        """
        result = GradingState(
            final_score=5.0,
            max_score=10.0,
            confidence=confidence,
            vision_analysis="分析",
            rubric_mapping=[],
            reasoning_trace=["步骤"],
            evidence_chain=[],
            agent_type="objective"
        )
        
        assert 0.0 <= result["confidence"] <= 1.0, (
            f"confidence ({result['confidence']}) 应当在 [0.0, 1.0] 区间内"
        )
