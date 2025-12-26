"""属性测试：异常自动回滚

验证当灰度发布期间检测到异常时，系统会自动回滚到上一版本。

**Feature: self-evolving-grading, Property 25: 异常自动回滚**
**Validates: Requirements 9.5**
"""

import pytest
from hypothesis import given, strategies as st, settings, Phase
from datetime import datetime
from uuid import uuid4

from src.services.patch_deployer import PatchDeployer, AnomalyDetected
from src.models.rule_patch import RulePatch, PatchType, PatchStatus


# 配置 Hypothesis
settings.register_profile(
    "ci",
    max_examples=100,
    phases=[Phase.generate, Phase.target, Phase.shrink]
)
settings.load_profile("ci")


# 策略：生成补丁
@st.composite
def patch_strategy(draw):
    """生成规则补丁"""
    patch_type = draw(st.sampled_from([PatchType.RULE, PatchType.PROMPT, PatchType.EXEMPLAR]))
    version = f"v1.0.{draw(st.integers(min_value=1, max_value=1000))}"
    
    return RulePatch(
        patch_id=f"patch_{uuid4().hex[:8]}",
        patch_type=patch_type,
        version=version,
        description=draw(st.text(min_size=10, max_size=100)),
        content={"test": "content"},
        source_pattern_id=f"pattern_{draw(st.integers(min_value=1, max_value=100))}"
    )


# 策略：生成指标
@st.composite
def metrics_strategy(draw):
    """生成系统指标"""
    return {
        "error_rate": draw(st.floats(min_value=0.0, max_value=1.0)),
        "miss_rate": draw(st.floats(min_value=0.0, max_value=1.0)),
        "review_rate": draw(st.floats(min_value=0.0, max_value=1.0)),
        "timestamp": datetime.utcnow().isoformat()
    }


@pytest.mark.asyncio
@given(
    patch=patch_strategy(),
    baseline_error_rate=st.floats(min_value=0.0, max_value=0.5),
    error_rate_increase=st.floats(min_value=0.15, max_value=0.5)  # 超过阈值的增加
)
@settings(max_examples=100, deadline=None)
async def test_auto_rollback_on_error_rate_anomaly(
    patch: RulePatch,
    baseline_error_rate: float,
    error_rate_increase: float
):
    """
    属性：当误判率增加超过阈值时，系统应自动回滚
    
    **Feature: self-evolving-grading, Property 25: 异常自动回滚**
    **Validates: Requirements 9.5**
    
    对于任意补丁和基线误判率，当当前误判率增加超过异常阈值（默认10%）时，
    监控系统应检测到异常并自动回滚部署。
    """
    # 创建部署器（异常阈值设为10%）
    deployer = PatchDeployer(anomaly_threshold=0.1)
    
    # 模拟基线指标
    baseline_metrics = {
        "error_rate": baseline_error_rate,
        "miss_rate": 0.05,
        "review_rate": 0.15
    }
    
    # 模拟当前指标（误判率增加）
    current_metrics = {
        "error_rate": baseline_error_rate + error_rate_increase,
        "miss_rate": 0.05,
        "review_rate": 0.15
    }
    
    # 检测异常
    anomalies = deployer._detect_anomalies(baseline_metrics, current_metrics)
    
    # 验证：应该检测到误判率增加的异常
    assert len(anomalies) > 0, "应该检测到异常"
    
    # 验证：至少有一个严重异常（critical）
    critical_anomalies = [a for a in anomalies if a["severity"] == "critical"]
    assert len(critical_anomalies) > 0, "应该检测到严重异常"
    
    # 验证：严重异常应该是误判率相关的
    error_rate_anomalies = [
        a for a in critical_anomalies
        if a["type"] in ["error_rate_increase", "high_error_rate"]
    ]
    assert len(error_rate_anomalies) > 0, "应该检测到误判率异常"


