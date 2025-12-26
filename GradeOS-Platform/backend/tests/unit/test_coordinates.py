"""坐标转换工具函数的单元测试"""

import pytest
from src.utils.coordinates import normalize_coordinates, denormalize_coordinates
from src.models.region import BoundingBox


class TestNormalizeCoordinates:
    """测试 normalize_coordinates 函数"""
    
    def test_basic_conversion(self):
        """测试基本坐标转换"""
        # 归一化坐标 [100, 200, 500, 800] 在 1920x1080 图像上
        result = normalize_coordinates([100, 200, 500, 800], 1920, 1080)
        
        assert result.ymin == 108  # 100 * 1080 / 1000
        assert result.xmin == 384  # 200 * 1920 / 1000
        assert result.ymax == 540  # 500 * 1080 / 1000
        assert result.xmax == 1536  # 800 * 1920 / 1000
    
    def test_full_range(self):
        """测试完整范围 [0, 0, 1000, 1000]"""
        result = normalize_coordinates([0, 0, 1000, 1000], 1920, 1080)
        
        assert result.ymin == 0
        assert result.xmin == 0
        assert result.ymax == 1080
        assert result.xmax == 1920
    
    def test_small_image(self):
        """测试小尺寸图像"""
        result = normalize_coordinates([500, 500, 750, 750], 100, 100)
        
        assert result.ymin == 50
        assert result.xmin == 50
        assert result.ymax == 75
        assert result.xmax == 75
    
    def test_invalid_box_length(self):
        """测试无效的边界框长度"""
        with pytest.raises(ValueError, match="box_1000 必须包含 4 个元素"):
            normalize_coordinates([100, 200, 500], 1920, 1080)
    
    def test_invalid_image_dimensions(self):
        """测试无效的图像尺寸"""
        with pytest.raises(ValueError, match="图像尺寸必须为正数"):
            normalize_coordinates([100, 200, 500, 800], 0, 1080)
        
        with pytest.raises(ValueError, match="图像尺寸必须为正数"):
            normalize_coordinates([100, 200, 500, 800], 1920, -100)
    
    def test_out_of_range_coordinates(self):
        """测试超出范围的归一化坐标"""
        with pytest.raises(ValueError, match="必须在 0-1000 范围内"):
            normalize_coordinates([100, 200, 1500, 800], 1920, 1080)
        
        with pytest.raises(ValueError, match="必须在 0-1000 范围内"):
            normalize_coordinates([-10, 200, 500, 800], 1920, 1080)
    
    def test_boundary_clamping(self):
        """测试边界裁剪（确保坐标不超出图像边界）"""
        # 即使计算结果可能略微超出，也应该被裁剪到图像边界内
        result = normalize_coordinates([0, 0, 1000, 1000], 100, 100)
        
        assert result.ymin >= 0
        assert result.xmin >= 0
        assert result.ymax <= 100
        assert result.xmax <= 100


class TestDenormalizeCoordinates:
    """测试 denormalize_coordinates 函数"""
    
    def test_basic_conversion(self):
        """测试基本坐标转换"""
        box = BoundingBox(ymin=108, xmin=384, ymax=540, xmax=1536)
        result = denormalize_coordinates(box, 1920, 1080)
        
        assert result[0] == 100  # ymin
        assert result[1] == 200  # xmin
        assert result[2] == 500  # ymax
        assert result[3] == 800  # xmax
    
    def test_full_range(self):
        """测试完整范围"""
        box = BoundingBox(ymin=0, xmin=0, ymax=1080, xmax=1920)
        result = denormalize_coordinates(box, 1920, 1080)
        
        assert result == [0, 0, 1000, 1000]
    
    def test_small_image(self):
        """测试小尺寸图像"""
        box = BoundingBox(ymin=50, xmin=50, ymax=75, xmax=75)
        result = denormalize_coordinates(box, 100, 100)
        
        assert result == [500, 500, 750, 750]
    
    def test_invalid_image_dimensions(self):
        """测试无效的图像尺寸"""
        box = BoundingBox(ymin=100, xmin=200, ymax=500, xmax=800)
        
        with pytest.raises(ValueError, match="图像尺寸必须为正数"):
            denormalize_coordinates(box, 0, 1080)
        
        with pytest.raises(ValueError, match="图像尺寸必须为正数"):
            denormalize_coordinates(box, 1920, -100)
    
    def test_boundary_clamping(self):
        """测试边界裁剪（确保归一化坐标在 0-1000 范围内）"""
        box = BoundingBox(ymin=0, xmin=0, ymax=100, xmax=100)
        result = denormalize_coordinates(box, 100, 100)
        
        assert all(0 <= coord <= 1000 for coord in result)


class TestRoundTrip:
    """测试往返转换的一致性"""
    
    def test_normalize_then_denormalize(self):
        """测试归一化后反归一化"""
        original = [100, 200, 500, 800]
        img_width, img_height = 1920, 1080
        
        # 归一化
        box_pixel = normalize_coordinates(original, img_width, img_height)
        
        # 反归一化
        result = denormalize_coordinates(box_pixel, img_width, img_height)
        
        # 由于整数除法可能有精度损失，允许小误差
        for orig, res in zip(original, result):
            assert abs(orig - res) <= 1
    
    def test_denormalize_then_normalize(self):
        """测试反归一化后归一化"""
        original_box = BoundingBox(ymin=108, xmin=384, ymax=540, xmax=1536)
        img_width, img_height = 1920, 1080
        
        # 反归一化
        normalized = denormalize_coordinates(original_box, img_width, img_height)
        
        # 归一化
        result_box = normalize_coordinates(normalized, img_width, img_height)
        
        # 由于整数除法可能有精度损失，允许小误差
        assert abs(original_box.ymin - result_box.ymin) <= 1
        assert abs(original_box.xmin - result_box.xmin) <= 1
        assert abs(original_box.ymax - result_box.ymax) <= 1
        assert abs(original_box.xmax - result_box.xmax) <= 1
