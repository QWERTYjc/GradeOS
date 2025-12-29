"""并行批改架构优化单元测试

测试批次配置、Worker 独立性、批次失败重试和进度报告功能。

Requirements: 3.1, 3.2, 3.3, 3.4, 9.3, 10.1
"""

import pytest
import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.graphs.batch_grading import (
    BatchConfig,
    BatchProgress,
    BatchTaskState,
    get_batch_config,
    set_batch_config,
    grading_fanout_router,
    grade_batch_node,
)
from src.graphs.state import BatchGradingGraphState


class TestBatchConfig:
    """测试批次配置类"""
    
    def test_default_config(self):
        """测试默认配置值"""
        config = BatchConfig()
        assert config.batch_size == 10
        assert config.max_concurrent_workers == 5
        assert config.max_retries == 2
        assert config.retry_delay == 1.0
    
    def test_custom_config(self):
        """测试自定义配置"""
        config = BatchConfig(
            batch_size=5,
            max_concurrent_workers=3,
            max_retries=3,
            retry_delay=2.0
        )
        assert config.batch_size == 5
        assert config.max_concurrent_workers == 3
        assert config.max_retries == 3
        assert config.retry_delay == 2.0
    
    def test_from_env(self):
        """测试从环境变量加载配置"""
        with patch.dict(os.environ, {
            "GRADING_BATCH_SIZE": "15",
            "GRADING_MAX_WORKERS": "8",
            "GRADING_MAX_RETRIES": "5",
            "GRADING_RETRY_DELAY": "3.0"
        }):
            config = BatchConfig.from_env()
            assert config.batch_size == 15
            assert config.max_concurrent_workers == 8
            assert config.max_retries == 5
            assert config.retry_delay == 3.0
    
    def test_set_and_get_config(self):
        """测试设置和获取全局配置"""
        custom_config = BatchConfig(batch_size=20)
        set_batch_config(custom_config)
        
        retrieved_config = get_batch_config()
        assert retrieved_config.batch_size == 20


class TestBatchProgress:
    """测试批次进度类"""
    
    def test_initial_progress(self):
        """测试初始进度状态"""
        progress = BatchProgress(
            batch_id="test_batch",
            total_batches=5,
            total_pages=50
        )
        
        assert progress.batch_id == "test_batch"
        assert progress.total_batches == 5
        assert progress.completed_batches == 0
        assert progress.failed_batches == 0
        assert progress.total_pages == 50
        assert progress.processed_pages == 0
        assert progress.percentage == 0.0
    
    def test_update_batch_status(self):
        """测试更新批次状态"""
        progress = BatchProgress(
            batch_id="test_batch",
            total_batches=5,
            total_pages=50
        )
        
        # 更新第一个批次为完成
        progress.update_batch_status(
            batch_index=0,
            status="completed",
            pages_processed=10
        )
        
        assert progress.completed_batches == 1
        assert progress.processed_pages == 10
        assert progress.percentage > 0
        
        # 更新第二个批次为失败
        progress.update_batch_status(
            batch_index=1,
            status="failed",
            pages_failed=10,
            error="API 调用失败"
        )
        
        assert progress.failed_batches == 1
        assert progress.failed_pages == 10
    
    def test_to_dict(self):
        """测试序列化为字典"""
        progress = BatchProgress(
            batch_id="test_batch",
            total_batches=3,
            total_pages=30
        )
        
        data = progress.to_dict()
        
        assert data["batch_id"] == "test_batch"
        assert data["total_batches"] == 3
        assert data["total_pages"] == 30
        assert "batch_details" in data


class TestBatchTaskState:
    """测试批次任务状态类"""
    
    def test_initial_state(self):
        """测试初始任务状态"""
        task = BatchTaskState(
            batch_id="batch_001",
            batch_index=0,
            total_batches=5,
            page_indices=[0, 1, 2],
            images=["img1", "img2", "img3"],
            rubric="评分标准",
            parsed_rubric={},
            api_key="test_key"
        )
        
        assert task.batch_id == "batch_001"
        assert task.batch_index == 0
        assert task.retry_count == 0
        assert task.status == "pending"
        assert task.error is None


