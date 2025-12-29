"""批改标准解析服务

解析批改标准 PDF，提取：
1. 每道题的题号和分值
2. 各个得分点及其分值
3. 另类解法（不计入总分）
4. 支持"题目+答案"混合格式的解析
"""

import base64
import json
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from src.config.models import get_default_model


logger = logging.getLogger(__name__)


@dataclass
class ScoringPoint:
    """得分点"""
    description: str          # 得分点描述
    score: float              # 该得分点的分值
    is_required: bool = True  # 是否必须（部分分数可能是可选的）


@dataclass
class AlternativeSolution:
    """另类解法"""
    description: str          # 解法描述
    scoring_criteria: str     # 得分条件
    note: str = ""            # 备注


@dataclass
class QuestionRubric:
    """单题评分标准"""
    question_id: str                              # 题号
    max_score: float                              # 满分
    question_text: str = ""                       # 题目内容（如果有）
    standard_answer: str = ""                     # 标准答案
    scoring_points: List[ScoringPoint] = field(default_factory=list)  # 得分点列表
    alternative_solutions: List[AlternativeSolution] = field(default_factory=list)  # 另类解法
    grading_notes: str = ""                       # 批改注意事项


@dataclass
class ParsedRubric:
    """解析后的完整评分标准"""
    total_questions: int                          # 总题数
    total_score: float                            # 总分
    questions: List[QuestionRubric]               # 各题评分标准
    general_notes: str = ""                       # 通用批改说明
    rubric_format: str = "standard"               # 格式类型: standard/embedded


