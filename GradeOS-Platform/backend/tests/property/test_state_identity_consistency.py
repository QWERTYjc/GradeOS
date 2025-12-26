"""
属性测试：状态标识一致性

**功能: architecture-deep-integration, 属性 1: 状态标识一致性**
**验证: 需求 1.1, 1.5**

测试 Temporal workflow_run_id 与 LangGraph thread_id 的一致性，
以及通过 Temporal Query 查询的状态与 LangGraph 最新状态的一致性。
"""

import pytest
from hypothesis import given, strategies as st, settings, Phase
from unittest.mock import MagicMock, AsyncMock, patch
import uuid

from src.workflows.enhanced_workflow import (
    EnhancedWorkflowMixin,
    StateIdentityManager,
)
from src.activities.enhanced_activities import (
    create_langgraph_config_activity,
    get_latest_langgraph_state_activity,
)


# 配置 Hypothesis
settings.register_profile(
    "ci",
    max_examples=100,
    phases=[Phase.generate, Phase.target, Phase.shrink]
)


# ==================== 策略定义 ====================

# 生成有效的 UUID 字符串
uuid_strategy = st.uuids().map(str)

# 生成有效的检查点命名空间
checkpoint_ns_strategy = st.text(
    alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='_-'),
    min_size=0,
    max_size=50
)

# 生成 LangGraph 状态
langgraph_state_strategy = st.fixed_dictionaries({
    "channel_values": st.dictionaries(
        keys=st.text(min_size=1, max_size=20),
        values=st.one_of(
            st.text(max_size=100),
            st.integers(),
            st.floats(allow_nan=False, allow_infinity=False),
            st.booleans(),
        ),
        max_size=10
    ),
    "metadata": st.fixed_dictionaries({
        "source": st.sampled_from(["input", "loop", "update"]),
        "step": st.integers(min_value=-1, max_value=1000),
    }),
})


# ==================== 属性测试 ====================

class TestStateIdentityConsistency:
    """
    状态标识一致性属性测试
    
    **功能: architecture-deep-integration, 属性 1: 状态标识一致性**
    **验证: 需求 1.1, 1.5**
    """
    
    @given(workflow_run_id=uuid_strategy)
    @settings(max_examples=100)
    def test_thread_id_equals_workflow_run_id(self, workflow_run_id: str):
        """
        属性 1.1: thread_id 应当等于 workflow_run_id
        
        *对于任意* Temporal 工作流启动的 LangGraph 智能体，
        传递给智能体的 thread_id 应当等于 workflow_run_id。
        
        **功能: architecture-deep-integration, 属性 1: 状态标识一致性**
        **验证: 需求 1.1**
        """
        # 创建状态标识管理器
        manager = StateIdentityManager(workflow_run_id)
        
        # 验证 thread_id 等于 workflow_run_id
        assert manager.thread_id == workflow_run_id
        assert manager.workflow_run_id == workflow_run_id
        
        # 验证生成的 LangGraph 配置
        config = manager.get_langgraph_config()
        assert config["configurable"]["thread_id"] == workflow_run_id
    
    @given(
        workflow_run_id=uuid_strategy,
        checkpoint_ns=checkpoint_ns_strategy
    )
    @settings(max_examples=100)
    def test_langgraph_config_consistency(
        self,
        workflow_run_id: str,
        checkpoint_ns: str
    ):
        """
        属性 1.2: LangGraph 配置应保持一致性
        
        *对于任意* workflow_run_id 和 checkpoint_ns，
        生成的 LangGraph 配置应当包含正确的 thread_id。
        
        **功能: architecture-deep-integration, 属性 1: 状态标识一致性**
        **验证: 需求 1.1**
        """
        manager = StateIdentityManager(workflow_run_id)
        config = manager.get_langgraph_config(checkpoint_ns)
        
        # 验证配置结构
        assert "configurable" in config
        assert "thread_id" in config["configurable"]
        assert "checkpoint_ns" in config["configurable"]
        
        # 验证值
        assert config["configurable"]["thread_id"] == workflow_run_id
        assert config["configurable"]["checkpoint_ns"] == checkpoint_ns
    
    @given(
        workflow_run_id=uuid_strategy,
        state=langgraph_state_strategy
    )
    @settings(max_examples=100)
    def test_state_cache_consistency(
        self,
        workflow_run_id: str,
        state: dict
    ):
        """
        属性 1.3: 状态缓存应保持一致性
        
        *对于任意* 状态更新，缓存的状态应当与更新的状态一致。
        
        **功能: architecture-deep-integration, 属性 1: 状态标识一致性**
        **验证: 需求 1.5**
        """
        manager = StateIdentityManager(workflow_run_id)
        
        # 初始状态应为 None
        assert manager.get_state_cache() is None
        
        # 更新状态
        manager.update_state_cache(state)
        
        # 验证缓存的状态与更新的状态一致
        cached_state = manager.get_state_cache()
        assert cached_state == state
        assert cached_state["channel_values"] == state["channel_values"]
        assert cached_state["metadata"] == state["metadata"]


