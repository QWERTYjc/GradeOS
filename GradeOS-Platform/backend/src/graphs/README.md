# Graphs Module

This module defines LangGraph state types, retry helpers, and graph factories used by the backend orchestrator.

## Key Files
- `state.py`: Typed state contracts for grading flows.
- `retry.py`: Retry policy helpers for resilient node execution.
- `batch_grading.py`: Main batch grading graph factory and nodes.
- `rule_upgrade.py`: Rule upgrade graph factories.

## Exported Factories
- `create_batch_grading_graph()`
- `create_rule_upgrade_graph()`
- `create_scheduled_rule_upgrade_graph()`

## Notes
- The backend uses LangGraph orchestration only.
- Checkpointing and execution metadata are persisted through the orchestrator/checkpointer stack.
