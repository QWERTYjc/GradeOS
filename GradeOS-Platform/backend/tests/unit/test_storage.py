"""存储服务单元测试"""

import pytest
import tempfile
import shutil
from pathlib import Path

from src.services.storage import StorageService, StorageError


@pytest.fixture
def temp_storage():
    """创建临时存储目录"""
    temp_dir = tempfile.mkdtemp()
    storage = StorageService(base_path=temp_dir)
    
    yield storage
    
    # 清理
    shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_save_file_success(temp_storage):
    """测试成功保存文件"""
    file_data = b"test-data"
    submission_id = "test-submission"
    
    file_path = await temp_storage.save_file(
        file_data,
        submission_id,
        file_index=0,
        extension="png"
    )
    
    assert file_path is not None
    assert submission_id in file_path
    assert "page_0.png" in file_path


@pytest.mark.asyncio
async def test_save_multiple_files(temp_storage):
    """测试保存多个文件"""
    files_data = [b"data1", b"data2", b"data3"]
    submission_id = "test-submission"
    
    file_paths = await temp_storage.save_files(
        files_data,
        submission_id,
        extension="png"
    )
    
    assert len(file_paths) == 3
    assert all(submission_id in path for path in file_paths)
    assert "page_0.png" in file_paths[0]
    assert "page_1.png" in file_paths[1]
    assert "page_2.png" in file_paths[2]


@pytest.mark.asyncio
async def test_get_file_success(temp_storage):
    """测试成功读取文件"""
    file_data = b"test-data"
    submission_id = "test-submission"
    
    # 先保存
    file_path = await temp_storage.save_file(
        file_data,
        submission_id,
        file_index=0
    )
    
    # 再读取
    retrieved_data = await temp_storage.get_file(file_path)
    
    assert retrieved_data == file_data


@pytest.mark.asyncio
async def test_get_nonexistent_file_fails(temp_storage):
    """测试读取不存在的文件失败"""
    with pytest.raises(StorageError) as exc_info:
        await temp_storage.get_file("nonexistent/file.png")
    
    assert "文件不存在" in str(exc_info.value)


@pytest.mark.asyncio
async def test_delete_files_success(temp_storage):
    """测试成功删除文件"""
    file_data = b"test-data"
    submission_id = "test-submission"
    
    # 先保存
    await temp_storage.save_file(
        file_data,
        submission_id,
        file_index=0
    )
    
    # 删除
    result = await temp_storage.delete_files(submission_id)
    
    assert result is True
    
    # 验证目录已删除
    submission_dir = temp_storage.base_path / submission_id
    assert not submission_dir.exists()


@pytest.mark.asyncio
async def test_delete_nonexistent_files(temp_storage):
    """测试删除不存在的文件"""
    result = await temp_storage.delete_files("nonexistent-submission")
    
    assert result is False


@pytest.mark.asyncio
async def test_save_file_creates_directory(temp_storage):
    """测试保存文件时自动创建目录"""
    file_data = b"test-data"
    submission_id = "new-submission"
    
    # 确保目录不存在
    submission_dir = temp_storage.base_path / submission_id
    assert not submission_dir.exists()
    
    # 保存文件
    await temp_storage.save_file(
        file_data,
        submission_id,
        file_index=0
    )
    
    # 验证目录已创建
    assert submission_dir.exists()
    assert submission_dir.is_dir()
