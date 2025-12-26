"""
属性测试：工作流进度查询

**功能: architecture-deep-integration, 属性 20: 工作流进度查询**
**验证: 需求 10.2**

测试通过 Temporal Query 能够获取当前进度信息，
进度信息应当包含阶段、百分比和更新时间。
"""

import pytest
from hypothesis import given, strategies as st, settings, Phase
from unittest.mock import MagicMock, patch
import uuid

from src.workflows.enhanced_workflow import (
    EnhancedWorkflowMixin,
    WorkflowProgress,
)


# 配置 Hypothesis
settings.register_profile(
    "ci",
    max_examples=100,
    phases=[Phase.generate, Phase.target, Phase.shrink]
)


# ==================== 策略定义 ====================

# 生成有效的阶段名称
stage_strategy = st.text(
    alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='_-'),
    min_size=1,
    max_size=50
)

# 生成有效的百分比 (0.0 - 100.0)
percentage_strategy = st.floats(
    min_value=0.0,
    max_value=100.0,
    allow_nan=False,
    allow_infinity=False
)

# 生成超出范围的百分比
out_of_range_percentage_strategy = st.one_of(
    st.floats(max_value=-0.1, allow_nan=False, allow_infinity=False),
    st.floats(min_value=100.1, allow_nan=False, allow_infinity=False),
)

# 生成进度详情
details_strategy = st.dictionaries(
    keys=st.text(min_size=1, max_size=20),
    values=st.one_of(
        st.text(max_size=100),
        st.integers(),
        st.floats(allow_nan=False, allow_infinity=False),
        st.booleans(),
    ),
    max_size=10
)


# ==================== 属性测试 ====================

