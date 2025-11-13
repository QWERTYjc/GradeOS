#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件处理器 - 支持图片、PDF、Word 等多种格式
"""

import os
from pathlib import Path
from typing import Optional
import base64


def process_file(file_path: str) -> dict:
    """
    处理上传的文件，提取文本或图片内容
    
    Args:
        file_path: 文件路径
        
    Returns:
        {
            'type': 'text' | 'image',
            'content': str (文本内容或base64编码的图片),
            'format': str (文件格式),
            'original_path': str
        }
    """
    path = Path(file_path)
    suffix = path.suffix.lower()
    
    # 图片格式
    if suffix in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
        return {
            'type': 'image',
            'content': _read_image_as_base64(file_path),
            'format': suffix,
            'original_path': file_path
        }
    
    # PDF 格式
    elif suffix == '.pdf':
        return {
            'type': 'pdf',
            'content': _read_pdf_as_text(file_path),
            'format': suffix,
            'original_path': file_path
        }
    
    # Word 格式
    elif suffix in ['.docx', '.doc']:
        return {
            'type': 'document',
            'content': _read_word_as_text(file_path),
            'format': suffix,
            'original_path': file_path
        }
    
    # 文本格式
    elif suffix in ['.txt', '.md', '.json', '.csv']:
        return {
            'type': 'text',
            'content': _read_text_file(file_path),
            'format': suffix,
            'original_path': file_path
        }
    
    else:
        raise ValueError(f"不支持的文件格式: {suffix}")


def _read_image_as_base64(file_path: str) -> str:
    """读取图片并转换为 base64"""
    with open(file_path, 'rb') as f:
        image_data = f.read()
        return base64.b64encode(image_data).decode('utf-8')


def _read_pdf_as_text(file_path: str) -> str:
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
                return f"[扫描版PDF，需要OCR: {file_path}]"

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