class TestEnhancedWorkflowMixinStateIdentity:
    """
    EnhancedWorkflowMixin 状态标识一致性测试
    
    **功能: architecture-deep-integration, 属性 1: 状态标识一致性**
    **验证: 需求 1.1, 1.5**
    """
    
    @given(state=langgraph_state_strategy)
    @settings(max_examples=100)
    def test_langgraph_state_query_consistency(self, state: dict):
        """
        属性 1.4: Query 返回的状态应与 LangGraph 最新状态一致
        
        *对于任意* LangGraph 状态更新，通过 Temporal Query 查询的状态
        应当与 LangGraph 最新状态一致。
        
        **功能: architecture-deep-integration, 属性 1: 状态标识一致性**
        **验证: 需求 1.5**
        """
        # 创建 mixin 实例
        mixin = EnhancedWorkflowMixin()
        
        # 初始状态应为 None
        assert mixin.get_langgraph_state() is None
        
        # 模拟状态更新（通过 Signal）
        full_state = {
            "thread_id": str(uuid.uuid4()),
            "checkpoint_id": str(uuid.uuid4()),
            **state,
            "updated_at": "2024-01-01T00:00:00Z",
        }
        mixin.update_langgraph_state(full_state)
        
        # 验证 Query 返回的状态与更新的状态一致
        queried_state = mixin.get_langgraph_state()
        assert queried_state == full_state
        assert queried_state["channel_values"] == state["channel_values"]
        assert queried_state["metadata"] == state["metadata"]
    
    @given(
        events=st.lists(
            st.fixed_dictionaries({
                "event_type": st.text(min_size=1, max_size=20),
                "payload": st.dictionaries(
                    keys=st.text(min_size=1, max_size=10),
                    values=st.text(max_size=50),
                    max_size=5
                ),
                "timestamp": st.text(min_size=10, max_size=30),
            }),
            min_size=0,
            max_size=10
        )
    )
    @settings(max_examples=100)
    def test_external_events_query_consistency(self, events: list):
        """
        属性 1.5: 外部事件查询应返回所有接收的事件
        
        *对于任意* 外部事件序列，Query 应返回所有已接收的事件。
        
        **功能: architecture-deep-integration, 属性 1: 状态标识一致性**
        **验证: 需求 1.5**
        """
        mixin = EnhancedWorkflowMixin()
        
        # 初始事件列表应为空
        assert mixin.get_external_events() == []
        
        # 接收所有事件
        for event in events:
            mixin.external_event(event)
        
        # 验证 Query 返回所有事件
        queried_events = mixin.get_external_events()
        assert len(queried_events) == len(events)
        
        for i, event in enumerate(events):
            assert queried_events[i] == event


class TestCreateLangGraphConfigActivity:
    """
    create_langgraph_config_activity 测试
    
    **功能: architecture-deep-integration, 属性 1: 状态标识一致性**
    **验证: 需求 1.1**
    """
    
    @given(
        workflow_run_id=uuid_strategy,
        checkpoint_ns=checkpoint_ns_strategy
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_config_thread_id_equals_workflow_run_id(
        self,
        workflow_run_id: str,
        checkpoint_ns: str
    ):
        """
        属性 1.6: Activity 生成的配置中 thread_id 应等于 workflow_run_id
        
        **功能: architecture-deep-integration, 属性 1: 状态标识一致性**
        **验证: 需求 1.1**
        """
        config = await create_langgraph_config_activity(
            workflow_run_id,
            checkpoint_ns
        )
        
        # 验证配置结构
        assert "configurable" in config
        assert config["configurable"]["thread_id"] == workflow_run_id
        assert config["configurable"]["checkpoint_ns"] == checkpoint_ns
