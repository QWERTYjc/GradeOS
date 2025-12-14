"""Temporal Activities 模块

包含所有 Temporal Activity 定义，用于分布式工作流编排。
"""

from .segment import segment_document_activity
from .grade import grade_question_activity
from .notify import notify_teacher_activity
from .persist import persist_results_activity


__all__ = [
    "segment_document_activity",
    "grade_question_activity",
    "notify_teacher_activity",
    "persist_results_activity"
]
