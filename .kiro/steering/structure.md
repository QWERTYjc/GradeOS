# GradeOS Platform - Project Structure

## Main Platform (`GradeOS-Platform/`)

### Backend (`GradeOS-Platform/backend/`)
```
src/
├── api/                    # FastAPI application
│   ├── main.py            # App entry point, lifespan management
│   ├── routes/            # API route handlers
│   │   ├── unified_api.py # Main unified API (classes, homework, analysis)
│   │   └── batch_langgraph.py # Batch grading endpoints
│   ├── middleware/        # Rate limiting, auth middleware
│   └── dependencies.py    # Dependency injection
│
├── agents/                # AI agents (LangGraph)
│   ├── grading_agent.py   # Core grading agent
│   ├── supervisor.py      # Agent supervisor
│   └── pool.py           # Agent pool management
│
├── graphs/               # LangGraph workflows
│   ├── batch_grading.py  # Batch grading graph
│   └── state.py          # State definitions
│
├── models/               # Pydantic models
│   ├── unified_models.py # Database table models (19 tables)
│   ├── grading_models.py # Grading-specific models
│   └── submission.py     # Submission models
│
├── services/             # Business logic layer
│   ├── gemini_reasoning.py    # Gemini API integration
│   ├── rubric_parser.py       # Rubric parsing
│   ├── strict_grading.py      # Grading service
│   ├── cache.py               # Redis caching
│   └── student_identification.py # Student ID extraction
│
├── repositories/         # Data access layer
│   ├── submission.py     # Submission CRUD
│   └── rubric.py         # Rubric CRUD
│
├── utils/               # Utilities
│   ├── database.py      # DB connection pool
│   ├── pdf.py           # PDF processing
│   └── pool_manager.py  # Connection pool manager
│
└── workers/             # Background workers
    └── langgraph_worker.py # Async grading worker
```

### Frontend (`GradeOS-Platform/frontend/`)
```
src/
├── app/                  # Next.js App Router
│   ├── (auth)/          # Auth routes (login)
│   ├── teacher/         # Teacher module
│   │   ├── dashboard/   # Class management
│   │   ├── homework/    # Homework management
│   │   ├── statistics/  # Data analytics
│   │   └── class/[id]/  # Class detail
│   ├── student/         # Student module
│   │   ├── dashboard/   # My courses
│   │   ├── assistant/   # AI learning assistant
│   │   ├── analysis/    # Error analysis
│   │   └── report/      # Learning report
│   ├── console/         # AI grading console
│   └── page.tsx         # Landing page
│
├── components/
│   ├── layout/          # DashboardLayout, navigation
│   ├── console/         # Grading console components
│   └── landing/         # Landing page components
│
├── services/
│   ├── api.ts           # Unified API client
│   └── ws.ts            # WebSocket client
│
├── store/
│   ├── authStore.ts     # Auth state (Zustand)
│   └── consoleStore.ts  # Console state
│
└── types/
    └── index.ts         # TypeScript type definitions
```

## Legacy/Standalone Projects

These projects are being integrated into GradeOS-Platform:

- `批改/` - Original AI grading backend (being merged into GradeOS-Platform/backend)
- `ai_correction/` - Streamlit-based grading prototype
- `GradeOS-frontend/` - Original teacher frontend (merged into GradeOS-Platform/frontend/teacher)
- `studentassisant/` - Student AI assistant (merged into GradeOS-Platform/frontend/student/assistant)
- `intellilearn---ai-teaching-agent/` - Error analysis system (merged into GradeOS-Platform/frontend/student/analysis)

## Key Files

- `GradeOS-Platform/backend/scripts/init_database.sql` - Database schema
- `GradeOS-Platform/docker-compose.yml` - Docker orchestration
- `GradeOS-Platform/start_dev.ps1` - Windows dev startup script
- `后端数据库需求文档_基于API整合.md` - Database requirements doc
