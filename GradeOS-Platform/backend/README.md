# GradeOS Backend

AI-Powered Grading Engine with FastAPI + LangGraph + Temporal

## Deployment Modes

GradeOS supports two deployment modes:

### 1. Database Mode (Full Features)
- Complete functionality with PostgreSQL and Redis
- Data persistence and history
- Analytics and WebSocket support

### 2. No-Database Mode (Lightweight)
- Quick start with minimal dependencies
- Only requires Gemini API Key
- Uses in-memory caching
- Perfect for testing and small-scale use

See [No-Database Mode Guide](docs/NO_DATABASE_MODE.md) for details.

## Quick Start

### No-Database Mode (Fastest)

```bash
# Install dependencies
uv sync

# Set Gemini API Key only
export GEMINI_API_KEY="your-api-key"

# Start API server
uvicorn src.api.main:app --reload --port 8001
```

### Database Mode (Full Features)

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
| `/health` | GET | Health check + deployment mode |

## Architecture

- **FastAPI** - API Gateway
- **LangGraph** - Agent reasoning framework
- **Temporal** - Workflow orchestration
- **PostgreSQL** - Primary database (optional in no-database mode)
- **Redis** - Caching & rate limiting (optional in no-database mode)
- **Gemini 3.0 Flash** - Vision-native grading
