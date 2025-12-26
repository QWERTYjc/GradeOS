"""缓存服务的单元测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from redis.exceptions import RedisError
from PIL import Image
from io import BytesIO

from src.services.cache import CacheService
from src.models.grading import GradingResult


def create_test_image(width: int = 100, height: int = 100, color: tuple = (255, 0, 0)) -> bytes:
    """创建测试图像"""
    img = Image.new('RGB', (width, height), color)
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()


def create_test_grading_result(confidence: float = 0.95) -> GradingResult:
    """创建测试批改结果"""
    return GradingResult(
        question_id="q1",
        score=8.5,
        max_score=10.0,
        confidence=confidence,
        feedback="解题思路正确",
        visual_annotations=[],
        agent_trace={"vision_analysis": "学生使用了正确的公式"}
    )


@pytest.fixture
def mock_redis():
    """创建 Mock Redis 客户端"""
    redis_mock = AsyncMock()
    return redis_mock


@pytest.fixture
def cache_service(mock_redis):
    """创建缓存服务实例"""
    return CacheService(redis_client=mock_redis, default_ttl_days=30)


class TestCacheServiceGetCachedResult:
    """测试缓存查询功能"""
    
    @pytest.mark.asyncio
    async def test_cache_hit_returns_result(self, cache_service, mock_redis):
        """测试缓存命中返回结果"""
        rubric_text = "评分细则"
        image_data = create_test_image()
        expected_result = create_test_grading_result()
        
        # Mock Redis 返回缓存数据
        mock_redis.get.return_value = expected_result.model_dump_json()
        
        result = await cache_service.get_cached_result(rubric_text, image_data)
        
        assert result is not None
        assert result.question_id == expected_result.question_id
        assert result.score == expected_result.score
        assert result.confidence == expected_result.confidence
    
    @pytest.mark.asyncio
    async def test_cache_miss_returns_none(self, cache_service, mock_redis):
        """测试缓存未命中返回 None"""
        rubric_text = "评分细则"
        image_data = create_test_image()
        
        # Mock Redis 返回 None（缓存未命中）
        mock_redis.get.return_value = None
        
        result = await cache_service.get_cached_result(rubric_text, image_data)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_redis_error_returns_none(self, cache_service, mock_redis):
        """测试 Redis 错误时返回 None（优雅降级）"""
        rubric_text = "评分细则"
        image_data = create_test_image()
        
        # Mock Redis 抛出错误
        mock_redis.get.side_effect = RedisError("连接失败")
        
        result = await cache_service.get_cached_result(rubric_text, image_data)
        
        # 应该优雅降级，返回 None 而不抛出异常
        assert result is None
    
    @pytest.mark.asyncio
    async def test_invalid_json_returns_none(self, cache_service, mock_redis):
        """测试无效 JSON 数据返回 None"""
        rubric_text = "评分细则"
        image_data = create_test_image()
        
        # Mock Redis 返回无效 JSON
        mock_redis.get.return_value = "invalid json"
        
        result = await cache_service.get_cached_result(rubric_text, image_data)
        
        assert result is None


class TestCacheServiceCacheResult:
    """测试缓存存储功能"""
    
    @pytest.mark.asyncio
    async def test_high_confidence_result_is_cached(self, cache_service, mock_redis):
        """测试高置信度结果被缓存"""
        rubric_text = "评分细则"
        image_data = create_test_image()
        result = create_test_grading_result(confidence=0.95)
        
        success = await cache_service.cache_result(rubric_text, image_data, result)
        
        assert success is True
        mock_redis.setex.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_low_confidence_result_not_cached(self, cache_service, mock_redis):
        """测试低置信度结果不被缓存"""
        rubric_text = "评分细则"
        image_data = create_test_image()
        result = create_test_grading_result(confidence=0.85)  # <= 0.9
        
        success = await cache_service.cache_result(rubric_text, image_data, result)
        
        assert success is False
        mock_redis.setex.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_redis_error_returns_false(self, cache_service, mock_redis):
        """测试 Redis 错误时返回 False（优雅降级）"""
        rubric_text = "评分细则"
        image_data = create_test_image()
        result = create_test_grading_result(confidence=0.95)
        
        # Mock Redis 抛出错误
        mock_redis.setex.side_effect = RedisError("存储失败")
        
        success = await cache_service.cache_result(rubric_text, image_data, result)
        
        # 应该优雅降级，返回 False 而不抛出异常
        assert success is False
    
    @pytest.mark.asyncio
    async def test_custom_ttl_is_used(self, cache_service, mock_redis):
        """测试自定义 TTL 被使用"""
        rubric_text = "评分细则"
        image_data = create_test_image()
        result = create_test_grading_result(confidence=0.95)
        custom_ttl_days = 15
        
        await cache_service.cache_result(rubric_text, image_data, result, ttl_days=custom_ttl_days)
        
        # 检查 setex 调用的 TTL 参数
        call_args = mock_redis.setex.call_args
        assert call_args is not None
        ttl_arg = call_args[0][1]  # 第二个参数是 TTL
        assert ttl_arg.days == custom_ttl_days


class TestCacheServiceInvalidateByRubric:
    """测试评分细则缓存失效功能"""
    
    @pytest.mark.asyncio
    async def test_invalidate_deletes_matching_keys(self, cache_service, mock_redis):
        """测试失效操作删除匹配的键"""
        rubric_text = "评分细则"
        
        # Mock scan 返回匹配的键
        mock_redis.scan.return_value = (0, [b"key1", b"key2", b"key3"])
        mock_redis.delete.return_value = 3
        
        deleted_count = await cache_service.invalidate_by_rubric(rubric_text)
        
        assert deleted_count == 3
        mock_redis.delete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_invalidate_handles_redis_error(self, cache_service, mock_redis):
        """测试失效操作处理 Redis 错误"""
        rubric_text = "评分细则"
        
        # Mock scan 抛出错误
        mock_redis.scan.side_effect = RedisError("扫描失败")
        
        deleted_count = await cache_service.invalidate_by_rubric(rubric_text)
        
        # 应该返回 0 而不抛出异常
        assert deleted_count == 0


class TestCacheServiceGetCacheStats:
    """测试缓存统计功能"""
    
    @pytest.mark.asyncio
    async def test_get_cache_stats_returns_dict(self, cache_service, mock_redis):
        """测试获取缓存统计返回字典"""
        # Mock Redis info 和 scan
        mock_redis.info.return_value = {
            "keyspace_hits": 100,
            "keyspace_misses": 20
        }
        mock_redis.scan.return_value = (0, [b"key1", b"key2"])
        
        stats = await cache_service.get_cache_stats()
        
        assert isinstance(stats, dict)
        assert "total_cache_keys" in stats
        assert "keyspace_hits" in stats
        assert "keyspace_misses" in stats
        assert "hit_rate" in stats
    
    @pytest.mark.asyncio
    async def test_get_cache_stats_handles_error(self, cache_service, mock_redis):
        """测试获取统计处理错误"""
        # Mock Redis 抛出错误
        mock_redis.info.side_effect = RedisError("获取信息失败")
        
        stats = await cache_service.get_cache_stats()
        
        # 应该返回默认值而不抛出异常
        assert stats["total_cache_keys"] == 0
        assert "error" in stats
