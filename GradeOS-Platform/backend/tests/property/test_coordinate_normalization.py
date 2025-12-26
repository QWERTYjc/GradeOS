"""坐标归一化数学正确性的属性测试

**功能: ai-grading-agent, 属性 1: 坐标归一化数学正确性**
**验证: 需求 2.3**

属性定义：
对于任意归一化边界框坐标（[0, 1000] 比例）和任意正整数图像尺寸（宽度、高度），
像素坐标转换应当产生满足以下条件的值：
- pixel_y = normalized_y * height / 1000
- pixel_x = normalized_x * width / 1000
- 所有输出坐标为图像边界内的非负整数
"""

import pytest
from hypothesis import given, strategies as st, assume, settings

from src.utils.coordinates import normalize_coordinates, denormalize_coordinates
from src.models.region import BoundingBox


# 策略定义：生成有效的边界框坐标（确保 ymax > ymin, xmax > xmin）
# 使用足够大的差值以确保在小图像上也能产生有效的像素差异
@st.composite
def valid_normalized_box(draw):
    """生成有效的归一化边界框坐标，确保 ymax > ymin 且 xmax > xmin"""
    ymin = draw(st.integers(min_value=0, max_value=900))
    xmin = draw(st.integers(min_value=0, max_value=900))
    # 确保 ymax > ymin 和 xmax > xmin，且差值足够大
    ymax = draw(st.integers(min_value=ymin + 100, max_value=1000))
    xmax = draw(st.integers(min_value=xmin + 100, max_value=1000))
    return [ymin, xmin, ymax, xmax]


# 策略定义：有效的图像尺寸（足够大以产生有效的像素差异）
image_dimension = st.integers(min_value=100, max_value=10000)


