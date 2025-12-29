# GradeOS Platform - Tech Stack

## Backend (Python)

- **Runtime**: Python 3.11+
- **Framework**: FastAPI
- **AI/ML**: LangGraph, LangChain, Google Gemini API (gemini-2.0-flash)
- **Database**: PostgreSQL 15+ with asyncpg
- **Cache**: Redis 7+
- **PDF Processing**: PyMuPDF, pdf2image, Pillow
- **Package Manager**: uv (preferred) or pip

### Backend Code Style
- Formatter: Black (line-length: 100)
- Linter: Ruff
- Type checking: mypy (strict mode)
- All functions require type annotations

## Frontend (TypeScript)

- **Runtime**: Node.js 18+
- **Framework**: Next.js 15 (App Router)
- **React**: React 19
- **UI Library**: Ant Design 5, Tailwind CSS 4
- **State Management**: Zustand
- **Charts**: Recharts
- **3D Graphics**: Three.js, React Three Fiber
- **HTTP Client**: Axios

### Frontend Code Style
- ESLint + Prettier
- TypeScript strict mode
- Tailwind CSS for styling

## Database Schema

- 19 core tables covering users, classes, assignments, grading, error analysis
- Uses PostgreSQL JSONB for flexible data storage
- Alembic for migrations

## Common Commands

### Backend
```bash
# Install dependencies
cd GradeOS-Platform/backend
uv sync                          # or: pip install -r requirements.txt

# Run development server
uvicorn src.api.main:app --reload --port 8001

# Run tests
pytest tests/ -v

# Format code
black src/
ruff check src/ --fix

# Database migration
alembic upgrade head
```

### Frontend
```bash
# Install dependencies
cd GradeOS-Platform/frontend
npm install

# Run development server
npm run dev                      # Runs on port 3000

# Build for production
npm run build

# Lint
npm run lint
```

### Docker
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f
```

## Environment Variables

Backend requires `.env` file with:
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `GEMINI_API_KEY` - Google Gemini API key
- `JWT_SECRET` - JWT signing secret

## API Conventions

- Base path: `/api`
- Authentication: JWT Bearer Token
- Response format: `{ data, error, message }`
- API docs available at `/docs` (Swagger) and `/redoc`
