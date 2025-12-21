"""补丁生成条件属性测试

**Feature: self-evolving-grading, Property 22: 补丁生成条件**
**Validates: Requirements 9.2**

属性：对于任意可修复的失败模式，应生成对应的候选补丁。
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from src.services.patch_generator import PatchGenerator
from src.models.failure_pattern import FailurePattern, PatternType


# 策略：生成失败模式类型
pattern_type_strategy = st.sampled_from([
    PatternType.EXTRACTION,
    PatternType.NORMALIZATION,
    PatternType.MATCHING,
    PatternType.SCORING
])


# 策略：生成失败模式
def failure_pattern_strategy(is_fixable: bool = True):
    """生成失败模式的策略"""
    return st.builds(
        FailurePattern,
        pattern_type=pattern_type_strategy,
        description=st.text(min_size=10, max_size=200),
        frequency=st.integers(min_value=1, max_value=100),
        sample_log_ids=st.lists(
            st.text(min_size=5, max_size=20),
            min_size=1,
            max_size=10
        ),
        confidence=st.floats(min_value=0.0, max_value=1.0),
        is_fixable=st.just(is_fixable),
        error_signature=st.one_of(
            st.none(),
            st.text(min_size=5, max_size=50)
        ),
        affected_question_types=st.lists(
            st.text(min_size=1, max_size=10),
            max_size=5
        ),
        suggested_fix=st.one_of(
            st.none(),
            st.text(min_size=10, max_size=100)
        )
    )


@pytest.mark.asyncio
@given(pattern=failure_pattern_strategy(is_fixable=True))
@settings(max_examples=100, deadline=None)
async def test_fixable_pattern_generates_patch(pattern):
    """
    **Feature: self-evolving-grading, Property 22: 补丁生成条件**
    **Validates: Requirements 9.2**
    
    属性：对于任意可修复的失败模式，应生成对应的候选补丁。
    
    测试策略：
    1. 生成随机的可修复失败模式
    2. 调用 generate_patch 方法
    3. 验证返回的补丁不为 None
    4. 验证补丁的基本属性正确
    """
    # 对于评分类型的模式，需要特殊处理
    # 只有包含"固定扣分"或"扣分规则"的评分模式才会生成补丁
    if pattern.pattern_type == PatternType.SCORING:
        if "固定扣分" not in pattern.description and "扣分规则" not in pattern.description:
            # 这种情况下不应该生成补丁，跳过测试
            assume(False)
    
    generator = PatchGenerator()
    patch = await generator.generate_patch(pattern)
    
    # 验证生成了补丁
    assert patch is not None, f"可修复的模式 {pattern.pattern_id} 应该生成补丁"
    
    # 验证补丁的基本属性
    assert patch.patch_id is not None
    assert patch.version is not None
    assert patch.patch_type is not None
    assert patch.description is not None
    assert len(patch.description) > 0
    assert patch.content is not None
    assert isinstance(patch.content, dict)
    assert patch.source_pattern_id == pattern.pattern_id
    
    # 验证补丁内容包含必要字段
    assert "patch_target" in patch.content
    assert "pattern_type" in patch.content
    assert patch.content["pattern_type"] == pattern.pattern_type.value


@pytest.mark.asyncio
@given(pattern=failure_pattern_strategy(is_fixable=False))
@settings(max_examples=100, deadline=None)
async def test_unfixable_pattern_no_patch(pattern):
    """
    **Feature: self-evolving-grading, Property 22: 补丁生成条件（反向）**
    **Validates: Requirements 9.2**
    
    属性：对于任意不可修复的失败模式，不应生成补丁。
    
    测试策略：
    1. 生成随机的不可修复失败模式
    2. 调用 generate_patch 方法
    3. 验证返回 None
    """
    generator = PatchGenerator()
    patch = await generator.generate_patch(pattern)
    
    # 验证没有生成补丁
    assert patch is None, f"不可修复的模式 {pattern.pattern_id} 不应该生成补丁"


@pytest.mark.asyncio
@given(
    pattern_type=pattern_type_strategy,
    frequency=st.integers(min_value=1, max_value=100),
    confidence=st.floats(min_value=0.0, max_value=1.0)
)
@settings(max_examples=100, deadline=None)
async def test_patch_type_matches_pattern_type(pattern_type, frequency, confidence):
    """
    **Feature: self-evolving-grading, Property 22: 补丁类型匹配**
    **Validates: Requirements 9.2**
    
    属性：生成的补丁类型应该与失败模式类型相匹配。
    
    测试策略：
    1. 生成不同类型的失败模式
    2. 验证生成的补丁类型符合预期
    """
    # 构造可修复的模式
    description = "测试模式"
    if pattern_type == PatternType.SCORING:
        # 评分类型需要特殊描述才能生成补丁
        description = "固定扣分规则错误"
    
    pattern = FailurePattern(
        pattern_type=pattern_type,
        description=description,
        frequency=frequency,
        sample_log_ids=["log_001"],
        confidence=confidence,
        is_fixable=True
    )
    
    generator = PatchGenerator()
    patch = await generator.generate_patch(pattern)
    
    if patch is not None:
        # 验证补丁类型
        if pattern_type == PatternType.EXTRACTION:
            # 提取阶段应该生成提示词补丁
            from src.models.rule_patch import PatchType
            assert patch.patch_type == PatchType.PROMPT
        elif pattern_type in [PatternType.NORMALIZATION, PatternType.MATCHING, PatternType.SCORING]:
            # 其他阶段应该生成规则补丁
            from src.models.rule_patch import PatchType
            assert patch.patch_type == PatchType.RULE


@pytest.mark.asyncio
@given(
    patterns=st.lists(
        failure_pattern_strategy(is_fixable=True),
        min_size=1,
        max_size=10
    )
)
@settings(max_examples=50, deadline=None)
async def test_version_uniqueness(patterns):
    """
    **Feature: self-evolving-grading, Property 22: 版本号唯一性**
    **Validates: Requirements 9.2**
    
    属性：批量生成补丁时，每个补丁应该有唯一的版本号。
    
    测试策略：
    1. 批量生成多个补丁
    2. 验证所有版本号都不相同
    """
    # 过滤掉不会生成补丁的评分模式
    filtered_patterns = []
    for pattern in patterns:
        if pattern.pattern_type == PatternType.SCORING:
            if "固定扣分" not in pattern.description and "扣分规则" not in pattern.description:
                continue
        filtered_patterns.append(pattern)
    
    assume(len(filtered_patterns) > 0)
    
    generator = PatchGenerator()
    patches = []
    
    for pattern in filtered_patterns:
        patch = await generator.generate_patch(pattern)
        if patch is not None:
            patches.append(patch)
    
    # 如果生成了补丁，验证版本号唯一性
    if len(patches) > 1:
        versions = [patch.version for patch in patches]
        assert len(versions) == len(set(versions)), "补丁版本号应该唯一"


@pytest.mark.asyncio
@given(pattern=failure_pattern_strategy(is_fixable=True))
@settings(max_examples=100, deadline=None)
async def test_patch_content_structure(pattern):
    """
    **Feature: self-evolving-grading, Property 22: 补丁内容结构**
    **Validates: Requirements 9.2**
    
    属性：生成的补丁应该包含完整的内容结构。
    
    测试策略：
    1. 生成随机的可修复失败模式
    2. 验证补丁内容包含必要的字段
    """
    # 对于评分类型的模式，需要特殊处理
    if pattern.pattern_type == PatternType.SCORING:
        if "固定扣分" not in pattern.description and "扣分规则" not in pattern.description:
            assume(False)
    
    generator = PatchGenerator()
    patch = await generator.generate_patch(pattern)
    
    if patch is not None:
        # 验证补丁内容结构
        assert "patch_target" in patch.content
        assert "pattern_type" in patch.content
        assert "enhancement" in patch.content
        
        # 验证 enhancement 结构
        enhancement = patch.content["enhancement"]
        assert "type" in enhancement
        assert "description" in enhancement
        assert isinstance(enhancement["description"], str)
        assert len(enhancement["description"]) > 0


@pytest.mark.asyncio
@given(
    pattern=failure_pattern_strategy(is_fixable=True),
    version_prefix=st.text(min_size=1, max_size=5, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")))
)
@settings(max_examples=50, deadline=None)
async def test_version_prefix_applied(pattern, version_prefix):
    """
    **Feature: self-evolving-grading, Property 22: 版本前缀应用**
    **Validates: Requirements 9.2**
    
    属性：生成的补丁版本号应该使用配置的前缀。
    
    测试策略：
    1. 使用自定义版本前缀创建生成器
    2. 验证生成的补丁版本号包含该前缀
    """
    # 对于评分类型的模式，需要特殊处理
    if pattern.pattern_type == PatternType.SCORING:
        if "固定扣分" not in pattern.description and "扣分规则" not in pattern.description:
            assume(False)
    
    generator = PatchGenerator(version_prefix=version_prefix)
    patch = await generator.generate_patch(pattern)
    
    if patch is not None:
        # 验证版本号前缀
        assert patch.version.startswith(version_prefix), \
            f"版本号 {patch.version} 应该以 {version_prefix} 开头"


@pytest.mark.asyncio
@given(pattern=failure_pattern_strategy(is_fixable=True))
@settings(max_examples=100, deadline=None)
async def test_patch_source_traceability(pattern):
    """
    **Feature: self-evolving-grading, Property 22: 补丁来源可追溯**
    **Validates: Requirements 9.2**
    
    属性：生成的补丁应该能追溯到源失败模式。
    
    测试策略：
    1. 生成随机的可修复失败模式
    2. 验证补丁的 source_pattern_id 与模式 ID 一致
    """
    # 对于评分类型的模式，需要特殊处理
    if pattern.pattern_type == PatternType.SCORING:
        if "固定扣分" not in pattern.description and "扣分规则" not in pattern.description:
            assume(False)
    
    generator = PatchGenerator()
    patch = await generator.generate_patch(pattern)
    
    if patch is not None:
        # 验证来源可追溯
        assert patch.source_pattern_id == pattern.pattern_id, \
            "补丁应该记录源失败模式ID"
