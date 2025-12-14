"""
属性测试：评分细则哈希预计算

**功能: architecture-deep-integration, 属性 11: 评分细则哈希预计算**
**验证: 需求 6.2**

测试评分细则创建时预计算并缓存哈希值，后续查询能够从缓存获取。
"""

import pytest
import asyncio
from hypothesis import given, strategies as st, settings, Phase
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from src.services.cache_warmup import CacheWarmupService
from src.utils.pool_manager import UnifiedPoolManager
from src.services.multi_layer_cache import MultiLayerCacheService, CacheConfig
from src.utils.hashing import compute_rubric_hash


# 配置 Hypothesis
settings.register_profile(
    "ci",
    max_examples=100,
    phases=[Phase.generate, Phase.target, Phase.shrink]
)
settings.load_profile("ci")


# 策略：生成评分细则文本
rubric_text_strategy = st.text(min_size=10, max_size=500)

# 策略：生成考试 ID 和题目 ID
exam_id_strategy = st.text(
    min_size=5,
    max_size=20,
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_-")
)
question_id_strategy = st.text(
    min_size=1,
    max_size=10,
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_-")
)


@pytest.fixture
async def mock_pool_manager():
    """创建模拟的连接池管理器"""
    pool_manager = MagicMock(spec=UnifiedPoolManager)
    
    # 模拟 Redis 客户端
    redis_client = AsyncMock()
    redis_client.setex = AsyncMock()
    redis_client.get = AsyncMock()
    redis_client.delete = AsyncMock(return_value=1)
    
    pool_manager.get_redis_client.return_value = redis_client
    
    return pool_manager


@pytest.fixture
async def cache_service(mock_pool_manager):
    """创建缓存服务"""
    config = CacheConfig(
        pubsub_channel="test_cache_invalidation",
        enable_pubsub=False  # 测试时禁用 Pub/Sub
    )
    service = MultiLayerCacheService(mock_pool_manager, config)
    return service


@pytest.fixture
async def warmup_service(mock_pool_manager, cache_service):
    """创建缓存预热服务"""
    service = CacheWarmupService(
        pool_manager=mock_pool_manager,
        cache_service=cache_service,
        high_confidence_threshold=0.9,
        warmup_days=7,
        batch_size=100
    )
    return service


@given(
    rubric_text=rubric_text_strategy,
    exam_id=exam_id_strategy,
    question_id=question_id_strategy
)
@settings(max_examples=100, deadline=None)
def test_rubric_hash_precomputation(
    rubric_text: str,
    exam_id: str,
    question_id: str
):
    """
    **功能: architecture-deep-integration, 属性 11: 评分细则哈希预计算**
    **验证: 需求 6.2**
    
    属性：对于任意新创建的评分细则，系统应当预计算并缓存该细则的哈希值，
    后续查询应当能够从缓存获取哈希值。
    
    测试步骤：
    1. 创建评分细则并预计算哈希
    2. 验证哈希值被正确计算
    3. 验证哈希值被缓存到 Redis
    4. 模拟从缓存查询哈希值
    5. 验证查询到的哈希值与预计算的一致
    """
    async def run_test():
        # 创建模拟的连接池管理器
        pool_manager = MagicMock(spec=UnifiedPoolManager)
        
        # 存储缓存的数据
        cache_storage = {}
        
        # 模拟 Redis 客户端
        redis_client = AsyncMock()
        
        async def mock_setex(key, ttl, value):
            cache_storage[key] = value
        
        async def mock_get(key):
            return cache_storage.get(key)
        
        redis_client.setex = mock_setex
        redis_client.get = mock_get
        
        pool_manager.get_redis_client.return_value = redis_client
        
        # 创建缓存服务
        config = CacheConfig(enable_pubsub=False)
        cache_service = MultiLayerCacheService(pool_manager, config)
        
        # 创建预热服务
        warmup_service = CacheWarmupService(
            pool_manager=pool_manager,
            cache_service=cache_service
        )
        
        # 生成评分细则 ID
        rubric_id = f"rubric_{exam_id}_{question_id}"
        
        # 步骤 1: 预计算哈希
        computed_hash = await warmup_service.precompute_rubric_hash(
            rubric_id=rubric_id,
            rubric_text=rubric_text,
            exam_id=exam_id,
            question_id=question_id
        )
        
        # 步骤 2: 验证哈希值被正确计算
        expected_hash = compute_rubric_hash(rubric_text)
        assert computed_hash == expected_hash, (
            f"预计算的哈希值不正确: expected={expected_hash}, got={computed_hash}"
        )
        
        # 步骤 3: 验证哈希值被缓存
        cache_key = f"{config.hot_cache_prefix}:rubric_hash:{exam_id}:{question_id}"
        assert cache_key in cache_storage, (
            f"哈希值未被缓存: key={cache_key}"
        )
        
        # 步骤 4: 从缓存查询哈希值
        cached_hash = await warmup_service.get_cached_rubric_hash(
            exam_id=exam_id,
            question_id=question_id
        )
        
        # 步骤 5: 验证查询到的哈希值与预计算的一致
        assert cached_hash is not None, (
            f"未能从缓存获取哈希值: exam_id={exam_id}, question_id={question_id}"
        )
        assert cached_hash == expected_hash, (
            f"缓存的哈希值不一致: expected={expected_hash}, cached={cached_hash}"
        )
        
        # 额外验证：相同的评分细则文本应产生相同的哈希
        hash_again = compute_rubric_hash(rubric_text)
        assert hash_again == expected_hash, (
            f"相同文本的哈希值不一致: first={expected_hash}, second={hash_again}"
        )
    
    # 运行异步测试
    asyncio.run(run_test())