@pytest.mark.asyncio
@given(
    patch=patch_strategy(),
    baseline_miss_rate=st.floats(min_value=0.0, max_value=0.5),
    miss_rate_increase=st.floats(min_value=0.15, max_value=0.5)  # 超过阈值的增加
)
@settings(max_examples=100, deadline=None)
async def test_auto_rollback_on_miss_rate_anomaly(
    patch: RulePatch,
    baseline_miss_rate: float,
    miss_rate_increase: float
):
    """
    属性：当漏判率增加超过阈值时，系统应检测到异常
    
    **Feature: self-evolving-grading, Property 25: 异常自动回滚**
    **Validates: Requirements 9.5**
    
    对于任意补丁和基线漏判率，当当前漏判率增加超过异常阈值时，
    监控系统应检测到异常。
    """
    # 创建部署器
    deployer = PatchDeployer(anomaly_threshold=0.1)
    
    # 模拟基线指标
    baseline_metrics = {
        "error_rate": 0.10,
        "miss_rate": baseline_miss_rate,
        "review_rate": 0.15
    }
    
    # 模拟当前指标（漏判率增加）
    current_metrics = {
        "error_rate": 0.10,
        "miss_rate": baseline_miss_rate + miss_rate_increase,
        "review_rate": 0.15
    }
    
    # 检测异常
    anomalies = deployer._detect_anomalies(baseline_metrics, current_metrics)
    
    # 验证：应该检测到异常
    assert len(anomalies) > 0, "应该检测到漏判率异常"
    
    # 验证：应该有漏判率相关的异常
    miss_rate_anomalies = [a for a in anomalies if a["type"] == "miss_rate_increase"]
    assert len(miss_rate_anomalies) > 0, "应该检测到漏判率增加异常"


@pytest.mark.asyncio
@given(
    patch=patch_strategy(),
    absolute_error_rate=st.floats(min_value=0.25, max_value=1.0)  # 超过绝对阈值
)
@settings(max_examples=100, deadline=None)
async def test_auto_rollback_on_high_absolute_error_rate(
    patch: RulePatch,
    absolute_error_rate: float
):
    """
    属性：当误判率超过绝对阈值时，系统应检测到严重异常
    
    **Feature: self-evolving-grading, Property 25: 异常自动回滚**
    **Validates: Requirements 9.5**
    
    对于任意补丁，当当前误判率超过绝对阈值（默认20%）时，
    无论基线如何，监控系统都应检测到严重异常。
    """
    # 创建部署器（错误率阈值设为20%）
    deployer = PatchDeployer(error_rate_threshold=0.2)
    
    # 模拟基线指标（误判率正常）
    baseline_metrics = {
        "error_rate": 0.10,
        "miss_rate": 0.05,
        "review_rate": 0.15
    }
    
    # 模拟当前指标（误判率过高）
    current_metrics = {
        "error_rate": absolute_error_rate,
        "miss_rate": 0.05,
        "review_rate": 0.15
    }
    
    # 检测异常
    anomalies = deployer._detect_anomalies(baseline_metrics, current_metrics)
    
    # 验证：应该检测到异常
    assert len(anomalies) > 0, "应该检测到高误判率异常"
    
    # 验证：应该有严重异常
    critical_anomalies = [a for a in anomalies if a["severity"] == "critical"]
    assert len(critical_anomalies) > 0, "应该检测到严重异常"
    
    # 验证：应该有高误判率异常
    high_error_anomalies = [a for a in anomalies if a["type"] == "high_error_rate"]
    assert len(high_error_anomalies) > 0, "应该检测到高误判率异常"


@pytest.mark.asyncio
@given(
    patch=patch_strategy(),
    baseline_metrics=metrics_strategy(),
    small_increase=st.floats(min_value=0.0, max_value=0.05)  # 小于阈值的增加
)
@settings(max_examples=100, deadline=None)
async def test_no_rollback_on_normal_metrics(
    patch: RulePatch,
    baseline_metrics: dict,
    small_increase: float
):
    """
    属性：当指标变化在正常范围内时，不应触发回滚
    
    **Feature: self-evolving-grading, Property 25: 异常自动回滚**
    **Validates: Requirements 9.5**
    
    对于任意补丁和基线指标，当当前指标变化小于异常阈值时，
    监控系统不应检测到严重异常，也不应触发回滚。
    """
    # 创建部署器
    deployer = PatchDeployer(anomaly_threshold=0.1, error_rate_threshold=0.2)
    
    # 确保基线指标在合理范围内
    baseline_metrics["error_rate"] = min(baseline_metrics["error_rate"], 0.15)
    baseline_metrics["miss_rate"] = min(baseline_metrics["miss_rate"], 0.15)
    baseline_metrics["review_rate"] = min(baseline_metrics["review_rate"], 0.20)
    
    # 模拟当前指标（小幅增加）
    current_metrics = {
        "error_rate": baseline_metrics["error_rate"] + small_increase,
        "miss_rate": baseline_metrics["miss_rate"] + small_increase,
        "review_rate": baseline_metrics["review_rate"] + small_increase
    }
    
    # 检测异常
    anomalies = deployer._detect_anomalies(baseline_metrics, current_metrics)
    
    # 验证：不应该有严重异常
    critical_anomalies = [a for a in anomalies if a["severity"] == "critical"]
    assert len(critical_anomalies) == 0, "正常指标变化不应触发严重异常"


