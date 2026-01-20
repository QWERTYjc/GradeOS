# GradeOS

Vision-native AI grading platform built on FastAPI, LangGraph, and Next.js 16.
The system ingests rubric PDFs and student submissions, orchestrates multi-step grading,
and streams progress and results to the UI.

## Overview
- Vision-first grading pipeline (no OCR-first dependency)
- Multi-agent orchestration via LangGraph
- Batch grading with WebSocket progress updates
- Human-in-the-loop review and export-ready results
- SQLite by default, PostgreSQL supported; optional no-database mode

## Architecture
Four-layer flow used across backend services:
1) Ingestion: FastAPI + WebSocket + object storage inputs
2) Orchestration: LangGraph state machine and retry policies
3) Cognitive: multi-agent grading logic (Supervisor + specialized agents)
4) Persistence: grading history, student results, analytics

## Repository Structure
- `GradeOS-Platform/backend`: FastAPI + LangGraph backend
- `GradeOS-Platform/frontend`: Next.js 16 frontend
- `GradeOS-Platform/docs`: backend documentation
- `GradeOS-Platform/docs/research`: local test PDFs and images

## Backend Modules (Key)
- `GradeOS-Platform/backend/src/api`: REST + WebSocket endpoints
- `GradeOS-Platform/backend/src/graphs`: LangGraph workflows and nodes
- `GradeOS-Platform/backend/src/orchestration`: orchestration runtime
- `GradeOS-Platform/backend/src/services`: grading, parsing, caching, analytics
- `GradeOS-Platform/backend/src/db`: SQLite/PostgreSQL access
- `GradeOS-Platform/backend/src/utils`: shared helpers

## Frontend Modules (Key)
- `GradeOS-Platform/frontend/src/app`: Next.js App Router pages
- `GradeOS-Platform/frontend/src/components`: UI components
- `GradeOS-Platform/frontend/src/services`: API + WebSocket clients
- `GradeOS-Platform/frontend/src/store`: Zustand state

## Grading Workflow (LangGraph)
1) Intake: receive PDFs and store pages
2) Preprocess: image normalization
3) Index: detect student page boundaries
4) Rubric parse: extract rubric points and scores
5) Rubric review: optional human check
6) Grading: per-student, per-question scoring
7) Merge + review: cross-page aggregation and QA
8) Export: persist results and emit progress

## API Surface (Primary)
Base path: `/api`
- POST `/api/batch/submit`: submit batch grading
- GET `/api/batch/status/{batch_id}`: grading status
- GET `/api/batch/results/{batch_id}`: grading results
- GET `/api/batch/rubric/{batch_id}`: parsed rubric
- WS `/api/batch/ws/{batch_id}`: live progress stream

## LLM Configuration (OpenRouter)
All LLM calls route through OpenRouter-compatible APIs.

Environment variables:
- `LLM_API_KEY`: OpenRouter API key (required)
- `OPENROUTER_API_KEY`: fallback key
- `LLM_DEFAULT_MODEL`: default model name (default: `google/gemini-3-flash-preview`)
- `LLM_VISION_MODEL`, `LLM_TEXT_MODEL`, `LLM_RUBRIC_MODEL`, `LLM_GRADING_MODEL`, `LLM_INDEX_MODEL`
- `LLM_BASE_URL`: default `https://openrouter.ai/api/v1`
- `LLM_SITE_URL`, `LLM_SITE_TITLE`: OpenRouter headers

## Development
Backend (local):
```bash
cd GradeOS-Platform/backend
uv sync
uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8001 --reload
```

Backend (Docker compose):
```bash
cd GradeOS-Platform/backend
make dev
```

Frontend:
```bash
cd GradeOS-Platform/frontend
npm install
# Optional: set API base to backend
# NEXT_PUBLIC_API_URL=http://localhost:8001/api
npm run dev
```

## Testing
Backend:
```bash
cd GradeOS-Platform/backend
make test
```

## Deployment
- Docker compose for local development (`GradeOS-Platform/backend/docker-compose.yml`)
- Kubernetes + KEDA autoscaling configs in `GradeOS-Platform/backend/k8s`

## Project Status
- Core grading pipeline is implemented with LangGraph.
- Some features are marked TODO (image preprocessing, notifications, Redis integration).
- Frontend has no automated test suite yet.

## Documentation
- Backend guides live in `GradeOS-Platform/backend/docs`
- Research fixtures live in `GradeOS-Platform/docs/research`

## License
MIT
