"""Run state machine and failure classification helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Set, Tuple

from src.models.run_lifecycle import FailureClass, RunState


_ALLOWED_TRANSITIONS: Dict[RunState, Set[RunState]] = {
    RunState.CREATED: {
        RunState.RUNNING,
        RunState.FAILED,
        RunState.CANCELLED,
    },
    RunState.RUNNING: {
        RunState.RETRYING,
        RunState.PARTIAL_FAILED,
        RunState.COMPLETED,
        RunState.FAILED,
        RunState.CANCELLED,
    },
    RunState.RETRYING: {
        RunState.RUNNING,
        RunState.PARTIAL_FAILED,
        RunState.COMPLETED,
        RunState.FAILED,
        RunState.CANCELLED,
    },
    RunState.PARTIAL_FAILED: {
        RunState.RETRYING,
        RunState.COMPLETED,
        RunState.FAILED,
        RunState.CANCELLED,
    },
    RunState.COMPLETED: set(),
    RunState.FAILED: set(),
    RunState.CANCELLED: set(),
}


def map_legacy_status(status: str) -> RunState:
    """Map existing run status values to the unified run state."""
    normalized = (status or "").strip().lower()
    if normalized in {"pending", "created"}:
        return RunState.CREATED
    if normalized in {"running", "paused"}:
        return RunState.RUNNING
    if normalized in {"retrying"}:
        return RunState.RETRYING
    if normalized in {"partial", "partial_failed"}:
        return RunState.PARTIAL_FAILED
    if normalized in {"completed"}:
        return RunState.COMPLETED
    if normalized in {"cancelled"}:
        return RunState.CANCELLED
    return RunState.FAILED


def classify_failure(error_text: Optional[str]) -> FailureClass:
    """Classify failures into retryable/non-retryable/human-review classes."""
    if not error_text:
        return FailureClass.UNKNOWN

    text = error_text.lower()
    if any(k in text for k in ("cancel", "user abort", "user cancelled")):
        return FailureClass.USER_CANCELLED
    if any(k in text for k in ("timeout", "rate limit", "429", "temporarily unavailable")):
        return FailureClass.RETRYABLE
    if any(k in text for k in ("review required", "human review", "manual review")):
        return FailureClass.HUMAN_REVIEW_REQUIRED
    if any(k in text for k in ("invalid", "malformed", "schema", "permission", "auth")):
        return FailureClass.NON_RETRYABLE
    return FailureClass.UNKNOWN


@dataclass
class TransitionResult:
    previous: RunState
    current: RunState
    valid: bool


class RunStateMachine:
    """Minimal in-memory run state machine with transition validation."""

    def __init__(self) -> None:
        self._states: Dict[str, RunState] = {}

    def get(self, run_id: str) -> Optional[RunState]:
        return self._states.get(run_id)

    def set_initial(self, run_id: str, state: RunState = RunState.CREATED) -> TransitionResult:
        prev = self._states.get(run_id, state)
        self._states[run_id] = state
        return TransitionResult(previous=prev, current=state, valid=True)

    def transition(self, run_id: str, next_state: RunState) -> TransitionResult:
        current = self._states.get(run_id, RunState.CREATED)
        allowed = _ALLOWED_TRANSITIONS.get(current, set())
        valid = next_state == current or next_state in allowed
        if valid:
            self._states[run_id] = next_state
            return TransitionResult(previous=current, current=next_state, valid=True)
        # Keep current state unchanged when transition is invalid.
        return TransitionResult(previous=current, current=current, valid=False)

    def transition_from_legacy(self, run_id: str, legacy_status: str) -> TransitionResult:
        return self.transition(run_id, map_legacy_status(legacy_status))

    def clear(self, run_id: str) -> None:
        self._states.pop(run_id, None)

    def clear_all(self) -> None:
        self._states.clear()
