"""批改智能体 - LangGraph 图定义"""

from typing import Literal, Optional, Callable
from langgraph.graph import StateGraph, END

from ..models.state import GradingState
from ..services.gemini_reasoning import GeminiReasoningClient
from ..utils.enhanced_checkpointer import EnhancedPostgresCheckpointer
from .nodes import (
    vision_extraction_node,
    rubric_mapping_node,
    critique_node,
    finalization_node
)


class GradingAgent:
    """
    批改智能体，使用 LangGraph 实现循环推理
    
    集成增强型检查点器，支持增量存储、压缩和 Temporal 心跳。
    
    验证：需求 1.2, 9.1
    """
    
    def __init__(
        self,
        reasoning_client: GeminiReasoningClient,
        checkpointer: Optional[EnhancedPostgresCheckpointer] = None,
        heartbeat_callback: Optional[Callable[[str, float], None]] = None
    ):
        """
        初始化批改智能体
        
        Args:
            reasoning_client: Gemini 推理客户端
            checkpointer: 增强型 PostgreSQL 检查点保存器（可选）
            heartbeat_callback: Temporal Activity 心跳回调（可选）
        """
        self.reasoning_client = reasoning_client
        self.checkpointer = checkpointer
        self.heartbeat_callback = heartbeat_callback
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """
        构建 LangGraph 图结构
        
        Returns:
            StateGraph: 编译后的图
        """
        # 创建图
        workflow = StateGraph(GradingState)
        
        # 添加节点（使用 async lambda）
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
        
        # 设置入口点
        workflow.set_entry_point("vision_extraction")
        
        # 添加边
        # vision -> rubric_mapping
        workflow.add_edge("vision_extraction", "rubric_mapping")
        
        # rubric_mapping -> critique
        workflow.add_edge("rubric_mapping", "critique")
        
        # critique -> 条件边（决定是否需要修正）
        workflow.add_conditional_edges(
            "critique",
            self._should_revise,
            {
                "revise": "rubric_mapping",  # 循环回到评分节点
                "finalize": "finalization"    # 继续到最终化
            }
        )
        
        # finalization -> END
        workflow.add_edge("finalization", END)
        
        # 编译图
        if self.checkpointer:
            return workflow.compile(checkpointer=self.checkpointer)
        else:
            return workflow.compile()
    
    def _should_revise(self, state: GradingState) -> Literal["revise", "finalize"]:
        """
        条件函数：决定是否需要修正
        
        根据需求 3.5：
        - 如果有反馈且 revision_count < 3 -> 循环回到评分节点
        - 否则 -> 继续到最终化节点
        
        Args:
            state: 当前状态
            
        Returns:
            str: "revise" 或 "finalize"
        """
        # 检查是否有错误
        if state.get("error"):
            return "finalize"
        
        # 检查是否有反思反馈
        critique_feedback = state.get("critique_feedback")
        revision_count = state.get("revision_count", 0)
        
        # 如果有反馈且修正次数 < 3，则修正
        if critique_feedback and revision_count < 3:
            return "revise"
        
        # 否则最终化
        return "finalize"
    
    async def run(
        self,
        question_image: str,
        rubric: str,
        max_score: float,
        standard_answer: str = None,
        thread_id: str = None
    ) -> GradingState:
        """
        运行批改智能体
        
        Args:
            question_image: Base64 编码的题目图像
            rubric: 评分细则
            max_score: 满分
            standard_answer: 标准答案（可选）
            thread_id: 线程 ID（用于检查点持久化）
            
        Returns:
            GradingState: 最终状态
        """
        # 初始化状态
        initial_state: GradingState = {
            "question_image": question_image,
            "rubric": rubric,
            "max_score": max_score,
            "standard_answer": standard_answer,
            "revision_count": 0,
            "is_finalized": False,
            "reasoning_trace": []
        }
        
        # 配置
        config = {}
        if thread_id and self.checkpointer:
            config["configurable"] = {"thread_id": thread_id}
        
        # 运行图
        result = await self.graph.ainvoke(initial_state, config=config)
        
        return result