@given(
    rubric_text=rubric_text_strategy,
    exam_id=exam_id_strategy,
    question_id=question_id_strategy
)
@settings(max_examples=50, deadline=None)
def test_rubric_hash_cache_invalidation(
    rubric_text: str,
    exam_id: str,
    question_id: str
):
    """
    测试评分细则哈希缓存失效
    
    验证当评分细则更新或删除时，哈希缓存能够正确失效。
    """
    async def run_test():
        # 创建模拟的连接池管理器
        pool_manager = MagicMock(spec=UnifiedPoolManager)
        
        # 存储缓存的数据
        cache_storage = {}
        
        # 模拟 Redis 客户端
        redis_client = AsyncMock()
        
        async def mock_setex(key, ttl, value):
            cache_storage[key] = value
        
        async def mock_get(key):
            return cache_storage.get(key)
        
        async def mock_delete(key):
            if key in cache_storage:
                del cache_storage[key]
                return 1
            return 0
        
        redis_client.setex = mock_setex
        redis_client.get = mock_get
        redis_client.delete = mock_delete
        
        pool_manager.get_redis_client.return_value = redis_client
        
        # 创建缓存服务
        config = CacheConfig(enable_pubsub=False)
        cache_service = MultiLayerCacheService(pool_manager, config)
        
        # 创建预热服务
        warmup_service = CacheWarmupService(
            pool_manager=pool_manager,
            cache_service=cache_service
        )
        
        # 预计算哈希
        rubric_id = f"rubric_{exam_id}_{question_id}"
        computed_hash = await warmup_service.precompute_rubric_hash(
            rubric_id=rubric_id,
            rubric_text=rubric_text,
            exam_id=exam_id,
            question_id=question_id
        )
        
        # 验证哈希已缓存
        cached_hash = await warmup_service.get_cached_rubric_hash(
            exam_id=exam_id,
            question_id=question_id
        )
        assert cached_hash == computed_hash, "哈希未正确缓存"
        
        # 使缓存失效
        success = await warmup_service.invalidate_rubric_hash_cache(
            exam_id=exam_id,
            question_id=question_id
        )
        assert success, "缓存失效操作失败"
        
        # 验证缓存已失效
        cached_hash_after = await warmup_service.get_cached_rubric_hash(
            exam_id=exam_id,
            question_id=question_id
        )
        assert cached_hash_after is None, (
            f"缓存失效后仍能查询到哈希值: {cached_hash_after}"
        )
    
    # 运行异步测试
    asyncio.run(run_test())


@given(
    rubric_texts=st.lists(
        rubric_text_strategy,
        min_size=2,
        max_size=5,
        unique=True
    ),
    exam_id=exam_id_strategy,
    question_id=question_id_strategy
)
@settings(max_examples=50, deadline=None)
def test_different_rubrics_different_hashes(
    rubric_texts: list,
    exam_id: str,
    question_id: str
):
    """
    测试不同的评分细则产生不同的哈希值
    
    验证哈希函数的唯一性。
    """
    async def run_test():
        # 计算所有评分细则的哈希
        hashes = [compute_rubric_hash(text) for text in rubric_texts]
        
        # 验证所有哈希值都不相同
        unique_hashes = set(hashes)
        assert len(unique_hashes) == len(hashes), (
            f"不同的评分细则产生了相同的哈希值: "
            f"texts={len(rubric_texts)}, unique_hashes={len(unique_hashes)}"
        )
    
    # 运行异步测试
    asyncio.run(run_test())


@given(
    rubric_text=rubric_text_strategy,
    exam_id=exam_id_strategy,
    question_id=question_id_strategy
)
@settings(max_examples=50, deadline=None)
def test_hash_deterministic(
    rubric_text: str,
    exam_id: str,
    question_id: str
):
    """
    测试哈希计算的确定性
    
    验证相同的评分细则文本总是产生相同的哈希值。
    """
    async def run_test():
        # 多次计算哈希
        hash1 = compute_rubric_hash(rubric_text)
        hash2 = compute_rubric_hash(rubric_text)
        hash3 = compute_rubric_hash(rubric_text)
        
        # 验证所有哈希值都相同
        assert hash1 == hash2 == hash3, (
            f"相同文本的哈希值不一致: "
            f"hash1={hash1}, hash2={hash2}, hash3={hash3}"
        )
    
    # 运行异步测试
    asyncio.run(run_test())
