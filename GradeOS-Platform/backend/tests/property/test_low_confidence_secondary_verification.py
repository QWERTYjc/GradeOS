"""属性测试：低置信度二次验证触发

**Feature: self-evolving-grading, Property 16: 低置信度二次验证触发**
**Validates: Requirements 7.3**

验证对于任意置信度低于 0.85 的客观题评分，应触发二次验证流程
"""

import pytest
from hypothesis import given, strategies as st, settings
from unittest.mock import AsyncMock, patch
import base64

from src.agents.specialized.objective import ObjectiveAgent
from src.models.state import ContextPack
from src.models.enums import QuestionType


# 生成策略
@st.composite
def context_pack_strategy(draw):
    """生成客观题上下文包"""
    image_data = b"fake_image_data"
    question_image = base64.b64encode(image_data).decode('utf-8')
    
    rubric = draw(st.text(min_size=10, max_size=200))
    max_score = draw(st.floats(min_value=1.0, max_value=10.0))
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
def low_confidence_vision_result_strategy(draw):
    """生成低置信度的视觉提取结果"""
    student_answer = draw(st.sampled_from(["A", "B", "C", "D", "TRUE", "FALSE", ""]))
    # 低置信度场景：答案不清晰或未找到
    answer_clarity = draw(st.sampled_from(["unclear", "not_found"]))
    
    return {
        "student_answer": student_answer,
        "answer_location": [100, 100, 200, 200],
        "description": f"学生答案模糊，可能是 {student_answer}",
        "answer_clarity": answer_clarity
    }


@st.composite
def high_confidence_vision_result_strategy(draw):
    """生成高置信度的视觉提取结果"""
    student_answer = draw(st.sampled_from(["A", "B", "C", "D", "TRUE", "FALSE"]))
    
    return {
        "student_answer": student_answer,
        "answer_location": [100, 100, 200, 200],
        "description": f"学生选择了答案 {student_answer}",
        "answer_clarity": "clear"
    }


@pytest.mark.asyncio
@given(
    context_pack=context_pack_strategy(),
    vision_result=low_confidence_vision_result_strategy()
)
@settings(max_examples=100, deadline=None)
async def test_low_confidence_triggers_secondary_verification(context_pack, vision_result):
    """
    **Feature: self-evolving-grading, Property 16: 低置信度二次验证触发**
    **Validates: Requirements 7.3**
    
    属性：对于任意置信度低于 0.85 的客观题评分，应触发二次验证流程
    
    验证：
    1. 当答案清晰度为 unclear 或 not_found 时，置信度应 < 0.85
    2. 置信度 < 0.85 时，应调用二次验证方法
    3. reasoning_trace 中应包含二次验证的记录
    """
    agent = ObjectiveAgent(api_key="fake_api_key")
    
    # Mock 首次提取
    async def mock_extract(*args, **kwargs):
        return vision_result
    
    # Mock 二次验证
    secondary_called = False
    
    async def mock_secondary(*args, **kwargs):
        nonlocal secondary_called
        secondary_called = True
        return {
            "student_answer": vision_result["student_answer"],
            "score": 0.0,
            "is_correct": False,
            "answer_clarity": "clear",
            "verification_notes": "二次验证完成"
        }
    
    with patch.object(agent, '_extract_student_answer', side_effect=mock_extract), \
         patch.object(agent, '_perform_secondary_verification', side_effect=mock_secondary):
        
        result = await agent.grade(context_pack)
        
        # 验证 1：低置信度场景下置信度应 < 0.85
        # 注意：由于二次验证可能提高置信度，我们检查是否触发了二次验证
        
        # 验证 2：应调用二次验证方法
        assert secondary_called, \
            f"置信度低于 0.85 时应触发二次验证（answer_clarity={vision_result['answer_clarity']}）"
        
        # 验证 3：reasoning_trace 应包含二次验证记录
        reasoning_trace = result["reasoning_trace"]
        trace_text = " ".join(reasoning_trace)
        
        has_secondary_trigger = any("二次验证" in step for step in reasoning_trace)
        assert has_secondary_trigger, \
            "reasoning_trace 应包含二次验证触发的记录"
        
        # 验证 rubric_mapping 中标记了二次验证
        first_mapping = result["rubric_mapping"][0]
        assert "secondary_verification" in first_mapping, \
            "rubric_mapping 应包含 secondary_verification 标记"
        assert first_mapping["secondary_verification"] is True, \
            "secondary_verification 应为 True"


