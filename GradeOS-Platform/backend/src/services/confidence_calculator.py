"""置信度计算服务

实现评分置信度的计算逻辑，考虑：
1. 评分标准引用质量
2. 另类解法的影响
3. 得分点加权平均

设计原则：
- 有精确引用：base 0.9
- 部分引用：base * 0.9
- 无引用：min(base, 0.7)
- 另类解法：再降 25%

Requirements: 评分标准引用与记忆系统优化
"""

from typing import List, Optional, TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from ..models.grading_models import ScoringPointResult, QuestionResult


# 置信度计算常量
BASE_CONFIDENCE = 0.9  # 基础置信度
PARTIAL_CITATION_FACTOR = 0.9  # 部分引用系数
NO_CITATION_MAX = 0.7  # 无引用上限
ALTERNATIVE_SOLUTION_FACTOR = 0.75  # 另类解法系数


def calculate_point_confidence(
    has_rubric_reference: bool,
    citation_quality: str = "exact",
    is_alternative_solution: bool = False,
    base_confidence: float = BASE_CONFIDENCE,
) -> float:
    """
    计算单个得分点的置信度

    规则：
    1. 有精确引用：base_confidence (0.9)
    2. 有部分引用：base_confidence * 0.9 (0.81)
    3. 无引用：min(base_confidence, 0.7)
    4. 另类解法：再降低 25%

    Args:
        has_rubric_reference: 是否有评分标准引用
        citation_quality: 引用质量 (exact/partial/none)
        is_alternative_solution: 是否为另类解法
        base_confidence: 基础置信度

    Returns:
        float: 计算后的置信度 (0.0 - 1.0)

    属性 P1: 置信度计算正确性
    - 如果 rubric_reference 为 null，则 point_confidence <= 0.7
    - 如果 is_alternative_solution 为 true，则 point_confidence <= 0.75
    - point_confidence 始终在 [0, 1] 范围内
    """
    confidence = base_confidence

    # 根据引用质量调整
    if not has_rubric_reference or citation_quality == "none":
        confidence = min(confidence, NO_CITATION_MAX)
    elif citation_quality == "partial":
        confidence *= PARTIAL_CITATION_FACTOR
    # exact 保持原值

    # 另类解法降低置信度
    if is_alternative_solution:
        confidence *= ALTERNATIVE_SOLUTION_FACTOR

    # 确保在有效范围内
    return round(max(0.0, min(1.0, confidence)), 3)


def calculate_question_confidence(
    point_results: List["ScoringPointResult"],
) -> float:
    """
    计算题目整体置信度（加权平均）

    权重 = 得分点分值 / 总分值

    Args:
        point_results: 得分点结果列表

    Returns:
        float: 题目整体置信度 (0.0 - 1.0)
    """
    if not point_results:
        return 0.5  # 无得分点时返回中等置信度

    total_weight = sum(p.scoring_point.score for p in point_results)

    if total_weight == 0:
        # 所有得分点分值为0，使用简单平均
        return round(sum(p.point_confidence for p in point_results) / len(point_results), 3)

    # 加权平均
    weighted_sum = sum(p.point_confidence * p.scoring_point.score for p in point_results)
    return round(weighted_sum / total_weight, 3)


def calculate_student_confidence(
    question_results: List["QuestionResult"],
) -> float:
    """
    计算学生整体置信度（加权平均）

    权重 = 题目满分 / 总满分

    Args:
        question_results: 题目结果列表

    Returns:
        float: 学生整体置信度 (0.0 - 1.0)
    """
    if not question_results:
        return 0.5

    total_max_score = sum(q.max_score for q in question_results)

    if total_max_score == 0:
        return round(sum(q.confidence for q in question_results) / len(question_results), 3)

    weighted_sum = sum(q.confidence * q.max_score for q in question_results)
    return round(weighted_sum / total_max_score, 3)


def update_point_confidence(
    point_result: "ScoringPointResult",
) -> "ScoringPointResult":
    """
    根据得分点结果的字段更新其置信度

    Args:
        point_result: 得分点结果

    Returns:
        ScoringPointResult: 更新后的得分点结果（原地修改）
    """
    point_result.point_confidence = calculate_point_confidence(
        has_rubric_reference=point_result.rubric_reference is not None,
        citation_quality=point_result.citation_quality,
        is_alternative_solution=point_result.is_alternative_solution,
    )
    return point_result


@dataclass
class ConfidenceReport:
    """置信度报告"""

    overall_confidence: float
    low_confidence_points: List[str]  # 低置信度得分点ID列表
    alternative_solution_count: int
    no_citation_count: int

    @property
    def needs_review(self) -> bool:
        """是否需要人工复核"""
        return (
            self.overall_confidence < 0.7
            or len(self.low_confidence_points) > 0
            or self.alternative_solution_count > 0
        )


def generate_confidence_report(
    point_results: List["ScoringPointResult"],
    question_id: str = "",
) -> ConfidenceReport:
    """
    生成置信度报告

    Args:
        point_results: 得分点结果列表
        question_id: 题目ID（用于生成得分点ID）

    Returns:
        ConfidenceReport: 置信度报告
    """
    low_confidence_points = []
    alternative_solution_count = 0
    no_citation_count = 0

    for i, pr in enumerate(point_results):
        point_id = pr.scoring_point.point_id or f"{question_id}.{i+1}"

        if pr.point_confidence < 0.7:
            low_confidence_points.append(point_id)

        if pr.is_alternative_solution:
            alternative_solution_count += 1

        if pr.rubric_reference is None or pr.citation_quality == "none":
            no_citation_count += 1

    overall_confidence = calculate_question_confidence(point_results)

    return ConfidenceReport(
        overall_confidence=overall_confidence,
        low_confidence_points=low_confidence_points,
        alternative_solution_count=alternative_solution_count,
        no_citation_count=no_citation_count,
    )
