"""Supervisor agent for routing grading tasks."""

import json
import logging
from typing import Dict, Any, List, Optional

from langchain_core.messages import HumanMessage

from src.services.chat_model_factory import get_chat_model
from src.models.enums import QuestionType
from src.models.state import ContextPack, GradingState
from src.agents.base import BaseGradingAgent
from src.agents.pool import AgentPool, AgentNotFoundError
from src.config.models import get_lite_model


logger = logging.getLogger(__name__)


# Confidence threshold to trigger a second review.
CONFIDENCE_THRESHOLD = 0.75


class SupervisorAgent:
    """Select a grading agent based on question type and confidence."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        agent_pool: Optional[AgentPool] = None,
    ):
        """Initialize the supervisor agent.

        Args:
            api_key: LLM API key.
            model_name: Model name for question type analysis.
            agent_pool: Agent pool instance; defaults to global singleton.
        """
        if model_name is None:
            model_name = get_lite_model()
        self.llm = get_chat_model(
            api_key=api_key,
            model_name=model_name,
            temperature=0.1,
            purpose="vision",
            enable_thinking=True,
        )
        self.agent_pool = agent_pool or AgentPool()
        self._api_key = api_key

    async def analyze_question_type(self, image_data: str) -> QuestionType:
        """Analyze a question image and infer its type."""
        prompt = (
            "Analyze the image and return the question type.\n\n"
            "Question types:\n"
            "1. objective - multiple choice or true/false\n"
            "2. stepwise - multi-step calculation (math/physics)\n"
            "3. essay - essay or short answer\n"
            "4. lab_design - experiment design\n"
            "5. unknown - cannot be determined\n\n"
            "Return only the English type label (objective/stepwise/essay/lab_design/unknown)."
        )

        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": f"data:image/jpeg;base64,{image_data}"},
            ]
        )

        response = await self.llm.ainvoke([message])
        text = self._extract_text(response.content).strip().lower()
        if text.startswith("```"):
            text = text.strip('`')
        text = text.replace('\n', ' ').strip()

        if "objective" in text:
            return QuestionType.OBJECTIVE
        if "stepwise" in text:
            return QuestionType.STEPWISE
        if "essay" in text:
            return QuestionType.ESSAY
        if "lab_design" in text or "lab design" in text:
            return QuestionType.LAB_DESIGN
        return QuestionType.UNKNOWN

    def select_agent(self, question_type: QuestionType) -> BaseGradingAgent:
        """Select a grading agent for the given question type."""
        return self.agent_pool.get_agent(question_type)

    def build_context_pack(
        self,
        question_image: str,
        question_type: QuestionType,
        rubric: str,
        max_score: float,
        standard_answer: Optional[str] = None,
        terminology: Optional[List[str]] = None,
        previous_result: Optional[Dict[str, Any]] = None,
    ) -> ContextPack:
        """Build a context pack for grading agents."""
        context_pack: ContextPack = {
            "question_image": question_image,
            "question_type": question_type,
            "rubric": rubric,
            "max_score": max_score,
        }

        if standard_answer is not None:
            context_pack["standard_answer"] = standard_answer
        if terminology is not None:
            context_pack["terminology"] = terminology
        else:
            context_pack["terminology"] = []
        if previous_result is not None:
            context_pack["previous_result"] = previous_result

        return context_pack

    async def spawn_and_grade(self, context_pack: ContextPack) -> GradingState:
        """Select and run a grading agent, optionally with secondary review."""
        question_type = context_pack.get("question_type", QuestionType.UNKNOWN)

        try:
            agent = self.select_agent(question_type)
            logger.info(
                f"Selected agent {agent.agent_type} for question type: {question_type.value}"
            )
            result = await agent.grade(context_pack)

            confidence = result.get("confidence", 0.0)
            if confidence < CONFIDENCE_THRESHOLD:
                logger.info(
                    f"Confidence {confidence:.2f} below threshold {CONFIDENCE_THRESHOLD}."
                )
                result = await self.secondary_review(context_pack, result)

            return result

        except AgentNotFoundError as exc:
            logger.error(f"No suitable agent found: {exc}")
            return GradingState(
                context_pack=context_pack,
                final_score=0.0,
                max_score=context_pack.get("max_score", 0.0),
                confidence=0.0,
                agent_type="unknown",
                is_finalized=False,
                needs_secondary_review=True,
                error=str(exc),
                vision_analysis="",
                rubric_mapping=[],
                reasoning_trace=[f"error: {exc}"],
                evidence_chain=[],
                visual_annotations=[],
                student_feedback="Manual review required.",
                revision_count=0,
            )

    async def secondary_review(
        self,
        context_pack: ContextPack,
        initial_result: GradingState,
    ) -> GradingState:
        """Run a secondary review when confidence is low."""
        logger.info("Starting secondary review")

        context_pack_with_previous = self.build_context_pack(
            question_image=context_pack.get("question_image", ""),
            question_type=context_pack.get("question_type", QuestionType.UNKNOWN),
            rubric=context_pack.get("rubric", ""),
            max_score=context_pack.get("max_score", 0.0),
            standard_answer=context_pack.get("standard_answer"),
            terminology=context_pack.get("terminology"),
            previous_result={
                "score": initial_result.get("final_score", 0.0),
                "confidence": initial_result.get("confidence", 0.0),
                "vision_analysis": initial_result.get("vision_analysis", ""),
                "rubric_mapping": initial_result.get("rubric_mapping", []),
                "reasoning_trace": initial_result.get("reasoning_trace", []),
            },
        )

        question_type = context_pack.get("question_type", QuestionType.UNKNOWN)

        try:
            agent = self.select_agent(question_type)
            secondary_result = await agent.grade(context_pack_with_previous)
            secondary_result["needs_secondary_review"] = False

            if secondary_result.get("confidence", 0.0) < CONFIDENCE_THRESHOLD:
                secondary_result["needs_secondary_review"] = True
                logger.warning(
                    f"Secondary review confidence still low: {secondary_result.get('confidence', 0.0):.2f}"
                )

            initial_trace = initial_result.get("reasoning_trace", [])
            secondary_trace = secondary_result.get("reasoning_trace", [])
            secondary_result["reasoning_trace"] = (
                initial_trace + ["--- Secondary Review ---"] + secondary_trace
            )

            return secondary_result

        except AgentNotFoundError as exc:
            logger.error(f"Secondary review failed: {exc}")
            initial_result["needs_secondary_review"] = True
            return initial_result

    def _extract_text(self, content: Any) -> str:
        """Extract text content from LLM response content."""
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict):
                    text_parts.append(item.get("text", ""))
                else:
                    text_parts.append(str(item))
            return "\n".join(text_parts)
        return str(content)
