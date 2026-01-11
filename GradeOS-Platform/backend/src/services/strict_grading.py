"""严格批改服务

基于解析后的评分标准进行严格批改：
1. 逐题对照得分点评分
2. 识别另类解法并正确给分
3. 输出详细的得分点解释
"""

import base64
import json
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from src.services.rubric_parser import ParsedRubric, QuestionRubric
from src.config.models import get_default_model
from src.utils.llm_thinking import get_thinking_kwargs


logger = logging.getLogger(__name__)


@dataclass
class ScoringPointResult:
    """得分点评分结果"""
    description: str          # 得分点描述
    max_score: float          # 该得分点满分
    awarded_score: float      # 实际得分
    is_correct: bool          # 是否正确
    explanation: str          # 评分解释


@dataclass
class QuestionGradingResult:
    """单题批改结果"""
    question_id: str
    max_score: float
    awarded_score: float
    scoring_point_results: List[ScoringPointResult]
    used_alternative_solution: bool = False
    alternative_solution_note: str = ""
    overall_feedback: str = ""
    confidence: float = 0.9


@dataclass
class StudentGradingResult:
    """学生批改结果"""
    student_id: str
    student_name: str
    total_score: float
    max_total_score: float
    question_results: List[QuestionGradingResult]
    page_range: tuple = (0, 0)


