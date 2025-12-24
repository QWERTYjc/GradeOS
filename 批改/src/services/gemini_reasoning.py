"""Gemini 深度推理客户端 - 使用 Gemini 进行批改推理"""

import base64
import json
import logging
from typing import Dict, Any, List, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from ..models.grading import RubricMappingItem
from ..config.models import get_default_model


logger = logging.getLogger(__name__)


class GeminiReasoningClient:
    """Gemini 深度推理客户端，用于批改智能体的各个推理节点"""
    
    # 类常量：避免魔法数字
    MAX_QUESTIONS_IN_PROMPT = 20  # 提示词中最多显示的题目数
    MAX_CRITERIA_PER_QUESTION = 3  # 每道题最多显示的评分要点数
    
    def __init__(self, api_key: str, model_name: Optional[str] = None):
        """
        初始化 Gemini 推理客户端
        
        Args:
            api_key: Google AI API 密钥
            model_name: 使用的模型名称，默认使用全局配置
        """
        if model_name is None:
            model_name = get_default_model()
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=0.2
        )
        self.model_name = model_name
        self.temperature = 0.2  # 低温度以保持一致性
    
    def _extract_text_from_response(self, content: Any) -> str:
        """
        从响应中提取文本内容
        
        Args:
            content: 响应内容（可能是字符串或列表）
            
        Returns:
            str: 提取的文本
        """
        if isinstance(content, list):
            # Gemini 3.0 返回列表格式
            text_parts = []
            for item in content:
                if isinstance(item, dict):
                    text_parts.append(item.get('text', ''))
                else:
                    text_parts.append(str(item))
            return '\n'.join(text_parts)
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
    
    async def _call_vision_api(
        self,
        image_b64: str,
        prompt: str
    ) -> str:
        """
        调用视觉 API
        
        Args:
            image_b64: Base64 编码的图像
            prompt: 提示词
            
        Returns:
            str: LLM 响应文本
        """
        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": f"data:image/png;base64,{image_b64}"
                }
            ]
        )
        
        response = await self.llm.ainvoke([message])
        return self._extract_text_from_response(response.content)
        
    async def vision_extraction(
        self,
        question_image_b64: str,
        rubric: str,
        standard_answer: Optional[str] = None
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
                {
                    "type": "image_url",
                    "image_url": f"data:image/jpeg;base64,{question_image_b64}"
                }
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
        critique_feedback: Optional[str] = None
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
            "evidence": "在学生答案中找到的证据（如果没有找到，说明'未找到'）",
            "score_awarded": 获得的分数,
            "max_score": 该评分点的满分
        }}
    ],
    "initial_score": 总得分,
    "reasoning": "评分理由"
}}"""

        # 调用 LLM
        response = await self.llm.ainvoke([HumanMessage(content=prompt)])
        
        # 提取文本内容
        result_text = self._extract_text_from_response(response.content)
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
        standard_answer: Optional[str] = None
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

        # 调用 LLM
        response = await self.llm.ainvoke([HumanMessage(content=prompt)])
        
        # 提取文本内容
        result_text = self._extract_text_from_response(response.content)
        result_text = self._extract_json_from_text(result_text)
        
        result = json.loads(result_text)
        return result

    async def analyze_with_vision(
        self,
        images: List[bytes],
        prompt: str
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
                img_b64 = base64.b64encode(img_bytes).decode('utf-8')
            else:
                img_b64 = img_bytes  # 已经是 base64 字符串
            
            content.append({
                "type": "image_url",
                "image_url": f"data:image/png;base64,{img_b64}"
            })
        
        # 调用 LLM
        message = HumanMessage(content=content)
        response = await self.llm.ainvoke([message])
        
        # 提取文本内容
        result_text = self._extract_text_from_response(response.content)
        
        return {"response": result_text}

    # ==================== grade_page 拆分为多个私有方法 ====================
    
    def _build_grading_prompt(
        self,
        rubric: str,
        parsed_rubric: Optional[Dict[str, Any]]
    ) -> str:
        """
        构建评分提示词
        
        Args:
            rubric: 评分细则文本
            parsed_rubric: 解析后的评分标准
            
        Returns:
            str: 完整的评分提示词
        """
        # 优先使用解析后的评分标准上下文
        rubric_info = ""
        
        if parsed_rubric and parsed_rubric.get("rubric_context"):
            # 使用格式化的评分标准上下文
            rubric_info = parsed_rubric["rubric_context"]
        elif parsed_rubric and parsed_rubric.get("questions"):
            # 从题目信息构建评分标准
            questions_info = []
            for q in parsed_rubric.get("questions", [])[:self.MAX_QUESTIONS_IN_PROMPT]:
                q_info = f"第{q.get('id', '?')}题 (满分{q.get('max_score', 0)}分):"
                
                # 添加评分要点
                criteria = q.get("criteria", [])
                scoring_points = q.get("scoring_points", [])
                
                if scoring_points:
                    for sp in scoring_points[:self.MAX_CRITERIA_PER_QUESTION]:
                        q_info += f"\n  - [{sp.get('score', 0)}分] {sp.get('description', '')}"
                elif criteria:
                    for criterion in criteria[:self.MAX_CRITERIA_PER_QUESTION]:
                        q_info += f"\n  - {criterion}"
                
                # 添加标准答案摘要
                if q.get("standard_answer"):
                    answer_preview = q["standard_answer"][:100] + "..." if len(q["standard_answer"]) > 100 else q["standard_answer"]
                    q_info += f"\n  标准答案: {answer_preview}"
                
                questions_info.append(q_info)
            
            rubric_info = f"评分标准（共{parsed_rubric.get('total_questions', 0)}题，总分{parsed_rubric.get('total_score', 0)}分）：\n\n" + "\n\n".join(questions_info)
        elif rubric:
            # 使用原始评分细则
            rubric_info = rubric
        else:
            # 默认评分标准
            rubric_info = "请根据答案的正确性、完整性和清晰度进行评分"
        
        return f"""请仔细分析这张学生答题图像，进行详细评分。