class RubricParserService:
    """
    批改标准解析服务
    
    支持两种格式：
    1. 标准格式：独立的评分标准文档
    2. 嵌入格式：题目上直接标注答案的格式
    """
    
    def __init__(self, api_key: str, model_name: Optional[str] = None):
        if model_name is None:
            model_name = get_default_model()
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=0.1
        )
    
    async def parse_rubric(
        self,
        rubric_images: List[bytes],
        expected_total_score: float = 105
    ) -> ParsedRubric:
        """
        解析批改标准
        
        Args:
            rubric_images: 批改标准页面图像列表
            expected_total_score: 预期总分（用于验证）
            
        Returns:
            ParsedRubric: 解析后的评分标准
        """
        logger.info(f"开始解析批改标准，共 {len(rubric_images)} 页")
        
        # 分批处理：每批最多 4 页，避免请求过大
        MAX_PAGES_PER_BATCH = 4
        all_questions = []
        general_notes = ""
        rubric_format = "standard"
        
        for batch_start in range(0, len(rubric_images), MAX_PAGES_PER_BATCH):
            batch_end = min(batch_start + MAX_PAGES_PER_BATCH, len(rubric_images))
            batch_images = rubric_images[batch_start:batch_end]
            batch_num = batch_start // MAX_PAGES_PER_BATCH + 1
            total_batches = (len(rubric_images) + MAX_PAGES_PER_BATCH - 1) // MAX_PAGES_PER_BATCH
            
            logger.info(f"解析第 {batch_num}/{total_batches} 批（第 {batch_start+1}-{batch_end} 页）")
            
            batch_result = await self._parse_rubric_batch(
                batch_images, 
                expected_total_score,
                batch_num,
                total_batches
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
            rubric_format=rubric_format
        )
        
        # 验证总分
        if abs(calculated_total - expected_total_score) > 1:
            logger.warning(
                f"总分不匹配: 预期 {expected_total_score}, "
                f"实际解析出 {calculated_total}，请检查评分标准解析是否正确"
            )
        
        logger.info(
            f"批改标准解析完成: "
            f"{parsed.total_questions} 题, "
            f"总分 {parsed.total_score}"
        )
        
        return parsed
    
    async def _parse_rubric_batch(
        self,
        rubric_images: List[bytes],
        expected_total_score: float,
        batch_num: int,
        total_batches: int
    ) -> ParsedRubric:
        """解析单批评分标准页面"""
        # 将图像转为 base64
        images_b64 = [base64.b64encode(img).decode('utf-8') for img in rubric_images]
        
        batch_info = f"（第 {batch_num}/{total_batches} 批）" if total_batches > 1 else ""
        
        prompt = f"""你是一位专业的阅卷标准分析专家。请仔细分析这些批改标准/答案页面{batch_info}。

## 任务
1. 识别这些页面中的所有题目
2. 提取每道题的分值和得分点
3. 识别另类解法（如果有）

## 分析要求
- 每道题必须明确分值
- 得分点要具体，说明给分条件
- 另类解法单独列出，不计入主要得分点
- 只提取这些页面中出现的题目
- 注意区分主题和子题（如 7(a)、7(b) 应合并为第7题）

## 输出格式（JSON）
```json
{{
    "rubric_format": "standard 或 embedded",
    "general_notes": "通用批改说明（如果有）",
    "questions": [
        {{
            "question_id": "1",
            "max_score": 5,
            "question_text": "题目内容（简短描述）",
            "standard_answer": "标准答案（完整）",
            "scoring_points": [
                {{"description": "正确列出方程", "score": 2, "is_required": true}},
                {{"description": "正确求解", "score": 3, "is_required": true}}
            ],
            "alternative_solutions": [],
            "grading_notes": ""
        }}
    ]
}}
```

## 重要提醒
- 只提取当前页面中的题目，不要猜测其他页面的内容
- 另类解法的分值不要重复计算到 max_score 中
- 标准答案要尽可能完整，包括解题步骤
- 得分点要明确具体的给分条件和分值"""

        # 构建消息
        content = [{"type": "text", "text": prompt}]
        for img_b64 in images_b64:
            content.append({
                "type": "image_url",
                "image_url": f"data:image/png;base64,{img_b64}"
            })
        
        message = HumanMessage(content=content)
        
        try:
            # 添加重试机制处理 503 错误
            max_retries = 3
            retry_delay = 5  # 秒
            last_error = None
            
            for attempt in range(max_retries):
                try:
                    response = await self.llm.ainvoke([message])
                    break
                except Exception as e:
                    last_error = e
                    error_str = str(e)
                    if "503" in error_str or "overloaded" in error_str.lower():
                        if attempt < max_retries - 1:
                            logger.warning(f"Gemini API 过载，{retry_delay}秒后重试 ({attempt + 1}/{max_retries})")
                            import asyncio
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2  # 指数退避
                            continue
                    raise
            else:
                raise last_error
            
            # 处理 response.content 可能是列表的情况
            result_text = response.content
            if isinstance(result_text, list):
                # 多模态响应可能返回列表，提取文本部分
                text_parts = []
                for item in result_text:
                    if isinstance(item, str):
                        text_parts.append(item)
                    elif isinstance(item, dict) and "text" in item:
                        text_parts.append(item["text"])
                result_text = "".join(text_parts)
            elif not isinstance(result_text, str):
                result_text = str(result_text) if result_text else ""
            
            # 检查响应是否为空
            if not result_text or not result_text.strip():
                logger.warning(f"Gemini 返回空响应，使用空结果")
                return ParsedRubric(
                    total_questions=0,
                    total_score=0,
                    questions=[],
                    general_notes="",
                    rubric_format="standard"
                )
            
            logger.debug(f"Gemini 原始响应: {result_text[:500]}...")
            
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
                    rubric_format="standard"
                )
            
            try:
                data = json.loads(json_text)
            except json.JSONDecodeError as e:
                logger.warning(f"JSON 解析失败: {e}, 原文: {json_text[:200]}...")
                return ParsedRubric(
                    total_questions=0,
                    total_score=0,
                    questions=[],
                    general_notes="",
                    rubric_format="standard"
                )
            
            # 解析结果
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
                """标准化题目编号，将子题合并到主题"""
                if not qid:
                    return qid
                
                # 移除括号内容，如 "7(a)" -> "7", "15(1)" -> "15"
                import re
                main_id = re.sub(r'\([^)]*\)', '', str(qid)).strip()
                return main_id
            
            # 先收集所有题目，然后按主题编号合并
            raw_questions = []
            for q in data.get("questions", []):
                # 处理 scoring_points，可能是字典列表或字符串列表
                raw_scoring_points = q.get("scoring_points", [])
                scoring_points = []
                for sp in raw_scoring_points:
                    if isinstance(sp, dict):
                        scoring_points.append(ScoringPoint(
                            description=ensure_string(sp.get("description", "")),
                            score=float(sp.get("score", 0)),
                            is_required=sp.get("is_required", True)
                        ))
                    elif isinstance(sp, str):
                        # 如果是字符串，将其作为描述，分数设为 0
                        scoring_points.append(ScoringPoint(
                            description=sp,
                            score=0,
                            is_required=True
                        ))
                
                # 处理 alternative_solutions，可能是字典列表或字符串列表
                raw_alt_solutions = q.get("alternative_solutions", [])
                alternative_solutions = []
                for alt in raw_alt_solutions:
                    if isinstance(alt, dict):
                        alternative_solutions.append(AlternativeSolution(
                            description=ensure_string(alt.get("description", "")),
                            scoring_criteria=ensure_string(alt.get("scoring_criteria", "")),
                            note=ensure_string(alt.get("note", ""))
                        ))
                    elif isinstance(alt, str):
                        # 如果是字符串，将其作为描述
                        alternative_solutions.append(AlternativeSolution(
                            description=alt,
                            scoring_criteria="",
                            note=""
                        ))
                
                raw_questions.append({
                    "original_id": str(q.get("question_id", "")),
                    "normalized_id": normalize_question_id(str(q.get("question_id", ""))),
                    "max_score": float(q.get("max_score", 0)),
                    "question_text": ensure_string(q.get("question_text", "")),
                    "standard_answer": ensure_string(q.get("standard_answer", "")),
                    "scoring_points": scoring_points,
                    "alternative_solutions": alternative_solutions,
                    "grading_notes": ensure_string(q.get("grading_notes", ""))
                })
            
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
                    
                    # 合并文本内容
                    if q["question_text"] and q["question_text"] not in existing["question_text"]:
                        existing["question_text"] += f"\n子题: {q['question_text']}"
                    if q["standard_answer"] and q["standard_answer"] not in existing["standard_answer"]:
                        existing["standard_answer"] += f"\n子题答案: {q['standard_answer']}"
                    if q["grading_notes"] and q["grading_notes"] not in existing["grading_notes"]:
                        existing["grading_notes"] += f"\n{q['grading_notes']}"
                else:
                    # 新题目
                    merged_questions[norm_id] = q.copy()
            
            # 转换为 QuestionRubric 对象
            questions = []
            for norm_id, q in merged_questions.items():
                questions.append(QuestionRubric(
                    question_id=norm_id,
                    max_score=q["max_score"],
                    question_text=q["question_text"],
                    standard_answer=q["standard_answer"],
                    scoring_points=q["scoring_points"],
                    alternative_solutions=q["alternative_solutions"],
                    grading_notes=q["grading_notes"]
                ))
            
            # 返回批次结果
            batch_result = ParsedRubric(
                total_questions=len(questions),
                total_score=sum(q.max_score for q in questions),
                questions=questions,
                general_notes=ensure_string(data.get("general_notes", "")),
                rubric_format=ensure_string(data.get("rubric_format", "standard"))
            )
            
            logger.info(
                f"批次解析完成: "
                f"{len(questions)} 题, "
                f"分值 {batch_result.total_score}"
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
            ""
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
                answer_preview = standard_answer[:200] if len(standard_answer) > 200 else standard_answer
                lines.append(f"标准答案: {answer_preview}...")
            
            lines.append("得分点:")
            for i, sp in enumerate(q.scoring_points, 1):
                required = "必须" if sp.is_required else "可选"
                description = ensure_str(sp.description)
                lines.append(f"  {i}. [{sp.score}分/{required}] {description}")
            
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