class TestCoordinateNormalizationProperty:
    """坐标归一化数学正确性的属性测试"""

    @settings(max_examples=100)
    @given(
        box=valid_normalized_box(),
        width=image_dimension,
        height=image_dimension
    )
    def test_normalize_produces_non_negative_integers(
        self, box: list, width: int, height: int
    ):
        """
        **功能: ai-grading-agent, 属性 1: 坐标归一化数学正确性**
        **验证: 需求 2.3**
        
        验证：所有输出坐标为非负整数
        """
        ymin, xmin, ymax, xmax = box
        result = normalize_coordinates([ymin, xmin, ymax, xmax], width, height)
        
        # 验证所有坐标为非负整数
        assert isinstance(result.ymin, int), "ymin 应为整数"
        assert isinstance(result.xmin, int), "xmin 应为整数"
        assert isinstance(result.ymax, int), "ymax 应为整数"
        assert isinstance(result.xmax, int), "xmax 应为整数"
        
        assert result.ymin >= 0, f"ymin 应为非负数，实际为 {result.ymin}"
        assert result.xmin >= 0, f"xmin 应为非负数，实际为 {result.xmin}"
        assert result.ymax >= 0, f"ymax 应为非负数，实际为 {result.ymax}"
        assert result.xmax >= 0, f"xmax 应为非负数，实际为 {result.xmax}"

    @settings(max_examples=100)
    @given(
        box=valid_normalized_box(),
        width=image_dimension,
        height=image_dimension
    )
    def test_normalize_within_image_bounds(
        self, box: list, width: int, height: int
    ):
        """
        **功能: ai-grading-agent, 属性 1: 坐标归一化数学正确性**
        **验证: 需求 2.3**
        
        验证：所有输出坐标在图像边界内
        """
        ymin, xmin, ymax, xmax = box
        result = normalize_coordinates([ymin, xmin, ymax, xmax], width, height)
        
        # 验证 Y 坐标在图像高度范围内
        assert result.ymin <= height, f"ymin ({result.ymin}) 应 <= height ({height})"
        assert result.ymax <= height, f"ymax ({result.ymax}) 应 <= height ({height})"
        
        # 验证 X 坐标在图像宽度范围内
        assert result.xmin <= width, f"xmin ({result.xmin}) 应 <= width ({width})"
        assert result.xmax <= width, f"xmax ({result.xmax}) 应 <= width ({width})"

    @settings(max_examples=100)
    @given(
        box=valid_normalized_box(),
        width=image_dimension,
        height=image_dimension
    )
    def test_normalize_mathematical_correctness(
        self, box: list, width: int, height: int
    ):
        """
        **功能: ai-grading-agent, 属性 1: 坐标归一化数学正确性**
        **验证: 需求 2.3**
        
        验证：转换公式正确
        - pixel_y = normalized_y * height / 1000
        - pixel_x = normalized_x * width / 1000
        """
        ymin, xmin, ymax, xmax = box
        result = normalize_coordinates([ymin, xmin, ymax, xmax], width, height)
        
        # 计算期望值（使用整数除法，与实现一致）
        expected_ymin = int(ymin * height / 1000)
        expected_xmin = int(xmin * width / 1000)
        expected_ymax = int(ymax * height / 1000)
        expected_xmax = int(xmax * width / 1000)
        
        # 应用边界裁剪（与实现一致）
        expected_ymin = max(0, min(expected_ymin, height))
        expected_xmin = max(0, min(expected_xmin, width))
        expected_ymax = max(0, min(expected_ymax, height))
        expected_xmax = max(0, min(expected_xmax, width))
        
        assert result.ymin == expected_ymin, f"ymin: 期望 {expected_ymin}, 实际 {result.ymin}"
        assert result.xmin == expected_xmin, f"xmin: 期望 {expected_xmin}, 实际 {result.xmin}"
        assert result.ymax == expected_ymax, f"ymax: 期望 {expected_ymax}, 实际 {result.ymax}"
        assert result.xmax == expected_xmax, f"xmax: 期望 {expected_xmax}, 实际 {result.xmax}"

    @settings(max_examples=100)
    @given(
        box=valid_normalized_box(),
        width=image_dimension,
        height=image_dimension
    )
    def test_normalize_preserves_relative_ordering(
        self, box: list, width: int, height: int
    ):
        """
        **功能: ai-grading-agent, 属性 1: 坐标归一化数学正确性**
        **验证: 需求 2.3**
        
        验证：归一化保持相对顺序
        由于输入保证 ymin < ymax 和 xmin < xmax，输出也应保持此顺序
        """
        ymin, xmin, ymax, xmax = box
        result = normalize_coordinates([ymin, xmin, ymax, xmax], width, height)
        
        # 输入中 ymin < ymax，输出中也应保持（或相等，当差值很小时）
        assert result.ymin <= result.ymax, \
            f"ymin ({result.ymin}) 应 <= ymax ({result.ymax})"
        
        # 输入中 xmin < xmax，输出中也应保持（或相等，当差值很小时）
        assert result.xmin <= result.xmax, \
            f"xmin ({result.xmin}) 应 <= xmax ({result.xmax})"

    @settings(max_examples=100)
    @given(
        width=image_dimension,
        height=image_dimension
    )
    def test_normalize_boundary_values(self, width: int, height: int):
        """
        **功能: ai-grading-agent, 属性 1: 坐标归一化数学正确性**
        **验证: 需求 2.3**
        
        验证：边界值 [0, 0, 1000, 1000] 映射到完整图像
        """
        result = normalize_coordinates([0, 0, 1000, 1000], width, height)
        
        assert result.ymin == 0, f"ymin 应为 0，实际为 {result.ymin}"
        assert result.xmin == 0, f"xmin 应为 0，实际为 {result.xmin}"
        assert result.ymax == height, f"ymax 应为 {height}，实际为 {result.ymax}"
        assert result.xmax == width, f"xmax 应为 {width}，实际为 {result.xmax}"

    @settings(max_examples=100)
    @given(
        width=image_dimension,
        height=image_dimension
    )
    def test_normalize_zero_origin(self, width: int, height: int):
        """
        **功能: ai-grading-agent, 属性 1: 坐标归一化数学正确性**
        **验证: 需求 2.3**
        
        验证：归一化坐标 0 映射到像素坐标 0
        """
        # 使用有效的边界框 [0, 0, 500, 500]
        result = normalize_coordinates([0, 0, 500, 500], width, height)
        
        assert result.ymin == 0, f"归一化 0 应映射到像素 0，实际 ymin={result.ymin}"
        assert result.xmin == 0, f"归一化 0 应映射到像素 0，实际 xmin={result.xmin}"


