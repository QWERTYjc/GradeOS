"""属性测试：历史查询完整性

验证补丁历史查询返回完整信息。
**Feature: self-evolving-grading, Property 29: 历史查询完整性**
**Validates: Requirements 10.4**
"""

import pytest
from hypothesis import given, strategies as st, settings, Phase, HealthCheck
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

from src.services.version_manager import VersionManager, PatchVersion
from src.models.rule_patch import PatchStatus


# 配置 Hypothesis
settings.register_profile(
    "ci",
    max_examples=100,
    phases=[Phase.generate, Phase.target, Phase.shrink],
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
settings.load_profile("ci")


@pytest.mark.asyncio
@given(
    n_patches=st.integers(min_value=1, max_value=100),
    limit=st.integers(min_value=1, max_value=50)
)
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_history_query_completeness(n_patches: int, limit: int):
    """
    **Feature: self-evolving-grading, Property 29: 历史查询完整性**
    **Validates: Requirements 10.4**
    
    属性：对于任意补丁历史查询，返回的列表应包含：version、created_at、status。
    
    测试策略：
    1. 创建多个补丁
    2. 查询历史
    3. 验证返回的记录包含所有必要字段
    """
    # 创建模拟的补丁数据
    patches = []
    base_time = datetime.utcnow()
    
    for i in range(n_patches):
        patches.append({
            "patch_id": str(uuid4()),
            "version": f"v1.0.{i}",
            "status": "deployed" if i % 2 == 0 else "candidate",
            "dependencies": [],
            "created_at": base_time + timedelta(minutes=i),
            "deployed_at": base_time + timedelta(minutes=i, seconds=30) if i % 2 == 0 else None
        })
    
    # 按创建时间倒序排列
    patches_sorted = sorted(patches, key=lambda x: x["created_at"], reverse=True)
    
    # 限制返回数量
    expected_count = min(limit, n_patches)
    expected_patches = patches_sorted[:expected_count]
    
    # 创建 mock
    pool = AsyncMock()
    conn = AsyncMock()
    
    async def mock_fetch(query, *args):
        if "ORDER BY created_at DESC" in query:
            # 返回限制数量的补丁
            return expected_patches
        return []
    
    conn.fetch = AsyncMock(side_effect=mock_fetch)
    
    pool.connection = MagicMock()
    pool.connection.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.connection.return_value.__aexit__ = AsyncMock(return_value=None)
    
    with patch('src.services.version_manager.get_db_pool', return_value=pool):
        manager = VersionManager()
        
        # 查询历史
        history = await manager.get_history(limit=limit)
        
        # 验证返回数量
        assert len(history) == expected_count, (
            f"历史记录数量不正确：期望 {expected_count}，实际 {len(history)}"
        )
        
        # 验证每条记录的完整性
        for i, record in enumerate(history):
            assert isinstance(record, PatchVersion), (
                f"记录 {i} 类型错误：{type(record)}"
            )
            
            # 验证必要字段
            assert record.version is not None, f"记录 {i} 缺少 version"
            assert record.patch_id is not None, f"记录 {i} 缺少 patch_id"
            assert record.created_at is not None, f"记录 {i} 缺少 created_at"
            assert record.status is not None, f"记录 {i} 缺少 status"
            
            # 验证字段类型
            assert isinstance(record.version, str), f"记录 {i} version 类型错误"
            assert isinstance(record.patch_id, str), f"记录 {i} patch_id 类型错误"
            assert isinstance(record.created_at, datetime), f"记录 {i} created_at 类型错误"
            assert isinstance(record.status, PatchStatus), f"记录 {i} status 类型错误"


@pytest.mark.asyncio
async def test_history_query_ordering():
    """
    测试历史查询的排序
    
    验证历史记录按创建时间倒序排列。
    """
    # 创建多个补丁，时间递增
    patches = []
    base_time = datetime.utcnow()
    
    for i in range(10):
        patches.append({
            "patch_id": str(uuid4()),
            "version": f"v1.0.{i}",
            "status": "deployed",
            "dependencies": [],
            "created_at": base_time + timedelta(minutes=i),
            "deployed_at": base_time + timedelta(minutes=i, seconds=30)
        })
    
    # 按创建时间倒序排列
    patches_sorted = sorted(patches, key=lambda x: x["created_at"], reverse=True)
    
    pool = AsyncMock()
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=patches_sorted)
    
    pool.connection = MagicMock()
    pool.connection.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.connection.return_value.__aexit__ = AsyncMock(return_value=None)
    
    with patch('src.services.version_manager.get_db_pool', return_value=pool):
        manager = VersionManager()
        
        # 查询历史
        history = await manager.get_history(limit=10)
        
        # 验证排序
        for i in range(len(history) - 1):
            assert history[i].created_at >= history[i + 1].created_at, (
                f"历史记录排序错误：记录 {i} 的时间 {history[i].created_at} "
                f"应该 >= 记录 {i+1} 的时间 {history[i+1].created_at}"
            )


