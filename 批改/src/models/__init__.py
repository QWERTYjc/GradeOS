"""数据模型包"""

from .enums import FileType, SubmissionStatus, ReviewAction, QuestionType
from .submission import (
    SubmissionRequest,
    SubmissionResponse,
    SubmissionStatusResponse,
)
from .region import BoundingBox, QuestionRegion, SegmentationResult
from .grading import GradingResult, RubricMappingItem, ExamPaperResult
from .state import (
    GradingState,
    WorkflowInput,
    QuestionGradingInput,
    ContextPack,
    EvidenceItem,
)
from .rubric import (
    ScoringPoint,
    Rubric,
    RubricCreateRequest,
    RubricUpdateRequest,
)
from .review import ReviewSignal, PendingReview
from .prompt import PromptSection, AssembledPrompt
from .calibration import (
    ToleranceRule,
    CalibrationProfile,
    CalibrationProfileCreateRequest,
    CalibrationProfileUpdateRequest,
)

__all__ = [
    # 枚举
    "FileType",
    "SubmissionStatus",
    "ReviewAction",
    "QuestionType",
    # 提交
    "SubmissionRequest",
    "SubmissionResponse",
    "SubmissionStatusResponse",
    # 区域
    "BoundingBox",
    "QuestionRegion",
    "SegmentationResult",
    # 批改
    "GradingResult",
    "RubricMappingItem",
    "ExamPaperResult",
    # 状态
    "GradingState",
    "WorkflowInput",
    "QuestionGradingInput",
    "ContextPack",
    "EvidenceItem",
    # 评分细则
    "ScoringPoint",
    "Rubric",
    "RubricCreateRequest",
    "RubricUpdateRequest",
    # 审核
    "ReviewSignal",
    "PendingReview",
    # 提示词
    "PromptSection",
    "AssembledPrompt",
    # 校准配置
    "ToleranceRule",
    "CalibrationProfile",
    "CalibrationProfileCreateRequest",
    "CalibrationProfileUpdateRequest",
]
