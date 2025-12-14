"""提交服务单元测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from io import BytesIO
from PIL import Image

from src.services.submission import SubmissionService, SubmissionServiceError
from src.models.submission import SubmissionRequest
from src.models.enums import FileType, SubmissionStatus


@pytest.fixture
def mock_repository():
    """Mock 提交仓储"""
    repo = AsyncMock()
    repo.create.return_value = {
        "submission_id": "test-submission-id",
        "exam_id": "test-exam-id",
        "student_id": "test-student-id",
        "status": "UPLOADED",
        "total_score": None,
        "max_total_score": None,
        "file_paths": ["test/path1.png"],
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-01-01T00:00:00"
    }
    return repo


@pytest.fixture
def mock_storage():
    """Mock 存储服务"""
    storage = AsyncMock()
    storage.save_files.return_value = ["test/path1.png"]
    return storage


@pytest.fixture
def submission_service(mock_repository, mock_storage):
    """创建提交服务实例"""
    return SubmissionService(
        repository=mock_repository,
        storage=mock_storage,
        temporal_client=None  # 不测试 Temporal 集成
    )


def create_test_image() -> bytes:
    """创建测试图像"""
    img = Image.new('RGB', (100, 100), color='white')
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_submit_image_success(submission_service, mock_repository, mock_storage):
    """测试成功提交图像"""
    # 准备测试数据
    image_data = create_test_image()
    request = SubmissionRequest(
        exam_id="exam-001",
        student_id="student-001",
        file_type=FileType.IMAGE,
        file_data=image_data
    )
    
    # 执行提交
    response = await submission_service.submit(request)
    
    # 验证结果
    assert response.submission_id == "test-submission-id"
    assert response.status == SubmissionStatus.UPLOADED
    assert response.estimated_completion_time > 0
    
    # 验证调用
    mock_storage.save_files.assert_called_once()
    mock_repository.create.assert_called_once()


@pytest.mark.asyncio
async def test_submit_empty_file_fails(submission_service):
    """测试提交空文件失败"""
    request = SubmissionRequest(
        exam_id="exam-001",
        student_id="student-001",
        file_type=FileType.IMAGE,
        file_data=b""  # 空文件
    )
    
    with pytest.raises(SubmissionServiceError) as exc_info:
        await submission_service.submit(request)
    
    assert "文件为空" in str(exc_info.value)


@pytest.mark.asyncio
async def test_submit_oversized_file_fails(submission_service):
    """测试提交超大文件失败"""
    # 创建超过 50MB 的文件
    large_data = b"x" * (51 * 1024 * 1024)
    
    request = SubmissionRequest(
        exam_id="exam-001",
        student_id="student-001",
        file_type=FileType.IMAGE,
        file_data=large_data
    )
    
    with pytest.raises(SubmissionServiceError) as exc_info:
        await submission_service.submit(request)
    
    assert "文件大小超出限制" in str(exc_info.value)


@pytest.mark.asyncio
async def test_submit_pdf_conversion(submission_service, mock_repository, mock_storage):
    """测试 PDF 转换"""
    # Mock PDF 转换
    with patch('src.services.submission.convert_pdf_to_images') as mock_convert:
        mock_convert.return_value = [create_test_image(), create_test_image()]
        
        request = SubmissionRequest(
            exam_id="exam-001",
            student_id="student-001",
            file_type=FileType.PDF,
            file_data=b"fake-pdf-data"
        )
        
        response = await submission_service.submit(request)
        
        # 验证 PDF 转换被调用
        mock_convert.assert_called_once_with(b"fake-pdf-data", dpi=300)
        
        # 验证保存了多个文件
        mock_storage.save_files.assert_called_once()
        saved_files = mock_storage.save_files.call_args[0][0]
        assert len(saved_files) == 2


@pytest.mark.asyncio
async def test_get_status_success(submission_service, mock_repository):
    """测试成功查询状态"""
    mock_repository.get_by_id.return_value = {
        "submission_id": "test-id",
        "exam_id": "exam-001",
        "student_id": "student-001",
        "status": "COMPLETED",
        "total_score": 85.5,
        "max_total_score": 100.0,
        "file_paths": ["test/path1.png"],
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-01-01T00:00:00"
    }
    
    status = await submission_service.get_status("test-id")
    
    assert status is not None
    assert status.submission_id == "test-id"
    assert status.status == SubmissionStatus.COMPLETED
    assert status.total_score == 85.5
    assert status.max_total_score == 100.0


@pytest.mark.asyncio
async def test_get_status_not_found(submission_service, mock_repository):
    """测试查询不存在的提交"""
    mock_repository.get_by_id.return_value = None
    
    status = await submission_service.get_status("nonexistent-id")
    
    assert status is None
