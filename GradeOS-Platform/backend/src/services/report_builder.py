"""辅助批改报告构建器

汇总分析结果，生成结构化报告。
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from src.models.assistant_models import (
    AnalysisReport,
    ReportMetadata,
    ReportSummary,
    ActionPlan,
    UnderstandingResult,
    ErrorRecord,
    Suggestion,
    DeepAnalysisResult,
    LearningRecommendation,
    DifficultyLevel,
    Severity,
)


logger = logging.getLogger(__name__)


# ==================== 报告构建器 ====================


class ReportBuilder:
    """报告构建器"""

    def build_report(
        self,
        analysis_id: str,
        understanding: UnderstandingResult,
        errors: List[ErrorRecord],
        suggestions: List[Suggestion],
        deep_analysis: DeepAnalysisResult,
        submission_id: Optional[str] = None,
        student_id: Optional[str] = None,
        subject: Optional[str] = None,
        created_at: Optional[datetime] = None,
    ) -> AnalysisReport:
        """
        构建完整的分析报告

        Args:
            analysis_id: 分析任务 ID
            understanding: 理解分析结果
            errors: 错误列表
            suggestions: 建议列表
            deep_analysis: 深度分析结果
            submission_id: 提交 ID（可选）
            student_id: 学生 ID（可选）
            subject: 科目（可选）
            created_at: 创建时间（可选）

        Returns:
            完整的分析报告
        """
        try:
            logger.info(f"[ReportBuilder] 开始构建报告: analysis_id={analysis_id}")

            # 构建元数据
            metadata = ReportMetadata(
                analysis_id=analysis_id,
                submission_id=submission_id,
                student_id=student_id,
                subject=subject,
                created_at=created_at or datetime.now(),
                completed_at=datetime.now(),
                version="1.0",
            )

            # 构建摘要
            summary = self._build_summary(understanding, errors, suggestions, deep_analysis)

            # 构建行动计划
            action_plan = self._build_action_plan(errors, suggestions, deep_analysis)

            # 构建完整报告
            report = AnalysisReport(
                metadata=metadata,
                summary=summary,
                understanding=understanding,
                errors=errors,
                suggestions=suggestions,
                deep_analysis=deep_analysis,
                action_plan=action_plan,
                visualizations=None,  # TODO: 实现可视化
            )

            logger.info(f"[ReportBuilder] 报告构建完成: analysis_id={analysis_id}")

            return report

        except Exception as e:
            logger.error(f"[ReportBuilder] 报告构建失败: {e}", exc_info=True)
            raise

    def _build_summary(
        self,
        understanding: UnderstandingResult,
        errors: List[ErrorRecord],
        suggestions: List[Suggestion],
        deep_analysis: DeepAnalysisResult,
    ) -> ReportSummary:
        """构建报告摘要"""

        # 统计高严重度错误
        high_severity_errors = sum(1 for err in errors if err.severity == Severity.HIGH)

        # 估算完成时间
        estimated_time = understanding.estimated_time_minutes or 0

        return ReportSummary(
            overall_score=deep_analysis.overall_score,
            total_errors=len(errors),
            high_severity_errors=high_severity_errors,
            total_suggestions=len(suggestions),
            estimated_completion_time_minutes=estimated_time,
            actual_difficulty=understanding.difficulty_level,
        )

    def _build_action_plan(
        self,
        errors: List[ErrorRecord],
        suggestions: List[Suggestion],
        deep_analysis: DeepAnalysisResult,
    ) -> ActionPlan:
        """构建行动计划"""

        # 立即行动（高优先级建议）
        immediate_actions = [
            sugg.description for sugg in suggestions if sugg.priority == Severity.HIGH
        ][
            :3
        ]  # 最多 3 个

        # 短期目标（中优先级建议）
        short_term_goals = [
            sugg.description for sugg in suggestions if sugg.priority == Severity.MEDIUM
        ][:3]

        # 长期目标（学习建议）
        long_term_goals = [rec.description for rec in deep_analysis.learning_recommendations][:3]

        return ActionPlan(
            immediate_actions=immediate_actions,
            short_term_goals=short_term_goals,
            long_term_goals=long_term_goals,
        )


# ==================== 便捷函数 ====================


def build_report(
    analysis_id: str,
    understanding: UnderstandingResult,
    errors: List[ErrorRecord],
    suggestions: List[Suggestion],
    deep_analysis: DeepAnalysisResult,
    submission_id: Optional[str] = None,
    student_id: Optional[str] = None,
    subject: Optional[str] = None,
) -> AnalysisReport:
    """
    便捷函数：构建报告

    Args:
        analysis_id: 分析任务 ID
        understanding: 理解分析结果
        errors: 错误列表
        suggestions: 建议列表
        deep_analysis: 深度分析结果
        submission_id: 提交 ID（可选）
        student_id: 学生 ID（可选）
        subject: 科目（可选）

    Returns:
        完整的分析报告
    """
    builder = ReportBuilder()
    return builder.build_report(
        analysis_id=analysis_id,
        understanding=understanding,
        errors=errors,
        suggestions=suggestions,
        deep_analysis=deep_analysis,
        submission_id=submission_id,
        student_id=student_id,
        subject=subject,
    )
