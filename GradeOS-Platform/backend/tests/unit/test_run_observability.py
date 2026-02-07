from src.models.run_lifecycle import RunState
from src.services.run_observability import RunObservabilityStore


def test_observability_metrics_and_events() -> None:
    store = RunObservabilityStore(max_events_per_run=3)
    run_id = "run-ob-1"
    store.register_run(run_id, "batch_grading", "pending")
    store.update_state(run_id, RunState.RUNNING, "running")

    store.push_event(run_id, "on_chain_start", "preprocess", {})
    store.push_event(
        run_id,
        "llm_stream",
        "rubric_parse",
        {
            "usage": {
                "model": "gpt-4o-mini",
                "input_tokens": 100,
                "output_tokens": 30,
                "total_tokens": 130,
                "estimated_cost_usd": 0.001,
            }
        },
    )
    store.push_event(run_id, "retry", "grade", {})
    store.push_event(run_id, "error", None, {"error": "timeout"})
    store.update_state(run_id, RunState.COMPLETED, "completed")

    events = store.list_events(run_id, after_seq=0, limit=10)
    assert len(events) == 3  # bounded by max_events_per_run=3
    assert events[0]["seq"] < events[-1]["seq"]

    metrics = store.build_metrics(run_id)
    assert metrics is not None
    assert metrics.event_count >= 4
    assert metrics.llm_stream_chunks == 1
    assert metrics.cost.total_tokens == 130
    assert metrics.cost.input_tokens == 100
    assert metrics.cost.output_tokens == 30
    assert metrics.cost.estimated_cost_usd > 0
    assert metrics.quality.retry_rate > 0
    assert metrics.quality.failure_rate > 0
