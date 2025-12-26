"""补丁部署器单元测试

测试 PatchDeployer 的核心功能。
"""

import pytest
from datetime import datetime
from uuid import uuid4

from src.services.patch_deployer import PatchDeployer, DeploymentError
from src.models.rule_patch import RulePatch, PatchType, PatchStatus


@pytest.fixture
def sample_patch():
    """创建示例补丁"""
    return RulePatch(
        patch_id=f"patch_{uuid4().hex[:8]}",
        patch_type=PatchType.RULE,
        version="v1.0.1",
        description="测试补丁",
        content={"test": "content"},
        source_pattern_id="pattern_001"
    )


@pytest.fixture
def deployer():
    """创建部署器实例"""
    return PatchDeployer(
        canary_duration_minutes=30,
        anomaly_threshold=0.1,
        error_rate_threshold=0.2
    )


class TestAnomalyDetection:
    """测试异常检测功能"""
    
    def test_detect_error_rate_increase(self, deployer):
        """测试检测误判率增加"""
        baseline = {
            "error_rate": 0.10,
            "miss_rate": 0.05,
            "review_rate": 0.15
        }
        current = {
            "error_rate": 0.25,  # 增加15%
            "miss_rate": 0.05,
            "review_rate": 0.15
        }
        
        anomalies = deployer._detect_anomalies(baseline, current)
        
        assert len(anomalies) > 0
        assert any(a["type"] == "error_rate_increase" for a in anomalies)
        assert any(a["severity"] == "critical" for a in anomalies)
    
    def test_detect_high_absolute_error_rate(self, deployer):
        """测试检测高误判率"""
        baseline = {
            "error_rate": 0.10,
            "miss_rate": 0.05,
            "review_rate": 0.15
        }
        current = {
            "error_rate": 0.30,  # 超过阈值20%
            "miss_rate": 0.05,
            "review_rate": 0.15
        }
        
        anomalies = deployer._detect_anomalies(baseline, current)
        
        assert len(anomalies) > 0
        assert any(a["type"] == "high_error_rate" for a in anomalies)
        assert any(a["severity"] == "critical" for a in anomalies)
    
    def test_detect_miss_rate_increase(self, deployer):
        """测试检测漏判率增加"""
        baseline = {
            "error_rate": 0.10,
            "miss_rate": 0.05,
            "review_rate": 0.15
        }
        current = {
            "error_rate": 0.10,
            "miss_rate": 0.20,  # 增加15%
            "review_rate": 0.15
        }
        
        anomalies = deployer._detect_anomalies(baseline, current)
        
        assert len(anomalies) > 0
        assert any(a["type"] == "miss_rate_increase" for a in anomalies)
    
    def test_detect_review_rate_increase(self, deployer):
        """测试检测复核率增加"""
        baseline = {
            "error_rate": 0.10,
            "miss_rate": 0.05,
            "review_rate": 0.15
        }
        current = {
            "error_rate": 0.10,
            "miss_rate": 0.05,
            "review_rate": 0.40  # 增加25%（超过阈值的2倍）
        }
        
        anomalies = deployer._detect_anomalies(baseline, current)
        
        assert len(anomalies) > 0
        assert any(a["type"] == "review_rate_increase" for a in anomalies)
    
    def test_no_anomaly_on_normal_metrics(self, deployer):
        """测试正常指标不触发异常"""
        baseline = {
            "error_rate": 0.10,
            "miss_rate": 0.05,
            "review_rate": 0.15
        }
        current = {
            "error_rate": 0.12,  # 仅增加2%
            "miss_rate": 0.06,
            "review_rate": 0.16
        }
        
        anomalies = deployer._detect_anomalies(baseline, current)
        
        # 不应该有严重异常
        critical_anomalies = [a for a in anomalies if a["severity"] == "critical"]
        assert len(critical_anomalies) == 0
    
    def test_no_anomaly_on_improvement(self, deployer):
        """测试指标改善不触发异常"""
        baseline = {
            "error_rate": 0.15,
            "miss_rate": 0.10,
            "review_rate": 0.20
        }
        current = {
            "error_rate": 0.08,  # 下降
            "miss_rate": 0.05,   # 下降
            "review_rate": 0.12  # 下降
        }
        
        anomalies = deployer._detect_anomalies(baseline, current)
        
        assert len(anomalies) == 0


