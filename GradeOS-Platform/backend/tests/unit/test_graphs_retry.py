"""Graph Retry 单元测试"""

import pytest
import asyncio
from src.graphs.retry import (
    RetryConfig,
    with_retry,
    create_retryable_node,
    DEFAULT_RETRY_CONFIG,
    LLM_API_RETRY_CONFIG,
)
from src.graphs.state import GradingGraphState


def test_retry_config_calculate_interval():
    """测试重试间隔计算"""
    config = RetryConfig(
        initial_interval=1.0,
        backoff_coefficient=2.0,
        maximum_interval=60.0
    )
    
    # 第 0 次重试：1.0 * 2^0 = 1.0
    assert config.calculate_interval(0) == 1.0
    
    # 第 1 次重试：1.0 * 2^1 = 2.0
    assert config.calculate_interval(1) == 2.0
    
    # 第 2 次重试：1.0 * 2^2 = 4.0
    assert config.calculate_interval(2) == 4.0
    
    # 第 10 次重试：应该被限制在 maximum_interval
    assert config.calculate_interval(10) == 60.0


@pytest.mark.asyncio
async def test_with_retry_success():
    """测试成功执行（无需重试）"""
    call_count = 0
    
    async def success_func():
        nonlocal call_count
        call_count += 1
        return "success"
    
    config = RetryConfig(maximum_attempts=3)
    result = await with_retry(success_func, config)
    
    assert result == "success"
    assert call_count == 1  # 只调用一次


@pytest.mark.asyncio
async def test_with_retry_eventual_success():
    """测试最终成功（需要重试）"""
    call_count = 0
    
    async def flaky_func():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise RuntimeError("临时错误")
        return "success"
    
    config = RetryConfig(
        initial_interval=0.01,  # 快速测试
        maximum_attempts=3
    )
    result = await with_retry(flaky_func, config)
    
    assert result == "success"
    assert call_count == 3  # 重试 2 次后成功


@pytest.mark.asyncio
async def test_with_retry_all_failed():
    """测试所有重试都失败"""
    call_count = 0
    
    async def always_fail():
        nonlocal call_count
        call_count += 1
        raise RuntimeError("永久错误")
    
    config = RetryConfig(
        initial_interval=0.01,
        maximum_attempts=3
    )
    
    with pytest.raises(RuntimeError, match="永久错误"):
        await with_retry(always_fail, config)
    
    assert call_count == 3  # 尝试了 3 次


@pytest.mark.asyncio
async def test_with_retry_non_retryable_error():
    """测试不可重试错误"""
    call_count = 0
    
    async def value_error_func():
        nonlocal call_count
        call_count += 1
        raise ValueError("不可重试")
    
    config = RetryConfig(
        maximum_attempts=3,
        non_retryable_errors=[ValueError]
    )
    
    with pytest.raises(ValueError, match="不可重试"):
        await with_retry(value_error_func, config)
    
    assert call_count == 1  # 只调用一次，不重试


@pytest.mark.asyncio
async def test_with_retry_timeout():
    """测试超时"""
    async def slow_func():
        await asyncio.sleep(1.0)
        return "success"
    
    config = RetryConfig(
        timeout=0.1,  # 100ms 超时
        initial_interval=0.01,
        maximum_attempts=2
    )
    
    with pytest.raises(asyncio.TimeoutError):
        await with_retry(slow_func, config)


@pytest.mark.asyncio
async def test_create_retryable_node_success():
    """测试创建可重试节点 - 成功场景"""
    async def test_node(state: GradingGraphState) -> GradingGraphState:
        return {**state, "current_stage": "completed"}
    
    config = RetryConfig(maximum_attempts=3)
    retryable = create_retryable_node(test_node, config)
    
    state: GradingGraphState = {
        "job_id": "test",
        "current_stage": "initial"
    }
    
    result = await retryable(state)
    assert result["current_stage"] == "completed"


@pytest.mark.asyncio
async def test_create_retryable_node_with_fallback():
    """测试创建可重试节点 - 带降级逻辑"""
    async def failing_node(state: GradingGraphState) -> GradingGraphState:
        raise RuntimeError("节点失败")
    
    async def fallback_node(state: GradingGraphState, error: Exception) -> GradingGraphState:
        return {**state, "current_stage": "fallback", "error": str(error)}
    
    config = RetryConfig(
        initial_interval=0.01,
        maximum_attempts=2
    )
    retryable = create_retryable_node(failing_node, config, fallback_func=fallback_node)
    
    state: GradingGraphState = {
        "job_id": "test",
        "current_stage": "initial"
    }
    
    result = await retryable(state)
    assert result["current_stage"] == "fallback"
    assert "节点失败" in result["error"]


@pytest.mark.asyncio
async def test_create_retryable_node_error_recording():
    """测试创建可重试节点 - 错误记录"""
    async def failing_node(state: GradingGraphState) -> GradingGraphState:
        raise RuntimeError("测试错误")
    
    config = RetryConfig(
        initial_interval=0.01,
        maximum_attempts=2
    )
    retryable = create_retryable_node(failing_node, config)
    
    state: GradingGraphState = {
        "job_id": "test",
        "errors": [],
        "retry_count": 0
    }
    
    result = await retryable(state)
    
    # 验证错误被记录
    assert len(result["errors"]) == 1
    assert result["errors"][0]["error_type"] == "RuntimeError"
    assert result["errors"][0]["error_message"] == "测试错误"
    assert result["retry_count"] == 1


def test_predefined_configs():
    """测试预定义配置"""
    # 验证默认配置
    assert DEFAULT_RETRY_CONFIG.maximum_attempts == 3
    assert DEFAULT_RETRY_CONFIG.initial_interval == 1.0
    
    # 验证 Gemini API 配置
    assert LLM_API_RETRY_CONFIG.maximum_attempts == 5
    assert LLM_API_RETRY_CONFIG.timeout == 300.0
    assert ValueError in LLM_API_RETRY_CONFIG.non_retryable_errors
