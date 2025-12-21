"""回归测试器使用示例

演示如何使用 RegressionTester 验证规则补丁的有效性。
"""

import asyncio
from src.services.regression_tester import get_regression_tester
from src.models.rule_patch import RulePatch, PatchType


async def main():
    """主函数"""
    print("=" * 60)
    print("回归测试器使用示例")
    print("=" * 60)
    
    # 获取回归测试器
    tester = get_regression_tester()
    
    # 示例1：创建规则补丁
    print("\n1. 创建规则补丁")
    patch = RulePatch(
        patch_type=PatchType.RULE,
        version="v1.0.0",
        description="添加单位换算规则：cm -> m",
        content={
            "rule_type": "unit_conversion",
            "from_unit": "cm",
            "to_unit": "m",
            "conversion_factor": 0.01
        },
        source_pattern_id="pattern_001"
    )
    print(f"补丁ID: {patch.patch_id}")
    print(f"补丁类型: {patch.patch_type}")
    print(f"描述: {patch.description}")
    
    # 示例2：运行回归测试
    print("\n2. 运行回归测试")
    result = await tester.run_regression(
        patch=patch,
        eval_set_id="eval_001"
    )
    
    print(f"\n测试结果：{'✓ 通过' if result.passed else '✗ 未通过'}")
    print(f"评测集: {result.eval_set_id}")
    print(f"总样本数: {result.total_samples}")
    print(f"改进样本: {result.improved_samples}")
    print(f"退化样本: {result.degraded_samples}")
    
    print("\n指标对比:")
    print(f"  误判率: {result.old_error_rate:.2%} -> {result.new_error_rate:.2%}")
    print(f"  漏判率: {result.old_miss_rate:.2%} -> {result.new_miss_rate:.2%}")
    print(f"  复核率: {result.old_review_rate:.2%} -> {result.new_review_rate:.2%}")
    
    # 示例3：判断是否为改进
    print("\n3. 判断是否为改进")
    
    # 场景A：显著改进
    print("\n场景A：显著改进")
    is_improvement_a = tester.is_improvement(
        old_error_rate=0.15,
        new_error_rate=0.08,  # 下降7%
        old_miss_rate=0.10,
        new_miss_rate=0.05,   # 下降5%
        old_review_rate=0.20,
        new_review_rate=0.12, # 下降8%
        degraded_samples=2,
        total_samples=100
    )
    print(f"结果: {'✓ 是改进' if is_improvement_a else '✗ 不是改进'}")
    
    # 场景B：改进不足
    print("\n场景B：改进不足")
    is_improvement_b = tester.is_improvement(
        old_error_rate=0.15,
        new_error_rate=0.14,  # 仅下降1%
        old_miss_rate=0.10,
        new_miss_rate=0.09,   # 仅下降1%
        old_review_rate=0.20,
        new_review_rate=0.19, # 仅下降1%
        degraded_samples=1,
        total_samples=100
    )
    print(f"结果: {'✓ 是改进' if is_improvement_b else '✗ 不是改进'}")
    
    # 场景C：有指标恶化
    print("\n场景C：有指标恶化")
    is_improvement_c = tester.is_improvement(
        old_error_rate=0.15,
        new_error_rate=0.08,  # 下降7%
        old_miss_rate=0.10,
        new_miss_rate=0.15,   # 上升5%（恶化）
        old_review_rate=0.20,
        new_review_rate=0.12, # 下降8%
        degraded_samples=2,
        total_samples=100
    )
    print(f"结果: {'✓ 是改进' if is_improvement_c else '✗ 不是改进'}")
    
    # 场景D：退化样本过多
    print("\n场景D：退化样本过多")
    is_improvement_d = tester.is_improvement(
        old_error_rate=0.15,
        new_error_rate=0.08,  # 下降7%
        old_miss_rate=0.10,
        new_miss_rate=0.05,   # 下降5%
        old_review_rate=0.20,
        new_review_rate=0.12, # 下降8%
        degraded_samples=5,   # 5%退化（超过2%阈值）
        total_samples=100
    )
    print(f"结果: {'✓ 是改进' if is_improvement_d else '✗ 不是改进'}")
    
    # 示例4：自定义配置
    print("\n4. 自定义配置")
    from src.services.regression_tester import RegressionTester
    
    custom_tester = RegressionTester(
        improvement_threshold=0.03,  # 降低改进阈值到3%
        max_degradation_rate=0.05    # 提高最大退化率到5%
    )
    
    is_improvement_custom = custom_tester.is_improvement(
        old_error_rate=0.15,
        new_error_rate=0.12,  # 下降3%（刚好达到阈值）
        old_miss_rate=0.10,
        new_miss_rate=0.10,   # 不变
        old_review_rate=0.20,
        new_review_rate=0.20, # 不变
        degraded_samples=4,   # 4%退化（在5%阈值内）
        total_samples=100
    )
    print(f"自定义配置下的结果: {'✓ 是改进' if is_improvement_custom else '✗ 不是改进'}")
    
    print("\n" + "=" * 60)
    print("示例完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

