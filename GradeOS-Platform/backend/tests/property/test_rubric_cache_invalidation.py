"""评分细则缓存失效的属性测试

**功能: ai-grading-agent, 属性 15: 评分细则更新使缓存失效**
**验证: 需求 9.4**

属性定义：
对于任意评分细则更新操作，所有匹配 rubric_hash 的缓存条目应当被失效（从缓存中删除）。
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import AsyncMock, MagicMock, patch
from PIL import Image
from io import BytesIO

from src.services.cache import CacheService
from src.services.rubric import RubricService
from src.utils.hashing import compute_rubric_hash, compute_cache_key


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
def rubric_text_strategy(draw):
    """
    生成随机的评分细则文本
    
    Args:
        draw: Hypothesis draw 函数
        
    Returns:
        非空的评分细则文本
    """
    text = draw(st.text(
        min_size=10, 
        max_size=500, 
        alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z'))
    ))
    # 确保文本非空且有实际内容
    assume(len(text.strip()) >= 5)
    return text


# ============================================================================
# 属性测试
# ============================================================================

class TestRubricCacheInvalidation:
    """评分细则缓存失效的属性测试"""

    @settings(max_examples=100, deadline=None)
    @given(
        rubric_text=rubric_text_strategy(),
        num_cached_entries=st.integers(min_value=1, max_value=10)
    )
    @pytest.mark.asyncio
    async def test_invalidate_by_rubric_deletes_matching_keys(
        self, 
        rubric_text: str,
        num_cached_entries: int
    ):
        """
        **功能: ai-grading-agent, 属性 15: 评分细则更新使缓存失效**
        **验证: 需求 9.4**
        
        验证：当调用 invalidate_by_rubric 时，所有匹配 rubric_hash 的缓存条目
        应当被删除。
        """
        # 创建 Mock Redis 客户端
        mock_redis = AsyncMock()
        
        # 计算评分细则哈希
        rubric_hash = compute_rubric_hash(rubric_text)
        expected_pattern = f"grade_cache:v1:{rubric_hash}:*"
        
        # 模拟 Redis scan 返回匹配的键
        matching_keys = [
            f"grade_cache:v1:{rubric_hash}:image_hash_{i}".encode()
            for i in range(num_cached_entries)
        ]
        
        # 设置 scan 返回值：第一次返回所有键，cursor 为 0 表示结束
        mock_redis.scan.return_value = (0, matching_keys)
        
        # 设置 delete 返回删除的数量
        mock_redis.delete.return_value = num_cached_entries
        
        # 创建缓存服务
        cache_service = CacheService(redis_client=mock_redis)
        
        # 执行缓存失效
        deleted_count = await cache_service.invalidate_by_rubric(rubric_text)
        
        # 验证：scan 被调用，使用正确的模式
        mock_redis.scan.assert_called()
        call_args = mock_redis.scan.call_args
        assert call_args.kwargs.get('match') == expected_pattern, \
            f"scan 模式不匹配: {call_args.kwargs.get('match')} != {expected_pattern}"
        
        # 验证：delete 被调用，删除了所有匹配的键
        if matching_keys:
            mock_redis.delete.assert_called_once_with(*matching_keys)
        
        # 验证：返回正确的删除数量
        assert deleted_count == num_cached_entries, \
            f"删除数量不匹配: {deleted_count} != {num_cached_entries}"

    @settings(max_examples=100, deadline=None)
    @given(rubric_text=rubric_text_strategy())
    @pytest.mark.asyncio
    async def test_invalidate_by_rubric_no_matching_keys(
        self, 
        rubric_text: str
    ):
        """
        **功能: ai-grading-agent, 属性 15: 评分细则更新使缓存失效**
        **验证: 需求 9.4**
        
        验证：当没有匹配的缓存条目时，invalidate_by_rubric 应当返回 0。
        """
        # 创建 Mock Redis 客户端
        mock_redis = AsyncMock()
        
        # 设置 scan 返回空列表（没有匹配的键）
        mock_redis.scan.return_value = (0, [])
        
        # 创建缓存服务
        cache_service = CacheService(redis_client=mock_redis)
        
        # 执行缓存失效
        deleted_count = await cache_service.invalidate_by_rubric(rubric_text)
        
        # 验证：返回 0
        assert deleted_count == 0, f"没有匹配键时应返回 0，实际返回 {deleted_count}"
        
        # 验证：delete 没有被调用（因为没有键需要删除）
        mock_redis.delete.assert_not_called()

    @settings(max_examples=100, deadline=None)
    @given(
        rubric_text1=rubric_text_strategy(),
        rubric_text2=rubric_text_strategy()
    )
    @pytest.mark.asyncio
    async def test_different_rubrics_have_different_hash_patterns(
        self, 
        rubric_text1: str,
        rubric_text2: str
    ):
        """
        **功能: ai-grading-agent, 属性 15: 评分细则更新使缓存失效**
        **验证: 需求 9.4**
        
        验证：不同的评分细则应当产生不同的哈希值，
        因此失效操作只影响对应的缓存条目。
        """
        # 确保两个评分细则不同
        assume(rubric_text1 != rubric_text2)
        
        # 计算两个评分细则的哈希
        hash1 = compute_rubric_hash(rubric_text1)
        hash2 = compute_rubric_hash(rubric_text2)
        
        # 验证：不同的评分细则产生不同的哈希
        assert hash1 != hash2, \
            f"不同评分细则应产生不同哈希: {hash1} == {hash2}"
        
        # 验证：缓存键模式不同
        pattern1 = f"grade_cache:v1:{hash1}:*"
        pattern2 = f"grade_cache:v1:{hash2}:*"
        
        assert pattern1 != pattern2, \
            f"不同评分细则应产生不同缓存键模式: {pattern1} == {pattern2}"

    @settings(max_examples=100, deadline=None)
    @given(
        rubric_text=rubric_text_strategy(),
        image_data=random_image_data()
    )
    @pytest.mark.asyncio
    async def test_cache_key_contains_rubric_hash(
        self, 
        rubric_text: str,
        image_data: bytes
    ):
        """
        **功能: ai-grading-agent, 属性 15: 评分细则更新使缓存失效**
        **验证: 需求 9.4**
        
        验证：缓存键应当包含评分细则哈希，
        以便失效操作能够正确匹配。
        """
        # 计算评分细则哈希
        rubric_hash = compute_rubric_hash(rubric_text)
        
        # 计算完整的缓存键
        cache_key = compute_cache_key(rubric_text, image_data)
        
        # 验证：缓存键包含评分细则哈希
        assert rubric_hash in cache_key, \
            f"缓存键应包含评分细则哈希: {rubric_hash} not in {cache_key}"
        
        # 验证：缓存键格式正确
        assert cache_key.startswith("grade_cache:v1:"), \
            f"缓存键应以 'grade_cache:v1:' 开头: {cache_key}"

    @settings(max_examples=100, deadline=None)
    @given(rubric_text=rubric_text_strategy())
    @pytest.mark.asyncio
    async def test_invalidate_handles_redis_error_gracefully(
        self, 
        rubric_text: str
    ):
        """
        **功能: ai-grading-agent, 属性 15: 评分细则更新使缓存失效**
        **验证: 需求 9.4**
        
        验证：当 Redis 操作失败时，invalidate_by_rubric 应当优雅降级，
        返回 0 而不抛出异常。
        """
        from redis.exceptions import RedisError
        
        # 创建 Mock Redis 客户端
        mock_redis = AsyncMock()
        
        # 设置 scan 抛出 Redis 错误
        mock_redis.scan.side_effect = RedisError("Connection failed")
        
        # 创建缓存服务
        cache_service = CacheService(redis_client=mock_redis)
        
        # 执行缓存失效 - 不应抛出异常
        deleted_count = await cache_service.invalidate_by_rubric(rubric_text)
        
        # 验证：返回 0（优雅降级）
        assert deleted_count == 0, \
            f"Redis 错误时应返回 0，实际返回 {deleted_count}"

    @settings(max_examples=100, deadline=None)
    @given(
        rubric_text=rubric_text_strategy(),
        num_batches=st.integers(min_value=2, max_value=5),
        keys_per_batch=st.integers(min_value=1, max_value=5)
    )
    @pytest.mark.asyncio
    async def test_invalidate_handles_paginated_scan(
        self, 
        rubric_text: str,
        num_batches: int,
        keys_per_batch: int
    ):
        """
        **功能: ai-grading-agent, 属性 15: 评分细则更新使缓存失效**
        **验证: 需求 9.4**
        
        验证：当缓存条目较多需要分页扫描时，
        invalidate_by_rubric 应当正确处理所有批次。
        """
        # 创建 Mock Redis 客户端
        mock_redis = AsyncMock()
        
        # 计算评分细则哈希
        rubric_hash = compute_rubric_hash(rubric_text)
        
        # 生成多批次的键
        all_keys = []
        scan_results = []
        
        for batch_idx in range(num_batches):
            batch_keys = [
                f"grade_cache:v1:{rubric_hash}:image_{batch_idx}_{i}".encode()
                for i in range(keys_per_batch)
            ]
            all_keys.extend(batch_keys)
            
            # 最后一批 cursor 为 0，其他批次 cursor 为下一批的索引
            next_cursor = 0 if batch_idx == num_batches - 1 else batch_idx + 1
            scan_results.append((next_cursor, batch_keys))
        
        # 设置 scan 返回多批次结果
        mock_redis.scan.side_effect = scan_results
        
        # 设置 delete 返回每批删除的数量
        mock_redis.delete.return_value = keys_per_batch
        
        # 创建缓存服务
        cache_service = CacheService(redis_client=mock_redis)
        
        # 执行缓存失效
        deleted_count = await cache_service.invalidate_by_rubric(rubric_text)
        
        # 验证：scan 被调用了正确的次数
        assert mock_redis.scan.call_count == num_batches, \
            f"scan 调用次数不匹配: {mock_redis.scan.call_count} != {num_batches}"
        
        # 验证：delete 被调用了正确的次数
        assert mock_redis.delete.call_count == num_batches, \
            f"delete 调用次数不匹配: {mock_redis.delete.call_count} != {num_batches}"
        
        # 验证：总删除数量正确
        expected_total = num_batches * keys_per_batch
        assert deleted_count == expected_total, \
            f"总删除数量不匹配: {deleted_count} != {expected_total}"

    @settings(max_examples=100, deadline=None)
    @given(rubric_text=rubric_text_strategy())
    @pytest.mark.asyncio
    async def test_rubric_hash_is_deterministic(
        self, 
        rubric_text: str
    ):
        """
        **功能: ai-grading-agent, 属性 15: 评分细则更新使缓存失效**
        **验证: 需求 9.4**
        
        验证：相同的评分细则文本应当产生相同的哈希值，
        确保失效操作的一致性。
        """
        # 多次计算哈希
        hash1 = compute_rubric_hash(rubric_text)
        hash2 = compute_rubric_hash(rubric_text)
        hash3 = compute_rubric_hash(rubric_text)
        
        # 验证：所有哈希值相同
        assert hash1 == hash2 == hash3, \
            f"相同文本应产生相同哈希: {hash1}, {hash2}, {hash3}"


class TestRubricServiceCacheInvalidation:
    """评分细则服务的缓存失效集成测试"""

    @settings(max_examples=50, deadline=None)
    @given(
        rubric_text=rubric_text_strategy(),
        new_rubric_text=rubric_text_strategy()
    )
    @pytest.mark.asyncio
    async def test_update_rubric_invalidates_cache(
        self, 
        rubric_text: str,
        new_rubric_text: str
    ):
        """
        **功能: ai-grading-agent, 属性 15: 评分细则更新使缓存失效**
        **验证: 需求 9.4**
        
        验证：当通过 RubricService 更新评分细则时，
        相关的缓存条目应当被失效。
        """
        from src.models.rubric import RubricUpdateRequest
        
        # 确保新旧评分细则不同
        assume(rubric_text != new_rubric_text)
        
        # 创建 Mock 仓储
        mock_repository = AsyncMock()
        
        # 设置仓储返回旧评分细则数据
        rubric_id = "test-rubric-id"
        old_rubric_data = {
            "rubric_id": rubric_id,
            "exam_id": "exam-1",
            "question_id": "q-1",
            "rubric_text": rubric_text,
            "max_score": 10.0,
            "scoring_points": [],
            "standard_answer": None,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z"
        }
        
        updated_rubric_data = {
            **old_rubric_data,
            "rubric_text": new_rubric_text,
            "updated_at": "2024-01-02T00:00:00Z"
        }
        
        mock_repository.get_by_id.side_effect = [old_rubric_data, updated_rubric_data]
        mock_repository.update.return_value = True
        
        # 创建 Mock 缓存服务
        mock_cache_service = AsyncMock()
        mock_cache_service.invalidate_by_rubric.return_value = 5
        
        # 创建评分细则服务
        rubric_service = RubricService(
            rubric_repository=mock_repository,
            cache_service=mock_cache_service
        )
        
        # 执行更新
        update_request = RubricUpdateRequest(rubric_text=new_rubric_text)
        await rubric_service.update_rubric(rubric_id, update_request)
        
        # 验证：旧评分细则的缓存被失效
        mock_cache_service.invalidate_by_rubric.assert_any_call(rubric_text)
        
        # 验证：新评分细则的缓存也被失效（因为文本变了）
        mock_cache_service.invalidate_by_rubric.assert_any_call(new_rubric_text)

    @settings(max_examples=50, deadline=None)
    @given(rubric_text=rubric_text_strategy())
    @pytest.mark.asyncio
    async def test_delete_rubric_invalidates_cache(
        self, 
        rubric_text: str
    ):
        """
        **功能: ai-grading-agent, 属性 15: 评分细则更新使缓存失效**
        **验证: 需求 9.4**
        
        验证：当通过 RubricService 删除评分细则时，
        相关的缓存条目应当被失效。
        """
        # 创建 Mock 仓储
        mock_repository = AsyncMock()
        
        # 设置仓储返回评分细则数据
        rubric_id = "test-rubric-id"
        rubric_data = {
            "rubric_id": rubric_id,
            "exam_id": "exam-1",
            "question_id": "q-1",
            "rubric_text": rubric_text,
            "max_score": 10.0,
            "scoring_points": [],
            "standard_answer": None,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z"
        }
        
        mock_repository.get_by_id.return_value = rubric_data
        mock_repository.delete.return_value = True
        
        # 创建 Mock 缓存服务
        mock_cache_service = AsyncMock()
        mock_cache_service.invalidate_by_rubric.return_value = 3
        
        # 创建评分细则服务
        rubric_service = RubricService(
            rubric_repository=mock_repository,
            cache_service=mock_cache_service
        )
        
        # 执行删除
        result = await rubric_service.delete_rubric(rubric_id)
        
        # 验证：删除成功
        assert result is True
        
        # 验证：缓存被失效
        mock_cache_service.invalidate_by_rubric.assert_called_once_with(rubric_text)
