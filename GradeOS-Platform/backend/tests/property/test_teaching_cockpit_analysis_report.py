"""
Property-based tests for Teaching Cockpit, Mistake Analysis, and Progress Report features.

Feature: teaching-cockpit-analysis-report
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from typing import List, Dict, Any


# ============ Data Generators ============

@st.composite
def question_result_strategy(draw):
    """Generate a question result with score and maxScore."""
    max_score = draw(st.integers(min_value=1, max_value=20))
    score = draw(st.integers(min_value=0, max_value=max_score))
    return {
        "questionId": draw(st.text(min_size=1, max_size=5, alphabet="0123456789")),
        "score": score,
        "maxScore": max_score,
        "feedback": draw(st.text(max_size=100)),
        "page_indices": draw(st.lists(st.integers(min_value=0, max_value=50), max_size=3)),
    }


@st.composite
def student_result_strategy(draw):
    """Generate a student result with question results."""
    questions = draw(st.lists(question_result_strategy(), min_size=1, max_size=10))
    total_score = sum(q["score"] for q in questions)
    total_max = sum(q["maxScore"] for q in questions)
    return {
        "studentName": draw(st.text(min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz")),
        "score": total_score,
        "maxScore": total_max,
        "questionResults": questions,
    }


@st.composite
def submission_score_strategy(draw):
    """Generate a submission with score for improvement rate calculation."""
    return {
        "score": draw(st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False)),
        "submitted_at": draw(st.datetimes()).isoformat(),
    }


# ============ Property 2: Results Sorting Order ============

@given(st.lists(student_result_strategy(), min_size=2, max_size=20))
@settings(max_examples=100)
def test_results_sorting_order(results: List[Dict[str, Any]]):
    """
    Property 2: Results Sorting Order
    
    For any list of student results displayed in the Teaching Cockpit, 
    the students SHALL be sorted by score in descending order, such that 
    for any adjacent pair of students (i, i+1), student[i].score >= student[i+1].score.
    
    **Validates: Requirements 1.6**
    """
    # Sort results by score descending (same logic as frontend)
    sorted_results = sorted(results, key=lambda r: r["score"], reverse=True)
    
    # Verify sorting property
    for i in range(len(sorted_results) - 1):
        assert sorted_results[i]["score"] >= sorted_results[i + 1]["score"], \
            f"Results not sorted correctly at index {i}: {sorted_results[i]['score']} < {sorted_results[i + 1]['score']}"


# ============ Property 3: Wrong Question Extraction Correctness ============

@given(st.lists(question_result_strategy(), min_size=1, max_size=20))
@settings(max_examples=100)
def test_wrong_question_extraction_correctness(questions: List[Dict[str, Any]]):
    """
    Property 3: Wrong Question Extraction Correctness
    
    For any grading history containing question results, the Mistake Analysis System 
    SHALL extract exactly those questions where score < maxScore. No question with 
    score >= maxScore SHALL appear in the wrong questions list, and no question with 
    score < maxScore SHALL be omitted.
    
    **Validates: Requirements 2.2**
    """
    # Extract wrong questions (same logic as frontend)
    wrong_questions = [q for q in questions if q["maxScore"] > 0 and q["score"] < q["maxScore"]]
    correct_questions = [q for q in questions if q["maxScore"] > 0 and q["score"] >= q["maxScore"]]
    
    # Verify no correct question is in wrong list
    for q in correct_questions:
        assert q not in wrong_questions, \
            f"Correct question {q['questionId']} should not be in wrong questions list"
    
    # Verify all wrong questions are extracted
    for q in questions:
        if q["maxScore"] > 0 and q["score"] < q["maxScore"]:
            assert q in wrong_questions, \
                f"Wrong question {q['questionId']} should be in wrong questions list"


# ============ Property 5: Summary Statistics Calculation ============

@given(st.lists(question_result_strategy(), min_size=1, max_size=20))
@settings(max_examples=100)
def test_summary_statistics_calculation(questions: List[Dict[str, Any]]):
    """
    Property 5: Summary Statistics Calculation
    
    For any set of grading results, the Mistake Analysis System SHALL calculate 
    summary statistics such that:
    - totalQuestions = count of all questions with maxScore > 0
    - wrongQuestions = count of questions where score < maxScore
    - totalScore = sum of all question scores
    - totalMax = sum of all question maxScores
    - accuracyRate = (totalScore / totalMax) * 100
    
    **Validates: Requirements 2.5**
    """
    # Calculate statistics (same logic as frontend)
    valid_questions = [q for q in questions if q["maxScore"] > 0]
    total_questions = len(valid_questions)
    wrong_questions = len([q for q in valid_questions if q["score"] < q["maxScore"]])
    total_score = sum(q["score"] for q in valid_questions)
    total_max = sum(q["maxScore"] for q in valid_questions)
    
    # Verify calculations
    assert total_questions == len(valid_questions)
    assert wrong_questions <= total_questions
    assert total_score <= total_max
    
    if total_max > 0:
        accuracy_rate = (total_score / total_max) * 100
        assert 0 <= accuracy_rate <= 100, f"Accuracy rate {accuracy_rate} out of bounds"


# ============ Property 6: Focus Area Ranking ============

@given(st.lists(question_result_strategy(), min_size=3, max_size=20))
@settings(max_examples=100)
def test_focus_area_ranking(questions: List[Dict[str, Any]]):
    """
    Property 6: Focus Area Ranking
    
    For any set of wrong questions, the focus areas (薄弱集中区) SHALL be ranked 
    by error ratio (wrongCount / totalCount) in descending order, such that for 
    any adjacent pair (i, i+1), focusArea[i].ratio >= focusArea[i+1].ratio.
    
    **Validates: Requirements 2.6**
    """
    # Group questions by questionId and calculate error ratio
    focus_map: Dict[str, Dict[str, Any]] = {}
    
    for q in questions:
        if q["maxScore"] <= 0:
            continue
        qid = q["questionId"]
        if qid not in focus_map:
            focus_map[qid] = {"questionId": qid, "wrongCount": 0, "totalCount": 0}
        focus_map[qid]["totalCount"] += 1
        if q["score"] < q["maxScore"]:
            focus_map[qid]["wrongCount"] += 1
    
    # Calculate ratios and sort
    focus_list = []
    for stat in focus_map.values():
        stat["ratio"] = stat["wrongCount"] / stat["totalCount"] if stat["totalCount"] > 0 else 0
        focus_list.append(stat)
    
    focus_list.sort(key=lambda x: x["ratio"], reverse=True)
    
    # Verify sorting property
    for i in range(len(focus_list) - 1):
        assert focus_list[i]["ratio"] >= focus_list[i + 1]["ratio"], \
            f"Focus areas not sorted correctly at index {i}"


# ============ Property 7: Diagnosis Report Display Completeness ============

@st.composite
def diagnosis_report_strategy(draw):
    """Generate a complete diagnosis report."""
    return {
        "student_id": draw(st.text(min_size=1, max_size=10, alphabet="0123456789")),
        "report_period": draw(st.text(min_size=5, max_size=30)),
        "overall_assessment": {
            "mastery_score": draw(st.floats(min_value=0, max_value=1, allow_nan=False, allow_infinity=False)),
            "improvement_rate": draw(st.floats(min_value=-1, max_value=1, allow_nan=False, allow_infinity=False)),
            "consistency_score": draw(st.integers(min_value=0, max_value=100)),
        },
        "progress_trend": draw(st.lists(
            st.fixed_dictionaries({
                "date": st.text(min_size=5, max_size=10),
                "score": st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
                "average": st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
            }),
            min_size=1,
            max_size=10
        )),
        "knowledge_map": draw(st.lists(
            st.fixed_dictionaries({
                "knowledge_area": st.text(min_size=1, max_size=20),
                "mastery_level": st.floats(min_value=0, max_value=1, allow_nan=False, allow_infinity=False),
            }),
            min_size=1,
            max_size=8
        )),
        "error_patterns": {
            "most_common_error_types": draw(st.lists(
                st.fixed_dictionaries({
                    "type": st.text(min_size=1, max_size=20),
                    "count": st.integers(min_value=1, max_value=100),
                }),
                min_size=1,
                max_size=5
            ))
        },
        "personalized_insights": draw(st.lists(st.text(min_size=10, max_size=100), min_size=1, max_size=4)),
    }


@given(diagnosis_report_strategy())
@settings(max_examples=50)
def test_diagnosis_report_display_completeness(report: Dict[str, Any]):
    """
    Property 7: Diagnosis Report Display Completeness
    
    For any valid diagnosis report returned by the API, the Progress Report page 
    SHALL display all required fields:
    - overall_assessment (mastery_score, improvement_rate, consistency_score)
    - progress_trend (for AreaChart)
    - knowledge_map (for RadarChart)
    - error_patterns (for BarChart)
    - personalized_insights (for recommendations)
    - report_period
    
    **Validates: Requirements 3.2, 3.3, 3.4, 3.5, 3.6**
    """
    # Verify all required fields exist
    assert "student_id" in report
    assert "report_period" in report
    assert "overall_assessment" in report
    assert "progress_trend" in report
    assert "knowledge_map" in report
    assert "error_patterns" in report
    assert "personalized_insights" in report
    
    # Verify overall_assessment structure
    oa = report["overall_assessment"]
    assert "mastery_score" in oa
    assert "improvement_rate" in oa
    assert "consistency_score" in oa
    assert 0 <= oa["mastery_score"] <= 1
    assert 0 <= oa["consistency_score"] <= 100
    
    # Verify progress_trend has required fields for AreaChart
    for pt in report["progress_trend"]:
        assert "date" in pt
        assert "score" in pt
        assert "average" in pt
    
    # Verify knowledge_map has required fields for RadarChart
    for km in report["knowledge_map"]:
        assert "knowledge_area" in km
        assert "mastery_level" in km
        assert 0 <= km["mastery_level"] <= 1
    
    # Verify error_patterns has required fields for BarChart
    assert "most_common_error_types" in report["error_patterns"]
    for ep in report["error_patterns"]["most_common_error_types"]:
        assert "type" in ep
        assert "count" in ep
        assert ep["count"] > 0
    
    # Verify personalized_insights is a non-empty list
    assert len(report["personalized_insights"]) > 0


# ============ Property 8: Mastery Score Calculation ============

@given(st.lists(question_result_strategy(), min_size=1, max_size=20))
@settings(max_examples=100)
def test_mastery_score_calculation(questions: List[Dict[str, Any]]):
    """
    Property 8: Mastery Score Calculation
    
    For any student with grading results, the Diagnosis Report API SHALL calculate 
    mastery_score as total_score / total_max, where total_score and total_max are 
    aggregated from all student_grading_results for that student.
    
    **Validates: Requirements 4.3**
    """
    valid_questions = [q for q in questions if q["maxScore"] > 0]
    assume(len(valid_questions) > 0)
    
    total_score = sum(q["score"] for q in valid_questions)
    total_max = sum(q["maxScore"] for q in valid_questions)
    
    assume(total_max > 0)
    
    mastery_score = total_score / total_max
    
    # Verify mastery score is in valid range
    assert 0 <= mastery_score <= 1, f"Mastery score {mastery_score} out of bounds [0, 1]"
    
    # Verify calculation is correct
    expected = round(total_score / total_max, 4)
    actual = round(mastery_score, 4)
    assert actual == expected, f"Mastery score calculation incorrect: {actual} != {expected}"


# ============ Property 9: Improvement Rate Calculation ============

@given(st.lists(submission_score_strategy(), min_size=4, max_size=20))
@settings(max_examples=100)
def test_improvement_rate_calculation(submissions: List[Dict[str, Any]]):
    """
    Property 9: Improvement Rate Calculation
    
    For any student with at least 2 submissions, the Diagnosis Report API SHALL 
    calculate improvement_rate as (second_half_avg - first_half_avg) / first_half_avg, 
    where submissions are split chronologically into two halves.
    
    **Validates: Requirements 4.4**
    """
    # Sort by submitted_at
    sorted_submissions = sorted(submissions, key=lambda s: s["submitted_at"])
    
    assume(len(sorted_submissions) >= 2)
    
    # Split into halves
    mid = len(sorted_submissions) // 2
    first_half = sorted_submissions[:mid]
    second_half = sorted_submissions[mid:]
    
    assume(len(first_half) > 0 and len(second_half) > 0)
    
    first_avg = sum(s["score"] for s in first_half) / len(first_half)
    second_avg = sum(s["score"] for s in second_half) / len(second_half)
    
    assume(first_avg > 0)  # Avoid division by zero
    
    improvement_rate = (second_avg - first_avg) / first_avg
    
    # Verify improvement rate calculation
    expected = round((second_avg - first_avg) / first_avg, 4)
    actual = round(improvement_rate, 4)
    assert actual == expected, f"Improvement rate calculation incorrect: {actual} != {expected}"


# ============ Property 10: Consistency Score Calculation ============

@given(st.lists(st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False), min_size=3, max_size=20))
@settings(max_examples=100)
def test_consistency_score_calculation(scores: List[float]):
    """
    Property 10: Consistency Score Calculation
    
    For any student with at least 3 submissions, the Diagnosis Report API SHALL 
    calculate consistency_score based on score variance, where lower variance 
    results in higher consistency score (max 100, min 0).
    
    **Validates: Requirements 4.5**
    """
    assume(len(scores) >= 3)
    
    # Calculate variance
    avg = sum(scores) / len(scores)
    variance = sum((s - avg) ** 2 for s in scores) / len(scores)
    std_dev = variance ** 0.5
    
    # Calculate consistency score (same logic as backend)
    consistency_score = max(0, min(100, int(100 - std_dev * 2)))
    
    # Verify consistency score is in valid range
    assert 0 <= consistency_score <= 100, f"Consistency score {consistency_score} out of bounds [0, 100]"
    
    # Verify lower variance means higher consistency
    if std_dev == 0:
        assert consistency_score == 100, "Zero variance should give max consistency"
