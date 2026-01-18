"""StepwiseAgent - 计算题批改智能体

将解题过程拆解为步骤并逐步给分，生成证据链
"""

import json
import logging
from typing import List, Dict, Any, Optional

from langchain_core.messages import HumanMessage

from src.services.chat_model_factory import get_chat_model
from src.models.enums import QuestionType
from src.models.state import ContextPack, GradingState, EvidenceItem
from src.agents.base import BaseGradingAgent
from src.config.models import get_default_model


logger = logging.getLogger(__name__)


class StepwiseAgent(BaseGradingAgent):
    """计算题批改智能体
    
    专门处理数学、物理等需要分步骤计算的题目。
    将解题过程拆解为步骤，逐步评分，支持过程分。
    
    特点：
    - 步骤拆解与识别
    - 过程分评定
    - 错误传递分析
    - 生成完整证据链
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        """初始化 StepwiseAgent
        
        Args:
            api_key: Google AI API 密钥
            model_name: 使用的模型名称，默认使用全局配置
        """
        if model_name is None:
            model_name = get_default_model()
        self.llm = get_chat_model(
            api_key=api_key,
            model_name=model_name,
            temperature=0.2,
            purpose="vision",
            enable_thinking=True,
        )
        self._api_key = api_key
    
    @property
    def agent_type(self) -> str:
        return "stepwise"
    
    @property
    def supported_question_types(self) -> List[QuestionType]:
        return [QuestionType.STEPWISE]
    
    async def grade(self, context_pack: ContextPack) -> GradingState:
        """执行计算题批改
        
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
            # 步骤1：视觉提取 - 识别学生解题过程
            reasoning_trace.append("开始视觉提取：识别学生解题步骤")
            vision_analysis = await self._extract_solution_steps(
                question_image, rubric, standard_answer
            )
            reasoning_trace.append(f"视觉提取完成：识别到 {len(vision_analysis.get('steps', []))} 个步骤")
            
            # 步骤2：提取解题步骤
            steps = self.extract_steps(vision_analysis.get("description", ""))
            if not steps:
                steps = vision_analysis.get("steps", [])
            reasoning_trace.append(f"步骤提取完成：{len(steps)} 个步骤")
            
            # 步骤3：逐步评分
            reasoning_trace.append("开始逐步评分")
            scoring_result = await self._score_steps(
                steps, rubric, max_score, standard_answer
            )
            reasoning_trace.append(f"评分完成：总分 {scoring_result['total_score']}/{max_score}")
            
            # 步骤4：生成证据链
            evidence_chain = self._build_evidence_chain(
                steps=scoring_result.get("step_scores", []),
                rubric=rubric
            )
            
            # 步骤5：计算置信度
            confidence = self._calculate_confidence(
                vision_analysis, scoring_result, previous_result
            )
            reasoning_trace.append(f"置信度：{confidence:.2f}")
            
            # 步骤6：生成学生反馈
            student_feedback = self._generate_feedback(scoring_result)
            
            # 构建 rubric_mapping
            rubric_mapping = []
            for step_score in scoring_result.get("step_scores", []):
                rubric_mapping.append({
                    "rubric_point": step_score.get("step_name", ""),
                    "evidence": step_score.get("student_work", ""),
                    "score_awarded": step_score.get("score", 0),
                    "max_score": step_score.get("max_score", 0)
                })
            
            # 构建视觉标注
            visual_annotations = []
            for step_score in scoring_result.get("step_scores", []):
                visual_annotations.append({
                    "type": "step_region",
                    "bounding_box": step_score.get("location", [0, 0, 1000, 1000]),
                    "label": step_score.get("step_name", ""),
                    "score": f"{step_score.get('score', 0)}/{step_score.get('max_score', 0)}",
                    "is_correct": step_score.get("is_correct", False)
                })
            
            return GradingState(
                context_pack=context_pack,
                vision_analysis=vision_analysis.get("description", ""),
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
            logger.error(f"StepwiseAgent 批改失败: {e}")
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
    
    async def _extract_solution_steps(
        self,
        question_image: str,
        rubric: str,
        standard_answer: str
    ) -> dict:
        """从图像中提取学生解题步骤
        
        Args:
            question_image: Base64 编码的题目图像
            rubric: 评分细则
            standard_answer: 标准答案
            
        Returns:
            包含解题步骤的字典
        """
        prompt = f"""请分析这张计算题的答题图像，识别学生的解题步骤。

评分细则：
{rubric}

标准答案/解题过程：
{standard_answer if standard_answer else "未提供"}

请返回 JSON 格式：
{{
    "description": "对学生解题过程的整体描述",
    "steps": [
        {{
            "step_number": 1,
            "step_name": "步骤名称（如：列方程、代入数值、计算结果等）",
            "content": "该步骤的具体内容",
            "location": [ymin, xmin, ymax, xmax],  // 该步骤在图像中的位置
            "has_error": true/false,
            "error_description": "如果有错误，描述错误内容"
        }}
    ],
    "final_answer": "学生的最终答案",
    "work_clarity": "clear/partial/unclear"
}}

注意：
- 按照解题顺序识别每个步骤
- 标注每个步骤的位置
- 识别计算错误或逻辑错误
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
                "description": result_text,
                "steps": [],
                "final_answer": "",
                "work_clarity": "unclear"
            }
    
    def extract_steps(self, vision_analysis: str) -> List[Dict[str, Any]]:
        """从视觉分析中提取解题步骤
        
        Args:
            vision_analysis: 视觉分析文本
            
        Returns:
            解题步骤列表
        """
        # 如果视觉分析已经是结构化的，直接返回
        if not vision_analysis:
            return []
        
        # 尝试解析 JSON
        try:
            data = json.loads(vision_analysis)
            if isinstance(data, dict) and "steps" in data:
                return data["steps"]
        except json.JSONDecodeError:
            pass
        
        # 简单的文本解析（按行分割）
        steps = []
        lines = vision_analysis.split("\n")
        step_num = 0
        
        for line in lines:
            line = line.strip()
            if line and len(line) > 5:  # 过滤太短的行
                step_num += 1
                steps.append({
                    "step_number": step_num,
                    "step_name": f"步骤 {step_num}",
                    "content": line,
                    "location": [0, 0, 1000, 1000],
                    "has_error": False,
                    "error_description": ""
                })
        
        return steps
    
    async def _score_steps(
        self,
        steps: List[Dict[str, Any]],
        rubric: str,
        max_score: float,
        standard_answer: str
    ) -> dict:
        """对每个步骤进行评分
        
        Args:
            steps: 解题步骤列表
            rubric: 评分细则
            max_score: 满分
            standard_answer: 标准答案
            
        Returns:
            评分结果
        """
        if not steps:
            return {
                "total_score": 0.0,
                "step_scores": [],
                "feedback": "未能识别到解题步骤"
            }
        
        # 构建评分提示
        steps_text = json.dumps(steps, ensure_ascii=False, indent=2)
        
        prompt = f"""请对以下解题步骤进行评分。

学生解题步骤：
{steps_text}

评分细则：
{rubric}

标准答案/解题过程：
{standard_answer if standard_answer else "未提供"}

满分：{max_score}

请返回 JSON 格式：
{{
    "total_score": 总得分,
    "step_scores": [
        {{
            "step_number": 步骤编号,
            "step_name": "步骤名称",
            "student_work": "学生该步骤的内容",
            "location": [ymin, xmin, ymax, xmax],
            "max_score": 该步骤满分,
            "score": 该步骤得分,
            "is_correct": true/false,
            "feedback": "该步骤的评价"
        }}
    ],
    "overall_feedback": "整体评价"
}}

评分原则：
1. 过程分：即使最终答案错误，正确的步骤也应给分
2. 错误传递：如果前面步骤错误导致后续计算错误，后续步骤可酌情给分
3. 方法分：使用正确方法但计算错误，应给方法分"""

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
                "total_score": 0.0,
                "step_scores": [],
                "overall_feedback": "评分解析失败，需要人工审核"
            }
    
    def _build_evidence_chain(
        self,
        steps: List[Dict[str, Any]],
        rubric: str
    ) -> List[EvidenceItem]:
        """构建证据链
        
        Args:
            steps: 评分后的步骤列表
            rubric: 评分细则
            
        Returns:
            证据链列表
        """
        evidence_chain: List[EvidenceItem] = []
        
        for step in steps:
            evidence: EvidenceItem = {
                "scoring_point": step.get("step_name", f"步骤 {step.get('step_number', 0)}"),
                "image_region": step.get("location", [0, 0, 1000, 1000]),
                "text_description": step.get("student_work", step.get("content", "")),
                "reasoning": step.get("feedback", ""),
                "rubric_reference": rubric[:100] if rubric else "计算题评分标准",
                "points_awarded": step.get("score", 0)
            }
            evidence_chain.append(evidence)
        
        return evidence_chain
    
    def _calculate_confidence(
        self,
        vision_result: dict,
        scoring_result: dict,
        previous_result: Optional[dict]
    ) -> float:
        """计算置信度
        
        Args:
            vision_result: 视觉提取结果
            scoring_result: 评分结果
            previous_result: 前序结果
            
        Returns:
            置信度分数
        """
        base_confidence = 0.85
        
        # 根据解题清晰度调整
        clarity = vision_result.get("work_clarity", "clear")
        if clarity == "partial":
            base_confidence -= 0.1
        elif clarity == "unclear":
            base_confidence -= 0.25
        
        # 根据步骤数量调整（步骤越多，越容易出错）
        step_count = len(scoring_result.get("step_scores", []))
        if step_count > 5:
            base_confidence -= 0.05
        
        # 二次评估一致性
        if previous_result:
            prev_score = previous_result.get("score", -1)
            curr_score = scoring_result.get("total_score", 0)
            if abs(prev_score - curr_score) < 0.5:
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
        
        # 整体评价
        overall = scoring_result.get("overall_feedback", "")
        if overall:
            feedback_parts.append(overall)
        
        # 各步骤反馈
        step_scores = scoring_result.get("step_scores", [])
        incorrect_steps = [s for s in step_scores if not s.get("is_correct", True)]
        
        if incorrect_steps:
            feedback_parts.append("\n需要改进的地方：")
            for step in incorrect_steps[:3]:  # 最多显示3个
                step_feedback = step.get("feedback", "")
                if step_feedback:
                    feedback_parts.append(f"- {step.get('step_name', '步骤')}: {step_feedback}")
        
        if not feedback_parts:
            total = scoring_result.get("total_score", 0)
            feedback_parts.append(f"得分：{total}分")
        
        return "\n".join(feedback_parts)
    
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
