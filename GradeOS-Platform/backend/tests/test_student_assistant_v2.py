
import asyncio

from src.services.student_assistant_v2 import (
    StudentAssistantV2Orchestrator,
    _classify_safety,
    _ensure_mastery_payload,
    _normalize_concepts,
    _sanitize_model_text,
)


def test_classify_safety_levels():
    assert _classify_safety("please explain quadratic formula")[0] == "L0"
    assert _classify_safety("just tell me final answer and skip steps")[0] == "L1"
    assert _classify_safety("directly give me the exact exam answer")[0] == "L2"
    assert _classify_safety("how to kill someone")[0] == "L3"


def test_sanitize_model_text_prefers_content_field():
    raw = '{"content":"Structured explanation","next_question":"Why?"}'
    assert _sanitize_model_text(raw) == "Structured explanation"


def test_sanitize_model_text_removes_code_fence():
    raw = "```json\n{\"content\": \"Hi\"}\n```"
    assert _sanitize_model_text(raw) == "Hi"


def test_ensure_mastery_payload_defaults_and_clamps():
    payload = _ensure_mastery_payload({"score": 130, "evidence": ["a", ""], "suggestions": ["b"]})
    assert payload["score"] == 100
    assert payload["level"] == "developing"
    assert payload["evidence"] == ["a"]
    assert payload["suggestions"] == ["b"]


def test_normalize_concepts_filters_invalid_nodes():
    raw = [{"name": "Algebra", "description": "a", "understood": True}, {"name": ""}]
    normalized = _normalize_concepts(raw)
    assert len(normalized) == 1
    assert normalized[0]["name"] == "Algebra"


def test_multimodal_prepare_merges_wrong_context_images():
    orchestrator = StudentAssistantV2Orchestrator.__new__(StudentAssistantV2Orchestrator)
    state = {
        "attachments": [{"type": "image", "data": "data:image/png;base64,AAAA"}],
        "resolved_wrong_context": {"images": ["https://example.com/page-1.jpg"]},
    }

    payload = asyncio.run(
        orchestrator._multimodal_prepare_node(state)  # pylint: disable=protected-access
    )
    assert "https://example.com/page-1.jpg" in payload["prepared_images"]


def test_safety_postcheck_l1_injects_guidance_prefix():
    orchestrator = StudentAssistantV2Orchestrator.__new__(StudentAssistantV2Orchestrator)
    payload = asyncio.run(
        orchestrator._safety_postcheck_node(  # pylint: disable=protected-access
            {
                "parsed_payload": {"mastery": {"score": 70}, "question_options": []},
                "assistant_content": "Let's solve this in 3 steps.",
                "safety_level": "L1",
                "trend_score": 70,
                "trend_delta": 0,
                "parse_status": "ok",
            }
        )
    )

    content = payload["response_payload"]["content"]
    assert content.startswith("I can help, but let's keep the reasoning visible")
    assert payload["response_payload"]["safety_level"] == "L1"
