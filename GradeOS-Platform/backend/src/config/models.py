"""Global model configuration.

Default model routes to OpenRouter model names.
"""

import os

# Default model (OpenRouter-compatible name).
MODEL = os.getenv("LLM_DEFAULT_MODEL", "google/gemini-3-flash-preview")

# Aliases for legacy accessors.
DEFAULT_MODEL = MODEL
LITE_MODEL = MODEL
CACHE_MODEL = MODEL
INDEX_MODEL = os.getenv("LLM_INDEX_MODEL", MODEL)
FLASH_MODEL = os.getenv("LLM_FLASH_MODEL", MODEL)


def get_model() -> str:
    """Return the default model name."""
    return MODEL


def get_default_model() -> str:
    """Return the default model name (legacy accessor)."""
    return MODEL


def get_lite_model() -> str:
    """Return the lightweight model name (legacy accessor)."""
    return MODEL


def get_cache_model() -> str:
    """Return the cache model name (legacy accessor)."""
    return MODEL


def get_index_model() -> str:
    """Return the index model name."""
    return INDEX_MODEL


def get_flash_model() -> str:
    """Return the flash model name."""
    return FLASH_MODEL


def get_model_for_task(task_type: str) -> str:
    """Return a model name for a task type (legacy accessor)."""
    return MODEL


MODEL_INFO = {
    "google/gemini-2.0-flash-exp": {
        "description": "Gemini 2.0 Flash Experimental",
        "supports_vision": True,
        "supports_caching": True,
    },
    "google/gemini-1.5-flash": {
        "description": "Gemini 1.5 Flash",
        "supports_vision": True,
        "supports_caching": True,
    },
}


def print_model_config() -> None:
    """Print current model configuration."""
    print("=" * 50)
    print("Model configuration")
    print("=" * 50)
    print(f"Model: {MODEL}")
    print("=" * 50)
