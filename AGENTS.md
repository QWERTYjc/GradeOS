# PROJECT KNOWLEDGE BASE

**Generated:** 2026-01-19
**Commit:** 89fe6e7
**Branch:** main

## OVERVIEW
Full-stack AI grading platform: Python/FastAPI backend + LangGraph orchestration + Next.js 16 frontend. Monorepo structure with separate backend/frontend inside GradeOS-Platform.

## STRUCTURE
```
GradeOS-Platform/
├── backend/           # Python 3.11+ FastAPI + LangGraph
│   ├── src/           # Main source code
│   ├── tests/         # Pytest suite (property-based emphasis)
│   └── k8s/           # Kubernetes + KEDA configs
└── frontend/          # Next.js 16 + React 19 + Tailwind 4
    └── src/           # App Router (app/)
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Backend entry | `backend/src/api/main.py` | FastAPI app |
| Workflow engine | `backend/src/orchestration/langgraph_orchestrator.py` | LangGraph state machine |
| Frontend entry | `frontend/src/app/page.tsx` | Next.js App Router |
| AI grading logic | `backend/src/graphs/` | LangGraph workflow nodes |
| API routes | `backend/src/api/routes/` | Unified, batch, WebSocket |

## CONVENTIONS
- **Backend**: Black + Ruff (100-char line limit), Mypy strict mode (all funcs typed)
- **Frontend**: TypeScript strict, `@/` absolute imports required
- **Dependencies**: Backend uses `uv` (not pip), frontend uses `npm`
- **Testing**: Backend uses pytest + Hypothesis (property-based); frontend has no automated tests

## ANTI-PATTERNS (THIS PROJECT)
- Root-level PDFs/Word docs (`*.pdf`, `*.docx`) - move to `/docs` or `/research`
- Backend test files (`test_*.py`) in root instead of `/tests` directory
- `frontend/.next/` tracked in git - should be `.gitignore`'d
- Multiple Dockerfiles (`Dockerfile`, `Dockerfile.api`, `Dockerfile.worker`) - incomplete migration to distributed architecture

## UNIQUE STYLES
- **Dual Deployment Mode**: Supports "No-Database Mode" (in-memory) for local development vs PostgreSQL for production
- **KEDA Autoscaling**: Event-driven scaling for cognitive workers based on queue depth
- **Property-Based Testing**: Extensive Hypothesis tests in `backend/tests/property/` for mathematical correctness
- **LangGraph Over Temporal**: README mentions Temporal but actual implementation uses LangGraph for orchestration

## COMMANDS
```bash
# Backend
cd GradeOS-Platform/backend
make dev          # Start dev server
make test         # Run pytest
make quality      # lint + format + type-check

# Frontend
cd GradeOS-Platform/frontend
npm run dev       # Next.js dev server
npm run build     # Production build
npm run lint      # ESLint check
```

## NOTES
- System tuned for **Google Gemini 3.0 Flash**
- Frontend uses Ant Design 5 + Zustand + Framer Motion 12
- Backend property tests use vision fixtures (`tests/fixtures/*.png`) for OCR testing
- Many core features still marked as TODO (image processing, notifications, Redis integration)
