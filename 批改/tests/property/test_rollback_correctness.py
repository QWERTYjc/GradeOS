"""属性测试：回滚正确性

验证回滚操作正确恢复到指定版本。
**Feature: self-evolving-grading, Property 28: 回滚正确性**
**Validates: Requirements 10.3, 10.5**
"""

import pytest
from hypothesis import given, strategies as st, settings, Phase, HealthCheck
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

from src.services.version_manager import VersionManager, DependencyError
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
    n_patches=st.integers(min_value=3, max_value=10),
    rollback_index=st.integers(min_value=0, max_value=5)
)
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_rollback_correctness(n_patches: int, rollback_index: int):
    """
    **Feature: self-evolving-grading, Property 28: 回滚正确性**
    **Validates: Requirements 10.3, 10.5**
    
    属性：对于任意回滚请求，系统应恢复到指定版本的规则集，且处理依赖关系。
    
    测试策略：
    1. 创建多个补丁版本
    2. 回滚到指定版本
    3. 验证后续版本被标记为 rolled_back
    """
    # 限制 rollback_index 在有效范围内，且确保有补丁需要回滚
    if rollback_index >= n_patches - 1:
        rollback_index = n_patches - 2
    
    # 创建模拟的补丁数据
    patches = []
    base_time = datetime.utcnow()
    
    for i in range(n_patches):
        patches.append({
            "patch_id": str(uuid4()),
            "version": f"v1.0.{i}",
            "status": "deployed" if i < n_patches - 1 else "testing",
            "created_at": base_time + timedelta(minutes=i),
            "dependencies": []
        })
    
    # 目标版本
    target_version = patches[rollback_index]["version"]
    target_created_at = patches[rollback_index]["created_at"]
    
    # 需要回滚的补丁（创建时间晚于目标版本）
    rollback_patches = [p for p in patches if p["created_at"] > target_created_at]
    
    # 确保有补丁需要回滚
    assert len(rollback_patches) > 0, "测试用例应该有补丁需要回滚"
    
    # 创建 mock
    pool = AsyncMock()
    conn = AsyncMock()
    
    # 模拟查询目标版本
    async def mock_fetchrow(query, *args):
        if "WHERE version = $1" in query:
            # 查找目标版本
            for p in patches:
                if p["version"] == args[0]:
                    return p
            return None
        return None
    
    # 模拟查询需要回滚的补丁
    async def mock_fetch(query, *args):
        if "WHERE created_at > $1" in query:
            return rollback_patches
        elif "WHERE status IN" in query and "$1 = ANY(dependencies)" in query:
            # 检查依赖关系
            return []
        return []
    
    conn.fetchrow = AsyncMock(side_effect=mock_fetchrow)
    conn.fetch = AsyncMock(side_effect=mock_fetch)
    conn.execute = AsyncMock()
    
    pool.connection = MagicMock()
    pool.connection.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.connection.return_value.__aexit__ = AsyncMock(return_value=None)
    
    with patch('src.services.version_manager.get_db_pool', return_value=pool):
        manager = VersionManager()
        
        # 执行回滚
        success = await manager.rollback_to_version(target_version)
        assert success, f"回滚到版本 {target_version} 失败"
        
        # 验证数据库更新被调用
        execute_calls = conn.execute.call_count
        
        # 应该调用：len(rollback_patches) 次回滚更新 + 1 次激活目标版本
        expected_calls = len(rollback_patches) + 1
        assert execute_calls == expected_calls, (
            f"数据库更新调用次数不正确：期望 {expected_calls}，实际 {execute_calls}"
        )


