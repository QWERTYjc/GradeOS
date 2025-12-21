"""回归测试器单元测试"""

import pytest
from src.services.regression_tester import RegressionTester
from src.models.rule_patch import RulePatch, PatchType


class TestRegressionTester:
    """回归测试器单元测试"""
    
    @pytest.fixture
    def tester(self):
        """创建测试器实例"""
        return RegressionTester(
            improvement_threshold=0.05,
            max_degradation_rate=0.02
        )
    
    @pytest.fixture
    def sample_patch(self):
        """创建示例补丁"""
        return RulePatch(
            patch_type=PatchType.RULE,
            version="v1.0.0",
            description="测试补丁",
            content={"test": "data"},
            source_pattern_id="pattern_001"
        )
    
    def test_is_improvement_all_metrics_improved(self, tester):
        """测试：所有指标都改进"""
        result = tester.is_improvement(
            old_error_rate=0.15,
            new_error_rate=0.08,
            old_miss_rate=0.10,
            new_miss_rate=0.05,
            old_review_rate=0.20,
            new_review_rate=0.12,
            degraded_samples=1,
            total_samples=100
        )
        assert result is True
    
    def test_is_improvement_one_metric_improved(self, tester):
        """测试：只有一项指标改进"""
        result = tester.is_improvement(
            old_error_rate=0.15,
            new_error_rate=0.08,  # 改进7%
            old_miss_rate=0.10,
            new_miss_rate=0.10,   # 不变
            old_review_rate=0.20,
            new_review_rate=0.20, # 不变
            degraded_samples=1,
            total_samples=100
        )
        assert result is True
    
    def test_is_improvement_insufficient_improvement(self, tester):
        """测试：改进不足"""
        result = tester.is_improvement(
            old_error_rate=0.15,
            new_error_rate=0.14,  # 仅改进1%
            old_miss_rate=0.10,
            new_miss_rate=0.09,   # 仅改进1%
            old_review_rate=0.20,
            new_review_rate=0.19, # 仅改进1%
            degraded_samples=1,
            total_samples=100
        )
        assert result is False
    
    def test_is_improvement_metric_degraded(self, tester):
        """测试：有指标恶化"""
        result = tester.is_improvement(
            old_error_rate=0.15,
            new_error_rate=0.08,  # 改进7%
            old_miss_rate=0.10,
            new_miss_rate=0.15,   # 恶化5%
            old_review_rate=0.20,
            new_review_rate=0.12, # 改进8%
            degraded_samples=1,
            total_samples=100
        )
        assert result is False
    
    def test_is_improvement_too_many_degraded_samples(self, tester):
        """测试：退化样本过多"""
        result = tester.is_improvement(
            old_error_rate=0.15,
            new_error_rate=0.08,
            old_miss_rate=0.10,
            new_miss_rate=0.05,
            old_review_rate=0.20,
            new_review_rate=0.12,
            degraded_samples=5,  # 5%退化，超过2%阈值
            total_samples=100
        )
        assert result is False
    
    def test_is_improvement_at_threshold(self, tester):
        """测试：刚好达到改进阈值"""
        result = tester.is_improvement(
            old_error_rate=0.15,
            new_error_rate=0.10,  # 刚好改进5%
            old_miss_rate=0.10,
            new_miss_rate=0.10,
            old_review_rate=0.20,
            new_review_rate=0.20,
            degraded_samples=1,
            total_samples=100
        )
        assert result is True
    
    def test_is_improvement_zero_samples(self, tester):
        """测试：零样本情况"""
        result = tester.is_improvement(
            old_error_rate=0.15,
            new_error_rate=0.08,
            old_miss_rate=0.10,
            new_miss_rate=0.05,
            old_review_rate=0.20,
            new_review_rate=0.12,
            degraded_samples=0,
            total_samples=0
        )
        assert result is True  # 零样本时不检查退化率
    
    def test_calculate_metrics_empty_input(self, tester):
        """测试：空输入的指标计算"""
        metrics = tester._calculate_metrics([], [])
        assert metrics["error_rate"] == 0.0
        assert metrics["miss_rate"] == 0.0
        assert metrics["review_rate"] == 0.0
    
    def test_calculate_metrics_normal_case(self, tester):
        """测试：正常情况的指标计算"""
        samples = [
            {"sample_id": "1", "ground_truth_score": 8.0, "max_score": 10.0},
            {"sample_id": "2", "ground_truth_score": 9.0, "max_score": 10.0},
            {"sample_id": "3", "ground_truth_score": 7.0, "max_score": 10.0},
            {"sample_id": "4", "ground_truth_score": 10.0, "max_score": 10.0},
        ]
        results = [
            {"sample_id": "1", "predicted_score": 6.0, "confidence": 0.9},  # 误判（差2分）
            {"sample_id": "2", "predicted_score": 10.0, "confidence": 0.9}, # 漏判（应该扣分但给了满分）
            {"sample_id": "3", "predicted_score": 7.5, "confidence": 0.7},  # 低置信度
            {"sample_id": "4", "predicted_score": 10.0, "confidence": 0.95},
        ]
        
        metrics = tester._calculate_metrics(samples, results)
        assert metrics["error_rate"] == 0.25  # 1/4（样本1）
        assert metrics["miss_rate"] == 0.25   # 1/4（样本2）
        assert metrics["review_rate"] == 0.25 # 1/4（样本3）
    
    def test_compare_samples_improvements(self, tester):
        """测试：样本对比 - 改进情况"""
        samples = [
            {"sample_id": "1", "ground_truth_score": 8.0},
            {"sample_id": "2", "ground_truth_score": 9.0},
        ]
        old_results = [
            {"sample_id": "1", "predicted_score": 6.0},  # 误差2.0
            {"sample_id": "2", "predicted_score": 7.0},  # 误差2.0
        ]
        new_results = [
            {"sample_id": "1", "predicted_score": 8.0},  # 误差0.0（改进）
            {"sample_id": "2", "predicted_score": 9.5},  # 误差0.5（改进）
        ]
        
        improved, degraded = tester._compare_samples(samples, old_results, new_results)
        assert improved == 2
        assert degraded == 0
    
    def test_compare_samples_degradations(self, tester):
        """测试：样本对比 - 退化情况"""
        samples = [
            {"sample_id": "1", "ground_truth_score": 8.0},
            {"sample_id": "2", "ground_truth_score": 9.0},
        ]
        old_results = [
            {"sample_id": "1", "predicted_score": 8.0},  # 误差0.0
            {"sample_id": "2", "predicted_score": 9.0},  # 误差0.0
        ]
        new_results = [
            {"sample_id": "1", "predicted_score": 6.0},  # 误差2.0（退化）
            {"sample_id": "2", "predicted_score": 7.0},  # 误差2.0（退化）
        ]
        
        improved, degraded = tester._compare_samples(samples, old_results, new_results)
        assert improved == 0
        assert degraded == 2
    
    @pytest.mark.asyncio
    async def test_run_regression_empty_eval_set(self, tester, sample_patch):
        """测试：空评测集"""
        result = await tester.run_regression(
            patch=sample_patch,
            eval_set_id="empty_eval"
        )
        
        assert result.patch_id == sample_patch.patch_id
        assert result.passed is False
        assert result.total_samples == 0
        assert result.improved_samples == 0
        assert result.degraded_samples == 0
    
    def test_custom_thresholds(self):
        """测试：自定义阈值"""
        custom_tester = RegressionTester(
            improvement_threshold=0.03,
            max_degradation_rate=0.05
        )
        
        # 3%改进应该通过
        result = custom_tester.is_improvement(
            old_error_rate=0.15,
            new_error_rate=0.12,  # 改进3%
            old_miss_rate=0.10,
            new_miss_rate=0.10,
            old_review_rate=0.20,
            new_review_rate=0.20,
            degraded_samples=4,  # 4%退化（在5%阈值内）
            total_samples=100
        )
        assert result is True

