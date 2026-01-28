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
from src.services.grading_self_report import generate_self_report, generate_student_self_report
from src.services.student_summary import generate_student_summary, generate_class_summary
# 批注批改服务
from src.services.annotation_grading import AnnotationGradingService, AnnotationGradingConfig
from src.services.annotation_renderer import AnnotationRenderer, RenderConfig, render_annotations_on_image
# 后处理批注生成器
from src.services.post_grading_annotator import (
    PostGradingAnnotator,
    AnnotatorConfig,
    AnnotationMode,
    create_annotator_for_mode,
)
# 批改记忆系统
from src.services.grading_memory import (
    GradingMemoryService,
    MemoryType,
    MemoryImportance,
    MemoryEntry,
    get_memory_service,
    init_memory_service_with_db,
    reset_memory_service,
)
# 记忆存储后端
from src.services.memory_storage import (
    MemoryStorageBackend,
    InMemoryStorageBackend,
    RedisStorageBackend,
    PostgresStorageBackend,
    MultiLayerStorageBackend,
    create_storage_backend,
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
    # Self Report
    "generate_self_report",
    "generate_student_self_report",
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
    # 批改记忆系统
    "GradingMemoryService",
    "MemoryType",
    "MemoryImportance",
    "MemoryEntry",
    "get_memory_service",
    "init_memory_service_with_db",
    "reset_memory_service",
    # 记忆存储后端
    "MemoryStorageBackend",
    "InMemoryStorageBackend",
    "RedisStorageBackend",
    "PostgresStorageBackend",
    "MultiLayerStorageBackend",
    "create_storage_backend",
]

