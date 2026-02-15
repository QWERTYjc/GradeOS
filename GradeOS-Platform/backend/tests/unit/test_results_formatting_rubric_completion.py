from src.api.routes.batch_langgraph import _format_results_for_frontend


def test_format_results_generates_stable_question_id_when_missing():
    raw_results = [
        {
            "student_name": "学生A",
            "question_details": [
                {"score": 2, "max_score": 5, "feedback": "题号缺失"},
                {"_id": "2", "score": 1, "max_score": 3, "feedback": "有题号别名"},
            ],
        }
    ]

    formatted = _format_results_for_frontend(raw_results)
    questions = formatted[0]["questionResults"]
    question_ids = [q["questionId"] for q in questions]

    assert "__missing_1" in question_ids
    assert "2" in question_ids


def test_format_results_supports_question_id_alias_chain_from_question_results():
    raw_results = [
        {
            "student_name": "学生B",
            "question_results": [
                {"_id": "7", "score": 4, "maxScore": 6, "feedback": "来自 _id"},
            ],
        }
    ]

    formatted = _format_results_for_frontend(raw_results)
    questions = formatted[0]["questionResults"]

    assert len(questions) == 1
    assert questions[0]["questionId"] == "7"


def test_format_results_supplements_missing_rubric_questions():
    raw_results = [
        {
            "student_name": "学生C",
            "question_details": [
                {"question_id": "1", "score": 3, "max_score": 4, "feedback": "已批改"},
            ],
        }
    ]
    parsed_rubric = {
        "questions": [
            {"question_id": "1", "max_score": 4},
            {"question_id": "2", "max_score": 6},
        ]
    }

    formatted = _format_results_for_frontend(raw_results, parsed_rubric=parsed_rubric)
    student = formatted[0]
    questions = student["questionResults"]
    ids = [q["questionId"] for q in questions]

    assert ids[:2] == ["1", "2"]

    filled = next(q for q in questions if q["questionId"] == "2")
    assert filled["score"] == 0
    assert filled["maxScore"] == 6
    assert "补齐题目" in (filled.get("feedback") or "")

    assert student["score"] == 3
    assert student["maxScore"] == 10

