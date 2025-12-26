"""LangGraph 节点单元测试"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.graphs.nodes.segment import segment_node
from src.graphs.nodes.grade import grade_node
from src.graphs.nodes.persist import persist_node
from src.graphs.nodes.notify import notify_node, notify_teacher_node
from src.graphs.state import GradingGraphState


@pytest.fixture
def base_state() -> GradingGraphState:
    """创建基础测试状态"""
    return {
        "job_id": "job_123",
        "submission_id": "sub_123",
        "exam_id": "exam_123",
        "student_id": "student_123",
        "inputs": {},
        "file_paths": [],
        "rubric": "测试评分标准",
        "progress": {},
        "current_stage": "init",
        "percentage": 0.0,
        "artifacts": {},
        "grading_results": [],
        "total_score": 0.0,
        "max_total_score": 0.0,
        "errors": [],
        "retry_count": 0,
        "timestamps": {},
        "needs_review": False,
        "review_result": None,
        "external_event": None
    }


class TestSegmentNode:
    """测试分割节点"""
    
    @pytest.mark.asyncio
    async def test_segment_node_basic(self, base_state, tmp_path):
        """测试基本分割功能"""
        # 创建临时测试文件
        test_file = tmp_path / "test_page.jpg"
        test_file.write_bytes(b"fake image data")
        
        state = {
            **base_state,
            "file_paths": [str(test_file)]
        }
        
        # Mock LayoutAnalysisService
        with patch("src.graphs.nodes.segment.LayoutAnalysisService") as mock_service:
            mock_instance = AsyncMock()
            mock_service.return_value = mock_instance
            
            # Mock 返回结果
            mock_result = MagicMock()
            mock_result.regions = [
                MagicMock(dict=lambda: {"question_id": "q1", "bbox": [0, 0, 100, 100]})
            ]
            mock_result.metadata = {"page_count": 1}
            mock_instance.segment_document.return_value = mock_result
            
            # 执行节点
            result_state = await segment_node(state)
            
            # 验证结果
            assert result_state["current_stage"] == "segmentation_completed"
            assert result_state["percentage"] == 20.0
            assert "segmentation_results" in result_state["artifacts"]
            assert result_state["progress"]["segmentation_completed"] is True


class TestGradeNode:
    """测试批改节点"""
    
    @pytest.mark.asyncio
    async def test_grade_node_with_cache_hit(self, base_state, tmp_path):
        """测试缓存命中场景"""
        # 创建临时测试文件
        test_file = tmp_path / "test_page.jpg"
        test_file.write_bytes(b"fake image data")
        
        state = {
            **base_state,
            "file_paths": [str(test_file)],
            "artifacts": {
                "segmentation_results": [
                    {
                        "page_index": 0,
                        "file_path": str(test_file),
                        "regions": [
                            {"question_id": "q1", "max_score": 10.0}
                        ],
                        "metadata": {}
                    }
                ]
            }
        }
        
        # Mock CacheService 和 GradingAgent
        with patch("src.graphs.nodes.grade.CacheService") as mock_cache, \
             patch("src.graphs.nodes.grade.GradingAgent") as mock_agent:
            
            mock_cache_instance = AsyncMock()
            mock_cache.return_value = mock_cache_instance
            
            # Mock 缓存命中
            from src.models.grading import GradingResult
            cached_result = GradingResult(
                question_id="q1",
                score=8.0,
                max_score=10.0,
                confidence=0.95,
                feedback="缓存结果",
                visual_annotations=[],
                agent_trace={}
            )
            mock_cache_instance.get_cached_result.return_value = cached_result
            
            # 执行节点
            result_state = await grade_node(state)
            
            # 验证结果
            assert result_state["current_stage"] == "grading_completed"
            assert len(result_state["grading_results"]) == 1
            assert result_state["total_score"] == 8.0
            assert result_state["max_total_score"] == 10.0


class TestPersistNode:
    """测试持久化节点"""
    
    @pytest.mark.asyncio
    async def test_persist_node_basic(self, base_state):
        """测试基本持久化功能"""
        state = {
            **base_state,
            "grading_results": [
                {
                    "question_id": "q1",
                    "score": 8.0,
                    "max_score": 10.0,
                    "confidence": 0.9,
                    "feedback": "测试反馈",
                    "visual_annotations": [],
                    "agent_trace": {}
                }
            ],
            "total_score": 8.0,
            "max_total_score": 10.0
        }
        
        # Mock 数据库和仓储
        with patch("src.graphs.nodes.persist.get_db_pool") as mock_pool, \
             patch("src.graphs.nodes.persist.GradingResultRepository") as mock_gr_repo, \
             patch("src.graphs.nodes.persist.SubmissionRepository") as mock_sub_repo:
            
            mock_pool.return_value = AsyncMock()
            
            mock_gr_instance = AsyncMock()
            mock_gr_repo.return_value = mock_gr_instance
            
            mock_sub_instance = AsyncMock()
            mock_sub_repo.return_value = mock_sub_instance
            
            # 执行节点
            result_state = await persist_node(state)
            
            # 验证结果
            assert result_state["current_stage"] == "persistence_completed"
            assert result_state["percentage"] == 90.0
            assert result_state["progress"]["persistence_completed"] is True
            
            # 验证调用
            mock_gr_instance.create.assert_called_once()
            mock_sub_instance.update_scores.assert_called_once()
            mock_sub_instance.update_status.assert_called_once()


class TestNotifyNode:
    """测试通知节点"""
    
    @pytest.mark.asyncio
    async def test_notify_node_completed(self, base_state):
        """测试批改完成通知"""
        state = {
            **base_state,
            "grading_results": [
                {
                    "question_id": "q1",
                    "score": 8.0,
                    "max_score": 10.0,
                    "confidence": 0.95,
                    "feedback": "测试反馈"
                }
            ],
            "total_score": 8.0,
            "max_total_score": 10.0,
            "needs_review": False
        }
        
        # 执行节点
        result_state = await notify_node(state)
        
        # 验证结果
        assert result_state["current_stage"] == "notification_sent"
        assert result_state["percentage"] == 100.0
        assert result_state["progress"]["notification_sent"] is True
        assert "notification" in result_state["artifacts"]
        assert result_state["artifacts"]["notification"]["type"] == "grading_completed"
    
    @pytest.mark.asyncio
    async def test_notify_node_review_required(self, base_state):
        """测试需要审核通知"""
        state = {
            **base_state,
            "grading_results": [
                {
                    "question_id": "q1",
                    "score": 5.0,
                    "max_score": 10.0,
                    "confidence": 0.6,  # 低置信度
                    "feedback": "测试反馈"
                }
            ],
            "total_score": 5.0,
            "max_total_score": 10.0,
            "needs_review": True
        }
        
        # 执行节点
        result_state = await notify_node(state)
        
        # 验证结果
        assert result_state["current_stage"] == "notification_sent"
        assert "notification" in result_state["artifacts"]
        assert result_state["artifacts"]["notification"]["type"] == "review_required"
        assert len(result_state["artifacts"]["notification"]["low_confidence_questions"]) == 1
    
    @pytest.mark.asyncio
    async def test_notify_teacher_node(self, base_state):
        """测试教师通知节点"""
        state = {
            **base_state,
            "grading_results": [
                {
                    "question_id": "q1",
                    "score": 5.0,
                    "max_score": 10.0,
                    "confidence": 0.6,
                    "feedback": "测试反馈",
                    "visual_annotations": []
                }
            ]
        }
        
        # 执行节点
        result_state = await notify_teacher_node(state)
        
        # 验证结果
        assert "teacher_notification" in result_state["artifacts"]
        assert result_state["artifacts"]["teacher_notification"]["type"] == "low_confidence_review"
        assert result_state["artifacts"]["teacher_notification"]["low_confidence_count"] == 1
