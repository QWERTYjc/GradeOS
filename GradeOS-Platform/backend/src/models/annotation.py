"""批注坐标模型

定义 AI 批改输出的视觉批注数据结构，用于在图片上渲染：
- 分数标注位置
- 错误圈选区域
- 错误讲解位置
- 正确/部分正确标记

坐标系统：使用归一化坐标 (0.0-1.0)，便于适配不同分辨率的图片
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Literal
from enum import Enum
import json


class AnnotationType(str, Enum):
    """批注类型"""

    SCORE = "score"  # 分数标注（如 "8/10"）
    ERROR_CIRCLE = "error_circle"  # 错误圈选
    ERROR_UNDERLINE = "error_underline"  # 错误下划线
    CORRECT_CHECK = "correct_check"  # 正确勾选 ✓
    PARTIAL_CHECK = "partial_check"  # 部分正确 △
    WRONG_CROSS = "wrong_cross"  # 错误叉 ✗
    COMMENT = "comment"  # 文字批注/讲解
    HIGHLIGHT = "highlight"  # 高亮区域
    ARROW = "arrow"  # 箭头指示
    # A/M mark 细粒度批注类型
    A_MARK = "a_mark"  # A mark（答案分）标注，显示 "A1" 或 "A0"
    M_MARK = "m_mark"  # M mark（方法分）标注，显示 "M1" 或 "M0"
    STEP_CHECK = "step_check"  # 步骤正确勾选 ✓（用于标注每个步骤）
    STEP_CROSS = "step_cross"  # 步骤错误叉 ✗（用于标注每个步骤）
    # 简化标注类型 - 适应各种批改场景
    SIMPLE_CHECK = "simple_check"  # 只打勾 ✓（无得分数据时使用）
    SIMPLE_CROSS = "simple_cross"  # 只打叉 ✗（无得分数据时使用）
    SIMPLE_SCORE = "simple_score"  # 只写分数（如 "1"，绿色，无单位）
    HALF_CHECK = "half_check"  # 半对 ½ 或 ~（部分正确但无具体分数时）
    TOTAL_SCORE = "total_score"  # 题目总分标注（放在题目结尾）
    POINT_SCORE = "point_score"  # 得分点分数标注（如 "+1" 或 "-1"）


class AnnotationColor(str, Enum):
    """批注颜色"""

    RED = "#FF0000"  # 错误
    GREEN = "#00AA00"  # 正确
    ORANGE = "#FF8800"  # 部分正确/警告
    BLUE = "#0066FF"  # 信息/讲解
    PURPLE = "#9900FF"  # 重要提示


@dataclass
class BoundingBox:
    """
    边界框坐标（归一化坐标 0.0-1.0）

    坐标原点在图片左上角，x 向右增加，y 向下增加
    """

    x_min: float  # 左边界 (0.0-1.0)
    y_min: float  # 上边界 (0.0-1.0)
    x_max: float  # 右边界 (0.0-1.0)
    y_max: float  # 下边界 (0.0-1.0)

    def to_dict(self) -> Dict[str, float]:
        return {
            "x_min": self.x_min,
            "y_min": self.y_min,
            "x_max": self.x_max,
            "y_max": self.y_max,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BoundingBox":
        return cls(
            x_min=float(data.get("x_min") or data.get("xmin") or data.get("xMin") or 0),
            y_min=float(data.get("y_min") or data.get("ymin") or data.get("yMin") or 0),
            x_max=float(data.get("x_max") or data.get("xmax") or data.get("xMax") or 0),
            y_max=float(data.get("y_max") or data.get("ymax") or data.get("yMax") or 0),
        )

    def to_pixel_coords(self, image_width: int, image_height: int) -> Dict[str, int]:
        """转换为像素坐标"""
        return {
            "x_min": int(self.x_min * image_width),
            "y_min": int(self.y_min * image_height),
            "x_max": int(self.x_max * image_width),
            "y_max": int(self.y_max * image_height),
        }

    @property
    def center(self) -> tuple:
        """返回中心点坐标"""
        return ((self.x_min + self.x_max) / 2, (self.y_min + self.y_max) / 2)

    @property
    def width(self) -> float:
        return self.x_max - self.x_min

    @property
    def height(self) -> float:
        return self.y_max - self.y_min


@dataclass
class Point:
    """点坐标（归一化坐标 0.0-1.0）"""

    x: float
    y: float

    def to_dict(self) -> Dict[str, float]:
        return {"x": self.x, "y": self.y}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Point":
        return cls(
            x=float(data.get("x") or 0),
            y=float(data.get("y") or 0),
        )

    def to_pixel_coords(self, image_width: int, image_height: int) -> Dict[str, int]:
        return {
            "x": int(self.x * image_width),
            "y": int(self.y * image_height),
        }


@dataclass
class VisualAnnotation:
    """
    视觉批注

    表示一个批注元素，包含类型、位置、内容等信息
    """

    annotation_type: AnnotationType  # 批注类型
    bounding_box: BoundingBox  # 位置区域

    # 可选字段
    text: str = ""  # 批注文字（分数、评语等）
    color: str = AnnotationColor.RED.value  # 颜色
    confidence: float = 1.0  # 位置置信度

    # 关联信息
    question_id: str = ""  # 关联的题目 ID
    scoring_point_id: str = ""  # 关联的得分点 ID

    # 箭头专用
    arrow_end: Optional[Point] = None  # 箭头终点（如果是箭头类型）

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "annotation_type": (
                self.annotation_type.value
                if isinstance(self.annotation_type, AnnotationType)
                else self.annotation_type
            ),
            "bounding_box": self.bounding_box.to_dict(),
            "text": self.text,
            "color": self.color,
            "confidence": self.confidence,
            "question_id": self.question_id,
            "scoring_point_id": self.scoring_point_id,
            "metadata": self.metadata,
        }
        if self.arrow_end:
            result["arrow_end"] = self.arrow_end.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VisualAnnotation":
        annotation_type = data.get("annotation_type") or data.get("type") or "comment"
        if isinstance(annotation_type, str):
            try:
                annotation_type = AnnotationType(annotation_type)
            except ValueError:
                annotation_type = AnnotationType.COMMENT

        arrow_end = None
        if data.get("arrow_end"):
            arrow_end = Point.from_dict(data["arrow_end"])

        return cls(
            annotation_type=annotation_type,
            bounding_box=BoundingBox.from_dict(
                data.get("bounding_box") or data.get("boundingBox") or {}
            ),
            text=data.get("text") or data.get("message") or "",
            color=data.get("color") or AnnotationColor.RED.value,
            confidence=float(data.get("confidence") or 1.0),
            question_id=data.get("question_id") or data.get("questionId") or "",
            scoring_point_id=data.get("scoring_point_id") or data.get("scoringPointId") or "",
            arrow_end=arrow_end,
            metadata=data.get("metadata") or {},
        )


@dataclass
class PageAnnotations:
    """
    单页批注集合

    包含一个页面上的所有批注
    """

    page_index: int  # 页码
    image_width: int = 0  # 原图宽度（像素）
    image_height: int = 0  # 原图高度（像素）
    annotations: List[VisualAnnotation] = field(default_factory=list)

    # 汇总信息
    total_score: float = 0.0  # 该页总分
    max_score: float = 0.0  # 该页满分

    def to_dict(self) -> Dict[str, Any]:
        return {
            "page_index": self.page_index,
            "image_width": self.image_width,
            "image_height": self.image_height,
            "annotations": [a.to_dict() for a in self.annotations],
            "total_score": self.total_score,
            "max_score": self.max_score,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PageAnnotations":
        return cls(
            page_index=data.get("page_index") or data.get("pageIndex") or 0,
            image_width=data.get("image_width") or data.get("imageWidth") or 0,
            image_height=data.get("image_height") or data.get("imageHeight") or 0,
            annotations=[VisualAnnotation.from_dict(a) for a in data.get("annotations") or []],
            total_score=float(data.get("total_score") or data.get("totalScore") or 0),
            max_score=float(data.get("max_score") or data.get("maxScore") or 0),
        )

    def add_score_annotation(
        self,
        score: float,
        max_score: float,
        position: BoundingBox,
        question_id: str = "",
    ) -> None:
        """添加分数批注"""
        color = (
            AnnotationColor.GREEN.value
            if score >= max_score * 0.8
            else (
                AnnotationColor.ORANGE.value
                if score >= max_score * 0.5
                else AnnotationColor.RED.value
            )
        )
        self.annotations.append(
            VisualAnnotation(
                annotation_type=AnnotationType.SCORE,
                bounding_box=position,
                text=f"{score}/{max_score}",
                color=color,
                question_id=question_id,
            )
        )

    def add_error_circle(
        self,
        position: BoundingBox,
        message: str = "",
        question_id: str = "",
        scoring_point_id: str = "",
    ) -> None:
        """添加错误圈选"""
        self.annotations.append(
            VisualAnnotation(
                annotation_type=AnnotationType.ERROR_CIRCLE,
                bounding_box=position,
                text=message,
                color=AnnotationColor.RED.value,
                question_id=question_id,
                scoring_point_id=scoring_point_id,
            )
        )

    def add_comment(
        self,
        position: BoundingBox,
        text: str,
        color: str = AnnotationColor.BLUE.value,
        question_id: str = "",
    ) -> None:
        """添加文字批注"""
        self.annotations.append(
            VisualAnnotation(
                annotation_type=AnnotationType.COMMENT,
                bounding_box=position,
                text=text,
                color=color,
                question_id=question_id,
            )
        )

    def add_check_mark(
        self,
        position: BoundingBox,
        is_correct: bool = True,
        is_partial: bool = False,
        question_id: str = "",
    ) -> None:
        """添加勾选/叉号标记"""
        if is_correct:
            ann_type = AnnotationType.CORRECT_CHECK
            color = AnnotationColor.GREEN.value
        elif is_partial:
            ann_type = AnnotationType.PARTIAL_CHECK
            color = AnnotationColor.ORANGE.value
        else:
            ann_type = AnnotationType.WRONG_CROSS
            color = AnnotationColor.RED.value

        self.annotations.append(
            VisualAnnotation(
                annotation_type=ann_type,
                bounding_box=position,
                color=color,
                question_id=question_id,
            )
        )


@dataclass
class GradingAnnotationResult:
    """
    完整的批改批注结果

    包含所有页面的批注信息
    """

    submission_id: str
    pages: List[PageAnnotations] = field(default_factory=list)

    # 汇总
    total_score: float = 0.0
    max_total_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "submission_id": self.submission_id,
            "pages": [p.to_dict() for p in self.pages],
            "total_score": self.total_score,
            "max_total_score": self.max_total_score,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GradingAnnotationResult":
        return cls(
            submission_id=data.get("submission_id") or data.get("submissionId") or "",
            pages=[PageAnnotations.from_dict(p) for p in data.get("pages") or []],
            total_score=float(data.get("total_score") or data.get("totalScore") or 0),
            max_total_score=float(data.get("max_total_score") or data.get("maxTotalScore") or 0),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "GradingAnnotationResult":
        return cls.from_dict(json.loads(json_str))


# 导出
__all__ = [
    "AnnotationType",
    "AnnotationColor",
    "BoundingBox",
    "Point",
    "VisualAnnotation",
    "PageAnnotations",
    "GradingAnnotationResult",
]
