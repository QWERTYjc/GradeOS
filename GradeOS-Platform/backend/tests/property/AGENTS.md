# PROPERTY TESTS KNOWLEDGE

**Generated:** 2026-01-19

## OVERVIEW
Extensive property-based testing using Hypothesis to verify mathematical correctness and invariant preservation.

## STRUCTURE
```
property/
├── test_agent_execution_completeness.py    # NEVER: score negative, outside [0,100]
├── test_prompt_truncation_priority.py      # ALWAYS: preserve system/rubric content
├── test_cache_invalidation_propagation.py  # Cache consistency
├── test_coordinate_normalization.py        # Coordinate bounds validation
├── test_revision_loop_termination.py       # Prevent infinite loops
└── ... (60+ more property tests)
```

## WHERE TO LOOK
| Test Type | File | Focus |
|-----------|------|-------|
| Score bounds | `test_agent_execution_completeness.py` | NEVER negative, ALWAYS ≤ 100 |
| Prompt handling | `test_prompt_truncation_priority.py` | System/rubric preservation |
| Workflow safety | `test_revision_loop_termination.py` | Loop termination guarantees |

## CONVENTIONS
- Use `@given` from hypothesis for strategy-based testing
- Property tests verify invariants, not specific implementations
- Key constraints: score ∈ [0,100], prompt truncation preserves critical sections

## ANTI-PATTERNS
- Property tests don't cover frontend/backend integration
- No visual regression tests for OCR/grading output

## NOTES
- Fixtures in `tests/fixtures/*.png` for vision-based grading tests
- Run with `pytest tests/property/`
