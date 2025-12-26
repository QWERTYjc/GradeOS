"""评分细则服务单元测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.services.rubric import RubricService
from src.repositories.rubric import RubricRepository
from src.services.cache import CacheService
from src.models.rubric import (
    Rubric,
    RubricCreateRequest,
    RubricUpdateRequest,
    ScoringPoint
)


@pytest.fixture
def mock_repository():
    """Mock 评分细则仓储"""
    return AsyncMock(spec=RubricRepository)


@pytest.fixture
def mock_cache_service():
    """Mock 缓存服务"""
    return AsyncMock(spec=CacheService)


@pytest.fixture
def rubric_service(mock_repository, mock_cache_service):
    """评分细则服务实例"""
    return RubricService(mock_repository, mock_cache_service)


@pytest.fixture
def sample_rubric_data():
    """示例评分细则数据"""
    return {
        "rubric_id": "rubric-123",
        "exam_id": "exam-001",
        "question_id": "q1",
        "rubric_text": "1. 正确列出公式（3分）\n2. 计算过程正确（5分）",
        "max_score": 8.0,
        "scoring_points": [
            {"description": "正确列出公式", "score": 3.0, "required": True},
            {"description": "计算过程正确", "score": 5.0, "required": True}
        ],
        "standard_answer": "F=ma",
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-01-01T00:00:00"
    }


@pytest.fixture
def sample_create_request():
    """示例创建请求"""
    return RubricCreateRequest(
        exam_id="exam-001",
        question_id="q1",
        rubric_text="1. 正确列出公式（3分）\n2. 计算过程正确（5分）",
        max_score=8.0,
        scoring_points=[
            ScoringPoint(description="正确列出公式", score=3.0, required=True),
            ScoringPoint(description="计算过程正确", score=5.0, required=True)
        ],
        standard_answer="F=ma"
    )


class TestCreateRubric:
    """测试创建评分细则"""
    
    @pytest.mark.asyncio
    async def test_create_rubric_success(
        self,
        rubric_service,
        mock_repository,
        sample_create_request,
        sample_rubric_data
    ):
        """测试成功创建评分细则"""
        # 设置 mock
        mock_repository.exists.return_value = False
        mock_repository.create.return_value = sample_rubric_data
        
        # 执行
        result = await rubric_service.create_rubric(sample_create_request)
        
        # 验证
        assert isinstance(result, Rubric)
        assert result.rubric_id == "rubric-123"
        assert result.exam_id == "exam-001"
        assert result.question_id == "q1"
        assert result.max_score == 8.0
        
        # 验证仓储调用
        mock_repository.exists.assert_called_once_with("exam-001", "q1")
        mock_repository.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_rubric_already_exists(
        self,
        rubric_service,
        mock_repository,
        sample_create_request
    ):
        """测试创建已存在的评分细则"""
        # 设置 mock
        mock_repository.exists.return_value = True
        
        # 执行并验证异常
        with pytest.raises(ValueError, match="评分细则已存在"):
            await rubric_service.create_rubric(sample_create_request)
        
        # 验证未调用 create
        mock_repository.create.assert_not_called()


class TestGetRubric:
    """测试获取评分细则"""
    
    @pytest.mark.asyncio
    async def test_get_rubric_success(
        self,
        rubric_service,
        mock_repository,
        sample_rubric_data
    ):
        """测试成功获取评分细则"""
        # 设置 mock
        mock_repository.get_by_exam_and_question.return_value = sample_rubric_data
        
        # 执行
        result = await rubric_service.get_rubric("exam-001", "q1")
        
        # 验证
        assert isinstance(result, Rubric)
        assert result.rubric_id == "rubric-123"
        assert result.exam_id == "exam-001"
        
        mock_repository.get_by_exam_and_question.assert_called_once_with(
            "exam-001", "q1"
        )
    
    @pytest.mark.asyncio
    async def test_get_rubric_not_found(
        self,
        rubric_service,
        mock_repository
    ):
        """测试获取不存在的评分细则"""
        # 设置 mock
        mock_repository.get_by_exam_and_question.return_value = None
        
        # 执行
        result = await rubric_service.get_rubric("exam-001", "q1")
        
        # 验证
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_rubric_by_id(
        self,
        rubric_service,
        mock_repository,
        sample_rubric_data
    ):
        """测试根据 ID 获取评分细则"""
        # 设置 mock
        mock_repository.get_by_id.return_value = sample_rubric_data
        
        # 执行
        result = await rubric_service.get_rubric_by_id("rubric-123")
        
        # 验证
        assert isinstance(result, Rubric)
        assert result.rubric_id == "rubric-123"
        
        mock_repository.get_by_id.assert_called_once_with("rubric-123")


class TestUpdateRubric:
    """测试更新评分细则"""
    
    @pytest.mark.asyncio
    async def test_update_rubric_success(
        self,
        rubric_service,
        mock_repository,
        mock_cache_service,
        sample_rubric_data
    ):
        """测试成功更新评分细则"""
        # 设置 mock
        mock_repository.get_by_id.side_effect = [
            sample_rubric_data,  # 第一次调用：获取旧数据
            {**sample_rubric_data, "max_score": 10.0}  # 第二次调用：获取更新后数据
        ]
        mock_repository.update.return_value = True
        mock_cache_service.invalidate_by_rubric.return_value = 5
        
        # 执行
        update_request = RubricUpdateRequest(max_score=10.0)
        result = await rubric_service.update_rubric("rubric-123", update_request)
        
        # 验证
        assert isinstance(result, Rubric)
        assert result.max_score == 10.0
        
        # 验证缓存失效被调用
        mock_cache_service.invalidate_by_rubric.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_rubric_text_invalidates_both_caches(
        self,
        rubric_service,
        mock_repository,
        mock_cache_service,
        sample_rubric_data
    ):
        """测试更新评分细则文本时使新旧缓存都失效"""
        # 设置 mock
        new_rubric_text = "新的评分细则文本"
        mock_repository.get_by_id.side_effect = [
            sample_rubric_data,
            {**sample_rubric_data, "rubric_text": new_rubric_text}
        ]
        mock_repository.update.return_value = True
        mock_cache_service.invalidate_by_rubric.side_effect = [3, 2]
        
        # 执行
        update_request = RubricUpdateRequest(rubric_text=new_rubric_text)
        result = await rubric_service.update_rubric("rubric-123", update_request)
        
        # 验证缓存失效被调用两次（旧文本和新文本）
        assert mock_cache_service.invalidate_by_rubric.call_count == 2
    
    @pytest.mark.asyncio
    async def test_update_rubric_not_found(
        self,
        rubric_service,
        mock_repository
    ):
        """测试更新不存在的评分细则"""
        # 设置 mock
        mock_repository.get_by_id.return_value = None
        
        # 执行并验证异常
        update_request = RubricUpdateRequest(max_score=10.0)
        with pytest.raises(ValueError, match="评分细则不存在"):
            await rubric_service.update_rubric("rubric-123", update_request)


class TestDeleteRubric:
    """测试删除评分细则"""
    
    @pytest.mark.asyncio
    async def test_delete_rubric_success(
        self,
        rubric_service,
        mock_repository,
        mock_cache_service,
        sample_rubric_data
    ):
        """测试成功删除评分细则"""
        # 设置 mock
        mock_repository.get_by_id.return_value = sample_rubric_data
        mock_repository.delete.return_value = True
        mock_cache_service.invalidate_by_rubric.return_value = 3
        
        # 执行
        result = await rubric_service.delete_rubric("rubric-123")
        
        # 验证
        assert result is True
        
        # 验证缓存失效被调用
        mock_cache_service.invalidate_by_rubric.assert_called_once_with(
            sample_rubric_data["rubric_text"]
        )
        mock_repository.delete.assert_called_once_with("rubric-123")
    
    @pytest.mark.asyncio
    async def test_delete_rubric_not_found(
        self,
        rubric_service,
        mock_repository,
        mock_cache_service
    ):
        """测试删除不存在的评分细则"""
        # 设置 mock
        mock_repository.get_by_id.return_value = None
        
        # 执行
        result = await rubric_service.delete_rubric("rubric-123")
        
        # 验证
        assert result is False
        
        # 验证未调用缓存失效和删除
        mock_cache_service.invalidate_by_rubric.assert_not_called()
        mock_repository.delete.assert_not_called()


class TestValidateRubricForGrading:
    """测试评分细则验证"""
    
    @pytest.mark.asyncio
    async def test_validate_rubric_exists(
        self,
        rubric_service,
        mock_repository
    ):
        """测试验证存在的评分细则"""
        # 设置 mock
        mock_repository.exists.return_value = True
        
        # 执行
        is_valid, error_msg = await rubric_service.validate_rubric_for_grading(
            "exam-001", "q1"
        )
        
        # 验证
        assert is_valid is True
        assert error_msg is None
    
    @pytest.mark.asyncio
    async def test_validate_rubric_missing(
        self,
        rubric_service,
        mock_repository
    ):
        """测试验证缺失的评分细则"""
        # 设置 mock
        mock_repository.exists.return_value = False
        
        # 执行
        is_valid, error_msg = await rubric_service.validate_rubric_for_grading(
            "exam-001", "q1"
        )
        
        # 验证
        assert is_valid is False
        assert error_msg is not None
        assert "缺失评分细则" in error_msg
        assert "需要手动配置" in error_msg
    
    @pytest.mark.asyncio
    async def test_check_rubric_exists(
        self,
        rubric_service,
        mock_repository
    ):
        """测试检查评分细则是否存在"""
        # 设置 mock
        mock_repository.exists.return_value = True
        
        # 执行
        result = await rubric_service.check_rubric_exists("exam-001", "q1")
        
        # 验证
        assert result is True
        mock_repository.exists.assert_called_once_with("exam-001", "q1")


class TestGetExamRubrics:
    """测试获取考试的所有评分细则"""
    
    @pytest.mark.asyncio
    async def test_get_exam_rubrics(
        self,
        rubric_service,
        mock_repository,
        sample_rubric_data
    ):
        """测试获取考试的所有评分细则"""
        # 设置 mock
        rubric_data_2 = {**sample_rubric_data, "question_id": "q2", "rubric_id": "rubric-456"}
        mock_repository.get_by_exam.return_value = [sample_rubric_data, rubric_data_2]
        
        # 执行
        result = await rubric_service.get_exam_rubrics("exam-001")
        
        # 验证
        assert len(result) == 2
        assert all(isinstance(r, Rubric) for r in result)
        assert result[0].question_id == "q1"
        assert result[1].question_id == "q2"
        
        mock_repository.get_by_exam.assert_called_once_with("exam-001")