{rubric_info}

请完成以下任务：
1. 首先判断：这是否是一张空白页、封面页、目录页或没有学生作答内容的页面？
2. 如果是空白/封面/目录页：直接返回 score=0, max_score=0
3. 如果有学生作答：识别题目编号并逐题评分

请返回 JSON 格式：
{{
    "score": 本页总得分（数字，空白页为0）,
    "max_score": 本页涉及题目的满分总和（数字，空白页为0，注意：只计算本页实际出现的题目的满分，不是整张试卷的总分）,
    "confidence": 评分置信度（0.0-1.0）,
    "is_blank_page": true/false（是否为空白页、封面页或无作答内容的页面）,
    "question_numbers": ["识别到的题目编号列表，如 '1', '2', '3' 等，空白页为空数组"],
    "question_details": [
        {{
            "question_id": "题号",
            "score": 得分,
            "max_score": 该题满分,
            "student_answer": "学生答案摘要（简短描述学生写了什么）",
            "is_correct": true/false,
            "feedback": "详细评分说明，包括得分点和扣分原因"
        }}
    ],
    "page_summary": "本页整体评价（一句话总结，空白页说明'空白页/封面页/目录页'）",
    "student_info": {{
        "name": "学生姓名（如果能识别，否则为null）",
        "student_id": "学号（如果能识别，否则为null）"
    }}
}}

重要评分规则：
- 空白页、封面页、目录页：score=0, max_score=0, is_blank_page=true
- max_score 只计算本页实际出现的题目的满分，不是整张试卷的总分
- 严格按照上述评分标准进行评分
- 仔细对比学生答案与标准答案
- 明确指出正确和错误的部分
- 给出具体的扣分原因
- 如果学生答案部分正确，给予部分分数"""

    def _parse_grading_response(
        self,
        response_text: str,
        max_score: float
    ) -> Dict[str, Any]:
        """
        解析评分响应
        
        Args:
            response_text: LLM 响应文本
            max_score: 满分
            
        Returns:
            Dict: 解析后的评分结果
        """
        json_text = self._extract_json_from_text(response_text)
        return json.loads(json_text)
    
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
            q_feedback = f"第{q.get('question_id', '?')}题: {q.get('score', 0)}/{q.get('max_score', 0)}分"
            if q.get("feedback"):
                q_feedback += f" - {q['feedback']}"
            feedback_parts.append(q_feedback)
        
        return "\n".join(feedback_parts) if feedback_parts else "评分完成"

    async def grade_page(
        self,
        image: bytes,
        rubric: str,
        max_score: float = 10.0,
        parsed_rubric: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        批改单页：分析图像并给出详细评分
        
        Args:
            image: 图像字节
            rubric: 评分细则文本
            max_score: 满分
            parsed_rubric: 解析后的评分标准（包含题目信息）
            
        Returns:
            Dict: 包含详细评分结果
        """
        logger.debug(f"开始批改单页, rubric长度={len(rubric)}")
        
        # 1. 构建提示词
        prompt = self._build_grading_prompt(rubric, parsed_rubric)
        
        # 2. 转换图像为 base64
        if isinstance(image, bytes):
            img_b64 = base64.b64encode(image).decode('utf-8')
        else:
            img_b64 = image
        
        try:
            # 3. 调用视觉 API
            response_text = await self._call_vision_api(img_b64, prompt)
            
            # 4. 解析响应
            result = self._parse_grading_response(response_text, max_score)
            
            # 5. 生成综合反馈
            result["feedback"] = self._generate_feedback(result)
            
            logger.info(
                f"批改完成: score={result.get('score')}, "
                f"confidence={result.get('confidence')}"
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
                "student_info": None
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
                "student_info": None
            }
