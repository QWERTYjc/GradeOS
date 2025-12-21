"""配置模块"""

from src.config.models import (
    DEFAULT_MODEL,
    LITE_MODEL,
    CACHE_MODEL,
    get_default_model,
    get_lite_model,
    get_cache_model,
    get_model_for_task,
    MODEL_INFO,
    print_model_config,
)

__all__ = [
    "DEFAULT_MODEL",
    "LITE_MODEL",
    "CACHE_MODEL",
    "get_default_model",
    "get_lite_model",
    "get_cache_model",
    "get_model_for_task",
    "MODEL_INFO",
    "print_model_config",
]
