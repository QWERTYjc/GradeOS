import asyncio
import pytest

from src.graphs import batch_grading as batch_grading_module


def _build_student_result() -> dict:
    return {
        "student_key": "学生1",
        "question_details": [
            {
                "question_id": "1",
                "score": 2.0,
                "max_score": 5.0,
                "feedback": "原始反馈",
                "student_answer": "答题内容",
                "scoring_point_results": [],
            }
        ],
        "total_score": 2.0,
        "max_total_score": 5.0,
    }


def test_normalize_logic_review_items_supports_aliases_and_nested_lists():
    raw = [
        [
            {
                "_id": "5",
                "confidence": 0.5,
                "_reason": "理由A",
                "_summary": "摘要A",
                "_corrections": [{"point_id": "5.1"}],
            }
        ],
        {
            "qid": "6",
            "reason": "理由B",
            "summary": "摘要B",
            "corrections": {"point_id": "6.1"},
        },
    ]

    normalized = batch_grading_module._normalize_logic_review_items(raw)

    assert len(normalized) == 2
    assert normalized[0]["question_id"] == "5"
    assert normalized[0]["confidence_reason"] == "理由A"
    assert normalized[0]["review_summary"] == "摘要A"
    assert normalized[0]["review_corrections"] == [{"point_id": "5.1"}]

    assert normalized[1]["question_id"] == "6"
    assert normalized[1]["confidence_reason"] == "理由B"
    assert normalized[1]["review_summary"] == "摘要B"
    assert normalized[1]["review_corrections"] == [{"point_id": "6.1"}]


def test_logic_review_retries_once_and_applies_valid_output(monkeypatch):
    calls = {"stream": 0}

    async def _noop_broadcast(*_args, **_kwargs):
        return None

    class DummyReasoningClient:
        def __init__(self, *_args, **_kwargs):
            pass

        async def _call_text_api_stream(self, _prompt):
            calls["stream"] += 1
            if calls["stream"] == 1:
                # first attempt: missing question id, should trigger retry
                yield '{"question_reviews":[{"confidence":0.4,"_summary":"缺少题号"}]}'
            else:
                yield '{"question_reviews":[{"_id":"1","confidence":0.95,"_summary":"通过","_corrections":[]}]}'

        def _extract_json_from_text(self, text: str) -> str:
            return text

    monkeypatch.setattr(batch_grading_module, "_broadcast_progress", _noop_broadcast)
    monkeypatch.setattr(batch_grading_module, "split_thinking_content", lambda chunk: (chunk, ""))
    monkeypatch.setattr("src.services.llm_reasoning.LLMReasoningClient", DummyReasoningClient)

    state = {
        "batch_id": "batch_retry_ok",
        "student_results": [_build_student_result()],
        "parsed_rubric": {"questions": [{"question_id": "1", "max_score": 5}]},
        "api_key": "fake-key",
        "inputs": {},
        "timestamps": {},
    }

    result = asyncio.run(batch_grading_module.logic_review_node(state))
    student = result["student_results"][0]
    coverage = student["logic_review"]["coverage"]

    assert calls["stream"] == 2
    assert coverage["retried"] is True
    assert coverage["valid"] is True
    assert coverage["missing_question_ids"] == []
    assert coverage["reviewed_question_ids"] == ["1"]
    assert student["question_details"][0]["score"] == 2.0


def test_logic_review_retry_failure_keeps_scores_and_builds_placeholders(monkeypatch):
    calls = {"stream": 0}

    async def _noop_broadcast(*_args, **_kwargs):
        return None

    class DummyReasoningClient:
        def __init__(self, *_args, **_kwargs):
            pass

        async def _call_text_api_stream(self, _prompt):
            calls["stream"] += 1
            yield '{"question_reviews":[{"confidence":0.2,"summary":"仍然缺少题号"}]}'

        def _extract_json_from_text(self, text: str) -> str:
            return text

    monkeypatch.setattr(batch_grading_module, "_broadcast_progress", _noop_broadcast)
    monkeypatch.setattr(batch_grading_module, "split_thinking_content", lambda chunk: (chunk, ""))
    monkeypatch.setattr("src.services.llm_reasoning.LLMReasoningClient", DummyReasoningClient)

    state = {
        "batch_id": "batch_retry_fail",
        "student_results": [_build_student_result()],
        "parsed_rubric": {"questions": [{"question_id": "1", "max_score": 5}]},
        "api_key": "fake-key",
        "inputs": {},
        "timestamps": {},
    }

    result = asyncio.run(batch_grading_module.logic_review_node(state))
    student = result["student_results"][0]
    coverage = student["logic_review"]["coverage"]
    reviews = student["logic_review"]["question_reviews"]

    assert calls["stream"] == 2
    assert coverage["retried"] is True
    assert coverage["valid"] is False
    assert reviews[0]["question_id"] == "1"
    assert reviews[0]["confidence"] == pytest.approx(0.35)
    # fallback policy: keep original grading unchanged
    assert student["question_details"][0]["score"] == 2.0
