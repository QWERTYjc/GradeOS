"""LLM configuration (OpenRouter compatible).

Centralizes model routing and API settings for all LLM calls.
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional


class LLMProvider(Enum):
    """LLM provider types."""

    OPENROUTER = "openrouter"


DEFAULT_LLM_MODEL = os.getenv("LLM_DEFAULT_MODEL", "google/gemini-3-flash-preview")


@dataclass
class LLMConfig:
    """LLM configuration."""

    provider: LLMProvider = LLMProvider.OPENROUTER
    api_key: str = ""
    base_url: str = "https://openrouter.ai/api/v1"

    models: Dict[str, str] = field(
        default_factory=lambda: {
            "vision": DEFAULT_LLM_MODEL,
            "text": DEFAULT_LLM_MODEL,
            "summary": DEFAULT_LLM_MODEL,
            "rubric": DEFAULT_LLM_MODEL,
            "analysis": DEFAULT_LLM_MODEL,
            "assistant": DEFAULT_LLM_MODEL,
            "grading": DEFAULT_LLM_MODEL,
            "index": DEFAULT_LLM_MODEL,
            "embedding": os.getenv("LLM_EMBEDDING_MODEL", ""),
        }
    )

    site_url: str = "https://gradeos.app"
    site_title: str = "GradeOS AI Grading"

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Load configuration from environment variables."""
        api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENROUTER_API_KEY", "")
        base_url = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
        default_model = os.getenv("LLM_DEFAULT_MODEL", DEFAULT_LLM_MODEL)

        return cls(
            provider=LLMProvider.OPENROUTER,
            api_key=api_key,
            base_url=base_url,
            models={
                "vision": os.getenv("LLM_VISION_MODEL", default_model),
                "text": os.getenv("LLM_TEXT_MODEL", default_model),
                "summary": os.getenv("LLM_SUMMARY_MODEL", default_model),
                "rubric": os.getenv("LLM_RUBRIC_MODEL", default_model),
                "analysis": os.getenv("LLM_ANALYSIS_MODEL", default_model),
                "assistant": os.getenv("LLM_ASSISTANT_MODEL", default_model),
                "grading": os.getenv("LLM_GRADING_MODEL", default_model),
                "index": os.getenv("LLM_INDEX_MODEL", default_model),
                "embedding": os.getenv("LLM_EMBEDDING_MODEL", ""),
            },
            site_url=os.getenv("LLM_SITE_URL", "https://gradeos.app"),
            site_title=os.getenv("LLM_SITE_TITLE", "GradeOS AI Grading"),
        )

    def get_model(self, purpose: str) -> str:
        """Resolve model name by purpose."""
        return self.models.get(purpose, self.models.get("text", DEFAULT_LLM_MODEL))

    def get_headers(self) -> Dict[str, str]:
        """Get OpenRouter-specific headers."""
        return {
            "HTTP-Referer": self.site_url,
            "X-Title": self.site_title,
        }


_llm_config: Optional[LLMConfig] = None


def get_llm_config() -> LLMConfig:
    """Get global LLM configuration."""
    global _llm_config
    if _llm_config is None:
        _llm_config = LLMConfig.from_env()
    return _llm_config


def set_llm_config(config: LLMConfig) -> None:
    """Set global LLM configuration."""
    global _llm_config
    _llm_config = config