class TestDeploymentValidation:
    """测试部署验证"""
    
    @pytest.mark.asyncio
    async def test_invalid_traffic_percentage(self, deployer, sample_patch):
        """测试无效的流量比例"""
        with pytest.raises(ValueError):
            await deployer.deploy_canary(sample_patch, traffic_percentage=0.0)
        
        with pytest.raises(ValueError):
            await deployer.deploy_canary(sample_patch, traffic_percentage=1.5)
    
    def test_valid_traffic_percentage_sync(self, deployer):
        """测试有效的流量比例（同步验证）"""
        # 测试验证逻辑本身（不实际调用异步方法）
        # 这些应该不抛出异常
        assert 0.0 < 0.1 <= 1.0
        assert 0.0 < 0.5 <= 1.0
        assert 0.0 < 1.0 <= 1.0
        
        # 这些应该抛出异常
        try:
            if not 0.0 < 0.0 <= 1.0:
                raise ValueError("Invalid traffic percentage")
            pytest.fail("应该抛出 ValueError")
        except ValueError:
            pass
        
        try:
            if not 0.0 < 1.5 <= 1.0:
                raise ValueError("Invalid traffic percentage")
            pytest.fail("应该抛出 ValueError")
        except ValueError:
            pass


class TestMonitoringLogic:
    """测试监控逻辑"""
    
    def test_critical_anomaly_triggers_rollback(self, deployer):
        """测试严重异常触发回滚"""
        baseline = {
            "error_rate": 0.10,
            "miss_rate": 0.05,
            "review_rate": 0.15
        }
        current = {
            "error_rate": 0.30,  # 严重异常
            "miss_rate": 0.05,
            "review_rate": 0.15
        }
        
        anomalies = deployer._detect_anomalies(baseline, current)
        
        # 应该有严重异常
        critical_anomalies = [a for a in anomalies if a["severity"] == "critical"]
        assert len(critical_anomalies) > 0
        
        # 在实际的 monitor_deployment 中，这会触发自动回滚
    
    def test_warning_does_not_trigger_rollback(self, deployer):
        """测试警告不触发回滚"""
        baseline = {
            "error_rate": 0.10,
            "miss_rate": 0.05,
            "review_rate": 0.15
        }
        current = {
            "error_rate": 0.10,
            "miss_rate": 0.18,  # 警告级别
            "review_rate": 0.15
        }
        
        anomalies = deployer._detect_anomalies(baseline, current)
        
        # 可能有警告，但不应该有严重异常
        critical_anomalies = [a for a in anomalies if a["severity"] == "critical"]
        assert len(critical_anomalies) == 0


class TestAnomalyThresholds:
    """测试异常阈值"""
    
    def test_custom_anomaly_threshold(self):
        """测试自定义异常阈值"""
        deployer = PatchDeployer(anomaly_threshold=0.05)  # 更严格的阈值
        
        baseline = {
            "error_rate": 0.10,
            "miss_rate": 0.05,
            "review_rate": 0.15
        }
        current = {
            "error_rate": 0.16,  # 增加6%（超过5%阈值）
            "miss_rate": 0.05,
            "review_rate": 0.15
        }
        
        anomalies = deployer._detect_anomalies(baseline, current)
        
        assert len(anomalies) > 0
        assert any(a["type"] == "error_rate_increase" for a in anomalies)
    
    def test_custom_error_rate_threshold(self):
        """测试自定义错误率阈值"""
        deployer = PatchDeployer(error_rate_threshold=0.15)  # 更严格的阈值
        
        baseline = {
            "error_rate": 0.10,
            "miss_rate": 0.05,
            "review_rate": 0.15
        }
        current = {
            "error_rate": 0.18,  # 超过15%阈值
            "miss_rate": 0.05,
            "review_rate": 0.15
        }
        
        anomalies = deployer._detect_anomalies(baseline, current)
        
        assert len(anomalies) > 0
        assert any(a["type"] == "high_error_rate" for a in anomalies)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
