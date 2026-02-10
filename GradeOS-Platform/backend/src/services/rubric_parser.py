"""批改标准解析服务

解析批改标准 PDF，提取：
1. 每道题的题号和分值
2. 各个得分点及其分值
3. 另类解法（不计入总分）
4. 支持"题目+答案"混合格式的解析

支持 OpenRouter API 和直连 LLM API。
"""

import base64
import json
import logging
import os
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

# 使用 LLMReasoningClient（与批改流程一致）
from src.config.models import get_default_model
from src.services.llm_reasoning import LLMReasoningClient


logger = logging.getLogger(__name__)


def _escape_invalid_backslashes(text: str) -> str:
    """Escape invalid backslashes in JSON strings to improve parse resilience."""
    result = []
    i = 0
    hexdigits = "0123456789abcdefABCDEF"
    while i < len(text):
        ch = text[i]
        if ch != "\\":
            result.append(ch)
            i += 1
            continue
        if i + 1 >= len(text):
            result.append("\\\\")
            i += 1
            continue
        nxt = text[i + 1]
        if nxt in ('"', "\\", "/"):
            result.append("\\")
            result.append(nxt)
            i += 2
            continue
        if nxt == "u":
            seq = text[i + 2 : i + 6]
            if len(seq) == 4 and all(c in hexdigits for c in seq):
                result.append("\\u")
                result.append(seq)
                i += 6
                continue
            result.append("\\\\")
            i += 1
            continue
        result.append("\\\\")
        i += 1
    return "".join(result)


def _strip_control_chars(text: str) -> str:
    """Remove control characters that commonly break JSON parsing."""
    cleaned = []
    for ch in text:
        if ord(ch) < 0x20 and ch not in ("\t", "\n", "\r"):
            cleaned.append(" ")
        else:
            cleaned.append(ch)
    return "".join(cleaned)


