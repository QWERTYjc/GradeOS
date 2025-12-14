"""缓存失败弹性的属性测试

**功能: ai-grading-agent, 属性 12: 缓存失败不阻塞批改**
**验证: 需求 6.4**

属性定义：
对于任意失败的缓存操作（查找或存储），批改过程应当正常继续并产生有效结果。
缓存失败不应当作为异常传播给调用者。
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import AsyncMock, MagicMock, patch
from PIL import Image
from io import BytesIO
import json

from redis.exceptions import RedisError, ConnectionError, TimeoutError

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
def grading_result_strategy(draw):
    """
    生成随机的 GradingResult 对象
    
    Args:
        draw: Hypothesis draw 函数
        
    Returns:
        GradingResult 对象
    """
    max_score = draw(st.floats(min_value=1.0, max_value=100.0, allow_nan=False, allow_infinity=False))
    score = draw(st.floats(min_value=0.0, max_value=max_score, allow_nan=False, allow_infinity=False))
    # 高置信度以确保会尝试缓存
    confidence = draw(st.floats(min_value=0.91, max_value=1.0, allow_nan=False, allow_infinity=False))
    
    return GradingResult(
        question_id=draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('L', 'N')))),
        score=score,
        max_score=max_score,
        confidence=confidence,
        feedback=draw(st.text(min_size=1, max_size=200)),
        visual_annotations=[],
        agent_trace={"vision_analysis": draw(st.text(min_size=1, max_size=100))}
    )


# Redis 错误类型策略
redis_error_strategy = st.sampled_from([
    RedisError("Redis connection failed"),
    ConnectionError("Cannot connect to Redis"),
    TimeoutError("Redis operation timed out"),
])


# ============================================================================
# 属性测试
# ============================================================================

class TestCacheFailureResilience:
    """缓存失败弹性的属性测试"""

    @settings(max_examples=100, deadline=None)
    @given(
        rubric_text=st.text(min_size=1, max_size=500),
        image_data=random_image_data(),
        redis_error=redis_error_strategy
    )
    @pytest.mark.asyncio
    async def test_cache_lookup_failure_returns_none_not_exception(
        self, 
        rubric_text: str, 
        image_data: bytes,
        redis_error: Exception
    ):
        """
        **功能: ai-grading-agent, 属性 12: 缓存失败不阻塞批改**
        **验证: 需求 6.4**
        
        验证：当缓存查找失败时，服务应当返回 None 而不是抛出异常。
        """
        # 确保输入有效
        assume(len(rubric_text.strip()) > 0)
        
        # 创建 Mock Redis 客户端，模拟查找失败
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = redis_error
        
        # 创建缓存服务
        cache_service = CacheService(redis_client=mock_redis)
        
        # 查询缓存 - 不应抛出异常
        result = await cache_service.get_cached_result(rubric_text, image_data)
        
        # 验证：返回 None 而不是抛出异常
        assert result is None, \
            f"缓存查找失败时应返回 None，而不是抛出异常: {type(redis_error).__name__}"

    @settings(max_examples=100, deadline=None)
    @given(
        rubric_text=st.text(min_size=1, max_size=500),
        image_data=random_image_data(),
        grading_result=grading_result_strategy(),
        redis_error=redis_error_strategy
    )
    @pytest.mark.asyncio
    async def test_cache_store_failure_returns_false_not_exception(
        self, 
        rubric_text: str, 
        image_data: bytes,
        grading_result: GradingResult,
        redis_error: Exception
    ):
        """
        **功能: ai-grading-agent, 属性 12: 缓存失败不阻塞批改**
        **验证: 需求 6.4**
        
        验证：当缓存存储失败时，服务应当返回 False 而不是抛出异常。
        """
        # 确保输入有效
        assume(len(rubric_text.strip()) > 0)
        
        # 创建 Mock Redis 客户端，模拟存储失败
        mock_redis = AsyncMock()
        mock_redis.setex.side_effect = redis_error
        
        # 创建缓存服务
        cache_service = CacheService(redis_client=mock_redis)
        
        # 尝试缓存结果 - 不应抛出异常
        success = await cache_service.cache_result(rubric_text, image_data, grading_result)
        
        # 验证：返回 False 而不是抛出异常
        assert success is False, \
            f"缓存存储失败时应返回 False，而不是抛出异常: {type(redis_error).__name__}"

    @settings(max_examples=100, deadline=None)
    @given(
        rubric_text=st.text(min_size=1, max_size=500),
        image_data=random_image_data()
    )
    @pytest.mark.asyncio
    async def test_cache_lookup_with_corrupted_data_returns_none(
        self, 
        rubric_text: str, 
        image_data: bytes
    ):
        """
        **功能: ai-grading-agent, 属性 12: 缓存失败不阻塞批改**
        **验证: 需求 6.4**
        
        验证：当缓存数据损坏（无效 JSON）时，服务应当返回 None 而不是抛出异常。
        """
        # 确保输入有效
        assume(len(rubric_text.strip()) > 0)
        
        # 创建 Mock Redis 客户端，返回损坏的数据
        mock_redis = AsyncMock()
        mock_redis.get.return_value = "invalid json data {{{{"
        
        # 创建缓存服务
        cache_service = CacheService(redis_client=mock_redis)
        
        # 查询缓存 - 不应抛出异常
        result = await cache_service.get_cached_result(rubric_text, image_data)
        
        # 验证：返回 None 而不是抛出异常
        assert result is None, \
            "缓存数据损坏时应返回 None，而不是抛出异常"

    @settings(max_examples=100, deadline=None)
    @given(
        rubric_text=st.text(min_size=1, max_size=500),
        image_data=random_image_data()
    )
    @pytest.mark.asyncio
    async def test_cache_lookup_with_incomplete_data_returns_none(
        self, 
        rubric_text: str, 
        image_data: bytes
    ):
        """
        **功能: ai-grading-agent, 属性 12: 缓存失败不阻塞批改**
        **验证: 需求 6.4**
        
        验证：当缓存数据不完整（缺少必需字段）时，服务应当返回 None 而不是抛出异常。
        """
        # 确保输入有效
        assume(len(rubric_text.strip()) > 0)
        
        # 创建 Mock Redis 客户端，返回不完整的数据
        mock_redis = AsyncMock()
        incomplete_data = json.dumps({"question_id": "q1"})  # 缺少必需字段
        mock_redis.get.return_value = incomplete_data
        
        # 创建缓存服务
        cache_service = CacheService(redis_client=mock_redis)
        
        # 查询缓存 - 不应抛出异常
        result = await cache_service.get_cached_result(rubric_text, image_data)
        
        # 验证：返回 None 而不是抛出异常
        assert result is None, \
            "缓存数据不完整时应返回 None，而不是抛出异常"

    @settings(max_examples=100, deadline=None)
    @given(
        rubric_text=st.text(min_size=1, max_size=500),
        image_data=random_image_data(),
        grading_result=grading_result_strategy()
    )
    @pytest.mark.asyncio
    async def test_grading_continues_after_cache_lookup_failure(
        self, 
        rubric_text: str, 
        image_data: bytes,
        grading_result: GradingResult
    ):
        """
        **功能: ai-grading-agent, 属性 12: 缓存失败不阻塞批改**
        **验证: 需求 6.4**
        
        验证：缓存查找失败后，批改流程应当能够正常继续。
        模拟完整的批改流程：缓存查找失败 -> 执行批改 -> 缓存存储失败 -> 返回结果
        """
        # 确保输入有效
        assume(len(rubric_text.strip()) > 0)
        
        # 创建 Mock Redis 客户端，模拟所有操作失败
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = RedisError("Connection failed")
        mock_redis.setex.side_effect = RedisError("Connection failed")
        
        # 创建缓存服务
        cache_service = CacheService(redis_client=mock_redis)
        
        # 模拟批改流程
        # 1. 尝试从缓存获取结果（失败）
        cached_result = await cache_service.get_cached_result(rubric_text, image_data)
        assert cached_result is None, "缓存查找失败应返回 None"
        
        # 2. 执行批改（模拟）- 这里直接使用传入的 grading_result
        # 在实际系统中，这里会调用 LLM 进行批改
        
        # 3. 尝试缓存结果（失败）
        cache_success = await cache_service.cache_result(rubric_text, image_data, grading_result)
        assert cache_success is False, "缓存存储失败应返回 False"
        
        # 4. 验证：批改结果仍然有效
        assert grading_result.question_id is not None
        assert 0 <= grading_result.score <= grading_result.max_score
        assert 0 <= grading_result.confidence <= 1.0

    @settings(max_examples=100, deadline=None)
    @given(
        rubric_text=st.text(min_size=1, max_size=500),
        image_data=random_image_data(),
        grading_result=grading_result_strategy()
    )
    @pytest.mark.asyncio
    async def test_cache_failure_does_not_corrupt_result(
        self, 
        rubric_text: str, 
        image_data: bytes,
        grading_result: GradingResult
    ):
        """
        **功能: ai-grading-agent, 属性 12: 缓存失败不阻塞批改**
        **验证: 需求 6.4**
        
        验证：缓存失败不应当修改或损坏批改结果。
        """
        # 确保输入有效
        assume(len(rubric_text.strip()) > 0)
        
        # 保存原始结果的副本
        original_question_id = grading_result.question_id
        original_score = grading_result.score
        original_max_score = grading_result.max_score
        original_confidence = grading_result.confidence
        original_feedback = grading_result.feedback
        
        # 创建 Mock Redis 客户端，模拟存储失败
        mock_redis = AsyncMock()
        mock_redis.setex.side_effect = RedisError("Connection failed")
        
        # 创建缓存服务
        cache_service = CacheService(redis_client=mock_redis)
        
        # 尝试缓存结果（失败）
        await cache_service.cache_result(rubric_text, image_data, grading_result)
        
        # 验证：结果未被修改
        assert grading_result.question_id == original_question_id, \
            "缓存失败不应修改 question_id"
        assert grading_result.score == original_score, \
            "缓存失败不应修改 score"
        assert grading_result.max_score == original_max_score, \
            "缓存失败不应修改 max_score"
        assert grading_result.confidence == original_confidence, \
            "缓存失败不应修改 confidence"
        assert grading_result.feedback == original_feedback, \
            "缓存失败不应修改 feedback"

    @settings(max_examples=100, deadline=None)
    @given(
        rubric_text=st.text(min_size=1, max_size=500),
        redis_error=redis_error_strategy
    )
    @pytest.mark.asyncio
    async def test_cache_invalidation_failure_returns_zero(
        self, 
        rubric_text: str,
        redis_error: Exception
    ):
        """
        **功能: ai-grading-agent, 属性 12: 缓存失败不阻塞批改**
        **验证: 需求 6.4**
        
        验证：当缓存失效操作失败时，服务应当返回 0 而不是抛出异常。
        """
        # 确保输入有效
        assume(len(rubric_text.strip()) > 0)
        
        # 创建 Mock Redis 客户端，模拟 scan 操作失败
        mock_redis = AsyncMock()
        mock_redis.scan.side_effect = redis_error
        
        # 创建缓存服务
        cache_service = CacheService(redis_client=mock_redis)
        
        # 尝试失效缓存 - 不应抛出异常
        deleted_count = await cache_service.invalidate_by_rubric(rubric_text)
        
        # 验证：返回 0 而不是抛出异常
        assert deleted_count == 0, \
            f"缓存失效失败时应返回 0，而不是抛出异常: {type(redis_error).__name__}"

    @settings(max_examples=100, deadline=None)
    @given(
        rubric_text=st.text(min_size=1, max_size=500),
        image_data=random_image_data()
    )
    @pytest.mark.asyncio
    async def test_multiple_consecutive_failures_handled_gracefully(
        self, 
        rubric_text: str, 
        image_data: bytes
    ):
        """
        **功能: ai-grading-agent, 属性 12: 缓存失败不阻塞批改**
        **验证: 需求 6.4**
        
        验证：多次连续的缓存失败应当被优雅处理，不会导致系统崩溃。
        """
        # 确保输入有效
        assume(len(rubric_text.strip()) > 0)
        
        # 创建 Mock Redis 客户端，模拟所有操作失败
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = RedisError("Connection failed")
        mock_redis.setex.side_effect = RedisError("Connection failed")
        mock_redis.scan.side_effect = RedisError("Connection failed")
        
        # 创建缓存服务
        cache_service = CacheService(redis_client=mock_redis)
        
        # 创建测试结果
        test_result = GradingResult(
            question_id="test_q1",
            score=8.0,
            max_score=10.0,
            confidence=0.95,
            feedback="Test feedback",
            visual_annotations=[],
            agent_trace={"vision_analysis": "test"}
        )
        
        # 执行多次操作，所有操作都应当优雅失败
        for _ in range(5):
            # 查找失败
            result = await cache_service.get_cached_result(rubric_text, image_data)
            assert result is None
            
            # 存储失败
            success = await cache_service.cache_result(rubric_text, image_data, test_result)
            assert success is False
            
            # 失效失败
            deleted = await cache_service.invalidate_by_rubric(rubric_text)
            assert deleted == 0

    @settings(max_examples=100, deadline=None)
    @given(
        rubric_text=st.text(min_size=1, max_size=500),
        image_data=random_image_data()
    )
    @pytest.mark.asyncio
    async def test_unexpected_exception_handled_gracefully(
        self, 
        rubric_text: str, 
        image_data: bytes
    ):
        """
        **功能: ai-grading-agent, 属性 12: 缓存失败不阻塞批改**
        **验证: 需求 6.4**
        
        验证：即使发生未预期的异常，缓存服务也应当优雅处理。
        """
        # 确保输入有效
        assume(len(rubric_text.strip()) > 0)
        
        # 创建 Mock Redis 客户端，模拟未预期的异常
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = RuntimeError("Unexpected error")
        mock_redis.setex.side_effect = RuntimeError("Unexpected error")
        
        # 创建缓存服务
        cache_service = CacheService(redis_client=mock_redis)
        
        # 创建测试结果
        test_result = GradingResult(
            question_id="test_q1",
            score=8.0,
            max_score=10.0,
            confidence=0.95,
            feedback="Test feedback",
            visual_annotations=[],
            agent_trace={"vision_analysis": "test"}
        )
        
        # 查找应当返回 None 而不是抛出异常
        result = await cache_service.get_cached_result(rubric_text, image_data)
        assert result is None, "未预期异常时应返回 None"
        
        # 存储应当返回 False 而不是抛出异常
        success = await cache_service.cache_result(rubric_text, image_data, test_result)
        assert success is False, "未预期异常时应返回 False"
