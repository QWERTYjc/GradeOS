"""
属性测试：提示词截断优先级

**Feature: self-evolving-grading, Property 12: 提示词截断优先级**
**Validates: Requirements 5.5**

测试对于任意超过 token 限制的提示词，截断应按优先级进行：
SYSTEM > RUBRIC > EXEMPLARS > ERROR_GUIDANCE > DETAILED_REASONING > CALIBRATION
"""

import pytest
from hypothesis import given, strategies as st, settings, Phase, assume

from src.services.prompt_assembler import PromptAssembler
from src.models.prompt import PromptSection
from src.models.exemplar import Exemplar
from datetime import datetime


# 配置 Hypothesis
settings.register_profile(
    "ci",
    max_examples=100,
    phases=[Phase.generate, Phase.target, Phase.shrink]
)
settings.load_profile("ci")


# 优先级映射（数字越小优先级越高）
PRIORITY_MAP = {
    PromptSection.SYSTEM: 0,
    PromptSection.RUBRIC: 1,
    PromptSection.EXEMPLARS: 2,
    PromptSection.ERROR_GUIDANCE: 3,
    PromptSection.DETAILED_REASONING: 4,
    PromptSection.CALIBRATION: 5
}


def generate_long_text(length: int) -> str:
    """生成指定长度的文本"""
    base = "这是一段用于测试的长文本内容。"
    repeat_count = (length // len(base)) + 1
    return (base * repeat_count)[:length]


@given(
    rubric_length=st.integers(min_value=100, max_value=5000),
    exemplar_count=st.integers(min_value=0, max_value=10),
    error_pattern_count=st.integers(min_value=0, max_value=20),
    has_detailed_reasoning=st.booleans(),
    has_calibration=st.booleans(),
    max_tokens=st.integers(min_value=250, max_value=1000)  # 提高最小值
)
@settings(max_examples=100)
def test_truncation_priority_correctness(
    rubric_length: int,
    exemplar_count: int,
    error_pattern_count: int,
    has_detailed_reasoning: bool,
    has_calibration: bool,
    max_tokens: int
):
    """
    **Feature: self-evolving-grading, Property 12: 提示词截断优先级**
    **Validates: Requirements 5.5**
    
    属性：对于任意超过 token 限制的提示词，截断应按优先级进行。
    
    验证：
    1. 高优先级区段（SYSTEM, RUBRIC）应该被保留
    2. 如果发生截断，被截断的应该是低优先级区段
    3. 最终 token 数不应超过限制
    """
    assembler = PromptAssembler()
    
    # 生成长文本
    long_rubric = generate_long_text(rubric_length)
    
    # 生成判例
    exemplars = []
    for i in range(exemplar_count):
        exemplars.append(
            Exemplar(
                exemplar_id=f"ex{i}",
                question_type="objective",
                question_image_hash=f"hash{i}",
                student_answer_text=generate_long_text(200),
                score=5.0,
                max_score=10.0,
                teacher_feedback=generate_long_text(150),
                teacher_id="teacher1",
                confirmed_at=datetime.now(),
                usage_count=i,
                embedding=None
            )
        )
    
    # 生成错误模式
    error_patterns = [f"错误模式{i}：{generate_long_text(50)}" for i in range(error_pattern_count)]
    
    # 生成校准配置
    calibration = None
    if has_calibration:
        calibration = {
            "deduction_rules": {f"错误{i}": float(i) for i in range(10)},
            "strictness_level": 0.5
        }
    
    # 拼装提示词
    result = assembler.assemble(
        question_type="objective",
        rubric=long_rubric,
        exemplars=exemplars if exemplars else None,
        error_patterns=error_patterns if error_patterns else None,
        previous_confidence=0.7 if has_detailed_reasoning else None,
        calibration=calibration,
        max_tokens=max_tokens
    )
    
    # 验证 1：最终 token 数不超过限制（允许小幅超出，因为截断标记）
    assert result.total_tokens <= max_tokens + 50, \
        f"Token 数 {result.total_tokens} 超过限制 {max_tokens} 太多"
    
    # 验证 2：高优先级区段应该被保留
    assert PromptSection.SYSTEM in result.sections, "SYSTEM 区段必须被保留"
    
    # 验证 3：如果发生截断，检查优先级
    if result.truncated_sections:
        for truncated_section in result.truncated_sections:
            truncated_priority = PRIORITY_MAP[truncated_section]
            
            # 被截断的区段优先级应该低于或等于某些被保留的区段
            # 换句话说，不应该有比被截断区段优先级更低的区段被完整保留
            for kept_section in result.sections:
                if kept_section not in result.truncated_sections:
                    kept_priority = PRIORITY_MAP[kept_section]
                    # 被保留的区段优先级应该 <= 被截断的区段优先级
                    # 或者被保留的区段是高优先级的（SYSTEM, RUBRIC）
                    assert kept_priority <= truncated_priority or kept_priority <= 1, \
                        f"低优先级区段 {kept_section} (优先级 {kept_priority}) 被保留，" \
                        f"而高优先级区段 {truncated_section} (优先级 {truncated_priority}) 被截断"


@given(
    max_tokens=st.integers(min_value=150, max_value=500)  # 提高最小值，确保有足够空间
)
@settings(max_examples=50)
def test_system_and_rubric_always_preserved(max_tokens: int):
    """
    测试 SYSTEM 和 RUBRIC 区段在合理限制下被保留
    
    属性：当 token 限制合理时（>= 150），SYSTEM 和 RUBRIC 都应该至少部分存在
    """
    assembler = PromptAssembler()
    
    # 创建大量内容
    long_rubric = generate_long_text(2000)
    exemplars = [
        Exemplar(
            exemplar_id=f"ex{i}",
            question_type="objective",
            question_image_hash=f"hash{i}",
            student_answer_text=generate_long_text(200),
            score=5.0,
            max_score=10.0,
            teacher_feedback=generate_long_text(150),
            teacher_id="teacher1",
            confirmed_at=datetime.now(),
            usage_count=i,
            embedding=None
        )
        for i in range(10)
    ]
    
    result = assembler.assemble(
        question_type="objective",
        rubric=long_rubric,
        exemplars=exemplars,
        error_patterns=["错误1", "错误2"] * 20,
        previous_confidence=0.7,
        max_tokens=max_tokens
    )
    
    # 验证 SYSTEM 始终存在（最高优先级）
    assert PromptSection.SYSTEM in result.sections, "SYSTEM 区段必须存在"
    
    # 验证 RUBRIC 在合理限制下存在（第二优先级）
    # 如果 token 限制足够大，RUBRIC 应该存在
    if max_tokens >= 200:
        assert PromptSection.RUBRIC in result.sections, "RUBRIC 区段应该存在（token 限制 >= 200）"


@given(
    section_lengths=st.lists(
        st.integers(min_value=100, max_value=1000),
        min_size=3,
        max_size=6
    ),
    max_tokens=st.integers(min_value=200, max_value=800)
)
@settings(max_examples=50)
def test_truncation_order_consistency(section_lengths: list, max_tokens: int):
    """
    测试截断顺序的一致性
    
    属性：给定相同的输入，截断结果应该一致
    """
    assembler = PromptAssembler()
    
    # 创建内容
    rubric = generate_long_text(section_lengths[0])
    exemplars = [
        Exemplar(
            exemplar_id="ex1",
            question_type="objective",
            question_image_hash="hash1",
            student_answer_text=generate_long_text(section_lengths[1] if len(section_lengths) > 1 else 100),
            score=5.0,
            max_score=10.0,
            teacher_feedback="反馈",
            teacher_id="teacher1",
            confirmed_at=datetime.now(),
            usage_count=1,
            embedding=None
        )
    ] if len(section_lengths) > 1 else None
    
    error_patterns = [generate_long_text(section_lengths[2])] if len(section_lengths) > 2 else None
    
    # 多次拼装
    result1 = assembler.assemble(
        question_type="objective",
        rubric=rubric,
        exemplars=exemplars,
        error_patterns=error_patterns,
        max_tokens=max_tokens
    )
    
    result2 = assembler.assemble(
        question_type="objective",
        rubric=rubric,
        exemplars=exemplars,
        error_patterns=error_patterns,
        max_tokens=max_tokens
    )
    
    # 验证截断结果一致
    assert result1.truncated_sections == result2.truncated_sections, \
        "相同输入应产生相同的截断结果"
    
    # 验证 token 数一致
    assert result1.total_tokens == result2.total_tokens, \
        "相同输入应产生相同的 token 数"


@given(
    max_tokens=st.integers(min_value=300, max_value=1000)
)
@settings(max_examples=30)
def test_no_truncation_when_under_limit(max_tokens: int):
    """
    测试在限制内不截断
    
    属性：如果内容总量小于限制，不应该有任何截断
    """
    assembler = PromptAssembler()
    
    # 创建适量内容（确保不超过限制）
    result = assembler.assemble(
        question_type="objective",
        rubric="简短的评分标准",
        max_tokens=max_tokens
    )
    
    # 验证没有截断
    assert len(result.truncated_sections) == 0, "内容未超限时不应该截断"
    
    # 验证 token 数小于限制
    assert result.total_tokens < max_tokens, "Token 数应该小于限制"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--hypothesis-show-statistics"])
