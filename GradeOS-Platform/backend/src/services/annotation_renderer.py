"""批注渲染服务

将 AI 输出的批注坐标渲染到图片上，生成带批改标记的图片。

支持的批注类型：
- 分数标注
- 错误圈选（椭圆/矩形）
- 下划线
- 勾选/叉号
- 文字批注
- 高亮区域
"""

import io
import logging
from typing import List, Optional, Tuple
from dataclasses import dataclass
from PIL import Image, ImageDraw, ImageFont

from src.models.annotation import (
    AnnotationType,
    AnnotationColor,
    BoundingBox,
    VisualAnnotation,
    PageAnnotations,
    GradingAnnotationResult,
)


logger = logging.getLogger(__name__)


@dataclass
class RenderConfig:
    """渲染配置"""

    # 字体设置
    font_path: Optional[str] = None  # 字体文件路径，None 使用默认字体
    font_size_score: int = 24  # 分数字体大小
    font_size_comment: int = 16  # 批注字体大小

    # 线条设置
    line_width_circle: int = 3  # 圈选线宽
    line_width_underline: int = 2  # 下划线线宽
    line_width_check: int = 3  # 勾选线宽

    # 透明度
    highlight_alpha: int = 80  # 高亮透明度 (0-255)

    # 边距
    comment_padding: int = 4  # 批注文字内边距

    # 输出格式
    output_format: str = "PNG"  # 输出图片格式
    output_quality: int = 95  # JPEG 质量


