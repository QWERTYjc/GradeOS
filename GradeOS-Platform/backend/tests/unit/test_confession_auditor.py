from src.services.confession_auditor import (
    CONFESSION_REPORT_VERSION,
    _apply_honesty_penalty,
    postprocess_confession_report,
    should_trigger_logic_review_from_confession,
)


def test_postprocess_confession_report_filters_dedups_and_respects_budget(monkeypatch):
    monkeypatch.delenv("CONFESSION_LOGIC_REVIEW_RISK_THRESHOLD", raising=False)
    monkeypatch.delenv("CONFESSION_LOGIC_REVIEW_WARNING_THRESHOLD", raising=False)

    raw = {
        "version": "anything",
        "scope": "grading",
        "subject_id": "ignored",
        "overall_confidence": 0.99,
        "risk_score": 0.99,
        "items": [
            # Keep: valid, and should win dedup against the warning below.
            {
                "issue_type": "missing_evidence_awarded_positive",
                "severity": "error",
                "question_id": "1",
                "point_id": "1.1",
                "refs": {"page_indices": [1]},
                "impact": {"impact_area": "evidence", "max_delta_points": 2},
                "action": "Check the cited evidence exists for this awarded point.",
            },
            # Drop: deduped by same (issue_type, question_id, point_id) with lower severity.
            {
                "issue_type": "missing_evidence_awarded_positive",
                "severity": "warning",
                "question_id": "1",
                "point_id": "1.1",
                "refs": {"page_indices": [1]},
                "impact": {"impact_area": "evidence", "max_delta_points": 1},
                "action": "Please double-check evidence.",
            },
            # Drop: issue_type not allowed.
            {
                "issue_type": "not_allowed_type",
                "severity": "error",
                "question_id": "2",
                "point_id": "2.1",
                "refs": {"page_indices": [2]},
                "impact": {"impact_area": "evidence"},
                "action": "noop",
            },
            # Drop: invalid severity.
            {
                "issue_type": "missing_evidence",
                "severity": "critical",
                "question_id": "3",
                "point_id": "3.1",
                "refs": {"page_indices": [3]},
                "impact": {"impact_area": "evidence"},
                "action": "noop",
            },
            # Drop: missing refs.
            {
                "issue_type": "missing_evidence",
                "severity": "warning",
                "question_id": "4",
                "point_id": "4.1",
                "refs": {},
                "impact": {"impact_area": "evidence"},
                "action": "Need a ref to be actionable.",
            },
            # Keep: valid second item (to hit budget=2).
            {
                "issue_type": "missing_rubric_reference",
                "severity": "warning",
                "question_id": "5",
                "point_id": "5.2",
                "refs": {"evidence_excerpt": "Awarded points but rubric reference is empty."},
                "impact": {"impact_area": "reference", "max_delta_points": 1},
                "action": "Add the rubric_reference excerpt for this scoring point.",
            },
            # Would be valid but should be truncated by budget.
            {
                "issue_type": "low_confidence",
                "severity": "warning",
                "question_id": "6",
                "point_id": None,
                "refs": {"page_indices": [6]},
                "impact": {"impact_area": "score"},
                "action": "Re-check the reasoning for this question due to low confidence.",
            },
        ],
    }

    report = postprocess_confession_report(raw, scope="grading", subject_id="s1", max_items=2)

    assert report["version"] == CONFESSION_REPORT_VERSION
    assert report["scope"] == "grading"
    assert report["subject_id"] == "s1"
    assert report["budget"]["max_items"] == 2
    assert report["budget"]["emitted_items"] == 2

    items = report["items"]
    assert len(items) == 2

    # Dedup kept the error version.
    assert any(
        i["issue_type"] == "missing_evidence_awarded_positive" and i["severity"] == "error"
        for i in items
    )

    # Only allowed issue_types should remain.
    assert all(i["issue_type"] != "not_allowed_type" for i in items)


def test_should_trigger_logic_review_from_confession_thresholds(monkeypatch):
    monkeypatch.setenv("CONFESSION_LOGIC_REVIEW_RISK_THRESHOLD", "0.30")
    monkeypatch.setenv("CONFESSION_LOGIC_REVIEW_WARNING_THRESHOLD", "3")

    # Conservative default: non-dict means we allow downstream review.
    assert should_trigger_logic_review_from_confession(None) is True

    # Error always triggers.
    report_error = {
        "risk_score": 0.0,
        "items": [
            {
                "issue_type": "missing_evidence_awarded_positive",
                "severity": "error",
                "refs": {"page_indices": [1]},
                "impact": {"impact_area": "evidence"},
                "action": "Check evidence.",
            }
        ],
    }
    assert should_trigger_logic_review_from_confession(report_error) is True

    # Warning threshold triggers.
    report_warns = {"risk_score": 0.0, "items": [{"severity": "warning"}] * 3}
    assert should_trigger_logic_review_from_confession(report_warns) is True

    # Risk threshold triggers.
    report_risk = {"risk_score": 0.30, "items": []}
    assert should_trigger_logic_review_from_confession(report_risk) is True

    # Below thresholds: should not trigger.
    report_low = {"risk_score": 0.29, "items": [{"severity": "warning"}] * 2}
    assert should_trigger_logic_review_from_confession(report_low) is False


def test_apply_honesty_penalty_inserts_omitted_mandatory_items_and_increases_risk():
    student = {
        "student_key": "s1",
        "question_details": [
            {
                "question_id": "1",
                "score": 2,
                "max_score": 5,
                "confidence": 0.9,
                "page_indices": [1],
                "scoring_point_results": [
                    {
                        "point_id": "1.1",
                        "awarded": 2,
                        "max_points": 2,
                        # Missing evidence but awarded positive should be mandatory error.
                        "evidence": "【原文引用】未找到",
                        "rubric_reference": "ref",
                    }
                ],
            }
        ],
    }

    # Model output "dishonestly" omits the mandatory missing_evidence_awarded_positive issue.
    report = {
        "version": CONFESSION_REPORT_VERSION,
        "scope": "grading",
        "subject_id": "s1",
        "overall_confidence": 0.95,
        "risk_score": 0.0,
        "items": [],
    }

    updated = _apply_honesty_penalty(report, student=student, max_items=25)

    assert isinstance(updated.get("honesty"), dict)
    assert updated["honesty"]["omitted_mandatory_issue_count"] >= 1
    assert updated["risk_score"] > 0.0
    assert any(
        i.get("issue_type") == "missing_evidence_awarded_positive" and i.get("severity") == "error"
        for i in updated.get("items", [])
        if isinstance(i, dict)
    )
