"""Grading agent using LangGraph."""

from typing import Literal, Optional, Callable
from langgraph.graph import StateGraph, END

from ..models.state import GradingState
from ..services.llm_reasoning import LLMReasoningClient
from ..utils.enhanced_checkpointer import EnhancedPostgresCheckpointer
from .nodes import (
    vision_extraction_node,
    rubric_mapping_node,
    critique_node,
    finalization_node,
)


class GradingAgent:
    """LangGraph grading agent with checkpoint support."""

    def __init__(
        self,
        reasoning_client: LLMReasoningClient,
        checkpointer: Optional[EnhancedPostgresCheckpointer] = None,
        heartbeat_callback: Optional[Callable[[str, float], None]] = None,
    ):
        """Initialize the grading agent."""
        self.reasoning_client = reasoning_client
        self.checkpointer = checkpointer
        self.heartbeat_callback = heartbeat_callback
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build LangGraph workflow."""
        workflow = StateGraph(GradingState)

        async def _vision_node(state):
            return await vision_extraction_node(state, self.reasoning_client)

        async def _rubric_node(state):
            return await rubric_mapping_node(state, self.reasoning_client)

        async def _critique_node(state):
            return await critique_node(state, self.reasoning_client)

        workflow.add_node("vision_extraction", _vision_node)
        workflow.add_node("rubric_mapping", _rubric_node)
        workflow.add_node("critique", _critique_node)
        workflow.add_node("finalization", finalization_node)

        workflow.set_entry_point("vision_extraction")
        workflow.add_edge("vision_extraction", "rubric_mapping")
        workflow.add_edge("rubric_mapping", "critique")
        workflow.add_conditional_edges(
            "critique",
            self._should_revise,
            {
                "revise": "rubric_mapping",
                "finalize": "finalization",
            },
        )
        workflow.add_edge("finalization", END)

        if self.checkpointer:
            return workflow.compile(checkpointer=self.checkpointer)
        return workflow.compile()

    def _should_revise(self, state: GradingState) -> Literal["revise", "finalize"]:
        """Decide whether to revise based on critique feedback."""
        if state.get("error"):
            return "finalize"

        critique_feedback = state.get("critique_feedback")
        revision_count = state.get("revision_count", 0)
        if critique_feedback and revision_count < 3:
            return "revise"
        return "finalize"

    async def run(
        self,
        question_image: str,
        rubric: str,
        max_score: float,
        standard_answer: str = None,
        thread_id: str = None,
    ) -> GradingState:
        """Run grading workflow."""
        initial_state: GradingState = {
            "question_image": question_image,
            "rubric": rubric,
            "max_score": max_score,
            "standard_answer": standard_answer,
            "revision_count": 0,
            "is_finalized": False,
            "reasoning_trace": [],
        }

        config = {}
        if thread_id and self.checkpointer:
            config["configurable"] = {"thread_id": thread_id}

        return await self.graph.ainvoke(initial_state, config=config)
