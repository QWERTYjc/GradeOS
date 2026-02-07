# API Reference

This document lists active backend APIs after legacy route removal.

## Health
- `GET /health`
- `GET /api/health`

## Homework (Unified API)
- `POST /api/homework/submit`
- `POST /api/homework/submit-scan`
- `GET /api/homework/list`
- `GET /api/homework/detail/{homework_id}`
- `GET /api/homework/submissions`

## Batch Grading (LangGraph)
- `POST /api/batch/submit`
- `GET /api/batch/active`
- `GET /api/batch/status/{batch_id}`
- `GET /api/batch/results/{batch_id}`
- `GET /api/batch/full-results/{batch_id}`
- `WS /api/batch/ws/{batch_id}`
- `POST /api/batch/review/rubric`
- `POST /api/batch/review/results`
- `POST /api/batch/confirm-boundary`
- `POST /api/batch/export/annotated-images/{batch_id}`
- `POST /api/batch/export/excel/{batch_id}`
- `POST /api/batch/export/smart-excel/{batch_id}`

## Annotation Grading
- `GET /api/annotations/...`
- `POST /api/annotations/...`
- `PUT /api/annotations/...`
- `DELETE /api/annotations/...`

## Assistant Grading
- `POST /api/assistant/analyze`
- `POST /api/assistant/analyze/batch`
- `GET /api/assistant/report/{analysis_id}`
- `GET /api/assistant/status/{analysis_id}`
- `WS /api/assistant/ws/{analysis_id}`

## Memory API
- `GET /api/memory/stats`
- `GET /api/memory/list`
- `GET /api/memory/{memory_id}`
- `POST /api/memory/{memory_id}/verify`
- `POST /api/memory/{memory_id}/rollback`
- `DELETE /api/memory/{memory_id}`

## OpenBoard
- `GET /api/openboard/forums`
- `POST /api/openboard/forums`
- `GET /api/openboard/forums/{forum_id}/posts`
- `POST /api/openboard/posts`
- `GET /api/openboard/posts/{post_id}`
- `GET /api/openboard/search`

## Deprecated/Removed
- Legacy grading route modules were removed from `src/api/routes/`.
- Integrations must use active unified and batch APIs only.
