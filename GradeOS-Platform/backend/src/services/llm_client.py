"""Unified LLM client for OpenRouter-compatible APIs."""

from __future__ import annotations

import asyncio
import base64
import logging
import os
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
            # 增加超时时间以支持大型视觉分析任务
            # 可通过环境变量 LLM_HTTP_TIMEOUT 覆盖
            timeout = self._read_float_env("LLM_HTTP_TIMEOUT", 300.0)
            self._client = httpx.AsyncClient(timeout=timeout)
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

    @staticmethod
    async def _safe_read_response_text(response: Optional[httpx.Response]) -> str:
        if response is None:
            return "<no response>"
        try:
            body = await response.aread()
            return body.decode("utf-8", errors="replace")
        except Exception:
            try:
                return response.text
            except Exception:
                return "<unreadable response>"

    @staticmethod
    def _read_int_env(key: str, default: int) -> int:
        raw = os.getenv(key)
        if raw is None:
            return default
        try:
            return int(raw)
        except ValueError:
            return default

    @staticmethod
    def _read_float_env(key: str, default: float) -> float:
        raw = os.getenv(key)
        if raw is None:
            return default
        try:
            return float(raw)
        except ValueError:
            return default

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

        logger.debug(
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
            header_key = response.headers.get("x-openrouter-usage") or response.headers.get(
                "x-usage"
            )
            if header_key:
                try:
                    import json

                    header_usage = json.loads(header_key)
                except Exception:
                    header_usage = {}
            if header_usage:
                usage = {**usage, **header_usage}

            logger.debug("[LLM] response chars=%s tokens=%s", len(content), usage)
            return LLMResponse(
                content=content,
                model=resolved_model,
                usage=usage,
                finish_reason=choice.get("finish_reason"),
            )
        except httpx.HTTPStatusError as exc:
            text = await self._safe_read_response_text(exc.response)
            status_code = exc.response.status_code if exc.response else "unknown"
            logger.error("[LLM] HTTP error %s: %s", status_code, text)
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

        logger.debug(
            "[LLM] stream model=%s purpose=%s images=%s messages=%s",
            resolved_model,
            purpose,
            image_count,
            len(payload["messages"]),
        )

        max_retries = max(0, self._read_int_env("LLM_STREAM_MAX_RETRIES", 2))
        retry_delay = max(0.1, self._read_float_env("LLM_STREAM_RETRY_DELAY", 2.0))
        max_delay = max(retry_delay, self._read_float_env("LLM_STREAM_RETRY_MAX_DELAY", 30.0))
        attempt = 0

        while True:
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
                return
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code if exc.response else None
                text = await self._safe_read_response_text(exc.response)
                retry_after = None
                if exc.response is not None:
                    retry_after_header = exc.response.headers.get("Retry-After")
                    if retry_after_header:
                        try:
                            retry_after = float(retry_after_header)
                        except ValueError:
                            retry_after = None
                logger.error("[LLM] stream HTTP error %s: %s", status_code, text)
                if status_code in {429, 502, 503, 504} and attempt < max_retries:
                    wait_time = retry_after or retry_delay
                    logger.warning(
                        "[LLM] stream retrying in %.1fs (%s/%s)",
                        wait_time,
                        attempt + 1,
                        max_retries,
                    )
                    await asyncio.sleep(wait_time)
                    retry_delay = min(retry_delay * 2, max_delay)
                    attempt += 1
                    continue
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
            text = await self._safe_read_response_text(exc.response)
            status_code = exc.response.status_code if exc.response else "unknown"
            logger.error("[LLM] embeddings HTTP error %s: %s", status_code, text)
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
