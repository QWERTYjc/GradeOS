"""检查点保存重试属性测试

**功能: architecture-deep-integration, 属性 18: 检查点保存重试**
**验证: 需求 9.4**

属性 18 定义：对于任意检查点保存失败，系统应当重试最多 3 次，
3 次失败后应当标记任务为需要人工干预。
"""

import pytest
import asyncio
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from contextlib import asynccontextmanager

from src.utils.enhanced_checkpointer import (
    EnhancedPostgresCheckpointer,
    ManualInterventionRequired,
)


def create_mock_pool_manager(fail_count: int = 0):
    """
    创建模拟的连接池管理器
    
    Args:
        fail_count: 前 N 次调用失败
    """
    manager = MagicMock()
    call_count = [0]
    
    @asynccontextmanager
    async def mock_pg_transaction():
        call_count[0] += 1
        if call_count[0] <= fail_count:
            raise Exception(f"模拟数据库错误 (尝试 {call_count[0]})")
        
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=AsyncMock(fetchone=AsyncMock(return_value=None)))
        yield mock_conn
    
    @asynccontextmanager
    async def mock_pg_connection():
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=AsyncMock(fetchone=AsyncMock(return_value=None)))
        yield mock_conn
    
    manager.pg_transaction = mock_pg_transaction
    manager.pg_connection = mock_pg_connection
    
    return manager, call_count


class TestCheckpointSaveRetry:
    """检查点保存重试属性测试
    
    **功能: architecture-deep-integration, 属性 18: 检查点保存重试**
    **验证: 需求 9.4**
    """
    
    @pytest.mark.asyncio
    @given(
        thread_id=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=5, max_size=20),
        fail_count=st.integers(min_value=0, max_value=2),
    )
    @settings(max_examples=30)
    async def test_retry_succeeds_within_limit(self, thread_id, fail_count):
        """
        **功能: architecture-deep-integration, 属性 18: 检查点保存重试**
        **验证: 需求 9.4**
        
        当失败次数小于最大重试次数时，保存应当最终成功。
        """
        pool_manager, call_count = create_mock_pool_manager(fail_count=fail_count)
        
        checkpointer = EnhancedPostgresCheckpointer(
            pool_manager=pool_manager,
            max_retries=3,
        )
        # 设置重试延迟为 0 以加快测试
        checkpointer.RETRY_DELAY = 0
        
        config = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": "",
            }
        }
        
        checkpoint = {
            "id": "test_checkpoint_id",
            "v": 1,
            "ts": "2024-01-01T00:00:00Z",
            "channel_values": {"key": "value"},
            "channel_versions": {},
            "versions_seen": {},
        }
        
        # 创建模拟的 metadata
        metadata = MagicMock()
        metadata.source = "input"
        metadata.step = 0
        metadata.writes = None
        metadata.parents = {}
        
        # 保存应当成功
        result = await checkpointer.aput(config, checkpoint, metadata, {})
        
        assert result is not None
        assert result["configurable"]["thread_id"] == thread_id
        # 验证重试次数
        assert call_count[0] == fail_count + 1
    
    @pytest.mark.asyncio
    @given(
        thread_id=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=5, max_size=20),
    )
    @settings(max_examples=20)
    async def test_retry_fails_after_max_attempts(self, thread_id):
        """
        **功能: architecture-deep-integration, 属性 18: 检查点保存重试**
        **验证: 需求 9.4**
        
        当失败次数达到最大重试次数时，应当抛出 ManualInterventionRequired 异常。
        """
        # 设置失败次数超过最大重试次数
        pool_manager, call_count = create_mock_pool_manager(fail_count=10)
        
        checkpointer = EnhancedPostgresCheckpointer(
            pool_manager=pool_manager,
            max_retries=3,
        )
        checkpointer.RETRY_DELAY = 0
        
        config = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": "",
            }
        }
        
        checkpoint = {
            "id": "test_checkpoint_id",
            "v": 1,
            "ts": "2024-01-01T00:00:00Z",
            "channel_values": {"key": "value"},
            "channel_versions": {},
            "versions_seen": {},
        }
        
        metadata = MagicMock()
        metadata.source = "input"
        metadata.step = 0
        metadata.writes = None
        metadata.parents = {}
        
        # 应当抛出 ManualInterventionRequired
        with pytest.raises(ManualInterventionRequired) as exc_info:
            await checkpointer.aput(config, checkpoint, metadata, {})
        
        # 验证错误消息
        assert "人工干预" in str(exc_info.value)
        # 验证重试了 3 次
        assert call_count[0] == 3
    
    @pytest.mark.asyncio
    @given(
        max_retries=st.integers(min_value=1, max_value=5),
    )
    @settings(max_examples=20)
    async def test_retry_count_matches_config(self, max_retries):
        """
        **功能: architecture-deep-integration, 属性 18: 检查点保存重试**
        **验证: 需求 9.4**
        
        重试次数应当与配置的 max_retries 一致。
        """
        pool_manager, call_count = create_mock_pool_manager(fail_count=100)
        
        checkpointer = EnhancedPostgresCheckpointer(
            pool_manager=pool_manager,
            max_retries=max_retries,
        )
        checkpointer.RETRY_DELAY = 0
        
        config = {
            "configurable": {
                "thread_id": "test_thread",
                "checkpoint_ns": "",
            }
        }
        
        checkpoint = {
            "id": "test_checkpoint_id",
            "v": 1,
            "ts": "2024-01-01T00:00:00Z",
            "channel_values": {},
            "channel_versions": {},
            "versions_seen": {},
        }
        
        metadata = MagicMock()
        metadata.source = "input"
        metadata.step = 0
        metadata.writes = None
        metadata.parents = {}
        
        with pytest.raises(ManualInterventionRequired):
            await checkpointer.aput(config, checkpoint, metadata, {})
        
        # 验证重试次数等于配置值
        assert call_count[0] == max_retries


