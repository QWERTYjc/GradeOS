"""Run observability API routes."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.dependencies import get_orchestrator
from src.models.run_lifecycle import RunMetricsResponse
from src.orchestration.base import Orchestrator


router = APIRouter(prefix="/runs", tags=["run-observability"])


def _require_orchestrator(orchestrator: Orchestrator | None) -> Orchestrator:
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator is not initialized")
    return orchestrator


@router.get("/{run_id}/metrics", response_model=RunMetricsResponse)
async def get_run_metrics(
    run_id: str,
    orchestrator: Orchestrator = Depends(get_orchestrator),
) -> RunMetricsResponse:
    orchestrator = _require_orchestrator(orchestrator)
    payload = await orchestrator.get_run_metrics(run_id)
    if not payload:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunMetricsResponse(**payload)


@router.get("/{run_id}/events")
async def get_run_events(
    run_id: str,
    after_seq: int = Query(0, ge=0, description="Return events with seq > after_seq"),
    limit: int = Query(200, ge=1, le=2000),
    orchestrator: Orchestrator = Depends(get_orchestrator),
) -> Dict[str, Any]:
    orchestrator = _require_orchestrator(orchestrator)
    events = await orchestrator.get_run_events(run_id, after_seq=after_seq, limit=limit)
    next_seq = events[-1]["seq"] if events else after_seq
    return {
        "run_id": run_id,
        "after_seq": after_seq,
        "next_seq": next_seq,
        "count": len(events),
        "events": events,
    }


@router.get("/{run_id}/artifacts/{artifact_id}")
async def get_run_artifact(
    run_id: str,
    artifact_id: str,
    orchestrator: Orchestrator = Depends(get_orchestrator),
) -> Dict[str, Any]:
    orchestrator = _require_orchestrator(orchestrator)
    artifact = await orchestrator.get_run_artifact(run_id, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return artifact
