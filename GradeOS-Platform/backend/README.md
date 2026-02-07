# GradeOS Backend

AI-powered grading backend built on FastAPI and LangGraph.

## Stack
- FastAPI
- LangGraph
- PostgreSQL (optional in no-db mode)
- Redis (optional in no-db mode)

## Quick Start

### No-Database Mode
```bash
uv sync
export LLM_API_KEY="your-api-key"
uvicorn src.api.main:app --reload --port 8001
```

### Database Mode
```bash
uv sync
cp .env.example .env
# set LLM_API_KEY, DATABASE_URL, REDIS_URL
uv run alembic upgrade head
uvicorn src.api.main:app --reload --port 8001
```

## Main Endpoints
- `GET /health`
- `POST /api/homework/submit-scan`
- `POST /api/batch/submit`
- `GET /api/batch/status/{batch_id}`
- `GET /api/batch/results/{batch_id}`
- `WS /api/batch/ws/{batch_id}`
- `GET /api/runs/{run_id}/metrics`
- `GET /api/runs/{run_id}/events?after_seq=`
- `GET /api/runs/{run_id}/artifacts/{artifact_id}`

## Runtime Controls
- `RUN_MAX_CONCURRENCY`: max concurrent active runs in orchestrator.
- `TEACHER_MAX_ACTIVE_RUNS`: per-teacher active run slots.
- `RUN_MAX_PARALLEL_LLM_CALLS`: global max parallel LLM calls for orchestration.
- `RUN_BATCH_CHUNK_SIZE`: grading batch chunk size (default `50`).
- `SOFT_BUDGET_USD_PER_RUN`: soft budget warning threshold per run (`0` disables).
- `BATCH_IMAGE_CACHE_MAX_BATCHES`: in-memory image cache batch cap.
- `RUN_UPLOAD_QUEUE_WATERMARK`: optional queued-run watermark per teacher (`0` disables).
- `RUN_UPLOAD_ACTIVE_WATERMARK`: optional active-run watermark per teacher (`0` disables).

## Notes
- Legacy grading route modules were removed.
- Worker image now runs a single LangGraph worker entrypoint.
