"""属性测试：二次验证不一致处理

**Feature: self-evolving-grading, Property 17: 二次验证不一致处理**
**Validates: Requirements 7.4**

验证对于任意二次验证结果与首次不一致的情况，该题应被标记为待人工复核
"""

import pytest
from hypothesis import given, strategies as st, settings
from unittest.mock import patch
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
    standard_answer = draw(st.sampled_from(["A", "B", "C", "D"]))
    
    return ContextPack(
        question_image=question_image,
        question_type=QuestionType.OBJECTIVE,
        rubric=rubric,
        max_score=max_score,
        standard_answer=standard_answer,
        terminology=[],
        previous_result=None
    )


@pytest.mark.asyncio
@given(
    context_pack=context_pack_strategy(),
    first_answer=st.sampled_from(["A", "B", "C", "D"]),
    second_answer=st.sampled_from(["A", "B", "C", "D"])
)
@settings(max_examples=100, deadline=None)
async def test_inconsistent_verification_marks_for_review(context_pack, first_answer, second_answer):
    """
    **Feature: self-evolving-grading, Property 17: 二次验证不一致处理**
    **Validates: Requirements 7.4**
    
    属性：对于任意二次验证结果与首次不一致的情况，该题应被标记为待人工复核
    
    验证：
    1. 当首次和二次验证答案不同时，needs_secondary_review 应为 True
    2. 置信度应降低到 0.0
    3. reasoning_trace 应包含不一致警告
    4. rubric_mapping 应标记 inconsistent_verification
    """
    agent = ObjectiveAgent(api_key="fake_api_key")
    
    # Mock 首次提取 - 低置信度以触发二次验证
    async def mock_extract(*args, **kwargs):
        return {
            "student_answer": first_answer,
            "answer_location": [100, 100, 200, 200],
            "description": f"学生答案模糊，可能是 {first_answer}",
            "answer_clarity": "unclear"  # 低置信度
        }
    
    # Mock 二次验证 - 返回不同答案
    async def mock_secondary(*args, **kwargs):
        return {
            "student_answer": second_answer,
            "score": context_pack["max_score"] if second_answer == context_pack["standard_answer"] else 0.0,
            "is_correct": second_answer == context_pack["standard_answer"],
            "answer_clarity": "clear",
            "verification_notes": "二次验证完成"
        }
    
    with patch.object(agent, '_extract_student_answer', side_effect=mock_extract), \
         patch.object(agent, '_perform_secondary_verification', side_effect=mock_secondary):
        
        result = await agent.grade(context_pack)
        
        # 如果两次答案不同，应标记为待复核
        if first_answer != second_answer:
            # 验证 1：needs_secondary_review 应为 True
            assert result["needs_secondary_review"] is True, \
                f"二次验证不一致时应标记为待人工复核（首次：{first_answer}，二次：{second_answer}）"
            
            # 验证 2：置信度应降低到 0.0
            assert result["confidence"] == 0.0, \
                f"二次验证不一致时置信度应降低到 0.0，实际：{result['confidence']}"
            
            # 验证 3：reasoning_trace 应包含不一致警告
            reasoning_trace = result["reasoning_trace"]
            has_inconsistency_warning = any("不一致" in step for step in reasoning_trace)
            assert has_inconsistency_warning, \
                "reasoning_trace 应包含二次验证不一致的警告"
            
            # 验证 4：rubric_mapping 应标记 inconsistent_verification
            first_mapping = result["rubric_mapping"][0]
            assert "inconsistent_verification" in first_mapping, \
                "rubric_mapping 应包含 inconsistent_verification 标记"
            assert first_mapping["inconsistent_verification"] is True, \
                "inconsistent_verification 应为 True"
        else:
            # 如果两次答案相同，不应标记为不一致
            first_mapping = result["rubric_mapping"][0]
            if "inconsistent_verification" in first_mapping:
                assert first_mapping["inconsistent_verification"] is False, \
                    "二次验证一致时 inconsistent_verification 应为 False"


