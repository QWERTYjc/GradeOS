"""数据模型包"""

from .enums import FileType, SubmissionStatus, ReviewAction, QuestionType
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
from .prompt import PromptSection, AssembledPrompt
from .calibration import (
    ToleranceRule,
    CalibrationProfile,
    CalibrationProfileCreateRequest,
    CalibrationProfileUpdateRequest,
)

# 批改工作流优化数据模型
from .grading_models import (
    ScoringPoint as WorkflowScoringPoint,
    AlternativeSolution,
    QuestionRubric,
    ScoringPointResult,
    QuestionResult,
    StudentInfo,
    PageGradingResult,
    StudentResult,
    CrossPageQuestion,
    BatchGradingResult,
    ErrorLog,
)

# 批注坐标模型
from .annotation import (
    AnnotationType,
    AnnotationColor,
    BoundingBox as AnnotationBoundingBox,
    Point,
    VisualAnnotation,
    PageAnnotations,
    GradingAnnotationResult,
)

__all__ = [
    # 枚举
    "FileType",
    "SubmissionStatus",
    "ReviewAction",
    "QuestionType",
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
    # 提示词
    "PromptSection",
    "AssembledPrompt",
    # 校准配置
    "ToleranceRule",
    "CalibrationProfile",
    "CalibrationProfileCreateRequest",
    "CalibrationProfileUpdateRequest",
    # 批改工作流优化数据模型
    "WorkflowScoringPoint",
    "AlternativeSolution",
    "QuestionRubric",
    "ScoringPointResult",
    "QuestionResult",
    "StudentInfo",
    "PageGradingResult",
    "StudentResult",
    "CrossPageQuestion",
    "BatchGradingResult",
    "ErrorLog",
    # 批注坐标模型
    "AnnotationType",
    "AnnotationColor",
    "AnnotationBoundingBox",
    "Point",
    "VisualAnnotation",
    "PageAnnotations",
    "GradingAnnotationResult",
]
