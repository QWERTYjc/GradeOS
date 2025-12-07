#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多模态文件处理器 - Gemini 3 Pro 原生多模态支持
设计原则：
1. 完全依赖 Gemini 3 Pro 的原生多模态能力
2. 不进行任何格式转换（不转 base64、不转图片）
3. 直接传递文件路径给 Gemini SDK
4. 移除所有 Vision API 相关代码
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List
import logging

# 导入多模态数据模型
from .langgraph.multimodal_models import (
    MultiModalFile,
    TextContent,
    create_multimodal_file,
    create_text_content
)

logger = logging.getLogger(__name__)


def process_multimodal_file(file_path: str, prefer_vision: bool = True) -> MultiModalFile:
    """
    多模态文件处理 - Gemini 3 Pro 原生版本
    
    核心原则：
    1. PDF/图片直接传递文件路径给 Gemini SDK（不转换）
    2. 文本文件直接读取内容
    3. 完全移除 Vision API 相关代码
    
    Args:
        file_path: 文件路径
        prefer_vision: 忽略（保留参数以兼容旧代码）
        
    Returns:
        MultiModalFile对象
    """
    path = Path(file_path)
    suffix = path.suffix.lower()
    
    logger.info(f"📄 处理多模态文件: {path.name}, 类型: {suffix}")
    
    # PDF/图片格式 - 直接返回文件路径（Gemini SDK 会处理）
    if suffix in ['.pdf', '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
        return _process_native_multimodal_file(file_path)
    
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
    elif modality_type in ['image', 'pdf']:
        return {
            'type': modality_type,
            'content': content_repr.get('file_path', file_path),
            'format': mm_file['metadata']['file_extension'],
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

def _process_native_multimodal_file(file_path: str) -> MultiModalFile:
    """
    处理 PDF/图片文件 - Gemini 3 Pro 原生模式
    直接返回文件路径，同时生成 base64 编码（用于兼容性）
    """
    try:
        path = Path(file_path)
        suffix = path.suffix.lower()
        file_size = os.path.getsize(file_path)
        
        # 确定模态类型
        if suffix == '.pdf':
            modality_type = 'pdf'
            page_count = _get_pdf_page_count(file_path)
        else:
            modality_type = 'image'
            page_count = 1
        
        # 读取文件并生成 base64（用于 Vision API 兼容）
        base64_data = None
        try:
            import base64
            with open(file_path, 'rb') as f:
                file_bytes = f.read()
                base64_data = base64.b64encode(file_bytes).decode('utf-8')
        except Exception as e:
            logger.warning(f"⚠️  Base64 编码失败: {e}")
        
        # 创建内容表示（包含文件路径和 base64）
        content = {
            'file_path': str(path.absolute()),
            'mime_type': _get_mime_type(suffix),
            'page_count': page_count
        }
        
        # 如果成功生成 base64，添加到内容中
        if base64_data:
            content['base64_data'] = base64_data
        
        logger.info(f"✅ 原生多模态文件处理完成: {path.name}, 类型: {modality_type}, 大小: {file_size} bytes")
        
        return create_multimodal_file(
            file_path=file_path,
            modality_type=modality_type,
            content_representation=content,
            page_count=page_count,
            size_bytes=file_size
        )
    except Exception as e:
        logger.error(f"❌ 文件处理失败: {file_path}, 错误: {e}")
        raise


def _process_text_file(file_path: str) -> MultiModalFile:
    """处理纯文本文件"""
    try:
        path = Path(file_path)

        # 读取文本内容
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()

        content = create_text_content(text=text)

        logger.info(f"✅ 文本文件处理完成: {path.name}, 长度: {len(text)} 字符")

        return create_multimodal_file(
            file_path=file_path,
            modality_type='text',
            content_representation=content,
            size_bytes=len(text.encode('utf-8'))
        )
    except Exception as e:
        logger.error(f"❌ 文本文件处理失败: {file_path}, 错误: {e}")
        raise


def _process_word_file(file_path: str) -> MultiModalFile:
    """处理 Word 文档 - 提取文本"""
    try:
        from docx import Document

        path = Path(file_path)
        doc = Document(file_path)

        # 提取所有段落文本
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        text = '\n\n'.join(paragraphs)

        content = create_text_content(text=text)

        logger.info(f"✅ Word 文档处理完成: {path.name}, 段落数: {len(paragraphs)}")

        return create_multimodal_file(
            file_path=file_path,
            modality_type='document',
            content_representation=content,
            size_bytes=len(text.encode('utf-8'))
        )
    except ImportError:
        logger.error("❌ 请安装 python-docx: pip install python-docx")
        raise
    except Exception as e:
        logger.error(f"❌ Word 文档处理失败: {file_path}, 错误: {e}")
        raise


# ==================== 辅助函数 ====================

def _get_mime_type(suffix: str) -> str:
    """获取文件的 MIME 类型"""
    mime_types = {
        '.pdf': 'application/pdf',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.bmp': 'image/bmp',
        '.webp': 'image/webp'
    }
    return mime_types.get(suffix.lower(), 'application/octet-stream')


def _get_pdf_page_count(file_path: str) -> int:
    """获取 PDF 页数"""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(file_path)
        page_count = len(doc)
        doc.close()
        return page_count
    except ImportError:
        logger.warning("PyMuPDF 未安装，无法获取 PDF 页数")
        return 0
    except Exception as e:
        logger.error(f"获取 PDF 页数失败: {e}")
        return 0

