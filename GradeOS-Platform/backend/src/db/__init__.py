"""数据库模块"""

from .sqlite import (
    init_db,
    get_connection,
    # 工作流状态
    WorkflowState,
    save_workflow_state,
    get_workflow_state,
    update_workflow_status,
    # 批改历史
    GradingHistory,
    save_grading_history,
    get_grading_history,
    list_grading_history,
    # 学生结果
    StudentGradingResult,
    save_student_result,
    get_student_results,
)

__all__ = [
    "init_db",
    "get_connection",
    "WorkflowState",
    "save_workflow_state",
    "get_workflow_state",
    "update_workflow_status",
    "GradingHistory",
    "save_grading_history",
    "get_grading_history",
    "list_grading_history",
    "StudentGradingResult",
    "save_student_result",
    "get_student_results",
]
