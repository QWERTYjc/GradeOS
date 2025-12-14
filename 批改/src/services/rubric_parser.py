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
    
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
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
        
        # 将图像转为 base64
        images_b64 = [base64.b64encode(img).decode('utf-8') for img in rubric_images]
        
        prompt = f"""你是一位专业的阅卷标准分析专家。请仔细分析这份批改标准/答案文档。

## 任务
1. 识别所有题目（预期总分为 {expected_total_score} 分）
2. 提取每道题的分值和得分点
3. 识别另类解法（如果有）
4. 判断文档格式（独立答案 vs 题目上标注答案）

## 分析要求
- 每道题必须明确分值
- 得分点要具体，说明给分条件
- 另类解法单独列出，不计入主要得分点
- 如果是"题目+答案"混合格式，也要能识别

## 输出格式（JSON）
```json
{{
    "rubric_format": "standard 或 embedded",
    "total_questions": 19,
    "total_score": {expected_total_score},
    "general_notes": "通用批改说明",
    "questions": [
        {{
            "question_id": "1",
            "max_score": 5,
            "question_text": "题目内容（如果可见）",
            "standard_answer": "标准答案",
            "scoring_points": [
                {{
                    "description": "正确列出方程",
                    "score": 2,
                    "is_required": true
                }},
                {{
                    "description": "正确求解",
                    "score": 3,
                    "is_required": true
                }}
            ],
            "alternative_solutions": [
                {{
                    "description": "使用图解法",
                    "scoring_criteria": "图形正确且标注清晰可得满分",
                    "note": "此为另类解法"
                }}
            ],
            "grading_notes": "注意检查单位"
        }}
    ]
}}
```

## 重要提醒
- 确保所有题目的分值之和等于 {expected_total_score}
- 另类解法的分值不要重复计算到 max_score 中
- 如果某题有多个小题（如 a, b, c），分别列出得分点"""

        # 构建消息
        content = [{"type": "text", "text": prompt}]
        for img_b64 in images_b64:
            content.append({
                "type": "image_url",
                "image_url": f"data:image/png;base64,{img_b64}"
            })
        
        message = HumanMessage(content=content)
        
        try:
            response = await self.llm.ainvoke([message])
            result_text = response.content
            
            # 提取 JSON
            if "```json" in result_text:
                json_start = result_text.find("```json") + 7
                json_end = result_text.find("```", json_start)
                result_text = result_text[json_start:json_end].strip()
            elif "```" in result_text:
                json_start = result_text.find("```") + 3
                json_end = result_text.find("```", json_start)
                result_text = result_text[json_start:json_end].strip()
            
            data = json.loads(result_text)
            
            # 解析结果
            questions = []
            for q in data.get("questions", []):
                scoring_points = [
                    ScoringPoint(
                        description=sp.get("description", ""),
                        score=float(sp.get("score", 0)),
                        is_required=sp.get("is_required", True)
                    )
                    for sp in q.get("scoring_points", [])
                ]
                
                alternative_solutions = [
                    AlternativeSolution(
                        description=alt.get("description", ""),
                        scoring_criteria=alt.get("scoring_criteria", ""),
                        note=alt.get("note", "")
                    )
                    for alt in q.get("alternative_solutions", [])
                ]
                
                questions.append(QuestionRubric(
                    question_id=str(q.get("question_id", "")),
                    max_score=float(q.get("max_score", 0)),
                    question_text=q.get("question_text", ""),
                    standard_answer=q.get("standard_answer", ""),
                    scoring_points=scoring_points,
                    alternative_solutions=alternative_solutions,
                    grading_notes=q.get("grading_notes", "")
                ))
            
            parsed = ParsedRubric(
                total_questions=int(data.get("total_questions", len(questions))),
                total_score=float(data.get("total_score", expected_total_score)),
                questions=questions,
                general_notes=data.get("general_notes", ""),
                rubric_format=data.get("rubric_format", "standard")
            )
            
            # 验证总分
            actual_total = sum(q.max_score for q in questions)
            if abs(actual_total - expected_total_score) > 1:
                logger.warning(
                    f"总分不匹配: 预期 {expected_total_score}, "
                    f"实际 {actual_total}"
                )
            
            logger.info(
                f"批改标准解析完成: "
                f"{parsed.total_questions} 题, "
                f"总分 {parsed.total_score}"
            )
            
            return parsed
            
        except Exception as e:
            logger.error(f"批改标准解析失败: {str(e)}")
            raise
    
    def format_rubric_context(self, rubric: ParsedRubric) -> str:
        """
        将解析后的评分标准格式化为批改 Agent 可用的上下文
        """
        lines = [
            "=" * 60,
            "评分标准（请严格遵循）",
            "=" * 60,
            f"总题数: {rubric.total_questions}",
            f"总分: {rubric.total_score}",
            f"格式: {rubric.rubric_format}",
            ""
        ]
        
        if rubric.general_notes:
            lines.append(f"通用说明: {rubric.general_notes}")
            lines.append("")
        
        for q in rubric.questions:
            lines.append("-" * 40)
            lines.append(f"【第 {q.question_id} 题】满分: {q.max_score} 分")
            
            if q.question_text and isinstance(q.question_text, str):
                text_preview = q.question_text[:100] if len(q.question_text) > 100 else q.question_text
                lines.append(f"题目: {text_preview}...")
            
            if q.standard_answer and isinstance(q.standard_answer, str):
                answer_preview = q.standard_answer[:200] if len(q.standard_answer) > 200 else q.standard_answer
                lines.append(f"标准答案: {answer_preview}...")
            
            lines.append("得分点:")
            for i, sp in enumerate(q.scoring_points, 1):
                required = "必须" if sp.is_required else "可选"
                lines.append(f"  {i}. [{sp.score}分/{required}] {sp.description}")
            
            if q.alternative_solutions:
                lines.append("另类解法（同样可得分）:")
                for alt in q.alternative_solutions:
                    lines.append(f"  - {alt.description}")
                    lines.append(f"    得分条件: {alt.scoring_criteria}")
            
            if q.grading_notes:
                lines.append(f"批改注意: {q.grading_notes}")
            
            lines.append("")
        
        return "\n".join(lines)