class TestRetryBehavior:
    """重试行为详细测试
    
    **功能: architecture-deep-integration, 属性 18: 检查点保存重试**
    **验证: 需求 9.4**
    """
    
    @pytest.mark.asyncio
    async def test_first_success_no_retry(self):
        """
        **功能: architecture-deep-integration, 属性 18: 检查点保存重试**
        **验证: 需求 9.4**
        
        第一次成功时不应有重试。
        """
        pool_manager, call_count = create_mock_pool_manager(fail_count=0)
        
        checkpointer = EnhancedPostgresCheckpointer(
            pool_manager=pool_manager,
            max_retries=3,
        )
        
        config = {
            "configurable": {
                "thread_id": "test_thread",
                "checkpoint_ns": "",
            }
        }
        
        checkpoint = {
            "id": "test_id",
            "v": 1,
            "ts": "2024-01-01T00:00:00Z",
            "channel_values": {},
            "channel_versions": {},
            "versions_seen": {},
        }
        
        metadata = MagicMock()
        metadata.source = "input"
        metadata.step = 0
        metadata.writes = None
        metadata.parents = {}
        
        await checkpointer.aput(config, checkpoint, metadata, {})
        
        # 只调用一次
        assert call_count[0] == 1
    
    @pytest.mark.asyncio
    async def test_heartbeat_called_on_retry(self):
        """
        **功能: architecture-deep-integration, 属性 18: 检查点保存重试**
        **验证: 需求 9.4**
        
        重试时应当调用心跳回调。
        """
        pool_manager, _ = create_mock_pool_manager(fail_count=2)
        
        heartbeat_calls = []
        
        def heartbeat_callback(stage, progress):
            heartbeat_calls.append((stage, progress))
        
        checkpointer = EnhancedPostgresCheckpointer(
            pool_manager=pool_manager,
            max_retries=3,
            heartbeat_callback=heartbeat_callback,
        )
        checkpointer.RETRY_DELAY = 0
        
        config = {
            "configurable": {
                "thread_id": "test_thread",
                "checkpoint_ns": "",
            }
        }
        
        checkpoint = {
            "id": "test_id",
            "v": 1,
            "ts": "2024-01-01T00:00:00Z",
            "channel_values": {},
            "channel_versions": {},
            "versions_seen": {},
        }
        
        metadata = MagicMock()
        metadata.source = "input"
        metadata.step = 0
        metadata.writes = None
        metadata.parents = {}
        
        await checkpointer.aput(config, checkpoint, metadata, {})
        
        # 验证心跳被调用
        assert len(heartbeat_calls) > 0
        # 验证有重试相关的心跳
        retry_calls = [c for c in heartbeat_calls if "retry" in c[0]]
        assert len(retry_calls) >= 1
