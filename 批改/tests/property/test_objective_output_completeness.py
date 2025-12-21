"""属性测试：客观题评分输出完整性

**Feature: self-evolving-grading, Property 15: 客观题评分输出完整性**
**Validates: Requirements 7.1, 7.2, 7.5**

验证对于任意客观题评分，输出应包含：score、confidence、reasoning_trace
"""

import pytest
import asyncio
from hypothesis import given, strategies as st, settings, HealthCheck
from unittest.mock import AsyncMock, MagicMock, patch
import base64

from src.agents.specialized.objective import ObjectiveAgent
from src.models.state import ContextPack
from src.models.enums import QuestionType


# 生成策略
@st.composite
def context_pack_strategy(draw):
    """生成客观题上下文包"""
    # 生成简单的图像数据
    image_data = b"fake_image_data"
    question_image = base64.b64encode(image_data).decode('utf-8')
    
    # 生成评分细则
    rubric = draw(st.text(min_size=10, max_size=200))
    
    # 生成满分
    max_score = draw(st.floats(min_value=1.0, max_value=10.0))
    
    # 生成标准答案
    standard_answer = draw(st.sampled_from(["A", "B", "C", "D", "TRUE", "FALSE"]))
    
    return ContextPack(
        question_image=question_image,
        question_type=QuestionType.OBJECTIVE,
        rubric=rubric,
        max_score=max_score,
        standard_answer=standard_answer,
        terminology=[],
        previous_result=None
    )


@st.composite
def vision_result_strategy(draw):
    """生成视觉提取结果"""
    student_answer = draw(st.sampled_from(["A", "B", "C", "D", "TRUE", "FALSE", ""]))
    answer_clarity = draw(st.sampled_from(["clear", "unclear", "not_found"]))
    
    return {
        "student_answer": student_answer,
        "answer_location": [100, 100, 200, 200],
        "description": f"学生选择了答案 {student_answer}",
        "answer_clarity": answer_clarity
    }


@given(
    context_pack=context_pack_strategy(),
    vision_result=vision_result_strategy()
)
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_objective_output_completeness(context_pack, vision_result):
    """
    **Feature: self-evolving-grading, Property 15: 客观题评分输出完整性**
    **Validates: Requirements 7.1, 7.2, 7.5**
    
    属性：对于任意客观题评分，输出应包含：
    1. final_score（得分）
    2. confidence（置信度，范围 0.0-1.0）
    3. reasoning_trace（推理轨迹，非空列表）
    4. rubric_mapping 中包含 scoring_rationale（评分依据）
    """
    async def run_test():
        # 创建 ObjectiveAgent
        agent = ObjectiveAgent(api_key="fake_api_key")
        
        # Mock _extract_student_answer 方法而不是 llm.ainvoke
        async def mock_extract(*args, **kwargs):
            return vision_result
        
        with patch.object(agent, '_extract_student_answer', side_effect=mock_extract):
            # 执行批改
            result = await agent.grade(context_pack)
            
            # 验证输出完整性
            
            # 1. 必须包含 final_score
            assert "final_score" in result, "输出必须包含 final_score"
            assert isinstance(result["final_score"], (int, float)), "final_score 必须是数值"
            assert 0 <= result["final_score"] <= context_pack["max_score"], \
                f"final_score 必须在 0 到 {context_pack['max_score']} 之间"
            
            # 2. 必须包含 confidence，且在 0.0-1.0 范围内
            assert "confidence" in result, "输出必须包含 confidence"
            assert isinstance(result["confidence"], (int, float)), "confidence 必须是数值"
            assert 0.0 <= result["confidence"] <= 1.0, \
                f"confidence 必须在 0.0-1.0 之间，实际值: {result['confidence']}"
            
            # 3. 必须包含 reasoning_trace，且为非空列表
            assert "reasoning_trace" in result, "输出必须包含 reasoning_trace"
            assert isinstance(result["reasoning_trace"], list), "reasoning_trace 必须是列表"
            assert len(result["reasoning_trace"]) > 0, "reasoning_trace 不能为空"
            
            # 验证 reasoning_trace 包含关键步骤
            trace_text = " ".join(result["reasoning_trace"])
            assert "视觉提取" in trace_text or "答案比对" in trace_text, \
                "reasoning_trace 应包含关键评分步骤"
            
            # 4. rubric_mapping 必须包含评分依据
            assert "rubric_mapping" in result, "输出必须包含 rubric_mapping"
            assert isinstance(result["rubric_mapping"], list), "rubric_mapping 必须是列表"
            assert len(result["rubric_mapping"]) > 0, "rubric_mapping 不能为空"
            
            # 验证第一个 rubric_mapping 项包含 scoring_rationale
            first_mapping = result["rubric_mapping"][0]
            assert "scoring_rationale" in first_mapping, \
                "rubric_mapping 项必须包含 scoring_rationale（评分依据）"
            assert isinstance(first_mapping["scoring_rationale"], str), \
                "scoring_rationale 必须是字符串"
            assert len(first_mapping["scoring_rationale"]) > 0, \
                "scoring_rationale 不能为空"
    
    # 运行异步测试
    asyncio.run(run_test())


