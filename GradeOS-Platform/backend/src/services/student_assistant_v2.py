
from __future__ import annotations

import base64
import json
import re
import uuid
from typing import Any, Dict, List, Optional, TypedDict

from langchain_core.messages import BaseMessage, SystemMessage
from langgraph.graph import END, StateGraph

from src.services.student_assistant_agent import get_student_assistant_agent

MAX_ATTACHMENT_IMAGES = 16
MAX_ATTACHMENT_BYTES = 12 * 1024 * 1024


class AssistantV2State(TypedDict, total=False):
    student_id: str
    class_id: Optional[str]
    conversation_id: str
    message: str
    session_mode: str
    concept_topic: str
    student_context: Dict[str, Any]
    history: List[BaseMessage]
    images: List[str]
    attachments: List[Dict[str, Any]]
    wrong_question_context: Optional[Dict[str, Any]]
    resolved_wrong_context: Optional[Dict[str, Any]]
    previous_trend_score: Optional[int]
    safety_level: str
    safety_reason: str
    guard_warnings: List[str]
    prepared_images: List[str]
    pedagogy_plan: Dict[str, Any]
    parsed_payload: Dict[str, Any]
    assistant_content: str
    model: Optional[str]
    usage: Optional[Dict[str, Any]]
    parse_status: str
    parse_error_code: Optional[str]
    mastery_payload: Dict[str, Any]
    trend_score: int
    trend_delta: int
    evidence_quality: float
    concept_trends: List[Dict[str, Any]]
    response_payload: Dict[str, Any]


def _clamp(value: int, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, value))


def _extract_data_uri_payload(value: str) -> str:
    if not value:
        return ""
    if value.startswith("data:") and "," in value:
        return value.split(",", 1)[1]
    return value


def _safe_decode_len(value: str) -> int:
    payload = _extract_data_uri_payload(value)
    try:
        return len(base64.b64decode(payload, validate=False))
    except Exception:
        return 0


def _sanitize_model_text(raw_content: str) -> str:
    text = (raw_content or "").strip()
    if not text:
        return ""

    if text.startswith("```"):
        lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            content = payload.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
    except Exception:
        pass

    if text.startswith("{") and text.endswith("}"):
        text = re.sub(r'"[A-Za-z_][A-Za-z0-9_]*"\s*:\s*', "", text)
        text = text.replace("{", "").replace("}", "").strip()

    return text[:4000]


