from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel, Field

from src.services.chat_model_factory import get_chat_model
from src.services.llm_client import get_llm_client, LLMMessage


class AssistantHistoryMessage(TypedDict):
    role: str
    content: str


AssistantHistoryItem = AssistantHistoryMessage | BaseMessage


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
    question_options: Optional[List[str]] = None
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
- If the student expresses confusion or says they don't know, briefly explain the missing concept before asking the next, simpler question.
- Ensure explanations are substantive: include 3-5 clear reasoning steps, highlight a key misconception, and end with a concise summary.

Output rules:
- Respond with JSON only.
- Follow the schema in {format_instructions}.
- Use the student's language based on their message.
- Provide "concept_breakdown" as a tree of fundamentals (2-4 levels deep when possible).
- Keep responses concise but not shallow; be precise, structured, and supportive.
- When you ask a "next_question", also provide 2-4 "question_options" as short clickable choices in the same language.
- When you provide an explanation, set response_type to "explanation".
- In concept_breakdown, set understood=true only for items the student has demonstrated; default to false for gaps.

Student context:
{student_context}

Session mode: {session_mode}
Concept topic: {concept_topic}
"""


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """从文本中提取 JSON 对象，支持处理 markdown 代码块包裹的情况"""
    # 首先尝试直接解析
    try:
        return json.loads(text)
    except Exception:
        pass
    
    # 尝试移除 markdown 代码块标记
    # 处理 ```json ... ``` 或 ``` ... ``` 格式
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # 移除开头的 ```json 或 ```
        lines = cleaned.split("\n", 1)
        if len(lines) > 1:
            cleaned = lines[1]
        # 移除结尾的 ```
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[:-3].rstrip()
    
    # 尝试解析清理后的文本
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    
    # 最后尝试用正则提取 JSON 对象
    match = re.search(r"\{.*\}", cleaned, re.S)
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
        history: Optional[Sequence[AssistantHistoryItem]],
    ) -> List[BaseMessage]:
        if not history:
            return []
        messages: List[BaseMessage] = []
        for item in list(history)[-8:]:
            if isinstance(item, BaseMessage):
                messages.append(item)
                continue
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
        history: Optional[Sequence[AssistantHistoryItem]] = None,
        images: Optional[List[str]] = None,  # 新增：base64 编码的图片列表
    ) -> AssistantAgentResult:
        # 如果有图片，使用多模态调用
        if images and len(images) > 0:
            return await self._ainvoke_with_images(
                message=message,
                student_context=student_context,
                session_mode=session_mode,
                concept_topic=concept_topic,
                history=history,
                images=images,
            )
        
        # 无图片时使用原有逻辑
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

    async def _ainvoke_with_images(
        self,
        *,
        message: str,
        student_context: Dict[str, Any],
        session_mode: str,
        concept_topic: str,
        history: Optional[Sequence[AssistantHistoryItem]] = None,
        images: List[str],
    ) -> AssistantAgentResult:
        """使用多模态 LLM 调用（支持图片）"""
        llm_client = get_llm_client()
        
        # 构建系统提示
        system_prompt = SYSTEM_PROMPT.format(
            format_instructions=self._parser.get_format_instructions(),
            student_context=json.dumps(student_context, ensure_ascii=False),
            session_mode=session_mode,
            concept_topic=concept_topic,
        )
        
        # 构建消息内容（包含图片和文本）
        content_parts: List[Dict[str, Any]] = []
        
        # 添加图片
        for img_data in images:
            # 处理 base64 图片（可能带有 data:image/xxx;base64, 前缀）
            if img_data.startswith("data:"):
                # 提取 base64 部分
                parts = img_data.split(",", 1)
                if len(parts) == 2:
                    img_bytes = base64.b64decode(parts[1])
                    # 提取 media type
                    media_type = "image/jpeg"
                    if "image/png" in parts[0]:
                        media_type = "image/png"
                    elif "image/webp" in parts[0]:
                        media_type = "image/webp"
                    content_parts.append(llm_client.create_image_content(img_bytes, media_type))
            else:
                # 纯 base64
                try:
                    img_bytes = base64.b64decode(img_data)
                    content_parts.append(llm_client.create_image_content(img_bytes))
                except Exception:
                    pass
        
        # 添加历史消息摘要（如果有）
        history_summary = ""
        if history:
            recent_history = self._convert_history(history)[-4:]  # 只取最近4条
            if recent_history:
                history_parts = []
                for msg in recent_history:
                    role = "Student" if isinstance(msg, HumanMessage) else "Assistant"
                    content = getattr(msg, "content", "")
                    if content and len(content) < 500:  # 避免太长的历史
                        history_parts.append(f"{role}: {content[:200]}")
                if history_parts:
                    history_summary = "\n\n[Recent conversation]\n" + "\n".join(history_parts)
        
        # 添加文本消息
        full_message = message + history_summary
        content_parts.append(llm_client.create_text_content(full_message))
        
        # 构建消息列表
        messages: List[LLMMessage] = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=content_parts),
        ]
        
        # 调用多模态 LLM
        response = await llm_client.invoke(
            messages=messages,
            purpose="vision",  # 使用 vision 模型
            temperature=0.4,
            max_tokens=2500,
        )
        
        raw_content = response.content
        parsed = self._parse_response(raw_content)
        
        return AssistantAgentResult(
            raw_content=raw_content,
            model=response.model,
            usage=response.usage,
            parsed=parsed,
        )


_assistant_agent: Optional[StudentAssistantAgent] = None


def get_student_assistant_agent() -> StudentAssistantAgent:
    global _assistant_agent
    if _assistant_agent is None:
        _assistant_agent = StudentAssistantAgent()
    return _assistant_agent
