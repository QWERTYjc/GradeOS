"""Unified LLM client for OpenRouter-compatible APIs."""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional, Union

import httpx

from src.config.llm import LLMConfig, LLMProvider, get_llm_config

logger = logging.getLogger(__name__)


@dataclass
class LLMMessage:
    """LLM message."""

    role: str
    content: Union[str, List[Dict[str, Any]]]


@dataclass
class LLMResponse:
    """LLM response."""

    content: str
    model: str
    usage: Optional[Dict[str, int]] = None
    finish_reason: Optional[str] = None


class UnifiedLLMClient:
    """Unified LLM client for OpenRouter-compatible APIs."""

    def __init__(self, config: Optional[LLMConfig] = None) -> None:
        self.config = config or get_llm_config()
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=120.0)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _build_headers(self, api_key_override: Optional[str] = None) -> Dict[str, str]:
        api_key = api_key_override or self.config.api_key
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        headers.update(self.config.get_headers())
        return headers

    def _format_messages(self, messages: List[LLMMessage]) -> List[Dict[str, Any]]:
        formatted: List[Dict[str, Any]] = []
        for msg in messages:
            if isinstance(msg.content, str):
                formatted.append({"role": msg.role, "content": msg.content})
                continue

            content = msg.content
            if self.config.provider == LLMProvider.OPENROUTER and isinstance(content, list):
                normalized = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "image_url":
                        image_url = item.get("image_url")
                        if isinstance(image_url, str):
                            normalized.append({**item, "image_url": {"url": image_url}})
                            continue
                    normalized.append(item)
                content = normalized

            formatted.append({"role": msg.role, "content": content})
        return formatted

    @staticmethod
    def create_image_content(image_bytes: bytes, media_type: str = "image/jpeg") -> Dict[str, Any]:
        base64_image = base64.b64encode(image_bytes).decode("utf-8")
        return {
            "type": "image_url",
            "image_url": {"url": f"data:{media_type};base64,{base64_image}"},
        }

    @staticmethod
    def create_text_content(text: str) -> Dict[str, Any]:
        return {"type": "text", "text": text}

    async def invoke(
        self,
        *,
        messages: List[LLMMessage],
        purpose: str = "text",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        model: Optional[str] = None,
        api_key_override: Optional[str] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        resolved_model = model or self.config.get_model(purpose)
        client = await self._get_client()
        payload = {
            "model": resolved_model,
            "messages": self._format_messages(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }

        logger.info(
            "[LLM] invoke model=%s purpose=%s messages=%s",
            resolved_model,
            purpose,
            len(messages),
        )

        try:
            response = await client.post(
                f"{self.config.base_url}/chat/completions",
                headers=self._build_headers(api_key_override),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            choice = data.get("choices", [{}])[0]
            content = choice.get("message", {}).get("content", "")
            usage = data.get("usage", {}) or {}

            header_usage = {}
            header_key = response.headers.get("x-openrouter-usage") or response.headers.get("x-usage")
            if header_key:
                try:
                    import json

                    header_usage = json.loads(header_key)
                except Exception:
                    header_usage = {}
            if header_usage:
                usage = {**usage, **header_usage}

            logger.info("[LLM] response chars=%s tokens=%s", len(content), usage)
            return LLMResponse(
                content=content,
                model=resolved_model,
                usage=usage,
                finish_reason=choice.get("finish_reason"),
            )
        except httpx.HTTPStatusError as exc:
            try:
                body = await exc.response.aread()
                text = body.decode("utf-8", errors="replace")
            except Exception:
                text = exc.response.text if exc.response else "<unreadable response>"
            logger.error("[LLM] HTTP error %s: %s", exc.response.status_code, text)
            raise
        except Exception as exc:
            logger.error("[LLM] invoke failed: %s", exc)
            raise

    async def stream(
        self,
        *,
        messages: List[LLMMessage],
        purpose: str = "text",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        model: Optional[str] = None,
        api_key_override: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        resolved_model = model or self.config.get_model(purpose)
        client = await self._get_client()
        payload = {
            "model": resolved_model,
            "messages": self._format_messages(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            **kwargs,
        }
        if self.config.provider == LLMProvider.OPENROUTER:
            payload["stream_options"] = {"include_usage": True}

        image_count = 0
        for msg in payload["messages"]:
            content = msg.get("content")
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "image_url":
                        image_count += 1

        logger.info(
            "[LLM] stream model=%s purpose=%s images=%s messages=%s",
            resolved_model,
            purpose,
            image_count,
            len(payload["messages"]),
        )

        try:
            async with client.stream(
                "POST",
                f"{self.config.base_url}/chat/completions",
                headers=self._build_headers(api_key_override),
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        import json

                        data = json.loads(data_str)
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except Exception:
                        continue
        except httpx.HTTPStatusError as exc:
            logger.error("[LLM] stream HTTP error %s: %s", exc.response.status_code, exc.response.text)
            raise
        except Exception as exc:
            logger.error("[LLM] stream failed: %s", exc)
            raise

    async def embed(
        self,
        *,
        inputs: Union[str, List[str]],
        model: Optional[str] = None,
        api_key_override: Optional[str] = None,
        **kwargs: Any,
    ) -> List[List[float]]:
        resolved_model = model or self.config.get_model("embedding")
        if not resolved_model:
            raise ValueError("Embedding model is not configured")

        payload = {
            "model": resolved_model,
            "input": inputs,
            **kwargs,
        }

        client = await self._get_client()
        try:
            response = await client.post(
                f"{self.config.base_url}/embeddings",
                headers=self._build_headers(api_key_override),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return [item.get("embedding", []) for item in data.get("data", [])]
        except httpx.HTTPStatusError as exc:
            logger.error("[LLM] embeddings HTTP error %s: %s", exc.response.status_code, exc.response.text)
            raise
        except Exception as exc:
            logger.error("[LLM] embeddings failed: %s", exc)
            raise

    async def invoke_with_images(
        self,
        *,
        prompt: str,
        images: List[bytes],
        purpose: str = "vision",
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        model: Optional[str] = None,
        api_key_override: Optional[str] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        content: List[Dict[str, Any]] = []
        for img in images:
            content.append(self.create_image_content(img))
        content.append(self.create_text_content(prompt))

        messages: List[LLMMessage] = []
        if system_prompt:
            messages.append(LLMMessage(role="system", content=system_prompt))
        messages.append(LLMMessage(role="user", content=content))

        return await self.invoke(
            messages=messages,
            purpose=purpose,
            temperature=temperature,
            max_tokens=max_tokens,
            model=model,
            api_key_override=api_key_override,
            **kwargs,
        )


_llm_client: Optional[UnifiedLLMClient] = None


def get_llm_client() -> UnifiedLLMClient:
    """Get global LLM client."""
    global _llm_client
    if _llm_client is None:
        _llm_client = UnifiedLLMClient()
    return _llm_client


async def close_llm_client() -> None:
    """Close global LLM client."""
    global _llm_client
    if _llm_client:
        await _llm_client.close()
        _llm_client = None
