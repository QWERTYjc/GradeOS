"""Rubric mapping node."""

from typing import Dict, Any
from ...models.state import GradingState
from ...services.llm_reasoning import LLMReasoningClient


async def rubric_mapping_node(
    state: GradingState,
    reasoning_client: LLMReasoningClient
) -> Dict[str, Any]:
    """Map rubric points to evidence and return initial score."""
    try:
        result = await reasoning_client.rubric_mapping(
            vision_analysis=state["vision_analysis"],
            rubric=state["rubric"],
            max_score=state["max_score"],
            standard_answer=state.get("standard_answer"),
            critique_feedback=state.get("critique_feedback")
        )

        reasoning_trace = state.get("reasoning_trace", [])
        reasoning_trace.append(
            f"[rubric_mapping] initial score: {result['initial_score']}/{state['max_score']}"
        )

        return {
            "rubric_mapping": result["rubric_mapping"],
            "initial_score": result["initial_score"],
            "reasoning_trace": reasoning_trace
        }
    except Exception as exc:
        return {
            "error": f"rubric mapping failed: {str(exc)}",
            "confidence": 0.0
        }