@pytest.mark.asyncio
async def test_rollback_with_dependencies():
    """
    测试回滚时的依赖关系处理
    
    验证当存在依赖关系时，回滚会正确检测并抛出异常。
    """
    # 创建有依赖关系的补丁
    patches = [
        {
            "patch_id": str(uuid4()),
            "version": "v1.0.0",
            "status": "deployed",
            "created_at": datetime.utcnow(),
            "dependencies": []
        },
        {
            "patch_id": str(uuid4()),
            "version": "v1.0.1",
            "status": "deployed",
            "created_at": datetime.utcnow() + timedelta(minutes=1),
            "dependencies": ["v1.0.0"]  # 依赖 v1.0.0
        },
        {
            "patch_id": str(uuid4()),
            "version": "v1.0.2",
            "status": "deployed",
            "created_at": datetime.utcnow() + timedelta(minutes=2),
            "dependencies": ["v1.0.1"]  # 依赖 v1.0.1
        }
    ]
    
    # 尝试回滚到 v1.0.0，但 v1.0.2 依赖 v1.0.1
    target_version = "v1.0.0"
    
    pool = AsyncMock()
    conn = AsyncMock()
    
    async def mock_fetchrow(query, *args):
        if "WHERE version = $1" in query:
            for p in patches:
                if p["version"] == args[0]:
                    return p
        return None
    
    async def mock_fetch(query, *args):
        if "WHERE created_at > $1" in query:
            # 返回需要回滚的补丁
            return [p for p in patches if p["version"] in ["v1.0.1", "v1.0.2"]]
        elif "$1 = ANY(dependencies)" in query:
            # v1.0.2 依赖 v1.0.1
            if args[0] == "v1.0.1":
                return [patches[2]]  # v1.0.2
        return []
    
    conn.fetchrow = AsyncMock(side_effect=mock_fetchrow)
    conn.fetch = AsyncMock(side_effect=mock_fetch)
    
    pool.connection = MagicMock()
    pool.connection.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.connection.return_value.__aexit__ = AsyncMock(return_value=None)
    
    with patch('src.services.version_manager.get_db_pool', return_value=pool):
        manager = VersionManager()
        
        # 尝试回滚，应该抛出依赖错误
        with pytest.raises(DependencyError, match="依赖于它"):
            await manager.rollback_to_version(target_version)


@pytest.mark.asyncio
async def test_rollback_to_nonexistent_version():
    """
    测试回滚到不存在的版本
    
    验证尝试回滚到不存在的版本时会抛出异常。
    """
    pool = AsyncMock()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)  # 版本不存在
    
    pool.connection = MagicMock()
    pool.connection.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.connection.return_value.__aexit__ = AsyncMock(return_value=None)
    
    with patch('src.services.version_manager.get_db_pool', return_value=pool):
        manager = VersionManager()
        
        # 尝试回滚到不存在的版本
        with pytest.raises(ValueError, match="不存在"):
            await manager.rollback_to_version("v99.99.99")


@pytest.mark.asyncio
async def test_rollback_idempotency():
    """
    测试回滚的幂等性
    
    验证重复回滚到同一版本不会导致错误。
    """
    target_patch = {
        "patch_id": str(uuid4()),
        "version": "v1.0.0",
        "status": "deployed",
        "created_at": datetime.utcnow(),
        "dependencies": []
    }
    
    pool = AsyncMock()
    conn = AsyncMock()
    
    async def mock_fetchrow(query, *args):
        if "WHERE version = $1" in query:
            return target_patch
        return None
    
    async def mock_fetch(query, *args):
        # 没有需要回滚的补丁
        return []
    
    conn.fetchrow = AsyncMock(side_effect=mock_fetchrow)
    conn.fetch = AsyncMock(side_effect=mock_fetch)
    conn.execute = AsyncMock()
    
    pool.connection = MagicMock()
    pool.connection.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.connection.return_value.__aexit__ = AsyncMock(return_value=None)
    
    with patch('src.services.version_manager.get_db_pool', return_value=pool):
        manager = VersionManager()
        
        # 第一次回滚
        success1 = await manager.rollback_to_version("v1.0.0")
        assert success1, "第一次回滚失败"
        
        # 第二次回滚（幂等）
        success2 = await manager.rollback_to_version("v1.0.0")
        assert success2, "第二次回滚失败"
