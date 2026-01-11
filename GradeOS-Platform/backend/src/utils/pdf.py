"""PDF 处理工具"""

from typing import List
from pdf2image import convert_from_bytes
from src.utils.image import pil_to_jpeg_bytes


class PDFProcessingError(Exception):
    """PDF 处理错误"""
    pass


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
        # 将 PDF 转换为 PIL Image 对象列表
        images = convert_from_bytes(pdf_data, dpi=dpi)
        
        if not images:
            raise PDFProcessingError("PDF 转换结果为空")
        
        # 将每个 PIL Image 转换为字节数据
        image_bytes_list: List[bytes] = []
        for img in images:
            # Convert each PIL image to JPEG bytes.
            image_bytes_list.append(pil_to_jpeg_bytes(img))
        
        return image_bytes_list
        
    except Exception as e:
        raise PDFProcessingError(f"PDF 转换失败: {str(e)}") from e
