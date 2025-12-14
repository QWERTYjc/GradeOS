"""文件验证工具单元测试"""

import pytest
from io import BytesIO
from PIL import Image

from src.utils.validation import (
    validate_image_format,
    validate_file_size,
    validate_file,
    FileValidationError,
    MAX_FILE_SIZE
)


def create_test_image(format_name: str = 'PNG') -> bytes:
    """创建测试图像"""
    img = Image.new('RGB', (100, 100), color='white')
    buffer = BytesIO()
    img.save(buffer, format=format_name)
    return buffer.getvalue()


def test_validate_image_format_png():
    """测试验证 PNG 格式"""
    image_data = create_test_image('PNG')
    is_valid, message = validate_image_format(image_data)
    
    assert is_valid is True
    assert message == 'PNG'


def test_validate_image_format_jpeg():
    """测试验证 JPEG 格式"""
    image_data = create_test_image('JPEG')
    is_valid, message = validate_image_format(image_data)
    
    assert is_valid is True
    assert message == 'JPEG'


def test_validate_image_format_webp():
    """测试验证 WEBP 格式"""
    image_data = create_test_image('WEBP')
    is_valid, message = validate_image_format(image_data)
    
    assert is_valid is True
    assert message == 'WEBP'


def test_validate_image_format_unsupported():
    """测试验证不支持的格式"""
    image_data = create_test_image('BMP')
    is_valid, message = validate_image_format(image_data)
    
    assert is_valid is False
    assert "不支持的图像格式" in message
    assert "BMP" in message


def test_validate_image_format_invalid():
    """测试验证无效图像"""
    is_valid, message = validate_image_format(b"not-an-image")
    
    assert is_valid is False
    assert "无法识别图像格式" in message


def test_validate_file_size_valid():
    """测试验证有效文件大小"""
    file_data = b"x" * 1024  # 1 KB
    is_valid, message = validate_file_size(file_data)
    
    assert is_valid is True
    assert "验证通过" in message


def test_validate_file_size_empty():
    """测试验证空文件"""
    is_valid, message = validate_file_size(b"")
    
    assert is_valid is False
    assert "文件为空" in message


def test_validate_file_size_too_large():
    """测试验证超大文件"""
    file_data = b"x" * (MAX_FILE_SIZE + 1)
    is_valid, message = validate_file_size(file_data)
    
    assert is_valid is False
    assert "文件大小超出限制" in message


def test_validate_file_success():
    """测试成功验证文件"""
    image_data = create_test_image('PNG')
    
    # 不应抛出异常
    validate_file(image_data, is_image=True)


def test_validate_file_empty_fails():
    """测试验证空文件失败"""
    with pytest.raises(FileValidationError) as exc_info:
        validate_file(b"", is_image=True)
    
    assert "文件为空" in str(exc_info.value)


def test_validate_file_too_large_fails():
    """测试验证超大文件失败"""
    large_data = b"x" * (MAX_FILE_SIZE + 1)
    
    with pytest.raises(FileValidationError) as exc_info:
        validate_file(large_data, is_image=True)
    
    assert "文件大小超出限制" in str(exc_info.value)


def test_validate_file_invalid_format_fails():
    """测试验证无效格式失败"""
    with pytest.raises(FileValidationError) as exc_info:
        validate_file(b"not-an-image", is_image=True)
    
    assert "无法识别图像格式" in str(exc_info.value)


def test_validate_file_skip_format_check():
    """测试跳过格式检查"""
    # 当 is_image=False 时，不检查图像格式
    file_data = b"some-data"
    
    # 不应抛出异常（只检查大小）
    validate_file(file_data, is_image=False)