def _extract_json_block(text: str) -> Optional[str]:
    """Extract the outermost JSON object from a text blob."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        return None
    return text[start : end + 1]


def _load_json_with_repair(text: str) -> Optional[Dict[str, Any]]:
    """Best-effort JSON loading with multiple repair passes."""
    if not text:
        return None
    candidates = [text]
    repaired = _strip_control_chars(_escape_invalid_backslashes(text))
    if repaired != text:
        candidates.append(repaired)
    block = _extract_json_block(repaired)
    if block and block not in candidates:
        candidates.append(block)

    for candidate in candidates:
        try:
            return json.loads(candidate, strict=False)
        except json.JSONDecodeError:
            continue
    return None


@dataclass
class ScoringPoint:
    """得分点"""

    description: str  # 得分点描述
    score: float  # 该得分点的分值
    is_required: bool = True  # 是否必须（部分分数可能是可选的）
    point_id: str = ""  # 得分点编号
    keywords: List[str] = field(default_factory=list)  # 关键词
    expected_value: str = ""  # 期望值


@dataclass
class AlternativeSolution:
    """另类解法"""

    description: str  # 解法描述
    scoring_criteria: str  # 得分条件
    note: str = ""  # 备注


@dataclass
class DeductionRule:
    """扣分规则"""

    description: str  # 典型错误/扣分条件描述
    deduction: float  # 扣分分值
    conditions: str = ""  # 扣分条件表达
    rule_id: str = ""  # 扣分规则编号


@dataclass
class QuestionConfession:
    """单题解析自白（极短）"""

    risk: str = ""  # 该题风险（≤10字）
    uncertainty: str = ""  # 不确定点（≤10字）

    def to_dict(self) -> Dict[str, Any]:
        return {"risk": self.risk, "uncertainty": self.uncertainty}


@dataclass
class RubricConfession:
    """评分标准解析自白（LLM 直接生成，极短）"""

    risks: List[str] = field(default_factory=list)  # 风险列表（每条≤15字）
    uncertainties: List[str] = field(default_factory=list)  # 不确定点列表
    blind_spots: List[str] = field(default_factory=list)  # 可能遗漏的内容
    needs_review: List[str] = field(default_factory=list)  # 建议人工复核的项
    confidence: float = 1.0  # 整体置信度 (0.0-1.0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "risks": self.risks,
            "uncertainties": self.uncertainties,
            "blindSpots": self.blind_spots,
            "needsReview": self.needs_review,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RubricConfession":
        return cls(
            risks=data.get("risks") or [],
            uncertainties=data.get("uncertainties") or [],
            blind_spots=data.get("blind_spots") or data.get("blindSpots") or [],
            needs_review=data.get("needs_review") or data.get("needsReview") or [],
            confidence=float(data.get("confidence", 1.0) or 1.0),
        )


@dataclass
class QuestionRubric:
    """单题评分标准"""

    question_id: str  # 题号
    max_score: float  # 满分
    question_text: str = ""  # 题目内容（如果有）
    standard_answer: str = ""  # 标准答案
    scoring_points: List[ScoringPoint] = field(default_factory=list)  # 得分点列表
    alternative_solutions: List[AlternativeSolution] = field(default_factory=list)  # 另类解法
    deduction_rules: List[DeductionRule] = field(default_factory=list)  # 扣分规则
    grading_notes: str = ""  # 批改注意事项
    # LLM 直接生成的自白（极短）
    confession: QuestionConfession = field(default_factory=QuestionConfession)
    # 解析自白字段（兼容旧版）
    parse_confidence: float = 1.0  # 解析置信度 (0.0-1.0)
    parse_uncertainties: List[str] = field(default_factory=list)  # 不确定性列表
    parse_quality_issues: List[str] = field(default_factory=list)  # 质量问题


@dataclass
class ParsedRubric:
    """解析后的完整评分标准"""

    total_questions: int  # 总题数
    total_score: float  # 总分
    questions: List[QuestionRubric]  # 各题评分标准
    general_notes: str = ""  # 通用批改说明
    rubric_format: str = "standard"  # 格式类型: standard/embedded
    # LLM 直接生成的自白（极短）
    confession: RubricConfession = field(default_factory=RubricConfession)
    # 解析自白字段（兼容旧版，由规则检查生成）
    overall_parse_confidence: float = 1.0  # 整体解析置信度 (0.0-1.0)
    parse_confession: Dict[str, Any] = field(default_factory=dict)  # 完整自白报告


class RubricParserService:
    """
    批改标准解析服务

    支持两种格式：
    1. 标准格式：独立的评分标准文档
    2. 嵌入格式：题目上直接标注答案的格式

    支持 OpenRouter API 和直连 LLM API。
    """

    def __init__(self, api_key: str = None, model_name: Optional[str] = None):
        """
        初始化服务

        Args:
            api_key: API 密钥（可选，默认从环境变量获取）
            model_name: 模型名称（可选，使用环境变量配置）
        """
        # 使用 LLMReasoningClient（与批改流程一致）
        self.api_key = api_key or os.getenv("LLM_API_KEY") or os.getenv("OPENROUTER_API_KEY", "")
        self.model_name = model_name or get_default_model()

        # 移除 token 限制：设置为 0 表示不限制输出长度
        # 这样可以确保 LLM 能完整输出所有题目的解析结果
        os.environ["GRADING_MAX_OUTPUT_TOKENS"] = "0"

        self.reasoning_client = LLMReasoningClient(api_key=self.api_key, model_name=self.model_name)

    async def parse_rubric(
        self, rubric_images: List[bytes], progress_callback=None, stream_callback=None
    ) -> ParsedRubric:
        """
        解析批改标准

        Args:
            rubric_images: 批改标准页面图像列表
            progress_callback: 进度回调 (batch_index, total_batches, status, message)
            stream_callback: 流式输出回调 (stream_type, chunk)

        Returns:
            ParsedRubric: 解析后的评分标准
        """
        logger.info(f"[rubric_parse] received {len(rubric_images)} pages")

        # Max images per LLM call for rubric parsing.
        MAX_PAGES_PER_BATCH = max(1, int(os.getenv("RUBRIC_PARSE_MAX_PAGES", "14")))
        all_questions = []
        general_notes = ""
        rubric_format = "standard"
        total_batches = 0

        for batch_start in range(0, len(rubric_images), MAX_PAGES_PER_BATCH):
            batch_end = min(batch_start + MAX_PAGES_PER_BATCH, len(rubric_images))
            batch_images = rubric_images[batch_start:batch_end]
            batch_num = batch_start // MAX_PAGES_PER_BATCH + 1
            total_batches = (len(rubric_images) + MAX_PAGES_PER_BATCH - 1) // MAX_PAGES_PER_BATCH

            logger.info(
                f"[rubric_parse] batch {batch_num}/{total_batches} pages {batch_start+1}-{batch_end}"
            )

            # 进度回调
            if progress_callback:
                try:
                    import asyncio

                    if asyncio.iscoroutinefunction(progress_callback):
                        await progress_callback(
                            batch_num - 1,
                            total_batches,
                            "parsing",
                            f"Parsing batch {batch_num}/{total_batches}",
                        )
                    else:
                        progress_callback(
                            batch_num - 1,
                            total_batches,
                            "parsing",
                            f"Parsing batch {batch_num}/{total_batches}",
                        )
                except Exception as e:
                    logger.debug(f"[rubric_parse] progress_callback error: {e}")

            batch_result = await self._parse_rubric_batch(
                batch_images,
                batch_num,
                total_batches,
                stream_callback,
            )

            all_questions.extend(batch_result.questions)
            if batch_result.general_notes:
                general_notes = batch_result.general_notes
            if batch_result.rubric_format != "standard":
                rubric_format = batch_result.rubric_format

        # 计算解析出的总分
        calculated_total = sum(q.max_score for q in all_questions)

        # 合并结果
        parsed = ParsedRubric(
            total_questions=len(all_questions),
            total_score=calculated_total,
            questions=all_questions,
            general_notes=general_notes,
            rubric_format=rubric_format,
        )

        if progress_callback and total_batches > 0:
            try:
                import asyncio

                if asyncio.iscoroutinefunction(progress_callback):
                    await progress_callback(
                        total_batches - 1, total_batches, "completed", "Parsing completed"
                    )
                else:
                    progress_callback(
                        total_batches - 1, total_batches, "completed", "Parsing completed"
                    )
            except Exception as e:
                logger.debug(f"[rubric_parse] progress_callback error: {e}")

        logger.info(
            f"批改标准解析完成: " f"{parsed.total_questions} 题, " f"总分 {parsed.total_score}"
        )

        return parsed

    async def _parse_rubric_batch(
        self,
        rubric_images: List[bytes],
        batch_num: int,
        total_batches: int,
        stream_callback=None,
    ) -> ParsedRubric:
        """解析单批评分标准页面"""
        batch_info = f"（第 {batch_num}/{total_batches} 批）" if total_batches > 1 else ""

        prompt_template = """你是一位专业的评分标准分析专家。请仔细分析这些评分标准/答案页面{batch_info}。