def _ensure_mastery_payload(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    payload = payload or {}
    score = _clamp(int(payload.get("score") or 50))
    level = str(payload.get("level") or "developing")
    analysis = str(payload.get("analysis") or "")
    evidence = payload.get("evidence") if isinstance(payload.get("evidence"), list) else []
    suggestions = payload.get("suggestions") if isinstance(payload.get("suggestions"), list) else []
    return {
        "score": score,
        "level": level,
        "analysis": analysis,
        "evidence": [str(item) for item in evidence if str(item).strip()],
        "suggestions": [str(item) for item in suggestions if str(item).strip()],
    }


def _flatten_concepts(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    queue = list(nodes)
    result: List[Dict[str, Any]] = []
    while queue:
        item = queue.pop(0)
        if not isinstance(item, dict):
            continue
        result.append(item)
        children = item.get("children")
        if isinstance(children, list):
            queue.extend([child for child in children if isinstance(child, dict)])
    return result


def _normalize_concepts(nodes: Any) -> List[Dict[str, Any]]:
    if not isinstance(nodes, list):
        return []

    def _normalize_node(node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        name = str(node.get("name") or "").strip()
        if not name:
            return None
        key = str(node.get("id") or uuid.uuid4().hex[:8])
        children_raw = node.get("children")
        children: List[Dict[str, Any]] = []
        if isinstance(children_raw, list):
            for child in children_raw:
                if isinstance(child, dict):
                    normalized_child = _normalize_node(child)
                    if normalized_child:
                        children.append(normalized_child)
        return {
            "id": key,
            "name": name,
            "description": str(node.get("description") or ""),
            "understood": bool(node.get("understood")),
            "children": children or None,
        }

    normalized: List[Dict[str, Any]] = []
    for raw in nodes:
        if isinstance(raw, dict):
            node = _normalize_node(raw)
            if node:
                normalized.append(node)
    return normalized


def _classify_safety(message: str) -> tuple[str, str]:
    lowered = (message or "").strip().lower()

    level_3_patterns = [
        "build a bomb",
        "make a bomb",
        "how to kill",
        "kill someone",
        "self-harm",
        "suicide",
    ]
    if any(token in lowered for token in level_3_patterns):
        return "L3", "severe_harm_request"

    level_2_patterns = [
        "give me the exact exam answer",
        "directly give me the answer",
        "answer only",
        "bypass proctor",
        "hack",
        "cheat on exam",
    ]
    if any(token in lowered for token in level_2_patterns):
        return "L2", "high_risk_academic_integrity"

    level_1_patterns = [
        "just tell me final answer",
        "just give me final answer",
        "give final answer",
        "no explanation",
        "skip steps",
    ]
    if any(token in lowered for token in level_1_patterns):
        return "L1", "low_risk_shortcut_intent"

    return "L0", "normal_learning"


def _build_wrong_question_prompt(context: Optional[Dict[str, Any]]) -> str:
    if not context:
        return ""
    parts = ["Student is reviewing a wrong question."]
    question_id = context.get("question_id") or context.get("questionId")
    if question_id:
        parts.append(f"Question: {question_id}")
    score = context.get("score")
    max_score = context.get("max_score") or context.get("maxScore")
    if score is not None and max_score is not None:
        parts.append(f"Score: {score}/{max_score}")
    feedback = context.get("feedback")
    if feedback:
        parts.append(f"Feedback: {feedback}")
    question_content = context.get("question_content") or context.get("questionContent")
    if question_content:
        parts.append(f"Question content: {question_content}")
    student_answer = context.get("student_answer") or context.get("studentAnswer")
    if student_answer:
        parts.append(f"Student answer: {student_answer}")
    return "\n".join(parts)


class StudentAssistantV2Orchestrator:
    def __init__(self) -> None:
        self._agent = get_student_assistant_agent()
        graph = StateGraph(AssistantV2State)
        graph.add_node("input_guard_node", self._input_guard_node)
        graph.add_node("context_resolve_node", self._context_resolve_node)
        graph.add_node("multimodal_prepare_node", self._multimodal_prepare_node)
        graph.add_node("pedagogy_plan_node", self._pedagogy_plan_node)
        graph.add_node("response_generate_node", self._response_generate_node)
        graph.add_node("mastery_trend_node", self._mastery_trend_node)
        graph.add_node("memory_write_node", self._memory_write_node)
        graph.add_node("safety_postcheck_node", self._safety_postcheck_node)

        graph.set_entry_point("input_guard_node")
        graph.add_edge("input_guard_node", "context_resolve_node")
        graph.add_edge("context_resolve_node", "multimodal_prepare_node")
        graph.add_edge("multimodal_prepare_node", "pedagogy_plan_node")
        graph.add_edge("pedagogy_plan_node", "response_generate_node")
        graph.add_edge("response_generate_node", "mastery_trend_node")
        graph.add_edge("mastery_trend_node", "memory_write_node")
        graph.add_edge("memory_write_node", "safety_postcheck_node")
        graph.add_edge("safety_postcheck_node", END)

        self._graph = graph.compile()

    async def ainvoke(self, *, state: AssistantV2State) -> Dict[str, Any]:
        final_state = await self._graph.ainvoke(
            state,
            config={
                "configurable": {"thread_id": state["conversation_id"]},
                "recursion_limit": 50,
            },
        )
        return final_state.get("response_payload") or {}

    async def _input_guard_node(self, state: AssistantV2State) -> Dict[str, Any]:
        message = (state.get("message") or "").strip()
        warnings: List[str] = []
        if len(message) > 6000:
            message = message[:6000]
            warnings.append("message_truncated")

        safety_level, safety_reason = _classify_safety(message)
        return {
            "message": message,
            "safety_level": safety_level,
            "safety_reason": safety_reason,
            "guard_warnings": warnings,
        }

    async def _context_resolve_node(self, state: AssistantV2State) -> Dict[str, Any]:
        student_context = dict(state.get("student_context") or {})
        resolved_wrong = state.get("resolved_wrong_context")
        fallback_wrong = state.get("wrong_question_context")

        if isinstance(resolved_wrong, dict) and resolved_wrong:
            student_context["wrong_question_context"] = resolved_wrong
        elif isinstance(fallback_wrong, dict) and fallback_wrong:
            student_context["wrong_question_context"] = fallback_wrong

        return {
            "student_context": student_context,
            "resolved_wrong_context": resolved_wrong if isinstance(resolved_wrong, dict) else None,
        }

    async def _multimodal_prepare_node(self, state: AssistantV2State) -> Dict[str, Any]:
        prepared: List[str] = []
        warnings = list(state.get("guard_warnings") or [])

        for image in state.get("images") or []:
            if isinstance(image, str) and image.strip():
                prepared.append(image.strip())

        for attachment in state.get("attachments") or []:
            if not isinstance(attachment, dict):
                continue
            attachment_type = str(attachment.get("type") or "").lower()
            if attachment_type not in {"image", "image_base64", "pdf_page", "image_url"}:
                continue
            data = attachment.get("data") or attachment.get("base64") or attachment.get("content")
            if isinstance(data, str) and data.strip():
                prepared.append(data.strip())

        resolved_wrong_context = state.get("resolved_wrong_context") or state.get("wrong_question_context")
        if isinstance(resolved_wrong_context, dict):
            for item in resolved_wrong_context.get("images") or []:
                if isinstance(item, str) and item.strip():
                    prepared.append(item.strip())

        unique_images: List[str] = []
        seen: set[str] = set()
        total_bytes = 0
        for item in prepared:
            key = item[:120]
            if key in seen:
                continue
            byte_len = _safe_decode_len(item)
            if total_bytes + byte_len > MAX_ATTACHMENT_BYTES:
                warnings.append("attachment_bytes_capped")
                break
            seen.add(key)
            unique_images.append(item)
            total_bytes += byte_len
            if len(unique_images) >= MAX_ATTACHMENT_IMAGES:
                warnings.append("attachment_count_capped")
                break

        return {
            "prepared_images": unique_images,
            "guard_warnings": warnings,
        }

    async def _pedagogy_plan_node(self, state: AssistantV2State) -> Dict[str, Any]:
        wrong_context = state.get("resolved_wrong_context") or state.get("wrong_question_context") or {}
        plan = {
            "principles": ["first_principles", "socratic_questioning"],
            "mode": state.get("session_mode") or "learning",
            "focus": state.get("concept_topic") or "general",
            "has_wrong_question_context": bool(wrong_context),
        }
        return {"pedagogy_plan": plan}

    async def _response_generate_node(self, state: AssistantV2State) -> Dict[str, Any]:
        safety_level = state.get("safety_level") or "L0"
        safety_reason = state.get("safety_reason") or "normal_learning"

        if safety_level == "L3":
            content = (
                "I cannot help with harmful requests. If this is a safety concern, "
                "please contact local emergency support immediately. "
                "If you want to study, I can help break down your topic safely."
            )
            return {
                "assistant_content": content,
                "parsed_payload": {
                    "content": content,
                    "response_type": "explanation",
                    "focus_mode": False,
                    "mastery": {
                        "score": 0,
                        "level": "beginner",
                        "analysis": "Safety block triggered.",
                        "evidence": [],
                        "suggestions": ["Switch to a safe academic question."],
                    },
                },
                "parse_status": "safe_block",
                "parse_error_code": safety_reason,
                "model": None,
                "usage": {},
            }

        history = list(state.get("history") or [])
        pedagogy = state.get("pedagogy_plan") or {}
        pedagogy_prompt = (
            "Apply first-principles decomposition and Socratic questioning. "
            "Avoid giving final answers too early."
        )
        if pedagogy.get("has_wrong_question_context"):
            pedagogy_prompt += " This is a wrong-question deep review session."
        history.append(SystemMessage(content=pedagogy_prompt))

        wrong_prompt = _build_wrong_question_prompt(
            state.get("resolved_wrong_context") or state.get("wrong_question_context")
        )
        message = state.get("message") or ""
        if wrong_prompt:
            message = f"{wrong_prompt}\n\nStudent question: {message}"

        result = await self._agent.ainvoke(
            message=message,
            student_context=state.get("student_context") or {},
            session_mode=state.get("session_mode") or "learning",
            concept_topic=state.get("concept_topic") or "general",
            history=history,
            images=state.get("prepared_images") or None,
        )

        if result.parsed:
            payload = result.parsed.model_dump()
            content = (payload.get("content") or "").strip() or _sanitize_model_text(result.raw_content)
            payload["content"] = content
            return {
                "assistant_content": content,
                "parsed_payload": payload,
                "parse_status": "ok",
                "parse_error_code": None,
                "model": result.model,
                "usage": result.usage or {},
            }

        fallback = _sanitize_model_text(result.raw_content)
        if not fallback:
            fallback = "Let's rebuild this concept step by step from first principles."
        return {
            "assistant_content": fallback,
            "parsed_payload": {
                "content": fallback,
                "response_type": "chat",
                "focus_mode": False,
                "next_question": None,
                "question_options": [],
                "concept_breakdown": [],
                "mastery": {
                    "score": 52,
                    "level": "developing",
                    "analysis": "Structured parsing fallback.",
                    "evidence": [],
                    "suggestions": ["Try one short explanation in your own words."],
                },
            },
            "parse_status": "fallback_plain",
            "parse_error_code": "structured_parse_failed",
            "model": result.model,
            "usage": result.usage or {},
        }

    async def _mastery_trend_node(self, state: AssistantV2State) -> Dict[str, Any]:
        payload = dict(state.get("parsed_payload") or {})
        mastery = _ensure_mastery_payload(payload.get("mastery") if isinstance(payload.get("mastery"), dict) else None)

        evidence_count = len(mastery.get("evidence") or [])
        has_next_question = bool(payload.get("next_question"))
        has_concepts = bool(payload.get("concept_breakdown"))
        evidence_quality = min(1.0, (evidence_count * 0.15) + (0.2 if has_next_question else 0) + (0.35 if has_concepts else 0))

        previous_trend = state.get("previous_trend_score")
        if previous_trend is None:
            previous_trend = mastery["score"]

        trend_score = _clamp(round((previous_trend * 0.6) + (mastery["score"] * 0.3) + (evidence_quality * 100 * 0.1)))
        trend_delta = trend_score - int(previous_trend)

        concepts = _normalize_concepts(payload.get("concept_breakdown") or [])
        concept_trends: List[Dict[str, Any]] = []
        for node in _flatten_concepts(concepts):
            concept_mastery = mastery["score"] if node.get("understood") else _clamp(mastery["score"] - 20)
            concept_trend = _clamp(round((trend_score * 0.7) + (concept_mastery * 0.3)))
            concept_trends.append(
                {
                    "concept_key": node.get("id") or uuid.uuid4().hex[:8],
                    "concept_name": node.get("name") or "",
                    "mastery_score": concept_mastery,
                    "trend_score": concept_trend,
                    "status": "understood" if node.get("understood") else "gap",
                }
            )

        payload["concept_breakdown"] = concepts
        payload["mastery"] = mastery

        return {
            "parsed_payload": payload,
            "mastery_payload": mastery,
            "trend_score": trend_score,
            "trend_delta": trend_delta,
            "evidence_quality": evidence_quality,
            "concept_trends": concept_trends,
        }

    async def _memory_write_node(self, state: AssistantV2State) -> Dict[str, Any]:
        from src.db import (
            append_assistant_turn,
            save_assistant_concept_trends,
            save_assistant_mastery_event,
            save_assistant_mastery_snapshot,
            save_assistant_safety_event,
            upsert_assistant_concepts,
            upsert_assistant_conversation,
        )

        conversation_id = state["conversation_id"]
        student_id = state["student_id"]
        class_id = state.get("class_id")
        raw_attachments = state.get("attachments") if isinstance(state.get("attachments"), list) else []
        retained_attachments: List[Dict[str, Any]] = []
        attachment_chars = 0
        for item in raw_attachments:
            if not isinstance(item, dict):
                continue
            attachment_type = str(item.get("type") or "").lower()
            if attachment_type not in {"image", "pdf_page", "image_base64", "image_url"}:
                continue
            data = item.get("data")
            if not isinstance(data, str) or not data.strip():
                continue
            if attachment_chars + len(data) > 2_000_000:
                break
            attachment_chars += len(data)
            retained_attachments.append(
                {
                    "type": attachment_type,
                    "source": item.get("source"),
                    "page_index": item.get("page_index"),
                    "name": item.get("name"),
                    "size": item.get("size"),
                    "mime_type": item.get("mime_type"),
                    "data": data,
                }
            )
            if len(retained_attachments) >= 8:
                break

        upsert_assistant_conversation(
            conversation_id,
            student_id,
            class_id,
            summary=(state.get("assistant_content") or "")[:160],
            ttl_days=7,
        )

        append_assistant_turn(
            conversation_id,
            student_id,
            class_id,
            "user",
            state.get("message") or "",
            metadata={
                "session_mode": state.get("session_mode") or "learning",
                "safety_level": state.get("safety_level") or "L0",
                "attachments": retained_attachments,
            },
        )
        append_assistant_turn(
            conversation_id,
            student_id,
            class_id,
            "assistant",
            state.get("assistant_content") or "",
            metadata={
                "response_type": (state.get("parsed_payload") or {}).get("response_type") or "chat",
                "parse_status": state.get("parse_status") or "ok",
                "trend_score": state.get("trend_score") or 0,
            },
        )

        mastery_payload = _ensure_mastery_payload(state.get("mastery_payload"))
        save_assistant_mastery_snapshot(student_id, class_id, mastery_payload)
        save_assistant_mastery_event(
            student_id,
            class_id,
            conversation_id,
            {
                "mastery_score": mastery_payload["score"],
                "trend_score": state.get("trend_score") or mastery_payload["score"],
                "trend_delta": state.get("trend_delta") or 0,
                "evidence_quality": state.get("evidence_quality") or 0.0,
                "response_type": (state.get("parsed_payload") or {}).get("response_type") or "chat",
                "metadata": {
                    "parse_status": state.get("parse_status") or "ok",
                    "safety_level": state.get("safety_level") or "L0",
                },
            },
        )

        concepts = (state.get("parsed_payload") or {}).get("concept_breakdown") or []
        if isinstance(concepts, list) and concepts:
            flattened_for_legacy: List[Dict[str, Any]] = []
            for node in _flatten_concepts(concepts):
                name = str(node.get("name") or "").strip()
                if not name:
                    continue
                flattened_for_legacy.append(
                    {
                        "concept_key": node.get("id") or uuid.uuid4().hex[:8],
                        "name": name,
                        "description": str(node.get("description") or ""),
                        "parent_key": None,
                        "understood": bool(node.get("understood")),
                    }
                )
            if flattened_for_legacy:
                upsert_assistant_concepts(student_id, class_id, flattened_for_legacy)

        if state.get("concept_trends"):
            save_assistant_concept_trends(student_id, class_id, conversation_id, state.get("concept_trends") or [])

        safety_level = state.get("safety_level") or "L0"
        if safety_level != "L0":
            save_assistant_safety_event(
                student_id,
                class_id,
                conversation_id,
                safety_level=safety_level,
                reason=state.get("safety_reason") or "policy_notice",
                input_excerpt=(state.get("message") or "")[:300],
                metadata={"parse_status": state.get("parse_status") or "ok"},
            )

        return {}

    async def _safety_postcheck_node(self, state: AssistantV2State) -> Dict[str, Any]:
        payload = dict(state.get("parsed_payload") or {})
        content = (state.get("assistant_content") or "").strip()
        safety_level = state.get("safety_level") or "L0"

        if safety_level == "L1":
            content = (
                "I can help, but let's keep the reasoning visible instead of jumping straight to a final answer.\n\n"
                + content
            )
            payload["content"] = content

        if safety_level == "L2":
            content = (
                "I can help you learn this safely, but I cannot provide shortcut or cheating instructions.\n\n"
                + content
            )
            payload["content"] = content

        response = {
            "content": content,
            "model": state.get("model"),
            "usage": state.get("usage") or {},
            "mastery": _ensure_mastery_payload(payload.get("mastery") if isinstance(payload.get("mastery"), dict) else None),
            "next_question": payload.get("next_question"),
            "question_options": payload.get("question_options") if isinstance(payload.get("question_options"), list) else [],
            "focus_mode": bool(payload.get("focus_mode")),
            "concept_breakdown": _normalize_concepts(payload.get("concept_breakdown") or []),
            "response_type": payload.get("response_type") or "chat",
            "conversation_id": state.get("conversation_id"),
            "trend_score": int(state.get("trend_score") or 0),
            "trend_delta": int(state.get("trend_delta") or 0),
            "parse_status": state.get("parse_status") or "ok",
            "parse_error_code": state.get("parse_error_code"),
            "safety_level": safety_level,
        }

        return {"response_payload": response}


_assistant_v2_orchestrator: Optional[StudentAssistantV2Orchestrator] = None


def get_student_assistant_v2_orchestrator() -> StudentAssistantV2Orchestrator:
    global _assistant_v2_orchestrator
    if _assistant_v2_orchestrator is None:
        _assistant_v2_orchestrator = StudentAssistantV2Orchestrator()
    return _assistant_v2_orchestrator
