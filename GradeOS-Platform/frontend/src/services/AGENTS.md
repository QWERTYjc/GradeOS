# FRONTEND API SERVICES KNOWLEDGE

**Generated:** 2026-01-19

## OVERVIEW
API client layer connecting frontend to backend endpoints (unified, batch, WebSocket).

## STRUCTURE
```
services/
├── api.ts                 # Base fetcher with auth headers
├── unifiedApi.ts          # /api/unified/* client
├── batchApi.ts            # /api/batch/* client
├── websocket.ts          # WebSocket connection manager
├── auth.ts                # Authentication/authorization
└── ...
```

## WHERE TO LOOK
| Service | File | Endpoint |
|---------|------|----------|
| Base fetcher | `api.ts` | Configures base URL, headers |
| Unified API | `unifiedApi.ts` | `/api/unified/*` operations |
| Batch API | `batchApi.ts` | `/api/batch/*` grading workflows |
| WebSocket | `websocket.ts` | `/ws/*` real-time updates |

## CONVENTIONS
- Centralized error handling in `api.ts`
- Auth tokens from Zustand store
- TypeScript strict typing for request/response

## ANTI-PATTERNS
- No request/response validation beyond TypeScript
- WebSocket reconnection logic may need refinement

## NOTES
- Backend routes documented in `backend/src/api/routes/AGENTS.md`
- WebSocket messages follow custom protocol (check `websocket.ts`)
