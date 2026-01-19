# BACKEND KNOWLEDGE BASE

**Stack**: FastAPI, LangGraph, SQLAlchemy
**Manager**: `uv` for dependencies

## OVERVIEW
The brain of GradeOS. Handles API requests, AI grading workflows (LangGraph), and asynchronous task processing. Supports a unique "No-Database" mode for lightweight deployment.

## STRUCTURE
```
backend/
├── src/
│   ├── api/          # FastAPI routes & middleware
│   ├── graphs/       # LangGraph nodes & edges (Core Logic)
│   ├── services/     # Business logic (Storage, Grading)
│   ├── models/       # Pydantic & SQLAlchemy models
│   └── orchestration/ # LangGraphOrchestrator engine
├── k8s/              # Kubernetes manifests
└── tests/            # Pytest suite (Property & Integration)
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| API entry | `src/api/main.py` | FastAPI app factory |
| LangGraph state machine | `src/orchestration/langgraph_orchestrator.py` | Core engine |
| Grading workflow | `src/graphs/batch_grading.py` | LangGraph definition |
| AI service | `src/services/gemini_services.py` | Gemini 3.0 Flash client |
| WebSocket routes | `src/api/routes/websocket_*.py` | Real-time updates |

## CONVENTIONS
- **Async First**: Use `async def` for all I/O bound operations.
- **Typed Python**: Strict `mypy` compliance required (all funcs typed).
- **Formatting**: Black + Ruff (100-char line limit).
- **Deployment mode switch**: `--mode no-db` for in-memory dev, default PostgreSQL.

## ANTI-PATTERNS (THIS BACKEND)
- Root test files (`test_*.py`) should move to `/tests`
- Missing TODO implementations in `src/graphs/nodes/` (image cropping, notifications)
- Dual package management: `uv.lock` + `requirements.txt` (keep synced)

## COMMANDS
```bash
make dev          # uv run uvicorn src.api.main:app --reload
make test         # uv run pytest
make quality      # ruff check + black check + mypy
make build        # docker build -t gradeos-backend .
make deploy       # ./k8s/deploy.sh (interactive)
```

## NOTES
- No GitHub workflows configured - CI/CD handled via custom `k8s/deploy.sh`
- Supports both SQLite (dev/no-db) and PostgreSQL (production)
- Property tests use `hypothesis` for mathematical correctness (score bounds, etc.)
