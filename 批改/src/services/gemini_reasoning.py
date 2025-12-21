"""Gemini 深度推理客户端 - 使用 Gemini 进行批改推理"""

import base64
import json
from typing import Dict, Any, List, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from ..models.grading import RubricMappingItem
from ..config.models import get_default_model


class GeminiReasoningClient:
    """Gemini 深度推理客户端，用于批改智能体的各个推理节点"""
    
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
        
        # 尝试从响应中提取 JSON
        if "```json" in result_text:
            json_start = result_text.find("```json") + 7
            json_end = result_text.find("```", json_start)
            result_text = result_text[json_start:json_end].strip()
        
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
        
        # 尝试从响应中提取 JSON
        if "```json" in result_text:
            json_start = result_text.find("```json") + 7
            json_end = result_text.find("```", json_start)
            result_text = result_text[json_start:json_end].strip()
        
        result = json.loads(result_text)
        return result
