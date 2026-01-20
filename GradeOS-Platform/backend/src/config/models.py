"""Global model configuration.

Default model routes to OpenRouter model names.
"""

import os

# Default model (OpenRouter-compatible name).
MODEL = os.getenv("LLM_DEFAULT_MODEL", "google/gemini-3-flash-preview")
INDEX_MODEL = os.getenv("LLM_INDEX_MODEL", MODEL)
FLASH_MODEL = os.getenv("LLM_FLASH_MODEL", MODEL)


def get_model() -> str:
    """Return the default model name."""
    return MODEL


def get_default_model() -> str:
    """Return the default model name (legacy accessor)."""
    return get_model()


def get_lite_model() -> str:
    """Return the lightweight model name (legacy accessor)."""
    return get_model()


def get_cache_model() -> str:
    """Return the cache model name (legacy accessor)."""
    return get_model()


def get_index_model() -> str:
    """Return the index model name."""
    return INDEX_MODEL


def get_flash_model() -> str:
    """Return the flash model name."""
    return FLASH_MODEL


def get_model_for_task(task_type: str) -> str:
    """Return a model name for a task type (legacy accessor)."""
    return get_model()