## ⚠️ 重要：严格按提供的评分标准构建 rubric

你必须**严格遵守**以下原则：
1. **不能合并得分点**：每个得分点必须单独列出，不能将多个得分点合并
2. **不能拆分得分点**：如果评分标准中某个得分点是完整的，不能拆分成多个
3. **默认每个得分点 1 分**：除非评分标准明确标注某个得分点值 2 分或以上，否则默认为 1 分
4. **严格按原文**：得分点的描述必须与原文一致，不能改写或简化

## 重要：你正在分析的是一份完整的评分标准文档
- 这份文档包含 **多道题目**（可能有 10-20 道或更多）
- 你必须 **逐页仔细阅读**，确保识别出 **每一道题目**
- **不要遗漏任何题目**，即使它们分布在不同的页面上

## 关键：题目识别规则
**只计数主题号，不要把子题当作独立题目！**

例如：
- ✅ 正确：题目 "7" 包含子题 7(1), 7(2), 7(3) → 这是 **1道题**，有3个得分点
- ❌ 错误：把 7(1), 7(2), 7(3) 当作 3道独立题目

**主题号识别**：
- 主题号格式：1、2、3... 或 一、二、三... 或 第1题、第2题...
- 子题格式：(1)、(2)、(3)... 或 ①、②、③... 或 a)、b)、c)...
- **子题应该作为主题的 scoring_points，而不是独立的 question**

## 得分点处理规则（非常重要）
1. **每个得分点默认 1 分**：
   - 如果评分标准写 "写出公式"，这是 1 个得分点，值 1 分
   - 如果评分标准写 "写出公式 (2分)"，这是 1 个得分点，值 2 分
   
2. **不能合并得分点**：
   - ❌ 错误：将 "写出公式" 和 "代入数值" 合并为 "写出公式并代入数值"
   - ✅ 正确：分别列出 "写出公式" (1分) 和 "代入数值" (1分)
   
3. **不能拆分得分点**：
   - ❌ 错误：将 "写出完整解题过程" 拆分为 "写出公式"、"代入数值"、"计算结果"
   - ✅ 正确：保持原样 "写出完整解题过程" (1分)
   
4. **严格按原文描述**：
   - 得分点的 description 必须与评分标准原文一致
   - 不能改写、简化或扩展

## 任务
1. **识别所有主题**：仔细查找每一道主题（不包括子题）
   - 只计数主题号（如 1, 2, 3...）
   - 子题作为该主题的得分点
2. **提取分值**：每道主题的满分分值（所有子题分值之和）
3. **提取得分点**：每道主题的评分要点和对应分值
   - 如果有子题，每个子题作为一个 scoring_point
   - point_id 格式：主题号.子题号（如 "7.1", "7.2", "7.3"）
   - **每个得分点默认 1 分，除非明确标注其他分值**
4. **提取标准答案**：如果有标准答案，完整提取
5. **提取扣分规则**：如果有扣分说明，提取扣分条件和分值

## 输出格式（仅返回 JSON，不要 markdown 代码块）
{{
  "rubric_format": "standard",
  "general_notes": "通用批改说明（如有）",
  "questions": [
    {{
      "question_id": "1",
      "max_score": 5,
      "question_text": "题目内容（如有）",
      "standard_answer": "标准答案（完整提取）",
      "scoring_points": [
        {{"point_id": "1.1", "description": "得分点描述（必须与原文一致）", "score": 1, "is_required": true}}
      ],
      "deduction_rules": [
        {{"rule_id": "1.d1", "description": "扣分条件", "deduction": 1, "conditions": "触发条件"}}
      ],
      "alternative_solutions": [
        {{"description": "另类解法描述", "scoring_criteria": "得分条件", "note": "备注"}}
      ],
      "grading_notes": "批改注意事项"
    }}
  ]
}}

## 示例
如果评分标准是：
```
7. (15分)
  (1) 计算结果 (5分)
  (2) 写出过程 (5分)  
  (3) 画出图形 (5分)
```

应该输出：
```json
{{
  "questions": [
    {{
      "question_id": "7",
      "max_score": 15,
      "scoring_points": [
        {{"point_id": "7.1", "description": "计算结果", "score": 5}},
        {{"point_id": "7.2", "description": "写出过程", "score": 5}},
        {{"point_id": "7.3", "description": "画出图形", "score": 5}}
      ]
    }}
  ]
}}
```
**注意：这是1道题，不是3道题！**

