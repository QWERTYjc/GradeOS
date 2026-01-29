"""枚举类型定义"""

from enum import Enum


class FileType(str, Enum):
    """文件类型"""

    PDF = "pdf"
    IMAGE = "image"


class SubmissionStatus(str, Enum):
    """提交状态"""

    UPLOADED = "UPLOADED"
    SEGMENTING = "SEGMENTING"
    GRADING = "GRADING"
    REVIEWING = "REVIEWING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"


class ReviewAction(str, Enum):
    """审核操作"""

    APPROVE = "APPROVE"
    OVERRIDE = "OVERRIDE"
    REJECT = "REJECT"


class QuestionType(str, Enum):
    """题目类型枚举

    用于 SupervisorAgent 分析题型并选择合适的批改智能体
    """

    OBJECTIVE = "objective"  # 选择题/判断题
    STEPWISE = "stepwise"  # 计算题（数学、物理等）
    ESSAY = "essay"  # 作文/简答题
    LAB_DESIGN = "lab_design"  # 实验设计题
    UNKNOWN = "unknown"  # 未知题型（需要人工审核）