@pytest.mark.asyncio
@given(
    context_pack=context_pack_strategy(),
    vision_result=high_confidence_vision_result_strategy()
)
@settings(max_examples=50, deadline=None)
async def test_high_confidence_skips_secondary_verification(context_pack, vision_result):
    """
    验证高置信度场景不触发二次验证
    
    属性：对于置信度 >= 0.85 的评分，不应触发二次验证
    """
    agent = ObjectiveAgent(api_key="fake_api_key")
    
    # Mock 首次提取 - 清晰答案
    async def mock_extract(*args, **kwargs):
        return vision_result
    
    # Mock 二次验证
    secondary_called = False
    
    async def mock_secondary(*args, **kwargs):
        nonlocal secondary_called
        secondary_called = True
        return {
            "student_answer": vision_result["student_answer"],
            "score": 0.0,
            "is_correct": False,
            "answer_clarity": "clear",
            "verification_notes": "不应被调用"
        }
    
    with patch.object(agent, '_extract_student_answer', side_effect=mock_extract), \
         patch.object(agent, '_perform_secondary_verification', side_effect=mock_secondary):
        
        result = await agent.grade(context_pack)
        
        # 验证：高置信度时不应调用二次验证
        assert not secondary_called, \
            f"高置信度场景不应触发二次验证（answer_clarity={vision_result['answer_clarity']}）"
        
        # 验证 rubric_mapping 中未标记二次验证
        first_mapping = result["rubric_mapping"][0]
        if "secondary_verification" in first_mapping:
            assert first_mapping["secondary_verification"] is False, \
                "高置信度场景 secondary_verification 应为 False"


@pytest.mark.asyncio
@given(
    context_pack=context_pack_strategy()
)
@settings(max_examples=30, deadline=None)
async def test_secondary_verification_not_triggered_on_retry(context_pack):
    """
    验证二次验证不会在已有 previous_result 时触发（避免无限循环）
    
    属性：当 context_pack 包含 previous_result 时，即使置信度低也不应触发二次验证
    """
    # 添加 previous_result
    context_pack_with_previous = dict(context_pack)
    context_pack_with_previous["previous_result"] = {
        "score": 0.0,
        "student_answer": "A"
    }
    
    agent = ObjectiveAgent(api_key="fake_api_key")
    
    # Mock 首次提取 - 低置信度
    async def mock_extract(*args, **kwargs):
        return {
            "student_answer": "B",
            "answer_location": [100, 100, 200, 200],
            "description": "答案模糊",
            "answer_clarity": "unclear"
        }
    
    # Mock 二次验证
    secondary_called = False
    
    async def mock_secondary(*args, **kwargs):
        nonlocal secondary_called
        secondary_called = True
        return {
            "student_answer": "B",
            "score": 0.0,
            "is_correct": False,
            "answer_clarity": "clear",
            "verification_notes": "不应被调用"
        }
    
    with patch.object(agent, '_extract_student_answer', side_effect=mock_extract), \
         patch.object(agent, '_perform_secondary_verification', side_effect=mock_secondary):
        
        result = await agent.grade(context_pack_with_previous)
        
        # 验证：有 previous_result 时不应触发二次验证
        assert not secondary_called, \
            "存在 previous_result 时不应触发二次验证（避免无限循环）"
