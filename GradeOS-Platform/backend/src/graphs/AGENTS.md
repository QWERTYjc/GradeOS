# WORKFLOW & AI KNOWLEDGE BASE

**Engine**: LangGraph
**Focus**: Multi-agent orchestration, Grading Logic

## OVERVIEW
Defines cognitive architecture of GradeOS. Manages lifecycle of a submission from image ingestion to final graded output via directed cyclic graphs.

## STRUCTURE
```
backend/src/graphs/
├── nodes/              # Individual graph steps (Grade, Review, Persist)
├── batch_grading.py    # Main graph definition (State Machine)
├── state.py            # GraphState TypeDict definitions
└── retry.py            # Fault tolerance policies
```

## KEY WORKFLOWS
1. **Ingestion**: Receive PDF/Images → Segment questions.
2. **Identification**: Match student ID & Name.
3. **Grading**:
   - **Primary**: Vision/Text analysis against Rubric.
   - **Critique**: Self-correction loop (Reflection).
   - **Review**: Human-in-the-loop (if low confidence).
4. **Finalization**: Aggregation & Persistence.

## CONVENTIONS
- **Nodes**: Must accept `GraphState` and return `Command` or partial state update.
- **State**: Immutable updates preferred.
- **Edges**: Use conditional edges for branching logic (e.g., `should_review`).
- **Prompts**: Store in `backend/src/agents/` with strict Chinese output constraints.

## ANTI-PATTERNS (THIS PROJECT)
- **NO Infinite Loops**: Always define `recursion_limit` in graph config.
- **NO Heavy Compute in Nodes**: Offload OCR/Heavy ML to specialized workers.
- **NO Mixed Languages**: Prompts must enforce Chinese output.
- `batch_grading.py` - TODO: image preprocessing and persistence
- `nodes/grade.py` - TODO: image cropping based on coordinates

## DEBUGGING
- Check `backend/src/services/tracing.py` for local log traces.
- State transitions logged via structured logging.
