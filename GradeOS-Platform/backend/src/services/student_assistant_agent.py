from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel, Field

from src.services.chat_model_factory import get_chat_model


class AssistantHistoryMessage(TypedDict):
    role: str
    content: str


class AssistantConceptNode(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = ""
    description: Optional[str] = ""
    understood: bool = False
    children: Optional[List["AssistantConceptNode"]] = None


class AssistantMastery(BaseModel):
    score: int = Field(default=50, ge=0, le=100)
    level: str = "developing"
    analysis: str = ""
    evidence: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)


class AssistantStructuredResponse(BaseModel):
    content: str
    next_question: Optional[str] = None
    focus_mode: bool = False
    response_type: str = "chat"
    mastery: Optional[AssistantMastery] = None
    concept_breakdown: Optional[List[AssistantConceptNode]] = None


AssistantConceptNode.model_rebuild()


@dataclass
class AssistantAgentResult:
    raw_content: str
    model: Optional[str]
    usage: Optional[Dict[str, Any]]
    parsed: Optional[AssistantStructuredResponse]


SYSTEM_PROMPT = """You are GradeOS Student Assistant, a rigorous tutor.

Teaching style:
- Use the Socratic method: guide with questions, challenge assumptions, avoid giving final answers too early.
- Use first principles: decompose concepts into fundamentals and rebuild understanding step by step.

Output rules:
- Respond with JSON only.
- Follow the schema in {format_instructions}.
- Use the student's language based on their message.
- Provide "concept_breakdown" as a tree of fundamentals (2-4 levels deep when possible).
- Keep responses concise, precise, and supportive.

Student context:
{student_context}

Session mode: {session_mode}
Concept topic: {concept_topic}
"""


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except Exception:
            return None


class StudentAssistantAgent:
    def __init__(self) -> None:
        self._parser = PydanticOutputParser(pydantic_object=AssistantStructuredResponse)
        self._prompt = ChatPromptTemplate.from_messages(
            [
                ("system", SYSTEM_PROMPT),
                MessagesPlaceholder("history"),
                ("human", "{message}"),
            ]
        )
        self._llm = get_chat_model(
            api_key=None,
            model_name=None,
            purpose="assistant",
            temperature=0.4,
            max_output_tokens=2500,
        )

    def _convert_history(
        self,
        history: Optional[Sequence[AssistantHistoryMessage]],
    ) -> List[BaseMessage]:
        if not history:
            return []
        messages: List[BaseMessage] = []
        for item in list(history)[-8:]:
            role = item.get("role", "user")
            content = item.get("content", "")
            if not content:
                continue
            if role == "assistant":
                messages.append(AIMessage(content=content))
            elif role == "system":
                messages.append(SystemMessage(content=content))
            else:
                messages.append(HumanMessage(content=content))
        return messages

    def _parse_response(self, raw_content: str) -> Optional[AssistantStructuredResponse]:
        try:
            return self._parser.parse(raw_content)
        except Exception:
            payload = _extract_json(raw_content)
            if payload is None:
                return None
            try:
                return AssistantStructuredResponse.model_validate(payload)
            except Exception:
                return None

    async def ainvoke(
        self,
        *,
        message: str,
        student_context: Dict[str, Any],
        session_mode: str,
        concept_topic: str,
        history: Optional[Sequence[AssistantHistoryMessage]] = None,
    ) -> AssistantAgentResult:
        prompt_value = self._prompt.format_prompt(
            format_instructions=self._parser.get_format_instructions(),
            history=self._convert_history(history),
            message=message,
            student_context=json.dumps(student_context, ensure_ascii=False),
            session_mode=session_mode,
            concept_topic=concept_topic,
        )

        response = await self._llm.ainvoke(prompt_value.to_messages())
        raw_content = getattr(response, "content", str(response))
        parsed = self._parse_response(raw_content)
        model = getattr(response, "model", None)
        usage = getattr(response, "usage", None)
        return AssistantAgentResult(
            raw_content=raw_content,
            model=model,
            usage=usage,
            parsed=parsed,
        )


_assistant_agent: Optional[StudentAssistantAgent] = None


def get_student_assistant_agent() -> StudentAssistantAgent:
    global _assistant_agent
    if _assistant_agent is None:
        _assistant_agent = StudentAssistantAgent()
    return _assistant_agent
