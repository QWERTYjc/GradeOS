"""工具函数模块"""

from src.utils.coordinates import (
    normalize_coordinates,
    denormalize_coordinates,
)
from src.utils.hashing import (
    compute_image_hash,
    compute_rubric_hash,
    compute_cache_key,
)
from src.utils.checkpoint import (
    create_checkpointer,
    get_thread_id,
)
from src.utils.pool_manager import (
    UnifiedPoolManager,
    PoolConfig,
    PoolError,
    ConnectionTimeoutError,
    PoolExhaustedError,
    PoolNotInitializedError,
    get_pool_manager,
    init_pool_manager,
)
from src.utils.enhanced_checkpointer import (
    EnhancedPostgresCheckpointer,
    CheckpointSaveError,
    CheckpointRecoveryError,
    ManualInterventionRequired,
)

__all__ = [
    "normalize_coordinates",
    "denormalize_coordinates",
    "compute_image_hash",
    "compute_rubric_hash",
    "compute_cache_key",
    "create_checkpointer",
    "get_thread_id",
    # 连接池管理
    "UnifiedPoolManager",
    "PoolConfig",
    "PoolError",
    "ConnectionTimeoutError",
    "PoolExhaustedError",
    "PoolNotInitializedError",
    "get_pool_manager",
    "init_pool_manager",
    # 增强型检查点器
    "EnhancedPostgresCheckpointer",
    "CheckpointSaveError",
    "CheckpointRecoveryError",
    "ManualInterventionRequired",
]
