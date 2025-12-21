"""补丁生成器单元测试"""

import pytest
from src.services.patch_generator import PatchGenerator
from src.models.failure_pattern import FailurePattern, PatternType
from src.models.rule_patch import PatchType


@pytest.fixture
def generator():
    """创建补丁生成器实例"""
    return PatchGenerator(version_prefix="v1")


@pytest.mark.asyncio
async def test_generate_extraction_patch(generator):
    """测试生成提取阶段补丁"""
    pattern = FailurePattern(
        pattern_type=PatternType.EXTRACTION,
        description="题目 Q1 答案提取失败",
        frequency=10,
        sample_log_ids=["log_001"],
        confidence=0.8,
        is_fixable=True,
        affected_question_types=["Q1"]
    )
    
    patch = await generator.generate_patch(pattern)
    
    assert patch is not None
    assert patch.patch_type == PatchType.PROMPT
    assert patch.version.startswith("v1.0.")
    assert "提取" in patch.description
    assert patch.source_pattern_id == pattern.pattern_id
    assert patch.content["patch_target"] == "extraction_prompt"


@pytest.mark.asyncio
async def test_generate_normalization_patch(generator):
    """测试生成规范化阶段补丁"""
    pattern = FailurePattern(
        pattern_type=PatternType.NORMALIZATION,
        description="规范化规则 'unit_conversion' 应用后仍然匹配失败",
        frequency=15,
        sample_log_ids=["log_002"],
        confidence=0.85,
        is_fixable=True,
        error_signature="normalization_unit_conversion"
    )
    
    patch = await generator.generate_patch(pattern)
    
    assert patch is not None
    assert patch.patch_type == PatchType.RULE
    assert patch.version.startswith("v1.0.")
    assert "规范化" in patch.description
    assert patch.content["patch_target"] == "normalization_rules"
    assert patch.content["rule_name"] == "unit_conversion"


@pytest.mark.asyncio
async def test_generate_matching_patch(generator):
    """测试生成匹配阶段补丁"""
    pattern = FailurePattern(
        pattern_type=PatternType.MATCHING,
        description="匹配失败：同义词未识别",
        frequency=20,
        sample_log_ids=["log_003"],
        confidence=0.9,
        is_fixable=True
    )
    
    patch = await generator.generate_patch(pattern)
    
    assert patch is not None
    assert patch.patch_type == PatchType.RULE
    assert patch.version.startswith("v1.0.")
    assert "匹配" in patch.description
    assert patch.content["patch_target"] == "matching_rules"
    assert "synonym_expansion" in patch.content["enhancement"]["type"]


@pytest.mark.asyncio
async def test_generate_scoring_patch_fixable(generator):
    """测试生成可修复的评分阶段补丁"""
    pattern = FailurePattern(
        pattern_type=PatternType.SCORING,
        description="评分偏差：固定扣分规则错误",
        frequency=8,
        sample_log_ids=["log_004"],
        confidence=0.7,
        is_fixable=True
    )
    
    patch = await generator.generate_patch(pattern)
    
    assert patch is not None
    assert patch.patch_type == PatchType.RULE
    assert patch.version.startswith("v1.0.")
    assert "评分" in patch.description
    assert patch.content["patch_target"] == "scoring_rules"


@pytest.mark.asyncio
async def test_generate_scoring_patch_unfixable(generator):
    """测试不生成不可修复的评分补丁"""
    pattern = FailurePattern(
        pattern_type=PatternType.SCORING,
        description="评分偏差：主观判断差异",
        frequency=5,
        sample_log_ids=["log_005"],
        confidence=0.6,
        is_fixable=True  # 虽然标记为可修复，但描述中没有"固定扣分"
    )
    
    patch = await generator.generate_patch(pattern)
    
    # 应该返回 None，因为不是可自动修复的评分问题
    assert patch is None


@pytest.mark.asyncio
async def test_skip_unfixable_pattern(generator):
    """测试跳过不可修复的模式"""
    pattern = FailurePattern(
        pattern_type=PatternType.EXTRACTION,
        description="提取失败",
        frequency=3,
        sample_log_ids=["log_006"],
        confidence=0.5,
        is_fixable=False  # 明确标记为不可修复
    )
    
    patch = await generator.generate_patch(pattern)
    
    assert patch is None


@pytest.mark.asyncio
async def test_version_allocation(generator):
    """测试版本号分配"""
    pattern1 = FailurePattern(
        pattern_type=PatternType.EXTRACTION,
        description="测试1",
        frequency=5,
        is_fixable=True
    )
    
    pattern2 = FailurePattern(
        pattern_type=PatternType.NORMALIZATION,
        description="测试2",
        frequency=5,
        is_fixable=True
    )
    
    patch1 = await generator.generate_patch(pattern1)
    patch2 = await generator.generate_patch(pattern2)
    
    assert patch1 is not None
    assert patch2 is not None
    
    # 版本号应该递增
    assert patch1.version == "v1.0.1"
    assert patch2.version == "v1.0.2"


@pytest.mark.asyncio
async def test_patch_content_structure(generator):
    """测试补丁内容结构"""
    pattern = FailurePattern(
        pattern_type=PatternType.NORMALIZATION,
        description="规范化失败",
        frequency=10,
        is_fixable=True
    )
    
    patch = await generator.generate_patch(pattern)
    
    assert patch is not None
    assert "patch_target" in patch.content
    assert "pattern_type" in patch.content
    assert "enhancement" in patch.content
    assert "type" in patch.content["enhancement"]
    assert "description" in patch.content["enhancement"]


@pytest.mark.asyncio
async def test_extract_rule_name(generator):
    """测试从描述中提取规则名称"""
    rule_name = generator._extract_rule_name(
        "规范化规则 'unit_conversion' 应用后仍然匹配失败"
    )
    assert rule_name == "unit_conversion"
    
    # 测试没有规则名称的情况
    rule_name = generator._extract_rule_name("规范化失败")
    assert rule_name is None


def test_suggest_variants(generator):
    """测试建议变体"""
    pattern = FailurePattern(
        pattern_type=PatternType.NORMALIZATION,
        description="单位转换失败",
        frequency=5,
        is_fixable=True,
        error_signature="normalization_unit"
    )
    
    variants = generator._suggest_variants(pattern)
    
    assert isinstance(variants, list)
    assert len(variants) > 0
    # 应该包含单位相关的变体
    assert any("unit" in v.lower() or "cm" in v or "m" in v for v in variants)


def test_suggest_synonyms(generator):
    """测试建议同义词"""
    pattern = FailurePattern(
        pattern_type=PatternType.MATCHING,
        description="匹配失败",
        frequency=5,
        is_fixable=True
    )
    
    synonyms = generator._suggest_synonyms(pattern)
    
    assert isinstance(synonyms, list)
    assert len(synonyms) > 0
    # 每个同义词组应该有 canonical 和 synonyms 字段
    for group in synonyms:
        assert "canonical" in group
        assert "synonyms" in group
        assert isinstance(group["synonyms"], list)


@pytest.mark.asyncio
async def test_batch_generation(generator):
    """测试批量生成补丁"""
    patterns = [
        FailurePattern(
            pattern_type=PatternType.EXTRACTION,
            description=f"提取失败 {i}",
            frequency=5,
            is_fixable=True
        )
        for i in range(5)
    ]
    
    patches = []
    for pattern in patterns:
        patch = await generator.generate_patch(pattern)
        if patch:
            patches.append(patch)
    
    assert len(patches) == 5
    # 版本号应该递增
    for i, patch in enumerate(patches, 1):
        assert patch.version == f"v1.0.{i}"