class TestDenormalizeCoordinatesProperty:
    """反归一化坐标的属性测试"""

    @st.composite
    def valid_pixel_box(draw, width_range=(100, 5000), height_range=(100, 5000)):
        """生成有效的像素边界框"""
        width = draw(st.integers(min_value=width_range[0], max_value=width_range[1]))
        height = draw(st.integers(min_value=height_range[0], max_value=height_range[1]))
        
        # 生成有效的像素坐标，确保 ymax > ymin 和 xmax > xmin
        ymin = draw(st.integers(min_value=0, max_value=height - 10))
        xmin = draw(st.integers(min_value=0, max_value=width - 10))
        ymax = draw(st.integers(min_value=ymin + 1, max_value=height))
        xmax = draw(st.integers(min_value=xmin + 1, max_value=width))
        
        return BoundingBox(ymin=ymin, xmin=xmin, ymax=ymax, xmax=xmax), width, height

    @settings(max_examples=100)
    @given(data=st.data())
    def test_denormalize_produces_valid_range(self, data):
        """
        **功能: ai-grading-agent, 属性 1: 坐标归一化数学正确性**
        **验证: 需求 2.3**
        
        验证：反归一化输出在 [0, 1000] 范围内
        """
        width = data.draw(st.integers(min_value=100, max_value=5000))
        height = data.draw(st.integers(min_value=100, max_value=5000))
        
        # 生成有效的像素坐标
        ymin = data.draw(st.integers(min_value=0, max_value=height - 10))
        xmin = data.draw(st.integers(min_value=0, max_value=width - 10))
        ymax = data.draw(st.integers(min_value=ymin + 1, max_value=height))
        xmax = data.draw(st.integers(min_value=xmin + 1, max_value=width))
        
        box = BoundingBox(ymin=ymin, xmin=xmin, ymax=ymax, xmax=xmax)
        result = denormalize_coordinates(box, width, height)
        
        # 验证所有归一化坐标在 [0, 1000] 范围内
        for i, coord in enumerate(result):
            assert 0 <= coord <= 1000, \
                f"归一化坐标 {i} 应在 [0, 1000] 范围内，实际为 {coord}"


class TestRoundTripProperty:
    """往返转换的属性测试"""

    @settings(max_examples=100)
    @given(
        ymin=st.integers(min_value=0, max_value=400),
        xmin=st.integers(min_value=0, max_value=400),
        width=st.integers(min_value=500, max_value=5000),
        height=st.integers(min_value=500, max_value=5000)
    )
    def test_round_trip_approximate_identity(
        self, ymin: int, xmin: int, width: int, height: int
    ):
        """
        **功能: ai-grading-agent, 属性 1: 坐标归一化数学正确性**
        **验证: 需求 2.3**
        
        验证：归一化后反归一化近似恢复原值（允许整数除法误差）
        
        注意：由于整数除法的精度损失，往返转换可能有误差。
        误差大小与图像尺寸成反比：图像越大，误差越小。
        对于 500+ 像素的图像，误差通常在 ±3 以内。
        """
        # 确保 ymax > ymin 和 xmax > xmin，使用较大的差值
        ymax = ymin + 200
        xmax = xmin + 200
        
        original = [ymin, xmin, ymax, xmax]
        
        # 归一化
        box_pixel = normalize_coordinates(original, width, height)
        
        # 反归一化
        result = denormalize_coordinates(box_pixel, width, height)
        
        # 由于整数除法可能有精度损失，允许小误差
        # 误差公式：最大误差 ≈ 1000 / min(width, height)
        max_error = max(3, 1000 // min(width, height) + 1)
        
        for orig, res in zip(original, result):
            assert abs(orig - res) <= max_error, \
                f"往返转换误差过大: 原始 {orig}, 结果 {res}, 允许误差 {max_error}"
