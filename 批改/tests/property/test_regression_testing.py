"""回归测试必要性和发布条件属性测试

验证：需求 9.3, 9.4 - 补丁必须通过回归测试，且误判率下降才能发布
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from uuid import uuid4

from src.services.regression_tester import RegressionTester
from src.models.rule_patch import RulePatch, PatchType


class TestRegressionTestingNecessity:
    """回归测试必要性属性测试
    
    **Feature: self-evolving-grading, Property 23: 回归测试必要性**
    **Validates: Requirements 9.3**
    """
    
    @given(
        patch_type=st.sampled_from([PatchType.RULE, PatchType.PROMPT, PatchType.EXEMPLAR]),
        version=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='.-_')),
        description=st.text(min_size=10, max_size=100)
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_all_patches_must_undergo_regression_testing(
        self,
        patch_type: PatchType,
        version: str,
        description: str
    ):
        """
        属性：对于任意生成的候选补丁，在部署前必须通过回归测试
        
        **Feature: self-evolving-grading, Property 23: 回归测试必要性**
        **Validates: Requirements 9.3**
        """
        # 创建补丁
        patch = RulePatch(
            patch_type=patch_type,
            version=version,
            description=description,
            content={"test": "data"},
            source_pattern_id=f"pattern_{uuid4().hex[:8]}"
        )
        
        # 创建回归测试器
        tester = RegressionTester()
        
        # 执行回归测试
        result = await tester.run_regression(
            patch=patch,
            eval_set_id="test_eval"
        )
        
        # 验证：必须返回测试结果
        assert result is not None, "回归测试必须返回结果"
        assert result.patch_id == patch.patch_id, "测试结果应该关联到正确的补丁"
        
        # 验证：测试结果必须包含所有必要字段
        assert hasattr(result, 'passed'), "测试结果必须包含 passed 字段"
        assert hasattr(result, 'old_error_rate'), "测试结果必须包含 old_error_rate 字段"
        assert hasattr(result, 'new_error_rate'), "测试结果必须包含 new_error_rate 字段"
        assert hasattr(result, 'old_miss_rate'), "测试结果必须包含 old_miss_rate 字段"
        assert hasattr(result, 'new_miss_rate'), "测试结果必须包含 new_miss_rate 字段"
        assert hasattr(result, 'old_review_rate'), "测试结果必须包含 old_review_rate 字段"
        assert hasattr(result, 'new_review_rate'), "测试结果必须包含 new_review_rate 字段"
        assert hasattr(result, 'total_samples'), "测试结果必须包含 total_samples 字段"
        assert hasattr(result, 'improved_samples'), "测试结果必须包含 improved_samples 字段"
        assert hasattr(result, 'degraded_samples'), "测试结果必须包含 degraded_samples 字段"
    
    @given(
        n_patches=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50, deadline=None)
    @pytest.mark.asyncio
    async def test_multiple_patches_all_tested(
        self,
        n_patches: int
    ):
        """
        属性：对于任意数量的候选补丁，每个都必须经过回归测试
        
        **Feature: self-evolving-grading, Property 23: 回归测试必要性**
        **Validates: Requirements 9.3**
        """
        # 创建多个补丁
        patches = []
        for i in range(n_patches):
            patch = RulePatch(
                patch_type=PatchType.RULE,
                version=f"v1.0.{i}",
                description=f"测试补丁 {i}",
                content={"test": f"data_{i}"},
                source_pattern_id=f"pattern_{i}"
            )
            patches.append(patch)
        
        # 创建回归测试器
        tester = RegressionTester()
        
        # 对每个补丁执行回归测试
        results = []
        for patch in patches:
            result = await tester.run_regression(
                patch=patch,
                eval_set_id="test_eval"
            )
            results.append(result)
        
        # 验证：每个补丁都应该有测试结果
        assert len(results) == n_patches, \
            f"应该有 {n_patches} 个测试结果，实际有 {len(results)} 个"
        
        # 验证：每个结果都关联到正确的补丁
        for patch, result in zip(patches, results):
            assert result.patch_id == patch.patch_id, \
                f"测试结果应该关联到补丁 {patch.patch_id}"


class TestPatchDeploymentConditions:
    """补丁发布条件属性测试
    
    **Feature: self-evolving-grading, Property 24: 补丁发布条件**
    **Validates: Requirements 9.4**
    """
    
    @given(
        old_error_rate=st.floats(min_value=0.05, max_value=0.50),
        improvement_delta=st.floats(min_value=0.05, max_value=0.20),
        old_miss_rate=st.floats(min_value=0.05, max_value=0.50),
        miss_improvement=st.floats(min_value=0.0, max_value=0.20),
        old_review_rate=st.floats(min_value=0.05, max_value=0.50),
        review_improvement=st.floats(min_value=0.0, max_value=0.20),
        degraded_samples=st.integers(min_value=0, max_value=1)
    )
    @settings(max_examples=100, deadline=None)
    def test_patch_deployment_requires_improvement(
        self,
        old_error_rate: float,
        improvement_delta: float,
        old_miss_rate: float,
        miss_improvement: float,
        old_review_rate: float,
        review_improvement: float,
        degraded_samples: int
    ):
        """
        属性：对于任意通过回归测试且误判率下降的补丁，应该被判定为改进
        
        **Feature: self-evolving-grading, Property 24: 补丁发布条件**
        **Validates: Requirements 9.4**
        """
        # 确保改进幅度足够大
        assume(improvement_delta >= 0.05)
        
        # 计算新的指标值（都有改进）
        new_error_rate = old_error_rate - improvement_delta
        new_miss_rate = old_miss_rate - miss_improvement
        new_review_rate = old_review_rate - review_improvement
        
        # 确保新指标值有效
        assume(new_error_rate >= 0.0)
        assume(new_miss_rate >= 0.0)
        assume(new_review_rate >= 0.0)
        
        # 创建回归测试器
        tester = RegressionTester(
            improvement_threshold=0.05,
            max_degradation_rate=0.02
        )
        
        # 判断是否为改进
        is_improvement = tester.is_improvement(
            old_error_rate=old_error_rate,
            new_error_rate=new_error_rate,
            old_miss_rate=old_miss_rate,
            new_miss_rate=new_miss_rate,
            old_review_rate=old_review_rate,
            new_review_rate=new_review_rate,
            degraded_samples=degraded_samples,
            total_samples=100
        )
        
        # 验证：应该被判定为改进
        assert is_improvement is True, \
            f"误判率下降 {improvement_delta:.2%}，应该被判定为改进"
    
    @given(
        old_error_rate=st.floats(min_value=0.05, max_value=0.50),
        error_change=st.floats(min_value=-0.10, max_value=0.10),
        old_miss_rate=st.floats(min_value=0.05, max_value=0.50),
        miss_change=st.floats(min_value=-0.10, max_value=0.10),
        old_review_rate=st.floats(min_value=0.05, max_value=0.50),
        review_change=st.floats(min_value=-0.10, max_value=0.10)
    )
    @settings(max_examples=100, deadline=None)
    def test_patch_rejected_if_metrics_worsen(
        self,
        old_error_rate: float,
        error_change: float,
        old_miss_rate: float,
        miss_change: float,
        old_review_rate: float,
        review_change: float
    ):
        """
        属性：对于任意有指标恶化的补丁，不应该被判定为改进
        
        **Feature: self-evolving-grading, Property 24: 补丁发布条件**
        **Validates: Requirements 9.4**
        """
        # 确保至少有一个指标恶化
        assume(error_change > 0 or miss_change > 0 or review_change > 0)
        
        # 计算新的指标值
        new_error_rate = old_error_rate + error_change
        new_miss_rate = old_miss_rate + miss_change
        new_review_rate = old_review_rate + review_change
        
        # 确保新指标值有效
        assume(0.0 <= new_error_rate <= 1.0)
        assume(0.0 <= new_miss_rate <= 1.0)
        assume(0.0 <= new_review_rate <= 1.0)
        
        # 创建回归测试器
        tester = RegressionTester(
            improvement_threshold=0.05,
            max_degradation_rate=0.02
        )
        
        # 判断是否为改进
        is_improvement = tester.is_improvement(
            old_error_rate=old_error_rate,
            new_error_rate=new_error_rate,
            old_miss_rate=old_miss_rate,
            new_miss_rate=new_miss_rate,
            old_review_rate=old_review_rate,
            new_review_rate=new_review_rate,
            degraded_samples=1,
            total_samples=100
        )
        
        # 验证：不应该被判定为改进
        assert is_improvement is False, \
            "有指标恶化的补丁不应该被判定为改进"
    
    @given(
        old_error_rate=st.floats(min_value=0.10, max_value=0.50),
        improvement_delta=st.floats(min_value=0.01, max_value=0.04),
        old_miss_rate=st.floats(min_value=0.10, max_value=0.50),
        old_review_rate=st.floats(min_value=0.10, max_value=0.50)
    )
    @settings(max_examples=100, deadline=None)
    def test_patch_rejected_if_improvement_insufficient(
        self,
        old_error_rate: float,
        improvement_delta: float,
        old_miss_rate: float,
        old_review_rate: float
    ):
        """
        属性：对于任意改进不足的补丁（< 5%），不应该被判定为改进
        
        **Feature: self-evolving-grading, Property 24: 补丁发布条件**
        **Validates: Requirements 9.4**
        """
        # 确保改进幅度不足
        assume(improvement_delta < 0.05)
        
        # 计算新的指标值（改进不足）
        new_error_rate = old_error_rate - improvement_delta
        new_miss_rate = old_miss_rate - improvement_delta
        new_review_rate = old_review_rate - improvement_delta
        
        # 确保新指标值有效
        assume(new_error_rate >= 0.0)
        assume(new_miss_rate >= 0.0)
        assume(new_review_rate >= 0.0)
        
        # 创建回归测试器
        tester = RegressionTester(
            improvement_threshold=0.05,
            max_degradation_rate=0.02
        )
        
        # 判断是否为改进
        is_improvement = tester.is_improvement(
            old_error_rate=old_error_rate,
            new_error_rate=new_error_rate,
            old_miss_rate=old_miss_rate,
            new_miss_rate=new_miss_rate,
            old_review_rate=old_review_rate,
            new_review_rate=new_review_rate,
            degraded_samples=1,
            total_samples=100
        )
        
        # 验证：不应该被判定为改进
        assert is_improvement is False, \
            f"改进幅度 {improvement_delta:.2%} < 5%，不应该被判定为改进"
    
    @given(
        old_error_rate=st.floats(min_value=0.10, max_value=0.50),
        improvement_delta=st.floats(min_value=0.05, max_value=0.20),
        degraded_samples=st.integers(min_value=3, max_value=10),
        total_samples=st.integers(min_value=100, max_value=200)
    )
    @settings(max_examples=100, deadline=None)
    def test_patch_rejected_if_too_many_degraded_samples(
        self,
        old_error_rate: float,
        improvement_delta: float,
        degraded_samples: int,
        total_samples: int
    ):
        """
        属性：对于任意退化样本过多的补丁（> 2%），不应该被判定为改进
        
        **Feature: self-evolving-grading, Property 24: 补丁发布条件**
        **Validates: Requirements 9.4**
        """
        # 确保退化率超过阈值
        degradation_rate = degraded_samples / total_samples
        assume(degradation_rate > 0.02)
        
        # 计算新的指标值（有显著改进）
        new_error_rate = old_error_rate - improvement_delta
        
        # 确保新指标值有效
        assume(new_error_rate >= 0.0)
        
        # 创建回归测试器
        tester = RegressionTester(
            improvement_threshold=0.05,
            max_degradation_rate=0.02
        )
        
        # 判断是否为改进
        is_improvement = tester.is_improvement(
            old_error_rate=old_error_rate,
            new_error_rate=new_error_rate,
            old_miss_rate=0.10,
            new_miss_rate=0.10,
            old_review_rate=0.20,
            new_review_rate=0.20,
            degraded_samples=degraded_samples,
            total_samples=total_samples
        )
        
        # 验证：不应该被判定为改进
        assert is_improvement is False, \
            f"退化样本比例 {degradation_rate:.2%} > 2%，不应该被判定为改进"
    
    @given(
        old_error_rate=st.floats(min_value=0.10, max_value=0.50),
        improvement_delta=st.floats(min_value=0.05, max_value=0.20),
        old_miss_rate=st.floats(min_value=0.10, max_value=0.50),
        old_review_rate=st.floats(min_value=0.10, max_value=0.50),
        degraded_samples=st.integers(min_value=0, max_value=2)
    )
    @settings(max_examples=100, deadline=None)
    def test_improvement_consistency(
        self,
        old_error_rate: float,
        improvement_delta: float,
        old_miss_rate: float,
        old_review_rate: float,
        degraded_samples: int
    ):
        """
        属性：对于任意满足所有条件的补丁，is_improvement 应该返回一致的结果
        
        **Feature: self-evolving-grading, Property 24: 补丁发布条件**
        **Validates: Requirements 9.4**
        """
        # 确保改进幅度足够
        assume(improvement_delta >= 0.05)
        
        # 计算新的指标值
        new_error_rate = old_error_rate - improvement_delta
        new_miss_rate = old_miss_rate
        new_review_rate = old_review_rate
        
        # 确保新指标值有效
        assume(new_error_rate >= 0.0)
        
        # 创建回归测试器
        tester = RegressionTester(
            improvement_threshold=0.05,
            max_degradation_rate=0.02
        )
        
        # 多次调用 is_improvement
        result1 = tester.is_improvement(
            old_error_rate=old_error_rate,
            new_error_rate=new_error_rate,
            old_miss_rate=old_miss_rate,
            new_miss_rate=new_miss_rate,
            old_review_rate=old_review_rate,
            new_review_rate=new_review_rate,
            degraded_samples=degraded_samples,
            total_samples=100
        )
        
        result2 = tester.is_improvement(
            old_error_rate=old_error_rate,
            new_error_rate=new_error_rate,
            old_miss_rate=old_miss_rate,
            new_miss_rate=new_miss_rate,
            old_review_rate=old_review_rate,
            new_review_rate=new_review_rate,
            degraded_samples=degraded_samples,
            total_samples=100
        )
        
        # 验证：结果应该一致
        assert result1 == result2, \
            "相同输入应该产生相同的判断结果"
    
    @given(
        old_error_rate=st.floats(min_value=0.10, max_value=0.50),
        new_error_rate=st.floats(min_value=0.05, max_value=0.45),
        old_miss_rate=st.floats(min_value=0.10, max_value=0.50),
        new_miss_rate=st.floats(min_value=0.05, max_value=0.45),
        old_review_rate=st.floats(min_value=0.10, max_value=0.50),
        new_review_rate=st.floats(min_value=0.05, max_value=0.45)
    )
    @settings(max_examples=100, deadline=None)
    def test_improvement_decision_deterministic(
        self,
        old_error_rate: float,
        new_error_rate: float,
        old_miss_rate: float,
        new_miss_rate: float,
        old_review_rate: float,
        new_review_rate: float
    ):
        """
        属性：对于任意指标组合，is_improvement 的判断应该是确定性的
        
        **Feature: self-evolving-grading, Property 24: 补丁发布条件**
        **Validates: Requirements 9.4**
        """
        # 创建回归测试器
        tester = RegressionTester()
        
        # 判断是否为改进
        result = tester.is_improvement(
            old_error_rate=old_error_rate,
            new_error_rate=new_error_rate,
            old_miss_rate=old_miss_rate,
            new_miss_rate=new_miss_rate,
            old_review_rate=old_review_rate,
            new_review_rate=new_review_rate,
            degraded_samples=1,
            total_samples=100
        )
        
        # 验证：结果应该是布尔值
        assert isinstance(result, bool), \
            "is_improvement 应该返回布尔值"
        
        # 验证：如果所有指标都恶化，结果应该是 False
        if (new_error_rate > old_error_rate and
            new_miss_rate > old_miss_rate and
            new_review_rate > old_review_rate):
            assert result is False, \
                "所有指标都恶化时，应该返回 False"
        
        # 验证：如果所有指标都显著改进，结果应该是 True
        if (old_error_rate - new_error_rate >= 0.05 and
            new_miss_rate <= old_miss_rate and
            new_review_rate <= old_review_rate):
            assert result is True, \
                "所有指标都显著改进时，应该返回 True"

