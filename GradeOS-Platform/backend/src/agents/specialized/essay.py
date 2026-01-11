"""EssayAgent - 作文/简答题批改智能体

依据内容、结构、语言等维度评分，生成证据链
"""

import json
import logging
from typing import List, Dict, Any, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from src.models.enums import QuestionType
from src.models.state import ContextPack, GradingState, EvidenceItem
from src.agents.base import BaseGradingAgent
from src.config.models import get_default_model
from src.utils.llm_thinking import get_thinking_kwargs


logger = logging.getLogger(__name__)


# 作文评分维度
ESSAY_DIMENSIONS = [
    {"name": "内容", "weight": 0.4, "description": "观点明确、论据充分、切题"},
    {"name": "结构", "weight": 0.25, "description": "层次清晰、逻辑连贯、段落分明"},
    {"name": "语言", "weight": 0.25, "description": "表达准确、语句通顺、用词恰当"},
    {"name": "书写", "weight": 0.1, "description": "字迹工整、卷面整洁"},
]


class EssayAgent(BaseGradingAgent):
    """作文/简答题批改智能体
    
    专门处理作文和简答题，从多个维度进行综合评分。
    
    特点：
    - 多维度评分（内容、结构、语言、书写）
    - 整体印象与细节分析结合
    - 生成详细的改进建议
    - 生成完整证据链
    """
    
    def __init__(
        self,
        api_key: str,
        model_name: Optional[str] = None
    ):
        """初始化 EssayAgent
        
        Args:
            api_key: Google AI API 密钥
            model_name: 使用的模型名称，默认使用全局配置
        """
        if model_name is None:
            model_name = get_default_model()
        thinking_kwargs = get_thinking_kwargs(model_name, enable_thinking=True)
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=0.3,  # slightly higher temperature for flexible evaluation
            **thinking_kwargs,
        )
        self._api_key = api_key
    
    @property
    def agent_type(self) -> str:
        return "essay"
    
    @property
    def supported_question_types(self) -> List[QuestionType]:
        return [QuestionType.ESSAY]
    
    async def grade(self, context_pack: ContextPack) -> GradingState:
        """执行作文/简答题批改
        
        Args:
            context_pack: 上下文包
            
        Returns:
            GradingState: 批改结果
        """
        question_image = context_pack.get("question_image", "")
        rubric = context_pack.get("rubric", "")
        max_score = context_pack.get("max_score", 0.0)
        standard_answer = context_pack.get("standard_answer", "")
        previous_result = context_pack.get("previous_result")
        
        reasoning_trace: List[str] = []
        
        try:
            # 步骤1：视觉提取 - 识别学生作答内容
            reasoning_trace.append("开始视觉提取：识别学生作答内容")
            vision_analysis = await self._extract_essay_content(
                question_image, rubric
            )
            reasoning_trace.append(f"视觉提取完成：字数约 {vision_analysis.get('word_count', 0)}")
            
            # 步骤2：多维度评分
            reasoning_trace.append("开始多维度评分")
            scoring_result = await self._score_essay(
                vision_analysis, rubric, max_score, standard_answer
            )
            reasoning_trace.append(f"评分完成：总分 {scoring_result['total_score']}/{max_score}")
            
            # 步骤3：生成证据链
            evidence_chain = self._build_evidence_chain(
                scoring_result.get("dimension_scores", []),
                rubric
            )
            
            # 步骤4：计算置信度
            confidence = self._calculate_confidence(
                vision_analysis, scoring_result, previous_result
            )
            reasoning_trace.append(f"置信度：{confidence:.2f}")
            
            # 步骤5：生成学生反馈
            student_feedback = self._generate_feedback(scoring_result)
            
            # 构建 rubric_mapping
            rubric_mapping = []
            for dim_score in scoring_result.get("dimension_scores", []):
                rubric_mapping.append({
                    "rubric_point": dim_score.get("dimension", ""),
                    "evidence": dim_score.get("evidence", ""),
                    "score_awarded": dim_score.get("score", 0),
                    "max_score": dim_score.get("max_score", 0)
                })
            
            # 构建视觉标注
            visual_annotations = [{
                "type": "essay_region",
                "bounding_box": vision_analysis.get("text_region", [0, 0, 1000, 1000]),
                "label": "作答区域",
                "word_count": vision_analysis.get("word_count", 0)
            }]
            
            # 添加亮点和问题标注
            for highlight in scoring_result.get("highlights", []):
                visual_annotations.append({
                    "type": "highlight",
                    "bounding_box": highlight.get("location", [0, 0, 100, 100]),
                    "label": highlight.get("text", ""),
                    "category": "positive"
                })
            
            for issue in scoring_result.get("issues", []):
                visual_annotations.append({
                    "type": "issue",
                    "bounding_box": issue.get("location", [0, 0, 100, 100]),
                    "label": issue.get("text", ""),
                    "category": "negative"
                })
            
            return GradingState(
                context_pack=context_pack,
                vision_analysis=vision_analysis.get("content", ""),
                rubric_mapping=rubric_mapping,
                initial_score=scoring_result["total_score"],
                reasoning_trace=reasoning_trace,
                critique_feedback=None,
                evidence_chain=evidence_chain,
                final_score=scoring_result["total_score"],
                max_score=max_score,
                confidence=confidence,
                visual_annotations=visual_annotations,
                student_feedback=student_feedback,
                agent_type=self.agent_type,
                revision_count=0,
                is_finalized=True,
                needs_secondary_review=confidence < 0.75
            )
            
        except Exception as e:
            logger.error(f"EssayAgent 批改失败: {e}")
            reasoning_trace.append(f"错误: {str(e)}")
            return GradingState(
                context_pack=context_pack,
                vision_analysis="",
                rubric_mapping=[],
                initial_score=0.0,
                reasoning_trace=reasoning_trace,
                critique_feedback=None,
                evidence_chain=[],
                final_score=0.0,
                max_score=max_score,
                confidence=0.0,
                visual_annotations=[],
                student_feedback="批改过程中发生错误，需要人工审核",
                agent_type=self.agent_type,
                revision_count=0,
                is_finalized=False,
                needs_secondary_review=True,
                error=str(e)
            )
    
    async def _extract_essay_content(
        self,
        question_image: str,
        rubric: str
    ) -> dict:
        """从图像中提取作文/简答内容
        
        Args:
            question_image: Base64 编码的题目图像
            rubric: 评分细则
            
        Returns:
            包含作答内容的字典
        """
        prompt = f"""请分析这张作文/简答题的答题图像，提取学生的作答内容。

评分细则：
{rubric}

请返回 JSON 格式：
{{
    "content": "学生作答的完整文字内容",
    "word_count": 估计字数,
    "text_region": [ymin, xmin, ymax, xmax],  // 作答区域位置
    "handwriting_quality": "excellent/good/fair/poor",  // 书写质量
    "structure_analysis": {{
        "has_title": true/false,
        "paragraph_count": 段落数,
        "has_clear_structure": true/false
    }},
    "key_points": ["关键点1", "关键点2", ...],  // 提取的要点
    "readability": "high/medium/low"  // 可读性
}}

注意：
- 尽可能完整地提取文字内容
- 识别段落结构
- 评估书写质量
- 坐标使用归一化格式（0-1000）"""

        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": f"data:image/jpeg;base64,{question_image}"
                }
            ]
        )
        
        response = await self.llm.ainvoke([message])
        result_text = self._extract_text(response.content)
        
        try:
            if "```json" in result_text:
                json_start = result_text.find("```json") + 7
                json_end = result_text.find("```", json_start)
                result_text = result_text[json_start:json_end].strip()
            return json.loads(result_text)
        except json.JSONDecodeError:
            logger.warning(f"无法解析视觉提取结果: {result_text}")
            return {
                "content": result_text,
                "word_count": len(result_text),
                "text_region": [0, 0, 1000, 1000],
                "handwriting_quality": "fair",
                "structure_analysis": {
                    "has_title": False,
                    "paragraph_count": 1,
                    "has_clear_structure": False
                },
                "key_points": [],
                "readability": "medium"
            }
    
    async def _score_essay(
        self,
        vision_analysis: dict,
        rubric: str,
        max_score: float,
        standard_answer: str
    ) -> dict:
        """对作文进行多维度评分
        
        Args:
            vision_analysis: 视觉分析结果
            rubric: 评分细则
            max_score: 满分
            standard_answer: 参考答案
            
        Returns:
            评分结果
        """
        content = vision_analysis.get("content", "")
        structure = vision_analysis.get("structure_analysis", {})
        handwriting = vision_analysis.get("handwriting_quality", "fair")
        
        # 构建评分提示
        dimensions_text = "\n".join([
            f"- {d['name']}（权重{d['weight']*100}%）: {d['description']}"
            for d in ESSAY_DIMENSIONS
        ])
        
        prompt = f"""请对以下作文/简答进行多维度评分。

学生作答内容：
{content}

结构分析：
- 是否有标题：{structure.get('has_title', False)}
- 段落数：{structure.get('paragraph_count', 0)}
- 结构清晰：{structure.get('has_clear_structure', False)}

书写质量：{handwriting}

评分细则：
{rubric}

参考答案/要点：
{standard_answer if standard_answer else "未提供"}

满分：{max_score}

评分维度：
{dimensions_text}

请返回 JSON 格式：
{{
    "total_score": 总得分,
    "dimension_scores": [
        {{
            "dimension": "维度名称",
            "max_score": 该维度满分,
            "score": 该维度得分,
            "evidence": "评分依据（引用学生作答中的具体内容）",
            "feedback": "该维度的评价"
        }}
    ],
    "highlights": [
        {{
            "text": "亮点内容",
            "location": [ymin, xmin, ymax, xmax],
            "reason": "为什么是亮点"
        }}
    ],
    "issues": [
        {{
            "text": "问题内容",
            "location": [ymin, xmin, ymax, xmax],
            "suggestion": "改进建议"
        }}
    ],
    "overall_comment": "整体评语",
    "grade_level": "A/B/C/D/E"  // 等级评定
}}"""

        response = await self.llm.ainvoke([HumanMessage(content=prompt)])
        result_text = self._extract_text(response.content)
        
        try:
            if "```json" in result_text:
                json_start = result_text.find("```json") + 7
                json_end = result_text.find("```", json_start)
                result_text = result_text[json_start:json_end].strip()
            return json.loads(result_text)
        except json.JSONDecodeError:
            logger.warning(f"无法解析评分结果: {result_text}")
            # 返回默认评分
            return {
                "total_score": max_score * 0.6,  # 默认给60%
                "dimension_scores": [],
                "highlights": [],
                "issues": [],
                "overall_comment": "评分解析失败，需要人工审核",
                "grade_level": "C"
            }
    
    def _build_evidence_chain(
        self,
        dimension_scores: List[Dict[str, Any]],
        rubric: str
    ) -> List[EvidenceItem]:
        """构建证据链
        
        Args:
            dimension_scores: 各维度评分
            rubric: 评分细则
            
        Returns:
            证据链列表
        """
        evidence_chain: List[EvidenceItem] = []
        
        for dim in dimension_scores:
            evidence: EvidenceItem = {
                "scoring_point": dim.get("dimension", ""),
                "image_region": [0, 0, 1000, 1000],  # 作文通常是整体评分
                "text_description": dim.get("evidence", ""),
                "reasoning": dim.get("feedback", ""),
                "rubric_reference": rubric[:100] if rubric else "作文评分标准",
                "points_awarded": dim.get("score", 0)
            }
            evidence_chain.append(evidence)
        
        return evidence_chain
    
    def _calculate_confidence(
        self,
        vision_analysis: dict,
        scoring_result: dict,
        previous_result: Optional[dict]
    ) -> float:
        """计算置信度
        
        Args:
            vision_analysis: 视觉分析结果
            scoring_result: 评分结果
            previous_result: 前序结果
            
        Returns:
            置信度分数
        """
        base_confidence = 0.75  # 作文评分主观性较强，基础置信度较低
        
        # 根据可读性调整
        readability = vision_analysis.get("readability", "medium")
        if readability == "high":
            base_confidence += 0.1
        elif readability == "low":
            base_confidence -= 0.15
        
        # 根据书写质量调整
        handwriting = vision_analysis.get("handwriting_quality", "fair")
        if handwriting == "poor":
            base_confidence -= 0.1
        
        # 根据字数调整（太短可能识别不完整）
        word_count = vision_analysis.get("word_count", 0)
        if word_count < 50:
            base_confidence -= 0.1
        
        # 二次评估一致性
        if previous_result:
            prev_score = previous_result.get("score", -1)
            curr_score = scoring_result.get("total_score", 0)
            max_score = scoring_result.get("max_score", 100)
            # 允许10%的误差
            if abs(prev_score - curr_score) < max_score * 0.1:
                base_confidence = min(1.0, base_confidence + 0.1)
            else:
                base_confidence -= 0.1
        
        return max(0.0, min(1.0, base_confidence))
    
    def _generate_feedback(self, scoring_result: dict) -> str:
        """生成学生反馈
        
        Args:
            scoring_result: 评分结果
            
        Returns:
            反馈文本
        """
        feedback_parts = []
        
        # 等级和总评
        grade = scoring_result.get("grade_level", "")
        overall = scoring_result.get("overall_comment", "")
        if grade:
            feedback_parts.append(f"等级：{grade}")
        if overall:
            feedback_parts.append(f"\n{overall}")
        
        # 亮点
        highlights = scoring_result.get("highlights", [])
        if highlights:
            feedback_parts.append("\n\n✨ 亮点：")
            for h in highlights[:2]:
                feedback_parts.append(f"- {h.get('reason', h.get('text', ''))}")
        
        # 改进建议
        issues = scoring_result.get("issues", [])
        if issues:
            feedback_parts.append("\n\n📝 改进建议：")
            for i in issues[:3]:
                feedback_parts.append(f"- {i.get('suggestion', i.get('text', ''))}")
        
        if not feedback_parts:
            total = scoring_result.get("total_score", 0)
            feedback_parts.append(f"得分：{total}分")
        
        return "".join(feedback_parts)
    
    def _extract_text(self, content) -> str:
        """从响应中提取文本"""
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict):
                    text_parts.append(item.get('text', ''))
                else:
                    text_parts.append(str(item))
            return '\n'.join(text_parts)
        return str(content)
