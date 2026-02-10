import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from src.orchestration.langgraph_orchestrator import LangGraphOrchestrator


def test_orchestrator_marks_run_paused_on_interrupt_snapshot():
    """
    Regression test:
    LangGraph `interrupt()` pauses the graph but does not emit `__interrupt__` in astream_events outputs.
    Our orchestrator must detect pause by inspecting the persisted state snapshot (tasks + interrupts),
    and emit a `paused` event with `interrupt_value`.
    """

    import asyncio

    async def _run():
        sg = StateGraph(dict)

        async def node_a(state: dict) -> dict:
            interrupt({"type": "rubric_review_required", "message": "Review required"})
            state = dict(state)
            state["after"] = True
            return state

        sg.add_node("a", node_a)
        sg.set_entry_point("a")
        sg.add_edge("a", END)
        compiled = sg.compile(checkpointer=InMemorySaver())

        orchestrator = LangGraphOrchestrator(
            db_pool=None, checkpointer=InMemorySaver(), offline_mode=True
        )
        orchestrator.register_graph("test_graph", compiled)

        run_id = await orchestrator.start_run(
            "test_graph", payload={"hello": "world"}, idempotency_key="t1"
        )

        terminal = None
        async for event in orchestrator.stream_run(run_id):
            if event.get("type") in {"paused", "completed", "error"}:
                terminal = event
                break

        assert terminal is not None
        assert terminal["type"] == "paused"
        assert (
            terminal["data"].get("interrupt_value", {}).get("type")
            == "rubric_review_required"
        )

        run_info = await orchestrator.get_run_info(run_id)
        assert run_info is not None
        assert run_info.status is not None
        assert run_info.status.value == "paused"

    asyncio.run(_run())
