"""PDF 处理工具"""

import logging
from typing import List

import fitz
from pdf2image import convert_from_bytes
from PIL import Image

from src.utils.image import pil_to_jpeg_bytes

logger = logging.getLogger(__name__)


class PDFProcessingError(Exception):
    """PDF 处理错误"""
    pass


def _convert_with_pymupdf(pdf_data: bytes, dpi: int) -> List[bytes]:
    doc = fitz.open(stream=pdf_data, filetype="pdf")
    images: List[bytes] = []
    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)
    try:
        for page in doc:
            pix = page.get_pixmap(matrix=matrix)
            mode = "RGB" if pix.alpha == 0 else "RGBA"
            img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
            if mode == "RGBA":
                img = img.convert("RGB")
            images.append(pil_to_jpeg_bytes(img))
    finally:
        doc.close()

    if not images:
        raise PDFProcessingError("PDF conversion returned empty output (pymupdf)")
    return images


async def convert_pdf_to_images(pdf_data: bytes, dpi: int = 300) -> List[bytes]:
    """
    将 PDF 转换为高分辨率图像
    
    Args:
        pdf_data: PDF 文件的字节数据
        dpi: 分辨率，默认 300 DPI
        
    Returns:
        图像字节数据列表，每页一个图像
        
    Raises:
        PDFProcessingError: PDF 转换失败时抛出
    """
    try:
        images = convert_from_bytes(pdf_data, dpi=dpi)
        if not images:
            raise PDFProcessingError("PDF conversion returned empty output (pdf2image)")

        image_bytes_list: List[bytes] = []
        for img in images:
            image_bytes_list.append(pil_to_jpeg_bytes(img))

        return image_bytes_list
    except Exception as exc:
        logger.warning("pdf2image failed, falling back to pymupdf: %s", exc)
        try:
            return _convert_with_pymupdf(pdf_data, dpi)
        except Exception as fallback_exc:
            raise PDFProcessingError(f"PDF 转换失败: {str(fallback_exc)}") from fallback_exc
