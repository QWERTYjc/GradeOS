"""补丁生成器使用示例

演示如何使用 PatchGenerator 从失败模式生成规则补丁。
"""

import asyncio
from src.services.patch_generator import get_patch_generator
from src.models.failure_pattern import FailurePattern, PatternType


async def main():
    """主函数"""
    print("=" * 60)
    print("补丁生成器使用示例")
    print("=" * 60)
    
    # 获取补丁生成器
    generator = get_patch_generator()
    
    # 示例 1：规范化阶段失败模式
    print("\n示例 1：规范化阶段失败模式")
    print("-" * 60)
    
    normalization_pattern = FailurePattern(
        pattern_type=PatternType.NORMALIZATION,
        description="规范化规则 'unit_conversion' 应用后仍然匹配失败",
        frequency=15,
        sample_log_ids=["log_001", "log_002", "log_003"],
        confidence=0.85,
        is_fixable=True,
        error_signature="normalization_unit_conversion",
        suggested_fix="检查规则 'unit_conversion' 的实现，可能需要添加更多变体"
    )
    
    patch1 = await generator.generate_patch(normalization_pattern)
    
    if patch1:
        print(f"✓ 生成补丁成功")
        print(f"  补丁ID: {patch1.patch_id}")
        print(f"  版本: {patch1.version}")
        print(f"  类型: {patch1.patch_type}")
        print(f"  描述: {patch1.description}")
        print(f"  状态: {patch1.status}")
        print(f"  内容: {patch1.content}")
    
    # 示例 2：提取阶段失败模式
    print("\n示例 2：提取阶段失败模式")
    print("-" * 60)
    
    extraction_pattern = FailurePattern(
        pattern_type=PatternType.EXTRACTION,
        description="题目 Q1 答案提取失败（低置信度或空答案）",
        frequency=10,
        sample_log_ids=["log_004", "log_005"],
        confidence=0.8,
        is_fixable=True,
        error_signature="extraction_failure_Q1",
        affected_question_types=["Q1"],
        suggested_fix="优化提取提示词，增加答案区域识别规则"
    )
    
    patch2 = await generator.generate_patch(extraction_pattern)
    
    if patch2:
        print(f"✓ 生成补丁成功")
        print(f"  补丁ID: {patch2.patch_id}")
        print(f"  版本: {patch2.version}")
        print(f"  类型: {patch2.patch_type}")
        print(f"  描述: {patch2.description}")
        print(f"  内容: {patch2.content}")
    
    # 示例 3：匹配阶段失败模式
    print("\n示例 3：匹配阶段失败模式")
    print("-" * 60)
    
    matching_pattern = FailurePattern(
        pattern_type=PatternType.MATCHING,
        description="匹配失败：答案表达方式不同但含义相同",
        frequency=20,
        sample_log_ids=["log_006", "log_007", "log_008"],
        confidence=0.9,
        is_fixable=True,
        error_signature="matching_1234",
        suggested_fix="添加同义词规则或放宽匹配条件"
    )
    
    patch3 = await generator.generate_patch(matching_pattern)
    
    if patch3:
        print(f"✓ 生成补丁成功")
        print(f"  补丁ID: {patch3.patch_id}")
        print(f"  版本: {patch3.version}")
        print(f"  类型: {patch3.patch_type}")
        print(f"  描述: {patch3.description}")
        print(f"  内容: {patch3.content}")
    
    # 示例 4：评分阶段失败模式（可修复）
    print("\n示例 4：评分阶段失败模式（可修复）")
    print("-" * 60)
    
    scoring_pattern_fixable = FailurePattern(
        pattern_type=PatternType.SCORING,
        description="评分偏差：固定扣分规则错误",
        frequency=8,
        sample_log_ids=["log_009", "log_010"],
        confidence=0.7,
        is_fixable=True,
        error_signature="scoring_deviation",
        suggested_fix="需要人工审核评分标准，可能需要调整校准配置"
    )
    
    patch4 = await generator.generate_patch(scoring_pattern_fixable)
    
    if patch4:
        print(f"✓ 生成补丁成功")
        print(f"  补丁ID: {patch4.patch_id}")
        print(f"  版本: {patch4.version}")
        print(f"  类型: {patch4.patch_type}")
        print(f"  描述: {patch4.description}")
        print(f"  内容: {patch4.content}")
    else:
        print("✗ 未生成补丁（评分问题需要人工介入）")
    
    # 示例 5：不可修复的模式
    print("\n示例 5：不可修复的模式")
    print("-" * 60)
    
    unfixable_pattern = FailurePattern(
        pattern_type=PatternType.SCORING,
        description="评分偏差：主观判断差异",
        frequency=5,
        sample_log_ids=["log_011"],
        confidence=0.6,
        is_fixable=False,  # 不可修复
        error_signature="scoring_subjective"
    )
    
    patch5 = await generator.generate_patch(unfixable_pattern)
    
    if patch5:
        print(f"✓ 生成补丁成功")
    else:
        print("✗ 未生成补丁（模式不可修复）")
    
    # 示例 6：批量生成补丁
    print("\n示例 6：批量生成补丁")
    print("-" * 60)
    
    patterns = [
        normalization_pattern,
        extraction_pattern,
        matching_pattern
    ]
    
    patches = []
    for pattern in patterns:
        patch = await generator.generate_patch(pattern)
        if patch:
            patches.append(patch)
    
    print(f"✓ 批量生成完成：{len(patches)}/{len(patterns)} 个补丁")
    for i, patch in enumerate(patches, 1):
        print(f"  {i}. {patch.patch_id} - {patch.description}")
    
    print("\n" + "=" * 60)
    print("示例完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
