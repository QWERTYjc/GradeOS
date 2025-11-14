#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多模态文件处理器 - 真正的多模态支持
设计原则：
1. 不进行强制OCR转换
2. 保留原始文件模态
3. 支持LLM Vision能力
4. 用户明确要求时才提示使用文本版本
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List
import base64
import logging

# 导入多模态数据模型
sys.path.insert(0, str(Path(__file__).parent))
from functions.langgraph.multimodal_models import (
    MultiModalFile,
    TextContent,
    ImageContent,
    PDFTextContent,
    PDFImageContent,
    DocumentContent,
    create_multimodal_file,
    create_text_content,
    create_image_content
)

logger = logging.getLogger(__name__)


def process_multimodal_file(file_path: str, prefer_vision: bool = False) -> MultiModalFile:
    """
    多模态文件处理 - 新版本
    
    核心原则：
    1. 不进行OCR转换
    2. 图片保持图片格式（base64）
    3. PDF根据情况处理（文本版提取文本，扫描版保持图片）
    4. 文本文件直接读取
    
    Args:
        file_path: 文件路径
        prefer_vision: 是否优先使用Vision模式（即使PDF可以提取文本）
        
    Returns:
        MultiModalFile对象
    """
    path = Path(file_path)
    suffix = path.suffix.lower()
    
    logger.info(f"处理多模态文件: {path.name}, 类型: {suffix}")
    
    # 图片格式 - 直接转base64，使用Vision API
    if suffix in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
        return _process_image_file(file_path)
    
    # PDF格式 - 根据内容和用户偏好决定
    elif suffix == '.pdf':
        return _process_pdf_file(file_path, prefer_vision)
    
    # Word文档 - 提取文本
    elif suffix in ['.docx', '.doc']:
        return _process_word_file(file_path)
    
    # 文本格式 - 直接读取
    elif suffix in ['.txt', '.md', '.json', '.csv']:
        return _process_text_file(file_path)
    
    else:
        raise ValueError(f"不支持的文件格式: {suffix}")


def process_file(file_path: str) -> dict:
    """
    旧版本兼容接口 - 保留向后兼容性
    内部调用新的多模态处理逻辑
    """
    mm_file = process_multimodal_file(file_path)
    
    # 转换为旧格式
    modality_type = mm_file['modality_type']
    content_repr = mm_file['content_representation']
    
    if modality_type == 'text':
        return {
            'type': 'text',
            'content': content_repr['text'],
            'format': mm_file['metadata']['file_extension'],
            'original_path': file_path
        }
    elif modality_type == 'image':
        return {
            'type': 'image',
            'content': content_repr['base64_data'],
            'format': mm_file['metadata']['file_extension'],
            'original_path': file_path
        }
    elif modality_type == 'pdf_text':
        return {
            'type': 'pdf',
            'content': content_repr['text'],
            'format': '.pdf',
            'original_path': file_path
        }
    elif modality_type == 'pdf_image':
        # PDF图片模式 - 返回第一页
        return {
            'type': 'image',
            'content': content_repr['pages'][0]['base64_data'] if content_repr['pages'] else '',
            'format': '.pdf',
            'original_path': file_path
        }
    elif modality_type == 'document':
        return {
            'type': 'document',
            'content': content_repr['text'],
            'format': mm_file['metadata']['file_extension'],
            'original_path': file_path
        }
    else:
        return {
            'type': 'text',
            'content': '',
            'format': mm_file['metadata']['file_extension'],
            'original_path': file_path
        }


# ==================== 多模态文件处理核心函数 ====================

def _process_image_file(file_path: str) -> MultiModalFile:
    """处理图片文件 - 转换为base64供Vision API使用"""
    try:
        path = Path(file_path)
        mime_type = _get_image_mime_type(path.suffix)
        
        # 读取图片为base64
        with open(file_path, 'rb') as f:
            image_data = f.read()
            base64_data = base64.b64encode(image_data).decode('utf-8')
        
        # 获取图片尺寸（可选）
        width, height = _get_image_dimensions(file_path)
        
        # 创建图片内容对象
        content = create_image_content(
            base64_data=base64_data,
            mime_type=mime_type,
            width=width,
            height=height
        )
        
        logger.info(f"✅ 图片文件处理成功: {path.name}, 大小: {len(image_data)} bytes")
        
        return create_multimodal_file(
            file_path=file_path,
            modality_type='image',
            content_representation=content,
            mime_type=mime_type,
            size_bytes=len(image_data)
        )
    except Exception as e:
        logger.error(f"❌ 图片文件处理失败: {file_path}, 错误: {e}")
        raise


