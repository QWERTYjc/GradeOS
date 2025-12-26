"""检查点存储效率属性测试

**功能: architecture-deep-integration, 属性 16: 检查点存储效率**
**验证: 需求 9.1, 9.3**

属性 16 定义：对于任意检查点保存操作，当状态变化较小时应当仅保存增量，
当数据超过 1MB 时应当压缩后存储，压缩后的数据应当能够正确解压恢复。
"""

import pytest
import zlib
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import MagicMock

from src.utils.enhanced_checkpointer import EnhancedPostgresCheckpointer


def create_checkpointer(compression_threshold: int = 1024 * 1024):
    """创建检查点器实例（用于测试）"""
    mock_pool_manager = MagicMock()
    return EnhancedPostgresCheckpointer(
        pool_manager=mock_pool_manager,
        compression_threshold=compression_threshold,
    )


# 生成状态字典的策略
state_dict_strategy = st.dictionaries(
    keys=st.text(alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=1, max_size=20),
    values=st.one_of(
        st.text(min_size=0, max_size=100),
        st.integers(min_value=-1000, max_value=1000),
        st.floats(min_value=-1000, max_value=1000, allow_nan=False, allow_infinity=False),
        st.booleans(),
        st.none(),
    ),
    min_size=0,
    max_size=20,
)


class TestCheckpointStorageEfficiency:
    """检查点存储效率属性测试
    
    **功能: architecture-deep-integration, 属性 16: 检查点存储效率**
    **验证: 需求 9.1, 9.3**
    """
    
    @given(
        previous_state=state_dict_strategy,
        current_state=state_dict_strategy,
    )
    @settings(max_examples=100)
    def test_delta_computation_preserves_information(
        self, previous_state, current_state
    ):
        """
        **功能: architecture-deep-integration, 属性 16: 检查点存储效率**
        **验证: 需求 9.1, 9.3**
        
        对于任意两个状态，计算增量后应用增量应当恢复原始状态。
        这是一个往返属性：apply_delta(base, compute_delta(base, target)) == target
        """
        checkpointer = create_checkpointer()
        
        # 计算增量
        delta, is_delta = checkpointer._compute_delta(previous_state, current_state)
        
        if is_delta:
            # 应用增量
            recovered_state = checkpointer._apply_delta(previous_state, delta)
            
            # 验证恢复后的状态与原始状态一致
            assert recovered_state == current_state, (
                f"增量恢复失败:\n"
                f"  previous: {previous_state}\n"
                f"  current: {current_state}\n"
                f"  delta: {delta}\n"
                f"  recovered: {recovered_state}"
            )
        else:
            # 如果不是增量（第一个检查点），delta 应该等于 current_state
            assert delta == current_state
    
    @given(
        state=state_dict_strategy,
    )
    @settings(max_examples=100)
    def test_delta_from_none_returns_full_state(self, state):
        """
        **功能: architecture-deep-integration, 属性 16: 检查点存储效率**
        **验证: 需求 9.1, 9.3**
        
        当前一个状态为 None 时，应当返回完整状态而非增量。
        """
        checkpointer = create_checkpointer()
        
        delta, is_delta = checkpointer._compute_delta(None, state)
        
        # 应当返回完整状态
        assert is_delta is False
        assert delta == state
    
    @given(
        state=state_dict_strategy,
    )
    @settings(max_examples=100)
    def test_delta_from_same_state_is_empty(self, state):
        """
        **功能: architecture-deep-integration, 属性 16: 检查点存储效率**
        **验证: 需求 9.1, 9.3**
        
        当两个状态相同时，增量应当为空。
        """
        checkpointer = create_checkpointer()
        
        delta, is_delta = checkpointer._compute_delta(state, state)
        
        # 应当返回空增量
        assert is_delta is True
        assert delta == {}
    
    @given(
        data=st.binary(min_size=0, max_size=500),
    )
    @settings(max_examples=100)
    def test_compression_roundtrip_small_data(self, data):
        """
        **功能: architecture-deep-integration, 属性 16: 检查点存储效率**
        **验证: 需求 9.1, 9.3**
        
        对于小于压缩阈值的数据，压缩和解压应当保持数据不变。
        """
        checkpointer = create_checkpointer()
        
        # 压缩
        compressed, is_compressed = checkpointer._compress(data)
        
        # 小数据不应被压缩
        assert is_compressed is False
        assert compressed == data
        
        # 解压
        decompressed = checkpointer._decompress(compressed, is_compressed)
        
        # 验证往返
        assert decompressed == data
    
    @given(
        # 生成大于压缩阈值的数据
        base_data=st.binary(min_size=100, max_size=500),
        repeat_count=st.integers(min_value=50, max_value=200),
    )
    @settings(max_examples=20)  # 减少示例数量因为生成大数据较慢
    def test_compression_roundtrip_large_data(
        self, base_data, repeat_count
    ):
        """
        **功能: architecture-deep-integration, 属性 16: 检查点存储效率**
        **验证: 需求 9.1, 9.3**
        
        对于大于压缩阈值的数据，压缩后应当能够正确解压恢复。
        """
        # 使用较低的压缩阈值（1KB）以便更容易测试压缩逻辑
        checkpointer = create_checkpointer(compression_threshold=1024)
        
        # 创建大数据（重复基础数据以超过阈值）
        large_data = base_data * repeat_count
        assume(len(large_data) > checkpointer.compression_threshold)
        
        # 压缩
        compressed, is_compressed = checkpointer._compress(large_data)
        
        # 大数据应被压缩（如果压缩有效）
        if is_compressed:
            assert len(compressed) < len(large_data), "压缩后数据应当更小"
        
        # 解压
        decompressed = checkpointer._decompress(compressed, is_compressed)
        
        # 验证往返
        assert decompressed == large_data, "解压后数据应当与原始数据一致"
    
    @given(
        data=st.binary(min_size=1, max_size=10000),
    )
    @settings(max_examples=100)
    def test_decompress_uncompressed_data_unchanged(self, data):
        """
        **功能: architecture-deep-integration, 属性 16: 检查点存储效率**
        **验证: 需求 9.1, 9.3**
        
        对于未压缩的数据，解压操作应当返回原始数据。
        """
        checkpointer = create_checkpointer()
        
        # 解压未压缩的数据
        result = checkpointer._decompress(data, is_compressed=False)
        
        assert result == data
    
    @given(
        data=st.binary(min_size=10, max_size=10000),
    )
    @settings(max_examples=50)
    def test_decompress_compressed_data_correct(self, data):
        """
        **功能: architecture-deep-integration, 属性 16: 检查点存储效率**
        **验证: 需求 9.1, 9.3**
        
        对于已压缩的数据，解压操作应当正确恢复原始数据。
        """
        checkpointer = create_checkpointer()
        
        # 手动压缩数据
        compressed = zlib.compress(data)
        
        # 解压
        result = checkpointer._decompress(compressed, is_compressed=True)
        
        assert result == data


