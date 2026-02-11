from __future__ import annotations

import asyncio
import os
from typing import List, Optional, Sequence

from langchain_core.chat_history import BaseChatMessageHistory, InMemoryChatMessageHistory
from langchain_core.messages import BaseMessage

try:
    from langchain.memory import ConversationBufferWindowMemory
except ImportError:  # pragma: no cover - optional dependency for runtime
    ConversationBufferWindowMemory = None

try:
    from langchain_community.chat_message_histories import RedisChatMessageHistory
except ImportError:  # pragma: no cover - optional dependency for runtime
    RedisChatMessageHistory = None


_ASSISTANT_MEMORY_WINDOW = int(os.getenv("ASSISTANT_MEMORY_WINDOW", "8"))
_ASSISTANT_MEMORY_TTL_SECONDS = int(os.getenv("ASSISTANT_MEMORY_TTL_SECONDS", "86400"))
_ASSISTANT_MEMORY_KEY_PREFIX = os.getenv("ASSISTANT_MEMORY_KEY_PREFIX", "assistant_memory")

_IN_MEMORY_HISTORIES: dict[str, InMemoryChatMessageHistory] = {}


def build_assistant_session_id(
    student_id: str,
    class_id: Optional[str],
    conversation_id: Optional[str] = None,
) -> str:
    if conversation_id and conversation_id.strip():
        return f"assistant:conv:{conversation_id.strip()}"
    suffix = class_id.strip() if class_id and class_id.strip() else "global"
    return f"assistant:{student_id}:{suffix}"


def _get_in_memory_history(session_id: str) -> InMemoryChatMessageHistory:
    history = _IN_MEMORY_HISTORIES.get(session_id)
    if history is None:
        history = InMemoryChatMessageHistory()
        _IN_MEMORY_HISTORIES[session_id] = history
    return history


def _create_redis_history(session_id: str) -> Optional[BaseChatMessageHistory]:
    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url or RedisChatMessageHistory is None:
        return None
    try:
        return RedisChatMessageHistory(
            session_id=session_id,
            url=redis_url,
            key_prefix=_ASSISTANT_MEMORY_KEY_PREFIX,
            ttl=_ASSISTANT_MEMORY_TTL_SECONDS,
        )
    except TypeError:
        return RedisChatMessageHistory(session_id, redis_url)


def _create_history(session_id: str) -> BaseChatMessageHistory:
    redis_history = _create_redis_history(session_id)
    if redis_history is not None:
        return redis_history
    return _get_in_memory_history(session_id)


class AssistantMemory:
    def __init__(self, session_id: str, window: Optional[int] = None) -> None:
        self._session_id = session_id
        self._window = max(1, window if window is not None else _ASSISTANT_MEMORY_WINDOW)
        self._history = _create_history(session_id)
        self._memory = None
        if ConversationBufferWindowMemory is not None:
            self._memory = ConversationBufferWindowMemory(
                chat_memory=self._history,
                k=self._window,
                return_messages=True,
            )

    def _load_sync(self) -> List[BaseMessage]:
        if self._memory is not None:
            payload = self._memory.load_memory_variables({})
            history = payload.get("history", [])
            if isinstance(history, list):
                return history
            return []
        return list(self._history.messages)

    async def load(self) -> List[BaseMessage]:
        return await asyncio.to_thread(self._load_sync)

    def _append_sync(self, messages: Sequence[BaseMessage]) -> None:
        for message in messages:
            self._history.add_message(message)

    async def append(self, messages: Sequence[BaseMessage]) -> None:
        if not messages:
            return
        await asyncio.to_thread(self._append_sync, messages)

    def _clear_sync(self) -> None:
        try:
            if hasattr(self._history, "clear"):
                self._history.clear()
                return
        except Exception:
            pass
        try:
            if hasattr(self._history, "messages"):
                self._history.messages = []
        except Exception:
            pass
        if isinstance(self._history, InMemoryChatMessageHistory):
            _IN_MEMORY_HISTORIES.pop(self._session_id, None)

    async def clear(self) -> None:
        await asyncio.to_thread(self._clear_sync)
