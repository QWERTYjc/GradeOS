"""高置信度缓存的属性测试

**功能: ai-grading-agent, 属性 11: 高置信度结果被缓存**
**验证: 需求 6.3**

属性定义：
对于任意 `confidence > 0.9` 的新生成批改结果，结果应当以正确的 
(rubric_hash, image_hash) 键和 30 天 TTL 存储到缓存中。
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import AsyncMock, MagicMock, patch, call
from PIL import Image
from io import BytesIO
from datetime import timedelta

from src.services.cache import CacheService
from src.models.grading import GradingResult
from src.utils.hashing import compute_cache_key


# ============================================================================
# 策略定义
# ============================================================================

@st.composite
def random_image_data(draw, min_size=32, max_size=100):
    """
    生成随机图像数据
    
    Args:
        draw: Hypothesis draw 函数
        min_size: 最小图像尺寸
        max_size: 最大图像尺寸
        
    Returns:
        PNG 格式的图像字节数据
    """
    width = draw(st.integers(min_value=min_size, max_value=max_size))
    height = draw(st.integers(min_value=min_size, max_value=max_size))
    
    # 创建图像
    img = Image.new('RGB', (width, height))
    pixels = img.load()
    
    # 使用随机颜色填充
    r = draw(st.integers(min_value=0, max_value=255))
    g = draw(st.integers(min_value=0, max_value=255))
    b = draw(st.integers(min_value=0, max_value=255))
    
    for i in range(width):
        for j in range(height):
            pixels[i, j] = (r, g, b)
    
    # 转换为字节
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()


@st.composite
def high_confidence_grading_result(draw):
    """
    生成高置信度（> 0.9）的 GradingResult 对象
    
    Args:
        draw: Hypothesis draw 函数
        
    Returns:
        置信度 > 0.9 的 GradingResult 对象
    """
    max_score = draw(st.floats(min_value=1.0, max_value=100.0, allow_nan=False, allow_infinity=False))
    score = draw(st.floats(min_value=0.0, max_value=max_score, allow_nan=False, allow_infinity=False))
    # 高置信度：> 0.9
    confidence = draw(st.floats(min_value=0.901, max_value=1.0, allow_nan=False, allow_infinity=False))
    
    return GradingResult(
        question_id=draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('L', 'N')))),
        score=score,
        max_score=max_score,
        confidence=confidence,
        feedback=draw(st.text(min_size=1, max_size=200)),
        visual_annotations=[],
        agent_trace={"vision_analysis": draw(st.text(min_size=1, max_size=100))}
    )


@st.composite
def low_confidence_grading_result(draw):
    """
    生成低置信度（<= 0.9）的 GradingResult 对象
    
    Args:
        draw: Hypothesis draw 函数
        
    Returns:
        置信度 <= 0.9 的 GradingResult 对象
    """
    max_score = draw(st.floats(min_value=1.0, max_value=100.0, allow_nan=False, allow_infinity=False))
    score = draw(st.floats(min_value=0.0, max_value=max_score, allow_nan=False, allow_infinity=False))
    # 低置信度：<= 0.9
    confidence = draw(st.floats(min_value=0.0, max_value=0.9, allow_nan=False, allow_infinity=False))
    
    return GradingResult(
        question_id=draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('L', 'N')))),
        score=score,
        max_score=max_score,
        confidence=confidence,
        feedback=draw(st.text(min_size=1, max_size=200)),
        visual_annotations=[],
        agent_trace={"vision_analysis": draw(st.text(min_size=1, max_size=100))}
    )


# ============================================================================
# 属性测试
# ============================================================================

class TestHighConfidenceCache:
    """高置信度缓存的属性测试"""

    @settings(max_examples=100, deadline=None)
    @given(
        rubric_text=st.text(min_size=1, max_size=500),
        image_data=random_image_data(),
        grading_result=high_confidence_grading_result()
    )
    @pytest.mark.asyncio
    async def test_high_confidence_result_is_cached(
        self, 
        rubric_text: str, 
        image_data: bytes, 
        grading_result: GradingResult
    ):
        """
        **功能: ai-grading-agent, 属性 11: 高置信度结果被缓存**
        **验证: 需求 6.3**
        
        验证：当置信度 > 0.9 时，结果应当被缓存。
        """
        # 确保输入有效
        assume(len(rubric_text.strip()) > 0)
        
        # 创建 Mock Redis 客户端
        mock_redis = AsyncMock()
        mock_redis.setex.return_value = True
        
        # 计算预期的缓存键
        expected_cache_key = compute_cache_key(rubric_text, image_data)
        
        # 创建缓存服务
        cache_service = CacheService(redis_client=mock_redis)
        
        # 缓存结果
        success = await cache_service.cache_result(rubric_text, image_data, grading_result)
        
        # 验证：高置信度结果应当被缓存
        assert success is True, \
            f"高置信度结果（confidence={grading_result.confidence}）应当被缓存"
        
        # 验证：Redis setex 被调用
        mock_redis.setex.assert_called_once()
        
        # 验证：使用正确的缓存键
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == expected_cache_key, \
            f"缓存键不匹配: {call_args[0][0]} != {expected_cache_key}"

    @settings(max_examples=100, deadline=None)
    @given(
        rubric_text=st.text(min_size=1, max_size=500),
        image_data=random_image_data(),
        grading_result=high_confidence_grading_result()
    )
    @pytest.mark.asyncio
    async def test_high_confidence_cache_uses_default_ttl(
        self, 
        rubric_text: str, 
        image_data: bytes, 
        grading_result: GradingResult
    ):
        """
        **功能: ai-grading-agent, 属性 11: 高置信度结果被缓存**
        **验证: 需求 6.3**
        
        验证：高置信度结果应当使用默认 30 天 TTL 存储。
        """
        # 确保输入有效
        assume(len(rubric_text.strip()) > 0)
        
        # 创建 Mock Redis 客户端
        mock_redis = AsyncMock()
        mock_redis.setex.return_value = True
        
        # 创建缓存服务（默认 30 天 TTL）
        cache_service = CacheService(redis_client=mock_redis, default_ttl_days=30)
        
        # 缓存结果
        await cache_service.cache_result(rubric_text, image_data, grading_result)
        
        # 验证：TTL 为 30 天
        call_args = mock_redis.setex.call_args
        ttl_arg = call_args[0][1]
        
        expected_ttl = timedelta(days=30)
        assert ttl_arg == expected_ttl, \
            f"TTL 不匹配: {ttl_arg} != {expected_ttl}"

    @settings(max_examples=100, deadline=None)
    @given(
        rubric_text=st.text(min_size=1, max_size=500),
        image_data=random_image_data(),
        grading_result=high_confidence_grading_result(),
        custom_ttl=st.integers(min_value=1, max_value=365)
    )
    @pytest.mark.asyncio
    async def test_high_confidence_cache_respects_custom_ttl(
        self, 
        rubric_text: str, 
        image_data: bytes, 
        grading_result: GradingResult,
        custom_ttl: int
    ):
        """
        **功能: ai-grading-agent, 属性 11: 高置信度结果被缓存**
        **验证: 需求 6.3**
        
        验证：高置信度结果应当尊重自定义 TTL 设置。
        """
        # 确保输入有效
        assume(len(rubric_text.strip()) > 0)
        
        # 创建 Mock Redis 客户端
        mock_redis = AsyncMock()
        mock_redis.setex.return_value = True
        
        # 创建缓存服务
        cache_service = CacheService(redis_client=mock_redis)
        
        # 使用自定义 TTL 缓存结果
        await cache_service.cache_result(
            rubric_text, image_data, grading_result, ttl_days=custom_ttl
        )
        
        # 验证：TTL 为自定义值
        call_args = mock_redis.setex.call_args
        ttl_arg = call_args[0][1]
        
        expected_ttl = timedelta(days=custom_ttl)
        assert ttl_arg == expected_ttl, \
            f"自定义 TTL 不匹配: {ttl_arg} != {expected_ttl}"

    @settings(max_examples=100, deadline=None)
    @given(
        rubric_text=st.text(min_size=1, max_size=500),
        image_data=random_image_data(),
        grading_result=low_confidence_grading_result()
    )
    @pytest.mark.asyncio
    async def test_low_confidence_result_not_cached(
        self, 
        rubric_text: str, 
        image_data: bytes, 
        grading_result: GradingResult
    ):
        """
        **功能: ai-grading-agent, 属性 11: 高置信度结果被缓存**
        **验证: 需求 6.3**
        
        验证：当置信度 <= 0.9 时，结果不应当被缓存。
        """
        # 确保输入有效
        assume(len(rubric_text.strip()) > 0)
        
        # 创建 Mock Redis 客户端
        mock_redis = AsyncMock()
        
        # 创建缓存服务
        cache_service = CacheService(redis_client=mock_redis)
        
        # 尝试缓存结果
        success = await cache_service.cache_result(rubric_text, image_data, grading_result)
        
        # 验证：低置信度结果不应当被缓存
        assert success is False, \
            f"低置信度结果（confidence={grading_result.confidence}）不应当被缓存"
        
        # 验证：Redis setex 未被调用
        mock_redis.setex.assert_not_called()

    @settings(max_examples=100, deadline=None)
    @given(
        rubric_text=st.text(min_size=1, max_size=500),
        image_data=random_image_data(),
        grading_result=high_confidence_grading_result()
    )
    @pytest.mark.asyncio
    async def test_cached_data_is_serialized_correctly(
        self, 
        rubric_text: str, 
        image_data: bytes, 
        grading_result: GradingResult
    ):
        """
        **功能: ai-grading-agent, 属性 11: 高置信度结果被缓存**
        **验证: 需求 6.3**
        
        验证：缓存的数据应当正确序列化为 JSON。
        """
        # 确保输入有效
        assume(len(rubric_text.strip()) > 0)
        
        # 创建 Mock Redis 客户端
        mock_redis = AsyncMock()
        mock_redis.setex.return_value = True
        
        # 创建缓存服务
        cache_service = CacheService(redis_client=mock_redis)
        
        # 缓存结果
        await cache_service.cache_result(rubric_text, image_data, grading_result)
        
        # 获取存储的数据
        call_args = mock_redis.setex.call_args
        stored_data = call_args[0][2]
        
        # 验证：存储的数据是有效的 JSON
        import json
        parsed_data = json.loads(stored_data)
        
        # 验证：数据包含所有必需字段
        assert parsed_data["question_id"] == grading_result.question_id
        assert parsed_data["score"] == grading_result.score
        assert parsed_data["max_score"] == grading_result.max_score
        assert parsed_data["confidence"] == grading_result.confidence
        assert parsed_data["feedback"] == grading_result.feedback

    @settings(max_examples=100, deadline=None)
    @given(
        rubric_text=st.text(min_size=1, max_size=500),
        image_data=random_image_data(),
        grading_result=high_confidence_grading_result()
    )
    @pytest.mark.asyncio
    async def test_cache_key_format_is_correct(
        self, 
        rubric_text: str, 
        image_data: bytes, 
        grading_result: GradingResult
    ):
        """
        **功能: ai-grading-agent, 属性 11: 高置信度结果被缓存**
        **验证: 需求 6.3**
        
        验证：缓存键应当使用正确的格式 grade_cache:v1:{rubric_hash}:{image_hash}。
        """
        # 确保输入有效
        assume(len(rubric_text.strip()) > 0)
        
        # 创建 Mock Redis 客户端
        mock_redis = AsyncMock()
        mock_redis.setex.return_value = True
        
        # 创建缓存服务
        cache_service = CacheService(redis_client=mock_redis)
        
        # 缓存结果
        await cache_service.cache_result(rubric_text, image_data, grading_result)
        
        # 获取使用的缓存键
        call_args = mock_redis.setex.call_args
        cache_key = call_args[0][0]
        
        # 验证：缓存键格式正确
        assert cache_key.startswith("grade_cache:v1:"), \
            f"缓存键格式不正确: {cache_key}"
        
        # 验证：缓存键包含两个哈希值（rubric_hash 和 image_hash）
        parts = cache_key.split(":")
        assert len(parts) == 4, \
            f"缓存键应包含 4 个部分: {cache_key}"

    @settings(max_examples=100, deadline=None)
    @given(
        rubric_text=st.text(min_size=1, max_size=500),
        image_data=random_image_data()
    )
    @pytest.mark.asyncio
    async def test_boundary_confidence_not_cached(
        self, 
        rubric_text: str, 
        image_data: bytes
    ):
        """
        **功能: ai-grading-agent, 属性 11: 高置信度结果被缓存**
        **验证: 需求 6.3**
        
        验证：置信度恰好为 0.9 时，结果不应当被缓存（边界条件）。
        """
        # 确保输入有效
        assume(len(rubric_text.strip()) > 0)
        
        # 创建置信度恰好为 0.9 的结果
        grading_result = GradingResult(
            question_id="test_q1",
            score=8.0,
            max_score=10.0,
            confidence=0.9,  # 边界值
            feedback="Test feedback",
            visual_annotations=[],
            agent_trace={"vision_analysis": "test"}
        )
        
        # 创建 Mock Redis 客户端
        mock_redis = AsyncMock()
        
        # 创建缓存服务
        cache_service = CacheService(redis_client=mock_redis)
        
        # 尝试缓存结果
        success = await cache_service.cache_result(rubric_text, image_data, grading_result)
        
        # 验证：边界值 0.9 不应当被缓存
        assert success is False, \
            "置信度恰好为 0.9 的结果不应当被缓存"
        
        # 验证：Redis setex 未被调用
        mock_redis.setex.assert_not_called()

    @settings(max_examples=100, deadline=None)
    @given(
        rubric_text=st.text(min_size=1, max_size=500),
        image_data=random_image_data(),
        grading_result=high_confidence_grading_result()
    )
    @pytest.mark.asyncio
    async def test_cache_roundtrip_preserves_high_confidence_data(
        self, 
        rubric_text: str, 
        image_data: bytes, 
        grading_result: GradingResult
    ):
        """
        **功能: ai-grading-agent, 属性 11: 高置信度结果被缓存**
        **验证: 需求 6.3**
        
        验证：高置信度结果的缓存往返应当保持数据完整性。
        """
        # 确保输入有效
        assume(len(rubric_text.strip()) > 0)
        
        # 存储实际写入的数据
        stored_data = None
        
        async def capture_setex(key, ttl, data):
            nonlocal stored_data
            stored_data = data
            return True
        
        # 创建 Mock Redis 客户端
        mock_redis = AsyncMock()
        mock_redis.setex.side_effect = capture_setex
        mock_redis.get.side_effect = lambda key: stored_data
        
        # 创建缓存服务
        cache_service = CacheService(redis_client=mock_redis)
        
        # 缓存结果
        cache_success = await cache_service.cache_result(rubric_text, image_data, grading_result)
        assert cache_success is True
        
        # 读取缓存
        retrieved_result = await cache_service.get_cached_result(rubric_text, image_data)
        
        # 验证：数据完整性
        assert retrieved_result is not None
        assert retrieved_result.question_id == grading_result.question_id
        assert retrieved_result.score == grading_result.score
        assert retrieved_result.max_score == grading_result.max_score
        assert retrieved_result.confidence == grading_result.confidence
        assert retrieved_result.feedback == grading_result.feedback
