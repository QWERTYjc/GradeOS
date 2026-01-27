"""后处理批注生成器

基于批改结果（包括自白和逻辑复核后的修正）智能生成批注。

设计原则：
1. 在所有批改流程完成后生成批注，确保批注反映最终结果
2. 智能选择批注类型，适应各种批改场景
3. 支持多种标注模式：简洁模式（只打勾）、详细模式（分数+说明）
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

from src.models.annotation import (
    AnnotationType,
    AnnotationColor,
    BoundingBox,
    VisualAnnotation,
    PageAnnotations,
    GradingAnnotationResult,
)


logger = logging.getLogger(__name__)


class AnnotationMode(str, Enum):
    """标注模式"""
    MINIMAL = "minimal"      # 最简模式：只打勾/叉
    SIMPLE = "simple"        # 简洁模式：勾/叉 + 简单分数
    STANDARD = "standard"    # 标准模式：分数 + 标记
    DETAILED = "detailed"    # 详细模式：分数 + M/A mark + 错误圈选 + 评语


@dataclass
class AnnotatorConfig:
    """批注生成器配置"""
    mode: AnnotationMode = AnnotationMode.STANDARD
    
    # 分数显示配置
    show_score_fraction: bool = True      # 是否显示分数（如 "8/10"）
    show_simple_score: bool = True        # 是否显示简单分数（如 "1"）
    show_unit: bool = False               # 是否显示单位（M/A）
    
    # 标记显示配置
    show_check_marks: bool = True         # 是否显示勾/叉
    show_m_a_marks: bool = True           # 是否显示 M/A mark
    show_error_circles: bool = True       # 是否显示错误圈选
    show_comments: bool = True            # 是否显示评语批注
    
    # 颜色配置
    correct_color: str = "#00AA00"        # 正确 - 绿色
    wrong_color: str = "#FF0000"          # 错误 - 红色
    partial_color: str = "#FF8800"        # 部分正确 - 橙色
    comment_color: str = "#0066FF"        # 评语 - 蓝色


class PostGradingAnnotator:
    """
    后处理批注生成器
    
    在批改流程（包括自白和逻辑复核）完成后，基于最终结果生成批注。
    """
    
    def __init__(self, config: Optional[AnnotatorConfig] = None):
        self.config = config or AnnotatorConfig()
    
    def generate_annotations_for_student(
        self,
        student_result: Dict[str, Any],
        page_images: Optional[List[bytes]] = None,
    ) -> GradingAnnotationResult:
        """
        为单个学生生成完整的批注结果
        
        Args:
            student_result: 学生批改结果（包含逻辑复核后的修正）
            page_images: 页面图片列表（用于获取图片尺寸，可选）
            
        Returns:
            GradingAnnotationResult: 完整的批注结果
        """
        submission_id = student_result.get("student_key") or student_result.get("submission_id") or ""
        result = GradingAnnotationResult(submission_id=submission_id)
        
        # 获取题目详情
        question_details = student_result.get("question_details") or []
        
        # 按页面分组题目
        page_questions: Dict[int, List[Dict[str, Any]]] = {}
        for q in question_details:
            source_pages = q.get("source_pages") or q.get("page_indices") or [0]
            for page_idx in source_pages:
                if page_idx not in page_questions:
                    page_questions[page_idx] = []
                page_questions[page_idx].append(q)
        
        # 为每个页面生成批注
        for page_idx, questions in sorted(page_questions.items()):
            page_annotations = self._generate_page_annotations(
                page_index=page_idx,
                questions=questions,
            )
            result.pages.append(page_annotations)
            result.total_score += page_annotations.total_score
            result.max_total_score += page_annotations.max_score
        
        return result
    
    def _generate_page_annotations(
        self,
        page_index: int,
        questions: List[Dict[str, Any]],
    ) -> PageAnnotations:
        """
        为单个页面生成批注
        
        Args:
            page_index: 页码
            questions: 该页涉及的题目列表
            
        Returns:
            PageAnnotations: 页面批注
        """
        page_annotations = PageAnnotations(page_index=page_index)
        
        total_score = 0.0
        max_score = 0.0
        
        for q in questions:
            question_id = str(q.get("question_id") or q.get("id") or "")
            q_score = float(q.get("score") or 0)
            q_max_score = float(q.get("max_score") or 0)
            
            total_score += q_score
            max_score += q_max_score
            
            # 生成该题的批注
            annotations = self._generate_question_annotations(q, page_index)
            page_annotations.annotations.extend(annotations)
        
        page_annotations.total_score = total_score
        page_annotations.max_score = max_score
        
        return page_annotations
    
    def _generate_question_annotations(
        self,
        question: Dict[str, Any],
        page_index: int,
    ) -> List[VisualAnnotation]:
        """
        为单道题目生成批注
        
        智能选择批注类型：
        1. 有具体分数 → 显示分数
        2. 无具体分数但有正误判断 → 只打勾/叉
        3. 有步骤信息 → 逐步骤标注
        4. 有错误区域 → 圈选错误
        
        Args:
            question: 题目批改结果
            page_index: 页码
            
        Returns:
            List[VisualAnnotation]: 批注列表
        """
        annotations = []
        
        question_id = str(question.get("question_id") or question.get("id") or "")
        score = question.get("score")
        max_score = question.get("max_score")
        is_correct = question.get("is_correct")
        feedback = question.get("feedback") or ""
        
        # 获取坐标信息
        answer_region = question.get("answer_region") or question.get("answerRegion")
        steps = question.get("steps") or []
        scoring_point_results = (
            question.get("scoring_point_results") or 
            question.get("scoringPointResults") or 
            []
        )
        
        # 确定是否有具体分数信息
        has_specific_score = (
            score is not None and 
            max_score is not None and 
            max_score > 0
        )
        
        # ========== 1. 步骤级别标注 ==========
        if steps and self.config.show_check_marks:
            for step in steps:
                step_annotations = self._generate_step_annotations(
                    step, question_id, page_index
                )
                annotations.extend(step_annotations)
        
        # ========== 2. 得分点级别标注 ==========
        if scoring_point_results:
            for spr in scoring_point_results:
                spr_annotations = self._generate_scoring_point_annotations(
                    spr, question_id, page_index, has_specific_score
                )
                annotations.extend(spr_annotations)
        
        # ========== 3. 题目总分标注 ==========
        if answer_region:
            score_annotation = self._generate_score_annotation(
                question_id=question_id,
                score=score,
                max_score=max_score,
                is_correct=is_correct,
                answer_region=answer_region,
                page_index=page_index,
                has_specific_score=has_specific_score,
            )
            if score_annotation:
                annotations.append(score_annotation)
        
        # ========== 4. 错误圈选和评语（详细模式）==========
        if self.config.mode == AnnotationMode.DETAILED:
            # 添加错误圈选
            if self.config.show_error_circles:
                for spr in scoring_point_results:
                    error_region = spr.get("error_region") or spr.get("errorRegion")
                    if error_region and not spr.get("is_correct", True):
                        annotations.append(VisualAnnotation(
                            annotation_type=AnnotationType.ERROR_CIRCLE,
                            bounding_box=BoundingBox.from_dict(error_region),
                            text="",
                            color=self.config.wrong_color,
                            question_id=question_id,
                            scoring_point_id=spr.get("point_id") or "",
                        ))
            
            # 添加评语批注
            if self.config.show_comments and feedback and answer_region:
                # 在答案区域右侧添加评语
                bbox = BoundingBox.from_dict(answer_region)
                comment_bbox = BoundingBox(
                    x_min=min(bbox.x_max + 0.02, 0.95),
                    y_min=bbox.y_min,
                    x_max=min(bbox.x_max + 0.25, 1.0),
                    y_max=min(bbox.y_min + 0.05, 1.0),
                )
                # 截断过长的评语
                short_feedback = feedback[:50] + "..." if len(feedback) > 50 else feedback
                annotations.append(VisualAnnotation(
                    annotation_type=AnnotationType.COMMENT,
                    bounding_box=comment_bbox,
                    text=short_feedback,
                    color=self.config.comment_color,
                    question_id=question_id,
                ))
        
        return annotations
    
    def _generate_step_annotations(
        self,
        step: Dict[str, Any],
        question_id: str,
        page_index: int,
    ) -> List[VisualAnnotation]:
        """
        为单个步骤生成批注
        
        Args:
            step: 步骤信息
            question_id: 题目 ID
            page_index: 页码
            
        Returns:
            List[VisualAnnotation]: 步骤批注列表
        """
        annotations = []
        
        step_region = step.get("step_region") or step.get("stepRegion")
        if not step_region:
            return annotations
        
        is_correct = step.get("is_correct", True)
        mark_type = step.get("mark_type") or "M"
        mark_value = step.get("mark_value")
        step_id = step.get("step_id") or ""
        
        bbox = BoundingBox.from_dict(step_region)
        
        # 在步骤右侧添加标记
        mark_bbox = BoundingBox(
            x_min=min(bbox.x_max + 0.01, 0.95),
            y_min=bbox.y_min,
            x_max=min(bbox.x_max + 0.06, 1.0),
            y_max=bbox.y_max,
        )
        
        # 根据模式选择标注类型
        if self.config.mode == AnnotationMode.MINIMAL:
            # 最简模式：只打勾/叉
            annotations.append(VisualAnnotation(
                annotation_type=AnnotationType.SIMPLE_CHECK if is_correct else AnnotationType.SIMPLE_CROSS,
                bounding_box=mark_bbox,
                text="",
                color=self.config.correct_color if is_correct else self.config.wrong_color,
                question_id=question_id,
                scoring_point_id=step_id,
            ))
        
        elif self.config.mode == AnnotationMode.SIMPLE:
            # 简洁模式：勾/叉 + 简单分数
            annotations.append(VisualAnnotation(
                annotation_type=AnnotationType.STEP_CHECK if is_correct else AnnotationType.STEP_CROSS,
                bounding_box=mark_bbox,
                text="",
                color=self.config.correct_color if is_correct else self.config.wrong_color,
                question_id=question_id,
                scoring_point_id=step_id,
            ))
            
            # 如果有分数，添加简单分数标注
            if mark_value is not None and mark_value > 0:
                score_bbox = BoundingBox(
                    x_min=min(mark_bbox.x_max + 0.01, 0.95),
                    y_min=mark_bbox.y_min,
                    x_max=min(mark_bbox.x_max + 0.05, 1.0),
                    y_max=mark_bbox.y_max,
                )
                annotations.append(VisualAnnotation(
                    annotation_type=AnnotationType.SIMPLE_SCORE,
                    bounding_box=score_bbox,
                    text=str(int(mark_value)) if mark_value == int(mark_value) else str(mark_value),
                    color=self.config.correct_color,
                    question_id=question_id,
                    scoring_point_id=step_id,
                ))
        
        else:
            # 标准/详细模式：M/A mark
            if self.config.show_m_a_marks and mark_type in ["M", "A"]:
                mark_text = f"{mark_type}{mark_value if mark_value is not None else (1 if is_correct else 0)}"
                annotations.append(VisualAnnotation(
                    annotation_type=AnnotationType.M_MARK if mark_type == "M" else AnnotationType.A_MARK,
                    bounding_box=mark_bbox,
                    text=mark_text,
                    color=self.config.correct_color if is_correct else self.config.wrong_color,
                    question_id=question_id,
                    scoring_point_id=step_id,
                ))
            else:
                # 无 M/A 信息时打勾/叉
                annotations.append(VisualAnnotation(
                    annotation_type=AnnotationType.STEP_CHECK if is_correct else AnnotationType.STEP_CROSS,
                    bounding_box=mark_bbox,
                    text="",
                    color=self.config.correct_color if is_correct else self.config.wrong_color,
                    question_id=question_id,
                    scoring_point_id=step_id,
                ))
        
        return annotations
    
    def _generate_scoring_point_annotations(
        self,
        spr: Dict[str, Any],
        question_id: str,
        page_index: int,
        has_specific_score: bool,
    ) -> List[VisualAnnotation]:
        """
        为单个得分点生成批注
        
        Args:
            spr: 得分点结果
            question_id: 题目 ID
            page_index: 页码
            has_specific_score: 是否有具体分数信息
            
        Returns:
            List[VisualAnnotation]: 得分点批注列表
        """
        annotations = []
        
        # 获取坐标
        evidence_region = spr.get("evidence_region") or spr.get("evidenceRegion")
        error_region = spr.get("error_region") or spr.get("errorRegion")
        
        if not evidence_region and not error_region:
            return annotations
        
        point_id = spr.get("point_id") or spr.get("pointId") or ""
        awarded = spr.get("awarded") or spr.get("score") or 0
        max_points = spr.get("max_score") or spr.get("maxScore") or spr.get("max_points") or 0
        mark_type = spr.get("mark_type") or spr.get("markType") or "M"
        is_correct = awarded >= max_points if max_points > 0 else spr.get("is_correct", True)
        
        region = evidence_region or error_region
        bbox = BoundingBox.from_dict(region)
        
        # 在区域右侧添加标记
        mark_bbox = BoundingBox(
            x_min=min(bbox.x_max + 0.01, 0.95),
            y_min=bbox.y_min,
            x_max=min(bbox.x_max + 0.06, 1.0),
            y_max=bbox.y_max,
        )
        
        if self.config.mode == AnnotationMode.MINIMAL:
            # 最简模式：只打勾/叉
            annotations.append(VisualAnnotation(
                annotation_type=AnnotationType.SIMPLE_CHECK if is_correct else AnnotationType.SIMPLE_CROSS,
                bounding_box=mark_bbox,
                text="",
                color=self.config.correct_color if is_correct else self.config.wrong_color,
                question_id=question_id,
                scoring_point_id=point_id,
            ))
        
        elif has_specific_score and awarded > 0:
            # 有分数且得分：显示绿色分数
            annotations.append(VisualAnnotation(
                annotation_type=AnnotationType.SIMPLE_SCORE,
                bounding_box=mark_bbox,
                text=str(int(awarded)) if awarded == int(awarded) else str(awarded),
                color=self.config.correct_color,
                question_id=question_id,
                scoring_point_id=point_id,
            ))
        
        elif has_specific_score and awarded == 0 and max_points > 0:
            # 有分数但未得分：显示叉
            annotations.append(VisualAnnotation(
                annotation_type=AnnotationType.SIMPLE_CROSS,
                bounding_box=mark_bbox,
                text="",
                color=self.config.wrong_color,
                question_id=question_id,
                scoring_point_id=point_id,
            ))
        
        else:
            # 无明确分数：只打勾/叉
            annotations.append(VisualAnnotation(
                annotation_type=AnnotationType.SIMPLE_CHECK if is_correct else AnnotationType.SIMPLE_CROSS,
                bounding_box=mark_bbox,
                text="",
                color=self.config.correct_color if is_correct else self.config.wrong_color,
                question_id=question_id,
                scoring_point_id=point_id,
            ))
        
        return annotations
    
    def _generate_score_annotation(
        self,
        question_id: str,
        score: Optional[float],
        max_score: Optional[float],
        is_correct: Optional[bool],
        answer_region: Dict[str, Any],
        page_index: int,
        has_specific_score: bool,
    ) -> Optional[VisualAnnotation]:
        """
        生成题目总分标注
        
        智能选择标注类型：
        - 有分数：显示分数（如 "8/10" 或 "1"）
        - 无分数但有正误：显示勾/叉
        - 都没有：不生成标注
        
        Args:
            question_id: 题目 ID
            score: 得分
            max_score: 满分
            is_correct: 是否正确
            answer_region: 答案区域坐标
            page_index: 页码
            has_specific_score: 是否有具体分数信息
            
        Returns:
            Optional[VisualAnnotation]: 总分标注，如果无法生成则返回 None
        """
        bbox = BoundingBox.from_dict(answer_region)
        
        # 在答案区域右上角添加总分标注
        score_bbox = BoundingBox(
            x_min=min(bbox.x_max + 0.02, 0.92),
            y_min=bbox.y_min,
            x_max=min(bbox.x_max + 0.08, 1.0),
            y_max=min(bbox.y_min + 0.05, 1.0),
        )
        
        if self.config.mode == AnnotationMode.MINIMAL:
            # 最简模式：只打勾/叉
            if is_correct is not None:
                return VisualAnnotation(
                    annotation_type=AnnotationType.SIMPLE_CHECK if is_correct else AnnotationType.SIMPLE_CROSS,
                    bounding_box=score_bbox,
                    text="",
                    color=self.config.correct_color if is_correct else self.config.wrong_color,
                    question_id=question_id,
                )
            return None
        
        if has_specific_score and score is not None and max_score is not None:
            # 有具体分数
            score_ratio = score / max_score if max_score > 0 else 0
            
            if self.config.show_score_fraction:
                # 显示分数比（如 "8/10"）
                score_text = f"{int(score) if score == int(score) else score}/{int(max_score) if max_score == int(max_score) else max_score}"
            else:
                # 只显示得分（如 "8"）
                score_text = str(int(score)) if score == int(score) else str(score)
            
            # 根据得分比例选择颜色
            if score_ratio >= 1.0:
                color = self.config.correct_color
            elif score_ratio >= 0.6:
                color = self.config.partial_color
            else:
                color = self.config.wrong_color
            
            return VisualAnnotation(
                annotation_type=AnnotationType.TOTAL_SCORE,
                bounding_box=score_bbox,
                text=score_text,
                color=color,
                question_id=question_id,
            )
        
        elif is_correct is not None:
            # 无分数但有正误判断：只打勾/叉
            return VisualAnnotation(
                annotation_type=AnnotationType.SIMPLE_CHECK if is_correct else AnnotationType.SIMPLE_CROSS,
                bounding_box=score_bbox,
                text="",
                color=self.config.correct_color if is_correct else self.config.wrong_color,
                question_id=question_id,
            )
        
        return None
    
    def update_annotations_after_logic_review(
        self,
        original_annotations: GradingAnnotationResult,
        logic_review_corrections: List[Dict[str, Any]],
        student_result: Dict[str, Any],
    ) -> GradingAnnotationResult:
        """
        逻辑复核后更新批注
        
        根据逻辑复核的修正记录，增量更新批注：
        - 分数变化：更新分数标注
        - 新发现错误：添加错误圈选
        - 置信度变化：可能添加不确定标记
        
        Args:
            original_annotations: 原始批注结果
            logic_review_corrections: 逻辑复核修正记录
            student_result: 最新的学生批改结果
            
        Returns:
            GradingAnnotationResult: 更新后的批注结果
        """
        # 如果逻辑复核没有修正，直接返回原始批注
        if not logic_review_corrections:
            return original_annotations
        
        # 重新生成批注（基于最新的 student_result）
        return self.generate_annotations_for_student(student_result)


def create_annotator_for_mode(mode: str) -> PostGradingAnnotator:
    """
    根据模式创建批注生成器
    
    Args:
        mode: 模式名称 ("minimal", "simple", "standard", "detailed")
        
    Returns:
        PostGradingAnnotator: 批注生成器实例
    """
    try:
        annotation_mode = AnnotationMode(mode)
    except ValueError:
        annotation_mode = AnnotationMode.STANDARD
    
    config = AnnotatorConfig(mode=annotation_mode)
    
    # 根据模式调整配置
    if annotation_mode == AnnotationMode.MINIMAL:
        config.show_score_fraction = False
        config.show_simple_score = False
        config.show_unit = False
        config.show_m_a_marks = False
        config.show_error_circles = False
        config.show_comments = False
    
    elif annotation_mode == AnnotationMode.SIMPLE:
        config.show_score_fraction = False
        config.show_simple_score = True
        config.show_unit = False
        config.show_m_a_marks = False
        config.show_error_circles = False
        config.show_comments = False
    
    elif annotation_mode == AnnotationMode.STANDARD:
        config.show_score_fraction = True
        config.show_simple_score = True
        config.show_unit = False
        config.show_m_a_marks = True
        config.show_error_circles = True
        config.show_comments = False
    
    elif annotation_mode == AnnotationMode.DETAILED:
        config.show_score_fraction = True
        config.show_simple_score = True
        config.show_unit = True
        config.show_m_a_marks = True
        config.show_error_circles = True
        config.show_comments = True
    
    return PostGradingAnnotator(config)


# 导出
__all__ = [
    "AnnotationMode",
    "AnnotatorConfig",
    "PostGradingAnnotator",
    "create_annotator_for_mode",
]