def _process_pdf_file(file_path: str, prefer_vision: bool = False) -> MultiModalFile:
    """
    处理PDF文件
    策略：
    1. 尝试提取文本
    2. 如果文本太少（扫描版），返回PDF图片模式
    3. 如果用户偏好Vision，直接返回PDF图片模式
    """
    try:
        path = Path(file_path)
        
        # 如果用户偏好Vision模式，直接转图片
        if prefer_vision:
            logger.info(f"用户偏好Vision模式，PDF转图片: {path.name}")
            return _process_pdf_as_images(file_path)
        
        # 尝试提取文本
        extracted_text = _extract_pdf_text(file_path)
        
        # 判断是否是扫描版（提取的文本太少）
        if len(extracted_text.strip()) < 50:
            logger.warning(f"⚠️ 检测到扫描版PDF或文本内容过少: {path.name}")
            logger.info("提示：建议使用文本版PDF或.txt文件以获得更好的批改效果")
            # 返回PDF图片模式
            return _process_pdf_as_images(file_path)
        
        # 文本PDF - 返回文本内容
        logger.info(f"✅ PDF文本提取成功: {path.name}, 长度: {len(extracted_text)} 字符")
        
        content = PDFTextContent(
            text=extracted_text,
            page_count=_get_pdf_page_count(file_path),
            extraction_method='PyPDF2'
        )
        
        return create_multimodal_file(
            file_path=file_path,
            modality_type='pdf_text',
            content_representation=content,
            page_count=content['page_count']
        )
    except Exception as e:
        logger.error(f"❌ PDF文件处理失败: {file_path}, 错误: {e}")
        # 失败时尝试转图片
        logger.info("尝试将PDF转换为图片模式...")
        return _process_pdf_as_images(file_path)


def _process_pdf_as_images(file_path: str) -> MultiModalFile:
    """将PDF转换为图片（每页一张）供Vision API使用"""
    try:
        # 注意：这需要pdf2image库
        # 如果未安装，返回提示信息
        try:
            from pdf2image import convert_from_path  # type: ignore
            import io
            from PIL import Image
        except ImportError:
            logger.warning("pdf2image未安装，无法将PDF转换为图片")
            logger.info("建议：pip install pdf2image poppler-utils")
            # 返回空内容但标记为pdf_image类型
            content = PDFImageContent(
                pages=[],
                page_count=0,
                conversion_method='未安装pdf2image'
            )
            return create_multimodal_file(
                file_path=file_path,
                modality_type='pdf_image',
                content_representation=content,
                warning='需要安装pdf2image库'
            )
        
        # 转换PDF为图片
        images = convert_from_path(file_path)
        
        # 将每页转换为base64
        page_contents = []
        for i, img in enumerate(images):
            # 转换PIL Image为base64
            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            img_bytes = buffered.getvalue()
            base64_data = base64.b64encode(img_bytes).decode('utf-8')
            
            page_content = create_image_content(
                base64_data=base64_data,
                mime_type='image/png',
                width=img.width,
                height=img.height
            )
            page_contents.append(page_content)
        
        logger.info(f"✅ PDF转图片成功: {Path(file_path).name}, 页数: {len(images)}")
        
        content = PDFImageContent(
            pages=page_contents,
            page_count=len(images),
            conversion_method='pdf2image'
        )
        
        return create_multimodal_file(
            file_path=file_path,
            modality_type='pdf_image',
            content_representation=content,
            page_count=len(images)
        )
    except Exception as e:
        logger.error(f"❌ PDF转图片失败: {file_path}, 错误: {e}")
        raise


def _process_word_file(file_path: str) -> MultiModalFile:
    """处理Word文档 - 提取文本"""
    try:
        path = Path(file_path)
        
        try:
            import docx
        except ImportError:
            logger.warning("python-docx未安装")
            logger.info("建议：pip install python-docx")
            raise ImportError("需要安装python-docx库")
        
        # 读取Word文档
        doc = docx.Document(file_path)
        text = "\n".join([para.text for para in doc.paragraphs])
        
        logger.info(f"✅ Word文档处理成功: {path.name}, 长度: {len(text)} 字符")
        
        content = DocumentContent(
            text=text,
            has_images=False,  # TODO: 检测是否包含图片
            extraction_method='python-docx'
        )
        
        return create_multimodal_file(
            file_path=file_path,
            modality_type='document',
            content_representation=content
        )
    except Exception as e:
        logger.error(f"❌ Word文档处理失败: {file_path}, 错误: {e}")
        raise


