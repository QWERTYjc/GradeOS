"""
Temporal-LangGraph 状态同步集成测试

测试 Temporal 工作流与 LangGraph 智能体之间的状态同步功能。

验证：需求 1.1, 1.3
"""

import pytest
import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from temporalio import workflow

from src.workflows.enhanced_workflow import (
    EnhancedWorkflowMixin,
    StateIdentityManager,
    RetryStrategyDecider,
    RetryDecision,
    CheckpointStatus,
    WorkflowProgress,
)


class TestStateIdentityConsistency:
    """
    测试状态标识一致性
    
    验证 Temporal workflow_run_id 与 LangGraph thread_id 保持一致。
    
    验证：需求 1.1
    """
    
    def test_state_identity_manager_initialization(self):
        """测试状态标识管理器初始化"""
        workflow_run_id = str(uuid.uuid4())
        manager = StateIdentityManager(workflow_run_id)
        
        # 验证 thread_id 等于 workflow_run_id
        assert manager.thread_id == workflow_run_id
        assert manager.workflow_run_id == workflow_run_id
    
    def test_get_langgraph_config(self):
        """测试获取 LangGraph 配置
        
        验证配置中的 thread_id 等于 workflow_run_id。
        
        验证：需求 1.1
        """
        workflow_run_id = str(uuid.uuid4())
        manager = StateIdentityManager(workflow_run_id)
        
        config = manager.get_langgraph_config()
        
        assert "configurable" in config
        assert config["configurable"]["thread_id"] == workflow_run_id
    
    def test_get_langgraph_config_with_namespace(self):
        """测试带命名空间的 LangGraph 配置"""
        workflow_run_id = str(uuid.uuid4())
        checkpoint_ns = "test_namespace"
        manager = StateIdentityManager(workflow_run_id)
        
        config = manager.get_langgraph_config(checkpoint_ns=checkpoint_ns)
        
        assert config["configurable"]["thread_id"] == workflow_run_id
        assert config["configurable"]["checkpoint_ns"] == checkpoint_ns
    
    def test_state_cache_operations(self):
        """测试状态缓存操作"""
        workflow_run_id = str(uuid.uuid4())
        manager = StateIdentityManager(workflow_run_id)
        
        # 初始状态为空
        assert manager.get_state_cache() is None
        
        # 更新状态缓存
        test_state = {"channel_values": {"score": 85.0}}
        manager.update_state_cache(test_state)
        
        # 验证缓存已更新
        cached = manager.get_state_cache()
        assert cached == test_state


