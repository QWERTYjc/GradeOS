"""Temporal Activities 单元测试"""

import pytest
import base64
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List

from src.activities.segment import segment_document_activity
from src.activities.grade import grade_question_activity
from src.activities.notify import notify_teacher_activity
from src.activities.persist import persist_results_activity

from src.models.region import (
    BoundingBox, QuestionRegion, SegmentationResult
)
from src.models.grading import GradingResult
from src.models.enums import SubmissionStatus


class TestSegmentDocumentActivity:
    """文档分割 Activity 测试"""
    
    @pytest.mark.asyncio
    async def test_segment_document_success(self):
        """测试成功分割文档"""
        # 准备测试数据
        submission_id = "sub_001"
        page_index = 0
        image_data = b"fake_image_data"
        
        # Mock LayoutAnalysisService
        mock_layout_service = AsyncMock()
        expected_result = SegmentationResult(
            submission_id=submission_id,
            total_pages=1,
            regions=[
                QuestionRegion(
                    question_id="q1",
                    page_index=0,
                    bounding_box=BoundingBox(
                        ymin=100, xmin=50, ymax=300, xmax=400
                    )
                )
            ]
        )
        mock_layout_service.segment_document.return_value = expected_result
        
        # 执行 Activity
        result = await segment_document_activity(
            submission_id=submission_id,
            image_data=image_data,
            page_index=page_index,
            layout_service=mock_layout_service
        )
        
        # 验证结果
        assert result.submission_id == submission_id
        assert len(result.regions) == 1
        assert result.regions[0].question_id == "q1"
        mock_layout_service.segment_document.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_segment_document_no_service(self):
        """测试缺少服务实例"""
        with pytest.raises(ValueError, match="layout_service 不能为 None"):
            await segment_document_activity(
                submission_id="sub_001",
                image_data=b"data",
                layout_service=None
            )
    
    @pytest.mark.asyncio
    async def test_segment_document_no_regions(self):
        """测试无法识别题目区域"""
        mock_layout_service = AsyncMock()
        mock_layout_service.segment_document.side_effect = ValueError(
            "未能识别页面 0 中的任何题目区域"
        )
        
        with pytest.raises(ValueError):
            await segment_document_activity(
                submission_id="sub_001",
                image_data=b"data",
                layout_service=mock_layout_service
            )


class TestGradeQuestionActivity:
    """批改题目 Activity 测试"""
    
    @pytest.mark.asyncio
    async def test_grade_question_cache_hit(self):
        """测试缓存命中"""
        # 准备测试数据
        submission_id = "sub_001"
        question_id = "q1"
        image_b64 = base64.b64encode(b"image_data").decode()
        rubric = "评分细则"
        max_score = 10.0
        
        # Mock 缓存服务
        mock_cache_service = AsyncMock()
        cached_result = GradingResult(
            question_id=question_id,
            score=8.5,
            max_score=max_score,
            confidence=0.95,
            feedback="很好",
            visual_annotations=[],
            agent_trace={}
        )
        mock_cache_service.get_cached_result.return_value = cached_result
        
        # Mock 智能体
        mock_agent = AsyncMock()
        
        # 执行 Activity
        result = await grade_question_activity(
            submission_id=submission_id,
            question_id=question_id,
            image_b64=image_b64,
            rubric=rubric,
            max_score=max_score,
            cache_service=mock_cache_service,
            grading_agent=mock_agent
        )
        
        # 验证结果
        assert result.score == 8.5
        assert result.confidence == 0.95
        # 验证智能体未被调用（缓存命中）
        mock_agent.run.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_grade_question_cache_miss(self):
        """测试缓存未命中，调用智能体"""
        # 准备测试数据
        submission_id = "sub_001"
        question_id = "q1"
        image_b64 = base64.b64encode(b"image_data").decode()
        rubric = "评分细则"
        max_score = 10.0
        
        # Mock 缓存服务
        mock_cache_service = AsyncMock()
        mock_cache_service.get_cached_result.return_value = None
        
        # Mock 智能体
        mock_agent = AsyncMock()
        mock_agent.run.return_value = {
            "final_score": 7.5,
            "confidence": 0.85,
            "student_feedback": "需要改进",
            "visual_annotations": [],
            "vision_analysis": "分析",
            "reasoning_trace": [],
            "rubric_mapping": [],
            "critique_feedback": None,
            "revision_count": 0
        }
        
        # 执行 Activity
        result = await grade_question_activity(
            submission_id=submission_id,
            question_id=question_id,
            image_b64=image_b64,
            rubric=rubric,
            max_score=max_score,
            cache_service=mock_cache_service,
            grading_agent=mock_agent
        )
        
        # 验证结果
        assert result.score == 7.5
        assert result.confidence == 0.85
        # 验证智能体被调用
        mock_agent.run.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_grade_question_cache_high_confidence(self):
        """测试高置信度结果被缓存"""
        # 准备测试数据
        submission_id = "sub_001"
        question_id = "q1"
        image_b64 = base64.b64encode(b"image_data").decode()
        rubric = "评分细则"
        max_score = 10.0
        
        # Mock 缓存服务
        mock_cache_service = AsyncMock()
        mock_cache_service.get_cached_result.return_value = None
        
        # Mock 智能体
        mock_agent = AsyncMock()
        mock_agent.run.return_value = {
            "final_score": 9.5,
            "confidence": 0.95,  # 高置信度
            "student_feedback": "很好",
            "visual_annotations": [],
            "vision_analysis": "分析",
            "reasoning_trace": [],
            "rubric_mapping": [],
            "critique_feedback": None,
            "revision_count": 0
        }
        
        # 执行 Activity
        result = await grade_question_activity(
            submission_id=submission_id,
            question_id=question_id,
            image_b64=image_b64,
            rubric=rubric,
            max_score=max_score,
            cache_service=mock_cache_service,
            grading_agent=mock_agent
        )
        
        # 验证缓存被调用
        mock_cache_service.cache_result.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_grade_question_no_agent(self):
        """测试缺少智能体实例"""
        with pytest.raises(ValueError, match="grading_agent 不能为 None"):
            await grade_question_activity(
                submission_id="sub_001",
                question_id="q1",
                image_b64="data",
                rubric="rubric",
                max_score=10.0,
                grading_agent=None
            )


