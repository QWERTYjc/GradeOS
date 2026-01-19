"""Critique node for grading review."""

from typing import Dict, Any
from ...models.state import GradingState
from ...services.llm_reasoning import LLMReasoningClient


async def critique_node(
    state: GradingState,
    reasoning_client: LLMReasoningClient
) -> Dict[str, Any]:
    """Review initial grading and return critique feedback."""
    try:
        result = await reasoning_client.critique(
            vision_analysis=state["vision_analysis"],
            rubric=state["rubric"],
            rubric_mapping=state["rubric_mapping"],
            initial_score=state["initial_score"],
            max_score=state["max_score"],
            standard_answer=state.get("standard_answer")
        )

        reasoning_trace = state.get("reasoning_trace", [])
        if result.get("needs_revision"):
            feedback = result.get("critique_feedback", "")
            reasoning_trace.append(
                f"[critique] needs revision: {feedback[:100]}..."
            )
        else:
            reasoning_trace.append("[critique] score acceptable")

        revision_count = state.get("revision_count", 0)
        if result.get("needs_revision"):
            revision_count += 1

        return {
            "critique_feedback": result.get("critique_feedback"),
            "confidence": result.get("confidence", 0.5),
            "reasoning_trace": reasoning_trace,
            "revision_count": revision_count
        }
    except Exception as exc:
        return {
            "error": f"critique node failed: {str(exc)}",
            "confidence": 0.0
        }