class TestWorkflowProgressQuery:
    """
    工作流进度查询属性测试
    
    **功能: architecture-deep-integration, 属性 20: 工作流进度查询**
    **验证: 需求 10.2**
    """
    
    @given(
        stage=stage_strategy,
        percentage=percentage_strategy,
        details=details_strategy
    )
    @settings(max_examples=100)
    def test_progress_query_returns_updated_progress(
        self,
        stage: str,
        percentage: float,
        details: dict
    ):
        """
        属性 20.1: Query 应返回最新进度信息
        
        *对于任意* 正在执行的工作流，通过 Temporal Query 应当能够
        获取当前进度信息。
        
        **功能: architecture-deep-integration, 属性 20: 工作流进度查询**
        **验证: 需求 10.2**
        """
        mixin = EnhancedWorkflowMixin()
        
        # 模拟 workflow.now() 返回值
        with patch('src.workflows.enhanced_workflow.workflow') as mock_workflow:
            mock_workflow.now.return_value.isoformat.return_value = "2024-01-01T00:00:00Z"
            
            # 更新进度
            mixin.update_progress(stage, percentage, details)
        
        # 查询进度
        progress = mixin.get_progress()
        
        # 验证进度信息包含必要字段
        assert "stage" in progress
        assert "percentage" in progress
        assert "details" in progress
        assert "updated_at" in progress
        
        # 验证进度值
        assert progress["stage"] == stage
        assert progress["details"] == details
    
    @given(
        stage=stage_strategy,
        percentage=percentage_strategy
    )
    @settings(max_examples=100)
    def test_progress_percentage_clamping(
        self,
        stage: str,
        percentage: float
    ):
        """
        属性 20.2: 百分比应被限制在 0-100 范围内
        
        *对于任意* 进度更新，百分比应当被限制在有效范围内。
        
        **功能: architecture-deep-integration, 属性 20: 工作流进度查询**
        **验证: 需求 10.2**
        """
        mixin = EnhancedWorkflowMixin()
        
        with patch('src.workflows.enhanced_workflow.workflow') as mock_workflow:
            mock_workflow.now.return_value.isoformat.return_value = "2024-01-01T00:00:00Z"
            mixin.update_progress(stage, percentage)
        
        progress = mixin.get_progress()
        
        # 验证百分比在有效范围内
        assert 0.0 <= progress["percentage"] <= 100.0
    
    @given(
        stage=stage_strategy,
        percentage=out_of_range_percentage_strategy
    )
    @settings(max_examples=100)
    def test_out_of_range_percentage_clamped(
        self,
        stage: str,
        percentage: float
    ):
        """
        属性 20.3: 超出范围的百分比应被钳制
        
        *对于任意* 超出 0-100 范围的百分比，应当被钳制到有效范围。
        
        **功能: architecture-deep-integration, 属性 20: 工作流进度查询**
        **验证: 需求 10.2**
        """
        mixin = EnhancedWorkflowMixin()
        
        with patch('src.workflows.enhanced_workflow.workflow') as mock_workflow:
            mock_workflow.now.return_value.isoformat.return_value = "2024-01-01T00:00:00Z"
            mixin.update_progress(stage, percentage)
        
        progress = mixin.get_progress()
        
        # 验证百分比被钳制到有效范围
        assert 0.0 <= progress["percentage"] <= 100.0
        
        if percentage < 0:
            assert progress["percentage"] == 0.0
        elif percentage > 100:
            assert progress["percentage"] == 100.0
    
    @given(
        stages=st.lists(
            st.tuples(stage_strategy, percentage_strategy, details_strategy),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=100)
    def test_progress_updates_are_sequential(
        self,
        stages: list
    ):
        """
        属性 20.4: 进度更新应保持最新值
        
        *对于任意* 进度更新序列，Query 应返回最后一次更新的值。
        
        **功能: architecture-deep-integration, 属性 20: 工作流进度查询**
        **验证: 需求 10.2**
        """
        mixin = EnhancedWorkflowMixin()
        
        with patch('src.workflows.enhanced_workflow.workflow') as mock_workflow:
            mock_workflow.now.return_value.isoformat.return_value = "2024-01-01T00:00:00Z"
            
            # 执行所有更新
            for stage, percentage, details in stages:
                mixin.update_progress(stage, percentage, details)
        
        # 获取最终进度
        progress = mixin.get_progress()
        
        # 验证是最后一次更新的值
        last_stage, last_percentage, last_details = stages[-1]
        assert progress["stage"] == last_stage
        assert progress["details"] == last_details


class TestWorkflowProgressDataClass:
    """
    WorkflowProgress 数据类测试
    
    **功能: architecture-deep-integration, 属性 20: 工作流进度查询**
    **验证: 需求 10.2**
    """
    
    @given(
        stage=stage_strategy,
        percentage=percentage_strategy,
        details=details_strategy,
        updated_at=st.text(min_size=10, max_size=30)
    )
    @settings(max_examples=100)
    def test_workflow_progress_to_dict(
        self,
        stage: str,
        percentage: float,
        details: dict,
        updated_at: str
    ):
        """
        属性 20.5: WorkflowProgress 序列化应保持一致性
        
        **功能: architecture-deep-integration, 属性 20: 工作流进度查询**
        **验证: 需求 10.2**
        """
        progress = WorkflowProgress(
            stage=stage,
            percentage=percentage,
            details=details,
            updated_at=updated_at,
        )
        
        progress_dict = progress.to_dict()
        
        # 验证字典内容
        assert progress_dict["stage"] == stage
        assert progress_dict["percentage"] == percentage
        assert progress_dict["details"] == details
        assert progress_dict["updated_at"] == updated_at


class TestProgressQueryWithBatchWorkflows:
    """
    批量子工作流进度查询测试
    
    **功能: architecture-deep-integration, 属性 20: 工作流进度查询**
    **验证: 需求 10.2**
    """
    
    @given(
        total=st.integers(min_value=1, max_value=100),
        completed=st.integers(min_value=0, max_value=100)
    )
    @settings(max_examples=100)
    def test_batch_progress_calculation(
        self,
        total: int,
        completed: int
    ):
        """
        属性 20.6: 批量进度计算应正确
        
        *对于任意* 批量任务，进度百分比应正确反映完成比例。
        
        **功能: architecture-deep-integration, 属性 20: 工作流进度查询**
        **验证: 需求 10.2**
        """
        # 确保 completed <= total
        completed = min(completed, total)
        
        mixin = EnhancedWorkflowMixin()
        
        with patch('src.workflows.enhanced_workflow.workflow') as mock_workflow:
            mock_workflow.now.return_value.isoformat.return_value = "2024-01-01T00:00:00Z"
            
            # 计算进度百分比
            percentage = (completed / total) * 100
            
            mixin.update_progress(
                stage="batch_processing",
                percentage=percentage,
                details={
                    "total": total,
                    "completed": completed,
                }
            )
        
        progress = mixin.get_progress()
        
        # 验证进度信息
        assert progress["stage"] == "batch_processing"
        assert progress["details"]["total"] == total
        assert progress["details"]["completed"] == completed
        
        # 验证百分比计算正确
        expected_percentage = (completed / total) * 100
        assert abs(progress["percentage"] - expected_percentage) < 0.001