class TestNotifyTeacherActivity:
    """通知教师 Activity 测试"""
    
    @pytest.mark.asyncio
    async def test_notify_teacher_success(self):
        """测试成功发送通知"""
        result = await notify_teacher_activity(
            submission_id="sub_001",
            exam_id="exam_001",
            student_id="student_001",
            teacher_email="teacher@example.com",
            low_confidence_questions=["q1", "q2"]
        )
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_notify_teacher_no_email(self):
        """测试没有邮箱的通知"""
        result = await notify_teacher_activity(
            submission_id="sub_001",
            exam_id="exam_001",
            student_id="student_001"
        )
        
        assert result is True


class TestPersistResultsActivity:
    """持久化结果 Activity 测试"""
    
    @pytest.mark.asyncio
    async def test_persist_results_success(self):
        """测试成功持久化结果"""
        # 准备测试数据
        submission_id = "sub_001"
        grading_results = [
            GradingResult(
                question_id="q1",
                score=8.5,
                max_score=10.0,
                confidence=0.9,
                feedback="很好",
                visual_annotations=[],
                agent_trace={}
            ),
            GradingResult(
                question_id="q2",
                score=7.5,
                max_score=10.0,
                confidence=0.85,
                feedback="需要改进",
                visual_annotations=[],
                agent_trace={}
            )
        ]
        
        # Mock 仓储
        mock_grading_repo = AsyncMock()
        mock_submission_repo = AsyncMock()
        
        # 执行 Activity
        result = await persist_results_activity(
            submission_id=submission_id,
            grading_results=grading_results,
            grading_result_repo=mock_grading_repo,
            submission_repo=mock_submission_repo
        )
        
        # 验证结果
        assert result is True
        # 验证为每个结果调用了 create
        assert mock_grading_repo.create.call_count == 2
        # 验证更新了总分
        mock_submission_repo.update_scores.assert_called_once_with(
            submission_id=submission_id,
            total_score=16.0,
            max_total_score=20.0
        )
        # 验证更新了状态
        mock_submission_repo.update_status.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_persist_results_no_repo(self):
        """测试缺少仓储实例"""
        with pytest.raises(ValueError):
            await persist_results_activity(
                submission_id="sub_001",
                grading_results=[],
                grading_result_repo=None,
                submission_repo=None
            )
    
    @pytest.mark.asyncio
    async def test_persist_results_empty_list(self):
        """测试空结果列表"""
        # Mock 仓储
        mock_grading_repo = AsyncMock()
        mock_submission_repo = AsyncMock()
        
        # 执行 Activity
        result = await persist_results_activity(
            submission_id="sub_001",
            grading_results=[],
            grading_result_repo=mock_grading_repo,
            submission_repo=mock_submission_repo
        )
        
        # 验证结果
        assert result is True
        # 验证更新了总分为 0
        mock_submission_repo.update_scores.assert_called_once_with(
            submission_id="sub_001",
            total_score=0.0,
            max_total_score=0.0
        )
