from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes import runs as runs_route


class _FakeOrchestrator:
    async def get_run_metrics(self, run_id: str) -> Optional[Dict[str, Any]]:
        if run_id != "run-1":
            return None
        return {
            "run_id": run_id,
            "graph_name": "batch_grading",
            "run_state": "running",
            "legacy_status": "running",
            "failure_class": None,
            "started_at": "2026-02-07T00:00:00Z",
            "completed_at": None,
            "duration_ms": None,
            "event_count": 3,
            "llm_stream_chunks": 1,
            "cost": {
                "input_tokens": 10,
                "output_tokens": 5,
                "total_tokens": 15,
                "estimated_cost_usd": 0.0,
                "model_breakdown": {},
            },
            "quality": {
                "failure_rate": 0.0,
                "retry_rate": 0.0,
                "review_trigger_rate": 0.0,
                "consistency_variance": None,
            },
            "extra": {},
        }

    async def get_run_events(
        self, run_id: str, after_seq: int = 0, limit: int = 200
    ) -> List[Dict[str, Any]]:
        events = [
            {"seq": 1, "kind": "on_chain_start", "name": "preprocess", "data": {}, "timestamp": "t1"},
            {"seq": 2, "kind": "llm_stream", "name": "grade", "data": {"chunk": "x"}, "timestamp": "t2"},
            {"seq": 3, "kind": "on_chain_end", "name": "grade", "data": {}, "timestamp": "t3"},
        ]
        return [item for item in events if item["seq"] > after_seq][:limit]

    async def get_run_artifact(self, run_id: str, artifact_id: str) -> Optional[Dict[str, Any]]:
        if artifact_id == "page_1":
            return {
                "artifact_id": artifact_id,
                "uri": "/api/batch/files/file-1/download",
                "metadata": {"page_index": 1},
            }
        return None


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(runs_route.router)
    app.dependency_overrides[runs_route.get_orchestrator] = lambda: _FakeOrchestrator()
    return TestClient(app)


def test_get_run_metrics_api() -> None:
    client = _build_client()
    resp = client.get("/runs/run-1/metrics")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["run_id"] == "run-1"
    assert payload["run_state"] == "running"
    assert payload["event_count"] == 3


def test_get_run_events_api() -> None:
    client = _build_client()
    resp = client.get("/runs/run-1/events?after_seq=1&limit=2")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["count"] == 2
    assert payload["events"][0]["seq"] == 2
    assert payload["next_seq"] == 3


def test_get_run_artifact_api() -> None:
    client = _build_client()
    ok_resp = client.get("/runs/run-1/artifacts/page_1")
    assert ok_resp.status_code == 200
    assert ok_resp.json()["artifact_id"] == "page_1"

    missing_resp = client.get("/runs/run-1/artifacts/missing")
    assert missing_resp.status_code == 404
