"""
感知哈希计算工具

提供图像和文本的哈希计算功能，用于语义缓存的键生成。
"""

import hashlib
from io import BytesIO
from typing import Union

import imagehash
from PIL import Image


def compute_image_hash(image_data: bytes) -> str:
    """
    计算图像的感知哈希值
    
    使用 pHash (Perceptual Hash) 算法计算图像的感知哈希。
    相似的图像会产生相同或相近的哈希值。
    
    Args:
        image_data: 图像的字节数据
        
    Returns:
        16 位十六进制字符串表示的感知哈希值
        
    Raises:
        ValueError: 如果图像数据无效或无法解析
        
    验证：需求 6.1
    """
    try:
        # 从字节数据加载图像
        image = Image.open(BytesIO(image_data))
        
        # 计算感知哈希 (pHash)
        # pHash 对图像的轻微变化（如压缩、缩放）具有鲁棒性
        phash = imagehash.phash(image)
        
        # 返回十六进制字符串
        return str(phash)
        
    except Exception as e:
        raise ValueError(f"无法计算图像哈希: {str(e)}") from e


def compute_rubric_hash(rubric_text: str) -> str:
    """
    计算评分细则的哈希值
    
    使用 SHA-256 算法计算评分细则文本的哈希值。
    相同的评分细则文本会产生相同的哈希值。
    
    Args:
        rubric_text: 评分细则的文本内容
        
    Returns:
        64 位十六进制字符串表示的 SHA-256 哈希值
        
    验证：需求 6.1
    """
    # 使用 SHA-256 计算文本哈希
    # 对评分细则使用确定性哈希（而非感知哈希）
    hash_obj = hashlib.sha256(rubric_text.encode('utf-8'))
    return hash_obj.hexdigest()


def compute_cache_key(rubric_text: str, image_data: bytes) -> str:
    """
    生成缓存键
    
    组合评分细则哈希和图像哈希生成唯一的缓存键。
    
    Args:
        rubric_text: 评分细则文本
        image_data: 图像字节数据
        
    Returns:
        格式为 "grade_cache:v1:{rubric_hash}:{image_hash}" 的缓存键
        
    验证：需求 6.1, 6.2
    """
    rubric_hash = compute_rubric_hash(rubric_text)
    image_hash = compute_image_hash(image_data)
    
    # 使用版本前缀以支持未来的缓存格式变更
    return f"grade_cache:v1:{rubric_hash}:{image_hash}"
