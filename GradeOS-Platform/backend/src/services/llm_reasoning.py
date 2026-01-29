"""LLM 深度推理客户端 - 使用 LLM 进行批改推理

本模块实现了批改工作流的核心推理能力，集成了：
- RubricRegistry: 动态获取评分标准
- GradingSkills: Agent 技能模块
- 得分点逐一核对逻辑
- 另类解法支持
- 指数退避重试机制 (Requirement 9.1)

Requirements: 1.1, 1.2, 1.3, 9.1
"""

import base64
import json
import logging
import os
import re
from typing import (
    Dict,
    Any,
    List,
    Optional,
    TYPE_CHECKING,
    AsyncIterator,
    Callable,
    Awaitable,
    Literal,
)

from langchain_core.messages import HumanMessage

from src.services.chat_model_factory import get_chat_model
from ..models.grading import RubricMappingItem
from ..models.grading_models import (
    QuestionRubric,
    QuestionResult,
    ScoringPoint,
    ScoringPointResult,
    PageGradingResult,
    StudentInfo,
)
from ..config.models import get_default_model
from ..utils.error_handling import with_retry, get_error_manager
from ..utils.llm_thinking import split_thinking_content

if TYPE_CHECKING:
    from ..services.rubric_registry import RubricRegistry


logger = logging.getLogger(__name__)

# 精简的 System Prompt - 提取所有通用约束
SYSTEM_PROMPT = """你是一位专业阅卷教师。请严格按以下规则批改：

【坐标系统】
- 原点：左上角，x向右(0-1)，y向下(0-1)
- 使用 {{x_min, y_min, x_max, y_max}} 格式

【输出要求】
- 必须返回有效JSON
- 每个得分点必须包含：point_id, awarded, max_points, evidence
- evidence必须以【原文引用】开头，引用学生原文
- 坐标必须精确到图片中的具体位置

【评分原则】
1. 严格按评分标准给分，禁止自创分值
2. 过程正确但结果错误，仍给过程分
3. 前步错误导致后步错误，只扣一次分
4. 非标准但正确的方法同样给分
5. 证据不足时给0分并说明"未找到"

【题型处理】
- 选择题/填空题：快速判断正误
- 计算题：逐步骤评分
- 证明题：检查逻辑链条
- 应用题：检查建模、计算、结论

【空白页】
- 空白页/封面页：is_blank_page=true, score=0, max_score=0
"""


