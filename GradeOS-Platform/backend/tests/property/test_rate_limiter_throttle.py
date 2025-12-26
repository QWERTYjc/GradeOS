"""限流器节流的属性测试

**功能: ai-grading-agent, 属性 14: 限流器节流**
**验证: 需求 8.3**

属性定义：
对于任意时间窗口内超过配置限制的 N 个请求序列，
限流器应当拒绝超出限制的请求并返回节流响应。
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from src.services.rate_limiter import RateLimiter


# ============================================================================
# 辅助函数
# ============================================================================

def create_mock_redis_with_counter():
    """
    创建一个带有计数器的 Mock Redis 客户端
    
    Returns:
        (mock_redis, counter_dict) 元组
    """
    mock_redis = MagicMock()
    counters = {}
    
    def get_counter_key(key):
        """从完整键中提取基础键"""
        # 键格式: prefix:key:timestamp
        parts = key.split(':')
        if len(parts) >= 2:
            return parts[1]  # 返回 key 部分
        return key
    
    @asynccontextmanager
    async def mock_pipeline(*args, **kwargs):
        """模拟 Redis Pipeline 的异步上下文管理器"""
        pipe = MagicMock()
        current_key = [None]
        
        def mock_incr(key):
            current_key[0] = get_counter_key(key)
            if current_key[0] not in counters:
                counters[current_key[0]] = 0
        
        async def mock_execute():
            if current_key[0] is not None:
                counters[current_key[0]] = counters.get(current_key[0], 0) + 1
                return [counters[current_key[0]], True]
            return [1, True]
        
        pipe.incr = mock_incr
        pipe.expire = MagicMock()
        pipe.execute = mock_execute
        
        yield pipe
    
    mock_redis.pipeline = mock_pipeline
    
    async def mock_get(key):
        base_key = get_counter_key(key)
        count = counters.get(base_key, 0)
        return str(count).encode() if count > 0 else None
    
    mock_redis.get = mock_get
    
    return mock_redis, counters


# ============================================================================
# 属性测试
# ============================================================================

class TestRateLimiterThrottle:
    """限流器节流的属性测试"""

    @settings(max_examples=100, deadline=None)
    @given(
        max_requests=st.integers(min_value=1, max_value=50),
        window_seconds=st.integers(min_value=1, max_value=3600),
        key=st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=('L', 'N')))
    )
    @pytest.mark.asyncio
    async def test_requests_within_limit_are_allowed(
        self,
        max_requests: int,
        window_seconds: int,
        key: str
    ):
        """
        **功能: ai-grading-agent, 属性 14: 限流器节流**
        **验证: 需求 8.3**
        
        验证：在限制内的请求应当被允许。
        对于任意 max_requests 配置，前 max_requests 个请求都应该返回 True。
        """
        assume(len(key.strip()) > 0)
        
        # 创建 Mock Redis 客户端
        mock_redis, counters = create_mock_redis_with_counter()
        
        # 创建限流器
        rate_limiter = RateLimiter(redis_client=mock_redis, key_prefix="test")
        
        # 发送 max_requests 个请求，所有请求都应该被允许
        results = []
        for _ in range(max_requests):
            result = await rate_limiter.acquire(
                key=key,
                max_requests=max_requests,
                window_seconds=window_seconds
            )
            results.append(result)
        
        # 验证：所有请求都被允许
        assert all(results), f"前 {max_requests} 个请求应该全部被允许，但结果为 {results}"

    @settings(max_examples=100, deadline=None)
    @given(
        max_requests=st.integers(min_value=1, max_value=50),
        window_seconds=st.integers(min_value=1, max_value=3600),
        extra_requests=st.integers(min_value=1, max_value=20),
        key=st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=('L', 'N')))
    )
    @pytest.mark.asyncio
    async def test_requests_exceeding_limit_are_rejected(
        self,
        max_requests: int,
        window_seconds: int,
        extra_requests: int,
        key: str
    ):
        """
        **功能: ai-grading-agent, 属性 14: 限流器节流**
        **验证: 需求 8.3**
        
        验证：超出限制的请求应当被拒绝。
        对于任意 N > max_requests 的请求序列，第 N 个请求应该返回 False。
        """
        assume(len(key.strip()) > 0)
        
        # 创建 Mock Redis 客户端
        mock_redis, counters = create_mock_redis_with_counter()
        
        # 创建限流器
        rate_limiter = RateLimiter(redis_client=mock_redis, key_prefix="test")
        
        total_requests = max_requests + extra_requests
        allowed_count = 0
        rejected_count = 0
        
        # 发送超过限制的请求
        for _ in range(total_requests):
            result = await rate_limiter.acquire(
                key=key,
                max_requests=max_requests,
                window_seconds=window_seconds
            )
            if result:
                allowed_count += 1
            else:
                rejected_count += 1
        
        # 验证：恰好 max_requests 个请求被允许
        assert allowed_count == max_requests, \
            f"应该恰好允许 {max_requests} 个请求，实际允许 {allowed_count} 个"
        
        # 验证：超出的请求被拒绝
        assert rejected_count == extra_requests, \
            f"应该拒绝 {extra_requests} 个请求，实际拒绝 {rejected_count} 个"

    @settings(max_examples=100, deadline=None)
    @given(
        max_requests=st.integers(min_value=1, max_value=50),
        window_seconds=st.integers(min_value=1, max_value=3600),
        key=st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=('L', 'N')))
    )
    @pytest.mark.asyncio
    async def test_boundary_request_is_allowed(
        self,
        max_requests: int,
        window_seconds: int,
        key: str
    ):
        """
        **功能: ai-grading-agent, 属性 14: 限流器节流**
        **验证: 需求 8.3**
        
        验证：恰好达到限制边界的请求应当被允许。
        第 max_requests 个请求应该返回 True，第 max_requests + 1 个应该返回 False。
        """
        assume(len(key.strip()) > 0)
        
        # 创建 Mock Redis 客户端
        mock_redis, counters = create_mock_redis_with_counter()
        
        # 创建限流器
        rate_limiter = RateLimiter(redis_client=mock_redis, key_prefix="test")
        
        # 发送 max_requests 个请求
        for i in range(max_requests):
            result = await rate_limiter.acquire(
                key=key,
                max_requests=max_requests,
                window_seconds=window_seconds
            )
            # 验证：每个请求都应该被允许
            assert result is True, f"第 {i+1} 个请求应该被允许"
        
        # 发送第 max_requests + 1 个请求
        result = await rate_limiter.acquire(
            key=key,
            max_requests=max_requests,
            window_seconds=window_seconds
        )
        
        # 验证：超出限制的请求被拒绝
        assert result is False, f"第 {max_requests + 1} 个请求应该被拒绝"

    @settings(max_examples=100, deadline=None)
    @given(
        max_requests=st.integers(min_value=1, max_value=50),
        window_seconds=st.integers(min_value=1, max_value=3600),
        current_count=st.integers(min_value=0, max_value=100),
        key=st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=('L', 'N')))
    )
    @pytest.mark.asyncio
    async def test_remaining_quota_consistency(
        self,
        max_requests: int,
        window_seconds: int,
        current_count: int,
        key: str
    ):
        """
        **功能: ai-grading-agent, 属性 14: 限流器节流**
        **验证: 需求 8.3**
        
        验证：剩余配额计算的一致性。
        remaining = max(0, max_requests - current_count)
        """
        assume(len(key.strip()) > 0)
        
        # 创建 Mock Redis 客户端
        mock_redis = MagicMock()
        
        # 设置 Mock：返回当前计数
        async def mock_get(k):
            return str(current_count).encode() if current_count > 0 else None
        
        mock_redis.get = mock_get
        
        # 创建限流器
        rate_limiter = RateLimiter(redis_client=mock_redis, key_prefix="test")
        
        # 获取剩余配额
        remaining = await rate_limiter.get_remaining(
            key=key,
            max_requests=max_requests,
            window_seconds=window_seconds
        )
        
        # 计算预期值
        expected_remaining = max(0, max_requests - current_count)
        
        # 验证：剩余配额计算正确
        assert remaining == expected_remaining, \
            f"剩余配额应为 {expected_remaining}，实际为 {remaining}"
        
        # 验证：剩余配额不为负数
        assert remaining >= 0, f"剩余配额不应为负数，实际为 {remaining}"

    @settings(max_examples=100, deadline=None)
    @given(
        max_requests=st.integers(min_value=1, max_value=50),
        window_seconds=st.integers(min_value=1, max_value=3600),
        key1=st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=('L', 'N'))),
        key2=st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=('L', 'N')))
    )
    @pytest.mark.asyncio
    async def test_different_keys_independent_limits(
        self,
        max_requests: int,
        window_seconds: int,
        key1: str,
        key2: str
    ):
        """
        **功能: ai-grading-agent, 属性 14: 限流器节流**
        **验证: 需求 8.3**
        
        验证：不同的限流键应当有独立的限制。
        对 key1 的请求不应影响 key2 的配额。
        """
        assume(len(key1.strip()) > 0)
        assume(len(key2.strip()) > 0)
        assume(key1 != key2)
        
        # 创建 Mock Redis 客户端
        mock_redis, counters = create_mock_redis_with_counter()
        
        # 创建限流器
        rate_limiter = RateLimiter(redis_client=mock_redis, key_prefix="test")
        
        # 对 key1 发送 max_requests 个请求（耗尽配额）
        for _ in range(max_requests):
            await rate_limiter.acquire(
                key=key1,
                max_requests=max_requests,
                window_seconds=window_seconds
            )
        
        # 验证 key1 的下一个请求被拒绝
        key1_result = await rate_limiter.acquire(
            key=key1,
            max_requests=max_requests,
            window_seconds=window_seconds
        )
        assert key1_result is False, "key1 的配额应该已耗尽"
        
        # 对 key2 发送请求（应该被允许，因为是独立的配额）
        key2_result = await rate_limiter.acquire(
            key=key2,
            max_requests=max_requests,
            window_seconds=window_seconds
        )
        
        # 验证：key2 的请求应该被允许
        assert key2_result is True, "不同键应该有独立的限流配额"

    @settings(max_examples=100, deadline=None)
    @given(
        max_requests=st.integers(min_value=2, max_value=20),
        window_seconds=st.integers(min_value=1, max_value=3600),
        key=st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=('L', 'N')))
    )
    @pytest.mark.asyncio
    async def test_throttle_count_matches_excess(
        self,
        max_requests: int,
        window_seconds: int,
        key: str
    ):
        """
        **功能: ai-grading-agent, 属性 14: 限流器节流**
        **验证: 需求 8.3**
        
        验证：被节流的请求数量等于超出限制的请求数量。
        如果发送 2 * max_requests 个请求，应该有 max_requests 个被拒绝。
        """
        assume(len(key.strip()) > 0)
        
        # 创建 Mock Redis 客户端
        mock_redis, counters = create_mock_redis_with_counter()
        
        # 创建限流器
        rate_limiter = RateLimiter(redis_client=mock_redis, key_prefix="test")
        
        total_requests = 2 * max_requests
        throttled_count = 0
        
        # 发送两倍限制的请求
        for _ in range(total_requests):
            result = await rate_limiter.acquire(
                key=key,
                max_requests=max_requests,
                window_seconds=window_seconds
            )
            if not result:
                throttled_count += 1
        
        # 验证：被节流的请求数量等于超出的数量
        expected_throttled = total_requests - max_requests
        assert throttled_count == expected_throttled, \
            f"应该节流 {expected_throttled} 个请求，实际节流 {throttled_count} 个"

    @settings(max_examples=100, deadline=None)
    @given(
        max_requests=st.integers(min_value=1, max_value=50),
        window_seconds=st.integers(min_value=1, max_value=3600),
        key=st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=('L', 'N')))
    )
    @pytest.mark.asyncio
    async def test_first_request_always_allowed(
        self,
        max_requests: int,
        window_seconds: int,
        key: str
    ):
        """
        **功能: ai-grading-agent, 属性 14: 限流器节流**
        **验证: 需求 8.3**
        
        验证：第一个请求总是被允许的。
        无论配置如何，第一个请求应该返回 True。
        """
        assume(len(key.strip()) > 0)
        
        # 创建 Mock Redis 客户端
        mock_redis, counters = create_mock_redis_with_counter()
        
        # 创建限流器
        rate_limiter = RateLimiter(redis_client=mock_redis, key_prefix="test")
        
        # 发送第一个请求
        result = await rate_limiter.acquire(
            key=key,
            max_requests=max_requests,
            window_seconds=window_seconds
        )
        
        # 验证：第一个请求被允许
        assert result is True, "第一个请求应该总是被允许"