@pytest.mark.asyncio
async def test_history_query_empty():
    """
    测试空历史查询
    
    验证当没有补丁时，查询返回空列表。
    """
    pool = AsyncMock()
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])  # 没有补丁
    
    pool.connection = MagicMock()
    pool.connection.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.connection.return_value.__aexit__ = AsyncMock(return_value=None)
    
    with patch('src.services.version_manager.get_db_pool', return_value=pool):
        manager = VersionManager()
        
        # 查询历史
        history = await manager.get_history()
        
        # 验证返回空列表
        assert history == [], "空历史应该返回空列表"
        assert len(history) == 0, "空历史长度应该为 0"


@pytest.mark.asyncio
async def test_history_query_with_dependencies():
    """
    测试包含依赖关系的历史查询
    
    验证历史记录正确包含依赖信息。
    """
    patches = [
        {
            "patch_id": str(uuid4()),
            "version": "v1.0.0",
            "status": "deployed",
            "dependencies": [],
            "created_at": datetime.utcnow(),
            "deployed_at": datetime.utcnow()
        },
        {
            "patch_id": str(uuid4()),
            "version": "v1.0.1",
            "status": "deployed",
            "dependencies": ["v1.0.0"],
            "created_at": datetime.utcnow() + timedelta(minutes=1),
            "deployed_at": datetime.utcnow() + timedelta(minutes=1)
        },
        {
            "patch_id": str(uuid4()),
            "version": "v1.0.2",
            "status": "deployed",
            "dependencies": ["v1.0.0", "v1.0.1"],
            "created_at": datetime.utcnow() + timedelta(minutes=2),
            "deployed_at": datetime.utcnow() + timedelta(minutes=2)
        }
    ]
    
    # 按创建时间倒序
    patches_sorted = sorted(patches, key=lambda x: x["created_at"], reverse=True)
    
    pool = AsyncMock()
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=patches_sorted)
    
    pool.connection = MagicMock()
    pool.connection.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.connection.return_value.__aexit__ = AsyncMock(return_value=None)
    
    with patch('src.services.version_manager.get_db_pool', return_value=pool):
        manager = VersionManager()
        
        # 查询历史
        history = await manager.get_history()
        
        # 验证依赖关系
        assert len(history) == 3
        
        # v1.0.2 应该依赖 v1.0.0 和 v1.0.1
        v102 = next(h for h in history if h.version == "v1.0.2")
        assert "v1.0.0" in v102.dependencies
        assert "v1.0.1" in v102.dependencies
        
        # v1.0.1 应该依赖 v1.0.0
        v101 = next(h for h in history if h.version == "v1.0.1")
        assert "v1.0.0" in v101.dependencies
        
        # v1.0.0 不应该有依赖
        v100 = next(h for h in history if h.version == "v1.0.0")
        assert len(v100.dependencies) == 0


@pytest.mark.asyncio
async def test_history_query_limit():
    """
    测试历史查询的限制参数
    
    验证 limit 参数正确限制返回数量。
    """
    # 创建 100 个补丁
    patches = []
    base_time = datetime.utcnow()
    
    for i in range(100):
        patches.append({
            "patch_id": str(uuid4()),
            "version": f"v1.0.{i}",
            "status": "deployed",
            "dependencies": [],
            "created_at": base_time + timedelta(minutes=i),
            "deployed_at": base_time + timedelta(minutes=i)
        })
    
    # 按创建时间倒序
    patches_sorted = sorted(patches, key=lambda x: x["created_at"], reverse=True)
    
    pool = AsyncMock()
    conn = AsyncMock()
    
    # 模拟数据库限制
    async def mock_fetch(query, *args):
        limit = args[0] if args else 50
        return patches_sorted[:limit]
    
    conn.fetch = AsyncMock(side_effect=mock_fetch)
    
    pool.connection = MagicMock()
    pool.connection.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.connection.return_value.__aexit__ = AsyncMock(return_value=None)
    
    with patch('src.services.version_manager.get_db_pool', return_value=pool):
        manager = VersionManager()
        
        # 测试不同的 limit 值
        for limit in [10, 25, 50]:
            history = await manager.get_history(limit=limit)
            assert len(history) == limit, (
                f"limit={limit} 时，返回数量应该是 {limit}，实际是 {len(history)}"
            )
