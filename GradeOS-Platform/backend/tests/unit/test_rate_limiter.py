"""
限流器单元测试

测试 RateLimiter 类的核心功能。
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from redis.exceptions import RedisError

from src.services.rate_limiter import RateLimiter


@pytest.fixture
def mock_redis():
    """创建 Mock Redis 客户端"""
    redis_mock = AsyncMock()
    redis_mock.pipeline = MagicMock()
    return redis_mock


@pytest.fixture
def rate_limiter(mock_redis):
    """创建 RateLimiter 实例"""
    return RateLimiter(redis_client=mock_redis, key_prefix="test_rate_limit")


class TestRateLimiterBasic:
    """基础功能测试"""
    
    @pytest.mark.asyncio
    async def test_acquire_within_limit(self, rate_limiter, mock_redis):
        """测试在限制内的请求应该被允许"""
        # 模拟 Redis Pipeline
        pipe_mock = AsyncMock()
        pipe_mock.__aenter__ = AsyncMock(return_value=pipe_mock)
        pipe_mock.__aexit__ = AsyncMock(return_value=None)
        pipe_mock.incr = MagicMock()
        pipe_mock.expire = MagicMock()
        pipe_mock.execute = AsyncMock(return_value=[5, True])  # 当前计数为 5
        
        mock_redis.pipeline.return_value = pipe_mock
        
        # 执行测试
        result = await rate_limiter.acquire(
            key="test_user",
            max_requests=10,
            window_seconds=60
        )
        
        assert result is True
        pipe_mock.incr.assert_called_once()
        pipe_mock.expire.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_acquire_exceeds_limit(self, rate_limiter, mock_redis):
        """测试超出限制的请求应该被拒绝"""
        # 模拟 Redis Pipeline
        pipe_mock = AsyncMock()
        pipe_mock.__aenter__ = AsyncMock(return_value=pipe_mock)
        pipe_mock.__aexit__ = AsyncMock(return_value=None)
        pipe_mock.incr = MagicMock()
        pipe_mock.expire = MagicMock()
        pipe_mock.execute = AsyncMock(return_value=[11, True])  # 当前计数为 11
        
        mock_redis.pipeline.return_value = pipe_mock
        
        # 执行测试
        result = await rate_limiter.acquire(
            key="test_user",
            max_requests=10,
            window_seconds=60
        )
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_acquire_at_limit_boundary(self, rate_limiter, mock_redis):
        """测试恰好达到限制的请求应该被允许"""
        # 模拟 Redis Pipeline
        pipe_mock = AsyncMock()
        pipe_mock.__aenter__ = AsyncMock(return_value=pipe_mock)
        pipe_mock.__aexit__ = AsyncMock(return_value=None)
        pipe_mock.incr = MagicMock()
        pipe_mock.expire = MagicMock()
        pipe_mock.execute = AsyncMock(return_value=[10, True])  # 当前计数恰好为 10
        
        mock_redis.pipeline.return_value = pipe_mock
        
        # 执行测试
        result = await rate_limiter.acquire(
            key="test_user",
            max_requests=10,
            window_seconds=60
        )
        
        assert result is True


class TestRateLimiterRemaining:
    """剩余配额测试"""
    
    @pytest.mark.asyncio
    async def test_get_remaining_with_usage(self, rate_limiter, mock_redis):
        """测试获取剩余配额（有使用记录）"""
        mock_redis.get = AsyncMock(return_value=b"7")
        
        remaining = await rate_limiter.get_remaining(
            key="test_user",
            max_requests=10,
            window_seconds=60
        )
        
        assert remaining == 3  # 10 - 7 = 3
    
    @pytest.mark.asyncio
    async def test_get_remaining_no_usage(self, rate_limiter, mock_redis):
        """测试获取剩余配额（无使用记录）"""
        mock_redis.get = AsyncMock(return_value=None)
        
        remaining = await rate_limiter.get_remaining(
            key="test_user",
            max_requests=10,
            window_seconds=60
        )
        
        assert remaining == 10  # 全部可用
    
    @pytest.mark.asyncio
    async def test_get_remaining_exceeds_limit(self, rate_limiter, mock_redis):
        """测试获取剩余配额（已超出限制）"""
        mock_redis.get = AsyncMock(return_value=b"15")
        
        remaining = await rate_limiter.get_remaining(
            key="test_user",
            max_requests=10,
            window_seconds=60
        )
        
        assert remaining == 0  # 不能为负数


class TestRateLimiterErrorHandling:
    """错误处理测试"""
    
    @pytest.mark.asyncio
    async def test_acquire_redis_error_fail_open(self, rate_limiter, mock_redis):
        """测试 Redis 错误时应该允许请求（fail-open 策略）"""
        # 模拟 Redis 错误
        pipe_mock = AsyncMock()
        pipe_mock.__aenter__ = AsyncMock(side_effect=RedisError("Connection failed"))
        mock_redis.pipeline.return_value = pipe_mock
        
        result = await rate_limiter.acquire(
            key="test_user",
            max_requests=10,
            window_seconds=60
        )
        
        # 应该允许请求（优雅降级）
        assert result is True
    
    @pytest.mark.asyncio
    async def test_get_remaining_redis_error(self, rate_limiter, mock_redis):
        """测试获取剩余配额时 Redis 错误应该返回最大值"""
        mock_redis.get = AsyncMock(side_effect=RedisError("Connection failed"))
        
        remaining = await rate_limiter.get_remaining(
            key="test_user",
            max_requests=10,
            window_seconds=60
        )
        
        # 应该返回最大值（保守估计）
        assert remaining == 10
    
    @pytest.mark.asyncio
    async def test_get_remaining_invalid_value(self, rate_limiter, mock_redis):
        """测试获取剩余配额时遇到无效值应该返回最大值"""
        mock_redis.get = AsyncMock(return_value=b"invalid")
        
        remaining = await rate_limiter.get_remaining(
            key="test_user",
            max_requests=10,
            window_seconds=60
        )
        
        # 应该返回最大值（保守估计）
        assert remaining == 10


class TestRateLimiterReset:
    """重置功能测试"""
    
    @pytest.mark.asyncio
    async def test_reset_existing_key(self, rate_limiter, mock_redis):
        """测试重置存在的限流计数器"""
        mock_redis.delete = AsyncMock(return_value=1)
        
        result = await rate_limiter.reset(
            key="test_user",
            window_seconds=60
        )
        
        assert result is True
        mock_redis.delete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_reset_nonexistent_key(self, rate_limiter, mock_redis):
        """测试重置不存在的限流计数器"""
        mock_redis.delete = AsyncMock(return_value=0)
        
        result = await rate_limiter.reset(
            key="test_user",
            window_seconds=60
        )
        
        assert result is True  # 不存在也算成功
    
    @pytest.mark.asyncio
    async def test_reset_redis_error(self, rate_limiter, mock_redis):
        """测试重置时 Redis 错误应该返回 False"""
        mock_redis.delete = AsyncMock(side_effect=RedisError("Connection failed"))
        
        result = await rate_limiter.reset(
            key="test_user",
            window_seconds=60
        )
        
        assert result is False


class TestRateLimiterInfo:
    """信息查询测试"""
    
    @pytest.mark.asyncio
    async def test_get_rate_limit_info(self, rate_limiter, mock_redis):
        """测试获取限流详细信息"""
        # 模拟 Redis Pipeline
        pipe_mock = AsyncMock()
        pipe_mock.__aenter__ = AsyncMock(return_value=pipe_mock)
        pipe_mock.__aexit__ = AsyncMock(return_value=None)
        pipe_mock.get = MagicMock()
        pipe_mock.ttl = MagicMock()
        pipe_mock.execute = AsyncMock(return_value=[b"7", 45])  # 使用 7 次，TTL 45 秒
        
        mock_redis.pipeline.return_value = pipe_mock
        
        info = await rate_limiter.get_rate_limit_info(
            key="test_user",
            max_requests=10,
            window_seconds=60
        )
        
        assert info["key"] == "test_user"
        assert info["limit"] == 10
        assert info["remaining"] == 3
        assert info["used"] == 7
        assert info["window_seconds"] == 60
        assert info["ttl_seconds"] == 45
        assert "reset_at" in info
    
    @pytest.mark.asyncio
    async def test_get_rate_limit_info_error(self, rate_limiter, mock_redis):
        """测试获取限流信息时发生错误应该返回默认值"""
        # 模拟 Redis 错误
        pipe_mock = AsyncMock()
        pipe_mock.__aenter__ = AsyncMock(side_effect=RedisError("Connection failed"))
        mock_redis.pipeline.return_value = pipe_mock
        
        info = await rate_limiter.get_rate_limit_info(
            key="test_user",
            max_requests=10,
            window_seconds=60
        )
        
        assert info["key"] == "test_user"
        assert info["limit"] == 10
        assert info["remaining"] == 10  # 默认值
        assert info["used"] == 0
        assert "error" in info


class TestRateLimiterWindowKey:
    """时间窗口键生成测试"""
    
    def test_window_key_format(self, rate_limiter):
        """测试时间窗口键的格式"""
        from datetime import timezone
        
        with patch('src.services.rate_limiter.datetime') as mock_datetime:
            # 固定时间：2025-12-07 10:30:45 UTC
            fixed_time = datetime(2025, 12, 7, 10, 30, 45, tzinfo=timezone.utc)
            mock_datetime.now.return_value = fixed_time
            
            key = rate_limiter._get_window_key("test_user", 60)
            
            # 窗口应该对齐到分钟边界：10:30:00
            expected_timestamp = int(datetime(2025, 12, 7, 10, 30, 0, tzinfo=timezone.utc).timestamp())
            assert key == f"test_rate_limit:test_user:{expected_timestamp}"
    
    def test_window_key_alignment(self, rate_limiter):
        """测试时间窗口键的对齐行为"""
        from datetime import timezone
        
        with patch('src.services.rate_limiter.datetime') as mock_datetime:
            # 测试同一分钟内的不同时间点应该生成相同的键
            times = [
                datetime(2025, 12, 7, 10, 30, 0, tzinfo=timezone.utc),
                datetime(2025, 12, 7, 10, 30, 30, tzinfo=timezone.utc),
                datetime(2025, 12, 7, 10, 30, 59, tzinfo=timezone.utc),
            ]
            
            keys = []
            for time in times:
                mock_datetime.now.return_value = time
                key = rate_limiter._get_window_key("test_user", 60)
                keys.append(key)
            
            # 所有键应该相同
            assert len(set(keys)) == 1
