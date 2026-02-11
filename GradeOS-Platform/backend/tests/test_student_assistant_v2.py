
from src.services.student_assistant_v2 import (
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
