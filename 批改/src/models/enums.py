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
