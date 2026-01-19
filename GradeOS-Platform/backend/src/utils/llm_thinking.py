"""Utilities for handling model thinking content."""

from __future__ import annotations

import os
import re
from typing import Any, Dict, Tuple


def get_thinking_kwargs(model_name: str, enable_thinking: bool = True) -> Dict[str, Any]:
    """Return safe kwargs for optional thinking content."""
    if not enable_thinking:
        return {}
    kwargs: Dict[str, Any] = {}
    if os.getenv("LLM_INCLUDE_THOUGHTS", "").lower() in ("1", "true", "yes"):
        kwargs["response_mime_type"] = "text/plain"
    return kwargs


def split_thinking_content(content: Any) -> Tuple[str, str]:
    """Split content into output and thinking segments."""
    text = _flatten_content(content)
    if not text:
        return "", ""

    thinking_parts = re.findall(r"<thinking>(.*?)</thinking>", text, flags=re.DOTALL | re.IGNORECASE)
    output_text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
    thinking_text = "\n".join(part.strip() for part in thinking_parts if part.strip())
    return output_text, thinking_text


def _flatten_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(str(item.get("text") or ""))
        return "".join(parts)
    if hasattr(content, "text"):
        return str(content.text)
    return str(content)
