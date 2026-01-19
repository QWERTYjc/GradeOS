# TESTING KNOWLEDGE BASE

**Framework**: Pytest, Hypothesis
**Focus**: Property-based testing, Regression protection

## OVERVIEW
GradeOS employs a rigorous testing strategy emphasizing **Property-Based Testing** to ensure the grading engine's invariant correctness under infinite random inputs.

## STRUCTURE
```
backend/tests/
├── property/           # Hypothesis tests (Invariants)
├── integration/        # End-to-end workflow tests
├── unit/               # Isolated component tests
└── fixtures/           # Shared test data & mocks
```

## KEY INVARIANTS (DO NOT BREAK)
1. **Score Bounds**: `0 <= score <= max_score`.
2. **Completeness**: All questions in a submission must be graded.
3. **Non-Negative**: No negative scores allowed.
4. **Idempotency**: Reprocessing the same submission yields the same result.

## CONVENTIONS
- **Property Tests**: Use `@given(st.data())` to generate inputs.
- **Async Tests**: Use `@pytest.mark.asyncio`.
- **Fixtures**: Define in `conftest.py` for global reuse.
- **Mocking**: Mock external LLM calls; never hit live APIs in unit tests.

## COMMANDS
```bash
# Run property tests (High value)
uv run pytest tests/property

# Run fast unit tests
uv run pytest tests/unit

# Run full suite
make test
```
