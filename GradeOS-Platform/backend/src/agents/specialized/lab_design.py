"""LabDesignAgent - 实验设计题批改智能体

评估实验方案的完整性和科学性，生成证据链
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


# 实验设计评分维度
LAB_DESIGN_DIMENSIONS = [
    {"name": "实验目的", "weight": 0.1, "description": "目的明确、与题目要求一致"},
    {"name": "实验原理", "weight": 0.15, "description": "原理正确、表述清晰"},
    {"name": "实验器材", "weight": 0.1, "description": "器材选择合理、完整"},
    {"name": "实验步骤", "weight": 0.25, "description": "步骤完整、顺序合理、可操作性强"},
    {"name": "变量控制", "weight": 0.2, "description": "自变量、因变量、控制变量明确"},
    {"name": "数据处理", "weight": 0.1, "description": "数据记录表格设计合理、处理方法正确"},
    {"name": "安全规范", "weight": 0.1, "description": "注意事项完整、安全意识强"},
]


class LabDesignAgent(BaseGradingAgent):
    """实验设计题批改智能体
    
    专门处理物理、化学、生物等学科的实验设计题。
    评估实验方案的完整性、科学性和可操作性。
    
    特点：
    - 多维度评估（目的、原理、器材、步骤、变量控制等）
    - 科学性验证
    - 安全规范检查
    - 生成完整证据链
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        """初始化 LabDesignAgent
        
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
        return "lab_design"
    
    @property
    def supported_question_types(self) -> List[QuestionType]:
        return [QuestionType.LAB_DESIGN]
    
    async def grade(self, context_pack: ContextPack) -> GradingState:
        """执行实验设计题批改
        
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
        terminology = context_pack.get("terminology", [])
        
        reasoning_trace: List[str] = []
        
        try:
            # 步骤1：视觉提取 - 识别实验设计内容
            reasoning_trace.append("开始视觉提取：识别实验设计方案")
            vision_analysis = await self._extract_lab_design(
                question_image, rubric, terminology
            )
            reasoning_trace.append(f"视觉提取完成：识别到 {len(vision_analysis.get('components', {}))} 个组成部分")
            
            # 步骤2：科学性验证
            reasoning_trace.append("开始科学性验证")
            validation_result = await self._validate_scientific_rigor(
                vision_analysis, rubric, standard_answer
            )
            reasoning_trace.append(f"科学性验证完成：{validation_result.get('overall_validity', 'unknown')}")
            
            # 步骤3：多维度评分
            reasoning_trace.append("开始多维度评分")
            scoring_result = await self._score_lab_design(
                vision_analysis, validation_result, rubric, max_score, standard_answer
            )
            reasoning_trace.append(f"评分完成：总分 {scoring_result['total_score']}/{max_score}")
            
            # 步骤4：生成证据链
            evidence_chain = self._build_evidence_chain(
                scoring_result.get("dimension_scores", []),
                rubric
            )
            
            # 步骤5：计算置信度
            confidence = self._calculate_confidence(
                vision_analysis, scoring_result, previous_result
            )
            reasoning_trace.append(f"置信度：{confidence:.2f}")
            
            # 步骤6：生成学生反馈
            student_feedback = self._generate_feedback(scoring_result, validation_result)
            
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
            visual_annotations = self._build_visual_annotations(
                vision_analysis, scoring_result
            )
            
            return GradingState(
                context_pack=context_pack,
                vision_analysis=json.dumps(vision_analysis.get("components", {}), ensure_ascii=False),
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
            logger.error(f"LabDesignAgent 批改失败: {e}")
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
    
    async def _extract_lab_design(
        self,
        question_image: str,
        rubric: str,
        terminology: List[str]
    ) -> dict:
        """从图像中提取实验设计内容
        
        Args:
            question_image: Base64 编码的题目图像
            rubric: 评分细则
            terminology: 相关术语
            
        Returns:
            包含实验设计各部分的字典
        """
        terminology_text = "、".join(terminology) if terminology else "无特定术语"
        
        prompt = f"""请分析这张实验设计题的答题图像，提取学生的实验设计方案。

评分细则：
{rubric}

相关术语：{terminology_text}

请返回 JSON 格式：
{{
    "components": {{
        "purpose": {{
            "content": "实验目的内容",
            "location": [ymin, xmin, ymax, xmax],
            "is_present": true/false
        }},
        "principle": {{
            "content": "实验原理内容",
            "location": [ymin, xmin, ymax, xmax],
            "is_present": true/false
        }},
        "materials": {{
            "content": "实验器材列表",
            "items": ["器材1", "器材2", ...],
            "location": [ymin, xmin, ymax, xmax],
            "is_present": true/false
        }},
        "procedure": {{
            "content": "实验步骤内容",
            "steps": ["步骤1", "步骤2", ...],
            "location": [ymin, xmin, ymax, xmax],
            "is_present": true/false
        }},
        "variables": {{
            "independent": "自变量",
            "dependent": "因变量",
            "controlled": ["控制变量1", ...],
            "location": [ymin, xmin, ymax, xmax],
            "is_present": true/false
        }},
        "data_table": {{
            "content": "数据记录表描述",
            "location": [ymin, xmin, ymax, xmax],
            "is_present": true/false
        }},
        "safety": {{
            "content": "安全注意事项",
            "location": [ymin, xmin, ymax, xmax],
            "is_present": true/false
        }}
    }},
    "overall_completeness": "complete/partial/incomplete",
    "diagram_present": true/false,
    "readability": "high/medium/low"
}}

注意：
- 识别实验设计的各个组成部分
- 标注每个部分的位置
- 评估方案的完整性
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
                "components": {},
                "overall_completeness": "incomplete",
                "diagram_present": False,
                "readability": "low"
            }
    
    async def _validate_scientific_rigor(
        self,
        vision_analysis: dict,
        rubric: str,
        standard_answer: str
    ) -> dict:
        """验证实验设计的科学性
        
        Args:
            vision_analysis: 视觉分析结果
            rubric: 评分细则
            standard_answer: 标准答案
            
        Returns:
            科学性验证结果
        """
        components = vision_analysis.get("components", {})
        
        prompt = f"""请验证以下实验设计方案的科学性。

实验设计内容：
{json.dumps(components, ensure_ascii=False, indent=2)}

评分细则：
{rubric}

参考答案：
{standard_answer if standard_answer else "未提供"}

请从以下方面验证并返回 JSON 格式：
{{
    "overall_validity": "valid/partially_valid/invalid",
    "principle_correct": true/false,
    "principle_issues": ["问题1", ...],
    "procedure_feasible": true/false,
    "procedure_issues": ["问题1", ...],
    "variable_control_proper": true/false,
    "variable_issues": ["问题1", ...],
    "safety_adequate": true/false,
    "safety_issues": ["问题1", ...],
    "scientific_errors": [
        {{
            "error": "错误描述",
            "severity": "critical/major/minor",
            "suggestion": "修正建议"
        }}
    ]
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
            logger.warning(f"无法解析科学性验证结果: {result_text}")
            return {
                "overall_validity": "partially_valid",
                "principle_correct": True,
                "procedure_feasible": True,
                "variable_control_proper": True,
                "safety_adequate": True,
                "scientific_errors": []
            }
    
    async def _score_lab_design(
        self,
        vision_analysis: dict,
        validation_result: dict,
        rubric: str,
        max_score: float,
        standard_answer: str
    ) -> dict:
        """对实验设计进行多维度评分
        
        Args:
            vision_analysis: 视觉分析结果
            validation_result: 科学性验证结果
            rubric: 评分细则
            max_score: 满分
            standard_answer: 标准答案
            
        Returns:
            评分结果
        """
        components = vision_analysis.get("components", {})
        
        # 构建评分提示
        dimensions_text = "\n".join([
            f"- {d['name']}（权重{d['weight']*100}%）: {d['description']}"
            for d in LAB_DESIGN_DIMENSIONS
        ])
        
        prompt = f"""请对以下实验设计方案进行多维度评分。

实验设计内容：
{json.dumps(components, ensure_ascii=False, indent=2)}

科学性验证结果：
{json.dumps(validation_result, ensure_ascii=False, indent=2)}

评分细则：
{rubric}

参考答案：
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
            "evidence": "评分依据",
            "feedback": "该维度的评价"
        }}
    ],
    "strengths": ["优点1", "优点2", ...],
    "weaknesses": ["不足1", "不足2", ...],
    "overall_comment": "整体评语",
    "improvement_suggestions": ["建议1", "建议2", ...]
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
            return {
                "total_score": max_score * 0.5,
                "dimension_scores": [],
                "strengths": [],
                "weaknesses": [],
                "overall_comment": "评分解析失败，需要人工审核",
                "improvement_suggestions": []
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
                "image_region": [0, 0, 1000, 1000],
                "text_description": dim.get("evidence", ""),
                "reasoning": dim.get("feedback", ""),
                "rubric_reference": rubric[:100] if rubric else "实验设计评分标准",
                "points_awarded": dim.get("score", 0)
            }
            evidence_chain.append(evidence)
        
        return evidence_chain
    
    def _build_visual_annotations(
        self,
        vision_analysis: dict,
        scoring_result: dict
    ) -> List[Dict[str, Any]]:
        """构建视觉标注
        
        Args:
            vision_analysis: 视觉分析结果
            scoring_result: 评分结果
            
        Returns:
            视觉标注列表
        """
        annotations = []
        components = vision_analysis.get("components", {})
        
        # 为每个组成部分添加标注
        component_names = {
            "purpose": "实验目的",
            "principle": "实验原理",
            "materials": "实验器材",
            "procedure": "实验步骤",
            "variables": "变量控制",
            "data_table": "数据记录",
            "safety": "安全注意事项"
        }
        
        for key, name in component_names.items():
            comp = components.get(key, {})
            if comp.get("is_present", False):
                annotations.append({
                    "type": "component_region",
                    "bounding_box": comp.get("location", [0, 0, 1000, 1000]),
                    "label": name,
                    "is_present": True
                })
        
        return annotations
    
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
        base_confidence = 0.80
        
        # 根据完整性调整
        completeness = vision_analysis.get("overall_completeness", "incomplete")
        if completeness == "complete":
            base_confidence += 0.05
        elif completeness == "incomplete":
            base_confidence -= 0.15
        
        # 根据可读性调整
        readability = vision_analysis.get("readability", "medium")
        if readability == "low":
            base_confidence -= 0.1
        
        # 根据组件识别数量调整
        components = vision_analysis.get("components", {})
        present_count = sum(1 for c in components.values() if c.get("is_present", False))
        if present_count < 3:
            base_confidence -= 0.1
        
        # 二次评估一致性
        if previous_result:
            prev_score = previous_result.get("score", -1)
            curr_score = scoring_result.get("total_score", 0)
            max_score = scoring_result.get("max_score", 100)
            if abs(prev_score - curr_score) < max_score * 0.1:
                base_confidence = min(1.0, base_confidence + 0.1)
            else:
                base_confidence -= 0.1
        
        return max(0.0, min(1.0, base_confidence))
    
    def _generate_feedback(
        self,
        scoring_result: dict,
        validation_result: dict
    ) -> str:
        """生成学生反馈
        
        Args:
            scoring_result: 评分结果
            validation_result: 科学性验证结果
            
        Returns:
            反馈文本
        """
        feedback_parts = []
        
        # 整体评语
        overall = scoring_result.get("overall_comment", "")
        if overall:
            feedback_parts.append(overall)
        
        # 优点
        strengths = scoring_result.get("strengths", [])
        if strengths:
            feedback_parts.append("\n\n✅ 优点：")
            for s in strengths[:3]:
                feedback_parts.append(f"- {s}")
        
        # 不足
        weaknesses = scoring_result.get("weaknesses", [])
        if weaknesses:
            feedback_parts.append("\n\n⚠️ 需要改进：")
            for w in weaknesses[:3]:
                feedback_parts.append(f"- {w}")
        
        # 科学性问题
        errors = validation_result.get("scientific_errors", [])
        critical_errors = [e for e in errors if e.get("severity") == "critical"]
        if critical_errors:
            feedback_parts.append("\n\n❌ 重要科学性问题：")
            for e in critical_errors[:2]:
                feedback_parts.append(f"- {e.get('error', '')}")
                if e.get("suggestion"):
                    feedback_parts.append(f"  建议：{e.get('suggestion')}")
        
        # 改进建议
        suggestions = scoring_result.get("improvement_suggestions", [])
        if suggestions:
            feedback_parts.append("\n\n💡 改进建议：")
            for s in suggestions[:3]:
                feedback_parts.append(f"- {s}")
        
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
