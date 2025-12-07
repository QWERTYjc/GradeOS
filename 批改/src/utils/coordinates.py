"""坐标转换工具函数

提供归一化坐标与像素坐标之间的转换功能。
Gemini 模型返回的坐标是归一化格式（0-1000 比例），需要转换为实际像素坐标。
"""

from typing import List
from src.models.region import BoundingBox


def normalize_coordinates(
    box_1000: List[int],
    img_width: int,
    img_height: int
) -> BoundingBox:
    """将归一化坐标（0-1000 比例）转换为像素坐标
    
    Args:
        box_1000: 归一化边界框坐标 [ymin, xmin, ymax, xmax]，范围 0-1000
        img_width: 图像宽度（像素）
        img_height: 图像高度（像素）
    
    Returns:
        BoundingBox: 像素坐标边界框
    
    Raises:
        ValueError: 如果输入参数无效
    
    Example:
        >>> normalize_coordinates([100, 200, 500, 800], 1920, 1080)
        BoundingBox(ymin=108, xmin=384, ymax=540, xmax=1536)
    """
    if len(box_1000) != 4:
        raise ValueError(f"box_1000 必须包含 4 个元素，实际为 {len(box_1000)}")
    
    if img_width <= 0 or img_height <= 0:
        raise ValueError(f"图像尺寸必须为正数，实际为 width={img_width}, height={img_height}")
    
    ymin_norm, xmin_norm, ymax_norm, xmax_norm = box_1000
    
    # 验证归一化坐标范围
    for coord, name in [(ymin_norm, "ymin"), (xmin_norm, "xmin"), 
                        (ymax_norm, "ymax"), (xmax_norm, "xmax")]:
        if not (0 <= coord <= 1000):
            raise ValueError(f"{name} 必须在 0-1000 范围内，实际为 {coord}")
    
    # 转换为像素坐标
    pixel_ymin = int(ymin_norm * img_height / 1000)
    pixel_xmin = int(xmin_norm * img_width / 1000)
    pixel_ymax = int(ymax_norm * img_height / 1000)
    pixel_xmax = int(xmax_norm * img_width / 1000)
    
    # 确保坐标在图像边界内
    pixel_ymin = max(0, min(pixel_ymin, img_height))
    pixel_xmin = max(0, min(pixel_xmin, img_width))
    pixel_ymax = max(0, min(pixel_ymax, img_height))
    pixel_xmax = max(0, min(pixel_xmax, img_width))
    
    return BoundingBox(
        ymin=pixel_ymin,
        xmin=pixel_xmin,
        ymax=pixel_ymax,
        xmax=pixel_xmax
    )


def denormalize_coordinates(
    box_pixel: BoundingBox,
    img_width: int,
    img_height: int
) -> List[int]:
    """将像素坐标转换为归一化坐标（0-1000 比例）
    
    Args:
        box_pixel: 像素坐标边界框
        img_width: 图像宽度（像素）
        img_height: 图像高度（像素）
    
    Returns:
        List[int]: 归一化边界框坐标 [ymin, xmin, ymax, xmax]，范围 0-1000
    
    Raises:
        ValueError: 如果输入参数无效
    
    Example:
        >>> box = BoundingBox(ymin=108, xmin=384, ymax=540, xmax=1536)
        >>> denormalize_coordinates(box, 1920, 1080)
        [100, 200, 500, 800]
    """
    if img_width <= 0 or img_height <= 0:
        raise ValueError(f"图像尺寸必须为正数，实际为 width={img_width}, height={img_height}")
    
    # 转换为归一化坐标
    ymin_norm = int(box_pixel.ymin * 1000 / img_height)
    xmin_norm = int(box_pixel.xmin * 1000 / img_width)
    ymax_norm = int(box_pixel.ymax * 1000 / img_height)
    xmax_norm = int(box_pixel.xmax * 1000 / img_width)
    
    # 确保归一化坐标在 0-1000 范围内
    ymin_norm = max(0, min(ymin_norm, 1000))
    xmin_norm = max(0, min(xmin_norm, 1000))
    ymax_norm = max(0, min(ymax_norm, 1000))
    xmax_norm = max(0, min(xmax_norm, 1000))
    
    return [ymin_norm, xmin_norm, ymax_norm, xmax_norm]
