"""Cached grading service using local rubric context caching."""

from __future__ import annotations

import base64
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.config.models import get_cache_model
from src.services.llm_client import get_llm_client
from src.services.rubric_parser import ParsedRubric
from src.services.strict_grading import (
    QuestionGradingResult,
    ScoringPointResult,
    StudentGradingResult,
)

logger = logging.getLogger(__name__)


class CachedGradingService:
    """Cached grading service that reuses rubric context across calls."""

    def __init__(
        self,
        api_key: Optional[str],
        model_name: Optional[str] = None,
        cache_ttl_hours: int = 1,
    ) -> None:
        if model_name is None:
            model_name = get_cache_model()
        self.api_key = api_key
        self.model_name = model_name
        self.cache_ttl_hours = cache_ttl_hours
        self.rubric: Optional[ParsedRubric] = None
        self.rubric_context: Optional[str] = None
        self.cache_created_at: Optional[float] = None
        self._client = get_llm_client()

    async def create_rubric_cache(self, rubric: ParsedRubric, rubric_context: str) -> Dict[str, Any]:
        """Store rubric context in memory for reuse."""
        self.rubric = rubric
        self.rubric_context = rubric_context
        self.cache_created_at = time.time()
        logger.info("Rubric cache created (local).")
        return {
            "status": "cached",
            "created_at": self.cache_created_at,
            "ttl_hours": self.cache_ttl_hours,
            "total_questions": rubric.total_questions,
        }

    def _is_cache_valid(self) -> bool:
        if not self.rubric_context or not self.cache_created_at:
            return False
        elapsed_hours = (time.time() - self.cache_created_at) / 3600
        return elapsed_hours < self.cache_ttl_hours

    async def grade_student_with_cache(
        self,
        student_pages: List[bytes],
        student_name: str = "student",
    ) -> StudentGradingResult:
        if not self._is_cache_valid() or not self.rubric:
            raise ValueError("Rubric cache is missing or expired. Call create_rubric_cache() first.")

        max_pages = min(len(student_pages), 25)
        images = student_pages[:max_pages]

        prompt = (
            f"Grade student '{student_name}' using the cached rubric context.\n\n"
            f"Total pages: {len(images)}.\n"
            "Return JSON only."
        )

        system_prompt = (
            "You are a strict grader. Follow the rubric context exactly.\n\n"
            f"{self.rubric_context}\n"
        )

        response = await self._client.invoke_with_images(
            prompt=prompt,
            images=images,
            purpose="grading",
            system_prompt=system_prompt,
            temperature=0.2,
            max_tokens=4096,
            model=self.model_name,
            api_key_override=self.api_key,
        )

        return self._parse_grading_result(response.content, student_name, self.rubric)

    def _parse_grading_result(
        self,
        result_text: str,
        student_name: str,
        rubric: ParsedRubric,
    ) -> StudentGradingResult:
        if "```json" in result_text:
            json_start = result_text.find("```json") + 7
            json_end = result_text.find("```", json_start)
            result_text = result_text[json_start:json_end].strip()
        elif "```" in result_text:
            json_start = result_text.find("```") + 3
            json_end = result_text.find("```", json_start)
            result_text = result_text[json_start:json_end].strip()

        try:
            data = json.loads(result_text)
        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON grading result; returning empty result.")
            return StudentGradingResult(
                student_id=student_name,
                student_name=student_name,
                total_score=0,
                max_total_score=rubric.total_score,
                question_results=[],
            )

        question_results: List[QuestionGradingResult] = []
        for q_data in data.get("questions", []) if isinstance(data.get("questions"), list) else []:
            scoring_point_results: List[ScoringPointResult] = []
            for sp_data in q_data.get("scoring_point_results", []) if isinstance(q_data.get("scoring_point_results"), list) else []:
                scoring_point_results.append(
                    ScoringPointResult(
                        description=str(sp_data.get("description", "")),
                        max_score=float(sp_data.get("max_score", 0)),
                        awarded_score=float(sp_data.get("awarded_score", 0)),
                        is_correct=bool(sp_data.get("is_correct", False)),
                        explanation=str(sp_data.get("explanation", "")),
                    )
                )

            question_results.append(
                QuestionGradingResult(
                    question_id=str(q_data.get("question_id", "")),
                    max_score=float(q_data.get("max_score", 0)),
                    awarded_score=float(q_data.get("awarded_score", 0)),
                    scoring_point_results=scoring_point_results,
                    used_alternative_solution=bool(q_data.get("used_alternative_solution", False)),
                    alternative_solution_note=str(q_data.get("alternative_solution_note", "")),
                    overall_feedback=str(q_data.get("overall_feedback", "")),
                    confidence=float(q_data.get("confidence", 0.9)),
                )
            )

        return StudentGradingResult(
            student_id=student_name,
            student_name=student_name,
            total_score=float(data.get("total_score", 0)),
            max_total_score=float(data.get("max_total_score", rubric.total_score)),
            question_results=question_results,
        )

    def delete_cache(self) -> None:
        self.rubric = None
        self.rubric_context = None
        self.cache_created_at = None
        logger.info("Rubric cache cleared.")

    def get_cache_info(self) -> Dict[str, Any]:
        if not self.rubric_context:
            return {"status": "no_cache"}
        elapsed_hours = (time.time() - (self.cache_created_at or time.time())) / 3600
        remaining_hours = max(0.0, self.cache_ttl_hours - elapsed_hours)
        return {
            "status": "active" if self._is_cache_valid() else "expired",
            "created_at": self.cache_created_at,
            "ttl_hours": self.cache_ttl_hours,
            "elapsed_hours": round(elapsed_hours, 2),
            "remaining_hours": round(remaining_hours, 2),
            "total_questions": self.rubric.total_questions if self.rubric else 0,
        }
