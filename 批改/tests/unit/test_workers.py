"""Temporal Workers 单元测试

这些测试验证 Worker 入口点的基本结构和配置。
由于 Temporal Worker 需要实际的 Temporal 服务器连接，
这里主要测试模块导入和基本结构。
"""

import pytest
from src.workers import (
    create_orchestration_worker,
    run_orchestration_worker,
    create_cognitive_worker,
    run_cognitive_worker
)


class TestWorkerModules:
    """Worker 模块测试"""
    
    def test_orchestration_worker_imports(self):
        """测试编排 Worker 模块导入"""
        # 验证函数可以导入
        assert callable(create_orchestration_worker)
        assert callable(run_orchestration_worker)
    
    def test_cognitive_worker_imports(self):
        """测试认知 Worker 模块导入"""
        # 验证函数可以导入
        assert callable(create_cognitive_worker)
        assert callable(run_cognitive_worker)


class TestWorkerConfiguration:
    """Worker 配置测试"""
    
    def test_orchestration_worker_has_correct_signature(self):
        """测试编排 Worker 函数签名"""
        import inspect
        sig = inspect.signature(create_orchestration_worker)
        
        # 验证参数
        assert 'temporal_host' in sig.parameters
        assert 'temporal_namespace' in sig.parameters
        assert 'task_queue' in sig.parameters
        
        # 验证默认值
        assert sig.parameters['task_queue'].default == "default-queue"
    
    def test_cognitive_worker_has_correct_signature(self):
        """测试认知 Worker 函数签名"""
        import inspect
        sig = inspect.signature(create_cognitive_worker)
        
        # 验证参数
        assert 'temporal_host' in sig.parameters
        assert 'temporal_namespace' in sig.parameters
        assert 'task_queue' in sig.parameters
        assert 'max_concurrent_activities' in sig.parameters
        
        # 验证默认值
        assert sig.parameters['task_queue'].default == "vision-compute-queue"
        assert sig.parameters['max_concurrent_activities'].default == 10
