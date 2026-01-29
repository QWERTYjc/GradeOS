"""文件验证工具"""

from typing import Tuple
from io import BytesIO
from PIL import Image


class FileValidationError(Exception):
    """文件验证错误"""

    pass


# 支持的图像格式
SUPPORTED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}

# 文件大小限制（字节）
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


def validate_image_format(image_data: bytes) -> Tuple[bool, str]:
    """
    验证图像格式

    Args:
        image_data: 图像字节数据

    Returns:
        (是否有效, 错误消息或格式名称)
    """
    try:
        img = Image.open(BytesIO(image_data))
        format_name = img.format

        if format_name not in SUPPORTED_IMAGE_FORMATS:
            return False, (
                f"不支持的图像格式: {format_name}。"
                f"支持的格式: {', '.join(SUPPORTED_IMAGE_FORMATS)}"
            )

        return True, format_name

    except Exception as e:
        return False, f"无法识别图像格式: {str(e)}"


def validate_file_size(file_data: bytes) -> Tuple[bool, str]:
    """
    验证文件大小

    Args:
        file_data: 文件字节数据

    Returns:
        (是否有效, 错误消息或成功消息)
    """
    file_size = len(file_data)

    if file_size > MAX_FILE_SIZE:
        max_size_mb = MAX_FILE_SIZE / (1024 * 1024)
        actual_size_mb = file_size / (1024 * 1024)
        return False, (
            f"文件大小超出限制。"
            f"最大允许: {max_size_mb:.1f} MB，实际大小: {actual_size_mb:.1f} MB"
        )

    if file_size == 0:
        return False, "文件为空"

    return True, "文件大小验证通过"


def validate_file(file_data: bytes, is_image: bool = True) -> None:
    """
    验证文件

    Args:
        file_data: 文件字节数据
        is_image: 是否为图像文件（如果为 False，则跳过格式验证）

    Raises:
        FileValidationError: 验证失败时抛出
    """
    # 验证文件大小
    size_valid, size_message = validate_file_size(file_data)
    if not size_valid:
        raise FileValidationError(size_message)

    # 如果是图像，验证格式
    if is_image:
        format_valid, format_message = validate_image_format(file_data)
        if not format_valid:
            raise FileValidationError(format_message)