class TestDeltaOperations:
    """增量操作详细测试
    
    **功能: architecture-deep-integration, 属性 16: 检查点存储效率**
    **验证: 需求 9.1, 9.3**
    """
    
    @given(
        key=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=10),
        value=st.text(min_size=0, max_size=50),
    )
    @settings(max_examples=100)
    def test_delta_detects_additions(self, key, value):
        """
        **功能: architecture-deep-integration, 属性 16: 检查点存储效率**
        **验证: 需求 9.1, 9.3**
        
        增量计算应当正确检测新增的键。
        """
        checkpointer = create_checkpointer()
        
        previous = {}
        current = {key: value}
        
        delta, is_delta = checkpointer._compute_delta(previous, current)
        
        assert is_delta is True
        assert key in delta
        assert delta[key]["op"] == "add"
        assert delta[key]["value"] == value
    
    @given(
        key=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=10),
        old_value=st.text(min_size=0, max_size=50),
        new_value=st.text(min_size=0, max_size=50),
    )
    @settings(max_examples=100)
    def test_delta_detects_updates(self, key, old_value, new_value):
        """
        **功能: architecture-deep-integration, 属性 16: 检查点存储效率**
        **验证: 需求 9.1, 9.3**
        
        增量计算应当正确检测更新的键。
        """
        assume(old_value != new_value)
        
        checkpointer = create_checkpointer()
        
        previous = {key: old_value}
        current = {key: new_value}
        
        delta, is_delta = checkpointer._compute_delta(previous, current)
        
        assert is_delta is True
        assert key in delta
        assert delta[key]["op"] == "update"
        assert delta[key]["value"] == new_value
    
    @given(
        key=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=10),
        value=st.text(min_size=0, max_size=50),
    )
    @settings(max_examples=100)
    def test_delta_detects_deletions(self, key, value):
        """
        **功能: architecture-deep-integration, 属性 16: 检查点存储效率**
        **验证: 需求 9.1, 9.3**
        
        增量计算应当正确检测删除的键。
        """
        checkpointer = create_checkpointer()
        
        previous = {key: value}
        current = {}
        
        delta, is_delta = checkpointer._compute_delta(previous, current)
        
        assert is_delta is True
        assert key in delta
        assert delta[key]["op"] == "delete"