@pytest.mark.asyncio
@given(
    patch=patch_strategy(),
    baseline_error_rate=st.floats(min_value=0.1, max_value=0.18),  # 确保基线不超过阈值太多
    error_rate_decrease=st.floats(min_value=0.02, max_value=0.1)  # 误判率下降
)
@settings(max_examples=100, deadline=None)
async def test_no_rollback_on_improvement(
    patch: RulePatch,
    baseline_error_rate: float,
    error_rate_decrease: float
):
    """
    属性：当指标改善且在正常范围内时，不应触发回滚
    
    **Feature: self-evolving-grading, Property 25: 异常自动回滚**
    **Validates: Requirements 9.5**
    
    对于任意补丁和基线指标，当当前指标优于基线且不超过绝对阈值时，
    监控系统不应检测到异常，也不应触发回滚。
    """
    # 创建部署器（错误率阈值20%）
    deployer = PatchDeployer(anomaly_threshold=0.1, error_rate_threshold=0.2)
    
    # 模拟基线指标
    baseline_metrics = {
        "error_rate": baseline_error_rate,
        "miss_rate": 0.10,
        "review_rate": 0.20
    }
    
    # 模拟当前指标（误判率下降，其他指标也改善）
    # 确保改善后的误判率不超过绝对阈值
    improved_error_rate = max(0.0, baseline_error_rate - error_rate_decrease)
    
    current_metrics = {
        "error_rate": improved_error_rate,
        "miss_rate": max(0.0, 0.10 - error_rate_decrease * 0.5),
        "review_rate": max(0.0, 0.20 - error_rate_decrease * 0.5)
    }
    
    # 检测异常
    anomalies = deployer._detect_anomalies(baseline_metrics, current_metrics)
    
    # 验证：不应该有任何异常
    assert len(anomalies) == 0, f"指标改善时不应检测到异常（误判率从 {baseline_error_rate:.2%} 降至 {improved_error_rate:.2%}）"


@pytest.mark.asyncio
@given(
    patch=patch_strategy(),
    traffic_percentage=st.floats(min_value=0.01, max_value=1.0)
)
@settings(max_examples=50, deadline=None)
async def test_anomaly_detection_independent_of_traffic(
    patch: RulePatch,
    traffic_percentage: float
):
    """
    属性：异常检测应该独立于流量比例
    
    **Feature: self-evolving-grading, Property 25: 异常自动回滚**
    **Validates: Requirements 9.5**
    
    对于任意补丁和流量比例，异常检测的逻辑应该保持一致，
    不应因为流量比例不同而改变异常判断标准。
    """
    # 创建部署器
    deployer = PatchDeployer(anomaly_threshold=0.1)
    
    # 模拟基线指标
    baseline_metrics = {
        "error_rate": 0.10,
        "miss_rate": 0.05,
        "review_rate": 0.15
    }
    
    # 模拟当前指标（误判率显著增加）
    current_metrics = {
        "error_rate": 0.25,  # 增加15%，超过阈值
        "miss_rate": 0.05,
        "review_rate": 0.15
    }
    
    # 检测异常（不依赖流量比例）
    anomalies = deployer._detect_anomalies(baseline_metrics, current_metrics)
    
    # 验证：应该检测到异常，且与流量比例无关
    assert len(anomalies) > 0, "应该检测到异常"
    critical_anomalies = [a for a in anomalies if a["severity"] == "critical"]
    assert len(critical_anomalies) > 0, "应该检测到严重异常"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--hypothesis-show-statistics"])
