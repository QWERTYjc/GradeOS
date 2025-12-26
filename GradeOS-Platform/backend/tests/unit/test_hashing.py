"""哈希计算功能的单元测试"""

import pytest
from PIL import Image
from io import BytesIO

from src.utils.hashing import (
    compute_image_hash,
    compute_rubric_hash,
    compute_cache_key,
)


def create_test_image(width: int = 100, height: int = 100, color: tuple = (255, 0, 0), pattern: str = "solid") -> bytes:
    """创建测试图像"""
    img = Image.new('RGB', (width, height), color)
    
    # 添加图案以确保不同图像有不同的哈希
    if pattern == "gradient":
        pixels = img.load()
        for i in range(width):
            for j in range(height):
                pixels[i, j] = (i % 256, j % 256, (i + j) % 256)
    elif pattern == "checkerboard":
        pixels = img.load()
        for i in range(width):
            for j in range(height):
                if (i // 10 + j // 10) % 2 == 0:
                    pixels[i, j] = color
                else:
                    pixels[i, j] = (255 - color[0], 255 - color[1], 255 - color[2])
    
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()


class TestImageHash:
    """测试图像哈希计算"""
    
    def test_compute_image_hash_returns_string(self):
        """测试图像哈希返回字符串"""
        image_data = create_test_image()
        hash_value = compute_image_hash(image_data)
        
        assert isinstance(hash_value, str)
        assert len(hash_value) == 16  # pHash 返回 16 位十六进制字符串
    
    def test_same_image_produces_same_hash(self):
        """测试相同图像产生相同哈希"""
        image_data = create_test_image(100, 100, (255, 0, 0))
        
        hash1 = compute_image_hash(image_data)
        hash2 = compute_image_hash(image_data)
        
        assert hash1 == hash2
    
    def test_different_images_produce_different_hashes(self):
        """测试不同图像产生不同哈希"""
        image1 = create_test_image(100, 100, (255, 0, 0), pattern="gradient")
        image2 = create_test_image(100, 100, (0, 255, 0), pattern="checkerboard")
        
        hash1 = compute_image_hash(image1)
        hash2 = compute_image_hash(image2)
        
        assert hash1 != hash2
    
    def test_invalid_image_data_raises_error(self):
        """测试无效图像数据抛出错误"""
        invalid_data = b"not an image"
        
        with pytest.raises(ValueError, match="无法计算图像哈希"):
            compute_image_hash(invalid_data)


class TestRubricHash:
    """测试评分细则哈希计算"""
    
    def test_compute_rubric_hash_returns_string(self):
        """测试评分细则哈希返回字符串"""
        rubric_text = "这是一个评分细则"
        hash_value = compute_rubric_hash(rubric_text)
        
        assert isinstance(hash_value, str)
        assert len(hash_value) == 64  # SHA-256 返回 64 位十六进制字符串
    
    def test_same_rubric_produces_same_hash(self):
        """测试相同评分细则产生相同哈希"""
        rubric_text = "这是一个评分细则"
        
        hash1 = compute_rubric_hash(rubric_text)
        hash2 = compute_rubric_hash(rubric_text)
        
        assert hash1 == hash2
    
    def test_different_rubrics_produce_different_hashes(self):
        """测试不同评分细则产生不同哈希"""
        rubric1 = "评分细则 1"
        rubric2 = "评分细则 2"
        
        hash1 = compute_rubric_hash(rubric1)
        hash2 = compute_rubric_hash(rubric2)
        
        assert hash1 != hash2
    
    def test_empty_rubric_produces_valid_hash(self):
        """测试空评分细则产生有效哈希"""
        rubric_text = ""
        hash_value = compute_rubric_hash(rubric_text)
        
        assert isinstance(hash_value, str)
        assert len(hash_value) == 64


class TestCacheKey:
    """测试缓存键生成"""
    
    def test_compute_cache_key_format(self):
        """测试缓存键格式正确"""
        rubric_text = "评分细则"
        image_data = create_test_image()
        
        cache_key = compute_cache_key(rubric_text, image_data)
        
        assert cache_key.startswith("grade_cache:v1:")
        parts = cache_key.split(":")
        assert len(parts) == 4
        assert parts[0] == "grade_cache"
        assert parts[1] == "v1"
        assert len(parts[2]) == 64  # rubric hash
        assert len(parts[3]) == 16  # image hash
    
    def test_same_inputs_produce_same_cache_key(self):
        """测试相同输入产生相同缓存键"""
        rubric_text = "评分细则"
        image_data = create_test_image()
        
        key1 = compute_cache_key(rubric_text, image_data)
        key2 = compute_cache_key(rubric_text, image_data)
        
        assert key1 == key2
    
    def test_different_rubrics_produce_different_keys(self):
        """测试不同评分细则产生不同缓存键"""
        image_data = create_test_image()
        
        key1 = compute_cache_key("评分细则 1", image_data)
        key2 = compute_cache_key("评分细则 2", image_data)
        
        assert key1 != key2
    
    def test_different_images_produce_different_keys(self):
        """测试不同图像产生不同缓存键"""
        rubric_text = "评分细则"
        
        key1 = compute_cache_key(rubric_text, create_test_image(100, 100, (255, 0, 0), pattern="gradient"))
        key2 = compute_cache_key(rubric_text, create_test_image(100, 100, (0, 255, 0), pattern="checkerboard"))
        
        assert key1 != key2
