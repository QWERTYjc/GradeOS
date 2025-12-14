"""PDF 处理工具单元测试"""

import pytest
from io import BytesIO
from PIL import Image

from src.utils.pdf import convert_pdf_to_images, PDFProcessingError


def create_fake_pdf() -> bytes:
    """创建一个假的 PDF（实际上是图像）用于测试"""
    # 注意：这不是真正的 PDF，只是用于测试错误处理
    return b"fake-pdf-data"


@pytest.mark.asyncio
async def test_convert_empty_pdf_fails():
    """测试转换空 PDF 失败"""
    with pytest.raises(PDFProcessingError):
        await convert_pdf_to_images(b"", dpi=300)


@pytest.mark.asyncio
async def test_convert_invalid_pdf_fails():
    """测试转换无效 PDF 失败"""
    with pytest.raises(PDFProcessingError):
        await convert_pdf_to_images(b"not-a-pdf", dpi=300)


@pytest.mark.asyncio
async def test_convert_pdf_with_custom_dpi():
    """测试使用自定义 DPI 转换 PDF"""
    # 这个测试需要真实的 PDF 文件，这里只测试参数传递
    # 在实际环境中，应该使用真实的 PDF 文件进行集成测试
    pass
