"""属性测试：部署记录完整性

验证部署记录包含所有必要信息。
**Feature: self-evolving-grading, Property 27: 部署记录完整性**
**Validates: Requirements 10.2**
"""

import pytest
from hypothesis import given, strategies as st, settings, Phase, HealthCheck
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

from src.services.version_manager import VersionManager
from src.models.rule_patch import PatchType, PatchStatus


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
    
    # 模拟补丁存在
    conn.fetchrow = AsyncMock(return_value={
        "patch_id": str(uuid4()),
        "version": "v1.0.0"
    })
    conn.execute = AsyncMock()
    
    # 模拟连接上下文管理器
    pool.connection = MagicMock()
    pool.connection.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.connection.return_value.__aexit__ = AsyncMock(return_value=None)
    
    return pool


@pytest.mark.asyncio
@given(
    scope=st.sampled_from(["canary", "full"])
)
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_deployment_record_completeness(scope: str):
    """
    **Feature: self-evolving-grading, Property 27: 部署记录完整性**
    **Validates: Requirements 10.2**
    
    属性：对于任意部署的补丁，应记录：deployed_at、deployment_scope。
    
    测试策略：
    1. 创建测试补丁
    2. 记录部署信息
    3. 验证调用了正确的数据库更新操作
    """
    mock_pool = create_mock_db_pool()
    
    with patch('src.services.version_manager.get_db_pool', return_value=mock_pool):
        manager = VersionManager()
        patch_id = str(uuid4())
        
        # 记录部署信息
        success = await manager.record_deployment(patch_id, scope)
        assert success, "记录部署信息失败"
        
        # 验证数据库更新被调用
        assert mock_pool.connection.return_value.__aenter__.return_value.execute.called
        
        # 获取调用参数
        call_args = mock_pool.connection.return_value.__aenter__.return_value.execute.call_args
        query = call_args[0][0]
        params = call_args[0][1:]
        
        # 验证更新了正确的字段
        assert "deployed_at" in query
        assert "deployment_scope" in query
        assert "status" in query
        
        # 验证参数
        assert scope in params
        assert patch_id in params


@pytest.mark.asyncio
async def test_deployment_record_invalid_scope():
    """
    测试无效部署范围的处理
    
    验证传入无效的 scope 参数时会抛出异常。
    """
    mock_pool = create_mock_db_pool()
    
    with patch('src.services.version_manager.get_db_pool', return_value=mock_pool):
        manager = VersionManager()
        patch_id = str(uuid4())
        
        # 尝试使用无效的 scope
        with pytest.raises(ValueError, match="无效的部署范围"):
            await manager.record_deployment(patch_id, "invalid_scope")


@pytest.mark.asyncio
async def test_deployment_record_nonexistent_patch():
    """
    测试记录不存在补丁的部署信息
    
    验证尝试记录不存在的补丁时会抛出异常。
    """
    # 模拟补丁不存在
    pool = AsyncMock()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)  # 补丁不存在
    conn.execute = AsyncMock()
    
    pool.connection = MagicMock()
    pool.connection.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.connection.return_value.__aexit__ = AsyncMock(return_value=None)
    
    with patch('src.services.version_manager.get_db_pool', return_value=pool):
        manager = VersionManager()
        fake_patch_id = "00000000-0000-0000-0000-000000000000"
        
        # 尝试记录部署信息
        with pytest.raises(ValueError, match="不存在"):
            await manager.record_deployment(fake_patch_id, "canary")


@pytest.mark.asyncio
async def test_deployment_status_update():
    """
    测试部署状态的正确更新
    
    验证 canary 部署更新状态为 testing，full 部署更新状态为 deployed。
    """
    mock_pool = create_mock_db_pool()
    
    with patch('src.services.version_manager.get_db_pool', return_value=mock_pool):
        manager = VersionManager()
        
        # 测试 canary 部署
        patch_id_canary = str(uuid4())
        await manager.record_deployment(patch_id_canary, "canary")
        
        # 获取调用参数
        call_args = mock_pool.connection.return_value.__aenter__.return_value.execute.call_args
        query = call_args[0][0]
        
        # 验证状态逻辑
        assert "WHEN $1 = 'canary' THEN 'testing'" in query
        assert "WHEN $1 = 'full' THEN 'deployed'" in query
        
        # 测试 full 部署
        patch_id_full = str(uuid4())
        await manager.record_deployment(patch_id_full, "full")
        
        # 验证调用了数据库更新
        assert mock_pool.connection.return_value.__aenter__.return_value.execute.call_count >= 2