## 严格规则
- **必须返回有效的 JSON**（不要 markdown 代码块，不要 ```json）
- **只计数主题号**，不要把子题当作独立题目
- **逐页检查**：确保每一页的内容都被分析
- **子题处理**：如果一道大题包含多个子题（如 7(1), 7(2), 7(3)），将它们作为该题的 scoring_points，而不是独立的 questions
- **不能合并得分点**：每个得分点必须单独列出
- **不能拆分得分点**：保持评分标准原文的完整性
- **默认 1 分**：每个得分点默认 1 分，除非明确标注其他分值
- max_score 必须是数字类型
- 不要编造不存在的题目
"""
        prompt = prompt_template.format(batch_info=batch_info)

        try:
            # 使用 LLMReasoningClient 调用视觉模型（带重试）
            max_retries = 3
            retry_delay = 5  # 秒
            last_error = None

            for attempt in range(max_retries):
                try:
                    # 使用 LLMReasoningClient 的 analyze_with_vision 方法
                    response = await self.reasoning_client.analyze_with_vision(
                        images=rubric_images,
                        prompt=prompt,
                        stream_callback=stream_callback,
                    )
                    result_text = response.get("response", "")
                    break
                except Exception as e:
                    last_error = e
                    error_str = str(e)
                    if (
                        "503" in error_str
                        or "overloaded" in error_str.lower()
                        or "429" in error_str
                    ):
                        if attempt < max_retries - 1:
                            logger.warning(
                                f"API 过载，{retry_delay}秒后重试 ({attempt + 1}/{max_retries})"
                            )
                            import asyncio

                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2  # 指数退避
                            continue
                    raise
            else:
                raise last_error

            # 检查响应是否为空
            if not result_text or not result_text.strip():
                logger.warning(f"LLM 返回空响应，使用空结果")
                return ParsedRubric(
                    total_questions=0,
                    total_score=0,
                    questions=[],
                    general_notes="",
                    rubric_format="standard",
                )

            logger.debug(f"LLM 原始响应: {result_text[:500]}...")

            # 🔍 简要日志：只记录响应长度
            logger.info(f"[rubric_parse] LLM 响应长度: {len(result_text)} 字符")
            # 详细响应内容改为 DEBUG 级别
            if len(result_text) < 2000:
                logger.debug(f"[rubric_parse] LLM 完整响应: {result_text}")
            else:
                logger.debug(f"[rubric_parse] LLM 响应前 2000 字符: {result_text[:2000]}...")

            # 提取 JSON
            json_text = result_text
            if "```json" in result_text:
                json_start = result_text.find("```json") + 7
                json_end = result_text.find("```", json_start)
                if json_end > json_start:
                    json_text = result_text[json_start:json_end].strip()
            elif "```" in result_text:
                json_start = result_text.find("```") + 3
                json_end = result_text.find("```", json_start)
                if json_end > json_start:
                    json_text = result_text[json_start:json_end].strip()

            # 尝试找到 JSON 对象
            if not json_text.startswith("{"):
                # 尝试找到第一个 {
                brace_start = json_text.find("{")
                if brace_start >= 0:
                    json_text = json_text[brace_start:]

            if not json_text or not json_text.strip().startswith("{"):
                logger.warning(f"无法从响应中提取 JSON: {result_text[:200]}...")
                return ParsedRubric(
                    total_questions=0,
                    total_score=0,
                    questions=[],
                    general_notes="",
                    rubric_format="standard",
                )

            data = _load_json_with_repair(json_text)
            if data is None:
                logger.warning(
                    f"[rubric_parse] JSON decode failed after repair attempts. Raw: {json_text[:200]}..."
                )
                return ParsedRubric(
                    total_questions=0,
                    total_score=0,
                    questions=[],
                    general_notes="",
                    rubric_format="standard",
                )

            def ensure_string(value, default=""):
                """确保值是字符串类型"""
                if value is None:
                    return default
                if isinstance(value, list):
                    return "\n".join(str(item) for item in value)
                if not isinstance(value, str):
                    return str(value)
                return value

            def normalize_question_id(qid: str) -> str:
                """标准化题目编号, 将子题合并到主题"""
                if not qid:
                    return qid

                # 移除括号内容，如 "7(a)" -> "7", "15(1)" -> "15"
                import re

                main_id = re.sub(r"\([^)]*\)", "", str(qid)).strip()
                return main_id

            def _assign_point_ids(question_id: str, scoring_points: List[ScoringPoint]) -> None:
                seen = set()
                for idx, sp in enumerate(scoring_points):
                    point_id = sp.point_id or f"{question_id}.{idx + 1}"
                    while point_id in seen:
                        point_id = f"{question_id}.{len(seen) + 1}"
                    sp.point_id = point_id
                    seen.add(point_id)

            def _assign_rule_ids(question_id: str, deduction_rules: List[DeductionRule]) -> None:
                seen = set()
                for idx, rule in enumerate(deduction_rules):
                    rule_id = rule.rule_id or f"{question_id}.d{idx + 1}"
                    while rule_id in seen:
                        rule_id = f"{question_id}.d{len(seen) + 1}"
                    rule.rule_id = rule_id
                    seen.add(rule_id)

            def _dedupe_deduction_rules(
                deduction_rules: List[DeductionRule],
            ) -> List[DeductionRule]:
                unique = []
                seen = set()
                for rule in deduction_rules:
                    key = (rule.description, rule.deduction, rule.conditions)
                    if key in seen:
                        continue
                    seen.add(key)
                    unique.append(rule)
                return unique

            # 先收集所有题目，然后按主题编号合并
            raw_questions = []
            for q in data.get("questions", []):
                # 处理 scoring_points，可能是字典列表或字符串列表
                raw_scoring_points = q.get("scoring_points", [])
                scoring_points = []
                for sp in raw_scoring_points:
                    if isinstance(sp, dict):
                        scoring_points.append(
                            ScoringPoint(
                                description=ensure_string(sp.get("description", "")),
                                score=float(sp.get("score", 0)),
                                is_required=sp.get("is_required", True),
                                point_id=ensure_string(
                                    sp.get("point_id") or sp.get("pointId") or sp.get("id") or ""
                                ),
                                keywords=(
                                    [str(item) for item in (sp.get("keywords") or [])]
                                    if isinstance(sp.get("keywords"), list)
                                    else ([str(sp.get("keywords"))] if sp.get("keywords") else [])
                                ),
                                expected_value=ensure_string(
                                    sp.get("expected_value") or sp.get("expectedValue") or ""
                                ),
                            )
                        )
                    elif isinstance(sp, str):
                        # 如果是字符串，将其作为描述，分数设为 0
                        scoring_points.append(
                            ScoringPoint(
                                description=sp,
                                score=0,
                                is_required=True,
                                point_id="",
                                keywords=[],
                                expected_value="",
                            )
                        )

                # 处理 alternative_solutions，可能是字典列表或字符串列表
                raw_alt_solutions = q.get("alternative_solutions", [])
                alternative_solutions = []
                for alt in raw_alt_solutions:
                    if isinstance(alt, dict):
                        alternative_solutions.append(
                            AlternativeSolution(
                                description=ensure_string(alt.get("description", "")),
                                scoring_criteria=ensure_string(alt.get("scoring_criteria", "")),
                                note=ensure_string(alt.get("note", "")),
                            )
                        )
                    elif isinstance(alt, str):
                        # 如果是字符串，将其作为描述
                        alternative_solutions.append(
                            AlternativeSolution(description=alt, scoring_criteria="", note="")
                        )

                raw_deductions = q.get("deduction_rules") or q.get("deductionRules") or []
                deduction_rules = []
                for dr in raw_deductions:
                    if isinstance(dr, dict):
                        deduction_rules.append(
                            DeductionRule(
                                description=ensure_string(
                                    dr.get("description") or dr.get("rule") or ""
                                ),
                                deduction=float(dr.get("deduction", dr.get("score", 0)) or 0),
                                conditions=ensure_string(
                                    dr.get("conditions") or dr.get("when") or ""
                                ),
                                rule_id=ensure_string(
                                    dr.get("rule_id") or dr.get("ruleId") or dr.get("id") or ""
                                ),
                            )
                        )
                    elif isinstance(dr, str):
                        deduction_rules.append(
                            DeductionRule(
                                description=dr,
                                deduction=0.0,
                                conditions="",
                                rule_id="",
                            )
                        )

                # 提取 LLM 生成的题目级 confession
                q_confession_raw = q.get("confession") or {}
                q_confession = QuestionConfession(
                    risk=ensure_string(q_confession_raw.get("risk", "")),
                    uncertainty=ensure_string(q_confession_raw.get("uncertainty", "")),
                )

                raw_questions.append(
                    {
                        "original_id": str(q.get("question_id", "")),
                        "normalized_id": normalize_question_id(str(q.get("question_id", ""))),
                        "max_score": float(q.get("max_score", 0)),
                        "question_text": ensure_string(q.get("question_text", "")),
                        "standard_answer": ensure_string(q.get("standard_answer", "")),
                        "scoring_points": scoring_points,
                        "alternative_solutions": alternative_solutions,
                        "deduction_rules": deduction_rules,
                        "grading_notes": ensure_string(q.get("grading_notes", "")),
                        # LLM 直接生成的自白（极短）
                        "confession": q_confession,
                        # LLM 输出的置信度字段（兼容旧版）
                        "parse_confidence": float(q.get("parse_confidence", 1.0) or 1.0),
                        "parse_uncertainties": q.get("parse_uncertainties") or [],
                        "parse_quality_issues": q.get("parse_quality_issues") or [],
                    }
                )

            # 按标准化题目编号合并子题
            merged_questions = {}
            for q in raw_questions:
                norm_id = q["normalized_id"]
                if norm_id in merged_questions:
                    # 合并到现有题目
                    existing = merged_questions[norm_id]
                    existing["max_score"] += q["max_score"]
                    existing["scoring_points"].extend(q["scoring_points"])
                    existing["alternative_solutions"].extend(q["alternative_solutions"])
                    existing["deduction_rules"].extend(q["deduction_rules"])

                    # 合并文本内容
                    if q["question_text"] and q["question_text"] not in existing["question_text"]:
                        existing["question_text"] += f"\n子题: {q['question_text']}"
                    if (
                        q["standard_answer"]
                        and q["standard_answer"] not in existing["standard_answer"]
                    ):
                        existing["standard_answer"] += f"\n子题答案: {q['standard_answer']}"
                    if q["grading_notes"] and q["grading_notes"] not in existing["grading_notes"]:
                        existing["grading_notes"] += f"\n{q['grading_notes']}"

                    # 合并置信度字段（取最小置信度，合并不确定性和质量问题）
                    existing["parse_confidence"] = min(
                        existing.get("parse_confidence", 1.0), q.get("parse_confidence", 1.0)
                    )
                    existing["parse_uncertainties"].extend(q.get("parse_uncertainties", []))
                    existing["parse_quality_issues"].extend(q.get("parse_quality_issues", []))
                    # 合并 confession（合并风险和不确定点）
                    existing_conf = existing.get("confession", QuestionConfession())
                    new_conf = q.get("confession", QuestionConfession())
                    if new_conf.risk and not existing_conf.risk:
                        existing_conf.risk = new_conf.risk
                    elif new_conf.risk and existing_conf.risk:
                        existing_conf.risk = f"{existing_conf.risk}; {new_conf.risk}"
                    if new_conf.uncertainty and not existing_conf.uncertainty:
                        existing_conf.uncertainty = new_conf.uncertainty
                    elif new_conf.uncertainty and existing_conf.uncertainty:
                        existing_conf.uncertainty = f"{existing_conf.uncertainty}; {new_conf.uncertainty}"
                    existing["confession"] = existing_conf
                else:
                    # 新题目
                    merged_questions[norm_id] = q.copy()

            # 转换为 QuestionRubric 对象
            questions = []
            for norm_id, q in merged_questions.items():
                _assign_point_ids(norm_id, q["scoring_points"])
                _assign_rule_ids(norm_id, q["deduction_rules"])
                q["deduction_rules"] = _dedupe_deduction_rules(q["deduction_rules"])
                questions.append(
                    QuestionRubric(
                        question_id=norm_id,
                        max_score=q["max_score"],
                        question_text=q["question_text"],
                        standard_answer=q["standard_answer"],
                        scoring_points=q["scoring_points"],
                        alternative_solutions=q["alternative_solutions"],
                        deduction_rules=q["deduction_rules"],
                        grading_notes=q["grading_notes"],
                        # LLM 直接生成的自白（极短）
                        confession=q.get("confession", QuestionConfession()),
                        # LLM 解析置信度字段（兼容旧版）
                        parse_confidence=q.get("parse_confidence", 1.0),
                        parse_uncertainties=q.get("parse_uncertainties", []),
                        parse_quality_issues=q.get("parse_quality_issues", []),
                    )
                )

            # 提取 LLM 直接生成的整体 confession
            confession_raw = data.get("confession") or {}
            llm_confession = RubricConfession(
                risks=confession_raw.get("risks") or [],
                uncertainties=confession_raw.get("uncertainties") or [],
                blind_spots=confession_raw.get("blind_spots") or confession_raw.get("blindSpots") or [],
                needs_review=confession_raw.get("needs_review") or confession_raw.get("needsReview") or [],
                confidence=float(confession_raw.get("confidence", 1.0) or 1.0),
            )

            # 返回批次结果（包含 LLM 输出的整体置信度）
            llm_overall_confidence = llm_confession.confidence
            # 如果 LLM 没有输出整体置信度，从各题置信度计算
            if llm_overall_confidence >= 1.0 and questions:
                question_confidences = [
                    q.parse_confidence for q in questions if q.parse_confidence < 1.0
                ]
                if question_confidences:
                    llm_overall_confidence = sum(question_confidences) / len(question_confidences)

            batch_result = ParsedRubric(
                total_questions=len(questions),
                total_score=sum(q.max_score for q in questions),
                questions=questions,
                general_notes=ensure_string(data.get("general_notes", "")),
                rubric_format=ensure_string(data.get("rubric_format", "standard")),
                # LLM 直接生成的自白
                confession=llm_confession,
                # LLM 解析置信度
                overall_parse_confidence=llm_overall_confidence,
            )

            logger.info(
                f"批次解析完成: " f"{len(questions)} 题, " f"分值 {batch_result.total_score}"
            )

            return batch_result

        except Exception as e:
            logger.error(f"批改标准解析失败: {str(e)}")
            raise

    def format_rubric_context(self, rubric: ParsedRubric) -> str:
        """
        将解析后的评分标准格式化为批改 Agent 可用的上下文
        """

        def ensure_str(value):
            """确保值是字符串"""
            if value is None:
                return ""
            if isinstance(value, list):
                return " ".join(str(item) for item in value)
            return str(value)

        lines = [
            "=" * 60,
            "评分标准（请严格遵循）",
            "=" * 60,
            f"总题数: {rubric.total_questions}",
            f"总分: {rubric.total_score}",
            f"格式: {ensure_str(rubric.rubric_format)}",
            "",
        ]

        if rubric.general_notes:
            lines.append(f"通用说明: {ensure_str(rubric.general_notes)}")
            lines.append("")

        for q in rubric.questions:
            lines.append("-" * 40)
            lines.append(f"【第 {ensure_str(q.question_id)} 题】满分: {q.max_score} 分")

            question_text = ensure_str(q.question_text)
            if question_text:
                text_preview = question_text[:100] if len(question_text) > 100 else question_text
                lines.append(f"题目: {text_preview}...")

            standard_answer = ensure_str(q.standard_answer)
            if standard_answer:
                answer_preview = (
                    standard_answer[:200] if len(standard_answer) > 200 else standard_answer
                )
                lines.append(f"标准答案: {answer_preview}...")

            lines.append("得分点:")
            for i, sp in enumerate(q.scoring_points, 1):
                required = "必须" if sp.is_required else "可选"
                description = ensure_str(sp.description)
                point_id = ensure_str(sp.point_id) or f"{ensure_str(q.question_id)}.{i}"
                lines.append(f"  [{point_id}] [{sp.score}分/{required}] {description}")

            if q.deduction_rules:
                lines.append("扣分规则（备注）")
                for idx, dr in enumerate(q.deduction_rules, 1):
                    rule_id = ensure_str(dr.rule_id) or f"{ensure_str(q.question_id)}.d{idx}"
                    deduction = dr.deduction
                    conditions = ensure_str(dr.conditions)
                    condition_text = f"，条件: {conditions}" if conditions else ""
                    lines.append(
                        f"  [{rule_id}] -{deduction}分 {ensure_str(dr.description)}{condition_text}"
                    )

            if q.alternative_solutions:
                lines.append("另类解法（同样可得分）:")
                for alt in q.alternative_solutions:
                    lines.append(f"  - {ensure_str(alt.description)}")
                    lines.append(f"    得分条件: {ensure_str(alt.scoring_criteria)}")

            grading_notes = ensure_str(q.grading_notes)
            if grading_notes:
                lines.append(f"批改注意: {grading_notes}")

            lines.append("")

        return "\n".join(lines)

    def _generate_parse_confession(
        self,
        rubric: ParsedRubric,
        expected_question_count: Optional[int] = None,
        expected_total_score: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        生成评分标准解析的自白报告

        执行多维度质量检查:
        - 题目数量合理性检查
        - 分值一致性检查
        - 得分点完整性检查
        - 关键信息缺失检查

        Args:
            rubric: 解析后的评分标准
            expected_question_count: 期望的题目数量(如果已知)
            expected_total_score: 期望的总分(如果已知)

        Returns:
            自白报告字典
        """
        from datetime import datetime

        issues = []
        uncertainties = []
        quality_checks = []
        overall_status = "ok"

        # 1. 题目数量合理性检查
        if rubric.total_questions == 0:
            issues.append(
                {"type": "no_questions", "message": "未识别到任何题目", "severity": "high"}
            )
            overall_status = "error"
            quality_checks.append(
                {"check": "题目数量检查", "passed": False, "detail": "未识别到任何题目"}
            )
        elif rubric.total_questions < 3:
            issues.append(
                {
                    "type": "few_questions",
                    "message": f"题目数量较少（{rubric.total_questions}题），可能存在遗漏",
                    "severity": "medium",
                }
            )
            if overall_status == "ok":
                overall_status = "caution"
            quality_checks.append(
                {
                    "check": "题目数量检查",
                    "passed": False,
                    "detail": f"仅识别到 {rubric.total_questions} 题",
                }
            )
        else:
            quality_checks.append(
                {
                    "check": "题目数量检查",
                    "passed": True,
                    "detail": f"识别到 {rubric.total_questions} 题",
                }
            )

        # 如果有期望题目数量，进行比对
        if expected_question_count and rubric.total_questions != expected_question_count:
            issues.append(
                {
                    "type": "question_count_mismatch",
                    "message": f"识别到 {rubric.total_questions} 题，但期望 {expected_question_count} 题",
                    "severity": "high",
                }
            )
            overall_status = "error"

        # 2. 分值一致性检查
        calculated_total = sum(q.max_score for q in rubric.questions)
        if abs(calculated_total - rubric.total_score) > 0.1:
            issues.append(
                {
                    "type": "score_mismatch",
                    "message": f"题目分值之和（{calculated_total}）与总分（{rubric.total_score}）不一致",
                    "severity": "medium",
                }
            )
            if overall_status == "ok":
                overall_status = "caution"
            quality_checks.append(
                {
                    "check": "分值一致性检查",
                    "passed": False,
                    "detail": f"分值差异 {abs(calculated_total - rubric.total_score):.1f} 分",
                }
            )
        else:
            quality_checks.append({"check": "分值一致性检查", "passed": True, "detail": "分值一致"})

        # 如果有期望总分，进行比对
        if expected_total_score and abs(rubric.total_score - expected_total_score) > 0.1:
            issues.append(
                {
                    "type": "total_score_mismatch",
                    "message": f"总分为 {rubric.total_score}，但期望 {expected_total_score}",
                    "severity": "high",
                }
            )
            overall_status = "error"

        # 3. 题目级别检查
        questions_with_issues = []
        for q in rubric.questions:
            q_issues = []

            # 检查得分点
            if not q.scoring_points:
                q_issues.append("缺少得分点")
                issues.append(
                    {
                        "type": "missing_scoring_points",
                        "message": f"题目 {q.question_id} 缺少得分点",
                        "questionId": q.question_id,
                        "severity": "high",
                    }
                )

            # 检查分值合理性
            if q.max_score <= 0:
                q_issues.append("分值异常")
                issues.append(
                    {
                        "type": "invalid_score",
                        "message": f"题目 {q.question_id} 分值异常（{q.max_score}）",
                        "questionId": q.question_id,
                        "severity": "high",
                    }
                )
            elif q.max_score > 30:
                uncertainties.append(f"题目 {q.question_id} 分值较高（{q.max_score}分），请确认")

            # 检查得分点分值之和
            if q.scoring_points:
                sp_total = sum(sp.score for sp in q.scoring_points)
                if abs(sp_total - q.max_score) > 0.1:
                    q_issues.append("得分点分值之和与题目满分不一致")
                    issues.append(
                        {
                            "type": "scoring_points_mismatch",
                            "message": f"题目 {q.question_id} 得分点分值之和（{sp_total}）与满分（{q.max_score}）不一致",
                            "questionId": q.question_id,
                            "severity": "medium",
                        }
                    )

            # 检查标准答案
            if not q.standard_answer:
                uncertainties.append(f"题目 {q.question_id} 缺少标准答案")

            # 检查题目置信度（如果有）
            if q.parse_confidence < 0.7:
                q_issues.append(f"解析置信度较低（{q.parse_confidence:.2f}）")
                issues.append(
                    {
                        "type": "low_confidence",
                        "message": f"题目 {q.question_id} 解析置信度较低（{q.parse_confidence:.2f}）",
                        "questionId": q.question_id,
                        "severity": "medium",
                    }
                )

            # 收集题目不确定性
            if q.parse_uncertainties:
                for unc in q.parse_uncertainties:
                    uncertainties.append(f"题目 {q.question_id}: {unc}")

            if q_issues:
                questions_with_issues.append(q.question_id)

        # 4. 得分点完整性检查
        questions_without_points = [q.question_id for q in rubric.questions if not q.scoring_points]
        if questions_without_points:
            quality_checks.append(
                {
                    "check": "得分点完整性检查",
                    "passed": False,
                    "detail": f"{len(questions_without_points)} 题缺少得分点: {', '.join(questions_without_points)}",
                }
            )
            if overall_status == "ok":
                overall_status = "caution"
        else:
            quality_checks.append(
                {"check": "得分点完整性检查", "passed": True, "detail": "所有题目都有得分点"}
            )

        # 5. 标准答案检查
        questions_without_answer = [
            q.question_id for q in rubric.questions if not q.standard_answer
        ]
        if questions_without_answer:
            quality_checks.append(
                {
                    "check": "标准答案完整性检查",
                    "passed": False,
                    "detail": f"{len(questions_without_answer)} 题缺少标准答案",
                }
            )
        else:
            quality_checks.append(
                {"check": "标准答案完整性检查", "passed": True, "detail": "所有题目都有标准答案"}
            )

        # 6. 计算整体置信度
        if rubric.overall_parse_confidence < 1.0:
            # 使用 LLM 提供的置信度
            overall_confidence = rubric.overall_parse_confidence
        else:
            # 基于质量检查计算置信度
            confidence_factors = []

            # 题目数量因素
            if rubric.total_questions == 0:
                confidence_factors.append(0.0)
            elif rubric.total_questions < 3:
                confidence_factors.append(0.6)
            else:
                confidence_factors.append(0.9)

            # 分值一致性因素
            if abs(calculated_total - rubric.total_score) > 0.1:
                confidence_factors.append(0.7)
            else:
                confidence_factors.append(1.0)

            # 得分点完整性因素
            if questions_without_points:
                confidence_factors.append(0.5)
            else:
                confidence_factors.append(0.95)

            # 题目置信度平均值
            if rubric.questions:
                avg_q_confidence = sum(q.parse_confidence for q in rubric.questions) / len(
                    rubric.questions
                )
                confidence_factors.append(avg_q_confidence)

            overall_confidence = (
                sum(confidence_factors) / len(confidence_factors) if confidence_factors else 0.5
            )

        # 7. 生成摘要
        if overall_status == "ok":
            summary = (
                f"成功解析 {rubric.total_questions} 题，总分 {rubric.total_score}，整体质量良好"
            )
        elif overall_status == "caution":
            summary = f"解析 {rubric.total_questions} 题，总分 {rubric.total_score}，存在 {len(issues)} 个问题需要注意"
        else:
            summary = f"解析存在严重问题，识别到 {rubric.total_questions} 题，有 {len([i for i in issues if i['severity'] == 'high'])} 个高严重性问题"

        # 8. 添加整体不确定性
        if rubric.parse_confession.get("parse_uncertainties"):
            uncertainties.extend(rubric.parse_confession["parse_uncertainties"])

        return {
            "overallStatus": overall_status,
            "overallConfidence": round(overall_confidence, 3),
            "summary": summary,
            "issues": issues,
            "uncertainties": uncertainties,
            "qualityChecks": quality_checks,
            "questionsWithIssues": questions_with_issues,
            "generatedAt": datetime.now().isoformat(),
            "parseMethod": "llm_vision",
        }
