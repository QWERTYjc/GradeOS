from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, Iterable, Optional

from langchain_core.messages import BaseMessage

from src.config.llm import get_llm_config
from src.services.llm_client import LLMMessage, get_llm_client


@dataclass
class _SimpleMessage:
    content: Any
    model: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None


def _resolve_role(message: BaseMessage) -> str:
    role = getattr(message, "type", None) or getattr(message, "role", None)
    if role in ("human", "user"):
        return "user"
    if role in ("ai", "assistant"):
        return "assistant"
    if role == "system":
        return "system"
    return "user"


def _resolve_openrouter_model(purpose: str, model_name: Optional[str]) -> str:
    config = get_llm_config()
    if model_name and "/" in model_name:
        return model_name
    return config.get_model(purpose)


class OpenRouterChatAdapter:
    def __init__(
        self,
        *,
        purpose: str,
        model: Optional[str],
        temperature: float,
        max_tokens: int,
        api_key_override: Optional[str] = None,
    ) -> None:
        self._client = get_llm_client()
        self._purpose = purpose
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._api_key_override = api_key_override

    def _convert_messages(self, messages: Iterable[BaseMessage]) -> list[LLMMessage]:
        converted: list[LLMMessage] = []
        for message in messages:
            role = _resolve_role(message)
            content = getattr(message, "content", "")
            converted.append(LLMMessage(role=role, content=content))
        return converted

    async def ainvoke(self, messages: Iterable[BaseMessage]) -> _SimpleMessage:
        response = await self._client.invoke(
            messages=self._convert_messages(messages),
            purpose=self._purpose,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            model=self._model,
            api_key_override=self._api_key_override,
        )
        return _SimpleMessage(response.content, model=response.model, usage=response.usage)

    async def astream(self, messages: Iterable[BaseMessage]) -> AsyncIterator[_SimpleMessage]:
        async for chunk in self._client.stream(
            messages=self._convert_messages(messages),
            purpose=self._purpose,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            model=self._model,
            api_key_override=self._api_key_override,
        ):
            yield _SimpleMessage(chunk)


def get_chat_model(
    *,
    api_key: Optional[str],
    model_name: Optional[str],
    purpose: str = "text",
    temperature: float = 0.2,
    enable_thinking: bool = False,
    streaming: bool = False,
    max_output_tokens: Optional[int] = None,
) -> Any:
    resolved_model = _resolve_openrouter_model(purpose, model_name)
    # 如果 max_output_tokens 为 None 或 0，使用较大的默认值以避免截断
    # 设置为 65536 以支持大多数模型的最大输出
    effective_max_tokens = max_output_tokens if max_output_tokens and max_output_tokens > 0 else 65536
    return OpenRouterChatAdapter(
        purpose=purpose,
        model=resolved_model,
        temperature=temperature,
        max_tokens=effective_max_tokens,
        api_key_override=api_key,
    )
