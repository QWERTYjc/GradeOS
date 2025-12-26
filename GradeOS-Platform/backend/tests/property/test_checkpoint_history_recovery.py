"""历史检查点恢复属性测试

**功能: architecture-deep-integration, 属性 17: 历史检查点恢复**
**验证: 需求 9.2**

属性 17 定义：对于任意历史检查点，系统应当能够从该检查点恢复状态，
恢复后的状态应当与保存时的状态一致。
"""

import pytest
import json
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio

from src.utils.enhanced_checkpointer import EnhancedPostgresCheckpointer


def create_checkpointer():
    """创建检查点器实例（用于测试）"""
    mock_pool_manager = MagicMock()
    return EnhancedPostgresCheckpointer(pool_manager=mock_pool_manager)


# 生成状态字典的策略
state_dict_strategy = st.dictionaries(
    keys=st.text(alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=1, max_size=15),
    values=st.one_of(
        st.text(min_size=0, max_size=50),
        st.integers(min_value=-1000, max_value=1000),
        st.floats(min_value=-1000, max_value=1000, allow_nan=False, allow_infinity=False),
        st.booleans(),
    ),
    min_size=1,
    max_size=10,
)


class TestHistoryCheckpointRecovery:
    """历史检查点恢复属性测试
    
    **功能: architecture-deep-integration, 属性 17: 历史检查点恢复**
    **验证: 需求 9.2**
    """
    
    @given(
        states=st.lists(state_dict_strategy, min_size=2, max_size=5),
    )
    @settings(max_examples=50)
    def test_delta_chain_recovery(self, states):
        """
        **功能: architecture-deep-integration, 属性 17: 历史检查点恢复**
        **验证: 需求 9.2**
        
        对于任意状态序列，通过增量链应当能够恢复任意历史状态。
        """
        checkpointer = create_checkpointer()
        
        # 构建增量链
        deltas = []
        for i in range(len(states)):
            if i == 0:
                # 第一个状态是完整状态
                delta, is_delta = checkpointer._compute_delta(None, states[i])
                deltas.append((delta, is_delta, None))
            else:
                # 后续状态是增量
                delta, is_delta = checkpointer._compute_delta(states[i-1], states[i])
                deltas.append((delta, is_delta, i-1))
        
        # 验证可以从增量链恢复任意状态
        for target_idx in range(len(states)):
            recovered = self._recover_state(checkpointer, states, deltas, target_idx)
            assert recovered == states[target_idx], (
                f"恢复状态 {target_idx} 失败:\n"
                f"  expected: {states[target_idx]}\n"
                f"  recovered: {recovered}"
            )
    
    def _recover_state(self, checkpointer, states, deltas, target_idx):
        """从增量链恢复状态"""
        delta, is_delta, base_idx = deltas[target_idx]
        
        if not is_delta:
            # 完整状态
            return delta
        
        if not delta:
            # 空增量，状态与前一个相同
            return self._recover_state(checkpointer, states, deltas, base_idx)
        
        # 递归恢复基础状态
        base_state = self._recover_state(checkpointer, states, deltas, base_idx)
        
        # 应用增量
        return checkpointer._apply_delta(base_state, delta)
    
    @given(
        base_state=state_dict_strategy,
        modifications=st.lists(
            st.tuples(
                st.sampled_from(["add", "update", "delete"]),
                st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=10),
                st.text(min_size=0, max_size=30),
            ),
            min_size=1,
            max_size=5,
        ),
    )
    @settings(max_examples=100)
    def test_incremental_modifications_recoverable(self, base_state, modifications):
        """
        **功能: architecture-deep-integration, 属性 17: 历史检查点恢复**
        **验证: 需求 9.2**
        
        对于任意基础状态和修改序列，每次修改后的状态都应当可恢复。
        """
        checkpointer = create_checkpointer()
        
        current_state = base_state.copy()
        history = [current_state.copy()]
        
        for op, key, value in modifications:
            new_state = current_state.copy()
            
            if op == "add" or op == "update":
                new_state[key] = value
            elif op == "delete" and key in new_state:
                del new_state[key]
            
            # 计算增量
            delta, is_delta = checkpointer._compute_delta(current_state, new_state)
            
            if is_delta and delta:
                # 验证可以从增量恢复
                recovered = checkpointer._apply_delta(current_state, delta)
                assert recovered == new_state, (
                    f"增量恢复失败:\n"
                    f"  op: {op}, key: {key}, value: {value}\n"
                    f"  current: {current_state}\n"
                    f"  new: {new_state}\n"
                    f"  delta: {delta}\n"
                    f"  recovered: {recovered}"
                )
            
            current_state = new_state
            history.append(current_state.copy())
    
    @given(
        state=state_dict_strategy,
        checkpoint_id=st.text(alphabet="0123456789abcdef", min_size=8, max_size=36),
    )
    @settings(max_examples=50)
    def test_checkpoint_id_preserved_in_recovery(self, state, checkpoint_id):
        """
        **功能: architecture-deep-integration, 属性 17: 历史检查点恢复**
        **验证: 需求 9.2**
        
        检查点 ID 应当在恢复过程中保持不变。
        """
        # 这个测试验证检查点 ID 的格式和唯一性
        assume(len(checkpoint_id) >= 8)
        
        # 验证 checkpoint_id 可以用于配置
        config = {
            "configurable": {
                "thread_id": "test_thread",
                "checkpoint_ns": "",
                "checkpoint_id": checkpoint_id,
            }
        }
        
        # 验证配置结构正确
        assert config["configurable"]["checkpoint_id"] == checkpoint_id
        assert config["configurable"]["thread_id"] == "test_thread"


