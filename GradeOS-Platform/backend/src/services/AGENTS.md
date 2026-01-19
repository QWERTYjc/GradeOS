# SERVICES KNOWLEDGE

**Generated:** 2026-01-19

## OVERVIEW
Core business logic for AI grading: Gemini integration, rubric management, grading orchestration.

## STRUCTURE
```
services/
├── gemini_services.py       # Google Gemini 3.0 Flash client
├── rubric_service.py         # Rubric parsing, validation, storage
├── grading_service.py        # High-level grading orchestration
├── patch_deployer.py         # Hot patching (TODO: Redis/Consul)
├── calibration.py            # Score calibration (TODO: unit conversion)
├── regression_tester.py      # Evaluation testing (TODO: load eval sets)
└── prompt_engine.py          # Prompt template management
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Gemini API calls | `gemini_services.py` | Direct client, no wrapper library |
| Rubric CRUD | `rubric_service.py` | Pydantic validation |
| Grading orchestration | `grading_service.py` | Calls LangGraph orchestrator |

## CONVENTIONS
- All services use async/await
- Strict Pydantic schemas for input/output
- TODOs marked for external integrations (Redis, notifications)

## ANTI-PATTERNS
- `patch_deployer.py` - incomplete Redis/Consul integration
- `calibration.py` - missing unit conversion and synonym matching
- `regression_tester.py` - missing evaluation set loading

## NOTES
- Services tested via both unit tests (`tests/unit/`) and property tests (`tests/property/`)
