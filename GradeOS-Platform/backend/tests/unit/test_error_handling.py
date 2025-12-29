"""错误处理模块单元测试

测试指数退避重试、错误隔离、部分结果保存和详细错误日志功能。

验证：需求 9.1, 9.2, 9.4, 9.5
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from src.utils.error_handling import (
    RetryConfig,
    retry_with_exponential_backoff,
    with_retry,
    execute_with_isolation,
    execute_batch_with_isolation,
    PartialResults,
    ErrorLog,
    ErrorLogManager,
    get_error_manager,
)


class TestRetryConfig:
    """测试重试配置"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.initial_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter is True
    
    def test_calculate_delay(self):
        """测试延迟计算"""
        config = RetryConfig(initial_delay=1.0, exponential_base=2.0, jitter=False)
        
        # 第0次重试: 1秒
        assert config.calculate_delay(0) == 1.0
        
        # 第1次重试: 2秒
        assert config.calculate_delay(1) == 2.0
        
        # 第2次重试: 4秒
        assert config.calculate_delay(2) == 4.0
    
    def test_max_delay_limit(self):
        """测试最大延迟限制"""
        config = RetryConfig(initial_delay=1.0, max_delay=5.0, jitter=False)
        
        # 第10次重试应该被限制在5秒
        assert config.calculate_delay(10) == 5.0


class TestExponentialBackoff:
    """测试指数退避重试"""
    
    @pytest.mark.asyncio
    async def test_successful_first_attempt(self):
        """测试第一次尝试成功"""
        mock_func = AsyncMock(return_value="success")
        
        result = await retry_with_exponential_backoff(mock_func)
        
        assert result == "success"
        assert mock_func.call_count == 1
    
    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """测试失败后重试"""
        mock_func = AsyncMock(side_effect=[
            Exception("First failure"),
            Exception("Second failure"),
            "success"
        ])
        
        config = RetryConfig(max_retries=3, initial_delay=0.01)
        result = await retry_with_exponential_backoff(mock_func, config=config)
        
        assert result == "success"
        assert mock_func.call_count == 3
    
    @pytest.mark.asyncio
    async def test_all_retries_fail(self):
        """测试所有重试都失败"""
        mock_func = AsyncMock(side_effect=Exception("Always fails"))
        
        config = RetryConfig(max_retries=2, initial_delay=0.01)
        
        with pytest.raises(Exception, match="Always fails"):
            await retry_with_exponential_backoff(mock_func, config=config)
        
        assert mock_func.call_count == 3  # 初始 + 2次重试
    
    @pytest.mark.asyncio
    async def test_with_retry_decorator(self):
        """测试重试装饰器"""
        call_count = 0
        
        @with_retry(max_retries=2, initial_delay=0.01)
        async def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Not yet")
            return "success"
        
        result = await flaky_function()
        
        assert result == "success"
        assert call_count == 2


class TestErrorIsolation:
    """测试错误隔离"""
    
    @pytest.mark.asyncio
    async def test_successful_execution(self):
        """测试成功执行"""
        async def success_func(x):
            return x * 2
        
        result = await execute_with_isolation(success_func, 5)
        
        assert result.is_success()
        assert result.get_result() == 10
    
    @pytest.mark.asyncio
    async def test_failed_execution(self):
        """测试失败执行"""
        async def fail_func(x):
            raise ValueError("Test error")
        
        result = await execute_with_isolation(fail_func, 5, index=0)
        
        assert result.is_failure()
        assert isinstance(result.get_error(), ValueError)
        assert result.error_log is not None
        assert result.index == 0
    
    @pytest.mark.asyncio
    async def test_batch_isolation(self):
        """测试批量隔离执行"""
        async def process_item(x):
            if x == 3:
                raise ValueError(f"Cannot process {x}")
            return x * 2
        
        items = [1, 2, 3, 4, 5]
        results = await execute_batch_with_isolation(process_item, items)
        
        assert len(results) == 5
        
        # 检查成功的结果
        successful = [r for r in results if r.is_success()]
        assert len(successful) == 4
        assert [r.get_result() for r in successful] == [2, 4, 8, 10]
        
        # 检查失败的结果
        failed = [r for r in results if r.is_failure()]
        assert len(failed) == 1
        assert failed[0].index == 2


class TestPartialResults:
    """测试部分结果保存"""
    
    def test_add_result(self):
        """测试添加成功结果"""
        partial = PartialResults(batch_id="test_batch", total_items=10)
        
        partial.add_result({"score": 85})
        partial.add_result({"score": 90})
        
        assert partial.completed_count == 2
        assert len(partial.completed_results) == 2
    
    def test_add_failure(self):
        """测试添加失败项"""
        partial = PartialResults(batch_id="test_batch", total_items=10)
        
        error = ValueError("Test error")
        partial.add_failure(5, error, context={"page": 5})
        
        assert partial.failed_count == 1
        assert len(partial.failed_items) == 1
        assert partial.failed_items[0]["index"] == 5
    
    def test_to_dict(self):
        """测试序列化为字典"""
        partial = PartialResults(batch_id="test_batch", total_items=10)
        partial.add_result({"score": 85})
        partial.add_failure(5, ValueError("Error"), context={})
        
        data = partial.to_dict()
        
        assert data["batch_id"] == "test_batch"
        assert data["total_items"] == 10
        assert data["completed_count"] == 1
        assert data["failed_count"] == 1
        assert data["completion_rate"] == 0.1
    
    def test_save_to_file(self, tmp_path):
        """测试保存到文件"""
        partial = PartialResults(batch_id="test_batch", total_items=10)
        partial.add_result({"score": 85})
        
        filepath = tmp_path / "partial_results.json"
        partial.save_to_file(str(filepath))
        
        assert filepath.exists()
        
        import json
        with open(filepath) as f:
            data = json.load(f)
        
        assert data["batch_id"] == "test_batch"
        assert data["completed_count"] == 1


