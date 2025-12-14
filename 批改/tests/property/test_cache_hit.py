"""缓存命中行为的属性测试

**功能: ai-grading-agent, 属性 10: 缓存命中返回缓存结果**
**验证: 需求 6.2**

属性定义：
对于任意存在 (rubric_hash, image_hash) 组合缓存条目的批改请求，
服务应当返回缓存结果而不调用 LLM，返回的结果应当与缓存值相同。
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import AsyncMock, MagicMock, patch
from PIL import Image
from io import BytesIO
import json

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
    confidence = draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))
    
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

class TestCacheHitBehavior:
    """缓存命中行为的属性测试"""

    @settings(max_examples=100, deadline=None)
    @given(
        rubric_text=st.text(min_size=1, max_size=500),
        image_data=random_image_data(),
        grading_result=grading_result_strategy()
    )
    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_result(
        self, 
        rubric_text: str, 
        image_data: bytes, 
        grading_result: GradingResult
    ):
        """
        **功能: ai-grading-agent, 属性 10: 缓存命中返回缓存结果**
        **验证: 需求 6.2**
        
        验证：当存在缓存条目时，服务应当返回缓存结果，
        且返回的结果应当与缓存值相同。
        """
        # 确保输入有效
        assume(len(rubric_text.strip()) > 0)
        
        # 创建 Mock Redis 客户端
        mock_redis = AsyncMock()
        
        # 计算预期的缓存键
        expected_cache_key = compute_cache_key(rubric_text, image_data)
        
        # 设置 Mock：Redis 返回缓存的结果
        mock_redis.get.return_value = grading_result.model_dump_json()
        
        # 创建缓存服务
        cache_service = CacheService(redis_client=mock_redis)
        
        # 查询缓存
        result = await cache_service.get_cached_result(rubric_text, image_data)
        
        # 验证：缓存命中时返回结果
        assert result is not None, "缓存命中时应返回结果"
        
        # 验证：返回的结果与缓存值相同
        assert result.question_id == grading_result.question_id, \
            f"question_id 不匹配: {result.question_id} != {grading_result.question_id}"
        assert result.score == grading_result.score, \
            f"score 不匹配: {result.score} != {grading_result.score}"
        assert result.max_score == grading_result.max_score, \
            f"max_score 不匹配: {result.max_score} != {grading_result.max_score}"
        assert result.confidence == grading_result.confidence, \
            f"confidence 不匹配: {result.confidence} != {grading_result.confidence}"
        assert result.feedback == grading_result.feedback, \
            f"feedback 不匹配: {result.feedback} != {grading_result.feedback}"
        
        # 验证：Redis 被正确调用
        mock_redis.get.assert_called_once_with(expected_cache_key)

    @settings(max_examples=100, deadline=None)
    @given(
        rubric_text=st.text(min_size=1, max_size=500),
        image_data=random_image_data()
    )
    @pytest.mark.asyncio
    async def test_cache_miss_returns_none(
        self, 
        rubric_text: str, 
        image_data: bytes
    ):
        """
        **功能: ai-grading-agent, 属性 10: 缓存命中返回缓存结果**
        **验证: 需求 6.2**
        
        验证：当缓存未命中时，服务应当返回 None。
        """
        # 确保输入有效
        assume(len(rubric_text.strip()) > 0)
        
        # 创建 Mock Redis 客户端
        mock_redis = AsyncMock()
        
        # 设置 Mock：Redis 返回 None（缓存未命中）
        mock_redis.get.return_value = None
        
        # 创建缓存服务
        cache_service = CacheService(redis_client=mock_redis)
        
        # 查询缓存
        result = await cache_service.get_cached_result(rubric_text, image_data)
        
        # 验证：缓存未命中时返回 None
        assert result is None, "缓存未命中时应返回 None"

    @settings(max_examples=100, deadline=None)
    @given(
        rubric_text=st.text(min_size=1, max_size=500),
        image_data=random_image_data(),
        grading_result=grading_result_strategy()
    )
    @pytest.mark.asyncio
    async def test_same_key_returns_same_result(
        self, 
        rubric_text: str, 
        image_data: bytes, 
        grading_result: GradingResult
    ):
        """
        **功能: ai-grading-agent, 属性 10: 缓存命中返回缓存结果**
        **验证: 需求 6.2**
        
        验证：对于相同的 (rubric_text, image_data) 组合，
        多次查询应当返回相同的缓存结果。
        """
        # 确保输入有效
        assume(len(rubric_text.strip()) > 0)
        
        # 创建 Mock Redis 客户端
        mock_redis = AsyncMock()
        
        # 设置 Mock：Redis 返回缓存的结果
        mock_redis.get.return_value = grading_result.model_dump_json()
        
        # 创建缓存服务
        cache_service = CacheService(redis_client=mock_redis)
        
        # 多次查询缓存
        result1 = await cache_service.get_cached_result(rubric_text, image_data)
        result2 = await cache_service.get_cached_result(rubric_text, image_data)
        result3 = await cache_service.get_cached_result(rubric_text, image_data)
        
        # 验证：所有结果相同
        assert result1 is not None
        assert result2 is not None
        assert result3 is not None
        
        assert result1.question_id == result2.question_id == result3.question_id
        assert result1.score == result2.score == result3.score
        assert result1.confidence == result2.confidence == result3.confidence

    @settings(max_examples=100, deadline=None)
    @given(
        rubric_text1=st.text(min_size=1, max_size=200),
        rubric_text2=st.text(min_size=1, max_size=200),
        image_data=random_image_data(),
        grading_result1=grading_result_strategy(),
        grading_result2=grading_result_strategy()
    )
    @pytest.mark.asyncio
    async def test_different_rubric_different_cache_key(
        self, 
        rubric_text1: str, 
        rubric_text2: str,
        image_data: bytes, 
        grading_result1: GradingResult,
        grading_result2: GradingResult
    ):
        """
        **功能: ai-grading-agent, 属性 10: 缓存命中返回缓存结果**
        **验证: 需求 6.2**
        
        验证：不同的评分细则应当使用不同的缓存键，
        因此返回不同的缓存结果。
        """
        # 确保两个评分细则不同
        assume(len(rubric_text1.strip()) > 0)
        assume(len(rubric_text2.strip()) > 0)
        assume(rubric_text1 != rubric_text2)
        
        # 计算两个缓存键
        cache_key1 = compute_cache_key(rubric_text1, image_data)
        cache_key2 = compute_cache_key(rubric_text2, image_data)
        
        # 验证：不同的评分细则产生不同的缓存键
        assert cache_key1 != cache_key2, \
            f"不同评分细则应产生不同缓存键: {cache_key1} == {cache_key2}"

    @settings(max_examples=100, deadline=None)
    @given(
        rubric_text=st.text(min_size=1, max_size=500),
        image_data=random_image_data(),
        grading_result=grading_result_strategy()
    )
    @pytest.mark.asyncio
    async def test_cache_roundtrip_preserves_data(
        self, 
        rubric_text: str, 
        image_data: bytes, 
        grading_result: GradingResult
    ):
        """
        **功能: ai-grading-agent, 属性 10: 缓存命中返回缓存结果**
        **验证: 需求 6.2**
        
        验证：缓存的序列化和反序列化过程应当保持数据完整性。
        """
        # 确保输入有效
        assume(len(rubric_text.strip()) > 0)
        
        # 模拟缓存存储和读取的完整流程
        # 序列化
        serialized = grading_result.model_dump_json()
        
        # 反序列化
        deserialized_dict = json.loads(serialized)
        deserialized = GradingResult(**deserialized_dict)
        
        # 验证：数据完整性
        assert deserialized.question_id == grading_result.question_id
        assert deserialized.score == grading_result.score
        assert deserialized.max_score == grading_result.max_score
        assert deserialized.confidence == grading_result.confidence
        assert deserialized.feedback == grading_result.feedback
        assert deserialized.visual_annotations == grading_result.visual_annotations
        assert deserialized.agent_trace == grading_result.agent_trace