class StrictGradingService:
    """
    严格批改服务
    
    特点：
    1. 严格遵循解析后的评分标准
    2. 逐个得分点评分
    3. 识别并正确处理另类解法
    4. 输出详细的评分解释
    """
    
    def __init__(self, api_key: str, model_name: Optional[str] = None):
        if model_name is None:
            model_name = get_default_model()
        thinking_kwargs = get_thinking_kwargs(model_name, enable_thinking=True)
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=0.1,
            streaming=True,  # enable streaming
            **thinking_kwargs,
        )
    
    async def grade_student(
        self,
        student_pages: List[bytes],
        rubric: ParsedRubric,
        rubric_context: str,
        student_name: str = "学生"
    ) -> StudentGradingResult:
        """
        批改单个学生的作答
        
        Args:
            student_pages: 学生作答页面图像
            rubric: 解析后的评分标准
            rubric_context: 格式化的评分标准上下文
            student_name: 学生名称
        """
        logger.info(f"开始批改 {student_name}，共 {len(student_pages)} 页")
        
        # 将图像转为 base64（限制数量避免超时）
        max_pages = min(len(student_pages), 25)
        images_b64 = [
            base64.b64encode(img).decode('utf-8') 
            for img in student_pages[:max_pages]
        ]
        
        # 构建批改 prompt
        prompt = f"""你是一位严格的阅卷老师。请根据以下评分标准，对学生作答进行逐题批改。

{rubric_context}

## 批改要求
1. **严格遵循评分标准**：只按照上述得分点给分
2. **逐个得分点评分**：每个得分点单独判断是否得分
3. **识别另类解法**：如果学生使用了另类解法，按另类解法的得分条件给分
4. **详细解释**：每个得分点都要说明为什么给分或扣分
5. **总题数**：必须批改全部 {rubric.total_questions} 道题

## 学生作答
以下是学生 "{student_name}" 的作答（共 {len(images_b64)} 页）：
[学生作答图像已附上]

## 输出格式（JSON）
```json
{{
    "questions": [
        {{
            "question_id": "1",
            "max_score": 5,
            "awarded_score": 4,
            "scoring_point_results": [
                {{
                    "description": "正确列出方程",
                    "max_score": 2,
                    "awarded_score": 2,
                    "is_correct": true,
                    "explanation": "学生正确列出了 x + y = 10 的方程"
                }},
                {{
                    "description": "正确求解",
                    "max_score": 3,
                    "awarded_score": 2,
                    "is_correct": false,
                    "explanation": "计算过程正确但最终答案有误，扣1分"
                }}
            ],
            "used_alternative_solution": false,
            "alternative_solution_note": "",
            "overall_feedback": "方程建立正确，但计算有小错误",
            "confidence": 0.95
        }}
    ],
    "total_score": 85,
    "max_total_score": {rubric.total_score}
}}
```

## 重要提醒
- 必须批改全部 {rubric.total_questions} 道题
- 每道题的 awarded_score 必须等于各得分点 awarded_score 之和
- 如果学生使用另类解法，设置 used_alternative_solution=true 并说明
- 总分必须等于各题 awarded_score 之和"""

        # 构建消息
        content = [{"type": "text", "text": prompt}]
        for img_b64 in images_b64:
            content.append({
                "type": "image_url",
                "image_url": f"data:image/png;base64,{img_b64}"
            })
        
        message = HumanMessage(content=content)
        
        try:
            # 使用流式 API 避免超时
            logger.info(f"开始流式批改 {student_name}...")
            result_text = ""
            
            max_retries = 3
            retry_delay = 5
            last_error = None
            
            for attempt in range(max_retries):
                try:
                    # 使用 astream 进行流式调用
                    async for chunk in self.llm.astream([message]):
                        if hasattr(chunk, 'content'):
                            content = chunk.content
                            # 处理 content 可能是列表的情况
                            if isinstance(content, list):
                                for item in content:
                                    if isinstance(item, str):
                                        result_text += item
                                    elif isinstance(item, dict) and "text" in item:
                                        result_text += item["text"]
                            elif isinstance(content, str):
                                result_text += content
                    break
                except Exception as e:
                    last_error = e
                    error_str = str(e)
                    if "503" in error_str or "overloaded" in error_str.lower() or "disconnected" in error_str.lower():
                        if attempt < max_retries - 1:
                            logger.warning(f"Gemini API 错误，{retry_delay}秒后重试 ({attempt + 1}/{max_retries}): {error_str[:100]}")
                            import asyncio
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2
                            result_text = ""  # 重置结果
                            continue
                    raise
            else:
                raise last_error
            
            logger.info(f"{student_name} 批改响应接收完成，长度: {len(result_text)}")
            
            # 提取 JSON
            if "```json" in result_text:
                json_start = result_text.find("```json") + 7
                json_end = result_text.find("```", json_start)
                result_text = result_text[json_start:json_end].strip()
            elif "```" in result_text:
                json_start = result_text.find("```") + 3
                json_end = result_text.find("```", json_start)
                result_text = result_text[json_start:json_end].strip()
            
            # 尝试修复常见的 JSON 错误
            try:
                data = json.loads(result_text)
            except json.JSONDecodeError as e:
                logger.warning(f"JSON 解析失败，尝试修复: {str(e)[:100]}")
                # 尝试修复：移除尾部逗号、修复引号等
                import re
                result_text = re.sub(r',\s*}', '}', result_text)
                result_text = re.sub(r',\s*]', ']', result_text)
                result_text = re.sub(r'[\x00-\x1f]', '', result_text)  # 移除控制字符
                try:
                    data = json.loads(result_text)
                except json.JSONDecodeError:
                    # 如果还是失败，返回空结果
                    logger.error("JSON 修复失败，返回空结果")
                    return StudentGradingResult(
                        student_id=student_name,
                        student_name=student_name,
                        total_score=0,
                        max_total_score=rubric.total_score,
                        question_results=[]
                    )
            
            # 解析结果
            question_results = []
            questions_data = data.get("questions", [])
            
            # 确保 questions_data 是列表
            if not isinstance(questions_data, list):
                logger.warning(f"questions 不是列表类型: {type(questions_data)}")
                questions_data = []
            
            for q in questions_data:
                # 确保 q 是字典
                if not isinstance(q, dict):
                    logger.warning(f"题目数据不是字典类型: {type(q)}")
                    continue
                
                # 解析得分点结果
                scoring_point_results = []
                sp_data = q.get("scoring_point_results", [])
                
                # 确保 sp_data 是列表
                if not isinstance(sp_data, list):
                    logger.warning(f"scoring_point_results 不是列表类型: {type(sp_data)}")
                    sp_data = []
                
                for sp in sp_data:
                    # 确保 sp 是字典
                    if not isinstance(sp, dict):
                        logger.warning(f"得分点数据不是字典类型: {type(sp)}")
                        continue
                    
                    scoring_point_results.append(
                        ScoringPointResult(
                            description=str(sp.get("description", "")),
                            max_score=float(sp.get("max_score", 0)),
                            awarded_score=float(sp.get("awarded_score", 0)),
                            is_correct=bool(sp.get("is_correct", False)),
                            explanation=str(sp.get("explanation", ""))
                        )
                    )
                
                question_results.append(QuestionGradingResult(
                    question_id=str(q.get("question_id", "")),
                    max_score=float(q.get("max_score", 0)),
                    awarded_score=float(q.get("awarded_score", 0)),
                    scoring_point_results=scoring_point_results,
                    used_alternative_solution=bool(q.get("used_alternative_solution", False)),
                    alternative_solution_note=str(q.get("alternative_solution_note", "")),
                    overall_feedback=str(q.get("overall_feedback", "")),
                    confidence=float(q.get("confidence", 0.9))
                ))
            
            total_score = float(data.get("total_score", 0))
            
            # 验证总分
            calculated_total = sum(q.awarded_score for q in question_results)
            if abs(calculated_total - total_score) > 0.5:
                logger.warning(
                    f"总分不一致: 声明 {total_score}, "
                    f"计算 {calculated_total}"
                )
                total_score = calculated_total
            
            result = StudentGradingResult(
                student_id=student_name,
                student_name=student_name,
                total_score=total_score,
                max_total_score=rubric.total_score,
                question_results=question_results
            )
            
            logger.info(
                f"批改完成: {student_name}, "
                f"得分 {result.total_score}/{result.max_total_score}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"批改失败: {str(e)}")
            raise
    
    def format_grading_report(
        self,
        result: StudentGradingResult,
        detailed: bool = True
    ) -> str:
        """
        格式化批改报告
        """
        lines = [
            "=" * 60,
            f"批改报告 - {result.student_name}",
            "=" * 60,
            f"总分: {result.total_score} / {result.max_total_score}",
            f"得分率: {result.total_score/result.max_total_score*100:.1f}%",
            f"批改题数: {len(result.question_results)}",
            ""
        ]
        
        for q in result.question_results:
            lines.append("-" * 40)
            lines.append(
                f"【第 {q.question_id} 题】"
                f"{q.awarded_score}/{q.max_score} 分"
            )
            
            if q.used_alternative_solution:
                lines.append(f"  ⚡ 使用另类解法: {q.alternative_solution_note}")
            
            if detailed:
                lines.append("  得分点详情:")
                for sp in q.scoring_point_results:
                    status = "✓" if sp.is_correct else "✗"
                    lines.append(
                        f"    {status} [{sp.awarded_score}/{sp.max_score}] "
                        f"{sp.description}"
                    )
                    lines.append(f"       → {sp.explanation}")
            
            lines.append(f"  评语: {q.overall_feedback}")
            lines.append("")
        
        return "\n".join(lines)
