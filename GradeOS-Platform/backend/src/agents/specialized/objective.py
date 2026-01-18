"""ObjectiveAgent - 选择题/判断题批改智能体

依据标准答案进行精确比对，生成证据链
"""

import json
import logging
from typing import List, Optional

from langchain_core.messages import HumanMessage

from src.services.chat_model_factory import get_chat_model
from src.models.enums import QuestionType
from src.models.state import ContextPack, GradingState, EvidenceItem
from src.agents.base import BaseGradingAgent
from src.config.models import get_default_model


logger = logging.getLogger(__name__)


class ObjectiveAgent(BaseGradingAgent):
    """选择题/判断题批改智能体
    
    专门处理选择题和判断题，通过视觉识别学生答案并与标准答案精确比对。
    
    特点：
    - 高精度答案识别
    - 精确比对评分
    - 生成完整证据链
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        """初始化 ObjectiveAgent
        
        Args:
            api_key: Google AI API 密钥
            model_name: 使用的模型名称，默认使用全局配置
        """
        if model_name is None:
            model_name = get_default_model()
        self.llm = get_chat_model(
            api_key=api_key,
            model_name=model_name,
            temperature=0.1,
            purpose="vision",
            enable_thinking=True,
        )
        self._api_key = api_key
    
    @property
    def agent_type(self) -> str:
        return "objective"
    
    @property
    def supported_question_types(self) -> List[QuestionType]:
        return [QuestionType.OBJECTIVE]
    
    async def grade(self, context_pack: ContextPack) -> GradingState:
        """执行选择题/判断题批改
        
        Args:
            context_pack: 上下文包，包含题目图像、评分细则等
            
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
            # 步骤1：视觉提取 - 识别学生答案
            reasoning_trace.append("开始视觉提取：识别学生选择的答案")
            vision_result = await self._extract_student_answer(
                question_image, rubric, standard_answer
            )
            reasoning_trace.append(f"视觉提取完成：{vision_result.get('description', '')}")
            
            student_answer = vision_result.get("student_answer", "")
            answer_location = vision_result.get("answer_location", [0, 0, 100, 100])
            
            # 步骤2：答案比对
            reasoning_trace.append(f"开始答案比对：学生答案='{student_answer}'，标准答案='{standard_answer}'")
            comparison_result = self._compare_answers(
                student_answer, standard_answer, max_score
            )
            reasoning_trace.append(f"比对结果：得分={comparison_result['score']}/{max_score}")
            
            # 步骤3：生成证据链
            evidence_chain = self._build_evidence_chain(
                student_answer=student_answer,
                standard_answer=standard_answer,
                answer_location=answer_location,
                score=comparison_result["score"],
                max_score=max_score,
                rubric=rubric
            )
            
            # 步骤4：计算置信度
            confidence = self._calculate_confidence(
                vision_result, comparison_result, previous_result
            )
            reasoning_trace.append(f"置信度计算：{confidence:.2f}")
            
            # 步骤4.5：低置信度二次验证
            needs_secondary_verification = confidence < 0.85
            secondary_result = None
            inconsistent_verification = False
            
            if needs_secondary_verification and not previous_result:
                reasoning_trace.append(f"置信度 {confidence:.2f} < 0.85，触发二次验证")
                secondary_result = await self._perform_secondary_verification(
                    question_image=question_image,
                    rubric=rubric,
                    standard_answer=standard_answer,
                    max_score=max_score,
                    first_result={
                        "student_answer": student_answer,
                        "score": comparison_result["score"],
                        "confidence": confidence
                    }
                )
                reasoning_trace.append(f"二次验证完成：学生答案='{secondary_result['student_answer']}'，得分={secondary_result['score']}")
                
                # 比较两次结果
                if secondary_result["student_answer"] != student_answer or secondary_result["score"] != comparison_result["score"]:
                    reasoning_trace.append("⚠️ 二次验证结果不一致，标记为待人工复核")
                    inconsistent_verification = True
                    # 使用第一次结果，但标记需要复核
                    confidence = 0.0  # 降低置信度到 0，强制人工复核
                else:
                    reasoning_trace.append("✓ 二次验证结果一致，提高置信度")
                    confidence = min(1.0, confidence + 0.15)  # 提高置信度
            
            # 步骤5：记录评分依据
            scoring_rationale = self._build_scoring_rationale(
                student_answer=student_answer,
                standard_answer=standard_answer,
                is_correct=comparison_result["is_correct"],
                answer_clarity=vision_result.get("answer_clarity", "clear"),
                confidence=confidence,
                secondary_result=secondary_result
            )
            reasoning_trace.append(f"评分依据：{scoring_rationale}")
            
            # 步骤6：生成学生反馈
            student_feedback = self._generate_feedback(
                student_answer, standard_answer, comparison_result["is_correct"]
            )
            
            # 构建最终状态
            return GradingState(
                context_pack=context_pack,
                vision_analysis=vision_result.get("description", ""),
                rubric_mapping=[{
                    "rubric_point": "答案正确性",
                    "evidence": f"学生答案: {student_answer}",
                    "score_awarded": comparison_result["score"],
                    "max_score": max_score,
                    "scoring_rationale": scoring_rationale,  # 添加评分依据
                    "answer_clarity": vision_result.get("answer_clarity", "clear"),
                    "secondary_verification": secondary_result is not None,
                    "inconsistent_verification": inconsistent_verification
                }],
                initial_score=comparison_result["score"],
                reasoning_trace=reasoning_trace,
                critique_feedback=None,
                evidence_chain=evidence_chain,
                final_score=comparison_result["score"],
                max_score=max_score,
                confidence=confidence,
                visual_annotations=[{
                    "type": "answer_region",
                    "bounding_box": answer_location,
                    "label": f"学生答案: {student_answer}",
                    "is_correct": comparison_result["is_correct"]
                }],
                student_feedback=student_feedback,
                agent_type=self.agent_type,
                revision_count=0,
                is_finalized=True,
                needs_secondary_review=confidence < 0.75 or inconsistent_verification
            )
            
        except Exception as e:
            logger.error(f"ObjectiveAgent 批改失败: {e}")
            reasoning_trace.append(f"错误: {str(e)}")
            reasoning_trace.append("评分依据：批改过程中发生错误，无法完成评分")
            
            # 即使出错也要返回完整的 rubric_mapping
            return GradingState(
                context_pack=context_pack,
                vision_analysis="",
                rubric_mapping=[{
                    "rubric_point": "答案正确性",
                    "evidence": "批改失败",
                    "score_awarded": 0.0,
                    "max_score": max_score,
                    "scoring_rationale": f"批改过程中发生错误：{str(e)}",
                    "answer_clarity": "not_found",
                    "secondary_verification": False,
                    "inconsistent_verification": False
                }],
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
    
    async def _extract_student_answer(
        self,
        question_image: str,
        rubric: str,
        standard_answer: str
    ) -> dict:
        """从图像中提取学生答案
        
        Args:
            question_image: Base64 编码的题目图像
            rubric: 评分细则
            standard_answer: 标准答案
            
        Returns:
            包含学生答案和位置信息的字典
        """
        prompt = f"""请分析这张选择题/判断题的答题图像，识别学生选择的答案。

评分细则：
{rubric}

标准答案：{standard_answer}

请返回 JSON 格式：
{{
    "student_answer": "学生选择的答案（如 A、B、C、D 或 对/错/√/×）",
    "answer_location": [ymin, xmin, ymax, xmax],  // 答案在图像中的位置（归一化坐标 0-1000）
    "description": "对学生答题情况的简要描述",
    "answer_clarity": "clear/unclear/not_found"  // 答案清晰度
}}

注意：
- 如果学生涂改了答案，请识别最终答案
- 如果无法识别答案，answer_clarity 设为 "not_found"
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
        
        # 解析 JSON
        try:
            if "```json" in result_text:
                json_start = result_text.find("```json") + 7
                json_end = result_text.find("```", json_start)
                result_text = result_text[json_start:json_end].strip()
            return json.loads(result_text)
        except json.JSONDecodeError:
            logger.warning(f"无法解析视觉提取结果: {result_text}")
            return {
                "student_answer": "",
                "answer_location": [0, 0, 1000, 1000],
                "description": result_text,
                "answer_clarity": "unclear"
            }
    
    async def _perform_secondary_verification(
        self,
        question_image: str,
        rubric: str,
        standard_answer: str,
        max_score: float,
        first_result: dict
    ) -> dict:
        """执行二次验证
        
        使用不同的提示词策略重新评估答案，以提高准确性
        
        Args:
            question_image: Base64 编码的题目图像
            rubric: 评分细则
            standard_answer: 标准答案
            max_score: 满分
            first_result: 首次评估结果
            
        Returns:
            二次验证结果字典
        """
        # 使用更详细的提示词进行二次验证
        prompt = f"""请仔细分析这张客观题的答题图像，进行二次验证。

评分细则：
{rubric}

标准答案：{standard_answer}

首次识别结果：{first_result['student_answer']}（置信度：{first_result['confidence']:.2f}）

请特别注意：
1. 学生是否有涂改痕迹？如有，最终答案是什么？
2. 答案标记是否清晰？是否存在多选或模糊情况？
3. 答案位置是否正确？是否在正确的答题区域？

请返回 JSON 格式：
{{
    "student_answer": "学生选择的答案",
    "answer_location": [ymin, xmin, ymax, xmax],
    "description": "详细的答题情况描述",
    "answer_clarity": "clear/unclear/not_found",
    "verification_notes": "二次验证的特别说明"
}}"""

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
        
        # 解析 JSON
        try:
            if "```json" in result_text:
                json_start = result_text.find("```json") + 7
                json_end = result_text.find("```", json_start)
                result_text = result_text[json_start:json_end].strip()
            vision_result = json.loads(result_text)
        except json.JSONDecodeError:
            logger.warning(f"无法解析二次验证结果: {result_text}")
            vision_result = {
                "student_answer": first_result["student_answer"],
                "answer_location": [0, 0, 1000, 1000],
                "description": result_text,
                "answer_clarity": "unclear",
                "verification_notes": "解析失败"
            }
        
        # 比对答案并计算得分
        student_answer = vision_result.get("student_answer", "")
        comparison_result = self._compare_answers(
            student_answer, standard_answer, max_score
        )
        
        return {
            "student_answer": student_answer,
            "score": comparison_result["score"],
            "is_correct": comparison_result["is_correct"],
            "answer_clarity": vision_result.get("answer_clarity", "clear"),
            "verification_notes": vision_result.get("verification_notes", "")
        }
    
    def _compare_answers(
        self,
        student_answer: str,
        standard_answer: str,
        max_score: float
    ) -> dict:
        """比对学生答案和标准答案
        
        Args:
            student_answer: 学生答案
            standard_answer: 标准答案
            max_score: 满分
            
        Returns:
            比对结果字典
        """
        # 标准化答案格式
        student_normalized = self._normalize_answer(student_answer)
        standard_normalized = self._normalize_answer(standard_answer)
        
        is_correct = student_normalized == standard_normalized
        score = max_score if is_correct else 0.0
        
        return {
            "is_correct": is_correct,
            "score": score,
            "student_normalized": student_normalized,
            "standard_normalized": standard_normalized
        }
    
    def _normalize_answer(self, answer: str) -> str:
        """标准化答案格式
        
        Args:
            answer: 原始答案
            
        Returns:
            标准化后的答案
        """
        if not answer:
            return ""
        
        answer = answer.strip().upper()
        
        # 处理判断题答案
        true_variants = {"对", "√", "T", "TRUE", "正确", "YES", "是"}
        false_variants = {"错", "×", "X", "F", "FALSE", "错误", "NO", "否"}
        
        if answer in true_variants:
            return "TRUE"
        if answer in false_variants:
            return "FALSE"
        
        # 处理选择题答案（去除多余字符）
        answer = "".join(c for c in answer if c.isalnum())
        
        return answer
    
    def _build_evidence_chain(
        self,
        student_answer: str,
        standard_answer: str,
        answer_location: List[int],
        score: float,
        max_score: float,
        rubric: str
    ) -> List[EvidenceItem]:
        """构建证据链
        
        Args:
            student_answer: 学生答案
            standard_answer: 标准答案
            answer_location: 答案位置
            score: 得分
            max_score: 满分
            rubric: 评分细则
            
        Returns:
            证据链列表
        """
        is_correct = score == max_score
        
        evidence: EvidenceItem = {
            "scoring_point": "答案正确性判定",
            "image_region": answer_location,
            "text_description": f"学生选择答案: {student_answer}，标准答案: {standard_answer}",
            "reasoning": "答案正确" if is_correct else f"答案错误，学生答案'{student_answer}'与标准答案'{standard_answer}'不符",
            "rubric_reference": rubric[:200] if rubric else "选择题/判断题评分标准",
            "points_awarded": score
        }
        
        return [evidence]
    
    def _calculate_confidence(
        self,
        vision_result: dict,
        comparison_result: dict,
        previous_result: Optional[dict]
    ) -> float:
        """计算置信度
        
        Args:
            vision_result: 视觉提取结果
            comparison_result: 比对结果
            previous_result: 前序结果（二次评估时）
            
        Returns:
            置信度分数 (0.0-1.0)
        """
        base_confidence = 0.95  # 选择题基础置信度较高
        
        # 根据答案清晰度调整
        clarity = vision_result.get("answer_clarity", "clear")
        if clarity == "unclear":
            base_confidence -= 0.2
        elif clarity == "not_found":
            base_confidence -= 0.5
        
        # 如果是二次评估且结果一致，提高置信度
        if previous_result:
            prev_score = previous_result.get("score", -1)
            if prev_score == comparison_result["score"]:
                base_confidence = min(1.0, base_confidence + 0.1)
            else:
                base_confidence -= 0.1
        
        return max(0.0, min(1.0, base_confidence))
    
    def _build_scoring_rationale(
        self,
        student_answer: str,
        standard_answer: str,
        is_correct: bool,
        answer_clarity: str,
        confidence: float,
        secondary_result: Optional[dict] = None
    ) -> str:
        """构建评分依据记录
        
        Args:
            student_answer: 学生答案
            standard_answer: 标准答案
            is_correct: 是否正确
            answer_clarity: 答案清晰度
            confidence: 置信度
            secondary_result: 二次验证结果（如有）
            
        Returns:
            评分依据文本
        """
        rationale_parts = []
        
        # 1. 答案识别情况
        if answer_clarity == "clear":
            rationale_parts.append(f"答案识别清晰，学生选择：{student_answer}")
        elif answer_clarity == "unclear":
            rationale_parts.append(f"答案识别存在模糊，推测学生选择：{student_answer}")
        else:
            rationale_parts.append(f"答案识别困难，可能选择：{student_answer}")
        
        # 2. 答案比对结果
        if is_correct:
            rationale_parts.append(f"答案正确，与标准答案 {standard_answer} 一致")
        else:
            rationale_parts.append(f"答案错误，标准答案为 {standard_answer}")
        
        # 3. 二次验证信息
        if secondary_result:
            if secondary_result["student_answer"] == student_answer:
                rationale_parts.append("二次验证结果一致")
            else:
                rationale_parts.append(f"⚠️ 二次验证结果不一致（二次识别：{secondary_result['student_answer']}）")
        
        # 4. 置信度说明
        if confidence >= 0.9:
            rationale_parts.append("高置信度评分")
        elif confidence >= 0.75:
            rationale_parts.append("中等置信度评分")
        else:
            rationale_parts.append("低置信度评分，建议人工复核")
        
        return "；".join(rationale_parts)
    
    def _generate_feedback(
        self,
        student_answer: str,
        standard_answer: str,
        is_correct: bool
    ) -> str:
        """生成学生反馈
        
        Args:
            student_answer: 学生答案
            standard_answer: 标准答案
            is_correct: 是否正确
            
        Returns:
            反馈文本
        """
        if is_correct:
            return f"回答正确！你选择的答案 {student_answer} 是正确的。"
        else:
            return f"回答错误。你选择的答案是 {student_answer}，正确答案是 {standard_answer}。"
    
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
