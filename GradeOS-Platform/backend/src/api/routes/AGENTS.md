# API ROUTES KNOWLEDGE

**Generated:** 2026-01-19

## OVERVIEW
FastAPI route handlers: unified API, batch grading, WebSocket support.

## STRUCTURE
```
routes/
├── unified.py              # /api/unified/* - System-wide operations
├── batch_langgraph.py      # /api/batch/* - Batch grading (TODO: rubric parsing)
├── websocket_grading.py     # /ws/* - Real-time grading updates
├── class_integration.py    # Class/assignment CRUD (TODO: DB fetch)
└── ...
```

## WHERE TO LOOK
| Route Group | Path | Notes |
|-------------|------|-------|
| Unified | `/api/unified/` | General operations |
| Batch | `/api/batch/` | Batch grading workflows |
| WebSocket | `/ws/` | Real-time grading progress |

## CONVENTIONS
- Use `WebSocket` for streaming grading results
- Return `Pydantic` models (not raw dicts)
- Async route handlers

## ANTI-PATTERNS
- `batch_langgraph.py` - TODO: rubric parsing implementation
- `class_integration.py` - TODO: database fetch logic for classes/assignments

## NOTES
- Routes tested via `tests/integration/` for end-to-end flows
