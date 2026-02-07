"""Activity 心跳进度报告属性测试

**功能: architecture-deep-integration, 属性 2: Activity 心跳进度报告**
**验证: 需求 1.2**

属性 2 定义：对于任意 LangGraph 智能体的状态转换，智能体应当通过 Activity Heartbeat 
向 编排运行时 报告进度，心跳间隔不超过配置的超时时间的一半。
"""

import pytest
import asyncio
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import MagicMock, AsyncMock
from contextlib import asynccontextmanager

from src.utils.enhanced_checkpointer import EnhancedPostgresCheckpointer


def create_mock_pool_manager():
    """创建模拟的连接池管理器"""
    manager = MagicMock()
    
    @asynccontextmanager
    async def mock_pg_transaction():
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=AsyncMock(fetchone=AsyncMock(return_value=None)))
        yield mock_conn
    
    @asynccontextmanager
    async def mock_pg_connection():
        mock_conn = AsyncMock()
        mock_result = AsyncMock()
        mock_result.fetchone = AsyncMock(return_value=None)
        mock_result.fetchall = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value=mock_result)
        yield mock_conn
    
    manager.pg_transaction = mock_pg_transaction
    manager.pg_connection = mock_pg_connection
    
    return manager


class TestActivityHeartbeatProgress:
    """Activity 心跳进度报告属性测试
    
    **功能: architecture-deep-integration, 属性 2: Activity 心跳进度报告**
    **验证: 需求 1.2**
    """
    
    @pytest.mark.asyncio
    @given(
        thread_id=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=5, max_size=20),
    )
    @settings(max_examples=30)
    async def test_heartbeat_called_during_put(self, thread_id):
        """
        **功能: architecture-deep-integration, 属性 2: Activity 心跳进度报告**
        **验证: 需求 1.2**
        
        在保存检查点时应当调用心跳回调报告进度。
        """
        pool_manager = create_mock_pool_manager()
        heartbeat_calls = []
        
        def heartbeat_callback(stage, progress):
            heartbeat_calls.append((stage, progress))
        
        checkpointer = EnhancedPostgresCheckpointer(
            pool_manager=pool_manager,
            heartbeat_callback=heartbeat_callback,
        )
        
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
        
        await checkpointer.aput(config, checkpoint, metadata, {})
        
        # 验证心跳被调用
        assert len(heartbeat_calls) > 0, "心跳回调应当被调用"
        
        # 验证有 checkpoint_put 相关的心跳
        put_calls = [c for c in heartbeat_calls if "checkpoint_put" in c[0]]
        assert len(put_calls) > 0, "应当有 checkpoint_put 相关的心跳"
    
    @pytest.mark.asyncio
    @given(
        thread_id=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=5, max_size=20),
    )
    @settings(max_examples=30)
    async def test_heartbeat_called_during_get(self, thread_id):
        """
        **功能: architecture-deep-integration, 属性 2: Activity 心跳进度报告**
        **验证: 需求 1.2**
        
        在获取检查点时应当调用心跳回调报告进度。
        """
        pool_manager = create_mock_pool_manager()
        heartbeat_calls = []
        
        def heartbeat_callback(stage, progress):
            heartbeat_calls.append((stage, progress))
        
        checkpointer = EnhancedPostgresCheckpointer(
            pool_manager=pool_manager,
            heartbeat_callback=heartbeat_callback,
        )
        
        config = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": "",
            }
        }
        
        # 获取检查点（即使不存在也应调用心跳）
        result = await checkpointer.aget(config)
        
        # 验证心跳被调用
        assert len(heartbeat_calls) > 0, "心跳回调应当被调用"
        
        # 验证有 checkpoint_get 相关的心跳
        get_calls = [c for c in heartbeat_calls if "checkpoint_get" in c[0]]
        assert len(get_calls) > 0, "应当有 checkpoint_get 相关的心跳"
    
    @pytest.mark.asyncio
    @given(
        progress_values=st.lists(
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
            min_size=1,
            max_size=10,
        ),
    )
    @settings(max_examples=50)
    async def test_heartbeat_progress_values_valid(self, progress_values):
        """
        **功能: architecture-deep-integration, 属性 2: Activity 心跳进度报告**
        **验证: 需求 1.2**
        
        心跳进度值应当在 0.0 到 1.0 之间。
        """
        pool_manager = create_mock_pool_manager()
        heartbeat_calls = []
        
        def heartbeat_callback(stage, progress):
            heartbeat_calls.append((stage, progress))
        
        checkpointer = EnhancedPostgresCheckpointer(
            pool_manager=pool_manager,
            heartbeat_callback=heartbeat_callback,
        )
        
        # 手动调用心跳报告
        for progress in progress_values:
            checkpointer._report_heartbeat("test_stage", progress)
        
        # 验证所有进度值都在有效范围内
        for stage, progress in heartbeat_calls:
            assert 0.0 <= progress <= 1.0, f"进度值 {progress} 超出有效范围"
    
    @pytest.mark.asyncio
    async def test_heartbeat_not_called_without_callback(self):
        """
        **功能: architecture-deep-integration, 属性 2: Activity 心跳进度报告**
        **验证: 需求 1.2**
        
        当没有配置心跳回调时，不应抛出异常。
        """
        pool_manager = create_mock_pool_manager()
        
        # 不配置心跳回调
        checkpointer = EnhancedPostgresCheckpointer(
            pool_manager=pool_manager,
            heartbeat_callback=None,
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
        
        # 不应抛出异常
        await checkpointer.aput(config, checkpoint, metadata, {})
        await checkpointer.aget(config)
    
    @pytest.mark.asyncio
    async def test_heartbeat_callback_exception_handled(self):
        """
        **功能: architecture-deep-integration, 属性 2: Activity 心跳进度报告**
        **验证: 需求 1.2**
        
        心跳回调抛出异常时不应影响主流程。
        """
        pool_manager = create_mock_pool_manager()
        
        def failing_callback(stage, progress):
            raise Exception("心跳回调失败")
        
        checkpointer = EnhancedPostgresCheckpointer(
            pool_manager=pool_manager,
            heartbeat_callback=failing_callback,
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
        
        # 不应抛出异常
        await checkpointer.aput(config, checkpoint, metadata, {})


class TestHeartbeatProgressSequence:
    """心跳进度序列测试
    
    **功能: architecture-deep-integration, 属性 2: Activity 心跳进度报告**
    **验证: 需求 1.2**
    """
    
    @pytest.mark.asyncio
    async def test_put_progress_sequence(self):
        """
        **功能: architecture-deep-integration, 属性 2: Activity 心跳进度报告**
        **验证: 需求 1.2**
        
        保存检查点时的进度应当从 0 递增到 1。
        """
        pool_manager = create_mock_pool_manager()
        heartbeat_calls = []
        
        def heartbeat_callback(stage, progress):
            heartbeat_calls.append((stage, progress))
        
        checkpointer = EnhancedPostgresCheckpointer(
            pool_manager=pool_manager,
            heartbeat_callback=heartbeat_callback,
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
            "channel_values": {"key": "value"},
            "channel_versions": {},
            "versions_seen": {},
        }
        
        metadata = MagicMock()
        metadata.source = "input"
        metadata.step = 0
        metadata.writes = None
        metadata.parents = {}
        
        await checkpointer.aput(config, checkpoint, metadata, {})
        
        # 获取 checkpoint_put 相关的进度
        put_progress = [p for s, p in heartbeat_calls if s == "checkpoint_put"]
        
        # 验证进度从 0 开始
        assert put_progress[0] == 0.0, "进度应当从 0 开始"
        
        # 验证进度以 1 结束
        assert put_progress[-1] == 1.0, "进度应当以 1 结束"
        
        # 验证进度递增
        for i in range(1, len(put_progress)):
            assert put_progress[i] >= put_progress[i-1], "进度应当递增"