class TestGradingFanoutRouter:
    """测试批改扇出路由"""
    
    def test_fanout_with_default_batch_size(self):
        """测试使用默认批次大小的扇出"""
        # 设置默认配置
        set_batch_config(BatchConfig(batch_size=10))
        
        state: BatchGradingGraphState = {
            "batch_id": "test_batch",
            "processed_images": [f"img_{i}" for i in range(25)],
            "rubric": "评分标准",
            "parsed_rubric": {},
            "api_key": "test_key"
        }
        
        sends = grading_fanout_router(state)
        
        # 25 页应该分成 3 个批次 (10 + 10 + 5)
        assert len(sends) == 3
    
    def test_fanout_with_custom_batch_size(self):
        """测试使用自定义批次大小的扇出"""
        set_batch_config(BatchConfig(batch_size=5))
        
        state: BatchGradingGraphState = {
            "batch_id": "test_batch",
            "processed_images": [f"img_{i}" for i in range(12)],
            "rubric": "评分标准",
            "parsed_rubric": {},
            "api_key": "test_key"
        }
        
        sends = grading_fanout_router(state)
        
        # 12 页应该分成 3 个批次 (5 + 5 + 2)
        assert len(sends) == 3
    
    def test_fanout_with_no_images(self):
        """测试没有图像时的扇出"""
        state: BatchGradingGraphState = {
            "batch_id": "test_batch",
            "processed_images": [],
            "rubric": "评分标准",
            "parsed_rubric": {},
            "api_key": "test_key"
        }
        
        sends = grading_fanout_router(state)
        
        # 没有图像时应该直接跳到 segment 节点
        assert len(sends) == 1
        assert sends[0].node == "segment"
    
    def test_fanout_includes_retry_config(self):
        """测试扇出包含重试配置"""
        set_batch_config(BatchConfig(batch_size=10, max_retries=3))
        
        state: BatchGradingGraphState = {
            "batch_id": "test_batch",
            "processed_images": [f"img_{i}" for i in range(5)],
            "rubric": "评分标准",
            "parsed_rubric": {},
            "api_key": "test_key"
        }
        
        sends = grading_fanout_router(state)
        
        assert len(sends) == 1
        # 验证任务状态包含重试配置
        task_state = sends[0].arg
        assert task_state["max_retries"] == 3
        assert task_state["retry_count"] == 0