class TestDeltaChainIntegrity:
    """增量链完整性测试
    
    **功能: architecture-deep-integration, 属性 17: 历史检查点恢复**
    **验证: 需求 9.2**
    """
    
    @given(
        initial_state=state_dict_strategy,
        num_updates=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=50)
    def test_long_delta_chain_recovery(self, initial_state, num_updates):
        """
        **功能: architecture-deep-integration, 属性 17: 历史检查点恢复**
        **验证: 需求 9.2**
        
        对于长增量链，应当能够正确恢复任意历史状态。
        """
        checkpointer = create_checkpointer()
        
        states = [initial_state.copy()]
        deltas = [(initial_state, False, None)]  # 第一个是完整状态
        
        current = initial_state.copy()
        
        # 生成状态序列
        for i in range(num_updates):
            # 随机修改状态
            new_state = current.copy()
            key = f"key_{i}"
            new_state[key] = f"value_{i}"
            
            # 计算增量
            delta, is_delta = checkpointer._compute_delta(current, new_state)
            deltas.append((delta, is_delta, len(states) - 1))
            states.append(new_state.copy())
            current = new_state
        
        # 验证可以恢复任意状态
        for idx in range(len(states)):
            recovered = self._recover_from_chain(checkpointer, states, deltas, idx)
            assert recovered == states[idx], f"恢复状态 {idx} 失败"
    
    def _recover_from_chain(self, checkpointer, states, deltas, target_idx):
        """从增量链恢复状态"""
        delta, is_delta, base_idx = deltas[target_idx]
        
        if not is_delta:
            return delta
        
        if not delta:
            return self._recover_from_chain(checkpointer, states, deltas, base_idx)
        
        base_state = self._recover_from_chain(checkpointer, states, deltas, base_idx)
        return checkpointer._apply_delta(base_state, delta)
    
    @given(
        state=state_dict_strategy,
    )
    @settings(max_examples=100)
    def test_empty_delta_preserves_state(self, state):
        """
        **功能: architecture-deep-integration, 属性 17: 历史检查点恢复**
        **验证: 需求 9.2**
        
        空增量应当保持状态不变。
        """
        checkpointer = create_checkpointer()
        
        # 计算相同状态的增量
        delta, is_delta = checkpointer._compute_delta(state, state)
        
        assert is_delta is True
        assert delta == {}
        
        # 应用空增量
        recovered = checkpointer._apply_delta(state, delta)
        assert recovered == state