@pytest.mark.asyncio
@given(
    context_pack=context_pack_strategy(),
    answer=st.sampled_from(["A", "B", "C", "D"])
)
@settings(max_examples=50, deadline=None)
async def test_consistent_verification_increases_confidence(context_pack, answer):
    """
    验证一致的二次验证结果应提高置信度
    
    属性：当首次和二次验证结果一致时，置信度应提高
    """
    agent = ObjectiveAgent(api_key="fake_api_key")
    
    # Mock 首次提取 - 低置信度
    async def mock_extract(*args, **kwargs):
        return {
            "student_answer": answer,
            "answer_location": [100, 100, 200, 200],
            "description": f"学生答案模糊，可能是 {answer}",
            "answer_clarity": "unclear"
        }
    
    # Mock 二次验证 - 返回相同答案
    async def mock_secondary(*args, **kwargs):
        return {
            "student_answer": answer,
            "score": context_pack["max_score"] if answer == context_pack["standard_answer"] else 0.0,
            "is_correct": answer == context_pack["standard_answer"],
            "answer_clarity": "clear",
            "verification_notes": "二次验证确认"
        }
    
    with patch.object(agent, '_extract_student_answer', side_effect=mock_extract), \
         patch.object(agent, '_perform_secondary_verification', side_effect=mock_secondary):
        
        result = await agent.grade(context_pack)
        
        # 验证：一致时置信度应提高（unclear 基础置信度约 0.75，提高 0.15 后约 0.90）
        assert result["confidence"] > 0.75, \
            f"二次验证一致时置信度应提高，实际：{result['confidence']}"
        
        # 验证：reasoning_trace 应包含一致确认
        reasoning_trace = result["reasoning_trace"]
        has_consistency_confirmation = any("一致" in step and "✓" in step for step in reasoning_trace)
        assert has_consistency_confirmation, \
            "reasoning_trace 应包含二次验证一致的确认"
        
        # 验证：不应标记为不一致
        first_mapping = result["rubric_mapping"][0]
        if "inconsistent_verification" in first_mapping:
            assert first_mapping["inconsistent_verification"] is False, \
                "二次验证一致时 inconsistent_verification 应为 False"


@pytest.mark.asyncio
@given(
    context_pack=context_pack_strategy()
)
@settings(max_examples=30, deadline=None)
async def test_score_inconsistency_also_triggers_review(context_pack):
    """
    验证即使答案相同但得分不同也应标记为不一致
    
    属性：当首次和二次验证的得分不同时，也应标记为待复核
    """
    agent = ObjectiveAgent(api_key="fake_api_key")
    
    # Mock 首次提取 - 低置信度
    async def mock_extract(*args, **kwargs):
        return {
            "student_answer": "A",
            "answer_location": [100, 100, 200, 200],
            "description": "学生答案模糊",
            "answer_clarity": "unclear"
        }
    
    # Mock 二次验证 - 相同答案但不同得分（模拟评分逻辑差异）
    first_score = context_pack["max_score"] if "A" == context_pack["standard_answer"] else 0.0
    second_score = 0.0 if first_score > 0 else context_pack["max_score"]
    
    async def mock_secondary(*args, **kwargs):
        return {
            "student_answer": "A",
            "score": second_score,
            "is_correct": second_score > 0,
            "answer_clarity": "clear",
            "verification_notes": "二次验证"
        }
    
    with patch.object(agent, '_extract_student_answer', side_effect=mock_extract), \
         patch.object(agent, '_perform_secondary_verification', side_effect=mock_secondary):
        
        result = await agent.grade(context_pack)
        
        # 如果得分不同，应标记为不一致
        if first_score != second_score:
            assert result["needs_secondary_review"] is True, \
                "得分不一致时应标记为待人工复核"
            
            assert result["confidence"] == 0.0, \
                "得分不一致时置信度应降低到 0.0"
            
            first_mapping = result["rubric_mapping"][0]
            assert first_mapping.get("inconsistent_verification", False) is True, \
                "得分不一致时应标记 inconsistent_verification"
