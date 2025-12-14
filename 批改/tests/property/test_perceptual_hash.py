"""感知哈希确定性的属性测试

**功能: ai-grading-agent, 属性 9: 感知哈希确定性**
**验证: 需求 6.1**

属性定义：
对于任意图像，多次计算感知哈希应当产生相同的哈希值。
对于任意两张视觉上相同的图像（相同内容，可能不同编码），哈希值应当相等。
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from PIL import Image
from io import BytesIO
import imagehash

from src.utils.hashing import compute_image_hash, compute_rubric_hash


def hamming_distance(hash1: str, hash2: str) -> int:
    """
    计算两个十六进制哈希字符串之间的汉明距离
    
    Args:
        hash1: 第一个哈希值（十六进制字符串）
        hash2: 第二个哈希值（十六进制字符串）
        
    Returns:
        汉明距离（不同位的数量）
    """
    # 将十六进制字符串转换为整数
    int1 = int(hash1, 16)
    int2 = int(hash2, 16)
    
    # 计算 XOR 并统计 1 的数量
    xor_result = int1 ^ int2
    return bin(xor_result).count('1')


# 策略定义：生成有效的图像尺寸
image_dimension = st.integers(min_value=32, max_value=500)

# 策略定义：生成 RGB 颜色值
rgb_color = st.tuples(
    st.integers(min_value=0, max_value=255),
    st.integers(min_value=0, max_value=255),
    st.integers(min_value=0, max_value=255)
)


@st.composite
def random_image_data(draw, min_size=32, max_size=200):
    """
    生成随机图像数据
    
    Args:
        draw: Hypothesis draw 函数
        min_size: 最小图像尺寸
        max_size: 最大图像尺寸
        
    Returns:
        PNG 格式的图像字节数据
    """
    width = draw(st.integers(min_value=min_size, max_value=max_size))
    height = draw(st.integers(min_value=min_size, max_value=max_size))
    
    # 创建图像
    img = Image.new('RGB', (width, height))
    pixels = img.load()
    
    # 使用确定性的图案填充（基于坐标）
    pattern_type = draw(st.sampled_from(['solid', 'gradient', 'checkerboard']))
    base_color = draw(rgb_color)
    
    if pattern_type == 'solid':
        for i in range(width):
            for j in range(height):
                pixels[i, j] = base_color
    elif pattern_type == 'gradient':
        for i in range(width):
            for j in range(height):
                r = (base_color[0] + i) % 256
                g = (base_color[1] + j) % 256
                b = (base_color[2] + i + j) % 256
                pixels[i, j] = (r, g, b)
    else:  # checkerboard
        for i in range(width):
            for j in range(height):
                if (i // 8 + j // 8) % 2 == 0:
                    pixels[i, j] = base_color
                else:
                    pixels[i, j] = (255 - base_color[0], 255 - base_color[1], 255 - base_color[2])
    
    # 转换为字节
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()


def create_image_with_pattern(width: int, height: int, pattern_seed: int) -> bytes:
    """
    使用确定性图案创建图像
    
    Args:
        width: 图像宽度
        height: 图像高度
        pattern_seed: 图案种子值
        
    Returns:
        PNG 格式的图像字节数据
    """
    img = Image.new('RGB', (width, height))
    pixels = img.load()
    
    for i in range(width):
        for j in range(height):
            r = (pattern_seed + i * 3) % 256
            g = (pattern_seed + j * 5) % 256
            b = (pattern_seed + i + j) % 256
            pixels[i, j] = (r, g, b)
    
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()


class TestPerceptualHashDeterminism:
    """感知哈希确定性的属性测试"""

    @settings(max_examples=100, deadline=None)
    @given(image_data=random_image_data())
    def test_same_image_produces_same_hash(self, image_data: bytes):
        """
        **功能: ai-grading-agent, 属性 9: 感知哈希确定性**
        **验证: 需求 6.1**
        
        验证：对于任意图像，多次计算感知哈希应当产生相同的哈希值
        """
        # 多次计算哈希
        hash1 = compute_image_hash(image_data)
        hash2 = compute_image_hash(image_data)
        hash3 = compute_image_hash(image_data)
        
        # 验证所有哈希值相同
        assert hash1 == hash2, f"第一次和第二次哈希不同: {hash1} != {hash2}"
        assert hash2 == hash3, f"第二次和第三次哈希不同: {hash2} != {hash3}"
        assert hash1 == hash3, f"第一次和第三次哈希不同: {hash1} != {hash3}"

    @settings(max_examples=100, deadline=None)
    @given(
        width=st.integers(min_value=64, max_value=200),
        height=st.integers(min_value=64, max_value=200),
        pattern_seed=st.integers(min_value=0, max_value=255)
    )
    def test_same_content_same_lossless_encoding_same_hash(
        self, width: int, height: int, pattern_seed: int
    ):
        """
        **功能: ai-grading-agent, 属性 9: 感知哈希确定性**
        **验证: 需求 6.1**
        
        验证：对于视觉上相同的图像（相同内容，相同无损编码格式），哈希值应当相等
        
        测试方法：创建相同内容的图像，分别保存为两个独立的 PNG 文件，
        验证感知哈希完全相同。
        
        注意：此测试仅验证无损格式（PNG）的确定性。
        JPEG 等有损压缩格式会引入不可预测的差异，不在此测试范围内。
        """
        # 创建原始图像
        img = Image.new('RGB', (width, height))
        pixels = img.load()
        
        for i in range(width):
            for j in range(height):
                r = (pattern_seed + i * 3) % 256
                g = (pattern_seed + j * 5) % 256
                b = (pattern_seed + i + j) % 256
                pixels[i, j] = (r, g, b)
        
        # 保存为第一个 PNG
        png_buffer1 = BytesIO()
        img.save(png_buffer1, format='PNG')
        png_data1 = png_buffer1.getvalue()
        
        # 保存为第二个 PNG（独立的保存操作）
        png_buffer2 = BytesIO()
        img.save(png_buffer2, format='PNG')
        png_data2 = png_buffer2.getvalue()
        
        # 计算哈希
        hash1 = compute_image_hash(png_data1)
        hash2 = compute_image_hash(png_data2)
        
        # 相同内容的无损编码应产生相同的哈希
        assert hash1 == hash2, \
            f"相同内容的 PNG 编码产生不同哈希: {hash1} != {hash2}"

    @settings(max_examples=100, deadline=None)
    @given(
        width=st.integers(min_value=32, max_value=200),
        height=st.integers(min_value=32, max_value=200),
        pattern_seed=st.integers(min_value=0, max_value=255)
    )
    def test_resaved_image_same_hash(
        self, width: int, height: int, pattern_seed: int
    ):
        """
        **功能: ai-grading-agent, 属性 9: 感知哈希确定性**
        **验证: 需求 6.1**
        
        验证：重新保存的图像（相同格式）应产生相同的哈希值
        """
        # 创建原始图像
        original_data = create_image_with_pattern(width, height, pattern_seed)
        
        # 加载并重新保存（使用相同的 PNG 格式）
        img = Image.open(BytesIO(original_data))
        resaved_buffer = BytesIO()
        img.save(resaved_buffer, format='PNG')
        resaved_data = resaved_buffer.getvalue()
        
        # 计算哈希
        original_hash = compute_image_hash(original_data)
        resaved_hash = compute_image_hash(resaved_data)
        
        # 验证哈希相同
        assert original_hash == resaved_hash, \
            f"重新保存后哈希不同: 原始={original_hash}, 重新保存={resaved_hash}"

    @settings(max_examples=100, deadline=None)
    @given(image_data=random_image_data())
    def test_hash_format_valid(self, image_data: bytes):
        """
        **功能: ai-grading-agent, 属性 9: 感知哈希确定性**
        **验证: 需求 6.1**
        
        验证：哈希值格式正确（16 位十六进制字符串）
        """
        hash_value = compute_image_hash(image_data)
        
        # 验证是字符串
        assert isinstance(hash_value, str), f"哈希值应为字符串，实际为 {type(hash_value)}"
        
        # 验证长度为 16
        assert len(hash_value) == 16, f"哈希值长度应为 16，实际为 {len(hash_value)}"
        
        # 验证是有效的十六进制字符串
        try:
            int(hash_value, 16)
        except ValueError:
            pytest.fail(f"哈希值不是有效的十六进制字符串: {hash_value}")


class TestRubricHashDeterminism:
    """评分细则哈希确定性的属性测试"""

    @settings(max_examples=100, deadline=None)
    @given(rubric_text=st.text(min_size=1, max_size=1000))
    def test_same_rubric_produces_same_hash(self, rubric_text: str):
        """
        **功能: ai-grading-agent, 属性 9: 感知哈希确定性**
        **验证: 需求 6.1**
        
        验证：对于任意评分细则文本，多次计算哈希应当产生相同的哈希值
        """
        # 多次计算哈希
        hash1 = compute_rubric_hash(rubric_text)
        hash2 = compute_rubric_hash(rubric_text)
        hash3 = compute_rubric_hash(rubric_text)
        
        # 验证所有哈希值相同
        assert hash1 == hash2, f"第一次和第二次哈希不同: {hash1} != {hash2}"
        assert hash2 == hash3, f"第二次和第三次哈希不同: {hash2} != {hash3}"

    @settings(max_examples=100, deadline=None)
    @given(rubric_text=st.text(min_size=1, max_size=1000))
    def test_rubric_hash_format_valid(self, rubric_text: str):
        """
        **功能: ai-grading-agent, 属性 9: 感知哈希确定性**
        **验证: 需求 6.1**
        
        验证：评分细则哈希值格式正确（64 位十六进制字符串）
        """
        hash_value = compute_rubric_hash(rubric_text)
        
        # 验证是字符串
        assert isinstance(hash_value, str), f"哈希值应为字符串，实际为 {type(hash_value)}"
        
        # 验证长度为 64（SHA-256）
        assert len(hash_value) == 64, f"哈希值长度应为 64，实际为 {len(hash_value)}"
        
        # 验证是有效的十六进制字符串
        try:
            int(hash_value, 16)
        except ValueError:
            pytest.fail(f"哈希值不是有效的十六进制字符串: {hash_value}")

    @settings(max_examples=100, deadline=None)
    @given(
        rubric_text=st.text(min_size=1, max_size=500),
        suffix=st.text(min_size=1, max_size=10)
    )
    def test_different_rubrics_different_hashes(self, rubric_text: str, suffix: str):
        """
        **功能: ai-grading-agent, 属性 9: 感知哈希确定性**
        **验证: 需求 6.1**
        
        验证：不同的评分细则文本应产生不同的哈希值
        """
        # 确保两个文本不同
        assume(suffix.strip() != "")
        
        rubric1 = rubric_text
        rubric2 = rubric_text + suffix
        
        hash1 = compute_rubric_hash(rubric1)
        hash2 = compute_rubric_hash(rubric2)
        
        # 不同文本应产生不同哈希
        assert hash1 != hash2, \
            f"不同评分细则产生相同哈希: '{rubric1}' 和 '{rubric2}' 都是 {hash1}"
