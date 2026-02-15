import asyncio
import json

import pytest

from src.services.rubric_parser import RubricParserService, _extract_questions_from_plain_text


class _FakeReasoningClient:
    def __init__(self, response_text: str):
        self._response_text = response_text

    async def analyze_with_vision(self, *, images, prompt, stream_callback=None):
        return {"response": self._response_text}


def _build_parser_with_response(response_text: str) -> RubricParserService:
    parser = RubricParserService.__new__(RubricParserService)
    parser.reasoning_client = _FakeReasoningClient(response_text)
    return parser


def test_extract_questions_from_plain_text_parses_two_questions():
    text = """GRADEOS TEST RUBRIC
Question 1 (5 marks)
Q1.1 Identify median correctly - 2 marks
Q1.2 Explain quartile reasoning - 3 marks

Question 2 (5 marks)
Q2.1 Correct mode reasoning - 2 marks
Q2.2 Correct standard deviation comparison - 3 marks

Total score: 10
General notes:
Award marks only when evidence appears in answer.
"""

    result = _extract_questions_from_plain_text(text)

    assert len(result["questions"]) == 2
    assert result["questions"][0]["question_id"] == "1"
    assert result["questions"][1]["question_id"] == "2"
    assert result["questions"][0]["max_score"] == 5
    assert result["questions"][1]["max_score"] == 5
    assert len(result["questions"][0]["scoring_points"]) == 2
    assert len(result["questions"][1]["scoring_points"]) == 2
    assert result["total_score"] == 10


def test_parse_rubric_batch_supports_alias_field_shapes():
    payload = {
        "rubric": {
            "general_notes": "alias payload",
            "questionRubrics": [
                {
                    "id": "1",
                    "maxScore": 5,
                    "questionText": "Question 1 (5 marks)",
                    "criteria": [
                        {"text": "Identify median correctly", "points": 2},
                        {"text": "Explain quartile reasoning", "points": 3},
                    ],
                },
                {
                    "_id": "2",
                    "maxScore": 5,
                    "questionText": "Question 2 (5 marks)",
                    "criteria": [
                        {"text": "Correct mode reasoning", "points": 2},
                        {"text": "Correct standard deviation comparison", "points": 3},
                    ],
                },
            ],
        }
    }
    parser = _build_parser_with_response(json.dumps(payload, ensure_ascii=False))

    result = asyncio.run(
        parser._parse_rubric_batch(
            rubric_images=[b"fake-image"],
            batch_num=1,
            total_batches=1,
            stream_callback=None,
        )
    )

    assert result.total_questions == 2
    assert result.total_score == 10
    assert [q.question_id for q in result.questions] == ["1", "2"]
    assert [q.max_score for q in result.questions] == [5, 5]
    assert len(result.questions[0].scoring_points) == 2
    assert len(result.questions[1].scoring_points) == 2


def test_parse_rubric_batch_falls_back_to_plain_text_without_json():
    plain_text = """GRADEOS TEST RUBRIC
Question 1 (5 marks)
Q1.1 Identify median correctly - 2 marks
Q1.2 Explain quartile reasoning - 3 marks

Question 2 (5 marks)
Q2.1 Correct mode reasoning - 2 marks
Q2.2 Correct standard deviation comparison - 3 marks

Total score: 10
"""
    parser = _build_parser_with_response(plain_text)

    result = asyncio.run(
        parser._parse_rubric_batch(
            rubric_images=[b"fake-image"],
            batch_num=1,
            total_batches=1,
            stream_callback=None,
        )
    )

    assert result.total_questions == 2
    assert result.total_score == 10
    assert [q.question_id for q in result.questions] == ["1", "2"]
