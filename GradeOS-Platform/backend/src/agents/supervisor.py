"""SupervisorAgent 总控调度智能体

负责分析题型并动态派生合适的批改智能体
"""

import json
import logging
from typing import Dict, Any, List, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from src.models.enums import QuestionType
from src.models.state import ContextPack, GradingState
from src.agents.base import BaseGradingAgent
from src.agents.pool import AgentPool, AgentNotFoundError
from src.utils.llm_thinking import get_thinking_kwargs
from src.config.models import get_lite_model


logger = logging.getLogger(__name__)


# 置信度阈值，低于此值触发二次评估
CONFIDENCE_THRESHOLD = 0.75


class SupervisorAgent:
    """总控调度智能体
    
    负责分析题型、选择合适的批改智能体、构建上下文包，
    并在置信度低时触发二次评估。
    
    Attributes:
        llm: Gemini 模型客户端
        agent_pool: 智能体池
    """
    
    def __init__(
        self,
        api_key: str,
        model_name: Optional[str] = None,
        agent_pool: Optional[AgentPool] = None
    ):
        """初始化 SupervisorAgent
        
        Args:
            api_key: Google AI API 密钥
            model_name: 用于题型分析的模型名称，默认使用全局配置
            agent_pool: 智能体池实例，如果不提供则使用全局单例
        """
        if model_name is None:
            model_name = get_lite_model()
        thinking_kwargs = get_thinking_kwargs(model_name, enable_thinking=True)
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=0.1,  # low temperature for consistent classification
            **thinking_kwargs,
        )
        self.agent_pool = agent_pool or AgentPool()
        self._api_key = api_key
    
    async def analyze_question_type(self, image_data: str) -> QuestionType:
        """分析题目图像，识别题型
        
        Args:
            image_data: Base64 编码的题目图像
            
        Returns:
            识别出的题型
        """
        prompt = """请分析这张题目图像，判断题目类型。

题目类型包括：
1. objective - 选择题或判断题（有明确的选项 A/B/C/D 或 对/错）
2. stepwise - 计算题（数学、物理等需要分步骤计算的题目）
3. essay - 作文或简答题（需要文字论述的题目）
4. lab_design - 实验设计题（需要设计实验方案的题目）
5. unknown - 无法识别的题型

请只返回题目类型的英文标识（如 objective、stepwise 等），不要返回其他内容。"""

        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": f"data:image/jpeg;base64,{image_data}"
                }
            ]
        )
        
        try:
            response = await self.llm.ainvoke([message])
            result_text = self._extract_text(response.content).strip().lower()
            
            # 映射到枚举
            type_mapping = {
                "objective": QuestionType.OBJECTIVE,
                "stepwise": QuestionType.STEPWISE,
                "essay": QuestionType.ESSAY,
                "lab_design": QuestionType.LAB_DESIGN,
                "unknown": QuestionType.UNKNOWN,
            }
            
            question_type = type_mapping.get(result_text, QuestionType.UNKNOWN)
            logger.info(f"题型分析结果: {question_type.value}")
            return question_type
            
        except Exception as e:
            logger.error(f"题型分析失败: {e}")
            return QuestionType.UNKNOWN
    
    def select_agent(self, question_type: QuestionType) -> BaseGradingAgent:
        """从 AgentPool 选择合适的智能体
        
        Args:
            question_type: 题目类型
            
        Returns:
            能够处理该题型的批改智能体
            
        Raises:
            AgentNotFoundError: 如果没有找到合适的智能体
        """
        return self.agent_pool.get_agent(question_type)
    
    def build_context_pack(
        self,
        question_image: str,
        question_type: QuestionType,
        rubric: str,
        max_score: float,
        standard_answer: Optional[str] = None,
        terminology: Optional[List[str]] = None,
        previous_result: Optional[Dict[str, Any]] = None
    ) -> ContextPack:
        """构建上下文包
        
        Args:
            question_image: Base64 编码的题目图像
            question_type: 题目类型
            rubric: 评分细则
            max_score: 满分
            standard_answer: 标准答案（可选）
            terminology: 相关术语列表（可选）
            previous_result: 前序智能体输出（二次评估时使用）
            
        Returns:
            构建好的上下文包
        """
        context_pack: ContextPack = {
            "question_image": question_image,
            "question_type": question_type,
            "rubric": rubric,
            "max_score": max_score,
        }
        
        if standard_answer is not None:
            context_pack["standard_answer"] = standard_answer
        
        if terminology is not None:
            context_pack["terminology"] = terminology
        else:
            context_pack["terminology"] = []
        
        if previous_result is not None:
            context_pack["previous_result"] = previous_result
        
        return context_pack
    
    async def spawn_and_grade(self, context_pack: ContextPack) -> GradingState:
        """派生智能体并执行批改
        
        根据上下文包中的题型选择合适的智能体，执行批改，
        并在置信度低时自动触发二次评估。
        
        Args:
            context_pack: 上下文包
            
        Returns:
            批改结果状态
        """
        question_type = context_pack.get("question_type", QuestionType.UNKNOWN)
        
        try:
            # 选择智能体
            agent = self.select_agent(question_type)
            logger.info(f"选择智能体: {agent.agent_type} 处理题型: {question_type.value}")
            
            # 执行批改
            result = await agent.grade(context_pack)
            
            # 检查是否需要二次评估
            confidence = result.get("confidence", 0.0)
            if confidence < CONFIDENCE_THRESHOLD:
                logger.info(
                    f"置信度 {confidence:.2f} 低于阈值 {CONFIDENCE_THRESHOLD}，"
                    "触发二次评估"
                )
                result = await self.secondary_review(context_pack, result)
            
            return result
            
        except AgentNotFoundError as e:
            logger.error(f"找不到合适的智能体: {e}")
            # 返回需要人工审核的状态
            return GradingState(
                context_pack=context_pack,
                final_score=0.0,
                max_score=context_pack.get("max_score", 0.0),
                confidence=0.0,
                agent_type="unknown",
                is_finalized=False,
                needs_secondary_review=True,
                error=str(e),
                vision_analysis="",
                rubric_mapping=[],
                reasoning_trace=[f"错误: {e}"],
                evidence_chain=[],
                visual_annotations=[],
                student_feedback="无法自动批改，需要人工审核",
                revision_count=0,
            )
    
    async def secondary_review(
        self,
        context_pack: ContextPack,
        initial_result: GradingState
    ) -> GradingState:
        """二次评估
        
        当初次批改置信度低时触发，使用不同的智能体或策略进行复核。
        
        Args:
            context_pack: 上下文包
            initial_result: 初次批改结果
            
        Returns:
            二次评估后的结果
        """
        logger.info("开始二次评估")
        
        # 将初次结果作为参考传递给二次评估
        context_pack_with_previous = self.build_context_pack(
            question_image=context_pack.get("question_image", ""),
            question_type=context_pack.get("question_type", QuestionType.UNKNOWN),
            rubric=context_pack.get("rubric", ""),
            max_score=context_pack.get("max_score", 0.0),
            standard_answer=context_pack.get("standard_answer"),
            terminology=context_pack.get("terminology"),
            previous_result={
                "score": initial_result.get("final_score", 0.0),
                "confidence": initial_result.get("confidence", 0.0),
                "vision_analysis": initial_result.get("vision_analysis", ""),
                "rubric_mapping": initial_result.get("rubric_mapping", []),
                "reasoning_trace": initial_result.get("reasoning_trace", []),
            }
        )
        
        question_type = context_pack.get("question_type", QuestionType.UNKNOWN)
        
        try:
            # 尝试使用同一智能体进行二次评估
            agent = self.select_agent(question_type)
            secondary_result = await agent.grade(context_pack_with_previous)
            
            # 标记为经过二次评估
            secondary_result["needs_secondary_review"] = False
            
            # 如果二次评估置信度仍然低，标记需要人工审核
            if secondary_result.get("confidence", 0.0) < CONFIDENCE_THRESHOLD:
                secondary_result["needs_secondary_review"] = True
                logger.warning(
                    f"二次评估置信度仍然较低: {secondary_result.get('confidence', 0.0):.2f}"
                )
            
            # 合并推理轨迹
            initial_trace = initial_result.get("reasoning_trace", [])
            secondary_trace = secondary_result.get("reasoning_trace", [])
            secondary_result["reasoning_trace"] = (
                initial_trace + ["--- 二次评估 ---"] + secondary_trace
            )
            
            return secondary_result
            
        except AgentNotFoundError as e:
            logger.error(f"二次评估失败: {e}")
            # 返回初次结果，但标记需要人工审核
            initial_result["needs_secondary_review"] = True
            return initial_result
    
    def _extract_text(self, content: Any) -> str:
        """从响应中提取文本内容"""
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict):
                    text_parts.append(item.get('text', ''))
                else:
                    text_parts.append(str(item))
            return '\n'.join(text_parts)
        return str(content)
