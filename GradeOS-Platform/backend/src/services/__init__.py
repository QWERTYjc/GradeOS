"""服务层模块"""

from src.services.cache import CacheService
from src.services.rate_limiter import RateLimiter
from src.services.layout_analysis import LayoutAnalysisService
from src.services.llm_reasoning import LLMReasoningClient
from src.services.multi_layer_cache import MultiLayerCacheService, CacheStrategy
from src.services.distributed_transaction import (
    DistributedTransactionCoordinator,
    SagaStep,
    SagaStepStatus,
    SagaTransactionStatus,
    SagaTransaction,
    ReviewOverrideSagaBuilder,
)
# grading_confession 已删除（批改和审计一体化改造）
from src.services.student_summary import generate_student_summary, generate_class_summary

# 批注批改服务
from src.services.annotation_grading import AnnotationGradingService, AnnotationGradingConfig
from src.services.annotation_renderer import (
    AnnotationRenderer,
    RenderConfig,
    render_annotations_on_image,
)

# 后处理批注生成器
from src.services.post_grading_annotator import (
    PostGradingAnnotator,
    AnnotatorConfig,
    AnnotationMode,
    create_annotator_for_mode,
)


__all__ = [
    "CacheService",
    "RateLimiter",
    "LayoutAnalysisService",
    "LLMReasoningClient",
    "MultiLayerCacheService",
    "CacheStrategy",
    "DistributedTransactionCoordinator",
    "SagaStep",
    "SagaStepStatus",
    "SagaTransactionStatus",
    "SagaTransaction",
    "ReviewOverrideSagaBuilder",
    # Student and class summary
    "generate_student_summary",
    "generate_class_summary",
    # 批注批改服务
    "AnnotationGradingService",
    "AnnotationGradingConfig",
    "AnnotationRenderer",
    "RenderConfig",
    "render_annotations_on_image",
    # 后处理批注生成器
    "PostGradingAnnotator",
    "AnnotatorConfig",
    "AnnotationMode",
    "create_annotator_for_mode",
]
