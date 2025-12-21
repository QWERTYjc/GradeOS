"""属性测试：版本号唯一性

验证版本管理器分配的版本号全局唯一。
**Feature: self-evolving-grading, Property 26: 版本号唯一性**
**Validates: Requirements 10.1**
"""

import pytest
from hypothesis import given, strategies as st, settings, Phase, HealthCheck
from typing import Set
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from src.services.version_manager import VersionManager


# 配置 Hypothesis
settings.register_profile(
    "ci",
    max_examples=100,
    phases=[Phase.generate, Phase.target, Phase.shrink],
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
settings.load_profile("ci")


def create_mock_db_pool():
    """创建模拟数据库连接池"""
    pool = AsyncMock()
    conn = AsyncMock()
    
    # 模拟空数据库（没有现有版本）
    # 使用 return_value 而不是 side_effect，这样可以无限次返回
    async def mock_fetchrow(query, *args):
        if "COUNT(*)" in query:
            return {"count": 0}  # 版本号唯一
        else:
            return None  # 没有现有版本
    
    conn.fetchrow = AsyncMock(side_effect=mock_fetchrow)
    
    # 模拟连接上下文管理器
    pool.connection = MagicMock()
    pool.connection.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.connection.return_value.__aexit__ = AsyncMock(return_value=None)
    
    return pool


@pytest.mark.asyncio
@given(n_allocations=st.integers(min_value=1, max_value=50))
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_version_uniqueness(n_allocations: int):
    """
    **Feature: self-evolving-grading, Property 26: 版本号唯一性**
    **Validates: Requirements 10.1**
    
    属性：对于任意创建的规则补丁，分配的版本号应全局唯一。
    
    测试策略：
    1. 生成随机数量的版本分配请求
    2. 顺序执行版本分配（模拟数据库递增）
    3. 验证所有分配的版本号都是唯一的
    """
    # 创建一个计数器来模拟数据库中的版本递增
    version_counter = [0]  # 使用列表以便在闭包中修改
    
    async def mock_fetchrow(query, *args):
        if "COUNT(*)" in query:
            return {"count": 0}  # 版本号唯一
        elif "ORDER BY created_at DESC" in query:
            # 返回当前最新版本
            if version_counter[0] == 0:
                return None
            else:
                return {"version": f"v1.0.{version_counter[0] - 1}"}
        else:
            return None
    
    pool = AsyncMock()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(side_effect=mock_fetchrow)
    pool.connection = MagicMock()
    pool.connection.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.connection.return_value.__aexit__ = AsyncMock(return_value=None)
    
    with patch('src.services.version_manager.get_db_pool', return_value=pool):
        manager = VersionManager()
        
        # 顺序分配版本号（模拟数据库递增）
        versions = []
        for _ in range(n_allocations):
            version = await manager.allocate_version()
            versions.append(version)
            version_counter[0] += 1
        
        # 验证唯一性
        unique_versions = set(versions)
        assert len(unique_versions) == n_allocations, (
            f"版本号不唯一：分配了 {n_allocations} 个版本，"
            f"但只有 {len(unique_versions)} 个唯一版本。版本列表：{versions}"
        )
        
        # 验证版本号格式
        for version in versions:
            assert version.startswith('v'), f"版本号格式错误：{version}"
            # 验证版本号包含数字
            assert any(c.isdigit() for c in version), f"版本号缺少数字：{version}"


@pytest.mark.asyncio
async def test_version_uniqueness_across_instances():
    """
    测试跨实例的版本号唯一性
    
    验证多个版本管理器实例分配的版本号也是唯一的。
    """
    # 创建一个共享的计数器
    version_counter = [0]
    
    async def mock_fetchrow(query, *args):
        if "COUNT(*)" in query:
            return {"count": 0}
        elif "ORDER BY created_at DESC" in query:
            if version_counter[0] == 0:
                return None
            else:
                return {"version": f"v1.0.{version_counter[0] - 1}"}
        else:
            return None
    
    pool = AsyncMock()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(side_effect=mock_fetchrow)
    pool.connection = MagicMock()
    pool.connection.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.connection.return_value.__aexit__ = AsyncMock(return_value=None)
    
    with patch('src.services.version_manager.get_db_pool', return_value=pool):
        # 创建多个实例
        manager1 = VersionManager()
        manager2 = VersionManager()
        manager3 = VersionManager()
        
        # 顺序分配版本号
        versions = []
        for manager in [manager1, manager2, manager3]:
            for _ in range(10):
                version = await manager.allocate_version()
                versions.append(version)
                version_counter[0] += 1
        
        # 验证唯一性
        unique_versions = set(versions)
        assert len(unique_versions) == len(versions), (
            f"跨实例版本号不唯一：分配了 {len(versions)} 个版本，"
            f"但只有 {len(unique_versions)} 个唯一版本"
        )


@pytest.mark.asyncio
async def test_version_format_consistency():
    """
    测试版本号格式的一致性
    
    验证所有分配的版本号都遵循相同的格式规范。
    """
    mock_pool = create_mock_db_pool()
    
    with patch('src.services.version_manager.get_db_pool', return_value=mock_pool):
        manager = VersionManager()
        
        # 分配多个版本号
        versions = [await manager.allocate_version() for _ in range(30)]
        
        # 验证格式一致性
        for version in versions:
            # 应该以 'v' 开头
            assert version.startswith('v'), f"版本号格式错误：{version}"
            
            # 应该包含点号分隔符
            parts = version.lstrip('v').split('.')
            assert len(parts) >= 3, f"版本号格式错误（缺少组件）：{version}"
            
            # 主版本号应该是数字
            assert parts[0].isdigit(), f"主版本号不是数字：{version}"


@pytest.mark.asyncio
async def test_version_incremental_allocation():
    """
    测试版本号递增分配
    
    验证版本号按照递增顺序分配。
    """
    # 第一次分配：没有现有版本
    pool1 = AsyncMock()
    conn1 = AsyncMock()
    conn1.fetchrow = AsyncMock(side_effect=[
        None,  # 查询现有版本：无
        {"count": 0}  # 检查唯一性：唯一
    ])
    pool1.connection = MagicMock()
    pool1.connection.return_value.__aenter__ = AsyncMock(return_value=conn1)
    pool1.connection.return_value.__aexit__ = AsyncMock(return_value=None)
    
    with patch('src.services.version_manager.get_db_pool', return_value=pool1):
        manager = VersionManager()
        v1 = await manager.allocate_version()
        assert v1 == "v1.0.0", f"第一个版本应该是 v1.0.0，实际是 {v1}"
    
    # 第二次分配：已有 v1.0.0
    pool2 = AsyncMock()
    conn2 = AsyncMock()
    conn2.fetchrow = AsyncMock(side_effect=[
        {"version": "v1.0.0"},  # 查询现有版本：v1.0.0
        {"count": 0}  # 检查唯一性：唯一
    ])
    pool2.connection = MagicMock()
    pool2.connection.return_value.__aenter__ = AsyncMock(return_value=conn2)
    pool2.connection.return_value.__aexit__ = AsyncMock(return_value=None)
    
    with patch('src.services.version_manager.get_db_pool', return_value=pool2):
        manager2 = VersionManager()
        v2 = await manager2.allocate_version()
        assert v2 == "v1.0.1", f"第二个版本应该是 v1.0.1，实际是 {v2}"