def _process_text_file(file_path: str) -> MultiModalFile:
    """处理文本文件 - 直接读取"""
    try:
        path = Path(file_path)
        
        # 读取文本内容
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
        
        logger.info(f"✅ 文本文件处理成功: {path.name}, 长度: {len(text)} 字符")
        
        content = create_text_content(
            text=text,
            encoding='utf-8'
        )
        
        return create_multimodal_file(
            file_path=file_path,
            modality_type='text',
            content_representation=content
        )
    except Exception as e:
        logger.error(f"❌ 文本文件处理失败: {file_path}, 错误: {e}")
        raise


# ==================== 辅助工具函数 ====================

def _get_image_mime_type(suffix: str) -> str:
    """根据文件扩展名获取MIME类型"""
    mime_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.bmp': 'image/bmp',
        '.webp': 'image/webp'
    }
    return mime_types.get(suffix.lower(), 'image/jpeg')


def _get_image_dimensions(file_path: str) -> tuple:
    """获取图片尺寸"""
    try:
        from PIL import Image
        with Image.open(file_path) as img:
            return img.width, img.height
    except Exception:
        return None, None


def _extract_pdf_text(file_path: str) -> str:
    """提取PDF文本（不强制，如果失败返回空字符串）"""
    try:
        import PyPDF2
        with open(file_path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            text = ""
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text.strip()
    except Exception as e:
        logger.warning(f"PDF文本提取失败: {e}")
        return ""


def _get_pdf_page_count(file_path: str) -> int:
    """获取PDF页数"""
    try:
        import PyPDF2
        with open(file_path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            return len(pdf_reader.pages)
    except Exception:
        return 0


# ==================== 旧版本兼容函数（保留） ====================

def _read_image_as_base64(file_path: str) -> str:
    """读取图片并转换为 base64 - 旧版本函数（保留兼容）"""
    with open(file_path, 'rb') as f:
        image_data = f.read()
        return base64.b64encode(image_data).decode('utf-8')
    """
    读取 PDF 文件内容

    注意：如果 PDF 是扫描版（图片），PyPDF2 无法提取文字
    这种情况下需要使用 OCR 或 LLM 视觉能力
    """
    try:
        import PyPDF2
        with open(file_path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            text = ""
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"

            # 如果提取的文字太少（可能是扫描版PDF），返回特殊标记
            if len(text.strip()) < 10:
                print("⚠️ 检测到扫描版PDF，无法提取文字内容")
                print("   建议：请使用文本版PDF或将内容复制到.txt文件")
                return f"[扫描版PDF，无法提取文字。建议使用文本版PDF或.txt文件]"

            return text.strip()
    except ImportError:
        # 如果没有 PyPDF2，返回文件路径
        print("⚠️ PyPDF2 未安装，无法解析 PDF 文件")
        print("   请运行: pip install PyPDF2")
        return f"[PDF文件（需要安装PyPDF2）: {file_path}]"
    except Exception as e:
        print(f"❌ PDF解析失败: {e}")
        return f"[PDF解析失败: {str(e)}]"


def _read_word_as_text(file_path: str) -> str:
    """读取 Word 文件内容"""
    try:
        import docx
        doc = docx.Document(file_path)
        text = "\n".join([para.text for para in doc.paragraphs])
        return text.strip()
    except ImportError:
        return f"[Word文件: {file_path}]"
    except Exception as e:
        return f"[Word解析失败: {str(e)}]"


def _read_text_file(file_path: str) -> str:
    """读取文本文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def extract_text_from_image_with_llm(image_base64: str, llm_client) -> str:
    """
    使用 LLM 从图片中提取文本（OCR）

    Args:
        image_base64: base64 编码的图片
        llm_client: LLM 客户端

    Returns:
        提取的文本内容
    """
    try:
        # 使用 LLM 的视觉能力提取文本
        prompt = """请仔细查看这张图片，提取其中的所有文字内容。

要求：
1. 保持原有的格式和结构
2. 如果是题目，请保留题号
3. 如果是答案，请保留答案标记
4. 如果是评分标准，请保留评分点和分值
5. 不要添加任何解释，只输出提取的文字

请直接输出提取的文字内容："""

        # 构建消息 - OpenRouter 支持视觉输入
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        }
                    }
                ]
            }
        ]

        response = llm_client.chat(messages=messages, temperature=0.3, max_tokens=4000)

        return response.strip()
    except Exception as e:
        print(f"❌ 图片文字提取失败: {e}")
        return f"[图片文字提取失败: {str(e)}]"
