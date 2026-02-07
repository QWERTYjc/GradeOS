"""Run observability store for events, metrics and artifact references."""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional

from src.models.run_lifecycle import CostMetric, FailureClass, QualityMetric, RunMetricsResponse, RunState
from src.services.state_snapshot import extract_artifact_refs


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunObservabilityStore:
    """In-memory run observability store with bounded event history."""

    def __init__(self, max_events_per_run: int = 5000) -> None:
        self._max_events_per_run = max_events_per_run
        self._events: Dict[str, Deque[Dict[str, Any]]] = defaultdict(deque)
        self._seq: Dict[str, int] = defaultdict(int)
        self._meta: Dict[str, Dict[str, Any]] = {}
        self._artifacts: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)

    def register_run(self, run_id: str, graph_name: str, legacy_status: str) -> None:
        if run_id in self._meta:
            return
        self._meta[run_id] = {
            "run_id": run_id,
            "graph_name": graph_name,
            "legacy_status": legacy_status,
            "run_state": RunState.CREATED.value,
            "failure_class": None,
            "created_at": _now_iso(),
            "started_at": None,
            "completed_at": None,
            "duration_ms": None,
            "event_count": 0,
            "llm_stream_chunks": 0,
            "retry_count": 0,
            "error_count": 0,
            "review_trigger_count": 0,
            "cost": CostMetric().model_dump(),
            "quality": QualityMetric().model_dump(),
            "extra": {},
        }

    def push_event(self, run_id: str, kind: str, name: Optional[str], data: Dict[str, Any]) -> Dict[str, Any]:
        seq = self._seq[run_id] + 1
        self._seq[run_id] = seq
        event = {
            "seq": seq,
            "timestamp": _now_iso(),
            "kind": kind,
            "name": name,
            "data": data or {},
        }
        queue = self._events[run_id]
        queue.append(event)
        if len(queue) > self._max_events_per_run:
            queue.popleft()

        meta = self._meta.get(run_id)
        if meta:
            meta["event_count"] += 1
            if kind == "llm_stream":
                meta["llm_stream_chunks"] += 1
            if kind == "error":
                meta["error_count"] += 1
            if kind in {"review_required", "human_review_required"}:
                meta["review_trigger_count"] += 1
            if kind == "retry":
                meta["retry_count"] += 1
            self._merge_usage_metrics(meta, data)
        return event

    def list_events(self, run_id: str, after_seq: int = 0, limit: int = 200) -> List[Dict[str, Any]]:
        if limit <= 0:
            return []
        events = self._events.get(run_id)
        if not events:
            return []
        selected = [item for item in events if int(item.get("seq", 0)) > int(after_seq)]
        return selected[:limit]

    def update_state(
        self,
        run_id: str,
        run_state: RunState,
        legacy_status: str,
        *,
        failure_class: Optional[FailureClass] = None,
    ) -> None:
        meta = self._meta.get(run_id)
        if not meta:
            return
        now = _now_iso()
        if run_state == RunState.RUNNING and not meta.get("started_at"):
            meta["started_at"] = now
        if run_state in {RunState.COMPLETED, RunState.FAILED, RunState.CANCELLED}:
            meta["completed_at"] = now
            started = meta.get("started_at")
            if started:
                try:
                    started_dt = datetime.fromisoformat(started.replace("Z", ""))
                    end_dt = datetime.fromisoformat(now.replace("Z", ""))
                    meta["duration_ms"] = int((end_dt - started_dt).total_seconds() * 1000)
                except Exception:
                    meta["duration_ms"] = None
        meta["run_state"] = run_state.value
        meta["legacy_status"] = legacy_status
        if failure_class is not None:
            meta["failure_class"] = failure_class.value
        self._refresh_quality(meta)

    def finalize_output(self, run_id: str, output_state: Optional[Dict[str, Any]]) -> None:
        if not isinstance(output_state, dict):
            return
        refs = extract_artifact_refs(run_id, output_state)
        if refs:
            self._artifacts[run_id].update(refs)

    def add_artifact(self, run_id: str, artifact: Dict[str, Any]) -> None:
        artifact_id = artifact.get("artifact_id")
        if not artifact_id:
            return
        self._artifacts[run_id][str(artifact_id)] = artifact

    def get_artifact(self, run_id: str, artifact_id: str) -> Optional[Dict[str, Any]]:
        return self._artifacts.get(run_id, {}).get(artifact_id)

    def list_artifacts(self, run_id: str) -> List[Dict[str, Any]]:
        artifacts = self._artifacts.get(run_id, {})
        return list(artifacts.values())

    def build_metrics(self, run_id: str) -> Optional[RunMetricsResponse]:
        meta = self._meta.get(run_id)
        if not meta:
            return None
        cost = CostMetric(**meta.get("cost", {}))
        quality = QualityMetric(**meta.get("quality", {}))
        return RunMetricsResponse(
            run_id=run_id,
            graph_name=meta.get("graph_name", ""),
            run_state=RunState(meta.get("run_state", RunState.CREATED.value)),
            legacy_status=meta.get("legacy_status", "pending"),
            failure_class=FailureClass(meta["failure_class"]) if meta.get("failure_class") else None,
            started_at=meta.get("started_at"),
            completed_at=meta.get("completed_at"),
            duration_ms=meta.get("duration_ms"),
            event_count=int(meta.get("event_count", 0)),
            llm_stream_chunks=int(meta.get("llm_stream_chunks", 0)),
            cost=cost,
            quality=quality,
            extra=dict(meta.get("extra", {})),
        )

    def _merge_usage_metrics(self, meta: Dict[str, Any], data: Dict[str, Any]) -> None:
        if not isinstance(data, dict):
            return
        usage = data.get("usage") or data.get("token_usage")
        if not isinstance(usage, dict):
            return

        in_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
        out_tokens = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
        total = int(usage.get("total_tokens") or (in_tokens + out_tokens))
        est_cost = float(usage.get("estimated_cost_usd") or 0.0)
        model_name = usage.get("model")

        cost = meta.setdefault("cost", CostMetric().model_dump())
        cost["input_tokens"] = int(cost.get("input_tokens", 0)) + in_tokens
        cost["output_tokens"] = int(cost.get("output_tokens", 0)) + out_tokens
        cost["total_tokens"] = int(cost.get("total_tokens", 0)) + total
        cost["estimated_cost_usd"] = float(cost.get("estimated_cost_usd", 0.0)) + est_cost

        if model_name:
            breakdown = cost.setdefault("model_breakdown", {})
            model_payload = breakdown.setdefault(
                str(model_name),
                {"calls": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            )
            model_payload["calls"] += 1
            model_payload["input_tokens"] += in_tokens
            model_payload["output_tokens"] += out_tokens
            model_payload["total_tokens"] += total

    def _refresh_quality(self, meta: Dict[str, Any]) -> None:
        retries = int(meta.get("retry_count", 0))
        errors = int(meta.get("error_count", 0))
        events = max(1, int(meta.get("event_count", 0)))
        reviews = int(meta.get("review_trigger_count", 0))

        quality = meta.setdefault("quality", QualityMetric().model_dump())
        quality["retry_rate"] = retries / events
        quality["failure_rate"] = errors / events
        quality["review_trigger_rate"] = reviews / events
