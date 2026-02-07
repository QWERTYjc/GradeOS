"""Run lifecycle and observability models."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class RunState(str, Enum):
    """Unified run state used by orchestration and observability."""

    CREATED = "created"
    RUNNING = "running"
    RETRYING = "retrying"
    PARTIAL_FAILED = "partial_failed"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FailureClass(str, Enum):
    """Failure classes used for incident triage."""

    RETRYABLE = "retryable"
    NON_RETRYABLE = "non_retryable"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    USER_CANCELLED = "user_cancelled"
    UNKNOWN = "unknown"


class ArtifactRef(BaseModel):
    """Reference object for large artifacts."""

    artifact_id: str = Field(..., description="Artifact unique id")
    uri: str = Field(..., description="Artifact URI or route path")
    hash: Optional[str] = Field(None, description="Artifact hash for cache keying")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class CostMetric(BaseModel):
    """Cost metric payload for a run."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    model_breakdown: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class QualityMetric(BaseModel):
    """Quality metric payload for a run."""

    failure_rate: float = 0.0
    retry_rate: float = 0.0
    review_trigger_rate: float = 0.0
    consistency_variance: Optional[float] = None


class RunMetricsResponse(BaseModel):
    """Metrics response model."""

    run_id: str
    graph_name: str
    run_state: RunState
    legacy_status: str
    failure_class: Optional[FailureClass] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = None
    event_count: int = 0
    llm_stream_chunks: int = 0
    cost: CostMetric = Field(default_factory=CostMetric)
    quality: QualityMetric = Field(default_factory=QualityMetric)
    extra: Dict[str, Any] = Field(default_factory=dict)