class TestGradeBatchNode:
    """测试批量批改节点"""
    
    @pytest.mark.asyncio
    async def test_grade_batch_success(self):
        """测试批改成功场景"""
        state = {
            "batch_id": "test_batch",
            "batch_index": 0,
            "total_batches": 1,
            "page_indices": [0, 1],
            "images": ["img_0", "img_1"],
            "rubric": "评分标准",
            "parsed_rubric": {},
            "api_key": "test_key",
            "retry_count": 0,
            "max_retries": 2
        }
        
        # Mock GeminiReasoningClient - 需要 mock 实际导入的模块
        with patch("src.services.gemini_reasoning.GeminiReasoningClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value = mock_instance
            
            # Mock grade_page 返回结果
            mock_instance.grade_page.return_value = {
                "score": 8.0,
                "max_score": 10.0,
                "confidence": 0.9,
                "feedback": "测试反馈",
                "question_numbers": ["1", "2"],
                "question_details": [],
                "is_blank_page": False
            }
            
            result = await grade_batch_node(state)
            
            # 验证结果
            assert "grading_results" in result
            assert len(result["grading_results"]) == 2
            assert all(r["status"] == "completed" for r in result["grading_results"])
            assert "batch_progress" in result
    
    @pytest.mark.asyncio
    async def test_grade_batch_with_retry(self):
        """测试批改失败重试场景"""
        state = {
            "batch_id": "test_batch",
            "batch_index": 0,
            "total_batches": 1,
            "page_indices": [0],
            "images": ["img_0"],
            "rubric": "评分标准",
            "parsed_rubric": {},
            "api_key": "test_key",
            "retry_count": 0,
            "max_retries": 2
        }
        
        # Mock GeminiReasoningClient 抛出异常
        with patch("src.services.gemini_reasoning.GeminiReasoningClient") as mock_client:
            mock_client.side_effect = Exception("API 调用失败")
            
            result = await grade_batch_node(state)
            
            # 验证返回重试标记
            assert "batch_retry_needed" in result
            assert result["batch_retry_needed"]["retry_count"] == 1
            assert result["batch_retry_needed"]["batch_index"] == 0
    
    @pytest.mark.asyncio
    async def test_grade_batch_max_retries_exceeded(self):
        """测试超过最大重试次数场景"""
        state = {
            "batch_id": "test_batch",
            "batch_index": 0,
            "total_batches": 1,
            "page_indices": [0],
            "images": ["img_0"],
            "rubric": "评分标准",
            "parsed_rubric": {},
            "api_key": "test_key",
            "retry_count": 2,  # 已经重试了 2 次
            "max_retries": 2
        }
        
        # Mock GeminiReasoningClient 抛出异常
        with patch("src.services.gemini_reasoning.GeminiReasoningClient") as mock_client:
            mock_client.side_effect = Exception("API 调用失败")
            
            result = await grade_batch_node(state)
            
            # 验证所有页面标记为失败
            assert "grading_results" in result
            assert all(r["status"] == "failed" for r in result["grading_results"])
            # 不应该再有重试标记
            assert "batch_retry_needed" not in result or result.get("batch_retry_needed") is None
    
    @pytest.mark.asyncio
    async def test_grade_batch_worker_independence(self):
        """测试 Worker 独立性（深拷贝评分标准）"""
        parsed_rubric = {
            "questions": [{"id": "1", "max_score": 10}]
        }
        
        state = {
            "batch_id": "test_batch",
            "batch_index": 0,
            "total_batches": 1,
            "page_indices": [0],
            "images": ["img_0"],
            "rubric": "评分标准",
            "parsed_rubric": parsed_rubric,
            "api_key": "test_key",
            "retry_count": 0,
            "max_retries": 2
        }
        
        # Mock GeminiReasoningClient
        with patch("src.services.gemini_reasoning.GeminiReasoningClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value = mock_instance
            
            # 在 grade_page 中修改传入的 parsed_rubric
            async def modify_rubric(*args, **kwargs):
                # 尝试修改传入的 parsed_rubric
                pr = kwargs.get("parsed_rubric", {})
                if "questions" in pr:
                    pr["questions"].append({"id": "modified"})
                return {
                    "score": 8.0,
                    "max_score": 10.0,
                    "confidence": 0.9,
                    "feedback": "测试反馈",
                    "question_numbers": ["1"],
                    "question_details": [],
                    "is_blank_page": False
                }
            
            mock_instance.grade_page.side_effect = modify_rubric
            
            await grade_batch_node(state)
            
            # 验证原始 parsed_rubric 没有被修改
            assert len(parsed_rubric["questions"]) == 1
            assert parsed_rubric["questions"][0]["id"] == "1"
    
    @pytest.mark.asyncio
    async def test_grade_batch_progress_info(self):
        """测试进度信息生成"""
        state = {
            "batch_id": "test_batch",
            "batch_index": 1,
            "total_batches": 3,
            "page_indices": [10, 11, 12],
            "images": ["img_10", "img_11", "img_12"],
            "rubric": "评分标准",
            "parsed_rubric": {},
            "api_key": "test_key",
            "retry_count": 0,
            "max_retries": 2
        }
        
        # Mock GeminiReasoningClient
        with patch("src.services.gemini_reasoning.GeminiReasoningClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value = mock_instance
            
            mock_instance.grade_page.return_value = {
                "score": 8.0,
                "max_score": 10.0,
                "confidence": 0.9,
                "feedback": "测试反馈",
                "question_numbers": ["1"],
                "question_details": [],
                "is_blank_page": False
            }
            
            result = await grade_batch_node(state)
            
            # 验证进度信息
            assert "batch_progress" in result
            progress = result["batch_progress"]
            assert progress["batch_index"] == 1
            assert progress["total_batches"] == 3
            assert progress["pages_processed"] == 3
            assert progress["pages_failed"] == 0
            assert progress["status"] == "completed"
            assert "timestamp" in progress


class TestWorkerIndependence:
    """测试 Worker 独立性保证"""
    
    @pytest.mark.asyncio
    async def test_multiple_workers_no_shared_state(self):
        """测试多个 Worker 不共享可变状态"""
        import asyncio
        
        shared_rubric = {
            "questions": [{"id": "1", "max_score": 10}]
        }
        
        results = []
        
        async def run_worker(batch_index: int):
            state = {
                "batch_id": "test_batch",
                "batch_index": batch_index,
                "total_batches": 3,
                "page_indices": [batch_index * 10],
                "images": [f"img_{batch_index * 10}"],
                "rubric": "评分标准",
                "parsed_rubric": shared_rubric,
                "api_key": "test_key",
                "retry_count": 0,
                "max_retries": 2
            }
            
            with patch("src.services.gemini_reasoning.GeminiReasoningClient") as mock_client:
                mock_instance = AsyncMock()
                mock_client.return_value = mock_instance
                
                mock_instance.grade_page.return_value = {
                    "score": 8.0,
                    "max_score": 10.0,
                    "confidence": 0.9,
                    "feedback": f"Worker {batch_index}",
                    "question_numbers": ["1"],
                    "question_details": [],
                    "is_blank_page": False
                }
                
                result = await grade_batch_node(state)
                results.append(result)
        
        # 并行运行多个 Worker
        await asyncio.gather(
            run_worker(0),
            run_worker(1),
            run_worker(2)
        )
        
        # 验证所有 Worker 都成功完成
        assert len(results) == 3
        for result in results:
            assert "grading_results" in result
            assert len(result["grading_results"]) == 1
        
        # 验证原始共享状态没有被修改
        assert len(shared_rubric["questions"]) == 1
