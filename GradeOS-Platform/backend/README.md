# GradeOS Backend

AI-Powered Grading Engine with FastAPI + LangGraph + Temporal

## Quick Start

```bash
# Install dependencies
uv sync

# Configure environment
cp .env.example .env
# Edit .env with your GEMINI_API_KEY, DATABASE_URL, REDIS_URL

# Database migration
alembic upgrade head

# Start API server
uvicorn src.api.main:app --reload --port 8001
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/batch/grade-cached` | POST | Batch grading with caching |
| `/batch/ws/{batch_id}` | WS | Real-time progress |
| `/api/v1/submissions` | POST | Single submission |
| `/health` | GET | Health check |

## Architecture

- **FastAPI** - API Gateway
- **LangGraph** - Agent reasoning framework
- **Temporal** - Workflow orchestration
- **PostgreSQL** - Primary database
- **Redis** - Caching & rate limiting
- **Gemini 3.0 Flash** - Vision-native grading