class TestEnhancedWorkflowMixin:
    """
    测试增强型工作流混入类
    
    验证：需求 1.1, 1.3, 1.5
    """
    
    def test_mixin_initialization(self):
        """测试混入类初始化"""
        mixin = EnhancedWorkflowMixin()
        
        assert mixin._progress["stage"] == "initialized"
        assert mixin._progress["percentage"] == 0.0
        assert mixin._external_events == []
        assert mixin._langgraph_state is None
        assert mixin._held_locks == {}
    
    @patch('src.workflows.enhanced_workflow.workflow')
    def test_update_progress(self, mock_workflow):
        """测试进度更新
        
        验证：需求 10.2
        """
        # Mock workflow.now() 返回固定时间
        mock_workflow.now.return_value = datetime(2025, 12, 13, 10, 0, 0, tzinfo=timezone.utc)
        
        mixin = EnhancedWorkflowMixin()
        
        mixin.update_progress(
            stage="grading",
            percentage=50.0,
            details={"current_question": 3, "total_questions": 6}
        )
        
        assert mixin._progress["stage"] == "grading"
        assert mixin._progress["percentage"] == 50.0
        assert mixin._progress["details"]["current_question"] == 3
    
    @patch('src.workflows.enhanced_workflow.workflow')
    def test_update_progress_clamps_percentage(self, mock_workflow):
        """测试进度百分比被限制在 0-100 范围内"""
        # Mock workflow.now() 返回固定时间
        mock_workflow.now.return_value = datetime(2025, 12, 13, 10, 0, 0, tzinfo=timezone.utc)
        
        mixin = EnhancedWorkflowMixin()
        
        # 测试超过 100
        mixin.update_progress(stage="test", percentage=150.0)
        assert mixin._progress["percentage"] == 100.0
        
        # 测试低于 0
        mixin.update_progress(stage="test", percentage=-10.0)
        assert mixin._progress["percentage"] == 0.0
    
    def test_external_event_signal(self):
        """测试外部事件信号接收
        
        验证：需求 10.1
        """
        mixin = EnhancedWorkflowMixin()
        
        event = {
            "event_type": "review_completed",
            "payload": {"submission_id": "sub_001"},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # 模拟接收信号
        mixin.external_event(event)
        
        assert len(mixin._external_events) == 1
        assert mixin._external_events[0]["event_type"] == "review_completed"
        assert mixin._event_received is True
    
    def test_update_langgraph_state_signal(self):
        """测试 LangGraph 状态更新信号
        
        验证：需求 1.5
        """
        mixin = EnhancedWorkflowMixin()
        
        state = {
            "thread_id": str(uuid.uuid4()),
            "checkpoint_id": "cp_001",
            "channel_values": {"score": 90.0}
        }
        
        mixin.update_langgraph_state(state)
        
        assert mixin._langgraph_state == state
        assert mixin._langgraph_state["checkpoint_id"] == "cp_001"
    
    def test_lock_signals(self):
        """测试分布式锁信号"""
        mixin = EnhancedWorkflowMixin()
        
        resource_id = "resource_001"
        lock_token = str(uuid.uuid4())
        
        # 获取锁
        mixin.lock_acquired(resource_id, lock_token)
        assert resource_id in mixin._held_locks
        assert mixin._held_locks[resource_id] == lock_token
        
        # 释放锁
        mixin.lock_released(resource_id)
        assert resource_id not in mixin._held_locks


class TestRetryStrategyDecision:
    """
    测试重试策略决策
    
    验证：需求 1.4
    """
    
    def test_recover_from_valid_checkpoint(self):
        """测试从有效检查点恢复
        
        当检查点存在且有效时，应该从检查点恢复。
        
        验证：需求 1.4
        """
        decider = RetryStrategyDecider()
        
        checkpoint_status = CheckpointStatus(
            exists=True,
            valid=True,
            checkpoint_id="cp_001",
            data_size_bytes=1024
        )
        
        decision = decider.decide(checkpoint_status)
        
        assert decision == RetryDecision.RECOVER_FROM_CHECKPOINT
    
    def test_restart_when_checkpoint_not_exists(self):
        """测试检查点不存在时重新开始
        
        当检查点不存在时，应该重新开始执行。
        
        验证：需求 1.4
        """
        decider = RetryStrategyDecider()
        
        checkpoint_status = CheckpointStatus(
            exists=False,
            valid=False
        )
        
        decision = decider.decide(checkpoint_status)
        
        assert decision == RetryDecision.RESTART_FROM_BEGINNING
    
    def test_restart_when_checkpoint_corrupted(self):
        """测试检查点损坏时重新开始
        
        当检查点存在但损坏时，应该重新开始执行。
        
        验证：需求 1.4
        """
        decider = RetryStrategyDecider()
        
        checkpoint_status = CheckpointStatus(
            exists=True,
            valid=False,
            is_corrupted=True,
            error="数据校验失败"
        )
        
        decision = decider.decide(checkpoint_status)
        
        assert decision == RetryDecision.RESTART_FROM_BEGINNING
    
    def test_fail_permanently_after_max_restarts(self):
        """测试超过最大重启次数后永久失败
        
        验证：需求 1.4
        """
        decider = RetryStrategyDecider(max_restart_attempts=2)
        
        checkpoint_status = CheckpointStatus(exists=False, valid=False)
        
        # 第一次重启
        decision1 = decider.decide(checkpoint_status)
        assert decision1 == RetryDecision.RESTART_FROM_BEGINNING
        
        # 第二次重启
        decision2 = decider.decide(checkpoint_status)
        assert decision2 == RetryDecision.RESTART_FROM_BEGINNING
        
        # 第三次应该永久失败
        decision3 = decider.decide(checkpoint_status)
        assert decision3 == RetryDecision.FAIL_PERMANENTLY
    
    def test_reset_restart_count(self):
        """测试重置重启计数"""
        decider = RetryStrategyDecider(max_restart_attempts=2)
        
        checkpoint_status = CheckpointStatus(exists=False, valid=False)
        
        # 触发两次重启
        decider.decide(checkpoint_status)
        decider.decide(checkpoint_status)
        
        # 重置计数
        decider.reset_restart_count()
        
        # 应该可以再次重启
        decision = decider.decide(checkpoint_status)
        assert decision == RetryDecision.RESTART_FROM_BEGINNING


class TestWorkflowProgressDataClass:
    """测试工作流进度数据类"""
    
    def test_progress_to_dict(self):
        """测试进度转换为字典"""
        progress = WorkflowProgress(
            stage="grading",
            percentage=75.0,
            details={"completed": 3, "total": 4},
            updated_at="2025-12-13T10:00:00Z"
        )
        
        result = progress.to_dict()
        
        assert result["stage"] == "grading"
        assert result["percentage"] == 75.0
        assert result["details"]["completed"] == 3
        assert result["updated_at"] == "2025-12-13T10:00:00Z"


class TestCheckpointStatusDataClass:
    """测试检查点状态数据类"""
    
    def test_checkpoint_status_to_dict(self):
        """测试检查点状态转换为字典"""
        status = CheckpointStatus(
            exists=True,
            valid=True,
            checkpoint_id="cp_001",
            data_size_bytes=2048,
            is_corrupted=False
        )
        
        result = status.to_dict()
        
        assert result["exists"] is True
        assert result["valid"] is True
        assert result["checkpoint_id"] == "cp_001"
        assert result["data_size_bytes"] == 2048
        assert result["is_corrupted"] is False


class TestCrashRecoveryScenarios:
    """
    测试崩溃恢复场景
    
    验证：需求 1.3
    """
    
    def test_recovery_decision_with_valid_checkpoint(self):
        """测试有有效检查点时的恢复决策"""
        decider = RetryStrategyDecider()
        
        # 模拟崩溃后发现有效检查点
        checkpoint_status = CheckpointStatus(
            exists=True,
            valid=True,
            checkpoint_id="cp_before_crash",
            data_size_bytes=4096
        )
        
        decision = decider.decide(checkpoint_status)
        
        # 应该从检查点恢复
        assert decision == RetryDecision.RECOVER_FROM_CHECKPOINT
    
    def test_recovery_decision_with_invalid_checkpoint(self):
        """测试检查点无效时的恢复决策"""
        decider = RetryStrategyDecider()
        
        # 模拟崩溃后发现检查点无效
        checkpoint_status = CheckpointStatus(
            exists=True,
            valid=False,
            checkpoint_id="cp_corrupted",
            is_corrupted=True,
            error="CRC 校验失败"
        )
        
        decision = decider.decide(checkpoint_status)
        
        # 应该重新开始
        assert decision == RetryDecision.RESTART_FROM_BEGINNING
    
    @pytest.mark.asyncio
    async def test_state_identity_preserved_after_recovery(self):
        """测试恢复后状态标识保持一致
        
        验证：需求 1.1, 1.3
        """
        # 模拟原始工作流
        original_workflow_run_id = str(uuid.uuid4())
        original_manager = StateIdentityManager(original_workflow_run_id)
        
        # 保存状态
        original_state = {
            "channel_values": {"score": 85.0, "feedback": "良好"},
            "metadata": {"step": 3}
        }
        original_manager.update_state_cache(original_state)
        
        # 模拟崩溃恢复 - 使用相同的 workflow_run_id
        recovered_manager = StateIdentityManager(original_workflow_run_id)
        
        # 验证 thread_id 保持一致
        assert recovered_manager.thread_id == original_manager.thread_id
        
        # 验证配置一致
        original_config = original_manager.get_langgraph_config()
        recovered_config = recovered_manager.get_langgraph_config()
        
        assert original_config["configurable"]["thread_id"] == \
               recovered_config["configurable"]["thread_id"]
