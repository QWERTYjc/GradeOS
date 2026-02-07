"""Centralized runtime controls for grading runs and orchestration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _int_env(name: str, default: int, *, min_value: int | None = None) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        value = default
    else:
        try:
            value = int(raw)
        except ValueError:
            value = default
    if min_value is not None and value < min_value:
        return min_value
    return value


def _float_env(name: str, default: float, *, min_value: float | None = None) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        value = default
    else:
        try:
            value = float(raw)
        except ValueError:
            value = default
    if min_value is not None and value < min_value:
        return min_value
    return value


@dataclass(frozen=True)
class RuntimeControls:
    run_max_concurrency: int
    run_max_parallel_llm_calls: int
    run_batch_chunk_size: int
    teacher_max_active_runs: int
    run_queue_poll_seconds: float
    run_queue_timeout_seconds: float
    run_event_buffer_size: int
    soft_budget_usd_per_run: float
    batch_image_cache_max_batches: int
    upload_queue_watermark: int
    upload_active_watermark: int


@lru_cache(maxsize=1)
def get_runtime_controls() -> RuntimeControls:
    """Load runtime controls from env with stable defaults."""
    max_parallel_llm_calls = _int_env("RUN_MAX_PARALLEL_LLM_CALLS", 0)
    if max_parallel_llm_calls <= 0:
        max_parallel_llm_calls = _int_env("LANGGRAPH_MAX_CONCURRENCY", 6, min_value=1)

    run_batch_chunk_size = _int_env("RUN_BATCH_CHUNK_SIZE", 0)
    if run_batch_chunk_size <= 0:
        run_batch_chunk_size = _int_env("GRADING_BATCH_SIZE", 50, min_value=1)

    return RuntimeControls(
        run_max_concurrency=_int_env("RUN_MAX_CONCURRENCY", 100, min_value=0),
        run_max_parallel_llm_calls=max_parallel_llm_calls,
        run_batch_chunk_size=run_batch_chunk_size,
        teacher_max_active_runs=_int_env("TEACHER_MAX_ACTIVE_RUNS", 3, min_value=0),
        run_queue_poll_seconds=_float_env("GRADING_RUN_POLL_SECONDS", 2.0, min_value=0.1),
        run_queue_timeout_seconds=_float_env("GRADING_RUN_WAIT_TIMEOUT_SECONDS", 60.0, min_value=0.0),
        run_event_buffer_size=_int_env("RUN_EVENT_BUFFER_SIZE", 5000, min_value=100),
        soft_budget_usd_per_run=_float_env("SOFT_BUDGET_USD_PER_RUN", 0.0, min_value=0.0),
        batch_image_cache_max_batches=_int_env("BATCH_IMAGE_CACHE_MAX_BATCHES", 50, min_value=1),
        upload_queue_watermark=_int_env("RUN_UPLOAD_QUEUE_WATERMARK", 0, min_value=0),
        upload_active_watermark=_int_env("RUN_UPLOAD_ACTIVE_WATERMARK", 0, min_value=0),
    )