class TestErrorLog:
    """测试错误日志"""
    
    def test_from_exception(self):
        """测试从异常创建错误日志"""
        try:
            raise ValueError("Test error")
        except Exception as e:
            error_log = ErrorLog.from_exception(
                exc=e,
                context={"operation": "test"},
                batch_id="batch_123",
                page_index=5,
                retry_count=2,
            )
        
        assert error_log.error_type == "ValueError"
        assert error_log.error_message == "Test error"
        assert error_log.context["operation"] == "test"
        assert error_log.batch_id == "batch_123"
        assert error_log.page_index == 5
        assert error_log.retry_count == 2
        assert not error_log.resolved
    
    def test_to_dict(self):
        """测试序列化为字典"""
        try:
            raise ValueError("Test error")
        except Exception as e:
            error_log = ErrorLog.from_exception(exc=e, context={})
        
        data = error_log.to_dict()
        
        assert "timestamp" in data
        assert data["error_type"] == "ValueError"
        assert data["error_message"] == "Test error"
        assert "stack_trace" in data


class TestErrorLogManager:
    """测试错误日志管理器"""
    
    def test_add_error(self):
        """测试添加错误"""
        manager = ErrorLogManager()
        
        try:
            raise ValueError("Test error")
        except Exception as e:
            error_log = manager.add_error(
                exc=e,
                context={"operation": "test"},
                batch_id="batch_123",
            )
        
        assert len(manager.error_logs) == 1
        assert error_log.error_type == "ValueError"
    
    def test_get_errors_by_batch(self):
        """测试按批次获取错误"""
        manager = ErrorLogManager()
        
        # 添加不同批次的错误
        for batch_id in ["batch_1", "batch_2", "batch_1"]:
            try:
                raise ValueError(f"Error in {batch_id}")
            except Exception as e:
                manager.add_error(exc=e, batch_id=batch_id)
        
        batch_1_errors = manager.get_errors_by_batch("batch_1")
        assert len(batch_1_errors) == 2
        
        batch_2_errors = manager.get_errors_by_batch("batch_2")
        assert len(batch_2_errors) == 1
    
    def test_get_unresolved_errors(self):
        """测试获取未解决的错误"""
        manager = ErrorLogManager()
        
        # 添加错误
        try:
            raise ValueError("Error 1")
        except Exception as e:
            error_log_1 = manager.add_error(exc=e)
        
        try:
            raise ValueError("Error 2")
        except Exception as e:
            error_log_2 = manager.add_error(exc=e)
        
        # 标记一个为已解决
        manager.mark_resolved(error_log_1)
        
        unresolved = manager.get_unresolved_errors()
        assert len(unresolved) == 1
        assert unresolved[0] == error_log_2
    
    def test_export_to_dict(self):
        """测试导出为字典"""
        manager = ErrorLogManager()
        
        try:
            raise ValueError("Test error")
        except Exception as e:
            manager.add_error(exc=e)
        
        data = manager.export_to_dict()
        
        assert data["total_errors"] == 1
        assert data["unresolved_errors"] == 1
        assert len(data["error_logs"]) == 1
    
    def test_export_to_file(self, tmp_path):
        """测试导出到文件"""
        manager = ErrorLogManager()
        
        try:
            raise ValueError("Test error")
        except Exception as e:
            manager.add_error(exc=e)
        
        filepath = tmp_path / "error_log.json"
        manager.export_to_file(str(filepath))
        
        assert filepath.exists()
        
        import json
        with open(filepath) as f:
            data = json.load(f)
        
        assert data["total_errors"] == 1
    
    def test_clear(self):
        """测试清空错误日志"""
        manager = ErrorLogManager()
        
        try:
            raise ValueError("Test error")
        except Exception as e:
            manager.add_error(exc=e)
        
        assert len(manager.error_logs) == 1
        
        manager.clear()
        assert len(manager.error_logs) == 0


class TestGlobalErrorManager:
    """测试全局错误管理器"""
    
    def test_get_error_manager(self):
        """测试获取全局错误管理器"""
        manager1 = get_error_manager()
        manager2 = get_error_manager()
        
        # 应该返回同一个实例
        assert manager1 is manager2
    
    def test_global_manager_persistence(self):
        """测试全局管理器持久性"""
        manager = get_error_manager()
        
        try:
            raise ValueError("Test error")
        except Exception as e:
            manager.add_error(exc=e)
        
        # 再次获取应该保留之前的错误
        manager2 = get_error_manager()
        assert len(manager2.error_logs) >= 1


@pytest.mark.asyncio
async def test_integration_example():
    """集成测试示例"""
    
    # 模拟批改任务
    async def grade_page(page_index):
        if page_index == 3:
            raise ValueError(f"Failed to grade page {page_index}")
        return {"page_index": page_index, "score": 85}
    
    # 使用错误隔离批量处理
    pages = list(range(5))
    results = await execute_batch_with_isolation(
        func=grade_page,
        items=pages,
        error_log_context={"batch_id": "test_batch"},
    )
    
    # 验证结果
    successful = [r for r in results if r.is_success()]
    failed = [r for r in results if r.is_failure()]
    
    assert len(successful) == 4
    assert len(failed) == 1
    assert failed[0].index == 3
    
    # 检查错误管理器
    error_manager = get_error_manager()
    batch_errors = error_manager.get_errors_by_batch("test_batch")
    
    # 注意：由于全局管理器可能包含其他测试的错误，这里只检查至少有1个
    assert len(batch_errors) >= 1
