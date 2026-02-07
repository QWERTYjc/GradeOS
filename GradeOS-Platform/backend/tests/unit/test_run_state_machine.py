from src.models.run_lifecycle import FailureClass, RunState
from src.services.run_state_machine import RunStateMachine, classify_failure, map_legacy_status


def test_map_legacy_status() -> None:
    assert map_legacy_status("pending") == RunState.CREATED
    assert map_legacy_status("running") == RunState.RUNNING
    assert map_legacy_status("paused") == RunState.RUNNING
    assert map_legacy_status("partial") == RunState.PARTIAL_FAILED
    assert map_legacy_status("completed") == RunState.COMPLETED
    assert map_legacy_status("cancelled") == RunState.CANCELLED


def test_state_machine_transitions() -> None:
    sm = RunStateMachine()
    sm.set_initial("run-1")
    ok = sm.transition("run-1", RunState.RUNNING)
    assert ok.valid is True
    assert ok.current == RunState.RUNNING

    ok = sm.transition("run-1", RunState.RETRYING)
    assert ok.valid is True
    assert ok.current == RunState.RETRYING

    ok = sm.transition("run-1", RunState.COMPLETED)
    assert ok.valid is True
    assert ok.current == RunState.COMPLETED

    invalid = sm.transition("run-1", RunState.RUNNING)
    assert invalid.valid is False
    assert invalid.current == RunState.COMPLETED


def test_classify_failure() -> None:
    assert classify_failure("rate limit exceeded") == FailureClass.RETRYABLE
    assert classify_failure("human review required for this page") == FailureClass.HUMAN_REVIEW_REQUIRED
    assert classify_failure("permission denied") == FailureClass.NON_RETRYABLE
    assert classify_failure("user cancelled run") == FailureClass.USER_CANCELLED