class AnnotationRenderer:
    """
    批注渲染器

    将批注坐标渲染到图片上
    """

    def __init__(self, config: Optional[RenderConfig] = None):
        self.config = config or RenderConfig()
        self._font_cache = {}

    def _get_font(self, size: int) -> ImageFont.FreeTypeFont:
        """获取字体（带缓存）"""
        if size in self._font_cache:
            return self._font_cache[size]

        try:
            if self.config.font_path:
                font = ImageFont.truetype(self.config.font_path, size)
            else:
                # 尝试加载系统中文字体
                chinese_fonts = [
                    "simhei.ttf",  # Windows 黑体
                    "msyh.ttc",  # Windows 微软雅黑
                    "SimHei.ttf",
                    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",  # Linux
                    "/System/Library/Fonts/PingFang.ttc",  # macOS
                    "arial.ttf",  # 回退到 Arial
                ]
                font = None
                for font_name in chinese_fonts:
                    try:
                        font = ImageFont.truetype(font_name, size)
                        break
                    except (IOError, OSError):
                        continue

                if font is None:
                    # 使用默认字体
                    font = ImageFont.load_default()
        except Exception as e:
            logger.warning(f"加载字体失败: {e}，使用默认字体")
            font = ImageFont.load_default()

        self._font_cache[size] = font
        return font

    def _parse_color(self, color: str) -> Tuple[int, int, int]:
        """解析颜色字符串为 RGB 元组"""
        if color.startswith("#"):
            color = color[1:]
        if len(color) == 6:
            return (
                int(color[0:2], 16),
                int(color[2:4], 16),
                int(color[4:6], 16),
            )
        return (255, 0, 0)  # 默认红色

    def _to_pixel_coords(
        self,
        bbox: BoundingBox,
        image_width: int,
        image_height: int,
    ) -> Tuple[int, int, int, int]:
        """将归一化坐标转换为像素坐标"""
        return (
            int(bbox.x_min * image_width),
            int(bbox.y_min * image_height),
            int(bbox.x_max * image_width),
            int(bbox.y_max * image_height),
        )

    def _draw_score(
        self,
        draw: ImageDraw.ImageDraw,
        annotation: VisualAnnotation,
        image_width: int,
        image_height: int,
    ) -> None:
        """绘制分数标注"""
        x1, y1, x2, y2 = self._to_pixel_coords(annotation.bounding_box, image_width, image_height)

        color = self._parse_color(annotation.color)
        font = self._get_font(self.config.font_size_score)

        # 绘制分数文字
        text = annotation.text or "0"

        # 计算文字位置（居中）
        try:
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
        except AttributeError:
            # 旧版 Pillow 兼容
            text_width, text_height = draw.textsize(text, font=font)

        text_x = x1 + (x2 - x1 - text_width) // 2
        text_y = y1 + (y2 - y1 - text_height) // 2

        # 绘制背景（半透明白色）
        padding = 4
        draw.rectangle(
            [
                text_x - padding,
                text_y - padding,
                text_x + text_width + padding,
                text_y + text_height + padding,
            ],
            fill=(255, 255, 255, 200),
        )

        # 绘制文字
        draw.text((text_x, text_y), text, fill=color, font=font)

    def _draw_error_circle(
        self,
        draw: ImageDraw.ImageDraw,
        annotation: VisualAnnotation,
        image_width: int,
        image_height: int,
    ) -> None:
        """绘制错误圈选（椭圆）"""
        x1, y1, x2, y2 = self._to_pixel_coords(annotation.bounding_box, image_width, image_height)

        color = self._parse_color(annotation.color)

        # 绘制椭圆
        draw.ellipse(
            [x1, y1, x2, y2],
            outline=color,
            width=self.config.line_width_circle,
        )

    def _draw_underline(
        self,
        draw: ImageDraw.ImageDraw,
        annotation: VisualAnnotation,
        image_width: int,
        image_height: int,
    ) -> None:
        """绘制下划线"""
        x1, y1, x2, y2 = self._to_pixel_coords(annotation.bounding_box, image_width, image_height)

        color = self._parse_color(annotation.color)

        # 在底部绘制波浪线
        y = y2
        draw.line(
            [(x1, y), (x2, y)],
            fill=color,
            width=self.config.line_width_underline,
        )

    def _draw_check_mark(
        self,
        draw: ImageDraw.ImageDraw,
        annotation: VisualAnnotation,
        image_width: int,
        image_height: int,
    ) -> None:
        """绘制勾选标记 ✓"""
        x1, y1, x2, y2 = self._to_pixel_coords(annotation.bounding_box, image_width, image_height)

        color = self._parse_color(annotation.color)

        # 计算勾选的关键点
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        size = min(x2 - x1, y2 - y1) // 2

        # 绘制勾选 ✓
        points = [
            (cx - size, cy),
            (cx - size // 3, cy + size // 2),
            (cx + size, cy - size // 2),
        ]
        draw.line(points, fill=color, width=self.config.line_width_check)

    def _draw_partial_check(
        self,
        draw: ImageDraw.ImageDraw,
        annotation: VisualAnnotation,
        image_width: int,
        image_height: int,
    ) -> None:
        """绘制部分正确标记 △"""
        x1, y1, x2, y2 = self._to_pixel_coords(annotation.bounding_box, image_width, image_height)

        color = self._parse_color(annotation.color)

        # 绘制三角形
        cx = (x1 + x2) // 2
        points = [
            (cx, y1),
            (x1, y2),
            (x2, y2),
            (cx, y1),
        ]
        draw.line(points, fill=color, width=self.config.line_width_check)

    def _draw_wrong_cross(
        self,
        draw: ImageDraw.ImageDraw,
        annotation: VisualAnnotation,
        image_width: int,
        image_height: int,
    ) -> None:
        """绘制错误叉号 ✗"""
        x1, y1, x2, y2 = self._to_pixel_coords(annotation.bounding_box, image_width, image_height)

        color = self._parse_color(annotation.color)

        # 绘制 X
        padding = 2
        draw.line(
            [(x1 + padding, y1 + padding), (x2 - padding, y2 - padding)],
            fill=color,
            width=self.config.line_width_check,
        )
        draw.line(
            [(x2 - padding, y1 + padding), (x1 + padding, y2 - padding)],
            fill=color,
            width=self.config.line_width_check,
        )

    def _draw_comment(
        self,
        draw: ImageDraw.ImageDraw,
        annotation: VisualAnnotation,
        image_width: int,
        image_height: int,
    ) -> None:
        """绘制文字批注"""
        x1, y1, x2, y2 = self._to_pixel_coords(annotation.bounding_box, image_width, image_height)

        color = self._parse_color(annotation.color)
        font = self._get_font(self.config.font_size_comment)

        text = annotation.text or ""
        if not text:
            return

        # 计算文字大小
        try:
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
        except AttributeError:
            text_width, text_height = draw.textsize(text, font=font)

        padding = self.config.comment_padding

        # 绘制背景
        bg_x1 = x1
        bg_y1 = y1
        bg_x2 = x1 + text_width + padding * 2
        bg_y2 = y1 + text_height + padding * 2

        draw.rectangle(
            [bg_x1, bg_y1, bg_x2, bg_y2],
            fill=(255, 255, 255, 230),
            outline=color,
        )

        # 绘制文字
        draw.text((x1 + padding, y1 + padding), text, fill=color, font=font)

    def _draw_highlight(
        self,
        image: Image.Image,
        annotation: VisualAnnotation,
    ) -> None:
        """绘制高亮区域"""
        x1, y1, x2, y2 = self._to_pixel_coords(annotation.bounding_box, image.width, image.height)

        color = self._parse_color(annotation.color)

        # 创建半透明覆盖层
        overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)

        overlay_draw.rectangle(
            [x1, y1, x2, y2],
            fill=(*color, self.config.highlight_alpha),
        )

        # 合并图层
        image.paste(Image.alpha_composite(image.convert("RGBA"), overlay))

    def _draw_a_mark(
        self,
        draw: ImageDraw.ImageDraw,
        annotation: VisualAnnotation,
        image_width: int,
        image_height: int,
    ) -> None:
        """绘制 A mark（答案分）标注"""
        x1, y1, x2, y2 = self._to_pixel_coords(annotation.bounding_box, image_width, image_height)

        color = self._parse_color(annotation.color)
        font = self._get_font(self.config.font_size_score)

        # 绘制 A mark 文字（如 "A1" 或 "A0"）
        text = annotation.text or "A"

        # 计算文字大小
        try:
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
        except AttributeError:
            text_width, text_height = draw.textsize(text, font=font)

        text_x = x1 + (x2 - x1 - text_width) // 2
        text_y = y1 + (y2 - y1 - text_height) // 2

        # 绘制圆形背景
        padding = 4
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        radius = max(text_width, text_height) // 2 + padding

        draw.ellipse(
            [cx - radius, cy - radius, cx + radius, cy + radius],
            fill=(255, 255, 255, 230),
            outline=color,
            width=2,
        )

        # 绘制文字
        draw.text((text_x, text_y), text, fill=color, font=font)

    def _draw_m_mark(
        self,
        draw: ImageDraw.ImageDraw,
        annotation: VisualAnnotation,
        image_width: int,
        image_height: int,
    ) -> None:
        """绘制 M mark（方法分）标注"""
        x1, y1, x2, y2 = self._to_pixel_coords(annotation.bounding_box, image_width, image_height)

        color = self._parse_color(annotation.color)
        font = self._get_font(self.config.font_size_score)

        # 绘制 M mark 文字（如 "M1" 或 "M0"）
        text = annotation.text or "M"

        # 计算文字大小
        try:
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
        except AttributeError:
            text_width, text_height = draw.textsize(text, font=font)

        text_x = x1 + (x2 - x1 - text_width) // 2
        text_y = y1 + (y2 - y1 - text_height) // 2

        # 绘制方形背景
        padding = 4
        draw.rectangle(
            [
                text_x - padding,
                text_y - padding,
                text_x + text_width + padding,
                text_y + text_height + padding,
            ],
            fill=(255, 255, 255, 230),
            outline=color,
            width=2,
        )

        # 绘制文字
        draw.text((text_x, text_y), text, fill=color, font=font)

    def _draw_step_check(
        self,
        draw: ImageDraw.ImageDraw,
        annotation: VisualAnnotation,
        image_width: int,
        image_height: int,
    ) -> None:
        """绘制步骤正确勾选 ✓（较小的勾选标记）"""
        x1, y1, x2, y2 = self._to_pixel_coords(annotation.bounding_box, image_width, image_height)

        color = self._parse_color(annotation.color)

        # 计算勾选的关键点（较小的勾选）
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        size = min(x2 - x1, y2 - y1) // 2

        # 绘制小勾选 ✓
        points = [
            (cx - size * 0.6, cy),
            (cx - size * 0.2, cy + size * 0.4),
            (cx + size * 0.6, cy - size * 0.4),
        ]
        draw.line(points, fill=color, width=max(2, self.config.line_width_check - 1))

    def _draw_step_cross(
        self,
        draw: ImageDraw.ImageDraw,
        annotation: VisualAnnotation,
        image_width: int,
        image_height: int,
    ) -> None:
        """绘制步骤错误叉 ✗（较小的叉号）"""
        x1, y1, x2, y2 = self._to_pixel_coords(annotation.bounding_box, image_width, image_height)

        color = self._parse_color(annotation.color)

        # 绘制小 X
        padding = 3
        size = min(x2 - x1, y2 - y1) // 2
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2

        draw.line(
            [
                (cx - size + padding, cy - size + padding),
                (cx + size - padding, cy + size - padding),
            ],
            fill=color,
            width=max(2, self.config.line_width_check - 1),
        )
        draw.line(
            [
                (cx + size - padding, cy - size + padding),
                (cx - size + padding, cy + size - padding),
            ],
            fill=color,
            width=max(2, self.config.line_width_check - 1),
        )

    def _draw_simple_check(
        self,
        draw: ImageDraw.ImageDraw,
        annotation: VisualAnnotation,
        image_width: int,
        image_height: int,
    ) -> None:
        """绘制简单勾选 ✓（无分数，只打勾）"""
        x1, y1, x2, y2 = self._to_pixel_coords(annotation.bounding_box, image_width, image_height)

        # 默认绿色
        color = self._parse_color(annotation.color or "#00AA00")

        # 计算勾选的关键点
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        size = min(x2 - x1, y2 - y1) // 2

        # 绘制粗勾选 ✓
        points = [
            (cx - size, cy),
            (cx - size // 4, cy + size * 0.6),
            (cx + size, cy - size * 0.5),
        ]
        draw.line(points, fill=color, width=self.config.line_width_check + 1)

    def _draw_simple_cross(
        self,
        draw: ImageDraw.ImageDraw,
        annotation: VisualAnnotation,
        image_width: int,
        image_height: int,
    ) -> None:
        """绘制简单叉号 ✗（无分数，只打叉）"""
        x1, y1, x2, y2 = self._to_pixel_coords(annotation.bounding_box, image_width, image_height)

        # 默认红色
        color = self._parse_color(annotation.color or "#FF0000")

        # 绘制粗 X
        padding = 2
        draw.line(
            [(x1 + padding, y1 + padding), (x2 - padding, y2 - padding)],
            fill=color,
            width=self.config.line_width_check + 1,
        )
        draw.line(
            [(x2 - padding, y1 + padding), (x1 + padding, y2 - padding)],
            fill=color,
            width=self.config.line_width_check + 1,
        )

    def _draw_simple_score(
        self,
        draw: ImageDraw.ImageDraw,
        annotation: VisualAnnotation,
        image_width: int,
        image_height: int,
    ) -> None:
        """绘制简单分数（如 "1"，绿色，无单位）"""
        x1, y1, x2, y2 = self._to_pixel_coords(annotation.bounding_box, image_width, image_height)

        # 默认绿色
        color = self._parse_color(annotation.color or "#00AA00")
        font = self._get_font(self.config.font_size_score)

        # 只显示分数数字（如 "1"、"2"），不带单位
        text = annotation.text or "1"

        # 计算文字大小
        try:
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
        except AttributeError:
            text_width, text_height = draw.textsize(text, font=font)

        text_x = x1 + (x2 - x1 - text_width) // 2
        text_y = y1 + (y2 - y1 - text_height) // 2

        # 绘制文字（无背景，直接绘制分数）
        draw.text((text_x, text_y), text, fill=color, font=font)

    def _draw_half_check(
        self,
        draw: ImageDraw.ImageDraw,
        annotation: VisualAnnotation,
        image_width: int,
        image_height: int,
    ) -> None:
        """绘制半对标记 ~ 或 ½"""
        x1, y1, x2, y2 = self._to_pixel_coords(annotation.bounding_box, image_width, image_height)

        # 橙色表示部分正确
        color = self._parse_color(annotation.color or "#FF8800")
        font = self._get_font(self.config.font_size_score)

        # 使用 ~ 符号
        text = annotation.text or "~"

        # 计算文字大小
        try:
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
        except AttributeError:
            text_width, text_height = draw.textsize(text, font=font)

        text_x = x1 + (x2 - x1 - text_width) // 2
        text_y = y1 + (y2 - y1 - text_height) // 2

        draw.text((text_x, text_y), text, fill=color, font=font)

    def _draw_total_score(
        self,
        draw: ImageDraw.ImageDraw,
        annotation: VisualAnnotation,
        image_width: int,
        image_height: int,
    ) -> None:
        """绘制题目总分标注（带圆圈背景）"""
        x1, y1, x2, y2 = self._to_pixel_coords(annotation.bounding_box, image_width, image_height)

        color = self._parse_color(annotation.color)
        font = self._get_font(self.config.font_size_score + 2)  # 稍大字体

        text = annotation.text or "0"

        # 计算文字大小
        try:
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
        except AttributeError:
            text_width, text_height = draw.textsize(text, font=font)

        # 绘制圆圈背景
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        radius = max(text_width, text_height) // 2 + 6

        draw.ellipse(
            [cx - radius, cy - radius, cx + radius, cy + radius],
            fill=(255, 255, 255, 240),
            outline=color,
            width=2,
        )

        # 绘制分数文字
        text_x = cx - text_width // 2
        text_y = cy - text_height // 2
        draw.text((text_x, text_y), text, fill=color, font=font)

    def _draw_point_score(
        self,
        draw: ImageDraw.ImageDraw,
        annotation: VisualAnnotation,
        image_width: int,
        image_height: int,
    ) -> None:
        """绘制得分点分数标注（如 "+1" 或 "-1"）"""
        x1, y1, x2, y2 = self._to_pixel_coords(annotation.bounding_box, image_width, image_height)

        # 根据正负确定颜色
        text = annotation.text or "+1"
        if text.startswith("-") or text.startswith("0"):
            color = self._parse_color(annotation.color or "#FF0000")  # 红色
        else:
            color = self._parse_color(annotation.color or "#00AA00")  # 绿色

        font = self._get_font(self.config.font_size_score - 2)  # 稍小字体

        # 计算文字大小
        try:
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
        except AttributeError:
            text_width, text_height = draw.textsize(text, font=font)

        text_x = x1 + (x2 - x1 - text_width) // 2
        text_y = y1 + (y2 - y1 - text_height) // 2

        # 绘制小背景
        padding = 2
        draw.rectangle(
            [
                text_x - padding,
                text_y - padding,
                text_x + text_width + padding,
                text_y + text_height + padding,
            ],
            fill=(255, 255, 255, 200),
        )

        # 绘制文字
        draw.text((text_x, text_y), text, fill=color, font=font)

    def render_annotation(
        self,
        draw: ImageDraw.ImageDraw,
        image: Image.Image,
        annotation: VisualAnnotation,
    ) -> None:
        """渲染单个批注"""
        width, height = image.size

        if annotation.annotation_type == AnnotationType.SCORE:
            self._draw_score(draw, annotation, width, height)
        elif annotation.annotation_type == AnnotationType.ERROR_CIRCLE:
            self._draw_error_circle(draw, annotation, width, height)
        elif annotation.annotation_type == AnnotationType.ERROR_UNDERLINE:
            self._draw_underline(draw, annotation, width, height)
        elif annotation.annotation_type == AnnotationType.CORRECT_CHECK:
            self._draw_check_mark(draw, annotation, width, height)
        elif annotation.annotation_type == AnnotationType.PARTIAL_CHECK:
            self._draw_partial_check(draw, annotation, width, height)
        elif annotation.annotation_type == AnnotationType.WRONG_CROSS:
            self._draw_wrong_cross(draw, annotation, width, height)
        elif annotation.annotation_type == AnnotationType.COMMENT:
            self._draw_comment(draw, annotation, width, height)
        elif annotation.annotation_type == AnnotationType.HIGHLIGHT:
            self._draw_highlight(image, annotation)
        # A/M mark 和步骤标注类型
        elif annotation.annotation_type == AnnotationType.A_MARK:
            self._draw_a_mark(draw, annotation, width, height)
        elif annotation.annotation_type == AnnotationType.M_MARK:
            self._draw_m_mark(draw, annotation, width, height)
        elif annotation.annotation_type == AnnotationType.STEP_CHECK:
            self._draw_step_check(draw, annotation, width, height)
        elif annotation.annotation_type == AnnotationType.STEP_CROSS:
            self._draw_step_cross(draw, annotation, width, height)
        # 新增简化标注类型
        elif annotation.annotation_type == AnnotationType.SIMPLE_CHECK:
            self._draw_simple_check(draw, annotation, width, height)
        elif annotation.annotation_type == AnnotationType.SIMPLE_CROSS:
            self._draw_simple_cross(draw, annotation, width, height)
        elif annotation.annotation_type == AnnotationType.SIMPLE_SCORE:
            self._draw_simple_score(draw, annotation, width, height)
        elif annotation.annotation_type == AnnotationType.HALF_CHECK:
            self._draw_half_check(draw, annotation, width, height)
        elif annotation.annotation_type == AnnotationType.TOTAL_SCORE:
            self._draw_total_score(draw, annotation, width, height)
        elif annotation.annotation_type == AnnotationType.POINT_SCORE:
            self._draw_point_score(draw, annotation, width, height)

    def render_page(
        self,
        image_data: bytes,
        page_annotations: PageAnnotations,
    ) -> bytes:
        """
        渲染单页批注

        Args:
            image_data: 原始图片数据
            page_annotations: 页面批注信息

        Returns:
            bytes: 渲染后的图片数据
        """
        # 打开图片
        image = Image.open(io.BytesIO(image_data))

        # 转换为 RGBA 以支持透明度
        if image.mode != "RGBA":
            image = image.convert("RGBA")

        # 创建绘图对象
        draw = ImageDraw.Draw(image, "RGBA")

        # 渲染所有批注
        for annotation in page_annotations.annotations:
            try:
                self.render_annotation(draw, image, annotation)
            except Exception as e:
                logger.warning(f"渲染批注失败: {e}")

        # 输出
        output = io.BytesIO()
        if self.config.output_format.upper() == "JPEG":
            # JPEG 不支持透明度，转换为 RGB
            image = image.convert("RGB")
            image.save(output, format="JPEG", quality=self.config.output_quality)
        else:
            image.save(output, format="PNG")

        return output.getvalue()

    def render_submission(
        self,
        pages: List[bytes],
        grading_result: GradingAnnotationResult,
    ) -> List[bytes]:
        """
        渲染整份提交的批注

        Args:
            pages: 原始页面图片列表
            grading_result: 批改批注结果

        Returns:
            List[bytes]: 渲染后的图片列表
        """
        rendered_pages = []

        for i, page_data in enumerate(pages):
            # 查找对应的批注
            page_annotations = None
            for pa in grading_result.pages:
                if pa.page_index == i:
                    page_annotations = pa
                    break

            if page_annotations and page_annotations.annotations:
                # 有批注，渲染
                rendered = self.render_page(page_data, page_annotations)
                rendered_pages.append(rendered)
            else:
                # 无批注，保持原样
                rendered_pages.append(page_data)

        return rendered_pages


# 便捷函数
def render_annotations_on_image(
    image_data: bytes,
    annotations: List[VisualAnnotation],
    config: Optional[RenderConfig] = None,
) -> bytes:
    """
    便捷函数：在图片上渲染批注

    Args:
        image_data: 原始图片数据
        annotations: 批注列表
        config: 渲染配置

    Returns:
        bytes: 渲染后的图片数据
    """
    renderer = AnnotationRenderer(config)
    page_annotations = PageAnnotations(page_index=0, annotations=annotations)
    return renderer.render_page(image_data, page_annotations)


# 导出
__all__ = [
    "RenderConfig",
    "AnnotationRenderer",
    "render_annotations_on_image",
]