class LLMReasoningClient:
    """
    LLM 深度推理客户端，用于批改智能体的各个推理节点

    集成了 RubricRegistry 和 GradingSkills，支持：
    - 动态评分标准获取 (Requirement 1.1)
    - 得分点逐一核对 (Requirement 1.2)
    - 另类解法支持 (Requirement 1.3)

    Requirements: 1.1, 1.2, 1.3
    """

    # 类常量：避免魔法数字
    MAX_QUESTIONS_IN_PROMPT = 0  # 提示词中最多显示的题目数
    MAX_CRITERIA_PER_QUESTION = 0  # 每道题最多显示的评分要点数

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        rubric_registry: Optional["RubricRegistry"] = None,
    ):
        """
        初始化 LLM 推理客户端

        Args:
            api_key: Google AI API 密钥
            model_name: 使用的模型名称，默认使用全局配置
            rubric_registry: 评分标准注册中心（可选）
        """
        if model_name is None:
            model_name = get_default_model()
        # 移除 token 限制：设置为 None 表示不限制输出长度
        # 可通过环境变量 GRADING_MAX_OUTPUT_TOKENS 覆盖（设为 0 或负数表示不限制）
        raw_max_tokens = self._read_int_env("GRADING_MAX_OUTPUT_TOKENS", 0)
        self._max_output_tokens = raw_max_tokens if raw_max_tokens > 0 else None
        self._max_prompt_questions = self._read_int_env(
            "GRADING_PROMPT_MAX_QUESTIONS",
            self.MAX_QUESTIONS_IN_PROMPT,
        )
        self._max_prompt_criteria = self._read_int_env(
            "GRADING_PROMPT_MAX_CRITERIA",
            self.MAX_CRITERIA_PER_QUESTION,
        )
        self.llm = get_chat_model(
            api_key=api_key,
            model_name=model_name,
            temperature=0.2,
            purpose="vision",
            enable_thinking=True,
            max_output_tokens=self._max_output_tokens,
        )
        self.model_name = model_name
        self.temperature = 0.2  # 低温度以保持一致性

        # 集成 RubricRegistry (Requirement 1.1)（已移除 Agent Skill）
        self._rubric_registry = rubric_registry

    @staticmethod
    def _read_int_env(key: str, default: int) -> int:
        raw = os.getenv(key)
        if raw is None:
            return default
        try:
            return int(raw)
        except ValueError:
            return default

    def _limit_questions_for_prompt(self, questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        max_questions = self._max_prompt_questions
        if max_questions <= 0:
            return questions
        return questions[:max_questions]

    def _limit_criteria_for_prompt(self, criteria: List[Any]) -> List[Any]:
        max_criteria = self._max_prompt_criteria
        if max_criteria <= 0:
            return criteria
        return criteria[:max_criteria]

    @property
    def rubric_registry(self) -> Optional["RubricRegistry"]:
        """获取评分标准注册中心"""
        return self._rubric_registry

    @rubric_registry.setter
    def rubric_registry(self, registry: "RubricRegistry") -> None:
        """设置评分标准注册中心"""
        self._rubric_registry = registry

    def _extract_text_from_response(self, content: Any) -> str:
        """
        从响应中提取文本内容

        Args:
            content: LLM 响应内容

        Returns:
            str: 提取的文本
        """
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            # 处理多部分响应（如包含 tool_calls 或 image）
            text_parts = []
            for part in content:
                if isinstance(part, str):
                    text_parts.append(part)
                elif isinstance(part, dict) and "text" in part:
                    text_parts.append(part["text"])
            return "".join(text_parts)
        return str(content)

    def _extract_json_from_text(self, text: str) -> str:
        """
        从文本中提取 JSON 部分

        Args:
            text: 包含 JSON 的文本

        Returns:
            str: 提取的 JSON 字符串
        """
        if "```json" in text:
            json_start = text.find("```json") + 7
            json_end = text.find("```", json_start)
            return text[json_start:json_end].strip()
        elif "```" in text:
            json_start = text.find("```") + 3
            json_end = text.find("```", json_start)
            return text[json_start:json_end].strip()
        return text

    def _escape_invalid_backslashes(self, text: str) -> str:
        return re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", text)

    def _strip_control_chars(self, text: str) -> str:
        cleaned = re.sub(r"[\x00-\x1F]", " ", text)
        return re.sub(r"[\u2028\u2029]", " ", cleaned)

    def _load_json_with_repair(self, text: str) -> Dict[str, Any]:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            repaired = self._escape_invalid_backslashes(text)
            try:
                return json.loads(repaired, strict=False)
            except json.JSONDecodeError:
                repaired = self._strip_control_chars(repaired)
                return json.loads(repaired, strict=False)

    def _extract_json_block(self, text: str) -> Optional[str]:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            return None
        return text[start : end + 1]

    def _normalize_question_detail(
        self,
        detail: Dict[str, Any],
        page_index: Optional[int],
    ) -> Dict[str, Any]:
        question_id = (
            detail.get("question_id") or detail.get("questionId") or detail.get("id") or "unknown"
        )
        score = float(detail.get("score") or 0)
        max_score = float(detail.get("max_score") or detail.get("maxScore") or 0)
        student_answer = detail.get("student_answer") or detail.get("studentAnswer") or ""
        feedback = detail.get("feedback") or ""
        is_correct = detail.get("is_correct") if "is_correct" in detail else detail.get("isCorrect")
        confidence = detail.get("confidence")
        source_pages = (
            detail.get("source_pages")
            or detail.get("sourcePages")
            or detail.get("page_indices")
            or detail.get("pageIndices")
            or []
        )
        if not source_pages and page_index is not None:
            source_pages = [page_index]
        scoring_point_results = (
            detail.get("scoring_point_results")
            or detail.get("scoringPointResults")
            or detail.get("scoring_results")
            or detail.get("scoringResults")
            or []
        )
        # 提取批注坐标
        annotations = detail.get("annotations") or []

        # 提取步骤信息（包含坐标）
        steps = detail.get("steps") or []

        # 提取答案区域坐标
        answer_region = detail.get("answer_region") or detail.get("answerRegion")

        # 🔥 后备逻辑：如果 LLM 没有返回 annotations，从 scoring_point_results 构建基本批注
        if not annotations and scoring_point_results:
            fallback_annotations = []
            for idx, spr in enumerate(scoring_point_results):
                # 从 error_region 构建错误圈选批注
                error_region = spr.get("error_region") or spr.get("errorRegion")
                if error_region:
                    fallback_annotations.append(
                        {
                            "type": "error_circle",
                            "page_index": page_index,
                            "bounding_box": error_region,
                            "text": spr.get("evidence", ""),
                            "color": "#FF0000",
                        }
                    )

                # 从 mark_type 构建 M/A mark 批注
                mark_type = spr.get("mark_type") or spr.get("markType")
                awarded = spr.get("awarded") or spr.get("score") or 0
                if mark_type and error_region:
                    mark_text = f"{mark_type}{1 if awarded > 0 else 0}"
                    mark_color = "#00AA00" if awarded > 0 else "#FF0000"
                    fallback_annotations.append(
                        {
                            "type": f"{mark_type.lower()}_mark",
                            "page_index": page_index,
                            "bounding_box": {
                                "x_min": min(error_region.get("x_max", 0.9) + 0.02, 0.95),
                                "y_min": error_region.get("y_min", 0.1),
                                "x_max": min(error_region.get("x_max", 0.9) + 0.08, 1.0),
                                "y_max": error_region.get("y_max", 0.15),
                            },
                            "text": mark_text,
                            "color": mark_color,
                        }
                    )

            if fallback_annotations:
                annotations = fallback_annotations
                logger.debug(
                    f"[_normalize_question_detail] 从 scoring_point_results 构建了 "
                    f"{len(fallback_annotations)} 个后备批注"
                )

        # 🔥 后备逻辑：如果 LLM 没有返回 steps，从 scoring_point_results 构建基本步骤
        if not steps and scoring_point_results:
            fallback_steps = []
            for idx, spr in enumerate(scoring_point_results):
                point_id = spr.get("point_id") or spr.get("pointId") or f"{question_id}.{idx + 1}"
                description = spr.get("description") or ""
                awarded = spr.get("awarded") or spr.get("score") or 0
                max_points = (
                    spr.get("max_points") or spr.get("maxPoints") or spr.get("max_score") or 0
                )
                mark_type = spr.get("mark_type") or spr.get("markType") or "M"
                error_region = spr.get("error_region") or spr.get("errorRegion")

                fallback_steps.append(
                    {
                        "step_id": point_id,
                        "step_content": description,
                        "step_region": error_region,  # 可能为 None
                        "is_correct": awarded > 0,
                        "mark_type": mark_type,
                        "mark_value": 1 if awarded > 0 else 0,
                        "feedback": spr.get("reason") or spr.get("evidence") or "",
                    }
                )

            if fallback_steps:
                steps = fallback_steps
                logger.debug(
                    f"[_normalize_question_detail] 从 scoring_point_results 构建了 "
                    f"{len(fallback_steps)} 个后备步骤"
                )

        return {
            "question_id": question_id,
            "score": score,
            "max_score": max_score,
            "student_answer": student_answer,
            "is_correct": is_correct,
            "feedback": feedback,
            "confidence": confidence,
            "source_pages": source_pages,
            "scoring_point_results": scoring_point_results,
            "self_critique": detail.get("self_critique") or detail.get("selfCritique"),
            "self_critique_confidence": detail.get("self_critique_confidence")
            or detail.get("selfCritiqueConfidence"),
            "rubric_refs": detail.get("rubric_refs") or detail.get("rubricRefs"),
            "question_type": detail.get("question_type") or detail.get("questionType"),
            "annotations": annotations,
            "steps": steps,
            "answer_region": answer_region,
            # 新增字段：另类解法标记
            "used_alternative_solution": detail.get("used_alternative_solution")
            or detail.get("usedAlternativeSolution")
            or False,
            "alternative_solution_ref": detail.get("alternative_solution_ref")
            or detail.get("alternativeSolutionRef")
            or "",
        }

    def _merge_page_break_results(
        self,
        page_results: List[Dict[str, Any]],
        student_key: str,
    ) -> Dict[str, Any]:
        question_map: Dict[str, Dict[str, Any]] = {}
        page_summaries: List[Dict[str, Any]] = []
        overall_feedback = ""
        student_info = None

        for page in page_results:
            page_index = page.get("page_index")
            if isinstance(page_index, str) and page_index.isdigit():
                page_index = int(page_index)
            if page_index is not None:
                page_summaries.append(
                    {
                        "page_index": page_index,
                        "question_numbers": page.get("question_numbers")
                        or page.get("questionNumbers")
                        or [],
                        "summary": page.get("page_summary") or page.get("summary") or "",
                    }
                )
            if student_info is None and page.get("student_info"):
                student_info = page.get("student_info")
            if not overall_feedback and page.get("overall_feedback"):
                overall_feedback = page.get("overall_feedback")

            for detail in page.get("question_details", []) or []:
                normalized = self._normalize_question_detail(detail, page_index)
                key = str(normalized.get("question_id") or "unknown")
                existing = question_map.get(key)
                if not existing:
                    question_map[key] = normalized
                    continue

                existing_pages = set(existing.get("source_pages") or [])
                existing_pages.update(normalized.get("source_pages") or [])
                existing["source_pages"] = sorted(existing_pages)

                existing["scoring_point_results"] = (
                    existing.get("scoring_point_results") or []
                ) + (normalized.get("scoring_point_results") or [])

                existing_answer = (existing.get("student_answer") or "").strip()
                new_answer = (normalized.get("student_answer") or "").strip()
                if new_answer and new_answer not in existing_answer:
                    existing["student_answer"] = "\n".join(
                        filter(None, [existing_answer, new_answer])
                    )

                existing_feedback = (existing.get("feedback") or "").strip()
                new_feedback = (normalized.get("feedback") or "").strip()
                if new_feedback and new_feedback not in existing_feedback:
                    existing["feedback"] = "\n".join(
                        filter(None, [existing_feedback, new_feedback])
                    )

                merged_max = max(
                    float(existing.get("max_score") or 0),
                    float(normalized.get("max_score") or 0),
                )
                merged_score = float(existing.get("score") or 0) + float(
                    normalized.get("score") or 0
                )
                if merged_max > 0:
                    merged_score = min(merged_score, merged_max)
                existing["score"] = merged_score
                existing["max_score"] = merged_max

                existing_conf = existing.get("confidence")
                new_conf = normalized.get("confidence")
                if existing_conf is None:
                    existing["confidence"] = new_conf
                elif new_conf is not None:
                    existing["confidence"] = (float(existing_conf) + float(new_conf)) / 2

                if not existing.get("question_type") and normalized.get("question_type"):
                    existing["question_type"] = normalized.get("question_type")

        question_details = list(question_map.values())
        confidence_values = [
            float(q.get("confidence"))
            for q in question_details
            if isinstance(q.get("confidence"), (int, float))
        ]
        total_score = sum(q.get("score", 0) for q in question_details)
        max_score = sum(q.get("max_score", 0) for q in question_details)

        result = {
            "student_key": student_key,
            "status": "completed",
            "total_score": total_score,
            "max_score": max_score,
            "confidence": (
                sum(confidence_values) / len(confidence_values) if confidence_values else 0.8
            ),
            "question_details": question_details,
            "page_summaries": page_summaries,
        }
        if student_info is not None:
            result["student_info"] = student_info
        if overall_feedback:
            result["overall_feedback"] = overall_feedback
        return result

    def _parse_page_break_output(
        self,
        full_response: str,
        student_key: str,
    ) -> Optional[Dict[str, Any]]:
        text = self._extract_json_from_text(full_response)
        sections = [
            section.strip() for section in text.split("---PAGE_BREAK---") if section.strip()
        ]
        if not sections:
            return None

        page_results: List[Dict[str, Any]] = []
        for section in sections:
            candidate = self._extract_json_from_text(section).strip()
            if not candidate:
                continue
            try:
                page_results.append(self._load_json_with_repair(candidate))
                continue
            except json.JSONDecodeError:
                pass

            trimmed = self._extract_json_block(candidate)
            if not trimmed:
                continue
            try:
                page_results.append(self._load_json_with_repair(trimmed))
            except json.JSONDecodeError:
                continue

        if not page_results:
            return None
        return self._merge_page_break_results(page_results, student_key)

    @with_retry(max_retries=3, initial_delay=1.0, max_delay=60.0)
    async def _call_vision_api(
        self,
        image_b64: str,
        prompt: str,
        stream_callback: Optional[Callable[[str, str], Awaitable[None]]] = None,
    ) -> str:
        """
        调用视觉 API (带指数退避重试)

        API 调用失败时使用指数退避策略重试最多3次。

        Args:
            image_b64: Base64 编码的图像
            prompt: 提示词
            stream_callback: 流式回调函数 (stream_type, chunk) -> None

        Returns:
            str: LLM 响应文本

        验证：需求 9.1
        """
        try:
            message = HumanMessage(
                content=[
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": f"data:image/png;base64,{image_b64}"},
                ]
            )

            if stream_callback:
                # 流式调用
                full_response = ""
                async for chunk in self.llm.astream([message]):
                    content = chunk.content
                    if content:
                        if isinstance(content, str):
                            full_response += content
                            await stream_callback("text", content)
                        elif isinstance(content, list):
                            # 处理复杂内容
                            for part in content:
                                if isinstance(part, str):
                                    full_response += part
                                    await stream_callback("text", part)

                return self._extract_text_from_response(full_response)
            else:
                # 非流式调用
                response = await self.llm.ainvoke([message])
                return self._extract_text_from_response(response.content)
        except Exception as e:
            # 记录错误到全局错误管理器
            error_manager = get_error_manager()
            error_manager.add_error(
                exc=e,
                context={
                    "function": "_call_vision_api",
                    "prompt_length": len(prompt),
                    "image_size": len(image_b64),
                },
            )
            raise

    @with_retry(max_retries=3, initial_delay=1.0, max_delay=60.0)
    async def _call_text_api(self, prompt: str) -> str:
        """
        调用纯文本 API (带指数退避重试)

        用于处理纯文本输入（如文本文件内容），不包含图像。

        Args:
            prompt: 提示词（包含学生答案文本）

        Returns:
            str: LLM 响应文本
        """
        try:
            message = HumanMessage(content=prompt)
            response = await self.llm.ainvoke([message])
            return self._extract_text_from_response(response.content)
        except Exception as e:
            error_manager = get_error_manager()
            error_manager.add_error(
                exc=e,
                context={
                    "function": "_call_text_api",
                    "prompt_length": len(prompt),
                },
            )
            raise

    async def _call_vision_api_stream(self, image_b64: str, prompt: str) -> AsyncIterator[str]:
        """流式调用视觉 API"""
        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": f"data:image/png;base64,{image_b64}"},
            ]
        )
        async for chunk in self.llm.astream([message]):
            yield self._extract_text_from_response(chunk.content)

    async def _call_text_api_stream(self, prompt: str) -> AsyncIterator[str]:
        """流式调用纯文本 API"""
        message = HumanMessage(content=prompt)
        async for chunk in self.llm.astream([message]):
            yield self._extract_text_from_response(chunk.content)

    def _is_text_content(self, data: bytes) -> bool:
        """
        检测输入是否为纯文本内容

        Args:
            data: 输入数据（bytes）

        Returns:
            bool: 如果是可解码的 UTF-8 文本返回 True
        """
        try:
            # 尝试解码为 UTF-8 文本
            text = data.decode("utf-8")
            # 检查是否包含常见的文本特征（中文字符、换行符等）
            # 排除二进制文件（如 PNG/PDF 的魔数）
            if data[:4] in [b"\x89PNG", b"%PDF", b"\xff\xd8\xff"]:
                return False
            # 如果能成功解码且包含可打印字符，认为是文本
            printable_ratio = sum(1 for c in text if c.isprintable() or c in "\n\r\t") / len(text)
            return printable_ratio > 0.8
        except (UnicodeDecodeError, ZeroDivisionError):
            return False

    async def vision_extraction(
        self, question_image_b64: str, rubric: str, standard_answer: Optional[str] = None
    ) -> str:
        """
        视觉提取节点：分析学生答案图像，生成详细的文字描述

        Args:
            question_image_b64: Base64 编码的题目图像
            rubric: 评分细则
            standard_answer: 标准答案（可选）

        Returns:
            str: 学生解题步骤的详细文字描述
        """
        # 构建提示词
        prompt = f"""请仔细分析这张学生答题图像，提供详细的文字描述。

评分细则：
{rubric}

{f"标准答案：{standard_answer}" if standard_answer else ""}

请描述：
1. 学生写了什么内容（公式、文字、图表等）
2. 学生的解题步骤和思路
3. 学生的计算过程
4. 任何可见的错误或遗漏

请提供详细、客观的描述，不要进行评分，只描述你看到的内容。"""

        # 构建消息
        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": f"data:image/jpeg;base64,{question_image_b64}"},
            ]
        )

        # 调用 LLM
        response = await self.llm.ainvoke([message])

        # 提取文本内容
        return self._extract_text_from_response(response.content)

    async def rubric_mapping(
        self,
        vision_analysis: str,
        rubric: str,
        max_score: float,
        standard_answer: Optional[str] = None,
        critique_feedback: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        评分映射节点：将评分细则的每个评分点映射到学生答案中的证据

        Args:
            vision_analysis: 视觉分析结果
            rubric: 评分细则
            max_score: 满分
            standard_answer: 标准答案（可选）
            critique_feedback: 反思反馈（如果是修正循环）

        Returns:
            Dict: 包含 rubric_mapping 和 initial_score
        """
        # 构建提示词
        prompt = f"""基于以下学生答案的视觉分析，请逐条核对评分细则，并给出评分。

视觉分析：
{vision_analysis}

评分细则：
{rubric}

满分：{max_score}

{f"标准答案：{standard_answer}" if standard_answer else ""}

{f"修正反馈：{critique_feedback}" if critique_feedback else ""}

请对每个评分点进行评估，返回 JSON 格式：
{{
    "rubric_mapping": [
        {{
            "rubric_point": "评分点描述",
            "evidence": "【必须】在学生答案中找到的证据。如果是文本，请引用原文；如果是图像，请描述位置（如'左上角'、'第x行'）。",
            "score_awarded": 获得的分数,
            "max_score": 该评分点的满分
        }}
    ],
    "initial_score": 总得分,
    "reasoning": "评分理由"
}}"""

        # 调用 LLM (使用流式以触发事件)
        message = HumanMessage(content=prompt)
        full_response = ""
        try:
            async for chunk in self.llm.astream([message]):
                content_chunk = chunk.content
                if content_chunk:
                    full_response += str(content_chunk)
        except Exception as e:
            logger.error(f"Rubric mapping streaming error: {e}")
            raise

        # 提取文本内容
        result_text = self._extract_text_from_response(full_response)
        result_text = self._extract_json_from_text(result_text)

        result = json.loads(result_text)
        return result

    async def critique(
        self,
        vision_analysis: str,
        rubric: str,
        rubric_mapping: List[Dict[str, Any]],
        initial_score: float,
        max_score: float,
        standard_answer: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        自我反思节点：审查评分逻辑，识别潜在的评分错误

        Args:
            vision_analysis: 视觉分析结果
            rubric: 评分细则
            rubric_mapping: 评分点映射
            initial_score: 初始评分
            max_score: 满分
            standard_answer: 标准答案（可选）

        Returns:
            Dict: 包含 critique_feedback 和 needs_revision
        """
        # 构建提示词
        prompt = f"""请审查以下评分结果，识别潜在的评分错误或不一致之处。

视觉分析：
{vision_analysis}

评分细则：
{rubric}

评分映射：
{json.dumps(rubric_mapping, ensure_ascii=False, indent=2)}

初始评分：{initial_score}/{max_score}

{f"标准答案：{standard_answer}" if standard_answer else ""}

请检查：
1. 评分点是否都被正确评估？
2. 证据是否充分支持给出的分数？
3. 是否有遗漏的评分点？
4. 评分是否过于严格或宽松？
5. 总分是否正确计算？

返回 JSON 格式：
{{
    "critique_feedback": "反思反馈（如果没有问题，返回 null）",
    "needs_revision": true/false,
    "confidence": 0.0-1.0 之间的置信度分数
}}"""

        # 调用 LLM (使用流式)
        message = HumanMessage(content=prompt)
        full_response = ""
        try:
            async for chunk in self.llm.astream([message]):
                content_chunk = chunk.content
                if content_chunk:
                    full_response += str(content_chunk)
        except Exception as e:
            logger.error(f"Critique streaming error: {e}")
            raise

        # 提取文本内容
        result_text = self._extract_text_from_response(full_response)
        result_text = self._extract_json_from_text(result_text)

        result = json.loads(result_text)
        return result

    async def analyze_with_vision(
        self,
        images: List[bytes],
        prompt: str,
        stream_callback: Optional[Callable[[str, str], Awaitable[None]]] = None,
    ) -> Dict[str, Any]:
        """
        通用视觉分析方法：分析多张图像并返回结构化结果

        Args:
            images: 图像字节列表
            prompt: 分析提示词

        Returns:
            Dict: 包含 response 的结果
        """
        # 构建消息内容
        content = [{"type": "text", "text": prompt}]

        # 添加图像
        for img_bytes in images:
            if isinstance(img_bytes, bytes):
                img_b64 = base64.b64encode(img_bytes).decode("utf-8")
            else:
                img_b64 = img_bytes  # 已经是 base64 字符串

            content.append({"type": "image_url", "image_url": f"data:image/png;base64,{img_b64}"})

        # 调用 LLM
        # 调用 LLM (使用流式)
        message = HumanMessage(content=content)
        full_response = ""
        try:
            async for chunk in self.llm.astream([message]):
                content_chunk = chunk.content
                if content_chunk:
                    # 正确提取文本内容
                    if isinstance(content_chunk, str):
                        full_response += content_chunk
                        if stream_callback:
                            await stream_callback("output", content_chunk)
                    elif isinstance(content_chunk, list):
                        # 处理多部分响应
                        for part in content_chunk:
                            if isinstance(part, str):
                                full_response += part
                                if stream_callback:
                                    await stream_callback("output", part)
                            elif isinstance(part, dict) and "text" in part:
                                full_response += part["text"]
                                if stream_callback:
                                    await stream_callback("output", part["text"])
                    else:
                        # 尝试转换为字符串，但记录警告
                        logger.warning(f"Unexpected chunk type: {type(content_chunk)}")
                        full_response += str(content_chunk)
        except Exception as e:
            logger.error(f"Vision streaming error: {e}")
            # Fallback to non-streaming if needed, or just re-raise
            raise

        # 提取文本内容
        result_text = self._extract_text_from_response(full_response)

        return {"response": result_text}

    def _format_page_index_context(self, page_context: Optional[Dict[str, Any]]) -> str:
        """格式化索引上下文，用于提示词注入"""
        if not page_context:
            return ""

        student_info = page_context.get("student_info") or {}
        student_parts = []
        if student_info:
            name = student_info.get("name") or "未知"
            student_id = student_info.get("student_id") or "未知"
            class_name = student_info.get("class_name") or "未知"
            confidence = student_info.get("confidence", 0.0)
            student_parts.append(f"姓名={name}")
            student_parts.append(f"学号={student_id}")
            student_parts.append(f"班级={class_name}")
            student_parts.append(f"置信度={confidence}")

        question_numbers = page_context.get("question_numbers") or []
        continuation_of = page_context.get("continuation_of") or "无"
        notes = page_context.get("index_notes") or []

        return (
            "## 索引上下文（优先使用）\n"
            f"- page_index: {page_context.get('page_index')}\n"
            f"- question_numbers: {', '.join(question_numbers) if question_numbers else '无'}\n"
            f"- continuation_of: {continuation_of}\n"
            f"- is_cover_page: {page_context.get('is_cover_page', False)}\n"
            f"- student_key: {page_context.get('student_key', '未知')}\n"
            f"- student_info: {', '.join(student_parts) if student_parts else '无'}\n"
            f"- notes: {', '.join(notes) if notes else '无'}\n"
        )

    # ==================== grade_page 拆分为多个私有方法 ====================

    def _build_compact_rubric_info(
        self, parsed_rubric: Optional[Dict[str, Any]], rubric: str
    ) -> str:
        """构建精简的评分标准信息"""
        if parsed_rubric and parsed_rubric.get("rubric_context"):
            return parsed_rubric["rubric_context"]

        if parsed_rubric and parsed_rubric.get("questions"):
            lines = []
            for q in self._limit_questions_for_prompt(parsed_rubric.get("questions", [])):
                qid = q.get("question_id", "?")
                max_score = q.get("max_score", 0)
                lines.append(f"第{qid}题(满分{max_score}分):")

                scoring_points = q.get("scoring_points", [])
                for idx, sp in enumerate(self._limit_criteria_for_prompt(scoring_points), 1):
                    point_id = sp.get("point_id") or f"{qid}.{idx}"
                    lines.append(
                        f"  [{point_id}] {sp.get('score', 0)}分: {sp.get('description', '')}"
                    )
            return "\n".join(lines)

        return rubric or "请根据答案正确性评分"

    def _build_grading_prompt(
        self,
        rubric: str,
        parsed_rubric: Optional[Dict[str, Any]],
        page_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """构建评分提示词（精简版）"""
        rubric_info = self._build_compact_rubric_info(parsed_rubric, rubric)
        index_context = self._format_page_index_context(page_context)

        return f"""## 评分标准
{rubric_info}
{index_context}

## 任务
1. 判断页面类型（空白页/封面页直接返回is_blank_page=true）
2. 识别题目并定位作答区域（坐标0-1）
3. 按评分标准逐题批改，输出JSON格式

## 输出JSON格式
```json
{{
  "score": 总得分,
  "max_score": 满分,
  "confidence": 0.0-1.0,
  "is_blank_page": false,
  "question_numbers": ["1", "2"],
  "question_details": [
    {{
      "question_id": "1",
      "score": 8,
      "max_score": 10,
      "student_answer": "学生答案摘要",
      "feedback": "评语",
      "answer_region": {{"x_min": 0.05, "y_min": 0.15, "x_max": 0.95, "y_max": 0.45}},
      "scoring_point_results": [
        {{
          "point_id": "1.1",
          "awarded": 3,
          "max_points": 3,
          "evidence": "【原文引用】学生写了...",
          "evidence_region": {{"x_min": 0.1, "y_min": 0.2, "x_max": 0.4, "y_max": 0.25}}
        }}
      ]
    }}
  ],
  "page_summary": "简要总结",
  "student_info": {{"name": "", "student_id": ""}}
}}
```"""

    def _parse_grading_response(self, response_text: str, max_score: float) -> Dict[str, Any]:
        """
        解析评分响应，并确保 evidence 字段被正确填充

        Args:
            response_text: LLM 响应文本
            max_score: 满分

        Returns:
            Dict: 解析后的评分结果
        """
        json_text = self._extract_json_from_text(response_text)
        result = json.loads(json_text)

        # 确保所有 scoring_point_results 都有 evidence 字段
        for q in result.get("question_details", []):
            for spr in q.get("scoring_point_results", []):
                # 检查 evidence 是否为空或无效
                evidence = spr.get("evidence", "")
                if not evidence or evidence.strip() in ["", "无", "N/A", "null", "None"]:
                    # 自动补充默认 evidence
                    awarded = spr.get("awarded", 0)
                    max_sp_score = spr.get("max_score", 0)
                    description = spr.get("description", "该评分点")

                    if awarded == max_sp_score:
                        spr["evidence"] = f"学生正确完成了{description}，获得满分"
                    elif awarded == 0:
                        spr["evidence"] = f"学生未作答或未正确完成{description}"
                    else:
                        spr["evidence"] = (
                            f"学生部分完成了{description}，获得{awarded}/{max_sp_score}分"
                        )

                    logger.warning(f"evidence 字段为空，已自动补充: {spr['evidence']}")

        return result

    def _generate_feedback(self, result: Dict[str, Any]) -> str:
        """
        从评分结果生成综合反馈

        Args:
            result: 评分结果字典

        Returns:
            str: 综合反馈文本
        """
        feedback_parts = []

        if result.get("page_summary"):
            feedback_parts.append(result["page_summary"])

        for q in result.get("question_details", []):
            q_feedback = (
                f"第{q.get('question_id', '?')}题: {q.get('score', 0)}/{q.get('max_score', 0)}分"
            )
            if q.get("feedback"):
                q_feedback += f" - {q['feedback']}"
            feedback_parts.append(q_feedback)

        return "\n".join(feedback_parts) if feedback_parts else "评分完成"

    def _build_text_grading_prompt(
        self,
        text_content: str,
        rubric: str,
        parsed_rubric: Optional[Dict[str, Any]],
        page_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        构建纯文本批改的提示词

        Args:
            text_content: 学生答案文本内容
            rubric: 评分细则文本
            parsed_rubric: 解析后的评分标准

        Returns:
            str: 完整的评分提示词
        """
        # 获取评分标准信息
        rubric_info = ""
        if parsed_rubric and parsed_rubric.get("rubric_context"):
            rubric_info = parsed_rubric["rubric_context"]
        elif rubric:
            rubric_info = rubric
        else:
            rubric_info = "请根据答案的正确性、完整性和清晰度进行评分"

        index_context = self._format_page_index_context(page_context)

        return f"""你是一位专业的阅卷教师，请仔细分析以下学生答案文本并进行精确评分。

## 评分标准
{rubric_info}
{index_context}

## 学生答案文本
```
{text_content}
```

## 评分任务

### 第一步：内容判断
首先判断这是否是有效的答题内容：
- 如果是空白或无意义内容，返回 score=0, max_score=0, is_blank_page=true
- 如果索引上下文标记 is_cover_page=true，也按空白页处理

### 第二步：题目识别与评分
如果包含有效答题内容：
1. 识别文本中出现的所有题目编号（如提供了索引上下文，必须以索引为准）
2. 对每道题逐一评分，严格按照评分标准
3. 记录学生答案的关键内容
4. 给出详细的评分说明

### 第三步：学生信息提取
尝试从文本中识别：
- 学生姓名
- 学号
- 班级信息

## 输出格式（JSON）
```json
{{
    "score": 本页总得分,
    "max_score": 本页涉及题目的满分总和,
    "confidence": 评分置信度（0.0-1.0）,
    "is_blank_page": false,
    "question_numbers": ["1", "2", "3"],
    "question_details": [
        {{
            "question_id": "1",
            "score": 8,
            "max_score": 10,
            "student_answer": "学生写了：...",
            "is_correct": false,
            "feedback": "第1步正确得3分，第2步计算错误扣2分...",
            "scoring_point_results": [
                {{
                    "point_index": 1,
                    "description": "第1步计算",
                    "max_score": 3,
                    "awarded": 3,
                    "evidence": "【必填】文本第3段中学生写道：'代入x=2得y=4'，计算正确"
                }},
                {{
                    "point_index": 2,
                    "description": "第2步逻辑",
                    "max_score": 7,
                    "awarded": 5,
                    "evidence": "【必填】学生在结论处写'因此答案为5'，但正确答案应为4，扣2分"
                }}
            ]
        }}
    ],
    "page_summary": "本页包含第1-3题，学生整体表现良好，主要在计算方面有失误",
    "student_info": {{
        "name": "张三",
        "student_id": "2024001"
    }}
}}
```

## 重要评分原则
1. **严格遵循评分标准**：每个得分点必须有明确依据
2. **部分分数**：如果学生答案部分正确，给予相应的部分分数
3. **max_score 计算**：只计算本页实际出现的题目的满分，不是整张试卷的总分
4. **详细反馈**：明确指出正确和错误的部分，给出具体的扣分原因

## 【关键】证据字段要求
**evidence 字段是必填项**，必须满足以下要求：
1. **具体位置**：说明证据在文本中的位置（如"第X段"、"第X行"、"答案末尾"）
2. **原文引用**：尽可能直接引用学生的原始文字
3. **对比说明**：如果答案错误，说明学生写的内容与正确答案的差异
4. **未找到情况**：如果找不到相关内容，写明"学生未作答此部分"或"文本中未找到相关内容"

禁止在 evidence 中写空字符串或模糊描述！"""

    async def grade_page(
        self,
        image: bytes,
        rubric: str,
        max_score: float = 10.0,
        parsed_rubric: Optional[Dict[str, Any]] = None,
        page_context: Optional[Dict[str, Any]] = None,
        stream_callback: Optional[Callable[[str, str], Awaitable[None]]] = None,
    ) -> Dict[str, Any]:
        """
        批改单页：分析图像或文本并给出详细评分

        自动检测输入类型（图像或文本），使用相应的 API 进行批改。

        Args:
            image: 图像字节或文本字节
            rubric: 评分细则文本
            max_score: 满分
            parsed_rubric: 解析后的评分标准（包含题目信息）

        Returns:
            Dict: 包含详细评分结果
        """
        logger.debug(f"开始批改单页, rubric长度={len(rubric)}")

        # 检测输入类型：文本还是图像
        is_text = isinstance(image, bytes) and self._is_text_content(image)

        try:
            if is_text:
                # 纯文本输入：使用文本 API
                text_content = image.decode("utf-8")
                logger.info(f"检测到文本输入，长度={len(text_content)}字符，使用文本API批改")

                # 构建文本批改提示词
                prompt = self._build_text_grading_prompt(
                    text_content, rubric, parsed_rubric, page_context
                )

                # 调用文本 API
                response_text = await self._call_text_api(prompt, stream_callback)
            else:
                # 图像输入：使用视觉 API
                logger.info("检测到图像输入，使用视觉API批改")

                # 构建图像批改提示词
                prompt = self._build_grading_prompt(rubric, parsed_rubric, page_context)

                # 转换图像为 base64
                if isinstance(image, bytes):
                    img_b64 = base64.b64encode(image).decode("utf-8")
                else:
                    img_b64 = image

                # 调用视觉 API
                response_text = await self._call_vision_api(img_b64, prompt, stream_callback)

            # 解析响应
            result = self._parse_grading_response(response_text, max_score)

            # 生成综合反馈
            result["feedback"] = self._generate_feedback(result)

            logger.info(
                f"批改完成: score={result.get('score')}, confidence={result.get('confidence')}"
            )

            return result

        except json.JSONDecodeError as e:
            logger.error(f"评分 JSON 解析失败: {e}")
            return {
                "score": 0.0,
                "max_score": max_score,
                "confidence": 0.0,
                "feedback": f"评分解析失败: {str(e)}",
                "question_numbers": [],
                "question_details": [],
                "student_info": None,
            }
        except Exception as e:
            logger.error(f"评分失败: {e}", exc_info=True)
            return {
                "score": 0.0,
                "max_score": max_score,
                "confidence": 0.0,
                "feedback": f"评分失败: {str(e)}",
                "question_numbers": [],
                "question_details": [],
                "student_info": None,
            }

    def _normalize_question_id(self, value: Any) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        if not text:
            return ""
        for token in ["第", "题目", "题", "Q", "q"]:
            text = text.replace(token, "")
        return text.strip().rstrip(".:：")

    def _build_question_hints(
        self, parsed_rubric: Optional[Dict[str, Any]], page_context: Optional[Dict[str, Any]] = None
    ) -> str:
        if not parsed_rubric:
            return ""

        preferred = []
        if page_context:
            preferred = page_context.get("question_numbers") or []

        questions = parsed_rubric.get("questions", [])
        lines = []
        for q in self._limit_questions_for_prompt(questions):
            qid = self._normalize_question_id(q.get("question_id") or q.get("id"))
            if not qid:
                continue
            if preferred and qid not in [self._normalize_question_id(p) for p in preferred]:
                continue
            text = q.get("question_text") or ""
            if text:
                text = text[:80] + "..." if len(text) > 80 else text
                lines.append(f"- 题号 {qid}: {text}")
            else:
                lines.append(f"- 题号 {qid}")

        if not lines and questions:
            for q in self._limit_questions_for_prompt(questions):
                qid = self._normalize_question_id(q.get("question_id") or q.get("id"))
                if qid:
                    lines.append(f"- 题号 {qid}")

        return "\n".join(lines)

    def _infer_question_type(self, question: Dict[str, Any]) -> str:
        raw_type = question.get("question_type") or question.get("questionType") or ""
        raw_type = str(raw_type).strip().lower()
        if raw_type:
            return raw_type

        question_text = (
            question.get("question_text") or question.get("questionText") or ""
        ).strip()
        grading_notes = (
            question.get("grading_notes") or question.get("gradingNotes") or ""
        ).strip()
        standard_answer = (
            question.get("standard_answer") or question.get("standardAnswer") or ""
        ).strip()
        alternative_solutions = (
            question.get("alternative_solutions") or question.get("alternativeSolutions") or []
        )

        text_blob = f"{question_text} {grading_notes}".lower()
        if question_text:
            text_no_space = re.sub(r"\s+", "", question_text)
            if re.search(r"[A-D][\\.、．]", text_no_space):
                return "choice"
        if standard_answer:
            answer_clean = re.sub(r"\s+", "", standard_answer.upper())
            if re.fullmatch(r"[A-D](?:[、,/， ]*[A-D]){0,3}", answer_clean):
                return "choice"
        if any(
            token in text_blob for token in ["选择题", "单选", "多选", "选项", "请选择", "下列"]
        ):
            return "choice"

        if alternative_solutions:
            return "subjective"
        if any(
            token in text_blob
            for token in [
                "简答",
                "论述",
                "证明",
                "推导",
                "解释",
                "分析",
                "讨论",
                "设计",
                "说明",
                "过程",
                "步骤",
            ]
        ):
            return "subjective"
        if any(token in text_blob for token in ["判断", "填空", "对错", "是非", "true", "false"]):
            return "objective"

        if standard_answer:
            answer_compact = re.sub(r"\s+", "", standard_answer)
            if len(answer_compact) <= 4 and re.fullmatch(
                r"[0-9A-Za-z+\\-.=()（）/\\\\]+", answer_compact
            ):
                return "objective"
            if len(standard_answer) > 30 or "\n" in standard_answer:
                return "subjective"

        return "objective"

    def _build_rubric_payload(
        self, parsed_rubric: Optional[Dict[str, Any]], question_ids: List[str]
    ) -> Dict[str, Any]:
        if not parsed_rubric:
            return {"questions": []}

        questions = parsed_rubric.get("questions", [])
        normalized_targets = [self._normalize_question_id(qid) for qid in question_ids if qid]
        selected = []
        for q in questions:
            qid = self._normalize_question_id(q.get("question_id") or q.get("id"))
            if normalized_targets and qid not in normalized_targets:
                continue
            question_type = self._infer_question_type(q)
            scoring_points = []
            for idx, sp in enumerate(q.get("scoring_points", [])):
                point_id = sp.get("point_id") or sp.get("pointId") or f"{qid}.{idx + 1}"
                scoring_points.append(
                    {
                        "point_id": point_id,
                        "description": sp.get("description", ""),
                        "score": sp.get("score", 0),
                        "is_required": sp.get("is_required", True),
                        "keywords": sp.get("keywords") or [],
                        "expected_value": sp.get("expected_value") or sp.get("expectedValue") or "",
                    }
                )
            deduction_rules = []
            for idx, dr in enumerate(q.get("deduction_rules") or q.get("deductionRules") or []):
                deduction_rules.append(
                    {
                        "rule_id": dr.get("rule_id") or dr.get("ruleId") or f"{qid}.d{idx + 1}",
                        "description": dr.get("description", ""),
                        "deduction": dr.get("deduction", dr.get("score", 0)),
                        "conditions": dr.get("conditions") or dr.get("when") or "",
                    }
                )
            alternative_solutions = []
            for alt in q.get("alternative_solutions") or q.get("alternativeSolutions") or []:
                if not isinstance(alt, dict):
                    continue
                alternative_solutions.append(
                    {
                        "description": (alt.get("description", "") or "")[:200],
                        "scoring_criteria": (
                            alt.get("scoring_criteria")
                            or alt.get("scoringCriteria")
                            or alt.get("scoring_conditions")
                            or alt.get("scoringConditions")
                            or ""
                        )[:200],
                        "max_score": alt.get(
                            "max_score", alt.get("maxScore", q.get("max_score", 0))
                        ),
                    }
                )
            selected.append(
                {
                    "question_id": qid,
                    "max_score": q.get("max_score", 0),
                    "question_type": question_type,
                    "question_text": (q.get("question_text") or "")[:200],
                    "standard_answer": (q.get("standard_answer") or "")[:300],
                    "grading_notes": (q.get("grading_notes") or "")[:300],
                    "scoring_points": scoring_points,
                    "deduction_rules": deduction_rules,
                    "alternative_solutions": alternative_solutions,
                }
            )

        if not selected:
            for q in self._limit_questions_for_prompt(questions):
                qid = self._normalize_question_id(q.get("question_id") or q.get("id"))
                if not qid:
                    continue
                question_type = self._infer_question_type(q)
                scoring_points = []
                for idx, sp in enumerate(q.get("scoring_points", [])):
                    point_id = sp.get("point_id") or sp.get("pointId") or f"{qid}.{idx + 1}"
                    scoring_points.append(
                        {
                            "point_id": point_id,
                            "description": sp.get("description", ""),
                            "score": sp.get("score", 0),
                            "is_required": sp.get("is_required", True),
                            "keywords": sp.get("keywords") or [],
                            "expected_value": sp.get("expected_value")
                            or sp.get("expectedValue")
                            or "",
                        }
                    )
                deduction_rules = []
                for idx, dr in enumerate(q.get("deduction_rules") or q.get("deductionRules") or []):
                    deduction_rules.append(
                        {
                            "rule_id": dr.get("rule_id") or dr.get("ruleId") or f"{qid}.d{idx + 1}",
                            "description": dr.get("description", ""),
                            "deduction": dr.get("deduction", dr.get("score", 0)),
                            "conditions": dr.get("conditions") or dr.get("when") or "",
                        }
                    )
                alternative_solutions = []
                for alt in q.get("alternative_solutions") or q.get("alternativeSolutions") or []:
                    if not isinstance(alt, dict):
                        continue
                    alternative_solutions.append(
                        {
                            "description": (alt.get("description", "") or "")[:200],
                            "scoring_criteria": (
                                alt.get("scoring_criteria")
                                or alt.get("scoringCriteria")
                                or alt.get("scoring_conditions")
                                or alt.get("scoringConditions")
                                or ""
                            )[:200],
                            "max_score": alt.get(
                                "max_score", alt.get("maxScore", q.get("max_score", 0))
                            ),
                        }
                    )
                selected.append(
                    {
                        "question_id": qid,
                        "max_score": q.get("max_score", 0),
                        "question_type": question_type,
                        "question_text": (q.get("question_text") or "")[:200],
                        "standard_answer": (q.get("standard_answer") or "")[:300],
                        "grading_notes": (q.get("grading_notes") or "")[:300],
                        "scoring_points": scoring_points,
                        "deduction_rules": deduction_rules,
                        "alternative_solutions": alternative_solutions,
                    }
                )

        return {
            "total_score": parsed_rubric.get("total_score", 0),
            "questions": selected,
        }

    def _safe_json_loads(self, text: str, fallback: Dict[str, Any]) -> Dict[str, Any]:
        if not text:
            return fallback
        json_text = self._extract_json_from_text(text)
        try:
            return self._load_json_with_repair(json_text)
        except Exception as e:
            logger.warning(f"JSON 解析失败: {e}")
            return fallback

    async def extract_answer_evidence(
        self,
        image: bytes,
        parsed_rubric: Optional[Dict[str, Any]] = None,
        page_context: Optional[Dict[str, Any]] = None,
        stream_callback: Optional[Callable[[str, str], Awaitable[None]]] = None,
    ) -> Dict[str, Any]:
        """
        仅进行答案证据抽取，禁止评分。
        """
        question_hints = self._build_question_hints(parsed_rubric, page_context)
        index_context = self._format_page_index_context(page_context)
        # 预先构建题号提示，避免 f-string 中使用反斜杠
        hints_section = f"可用题号提示:\n{question_hints}" if question_hints else ""
        prompt = f"""你是阅卷助理，只做“答案证据抽取”，不要评分。
{index_context}
{hints_section}

要求：
1. 只写图中明确可见的原文/公式/步骤，无法辨认就注明不清晰。
2. 不要推断、不补写、不评分。
3. If the page is a cover/instruction page, set is_cover_page=true and is_blank_page=true with answers=[]. If it is blank, set is_blank_page=true and is_cover_page=false.
4. answer_text 保留关键步骤与公式，避免长篇复述。
5. Output limits: answer_text<=160 chars; evidence_snippets<=1 item (<=90 chars); page_summary<=100 chars; question_numbers<=6.

输出 JSON：
```json
{{
  "is_blank_page": false,
  "is_cover_page": false,
  "question_numbers": ["1"],
  "page_summary": "本页内容概述（不评分）",
  "student_info": {{
    "name": "",
    "student_id": "",
    "class_name": "",
    "confidence": 0.0
  }},
  "answers": [
    {{
      "question_id": "1",
      "answer_text": "学生原文/公式/步骤",
      "evidence_snippets": ["【原文引用】..."],
      "uncertainty_flags": ["handwriting_unclear"],
      "confidence": 0.0
    }}
  ],
  "warnings": []
}}
```
"""
        if isinstance(image, bytes):
            img_b64 = base64.b64encode(image).decode("utf-8")
        else:
            img_b64 = image

        if stream_callback:
            response_text = ""
            async for chunk in self._call_vision_api_stream(img_b64, prompt):
                response_text += chunk
                await stream_callback("text", chunk)
        else:
            response_text = await self._call_vision_api(img_b64, prompt)
        fallback = {
            "is_blank_page": False,
            "is_cover_page": False,
            "question_numbers": [],
            "page_summary": "",
            "student_info": None,
            "answers": [],
            "warnings": ["parse_error"],
        }
        return self._safe_json_loads(response_text, fallback)

    async def score_from_evidence(
        self,
        evidence: Dict[str, Any],
        parsed_rubric: Optional[Dict[str, Any]] = None,
        page_context: Optional[Dict[str, Any]] = None,
        mode: Literal["fast", "strict"] = "fast",
        stream_callback: Optional[Callable[[str, str], Awaitable[None]]] = None,
    ) -> Dict[str, Any]:
        """
        基于证据与评分标准进行评分（纯文本调用）。
        """
        answer_ids = []
        for item in evidence.get("answers", []):
            qid = self._normalize_question_id(item.get("question_id"))
            if qid:
                answer_ids.append(qid)
        question_numbers = (
            evidence.get("question_numbers") or (page_context or {}).get("question_numbers") or []
        )
        for qid in question_numbers:
            normalized = self._normalize_question_id(qid)
            if normalized and normalized not in answer_ids:
                answer_ids.append(normalized)

        if not answer_ids and parsed_rubric and parsed_rubric.get("questions"):
            for q in self._limit_questions_for_prompt(parsed_rubric.get("questions", [])):
                qid = self._normalize_question_id(q.get("question_id") or q.get("id"))
                if qid and qid not in answer_ids:
                    answer_ids.append(qid)

        rubric_payload = self._build_rubric_payload(parsed_rubric, answer_ids)
        mode_label = "FAST" if mode == "fast" else "STRICT"
        fast_note = (
            "FAST mode: keep output minimal; if full score, feedback must be empty."
            if mode == "fast"
            else ""
        )
        output_constraints = (
            "Output constraints: feedback<=120 chars (empty if full score); "
            "student_answer<=120 chars; evidence<=90 chars; reason<=120 chars; "
            "typo_notes<=3 items."
        )
        question_type_rules = (
            "Question type rules:\n"
            "- choice: no analysis; feedback/self_critique must be empty; keep output minimal.\n"
            "- objective: strictly follow rubric/scoring_points/deduction_rules; no speculation.\n"
            "- subjective: allow partial credit; if using alternative_solutions, set "
            "used_alternative_solution=true and fill alternative_solution_ref; lower confidence.\n"
        )
        # 置信度计算规则说明（评分标准引用与记忆系统优化）
        confidence_rules = (
            "置信度计算规则：\n"
            "- 有精确引用(citation_quality=exact)：置信度 0.9\n"
            "- 部分引用(citation_quality=partial)：置信度 0.81\n"
            "- 无引用(citation_quality=none)：置信度最高 0.7\n"
            "- 另类解法(is_alternative_solution=true)：置信度再降 25%\n"
        )
        prompt = f"""你是严谨的阅卷老师，只能基于“评分标准”和“答案证据”评分。
Mode: {mode_label}
{fast_note}
{output_constraints}
{question_type_rules}
{confidence_rules}
禁止臆测；证据不足时必须给 0 分并说明。
如评分标准包含扣分规则（deduction_rules），请按规则扣分并在原因中说明。
如发现错别字/拼写错误，请在每道题的 typo_notes 中标出。
每个 scoring_point_results 必须包含 point_id、rubric_reference 和 evidence；证据不足时 evidence 写“【原文引用】未找到”。

评分标准(JSON)：
{json.dumps(rubric_payload, ensure_ascii=False, indent=2)}

答案证据(JSON)：
{json.dumps(evidence, ensure_ascii=False, indent=2)}

输出 JSON：
```json
{{
  "score": 0,
  "max_score": 0,
  "confidence": 0.0,
  "question_numbers": ["1"],
  "question_details": [
    {{
      "question_id": "1",
      "score": 0,
      "max_score": 0,
      "confidence": 0.0,
      "question_type": "objective",
      "student_answer": "",
      "feedback": "",
      "used_alternative_solution": false,
      "alternative_solution_ref": "",
      "typo_notes": ["发现的错别字/拼写错误（如有）"],
      "scoring_point_results": [
        {{
          "point_id": "1.1",
          "rubric_reference": "[1.1] 评分点描述（必须引用具体评分标准条目）",
          "citation_quality": "exact|partial|none",
          "is_alternative_solution": false,
          "alternative_description": "",
          "decision": "得分/未得分",
          "awarded": 0,
          "max_points": 0,
          "evidence": "【原文引用】...",
          "reason": ""
        }}
      ]
    }}
  ],
  "page_summary": "",
  "flags": []
}}
```
"""
        response_text = await self._call_text_api(prompt, stream_callback)
        fallback = {
            "score": 0.0,
            "max_score": 0.0,
            "confidence": 0.0,
            "question_numbers": [],
            "question_details": [],
            "page_summary": "",
            "flags": ["parse_error"],
        }
        return self._safe_json_loads(response_text, fallback)

    async def assist_from_evidence(
        self,
        evidence: Dict[str, Any],
        parsed_rubric: Optional[Dict[str, Any]] = None,
        page_context: Optional[Dict[str, Any]] = None,
        mode: Literal["teacher", "student"] = "teacher",
        stream_callback: Optional[Callable[[str, str], Awaitable[None]]] = None,
    ) -> Dict[str, Any]:
        """
        Provide assistive feedback without grading or scoring.
        """
        answer_ids: List[str] = []
        for item in evidence.get("answers", []):
            qid = self._normalize_question_id(item.get("question_id"))
            if qid:
                answer_ids.append(qid)

        question_numbers = (
            evidence.get("question_numbers") or (page_context or {}).get("question_numbers") or []
        )
        for qid in question_numbers:
            normalized = self._normalize_question_id(qid)
            if normalized and normalized not in answer_ids:
                answer_ids.append(normalized)

        if not answer_ids and parsed_rubric and parsed_rubric.get("questions"):
            for q in self._limit_questions_for_prompt(parsed_rubric.get("questions", [])):
                qid = self._normalize_question_id(q.get("question_id") or q.get("id"))
                if qid and qid not in answer_ids:
                    answer_ids.append(qid)

        rubric_payload = self._build_rubric_payload(parsed_rubric, answer_ids)
        mode_label = "TEACHER_ASSIST" if mode == "teacher" else "STUDENT_ASSIST"
        output_constraints = (
            "Output constraints: feedback<=160 chars (teacher) or <=600 chars (student); "
            "student_answer<=200 chars; error_hints<=3 items."
        )
        prompt = f"""你是批改助理，只做问题分析与建议，不要打分、不输出分数。
Mode: {mode_label}
{output_constraints}
只基于“答案证据”和可用评分标准（如有）给出提示；证据不足时明确说明不确定。
Teacher assist: focus on concise error hints and likely missing steps.
Student assist: explain mistakes and how to improve, step-by-step if needed.

评分标准(JSON，可为空)：
{json.dumps(rubric_payload, ensure_ascii=False, indent=2)}

答案证据(JSON)：
{json.dumps(evidence, ensure_ascii=False, indent=2)}

输出 JSON：
```json
{{
  "question_numbers": ["1"],
  "question_details": [
    {{
      "question_id": "1",
      "question_type": "objective",
      "student_answer": "",
      "feedback": "",
      "error_hints": ["..."],
      "confidence": 0.0
    }}
  ],
  "page_summary": "",
  "flags": []
}}
```
"""
        response_text = await self._call_text_api(prompt, stream_callback)
        fallback = {
            "question_numbers": [],
            "question_details": [],
            "page_summary": "",
            "flags": ["parse_error"],
        }
        return self._safe_json_loads(response_text, fallback)

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        """安全转换为浮点数"""
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    def _sum_question_detail_scores(self, details: List[Dict[str, Any]]) -> tuple[float, float]:
        total = 0.0
        max_total = 0.0
        for detail in details:
            total += self._safe_float(detail.get("score", 0))
            max_total += self._safe_float(detail.get("max_score", detail.get("maxScore", 0)))
        return total, max_total

    def _collect_question_detail_ids(self, details: List[Dict[str, Any]]) -> set[str]:
        ids: set[str] = set()
        for detail in details:
            if not isinstance(detail, dict):
                continue
            qid = self._normalize_question_id(
                detail.get("question_id") or detail.get("questionId") or detail.get("id")
            )
            if qid:
                ids.add(qid)
        return ids

    def _get_expected_question_ids(self, parsed_rubric: Dict[str, Any]) -> List[str]:
        questions = parsed_rubric.get("questions") or []
        expected = []
        for question in questions:
            qid = self._normalize_question_id(question.get("question_id") or question.get("id"))
            if qid:
                expected.append(qid)
        return expected

    def _merge_question_details(
        self,
        existing: List[Dict[str, Any]],
        incoming: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        merged = list(existing)
        existing_ids = self._collect_question_detail_ids(existing)
        for detail in incoming:
            if not isinstance(detail, dict):
                continue
            qid = self._normalize_question_id(
                detail.get("question_id") or detail.get("questionId") or detail.get("id")
            )
            if qid and qid in existing_ids:
                continue
            merged.append(detail)
        return merged

    def _build_missing_question_placeholders(
        self,
        missing_ids: List[str],
        parsed_rubric: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        placeholders = []
        rubric_map = {}
        for question in parsed_rubric.get("questions") or []:
            qid = self._normalize_question_id(question.get("question_id") or question.get("id"))
            if qid:
                rubric_map[qid] = question
        for qid in missing_ids:
            rubric = rubric_map.get(qid, {})
            max_score = self._safe_float(rubric.get("max_score", 0))
            placeholders.append(
                {
                    "question_id": qid,
                    "score": 0.0,
                    "max_score": max_score,
                    "student_answer": "",
                    "is_correct": False,
                    "feedback": "No answer detected.",
                    "confidence": 0.0,
                    "self_critique": "Insufficient evidence to grade; manual review recommended.",
                    "self_critique_confidence": 0.0,
                    "scoring_point_results": [],
                    "page_indices": [],
                    "question_type": rubric.get("question_type") or rubric.get("questionType"),
                }
            )
        return placeholders

    async def _grade_missing_questions(
        self,
        images: List[bytes],
        student_key: str,
        parsed_rubric: Dict[str, Any],
        missing_ids: List[str],
        context_info: str,
        stream_callback: Optional[Callable[[str, str], Awaitable[None]]] = None,
    ) -> List[Dict[str, Any]]:
        if not missing_ids:
            return []
        missing_ids_text = ", ".join(missing_ids)
        rubric_info = self._build_student_grading_rubric_info(
            parsed_rubric,
            question_ids=missing_ids,
        )
        prompt = (
            "You are a grading assistant. Grade ONLY the following questions for "
            f"{student_key}: {missing_ids_text}.\n\n"
            f"Rubric:\n{rubric_info}\n\n"
            f"Context:\n{context_info}\n\n"
            "Return JSON only with this structure:\n"
            '{"question_details": [{"question_id": "1", "score": 0, "max_score": 0, '
            '"student_answer": "", "is_correct": false, "feedback": "", '
            '"confidence": 0.0, "self_critique": "", '
            '"self_critique_confidence": 0.0, "scoring_point_results": []}]}\n'
            "Rules:\n"
            "- Only include the specified questions.\n"
            "- If an answer is missing or unclear, score 0 and explain in self_critique.\n"
            "- Return valid JSON only.\n"
        )
        content = [{"type": "text", "text": prompt}]
        for img_bytes in images:
            if isinstance(img_bytes, bytes):
                img_b64 = base64.b64encode(img_bytes).decode("utf-8")
            else:
                img_b64 = img_bytes
            content.append(
                {
                    "type": "image_url",
                    "image_url": f"data:image/jpeg;base64,{img_b64}",
                }
            )
        message = HumanMessage(content=content)
        full_response = ""
        async for chunk in self.llm.astream([message]):
            content_chunk = chunk.content
            if not content_chunk:
                continue
            if isinstance(content_chunk, str):
                full_response += content_chunk
                if stream_callback:
                    await stream_callback("output", content_chunk)
            elif isinstance(content_chunk, list):
                for part in content_chunk:
                    text_part = ""
                    if isinstance(part, str):
                        text_part = part
                    elif isinstance(part, dict) and "text" in part:
                        text_part = part["text"]
                    if text_part:
                        full_response += text_part
                        if stream_callback:
                            await stream_callback("output", text_part)
        if not full_response:
            return []
        try:
            json_text = self._extract_json_from_text(full_response)
            payload = self._load_json_with_repair(json_text)
        except Exception:
            return []
        raw_details = (
            payload.get("question_details")
            or payload.get("questionDetails")
            or payload.get("questions")
            or []
        )
        if not isinstance(raw_details, list):
            return []
        normalized_missing = {self._normalize_question_id(qid) for qid in missing_ids if qid}
        normalized = []
        for detail in raw_details:
            if not isinstance(detail, dict):
                continue
            normalized_detail = self._normalize_question_detail(detail, None)
            qid = self._normalize_question_id(normalized_detail.get("question_id"))
            if qid and qid in normalized_missing:
                normalized.append(normalized_detail)
        return normalized

    async def _ensure_student_result_complete(
        self,
        result: Dict[str, Any],
        parsed_rubric: Dict[str, Any],
        student_key: str,
        images: List[bytes],
        context_info: str,
        stream_callback: Optional[Callable[[str, str], Awaitable[None]]] = None,
    ) -> Dict[str, Any]:
        max_passes = self._read_int_env("GRADING_COMPLETION_PASSES", 1)
        if max_passes <= 0:
            return result
        expected_ids = self._get_expected_question_ids(parsed_rubric)
        if not expected_ids:
            return result
        details = result.get("question_details") or []
        if not isinstance(details, list):
            details = []
        existing_ids = self._collect_question_detail_ids(details)
        missing_ids = [qid for qid in expected_ids if qid not in existing_ids]
        if not missing_ids:
            return result
        completion_details = await self._grade_missing_questions(
            images=images,
            student_key=student_key,
            parsed_rubric=parsed_rubric,
            missing_ids=missing_ids,
            context_info=context_info,
            stream_callback=stream_callback,
        )
        if completion_details:
            merged = self._merge_question_details(details, completion_details)
        else:
            merged = self._merge_question_details(
                details,
                self._build_missing_question_placeholders(missing_ids, parsed_rubric),
            )
        result["question_details"] = merged
        result["missing_question_ids"] = missing_ids
        total_score, max_score = self._sum_question_detail_scores(merged)
        result["total_score"] = total_score
        result["max_score"] = max_score
        return result

    def _build_student_grading_rubric_info(
        self,
        parsed_rubric: Dict[str, Any],
        question_ids: Optional[List[str]] = None,
    ) -> str:
        """构建学生批改用的评分标准信息"""
        if not parsed_rubric:
            return "请根据答案的正确性、完整性和清晰度进行评分"

        if parsed_rubric.get("rubric_context"):
            return parsed_rubric["rubric_context"]

        questions = parsed_rubric.get("questions", [])
        if question_ids:
            normalized_ids = {self._normalize_question_id(qid) for qid in question_ids if qid}
            questions = [
                q
                for q in questions
                if self._normalize_question_id(q.get("question_id") or q.get("id"))
                in normalized_ids
            ]
        if not questions:
            return "请根据答案的正确性、完整性和清晰度进行评分"

        lines = [
            f"评分标准（共{parsed_rubric.get('total_questions', len(questions))}题，"
            f"总分{parsed_rubric.get('total_score', 0)}分）：",
            "",
        ]

        for q in self._limit_questions_for_prompt(questions):
            qid = q.get("question_id") or q.get("id") or "?"
            max_score = q.get("max_score", 0)
            lines.append(f"第{qid}题 (满分{max_score}分):")

            # 评分要点
            scoring_points = q.get("scoring_points", [])
            for idx, sp in enumerate(self._limit_criteria_for_prompt(scoring_points), 1):
                point_id = sp.get("point_id") or f"{qid}.{idx}"
                lines.append(
                    f"  - [{point_id}] [{sp.get('score', 0)}分] {sp.get('description', '')}"
                )

            # 标准答案
            if q.get("standard_answer"):
                answer = q["standard_answer"]
                preview = answer[:150] + "..." if len(answer) > 150 else answer
                lines.append(f"  标准答案: {preview}")

            lines.append("")

        return "\n".join(lines)

    async def grade_batch_pages_stream(
        self,
        images: List[bytes],
        page_indices: List[int],
        parsed_rubric: Dict[str, Any],
        page_contexts: Optional[Dict[int, Dict[str, Any]]] = None,
    ) -> AsyncIterator[Dict[str, str]]:
        """
        批量批改多页（一次 LLM 调用）

        将多张图片一起发送给 LLM，要求按页顺序批改。
        这比每页单独调用更高效，输出也更有序。

        Args:
            images: 图像字节列表
            page_indices: 对应的页面索引列表
            parsed_rubric: 解析后的评分标准
            page_contexts: 页面上下文字典 {page_index: context}

        Yields:
            str: LLM 响应的文本数据块
        """
        if not images:
            return

        # 构建评分标准信息（不让 LLM 决定 max_score）
        rubric_info = self._build_batch_rubric_info(parsed_rubric)

        # 构建页面上下文信息
        page_context_info = ""
        if page_contexts:
            context_lines = []
            for idx in page_indices:
                ctx = page_contexts.get(idx, {})
                if ctx:
                    q_nums = ctx.get("question_numbers", [])
                    if q_nums:
                        context_lines.append(
                            f"- 图片 {page_indices.index(idx) + 1} (页 {idx + 1}): 预期题号 {q_nums}"
                        )
            if context_lines:
                page_context_info = f"\n\n## 页面索引信息（请以此为准）\n" + "\n".join(
                    context_lines
                )

        # 构建批量批改 prompt
        prompt = f"""你是一位**严格但公平**的阅卷教师。请批改以下 {len(images)} 张学生答题图片。

## 评分标准（带编号）
{rubric_info}
{page_context_info}

## 批改任务
请按顺序批改每张图片，对每张图片：
1. 识别页面中的题目编号
2. **逐条评分**：每道题必须逐一覆盖该题所有评分点（point_id），每个评分点输出一个 scoring_results 条目
   - 若某评分点未在作答中出现，仍需输出该条目，awarded=0，evidence 填写 "【原文引用】未找到"
 3. 每个评分点必须输出对应的 rubric_reference（包含 point_id、描述，以及若已提供则包含标准值）以及**具体评分依据**（引用图片中的原文证据）
 4. **严格依据评分标准**：评分标准是核心依据，但允许等价表达与合理变形；不要要求一字不差，只要证据充分且逻辑等价即可给分
 5. **判定与得分一致**：若判定“得分/正确”，awarded 必须 > 0；若判定“不得分/错误”，awarded 必须 = 0
 6. **反幻觉约束**：只能基于图片中明确可见的内容引用证据；不得臆测或替学生“补写”。若证据不足，awarded=0，evidence=【原文引用】未找到，并在 self_critique 标注不确定
 7. **证据冲突直接扣分**：若证据与评分点要求冲突（如写 AAA 却被判 AAS/ASA），直接判 0 分并说明冲突点
 8. **证明/理由类不得“碰运气”**：需要理由/证明的评分点，若只给结论或仅写“disagree/unchanged”等无论证表述，必须判 0 分
 9. **多条件评分点**：若评分点描述包含“同时/并且/以及/both/and/含…与…”，必须逐项满足；缺任一项直接判 0 分
 10. 不得根据最终答案“倒推”过程正确；过程/理由错误即扣分，除非评分标准明确允许“仅答案正确”
 11. **另类方法**：如学生使用不同但有效的推理方法，可给分；但需在 self_critique 中说明其与标准的差异，并降低 confidence
 12. 每道题必须输出 self_critique，并提供自评置信度 self_critique_confidence（0-1）
 13. 自白需对自己的批改进行评判：主动指出不确定与遗漏
    - **奖励诚实**：坦诚指出证据不足/不确定之处，可维持或略升 self_critique_confidence
    - **惩罚不诚实**：若结论缺乏证据或存在夸大，自白必须降低 self_critique_confidence 并说明
 14. 若无法匹配评分标准的 point_id，仍可给分，但需在 self_critique 中说明，并显著降低 confidence
 15. **一致性自检**：输出前逐条核对 awarded / decision / reason / evidence / summary 是否一致；若冲突，以证据与评分标准为准进行修正

## 输出格式
请为每张图片输出一个 JSON 对象，图片之间用 `---PAGE_BREAK---` 分隔。

```json
{{
    "page_index": 0,
    "score": 本页总得分,
    "confidence": 评分置信度（0.0-1.0）,
    "is_blank_page": false,
    "question_numbers": ["1", "2"],
    "question_details": [
        {{
            "question_id": "1",
            "score": 8,
            "confidence": 0.82,
            "student_answer": "学生的解答内容摘要...",
            "feedback": "整体评价：xxx。扣分原因：xxx。",
            "self_critique": "证据只覆盖关键一步，仍可能遗漏中间推导，建议复核。",
            "self_critique_confidence": 0.62,
            "rubric_refs": ["1.1", "1.2"],
            "scoring_results": [
                {{
                    "point_id": "1.1",
                    "rubric_reference": "[1.1] 正确列出方程",
                    "decision": "得分",
                    "awarded": 2,
                    "max_points": 2,
                    "evidence": "【原文引用】学生写了 'x + 2 = 5'，正确列出方程",
                    "reason": "方程列式正确"
                }},
                {{
                    "point_id": "1.2",
                    "rubric_reference": "[1.2] 正确求解",
                    "decision": "不得分",
                    "awarded": 0,
                    "max_points": 3,
                    "evidence": "【原文引用】学生写 'x = 2'（错误，正确答案是 x = 3）",
                    "reason": "最终解错误"
                }}
            ]
        }}
    ],
    "page_summary": "本页包含第1-2题的解答"
}}
---PAGE_BREAK---
{{
    "page_index": 1,
    ...
}}
```

## 评分原则
1. **引用编号**：`point_id` 必须与评分标准中的编号一致（如 "1.1", "2.3"）
2. **提供证据**：`evidence` 必须引用学生答卷中的原文，用【原文引用】开头
3. **引用标准值**：若评分标准提供 expected_value，rubric_reference 中必须包含该标准值
4. **按顺序批改**：图片顺序对应页面顺序（图片1=页面1，图片2=页面2...）
5. **空白页处理**：如果是空白页，设置 is_blank_page=true, score=0
6. **详细反馈**：feedback 中说明整体评价和具体扣分原因
7. **自白与置信度**：每道题必须有 self_critique 与 self_critique_confidence
8. **判定一致性**：decision 与 awarded 必须一致，避免“判定得分但 awarded=0”的输出
9. **总结一致性**：summary/feedback 必须与评分点一致；若任一评分点为 0，不得写“完全正确”
10. **逐条输出**：不要只输出 summary；评分点条目必须完整覆盖该题全部 rubric 评分点

现在请开始批改。"""

        # 构建包含所有图片的消息内容
        content = [{"type": "text", "text": prompt}]
        for i, image in enumerate(images):
            img_b64 = base64.b64encode(image).decode("utf-8")
            content.append({"type": "image_url", "image_url": f"data:image/png;base64,{img_b64}"})

        message = HumanMessage(content=content)

        # 流式调用
        async for chunk in self.llm.astream([message]):
            output_text, thinking_text = split_thinking_content(chunk.content)
            if thinking_text:
                yield {"type": "thinking", "content": thinking_text}
            if output_text:
                yield {"type": "output", "content": output_text}

    def _build_batch_rubric_info(self, parsed_rubric: Dict[str, Any]) -> str:
        """构建批量批改的评分标准信息"""
        if not parsed_rubric:
            return "请根据答案的正确性、完整性和清晰度进行评分"

        if parsed_rubric.get("rubric_context"):
            rubric_context = parsed_rubric["rubric_context"]
            questions = parsed_rubric.get("questions", [])
            point_lines = []
            for q in self._limit_questions_for_prompt(questions):
                q_id = q.get("question_id", "?")
                scoring_points = q.get("scoring_points", [])
                if not scoring_points:
                    continue
                entries = []
                for sp in self._limit_criteria_for_prompt(scoring_points):
                    point_id = sp.get("point_id", "")
                    description = sp.get("description", "")
                    score = sp.get("score", 0)
                    expected_value = sp.get("expected_value") or sp.get("expectedValue") or ""
                    expected_value = str(expected_value).strip()
                    expected_value_snippet = ""
                    if expected_value:
                        snippet = (
                            expected_value
                            if len(expected_value) <= 80
                            else f"{expected_value[:80]}..."
                        )
                        expected_value_snippet = f"；标准值:{snippet}"
                    if point_id:
                        entries.append(
                            f"[{point_id}] {description}（{score}分{expected_value_snippet}）"
                        )
                if entries:
                    point_lines.append(f"第 {q_id} 题: " + "；".join(entries))
            if point_lines:
                return rubric_context + "\n\n## 得分点编号索引\n" + "\n".join(point_lines)
            return rubric_context

        # 从题目列表构建
        questions = parsed_rubric.get("questions", [])
        if not questions:
            return "请根据答案的正确性、完整性和清晰度进行评分"

        total_score = parsed_rubric.get("total_score", 0)
        lines = [f"共 {len(questions)} 题，总分 {total_score} 分。\n"]

        for q in self._limit_questions_for_prompt(questions):
            q_id = q.get("question_id", "?")
            max_score = q.get("max_score", 0)
            lines.append(f"第 {q_id} 题（满分 {max_score} 分）")

            # 添加得分点（包含 point_id）
            scoring_points = q.get("scoring_points", [])
            for sp in self._limit_criteria_for_prompt(scoring_points):
                point_id = sp.get("point_id", "")
                point_label = f"[{point_id}]" if point_id else ""
                expected_value = sp.get("expected_value") or sp.get("expectedValue") or ""
                expected_value = str(expected_value).strip()
                expected_value_snippet = ""
                if expected_value:
                    snippet = (
                        expected_value if len(expected_value) <= 80 else f"{expected_value[:80]}..."
                    )
                    expected_value_snippet = f"；标准值:{snippet}"
                lines.append(
                    f"  - {point_label} {sp.get('description', '')}（{sp.get('score', 0)}分{expected_value_snippet}）"
                )

        return "\n".join(lines)

    async def get_rubric_for_question(
        self,
        question_id: str,
    ) -> Optional[QuestionRubric]:
        """
        动态获取指定题目的评分标准 (Requirement 1.1)

        从 RubricRegistry 获取指定题目的评分标准，包括得分点、标准答案、另类解法。

        Args:
            question_id: 题目编号（如 "1", "7a", "15"）

        Returns:
            QuestionRubric: 该题目的完整评分标准，如果未找到返回 None
        """
        if self._rubric_registry is None:
            logger.warning("未设置 RubricRegistry，无法获取评分标准")
            return None

        result = self._rubric_registry.get_rubric_for_question(question_id)

        if result.is_default:
            logger.warning(f"题目 {question_id} 使用默认评分标准，置信度: {result.confidence}")

        return result.rubric

    def _build_scoring_point_prompt(
        self,
        rubric: QuestionRubric,
        student_answer: str,
        reviewer_notes: Optional[str] = None,
    ) -> str:
        """
        构建得分点逐一核对的提示词 (Requirement 1.2)

        Args:
            rubric: 评分标准
            student_answer: 学生答案描述

        Returns:
            str: 得分点核对提示词
        """
        # 构建得分点列表
        scoring_points_text = ""
        for i, sp in enumerate(rubric.scoring_points, 1):
            required_mark = "【必须】" if sp.is_required else "【可选】"
            point_id = sp.point_id or f"{rubric.question_id}.{i}"
            scoring_points_text += (
                f"{i}. [{point_id}] {required_mark} {sp.description} ({sp.score}分)\n"
            )

        # 构建另类解法列表 (Requirement 1.3)
        alternative_text = ""
        if rubric.alternative_solutions:
            alternative_text = "\n## 另类解法（同样有效）\n"
            for i, alt in enumerate(rubric.alternative_solutions, 1):
                alternative_text += f"{i}. {alt.description}\n"
                alternative_text += f"   评分条件: {alt.scoring_conditions}\n"
                alternative_text += f"   最高分: {alt.max_score}分\n"

        notes_block = reviewer_notes.strip() if reviewer_notes else ""

        return f"""请对以下学生答案进行得分点逐一核对评分。

## 题目信息
- 题号: {rubric.question_id}
- 满分: {rubric.max_score}分
- 题目: {rubric.question_text}

## 标准答案
{rubric.standard_answer}

## 得分点列表
{scoring_points_text}
{alternative_text}
## 批改注意事项
{rubric.grading_notes if rubric.grading_notes else "无特殊注意事项"}

## 教师备注
{notes_block or "无"}

## 学生答案
{student_answer}

## 评分任务
请逐一核对每个得分点，判断学生是否获得该得分点的分数。

注意：
1. 如果学生使用了另类解法，只要符合评分条件，同样给分
2. 部分正确的得分点可以给部分分数
3. 必须为每个得分点提供证据说明

## 输出格式（JSON）
```json
{{
    "question_id": "{rubric.question_id}",
    "total_score": 学生总得分,
    "max_score": {rubric.max_score},
    "confidence": 评分置信度（0.0-1.0）,
    "used_alternative_solution": false,
    "alternative_solution_index": null,
    "scoring_point_results": [
        {{
            "point_index": 1,
            "description": "得分点描述",
            "max_score": 该得分点满分,
            "awarded": 获得的分数,
            "evidence": "在学生答案中找到的证据或未找到的说明"
        }}
    ],
    "feedback": "综合评价和改进建议"
}}
```"""

    async def grade_question_with_scoring_points(
        self,
        question_id: str,
        student_answer: str,
        image: Optional[bytes] = None,
    ) -> QuestionResult:
        """
        使用得分点逐一核对方式评分单道题目 (Requirement 1.2)

        动态获取评分标准，逐一核对每个得分点，支持另类解法。

        Args:
            question_id: 题目编号
            student_answer: 学生答案描述（从视觉分析获得）
            image: 可选的题目图像（用于视觉验证）

        Returns:
            QuestionResult: 包含得分点明细的评分结果
        """
        # 1. 动态获取评分标准 (Requirement 1.1)
        rubric = await self.get_rubric_for_question(question_id)

        if rubric is None:
            logger.error(f"无法获取题目 {question_id} 的评分标准")
            return QuestionResult(
                question_id=question_id,
                score=0.0,
                max_score=0.0,
                confidence=0.0,
                feedback="无法获取评分标准",
                scoring_point_results=[],
                page_indices=[],
                is_cross_page=False,
                student_answer=student_answer,
            )

        # 2. 构建得分点核对提示词
        prompt = self._build_scoring_point_prompt(rubric, student_answer)

        # 3. 调用 LLM 进行评分
        try:
            if image:
                # 如果有图像，使用视觉 API
                img_b64 = (
                    base64.b64encode(image).decode("utf-8") if isinstance(image, bytes) else image
                )
                response_text = await self._call_vision_api(img_b64, prompt)
            else:
                # 纯文本评分
                response = await self.llm.ainvoke([HumanMessage(content=prompt)])
                response_text = self._extract_text_from_response(response.content)

            # 4. 解析响应
            json_text = self._extract_json_from_text(response_text)
            result = json.loads(json_text)

            # 5. 构建 QuestionResult
            scoring_point_results = []
            for spr_data in result.get("scoring_point_results", []):
                point_index = spr_data.get("point_index", 1) - 1
                if 0 <= point_index < len(rubric.scoring_points):
                    sp = rubric.scoring_points[point_index]
                else:
                    # 创建临时得分点
                    sp = ScoringPoint(
                        description=spr_data.get("description", ""),
                        score=spr_data.get("max_score", 0),
                        is_required=True,
                    )

                scoring_point_results.append(
                    ScoringPointResult(
                        scoring_point=sp,
                        awarded=spr_data.get("awarded", 0),
                        evidence=spr_data.get("evidence", ""),
                    )
                )

            question_result = QuestionResult(
                question_id=question_id,
                score=result.get("total_score", 0),
                max_score=result.get("max_score", rubric.max_score),
                confidence=result.get("confidence", 0.8),
                feedback=result.get("feedback", ""),
                scoring_point_results=scoring_point_results,
                page_indices=[],
                is_cross_page=False,
                student_answer=student_answer,
            )

            logger.info(
                f"题目 {question_id} 评分完成: "
                f"{question_result.score}/{question_result.max_score}, "
                f"置信度: {question_result.confidence}"
            )

            return question_result

        except json.JSONDecodeError as e:
            logger.error(f"得分点评分 JSON 解析失败: {e}")
            return QuestionResult(
                question_id=question_id,
                score=0.0,
                max_score=rubric.max_score,
                confidence=0.0,
                feedback=f"评分解析失败: {str(e)}",
                scoring_point_results=[],
                page_indices=[],
                is_cross_page=False,
                student_answer=student_answer,
            )
        except Exception as e:
            logger.error(f"得分点评分失败: {e}", exc_info=True)
            return QuestionResult(
                question_id=question_id,
                score=0.0,
                max_score=rubric.max_score,
                confidence=0.0,
                feedback=f"评分失败: {str(e)}",
                scoring_point_results=[],
                page_indices=[],
                is_cross_page=False,
                student_answer=student_answer,
            )

    async def grade_page_with_dynamic_rubric(
        self,
        image: bytes,
        page_index: int = 0,
        parsed_rubric: Optional[Dict[str, Any]] = None,
    ) -> PageGradingResult:
        """
        使用动态评分标准批改单页 (Requirements 1.1, 1.2, 1.3)

        集成 RubricRegistry 和 GradingSkills，实现：
        1. 识别页面中的题目编号
        2. 为每道题动态获取评分标准
        3. 逐一核对得分点
        4. 支持另类解法

        Args:
            image: 图像字节
            page_index: 页码索引
            parsed_rubric: 解析后的评分标准（可选，用于兼容旧接口）

        Returns:
            PageGradingResult: 包含详细得分点明细的页面批改结果
        """
        logger.info(f"开始批改第 {page_index + 1} 页（使用动态评分标准）")

        # 1. 首先进行基础批改，获取题目编号和学生答案
        basic_result = await self.grade_page(
            image=image,
            rubric="",  # 先不传评分标准，只做识别
            max_score=100.0,
            parsed_rubric=parsed_rubric,
        )

        # 2. 如果是空白页，直接返回
        if basic_result.get("is_blank_page", False):
            return PageGradingResult(
                page_index=page_index,
                question_results=[],
                student_info=None,
                is_blank_page=True,
                raw_response=json.dumps(basic_result, ensure_ascii=False),
            )

        # 3. 提取学生信息
        student_info = None
        if basic_result.get("student_info"):
            si = basic_result["student_info"]
            student_info = StudentInfo(
                student_id=si.get("student_id"),
                student_name=si.get("name"),
                confidence=0.8,
            )

        # 4. 对每道题进行得分点逐一核对评分
        question_results = []
        for q_detail in basic_result.get("question_details", []):
            question_id = q_detail.get("question_id", "")
            student_answer = q_detail.get("student_answer", "")

            if not question_id:
                continue

            # 使用得分点核对方式评分
            if self._rubric_registry:
                q_result = await self.grade_question_with_scoring_points(
                    question_id=question_id,
                    student_answer=student_answer,
                    image=image,
                )
                q_result.page_indices = [page_index]
            else:
                # 如果没有 RubricRegistry，使用基础结果
                q_result = QuestionResult(
                    question_id=question_id,
                    score=q_detail.get("score", 0),
                    max_score=q_detail.get("max_score", 0),
                    confidence=basic_result.get("confidence", 0.8),
                    feedback=q_detail.get("feedback", ""),
                    scoring_point_results=[],
                    page_indices=[page_index],
                    is_cross_page=False,
                    student_answer=student_answer,
                )

            question_results.append(q_result)

        # 5. 构建页面批改结果
        page_result = PageGradingResult(
            page_index=page_index,
            question_results=question_results,
            student_info=student_info,
            is_blank_page=False,
            raw_response=json.dumps(basic_result, ensure_ascii=False),
        )

        total_score = sum(qr.score for qr in question_results)
        total_max = sum(qr.max_score for qr in question_results)

        logger.info(
            f"第 {page_index + 1} 页批改完成: "
            f"{total_score}/{total_max}, "
            f"共 {len(question_results)} 道题"
        )

        return page_result

    def _format_rubric_for_prompt(
        self,
        rubric: QuestionRubric,
    ) -> str:
        """
        将 QuestionRubric 格式化为提示词中使用的文本

        Args:
            rubric: 评分标准对象

        Returns:
            str: 格式化的评分标准文本
        """
        lines = [
            f"第{rubric.question_id}题 (满分{rubric.max_score}分):",
            (
                f"  题目: {rubric.question_text[:200]}..."
                if len(rubric.question_text) > 200
                else f"  题目: {rubric.question_text}"
            ),
        ]

        # 添加得分点
        if rubric.scoring_points:
            lines.append("  得分点:")
            for sp in rubric.scoring_points:
                required = "【必须】" if sp.is_required else "【可选】"
                lines.append(f"    - {required} {sp.description} ({sp.score}分)")

        # 添加标准答案
        if rubric.standard_answer:
            answer_preview = (
                rubric.standard_answer[:150] + "..."
                if len(rubric.standard_answer) > 150
                else rubric.standard_answer
            )
            lines.append(f"  标准答案: {answer_preview}")

        # 添加另类解法 (Requirement 1.3)
        if rubric.alternative_solutions:
            lines.append("  另类解法:")
            for alt in rubric.alternative_solutions:
                lines.append(f"    - {alt.description} (最高{alt.max_score}分)")
                lines.append(f"      条件: {alt.scoring_conditions}")

        return "\n".join(lines)

    async def build_dynamic_rubric_context(
        self,
        question_ids: List[str],
    ) -> str:
        """
        为指定题目列表构建动态评分标准上下文

        Args:
            question_ids: 题目编号列表

        Returns:
            str: 格式化的评分标准上下文文本
        """
        if not self._rubric_registry:
            return ""

        rubric_texts = []
        for qid in question_ids:
            rubric = await self.get_rubric_for_question(qid)
            if rubric:
                rubric_texts.append(self._format_rubric_for_prompt(rubric))

        if not rubric_texts:
            return ""

        total_score = self._rubric_registry.total_score
        return f"评分标准（总分{total_score}分）：\n\n" + "\n\n".join(rubric_texts)

    # ==================== 得分点明细生成 (Requirement 1.2) ====================

    def _create_scoring_point_results_from_response(
        self,
        response_data: Dict[str, Any],
        rubric: QuestionRubric,
    ) -> List[ScoringPointResult]:
        """
        从 LLM 响应创建得分点明细列表 (Requirement 1.2)

        为每个得分点记录得分情况，生成详细的得分点明细。

        Args:
            response_data: LLM 响应数据
            rubric: 评分标准

        Returns:
            List[ScoringPointResult]: 得分点明细列表
        """
        scoring_point_results = []
        response_points = response_data.get("scoring_point_results", [])

        # 确保每个评分标准中的得分点都有对应的结果
        for i, sp in enumerate(rubric.scoring_points):
            # 查找对应的响应数据
            matched_response = None
            for rp in response_points:
                # 通过索引或描述匹配
                if rp.get("point_index") == i + 1:
                    matched_response = rp
                    break
                if rp.get("description", "").strip() == sp.description.strip():
                    matched_response = rp
                    break

            if matched_response:
                awarded = matched_response.get("awarded", 0)
                evidence = matched_response.get("evidence", "")
            else:
                # 如果没有匹配的响应，标记为未评估
                awarded = 0
                evidence = "未评估"

            scoring_point_results.append(
                ScoringPointResult(
                    scoring_point=sp,
                    awarded=awarded,
                    evidence=evidence,
                )
            )

        return scoring_point_results

    def generate_scoring_point_summary(
        self,
        scoring_point_results: List[ScoringPointResult],
    ) -> str:
        """
        生成得分点明细摘要 (Requirement 1.2)

        Args:
            scoring_point_results: 得分点明细列表

        Returns:
            str: 得分点明细摘要文本
        """
        if not scoring_point_results:
            return "无得分点明细"

        lines = ["得分点明细:"]
        total_awarded = 0
        total_max = 0

        for i, spr in enumerate(scoring_point_results, 1):
            sp = spr.scoring_point
            status = "✓" if spr.awarded >= sp.score else ("△" if spr.awarded > 0 else "✗")
            required_mark = "【必须】" if sp.is_required else "【可选】"

            lines.append(
                f"  {i}. {status} {required_mark} {sp.description}: {spr.awarded}/{sp.score}分"
            )
            if spr.evidence:
                lines.append(f"      证据: {spr.evidence[:100]}...")

            total_awarded += spr.awarded
            total_max += sp.score

        lines.append(f"  总计: {total_awarded}/{total_max}分")

        return "\n".join(lines)

    async def grade_with_detailed_scoring_points(
        self,
        image: bytes,
        question_id: str,
        page_index: int = 0,
        reviewer_notes: Optional[str] = None,
    ) -> QuestionResult:
        """
        使用详细得分点核对方式评分 (Requirement 1.2)

        这是一个完整的评分流程：
        1. 视觉分析提取学生答案
        2. 动态获取评分标准
        3. 逐一核对每个得分点
        4. 生成详细的得分点明细

        Args:
            image: 题目图像
            question_id: 题目编号
            page_index: 页码索引

        Returns:
            QuestionResult: 包含详细得分点明细的评分结果
        """
        # 1. 获取评分标准
        rubric = await self.get_rubric_for_question(question_id)
        if rubric is None:
            return QuestionResult(
                question_id=question_id,
                score=0.0,
                max_score=0.0,
                confidence=0.0,
                feedback="无法获取评分标准",
                scoring_point_results=[],
                page_indices=[page_index],
                is_cross_page=False,
                student_answer="",
            )

        # 2. 视觉分析提取学生答案
        img_b64 = base64.b64encode(image).decode("utf-8") if isinstance(image, bytes) else image

        extraction_prompt = f"""请分析这张学生答题图像，提取第{question_id}题的学生答案。

任务：
1. 找到第{question_id}题的学生作答内容
2. 详细描述学生写了什么（公式、文字、图表、计算过程等）
3. 客观描述，不要评分

输出格式（JSON）：
```json
{{
    "question_id": "{question_id}",
    "student_answer": "学生答案的详细描述",
    "has_content": true,
    "content_type": "计算/文字/图表/混合"
}}
```"""

        try:
            extraction_response = await self._call_vision_api(img_b64, extraction_prompt)
            extraction_json = self._extract_json_from_text(extraction_response)
            extraction_data = json.loads(extraction_json)
            student_answer = extraction_data.get("student_answer", "")
        except Exception as e:
            logger.warning(f"学生答案提取失败: {e}")
            student_answer = "无法提取学生答案"

        # 3. 构建得分点核对提示词
        prompt = self._build_scoring_point_prompt(
            rubric, student_answer, reviewer_notes=reviewer_notes
        )

        # 4. 调用 LLM 进行得分点核对
        try:
            response_text = await self._call_vision_api(img_b64, prompt)
            json_text = self._extract_json_from_text(response_text)
            result_data = json.loads(json_text)

            # 5. 创建得分点明细
            scoring_point_results = self._create_scoring_point_results_from_response(
                result_data, rubric
            )

            # 6. 生成反馈
            feedback = result_data.get("feedback", "")
            scoring_summary = self.generate_scoring_point_summary(scoring_point_results)
            full_feedback = f"{feedback}\n\n{scoring_summary}"

            return QuestionResult(
                question_id=question_id,
                score=result_data.get("total_score", 0),
                max_score=result_data.get("max_score", rubric.max_score),
                confidence=result_data.get("confidence", 0.8),
                feedback=full_feedback,
                scoring_point_results=scoring_point_results,
                page_indices=[page_index],
                is_cross_page=False,
                student_answer=student_answer,
            )

        except Exception as e:
            logger.error(f"详细得分点评分失败: {e}", exc_info=True)
            return QuestionResult(
                question_id=question_id,
                score=0.0,
                max_score=rubric.max_score,
                confidence=0.0,
                feedback=f"评分失败: {str(e)}",
                scoring_point_results=[],
                page_indices=[page_index],
                is_cross_page=False,
                student_answer=student_answer,
            )

    # ==================== 另类解法支持 (Requirement 1.3) ====================

    def _build_alternative_solution_prompt(
        self,
        rubric: QuestionRubric,
        student_answer: str,
    ) -> str:
        """
        构建另类解法检测提示词 (Requirement 1.3)

        Args:
            rubric: 评分标准
            student_answer: 学生答案描述

        Returns:
            str: 另类解法检测提示词
        """
        if not rubric.alternative_solutions:
            return ""

        alt_solutions_text = ""
        for i, alt in enumerate(rubric.alternative_solutions, 1):
            alt_solutions_text += f"""
### 另类解法 {i}
- 描述: {alt.description}
- 评分条件: {alt.scoring_conditions}
- 最高分: {alt.max_score}分
"""

        return f"""请判断学生是否使用了另类解法。

## 题目信息
- 题号: {rubric.question_id}
- 满分: {rubric.max_score}分

## 标准答案
{rubric.standard_answer}

## 可接受的另类解法
{alt_solutions_text}

## 学生答案
{student_answer}

## 任务
1. 判断学生是否使用了标准解法
2. 如果不是标准解法，判断是否使用了某个另类解法
3. 如果使用了另类解法，判断是否满足评分条件

## 输出格式（JSON）
```json
{{
    "uses_standard_solution": true/false,
    "uses_alternative_solution": true/false,
    "alternative_solution_index": null 或 1/2/3...,
    "alternative_solution_description": "使用的另类解法描述",
    "meets_scoring_conditions": true/false,
    "condition_analysis": "评分条件分析",
    "recommended_max_score": 建议的最高分
}}
```"""

    async def detect_alternative_solution(
        self,
        question_id: str,
        student_answer: str,
        image: Optional[bytes] = None,
    ) -> Dict[str, Any]:
        """
        检测学生是否使用了另类解法 (Requirement 1.3)

        Args:
            question_id: 题目编号
            student_answer: 学生答案描述
            image: 可选的题目图像

        Returns:
            Dict: 另类解法检测结果
        """
        # 获取评分标准
        rubric = await self.get_rubric_for_question(question_id)
        if rubric is None or not rubric.alternative_solutions:
            return {
                "uses_standard_solution": True,
                "uses_alternative_solution": False,
                "alternative_solution_index": None,
                "alternative_solution_description": None,
                "meets_scoring_conditions": False,
                "condition_analysis": "无另类解法可检测",
                "recommended_max_score": rubric.max_score if rubric else 0,
            }

        # 构建检测提示词
        prompt = self._build_alternative_solution_prompt(rubric, student_answer)

        try:
            if image:
                img_b64 = (
                    base64.b64encode(image).decode("utf-8") if isinstance(image, bytes) else image
                )
                response_text = await self._call_vision_api(img_b64, prompt)
            else:
                response = await self.llm.ainvoke([HumanMessage(content=prompt)])
                response_text = self._extract_text_from_response(response.content)

            json_text = self._extract_json_from_text(response_text)
            result = json.loads(json_text)

            logger.info(
                f"题目 {question_id} 另类解法检测: "
                f"标准解法={result.get('uses_standard_solution')}, "
                f"另类解法={result.get('uses_alternative_solution')}"
            )

            return result

        except Exception as e:
            logger.error(f"另类解法检测失败: {e}")
            return {
                "uses_standard_solution": True,
                "uses_alternative_solution": False,
                "alternative_solution_index": None,
                "alternative_solution_description": None,
                "meets_scoring_conditions": False,
                "condition_analysis": f"检测失败: {str(e)}",
                "recommended_max_score": rubric.max_score,
            }

    async def grade_with_alternative_solution_support(
        self,
        image: bytes,
        question_id: str,
        page_index: int = 0,
    ) -> QuestionResult:
        """
        支持另类解法的完整评分流程 (Requirement 1.3)

        这是一个增强的评分流程：
        1. 视觉分析提取学生答案
        2. 检测是否使用另类解法
        3. 根据解法类型选择评分标准
        4. 逐一核对得分点
        5. 生成详细的评分结果

        Args:
            image: 题目图像
            question_id: 题目编号
            page_index: 页码索引

        Returns:
            QuestionResult: 包含另类解法信息的评分结果
        """
        # 1. 获取评分标准
        rubric = await self.get_rubric_for_question(question_id)
        if rubric is None:
            return QuestionResult(
                question_id=question_id,
                score=0.0,
                max_score=0.0,
                confidence=0.0,
                feedback="无法获取评分标准",
                scoring_point_results=[],
                page_indices=[page_index],
                is_cross_page=False,
                student_answer="",
            )

        # 2. 视觉分析提取学生答案
        img_b64 = base64.b64encode(image).decode("utf-8") if isinstance(image, bytes) else image

        extraction_prompt = f"""请分析这张学生答题图像，提取第{question_id}题的学生答案。

任务：
1. 找到第{question_id}题的学生作答内容
2. 详细描述学生的解题方法和步骤
3. 客观描述，不要评分

输出格式（JSON）：
```json
{{
    "question_id": "{question_id}",
    "student_answer": "学生答案的详细描述",
    "solution_method": "学生使用的解题方法描述",
    "has_content": true
}}
```"""

        try:
            extraction_response = await self._call_vision_api(img_b64, extraction_prompt)
            extraction_json = self._extract_json_from_text(extraction_response)
            extraction_data = json.loads(extraction_json)
            student_answer = extraction_data.get("student_answer", "")
            solution_method = extraction_data.get("solution_method", "")
        except Exception as e:
            logger.warning(f"学生答案提取失败: {e}")
            student_answer = "无法提取学生答案"
            solution_method = ""

        # 3. 检测另类解法
        alt_detection = await self.detect_alternative_solution(
            question_id=question_id,
            student_answer=f"{student_answer}\n解题方法: {solution_method}",
            image=image,
        )

        # 4. 根据解法类型构建评分提示词
        if alt_detection.get("uses_alternative_solution") and alt_detection.get(
            "meets_scoring_conditions"
        ):
            # 使用另类解法的评分标准
            alt_index = alt_detection.get("alternative_solution_index", 1) - 1
            if 0 <= alt_index < len(rubric.alternative_solutions):
                alt_solution = rubric.alternative_solutions[alt_index]
                scoring_context = f"""
## 学生使用了另类解法
- 解法描述: {alt_solution.description}
- 评分条件: {alt_solution.scoring_conditions}
- 最高分: {alt_solution.max_score}分

请根据另类解法的评分条件进行评分。
"""
                effective_max_score = alt_solution.max_score
            else:
                scoring_context = ""
                effective_max_score = rubric.max_score
        else:
            scoring_context = ""
            effective_max_score = rubric.max_score

        # 5. 构建完整的评分提示词
        prompt = self._build_scoring_point_prompt(rubric, student_answer)
        if scoring_context:
            prompt = prompt.replace("## 学生答案", f"{scoring_context}\n## 学生答案")

        # 6. 调用 LLM 进行评分
        try:
            response_text = await self._call_vision_api(img_b64, prompt)
            json_text = self._extract_json_from_text(response_text)
            result_data = json.loads(json_text)

            # 7. 创建得分点明细
            scoring_point_results = self._create_scoring_point_results_from_response(
                result_data, rubric
            )

            # 8. 生成反馈（包含另类解法信息）
            feedback_parts = [result_data.get("feedback", "")]

            if alt_detection.get("uses_alternative_solution"):
                if alt_detection.get("meets_scoring_conditions"):
                    feedback_parts.append(
                        f"\n【另类解法】学生使用了有效的另类解法: "
                        f"{alt_detection.get('alternative_solution_description', '')}"
                    )
                else:
                    feedback_parts.append(
                        f"\n【另类解法】学生尝试使用另类解法，但未满足评分条件: "
                        f"{alt_detection.get('condition_analysis', '')}"
                    )

            scoring_summary = self.generate_scoring_point_summary(scoring_point_results)
            feedback_parts.append(f"\n{scoring_summary}")

            full_feedback = "\n".join(feedback_parts)

            # 9. 确保分数不超过有效最高分
            final_score = min(result_data.get("total_score", 0), effective_max_score)

            return QuestionResult(
                question_id=question_id,
                score=final_score,
                max_score=effective_max_score,
                confidence=result_data.get("confidence", 0.8),
                feedback=full_feedback,
                scoring_point_results=scoring_point_results,
                page_indices=[page_index],
                is_cross_page=False,
                student_answer=student_answer,
            )

        except Exception as e:
            logger.error(f"另类解法评分失败: {e}", exc_info=True)
            return QuestionResult(
                question_id=question_id,
                score=0.0,
                max_score=rubric.max_score,
                confidence=0.0,
                feedback=f"评分失败: {str(e)}",
                scoring_point_results=[],
                page_indices=[page_index],
                is_cross_page=False,
                student_answer=student_answer,
            )

    # ==================== grade_student 方法 ====================

    async def grade_student(
        self,
        images: List[bytes],
        student_key: str,
        parsed_rubric: Dict[str, Any],
        page_indices: Optional[List[int]] = None,
        page_contexts: Optional[Dict[int, Dict[str, Any]]] = None,
        stream_callback: Optional[Callable[[str, str], Awaitable[None]]] = None,
    ) -> Dict[str, Any]:
        """
        一次性批改整个学生的所有页面

        将学生的所有答题页面作为一个整体发送给 LLM，获取完整的批改结果。
        这种方式可以更好地处理跨页题目，并减少 API 调用次数。

        Args:
            images: 学生所有答题页面的图像字节列表
            student_key: 学生标识（如姓名、学号）
            parsed_rubric: 解析后的评分标准
            page_indices: 页面索引列表（可选）
            page_contexts: 页面索引上下文（可选）
            stream_callback: 流式回调函数 (stream_type, chunk) -> None

        Returns:
            Dict: 包含学生完整批改结果
                - status: "completed" | "failed"
                - total_score: 总得分
                - max_score: 满分
                - confidence: 置信度
                - question_details: 题目详情列表
                - overall_feedback: 总体反馈
                - student_info: 学生信息（如果识别到）
        """
        if not images:
            return {
                "status": "failed",
                "error": "没有提供答题图像",
                "total_score": 0,
                "max_score": 0,
                "confidence": 0,
                "question_details": [],
            }

        logger.info(f"[grade_student] 开始批改学生 {student_key}，共 {len(images)} 页")

        # 构建评分标准上下文
        rubric_context = ""
        total_score = 0
        questions_count = 0

        if parsed_rubric:
            rubric_context = parsed_rubric.get("rubric_context", "")
            total_score = parsed_rubric.get("total_score", 0)
            questions_count = len(parsed_rubric.get("questions", []))

            if not rubric_context and parsed_rubric.get("questions"):
                # 从题目信息构建评分标准上下文
                rubric_lines = [f"评分标准（总分 {total_score} 分，共 {questions_count} 道题）：\n"]
                for q in parsed_rubric.get("questions", []):
                    qid = q.get("question_id", "?")
                    max_q_score = q.get("max_score", 0)
                    rubric_lines.append(f"\n第{qid}题（满分 {max_q_score} 分）：")

                    # 添加得分点
                    for sp in q.get("scoring_points", []):
                        point_id = sp.get("point_id", "")
                        desc = sp.get("description", "")
                        score = sp.get("score", 0)
                        rubric_lines.append(f"  - [{point_id}] {desc}（{score}分）")

                    # 添加标准答案摘要
                    std_answer = q.get("standard_answer", "")
                    if std_answer:
                        preview = std_answer[:100] + "..." if len(std_answer) > 100 else std_answer
                        rubric_lines.append(f"  标准答案：{preview}")

                rubric_context = "\n".join(rubric_lines)

        # 构建页面上下文信息
        page_context_info = ""
        if page_contexts:
            context_lines = ["页面索引信息："]
            for idx, ctx in sorted(page_contexts.items()):
                q_nums = ctx.get("question_numbers", [])
                student_info = ctx.get("student_info")
                is_first = ctx.get("is_first_page", False)
                context_lines.append(f"  - 页面 {idx}: 题目={q_nums}, 首页={is_first}")
                if student_info:
                    context_lines.append(
                        f"    学生: {student_info.get('name', '未知')}, "
                        f"学号: {student_info.get('student_id', '未知')}"
                    )
            page_context_info = "\n".join(context_lines)

        # 构建批改提示词
        prompt = f"""你是一位专业的阅卷教师，请仔细分析以下学生的答题图像并进行精确评分，同时输出**逐步骤**的批注坐标信息。

## 学生信息
- 学生标识：{student_key}
- 答题页数：{len(images)} 页

## 评分标准
{rubric_context}

{page_context_info}

## 批改要求
1. **逐题评分**：对每道题目进行独立评分
2. **得分点核对**：严格按照评分标准的得分点给分
3. **跨页处理**：如果一道题跨越多页，需要综合所有页面的内容评分
4. **另类解法**：如果学生使用了有效的另类解法，同样给分
5. **详细反馈**：为每道题提供具体的评分说明
6. **完整记录学生作答**：student_answer 字段必须完整记录学生的原始作答内容，不要省略
7. **自白与置信度**：每道题必须输出 self_critique（自我反思）和 self_critique_confidence（置信度）
   - 自白需诚实指出不确定之处、证据不足的地方
   - 如果对某道题的评分不确定，必须在 self_critique 中说明
8. **逐步骤批注**：识别学生作答的每一个步骤，标注坐标和得分情况
9. **区分 A mark 和 M mark**：
   - **A mark（Answer mark）**：答案分，只看最终答案是否正确
   - **M mark（Method mark）**：方法分，看解题步骤/方法是否正确

## 坐标系统说明
- 坐标原点在图片**左上角**
- x 轴向右增加 (0.0 = 最左, 1.0 = 最右)
- y 轴向下增加 (0.0 = 最上, 1.0 = 最下)
- 使用 bounding_box 表示区域: {{"x_min", "y_min", "x_max", "y_max"}}
- 所有坐标值为归一化坐标 (0.0-1.0)

## 批注类型说明
- `score`: 总分标注，放在题目答案旁边
- `a_mark`: A mark 标注（答案分），显示 "A1"（得分）或 "A0"（不得分）
- `m_mark`: M mark 标注（方法分），显示 "M1"（得分）或 "M0"（不得分）
- `step_check`: 步骤正确勾选 ✓
- `step_cross`: 步骤错误叉 ✗
- `error_circle`: 错误圈选，圈出错误的地方
- `comment`: 文字批注/错误讲解
- `correct_check`: 正确勾选 ✓（用于整题）
- `wrong_cross`: 错误叉 ✗（用于整题）

## 输出格式（JSON）
```json
{{
    "student_key": "{student_key}",
    "status": "completed",
    "total_score": 总得分,
    "max_score": {total_score},
    "confidence": 评分置信度（0.0-1.0）,
    "student_info": {{
        "name": "识别到的学生姓名（如有）",
        "student_id": "识别到的学号（如有）",
        "class_name": "识别到的班级（如有）"
    }},
    "question_details": [
        {{
            "question_id": "题号",
            "score": 得分,
            "max_score": 满分,
            "student_answer": "【必须完整】学生的原始作答内容，包括所有文字、公式、步骤，不要省略",
            "is_correct": true/false,
            "feedback": "评分说明",
            "confidence": 置信度,
            "self_critique": "【必须填写】自我反思：对本题评分的不确定之处、可能的遗漏、证据是否充分等",
            "self_critique_confidence": 自评置信度（0.0-1.0，越低表示越不确定）,
            "source_pages": [页码列表],
            "answer_region": {{
                "x_min": 0.1, "y_min": 0.2, "x_max": 0.9, "y_max": 0.4
            }},
            "steps": [
                {{
                    "step_id": "1.1",
                    "step_content": "学生写的第一步内容",
                    "step_region": {{"x_min": 0.1, "y_min": 0.2, "x_max": 0.8, "y_max": 0.25}},
                    "is_correct": true,
                    "mark_type": "M",
                    "mark_value": 1,
                    "feedback": "方法正确"
                }},
                {{
                    "step_id": "1.2",
                    "step_content": "学生写的第二步内容",
                    "step_region": {{"x_min": 0.1, "y_min": 0.26, "x_max": 0.8, "y_max": 0.31}},
                    "is_correct": false,
                    "mark_type": "M",
                    "mark_value": 0,
                    "feedback": "计算错误：3+5 应该等于 8，不是 9",
                    "error_detail": "3+5=9 写错了"
                }},
                {{
                    "step_id": "1.3",
                    "step_content": "最终答案",
                    "step_region": {{"x_min": 0.1, "y_min": 0.32, "x_max": 0.5, "y_max": 0.36}},
                    "is_correct": false,
                    "mark_type": "A",
                    "mark_value": 0,
                    "feedback": "答案错误，因为前面计算有误"
                }}
            ],
            "scoring_point_results": [
                {{
                    "point_id": "得分点ID",
                    "description": "得分点描述",
                    "mark_type": "M 或 A",
                    "max_score": 该得分点满分,
                    "awarded": 获得的分数,
                    "evidence": "【必须引用原文】评分依据，引用学生答案中的具体内容",
                    "error_region": {{"x_min": 0.3, "y_min": 0.26, "x_max": 0.5, "y_max": 0.31}}
                }}
            ],
            "annotations": [
                {{
                    "type": "score",
                    "page_index": 0,
                    "bounding_box": {{"x_min": 0.85, "y_min": 0.2, "x_max": 0.95, "y_max": 0.25}},
                    "text": "2/3",
                    "color": "#FF8800"
                }},
                {{
                    "type": "m_mark",
                    "page_index": 0,
                    "bounding_box": {{"x_min": 0.82, "y_min": 0.21, "x_max": 0.88, "y_max": 0.24}},
                    "text": "M1",
                    "color": "#00AA00"
                }},
                {{
                    "type": "m_mark",
                    "page_index": 0,
                    "bounding_box": {{"x_min": 0.82, "y_min": 0.27, "x_max": 0.88, "y_max": 0.30}},
                    "text": "M0",
                    "color": "#FF0000"
                }},
                {{
                    "type": "a_mark",
                    "page_index": 0,
                    "bounding_box": {{"x_min": 0.82, "y_min": 0.33, "x_max": 0.88, "y_max": 0.36}},
                    "text": "A0",
                    "color": "#FF0000"
                }},
                {{
                    "type": "step_check",
                    "page_index": 0,
                    "bounding_box": {{"x_min": 0.78, "y_min": 0.21, "x_max": 0.81, "y_max": 0.24}},
                    "text": "",
                    "color": "#00AA00"
                }},
                {{
                    "type": "step_cross",
                    "page_index": 0,
                    "bounding_box": {{"x_min": 0.78, "y_min": 0.27, "x_max": 0.81, "y_max": 0.30}},
                    "text": "",
                    "color": "#FF0000"
                }},
                {{
                    "type": "error_circle",
                    "page_index": 0,
                    "bounding_box": {{"x_min": 0.3, "y_min": 0.26, "x_max": 0.5, "y_max": 0.31}},
                    "text": "3+5≠9",
                    "color": "#FF0000"
                }},
                {{
                    "type": "comment",
                    "page_index": 0,
                    "bounding_box": {{"x_min": 0.55, "y_min": 0.27, "x_max": 0.78, "y_max": 0.30}},
                    "text": "应为 3+5=8",
                    "color": "#0066FF"
                }}
            ]
        }}
    ],
    "overall_feedback": "总体评价和建议",
    "page_summaries": [
        {{
            "page_index": 页码,
            "question_numbers": ["该页包含的题号"],
            "summary": "该页内容摘要"
        }}
    ]
}}
```

## 批注坐标要求
1. **每个步骤都要标注**：识别学生写的每一行/每一步，给出坐标
2. **区分 A/M mark**：
   - M mark 标注在方法步骤旁边，显示 "M1"（得分）或 "M0"（不得分）
   - A mark 标注在最终答案旁边，显示 "A1"（得分）或 "A0"（不得分）
3. **错误必须圈出**：用 error_circle 圈出具体错误位置，并用 comment 说明原因
4. **坐标必须准确**：仔细观察图片，给出精确的坐标位置
5. **颜色规范**：
   - 绿色 #00AA00：正确（M1, A1, ✓）
   - 红色 #FF0000：错误（M0, A0, ✗, 错误圈选）
   - 橙色 #FF8800：部分正确/总分
   - 蓝色 #0066FF：讲解/批注
6. **每道题至少输出**：
   - 一个 score 类型的批注（总分）
   - 每个步骤对应的 m_mark 或 a_mark
   - 每个步骤对应的 step_check 或 step_cross

## 重要提醒
- 必须批改全部 {questions_count} 道题
- 每道题的 score 必须等于各得分点 awarded 之和
- total_score 必须等于各题 score 之和
- student_answer 必须完整记录学生的原始作答，不要用"..."省略
- self_critique 必须诚实反映评分的不确定性
- 如果无法识别某道题的答案，confidence 和 self_critique_confidence 设为较低值并在 self_critique 中说明原因
- **批注坐标必须准确**：仔细观察图片，给出精确的坐标位置
- **每个步骤都要标注**：不要遗漏任何步骤的坐标
"""

        try:
            # 将图像转为 base64
            content = [{"type": "text", "text": prompt}]
            for idx, img_bytes in enumerate(images):
                if isinstance(img_bytes, bytes):
                    img_b64 = base64.b64encode(img_bytes).decode("utf-8")
                else:
                    img_b64 = img_bytes
                content.append(
                    {"type": "image_url", "image_url": f"data:image/jpeg;base64,{img_b64}"}
                )

            message = HumanMessage(content=content)

            # 流式调用 LLM
            full_response = ""
            thinking_content = ""

            async for chunk in self.llm.astream([message]):
                chunk_content = chunk.content
                if chunk_content:
                    if isinstance(chunk_content, str):
                        full_response += chunk_content
                        if stream_callback:
                            await stream_callback("output", chunk_content)
                    elif isinstance(chunk_content, list):
                        for part in chunk_content:
                            if isinstance(part, str):
                                full_response += part
                                if stream_callback:
                                    await stream_callback("output", part)
                            elif isinstance(part, dict):
                                if part.get("type") == "thinking":
                                    thinking_content += part.get("thinking", "")
                                    if stream_callback:
                                        await stream_callback("thinking", part.get("thinking", ""))
                                elif "text" in part:
                                    full_response += part["text"]
                                    if stream_callback:
                                        await stream_callback("output", part["text"])

            # 分离思考内容和输出内容
            output_text, extracted_thinking = split_thinking_content(full_response)
            if extracted_thinking:
                thinking_content = extracted_thinking

            # 解析 JSON 响应
            json_text = self._extract_json_from_text(output_text)

            # 尝试多种方式解析 JSON
            result = None
            try:
                result = self._load_json_with_repair(json_text)
            except json.JSONDecodeError:
                # 尝试提取 JSON 块
                json_block = self._extract_json_block(json_text)
                if json_block:
                    try:
                        result = self._load_json_with_repair(json_block)
                    except json.JSONDecodeError:
                        pass

            # 尝试解析分页输出格式
            if result is None:
                result = self._parse_page_break_output(output_text, student_key)

            if result is None:
                logger.error(f"[grade_student] JSON 解析失败: {json_text[:500]}")
                return {
                    "status": "failed",
                    "error": "无法解析批改结果",
                    "total_score": 0,
                    "max_score": total_score,
                    "confidence": 0,
                    "question_details": [],
                    "raw_response": output_text[:1000],
                }

            # 规范化结果
            result["status"] = "completed"
            result["student_key"] = student_key

            # 确保必要字段存在
            if "total_score" not in result:
                result["total_score"] = sum(
                    q.get("score", 0) for q in result.get("question_details", [])
                )
            if "max_score" not in result:
                result["max_score"] = total_score
            if "confidence" not in result:
                result["confidence"] = 0.8
            if "question_details" not in result:
                result["question_details"] = []

            # 规范化 question_details
            normalized_details = []
            for detail in result.get("question_details", []):
                normalized = self._normalize_question_detail(
                    detail, page_indices[0] if page_indices else 0
                )
                normalized_details.append(normalized)
            result["question_details"] = normalized_details

            logger.info(
                f"[grade_student] 批改完成: student={student_key}, "
                f"score={result.get('total_score')}/{result.get('max_score')}, "
                f"questions={len(result.get('question_details', []))}"
            )

            return result

        except Exception as e:
            logger.error(f"[grade_student] 批改失败: {e}", exc_info=True)
            return {
                "status": "failed",
                "error": str(e),
                "total_score": 0,
                "max_score": total_score,
                "confidence": 0,
                "question_details": [],
            }