@given(
    context_pack=context_pack_strategy(),
    vision_result=vision_result_strategy()
)
@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_objective_reasoning_trace_quality(context_pack, vision_result):
    """
    验证 reasoning_trace 的质量：应包含完整的推理步骤
    """
    async def run_test():
        agent = ObjectiveAgent(api_key="fake_api_key")
        
        # Mock _extract_student_answer 方法
        async def mock_extract(*args, **kwargs):
            return vision_result
        
        with patch.object(agent, '_extract_student_answer', side_effect=mock_extract):
            result = await agent.grade(context_pack)
            
            reasoning_trace = result["reasoning_trace"]
            
            # 验证推理轨迹包含关键步骤
            trace_text = " ".join(reasoning_trace)
            
            # 应包含视觉提取步骤
            has_vision_step = any("视觉提取" in step or "识别" in step for step in reasoning_trace)
            assert has_vision_step, "reasoning_trace 应包含视觉提取步骤"
            
            # 应包含答案比对步骤
            has_comparison_step = any("比对" in step or "答案" in step for step in reasoning_trace)
            assert has_comparison_step, "reasoning_trace 应包含答案比对步骤"
            
            # 应包含置信度计算步骤
            has_confidence_step = any("置信度" in step for step in reasoning_trace)
            assert has_confidence_step, "reasoning_trace 应包含置信度计算步骤"
            
            # 应包含评分依据步骤
            has_rationale_step = any("评分依据" in step or "依据" in step for step in reasoning_trace)
            assert has_rationale_step, "reasoning_trace 应包含评分依据步骤"
    
    # 运行异步测试
    asyncio.run(run_test())



@given(
    context_pack=context_pack_strategy()
)
@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_objective_scoring_rationale_content(context_pack):
    """
    验证 scoring_rationale 的内容质量：应包含答案识别、比对结果和置信度说明
    """
    async def run_test():
        agent = ObjectiveAgent(api_key="fake_api_key")
        
        # Mock _extract_student_answer 方法 - 清晰答案
        async def mock_extract(*args, **kwargs):
            return {
                "student_answer": "A",
                "answer_location": [100, 100, 200, 200],
                "description": "学生选择了答案 A",
                "answer_clarity": "clear"
            }
        
        with patch.object(agent, '_extract_student_answer', side_effect=mock_extract):
            result = await agent.grade(context_pack)
            
            scoring_rationale = result["rubric_mapping"][0]["scoring_rationale"]
            
            # 验证评分依据包含关键信息
            # 1. 应包含答案识别情况
            has_answer_info = "答案识别" in scoring_rationale or "学生选择" in scoring_rationale
            assert has_answer_info, "scoring_rationale 应包含答案识别情况"
            
            # 2. 应包含比对结果（正确/错误）
            has_comparison = "正确" in scoring_rationale or "错误" in scoring_rationale
            assert has_comparison, "scoring_rationale 应包含答案比对结果"
            
            # 3. 应包含置信度说明
            has_confidence_info = "置信度" in scoring_rationale or "复核" in scoring_rationale
            assert has_confidence_info, "scoring_rationale 应包含置信度说明"
    
    # 运行异步测试
    asyncio.run(run_test())
