"""带批注的 PDF 导出服务

将批改结果和批注渲染到答题图片上，生成 PDF 文件。
"""

import base64
import io
import logging
import httpx
from typing import List, Optional, Dict, Any
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

from src.db.postgres_grading import GradingAnnotation, GradingPageImage, StudentGradingResult


logger = logging.getLogger(__name__)

# 批注颜色映射
ANNOTATION_COLORS = {
    "#FF0000": (255, 0, 0),      # 红色 - 错误
    "#00AA00": (0, 170, 0),      # 绿色 - 正确
    "#FF8800": (255, 136, 0),    # 橙色 - 部分正确
    "#0066FF": (0, 102, 255),    # 蓝色 - 信息
    "#9900FF": (153, 0, 255),    # 紫色 - 重要
}

# 默认字体大小
DEFAULT_FONT_SIZE = 24


async def export_annotated_pdf(
    student_result: StudentGradingResult,
    page_images: List[GradingPageImage],
    annotations: List[GradingAnnotation],
    include_summary: bool = True,
    fallback_images: Optional[Dict[int, bytes]] = None,
) -> bytes:
    """
    导出带批注的 PDF
    
    Args:
        student_result: 学生批改结果
        page_images: 页面图片列表
        annotations: 批注列表
        include_summary: 是否包含摘要页
    
    Returns:
        PDF 文件的字节数据
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas as pdf_canvas
        from reportlab.lib.utils import ImageReader
    except ImportError:
        logger.error("reportlab 未安装，无法导出 PDF")
        raise ImportError("请安装 reportlab: pip install reportlab")
    
    # 按页码排序图片
    sorted_images = sorted(page_images, key=lambda x: x.page_index)
    
    # 按页码分组批注
    annotations_by_page: Dict[int, List[GradingAnnotation]] = {}
    for ann in annotations:
        page_idx = ann.page_index
        if page_idx not in annotations_by_page:
            annotations_by_page[page_idx] = []
        annotations_by_page[page_idx].append(ann)
    
    # 创建 PDF
    pdf_buffer = io.BytesIO()
    c = pdf_canvas.Canvas(pdf_buffer, pagesize=A4)
    page_width, page_height = A4
    
    # 如果需要摘要页，先添加摘要
    if include_summary:
        _draw_summary_page(c, student_result, page_width, page_height)
        c.showPage()
    
    # 渲染每个页面
    for page_image in sorted_images:
        try:
            # 获取图片数据
            image_data = await _fetch_image_data(page_image, fallback_images=fallback_images)
            if not image_data:
                logger.warning(f"无法获取页面 {page_image.page_index} 的图片")
                continue
            
            # 加载图片
            pil_image = Image.open(io.BytesIO(image_data))
            
            # 获取该页的批注
            page_annotations = annotations_by_page.get(page_image.page_index, [])
            
            # 在图片上渲染批注
            if page_annotations:
                pil_image = _render_annotations_on_image(pil_image, page_annotations)
            
            # 将图片添加到 PDF
            img_buffer = io.BytesIO()
            pil_image.save(img_buffer, format='PNG')
            img_buffer.seek(0)
            
            img_reader = ImageReader(img_buffer)
            
            # 计算图片在页面上的尺寸（保持比例）
            img_width, img_height = pil_image.size
            aspect_ratio = img_width / img_height
            
            # 留边距
            margin = 20 * mm
            max_width = page_width - 2 * margin
            max_height = page_height - 2 * margin
            
            if aspect_ratio > max_width / max_height:
                # 宽度受限
                draw_width = max_width
                draw_height = draw_width / aspect_ratio
            else:
                # 高度受限
                draw_height = max_height
                draw_width = draw_height * aspect_ratio
            
            # 居中绘制
            x = (page_width - draw_width) / 2
            y = (page_height - draw_height) / 2
            
            c.drawImage(img_reader, x, y, width=draw_width, height=draw_height)
            
            # 添加页码
            c.setFont("Helvetica", 10)
            c.drawString(page_width - 50, 20, f"Page {page_image.page_index + 1}")
            
            c.showPage()
            
        except Exception as e:
            logger.error(f"渲染页面 {page_image.page_index} 失败: {e}")
            continue
    
    c.save()
    pdf_buffer.seek(0)
    return pdf_buffer.read()


def _draw_summary_page(c, student_result: StudentGradingResult, page_width: float, page_height: float):
    """绘制摘要页"""
    from reportlab.lib.units import mm
    
    margin = 30 * mm
    y = page_height - margin
    
    # 标题
    c.setFont("Helvetica-Bold", 24)
    c.drawString(margin, y, "Grading Report")
    y -= 15 * mm
    
    # 学生信息
    c.setFont("Helvetica", 14)
    c.drawString(margin, y, f"Student: {student_result.student_key}")
    y -= 8 * mm
    
    # 分数
    score = student_result.score or 0
    max_score = student_result.max_score or 100
    percentage = (score / max_score * 100) if max_score > 0 else 0
    
    c.setFont("Helvetica-Bold", 18)
    c.drawString(margin, y, f"Score: {score} / {max_score} ({percentage:.1f}%)")
    y -= 15 * mm
    
    # 题目详情
    result_data = student_result.result_data or {}
    question_results = (
        result_data.get("question_results")
        or result_data.get("questionResults")
        or result_data.get("question_details")
        or []
    )
    
    if question_results:
        c.setFont("Helvetica-Bold", 14)
        c.drawString(margin, y, "Question Details:")
        y -= 8 * mm
        
        c.setFont("Helvetica", 11)
        for q in question_results[:15]:  # 最多显示 15 道题
            qid = q.get("question_id") or q.get("questionId") or "?"
            q_score = q.get("score", 0)
            q_max = q.get("max_score") or q.get("maxScore", 0)
            feedback = (q.get("feedback") or "")[:50]
            
            line = f"Q{qid}: {q_score}/{q_max}"
            if feedback:
                line += f" - {feedback}"
            
            c.drawString(margin + 10, y, line)
            y -= 6 * mm
            
            if y < margin:
                break
    
    # 页脚
    c.setFont("Helvetica", 9)
    c.drawString(margin, 20, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    c.drawString(page_width - margin - 80, 20, "GradeOS")


def _render_annotations_on_image(
    image: Image.Image,
    annotations: List[GradingAnnotation],
) -> Image.Image:
    """在图片上渲染批注"""
    # 转换为 RGBA 以支持透明度
    if image.mode != 'RGBA':
        image = image.convert('RGBA')
    
    draw = ImageDraw.Draw(image)
    img_width, img_height = image.size
    
    # 尝试加载字体
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", DEFAULT_FONT_SIZE)
        small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", DEFAULT_FONT_SIZE - 6)
    except:
        try:
            font = ImageFont.truetype("arial.ttf", DEFAULT_FONT_SIZE)
            small_font = ImageFont.truetype("arial.ttf", DEFAULT_FONT_SIZE - 6)
        except:
            font = ImageFont.load_default()
            small_font = font
    
    for ann in annotations:
        try:
            bbox = ann.bounding_box
            if not bbox:
                continue
            
            # 转换归一化坐标为像素坐标
            x_min = int(bbox.get("x_min", 0) * img_width)
            y_min = int(bbox.get("y_min", 0) * img_height)
            x_max = int(bbox.get("x_max", 0) * img_width)
            y_max = int(bbox.get("y_max", 0) * img_height)
            
            # 获取颜色
            color_hex = ann.color or "#FF0000"
            color_rgb = ANNOTATION_COLORS.get(color_hex, (255, 0, 0))
            
            ann_type = ann.annotation_type
            text = ann.text or ""
            
            if ann_type == "score":
                # 分数标注：带背景的文字
                _draw_text_with_background(
                    draw, (x_min, y_min), text, font, color_rgb, (255, 255, 255, 220)
                )
            
            elif ann_type in ("m_mark", "a_mark"):
                # M/A mark 标注：小圆圈 + 文字
                center_x = (x_min + x_max) // 2
                center_y = (y_min + y_max) // 2
                radius = 15
                draw.ellipse(
                    [center_x - radius, center_y - radius, center_x + radius, center_y + radius],
                    fill=(*color_rgb, 200),
                    outline=color_rgb,
                    width=2
                )
                # 文字居中
                _draw_centered_text(draw, (center_x, center_y), text, small_font, (255, 255, 255))
            
            elif ann_type == "error_circle":
                # 错误圈选：椭圆 + 标注文字
                draw.ellipse(
                    [x_min, y_min, x_max, y_max],
                    outline=color_rgb,
                    width=3
                )
                if text:
                    _draw_text_with_background(
                        draw, (x_max + 5, y_min), text, small_font, color_rgb, (255, 255, 255, 220)
                    )
            
            elif ann_type == "comment":
                # 文字批注
                _draw_text_with_background(
                    draw, (x_min, y_min), text, small_font, color_rgb, (255, 255, 240, 220)
                )
            
            elif ann_type in ("correct_check", "step_check"):
                # 勾选 ✓
                _draw_check_mark(draw, (x_min, y_min, x_max, y_max), color_rgb)
            
            elif ann_type in ("wrong_cross", "step_cross"):
                # 叉号 ✗
                _draw_cross_mark(draw, (x_min, y_min, x_max, y_max), color_rgb)
            
            else:
                # 默认：绘制矩形框
                draw.rectangle([x_min, y_min, x_max, y_max], outline=color_rgb, width=2)
                if text:
                    draw.text((x_min, y_max + 2), text, fill=color_rgb, font=small_font)
        
        except Exception as e:
            logger.error(f"渲染批注失败: {e}")
            continue
    
    return image


def _draw_text_with_background(
    draw: ImageDraw.ImageDraw,
    position: tuple,
    text: str,
    font: ImageFont.FreeTypeFont,
    text_color: tuple,
    bg_color: tuple,
):
    """绘制带背景的文字"""
    x, y = position
    
    # 获取文字边界框
    bbox = draw.textbbox((x, y), text, font=font)
    padding = 4
    
    # 绘制背景
    draw.rectangle(
        [bbox[0] - padding, bbox[1] - padding, bbox[2] + padding, bbox[3] + padding],
        fill=bg_color
    )
    
    # 绘制文字
    draw.text((x, y), text, fill=text_color, font=font)


def _draw_centered_text(
    draw: ImageDraw.ImageDraw,
    center: tuple,
    text: str,
    font: ImageFont.FreeTypeFont,
    color: tuple,
):
    """绘制居中文字"""
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = center[0] - text_width // 2
    y = center[1] - text_height // 2
    draw.text((x, y), text, fill=color, font=font)


def _draw_check_mark(draw: ImageDraw.ImageDraw, bbox: tuple, color: tuple):
    """绘制勾选标记 ✓"""
    x_min, y_min, x_max, y_max = bbox
    width = x_max - x_min
    height = y_max - y_min
    
    # 勾的形状：从左下到中下，再到右上
    points = [
        (x_min + width * 0.1, y_min + height * 0.5),
        (x_min + width * 0.4, y_min + height * 0.8),
        (x_min + width * 0.9, y_min + height * 0.2),
    ]
    draw.line(points, fill=color, width=3)


def _draw_cross_mark(draw: ImageDraw.ImageDraw, bbox: tuple, color: tuple):
    """绘制叉号标记 ✗"""
    x_min, y_min, x_max, y_max = bbox
    
    # 两条对角线
    draw.line([(x_min, y_min), (x_max, y_max)], fill=color, width=3)
    draw.line([(x_max, y_min), (x_min, y_max)], fill=color, width=3)


async def _fetch_image_data(
    page_image: GradingPageImage,
    fallback_images: Optional[Dict[int, bytes]] = None,
) -> Optional[bytes]:
    """获取图片数据"""
    try:
        if page_image.file_url:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(page_image.file_url)
                if response.status_code == 200:
                    return response.content
        if fallback_images:
            fallback = fallback_images.get(page_image.page_index)
            if fallback:
                return fallback
        return None
    except Exception as e:
        logger.error(f"获取图片失败: {e}")
        return None
