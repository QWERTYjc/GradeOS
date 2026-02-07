from src.config.runtime_controls import get_runtime_controls


def test_runtime_controls_defaults(monkeypatch) -> None:
    keys = [
        "RUN_MAX_CONCURRENCY",
        "RUN_MAX_PARALLEL_LLM_CALLS",
        "LANGGRAPH_MAX_CONCURRENCY",
        "RUN_BATCH_CHUNK_SIZE",
        "GRADING_BATCH_SIZE",
        "TEACHER_MAX_ACTIVE_RUNS",
        "GRADING_RUN_POLL_SECONDS",
        "GRADING_RUN_WAIT_TIMEOUT_SECONDS",
        "RUN_EVENT_BUFFER_SIZE",
        "SOFT_BUDGET_USD_PER_RUN",
        "BATCH_IMAGE_CACHE_MAX_BATCHES",
        "RUN_UPLOAD_QUEUE_WATERMARK",
        "RUN_UPLOAD_ACTIVE_WATERMARK",
    ]
    for key in keys:
        monkeypatch.delenv(key, raising=False)

    get_runtime_controls.cache_clear()
    controls = get_runtime_controls()

    assert controls.run_max_concurrency == 100
    assert controls.run_max_parallel_llm_calls == 6
    assert controls.run_batch_chunk_size == 50
    assert controls.teacher_max_active_runs == 3
    assert controls.run_queue_poll_seconds == 2.0
    assert controls.run_queue_timeout_seconds == 60.0
    assert controls.run_event_buffer_size == 5000
    assert controls.soft_budget_usd_per_run == 0.0
    assert controls.batch_image_cache_max_batches == 50
    assert controls.upload_queue_watermark == 0
    assert controls.upload_active_watermark == 0
    get_runtime_controls.cache_clear()


def test_runtime_controls_alias_and_override(monkeypatch) -> None:
    monkeypatch.setenv("RUN_MAX_PARALLEL_LLM_CALLS", "0")
    monkeypatch.setenv("LANGGRAPH_MAX_CONCURRENCY", "9")
    monkeypatch.setenv("RUN_BATCH_CHUNK_SIZE", "0")
    monkeypatch.setenv("GRADING_BATCH_SIZE", "77")
    monkeypatch.setenv("RUN_UPLOAD_QUEUE_WATERMARK", "15")
    monkeypatch.setenv("RUN_UPLOAD_ACTIVE_WATERMARK", "4")

    get_runtime_controls.cache_clear()
    controls = get_runtime_controls()

    assert controls.run_max_parallel_llm_calls == 9
    assert controls.run_batch_chunk_size == 77
    assert controls.upload_queue_watermark == 15
    assert controls.upload_active_watermark == 4
    get_runtime_controls.cache_clear()
