"""Enhanced grading agent with optional learning components."""

import logging
from typing import Literal, Optional, Callable, Dict, Any, List
from datetime import datetime
from uuid import uuid4

from langgraph.graph import StateGraph, END

from src.models.state import GradingState
from src.models.grading_log import GradingLog
from src.services.llm_reasoning import LLMReasoningClient
from src.utils.enhanced_checkpointer import EnhancedPostgresCheckpointer
from src.services.exemplar_memory import ExemplarMemory
from src.services.prompt_assembler import PromptAssembler
from src.services.calibration import CalibrationService
from src.services.grading_logger import GradingLogger
from src.agents.nodes import (
    vision_extraction_node,
    rubric_mapping_node,
    critique_node,
    finalization_node
)


logger = logging.getLogger(__name__)


class EnhancedGradingAgent:
    """Enhanced grading agent with optional learning components."""

    def __init__(
        self,
        reasoning_client: LLMReasoningClient,
        exemplar_memory: Optional[ExemplarMemory] = None,
        prompt_assembler: Optional[PromptAssembler] = None,
        calibration_service: Optional[CalibrationService] = None,
        grading_logger: Optional[GradingLogger] = None,
        checkpointer: Optional[EnhancedPostgresCheckpointer] = None,
        heartbeat_callback: Optional[Callable[[str, float], None]] = None,
    ):
        """Initialize the enhanced grading agent."""
        self.reasoning_client = reasoning_client
        self.exemplar_memory = exemplar_memory or ExemplarMemory()
        self.prompt_assembler = prompt_assembler or PromptAssembler()
        self.calibration_service = calibration_service or CalibrationService()
        self.grading_logger = grading_logger or GradingLogger()
        self.checkpointer = checkpointer
        self.heartbeat_callback = heartbeat_callback
        self.graph = self._build_graph()
        
        logger.info("EnhancedGradingAgent initialized")
    
    def _build_graph(self) -> StateGraph:
        """
        构建 LangGraph 图结?
        
        Returns:
            StateGraph: 编译后的?
        """
        # 创建?
        workflow = StateGraph(GradingState)
        
        # 添加节点（使?async lambda?
        async def _vision_node(state):
            return await vision_extraction_node(state, self.reasoning_client)
        
        async def _rubric_node(state):
            return await rubric_mapping_node(state, self.reasoning_client)
        
        async def _critique_node(state):
            return await critique_node(state, self.reasoning_client)
        
        workflow.add_node("vision_extraction", _vision_node)
        workflow.add_node("rubric_mapping", _rubric_node)
        workflow.add_node("critique", _critique_node)
        workflow.add_node("finalization", finalization_node)
        
        # 设置入口?
        workflow.set_entry_point("vision_extraction")
        
        # 添加?
        workflow.add_edge("vision_extraction", "rubric_mapping")
        workflow.add_edge("rubric_mapping", "critique")
        
        # critique -> 条件边（决定是否需要修正）
        workflow.add_conditional_edges(
            "critique",
            self._should_revise,
            {
                "revise": "rubric_mapping",
                "finalize": "finalization"
            }
        )
        
        # finalization -> END
        workflow.add_edge("finalization", END)
        
        # 编译?
        if self.checkpointer:
            return workflow.compile(checkpointer=self.checkpointer)
        else:
            return workflow.compile()
    
    def _should_revise(self, state: GradingState) -> Literal["revise", "finalize"]:
        """
        条件函数：决定是否需要修?
        
        Args:
            state: 当前状?
            
        Returns:
            str: "revise" ?"finalize"
        """
        if state.get("error"):
            return "finalize"
        
        critique_feedback = state.get("critique_feedback")
        revision_count = state.get("revision_count", 0)
        
        if critique_feedback and revision_count < 3:
            return "revise"
        
        return "finalize"
    
    async def run(
        self,
        question_image: str,
        rubric: str,
        max_score: float,
        question_type: str,
        question_id: str,
        submission_id: str,
        teacher_id: str,
        standard_answer: str = None,
        thread_id: str = None,
        previous_confidence: Optional[float] = None,
        error_patterns: Optional[List[str]] = None
    ) -> GradingState:
        """
        运行增强版批改智能体
        
        集成自我成长组件的完整流程：
        1. 检索相似判例（ExemplarMemory?
        2. 加载教师校准配置（CalibrationService?
        3. 动态拼装提示词（PromptAssembler?
        4. 执行批改（LangGraph?
        5. 应用校准规则
        6. 记录批改日志（GradingLogger?
        
        Args:
            question_image: Base64 编码的题目图?
            rubric: 评分细则
            max_score: 满分
            question_type: 题目类型
            question_id: 题目 ID
            submission_id: 提交 ID
            teacher_id: 教师 ID
            standard_answer: 标准答案（可选）
            thread_id: 线程 ID（用于检查点持久化）
            previous_confidence: 上一次置信度（可选）
            error_patterns: 错误模式列表（可选）
            
        Returns:
            GradingState: 最终状?
        """
        log_id = str(uuid4())
        
        try:
            # ===== Step 1: retrieve similar exemplars =====
            logger.info(f"Retrieving exemplar cases: question_type={question_type}")
            exemplars = await self.exemplar_memory.retrieve_similar(
                question_image_hash=question_image[:64],  # 使用图像?4字符作为哈希
                question_type=question_type,
                top_k=5,
                min_similarity=0.7
            )
            logger.info(f"Retrieved {len(exemplars)} exemplar cases")
            
            # ===== Step 2: load teacher calibration profile =====
            logger.info(f"Loading calibration profile: teacher_id={teacher_id}")
            calibration_profile = await self.calibration_service.get_or_create_profile(
                teacher_id=teacher_id
            )
            logger.info(
                f"Calibration profile loaded: strictness_level={calibration_profile.strictness_level}"
            )
            
            # ===== Step 3: assemble prompt =====
            logger.info("Assembling prompt")
            assembled_prompt = self.prompt_assembler.assemble(
                question_type=question_type,
                rubric=rubric,
                exemplars=exemplars,
                error_patterns=error_patterns,
                previous_confidence=previous_confidence,
                calibration={
                    "deduction_rules": calibration_profile.deduction_rules,
                    "tolerance_rules": [rule.model_dump() for rule in calibration_profile.tolerance_rules],
                    "strictness_level": calibration_profile.strictness_level
                },
                max_tokens=8000
            )
            
            logger.info(
                f"提示词拼装完? "
                f"total_tokens={assembled_prompt.total_tokens}, "
                f"truncated_sections={len(assembled_prompt.truncated_sections)}"
            )
            
            # ===== 第四步：初始化状?=====
            initial_state: GradingState = {
                "question_image": question_image,
                "rubric": rubric,
                "max_score": max_score,
                "standard_answer": standard_answer,
                "revision_count": 0,
                "is_finalized": False,
                "reasoning_trace": [],
                # 添加增强字段
                "assembled_prompt": assembled_prompt.sections,
                "exemplars": [e.model_dump() for e in exemplars],
                "calibration_profile": calibration_profile.model_dump(),
                "question_type": question_type,
                "question_id": question_id,
                "submission_id": submission_id,
                "teacher_id": teacher_id
            }
            
            # ===== Step 5: run grading graph =====
            config = {}
            if thread_id and self.checkpointer:
                config["configurable"] = {"thread_id": thread_id}
            
            logger.info("Running grading graph")
            result = await self.graph.ainvoke(initial_state, config=config)
            logger.info("Grading graph completed")
            
            # ===== 第六步：应用校准规则 =====
            if result.get("student_answer") and standard_answer:
                is_equivalent = self.calibration_service.apply_tolerance(
                    student_answer=result["student_answer"],
                    standard_answer=standard_answer,
                    profile=calibration_profile
                )
                
                if is_equivalent and result.get("score", 0) < max_score:
                    logger.info("Tolerance applied: equivalent answer, adjusted to full score")
                    result["score"] = max_score
                    result["reasoning_trace"].append("Tolerance applied: equivalent answer")
            
            # ===== 第七步：生成评语 =====
            if result.get("score") is not None:
                score_ratio = result["score"] / max_score
                
                if score_ratio >= 0.9:
                    scenario = "correct"
                    context = {}
                elif score_ratio >= 0.5:
                    scenario = "partial_correct"
                    context = {"reason": result.get("critique_feedback", "部分正确")}
                else:
                    scenario = "incorrect"
                    context = {"reason": result.get("critique_feedback", "答案错误")}
                
                feedback = self.calibration_service.generate_feedback(
                    scenario=scenario,
                    context=context,
                    profile=calibration_profile
                )
                
                result["teacher_feedback"] = feedback
            
            # ===== 第八步：记录批改日志 =====
            logger.info("记录批改日志")
            grading_log = GradingLog(
                log_id=log_id,
                submission_id=submission_id,
                question_id=question_id,
                timestamp=datetime.now(),
                # 提取阶段
                extracted_answer=result.get("student_answer", ""),
                extraction_confidence=result.get("confidence", 0.0),
                evidence_snippets=result.get("evidence_snippets", []),
                # 规范化阶?
                normalized_answer=result.get("normalized_answer"),
                normalization_rules_applied=result.get("normalization_rules", []),
                # 匹配阶段
                match_result=result.get("match_result", False),
                match_failure_reason=result.get("match_failure_reason"),
                # 评分阶段
                score=result.get("score", 0.0),
                max_score=max_score,
                confidence=result.get("confidence", 0.0),
                reasoning_trace=result.get("reasoning_trace", []),
                # 改判信息
                was_overridden=False
            )
            
            await self.grading_logger.log_grading(grading_log)
            logger.info(f"批改日志已记? log_id={log_id}")
            
            # 添加日志 ID 到结?
            result["log_id"] = log_id
            
            return result
            
        except Exception as e:
            logger.error(f"批改失败: {e}", exc_info=True)
            
            # 记录错误日志
            try:
                error_log = GradingLog(
                    log_id=log_id,
                    submission_id=submission_id,
                    question_id=question_id,
                    timestamp=datetime.now(),
                    extracted_answer="",
                    extraction_confidence=0.0,
                    evidence_snippets=[],
                    score=0.0,
                    max_score=max_score,
                    confidence=0.0,
                    reasoning_trace=[f"批改失败: {str(e)}"],
                    was_overridden=False
                )
                await self.grading_logger.log_grading(error_log)
            except Exception as log_error:
                logger.error(f"记录错误日志失败: {log_error}")
            
            raise
    
    async def log_override(
        self,
        log_id: str,
        override_score: float,
        override_reason: str,
        teacher_id: str
    ) -> bool:
        """
        记录改判信息
        
        Args:
            log_id: 日志 ID
            override_score: 改判后的分数
            override_reason: 改判原因
            teacher_id: 改判教师 ID
            
        Returns:
            是否成功记录
        """
        return await self.grading_logger.log_override(
            log_id=log_id,
            override_score=override_score,
            override_reason=override_reason,
            teacher_id=teacher_id
        )
