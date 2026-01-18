from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator, Iterable, Optional

from langchain_core.messages import BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from src.config.llm import LLMProvider, get_llm_config
from src.config.models import get_default_model
from src.services.llm_client import LLMMessage, get_llm_client
from src.utils.llm_thinking import get_thinking_kwargs


@dataclass
class _SimpleMessage:
    content: Any


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
    ) -> None:
        self._client = get_llm_client()
        self._purpose = purpose
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

    def _convert_messages(self, messages: Iterable[BaseMessage]) -> list[LLMMessage]:
        converted: list[LLMMessage] = []
        for message in messages:
            role = _resolve_role(message)
            content = getattr(message, "content", "")
            converted.append(LLMMessage(role=role, content=content))
        return converted

    async def ainvoke(self, messages: Iterable[BaseMessage]) -> _SimpleMessage:
        kwargs = {}
        if self._model:
            kwargs["model"] = self._model
        response = await self._client.invoke(
            messages=self._convert_messages(messages),
            purpose=self._purpose,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            **kwargs,
        )
        return _SimpleMessage(response.content)

    async def astream(self, messages: Iterable[BaseMessage]) -> AsyncIterator[_SimpleMessage]:
        kwargs = {}
        if self._model:
            kwargs["model"] = self._model
        async for chunk in self._client.stream(
            messages=self._convert_messages(messages),
            purpose=self._purpose,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            **kwargs,
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
    config = get_llm_config()
    if config.provider == LLMProvider.OPENROUTER:
        resolved_model = _resolve_openrouter_model(purpose, model_name)
        return OpenRouterChatAdapter(
            purpose=purpose,
            model=resolved_model,
            temperature=temperature,
            max_tokens=max_output_tokens or 4096,
        )

    resolved_model = model_name or get_default_model()
    thinking_kwargs = get_thinking_kwargs(resolved_model, enable_thinking=enable_thinking)
    return ChatGoogleGenerativeAI(
        model=resolved_model,
        google_api_key=api_key or config.api_key,
        temperature=temperature,
        streaming=streaming,
        max_output_tokens=max_output_tokens,
        **thinking_kwargs,
    )
