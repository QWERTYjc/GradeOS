"""试卷批改 Graph 编译

使用现有节点（src/graphs/nodes/）组装完整的试卷批改流程。
包含人工审核中断机制（interrupt + resume）。

验证：需求 2.1, 2.2, 2.3, 5.1, 5.2, 5.3
"""

import logging
from typing import Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from src.graphs.state import GradingGraphState
from src.graphs.nodes.segment import segment_node
from src.graphs.nodes.grade import grade_node
from src.graphs.nodes.persist import persist_node
from src.graphs.nodes.notify import notify_node
from src.graphs.nodes.review import (
    review_check_node,
    review_interrupt_node,
    apply_review_node,
    should_interrupt_for_review,
    should_continue_after_review
)


logger = logging.getLogger(__name__)


def create_exam_paper_graph(
    checkpointer: Optional[AsyncPostgresSaver] = None,
    interrupt_before: Optional[list] = None,
    interrupt_after: Optional[list] = None
) -> StateGraph:
    """创建试卷批改 Graph
    
    组装完整的批改流程：
    1. segment: 文档分割（识别题目边界）
    2. grade: 批改（调用 GradingAgent + 缓存）
    3. review_check: 检查是否需要人工审核
    4. review_interrupt: 触发人工审核中断（可选）
    5. apply_review: 应用审核结果
    6. persist: 持久化（保存到数据库）
    7. notify: 通知（发送通知给教师）
    
    流程图：
    ```
    segment → grade → review_check
                          ↓
              ┌──────────┴──────────┐
              ↓                     ↓
        (needs_review)        (no_review)
              ↓                     ↓
      review_interrupt         persist
              ↓                     ↓
        apply_review            notify
              ↓                     ↓
        ┌─────┴─────┐             END
        ↓           ↓
    (REJECT)    (APPROVE/OVERRIDE)
        ↓           ↓
       END       persist → notify → END
    ```
    
    Args:
        checkpointer: PostgreSQL Checkpointer（可选）
        interrupt_before: 在这些节点前中断（调试用）
        interrupt_after: 在这些节点后中断（调试用）
        
    Returns:
        编译后的 Graph
        
    验证：需求 2.1, 2.2, 2.3, 5.1, 5.2, 5.3
    """
    logger.info("创建试卷批改 Graph（含人工审核）")
    
    # 创建 Graph
    graph = StateGraph(GradingGraphState)
    
    # ===== 添加节点 =====
    # 核心批改节点
    graph.add_node("segment", segment_node)
    graph.add_node("grade", grade_node)
    
    # 人工审核节点
    graph.add_node("review_check", review_check_node)
    graph.add_node("review_interrupt", review_interrupt_node)
    graph.add_node("apply_review", apply_review_node)
    
    # 持久化和通知节点
    graph.add_node("persist", persist_node)
    graph.add_node("notify", notify_node)
    
    # ===== 添加边 =====
    # 入口点
    graph.set_entry_point("segment")
    
    # 核心流程
    graph.add_edge("segment", "grade")
    graph.add_edge("grade", "review_check")
    
    # 审核检查后的条件路由
    graph.add_conditional_edges(
        "review_check",
        should_interrupt_for_review,
        {
            "review_interrupt": "review_interrupt",
            "persist": "persist"
        }
    )
    
    # 审核中断后应用结果
    graph.add_edge("review_interrupt", "apply_review")
    
    # 审核结果后的条件路由
    graph.add_conditional_edges(
        "apply_review",
        should_continue_after_review,
        {
            "persist": "persist",
            "end": END
        }
    )
    
    # 持久化后通知
    graph.add_edge("persist", "notify")
    
    # 通知后结束
    graph.add_edge("notify", END)
    
    # ===== 编译 Graph =====
    compile_kwargs = {}
    
    if checkpointer:
        compile_kwargs["checkpointer"] = checkpointer
    
    if interrupt_before:
        compile_kwargs["interrupt_before"] = interrupt_before
    
    if interrupt_after:
        compile_kwargs["interrupt_after"] = interrupt_after
    
    compiled_graph = graph.compile(**compile_kwargs)
    
    logger.info("试卷批改 Graph 已编译（含人工审核）")
    
    return compiled_graph


def create_simple_exam_paper_graph(
    checkpointer: Optional[AsyncPostgresSaver] = None
) -> StateGraph:
    """创建简化版试卷批改 Graph（无人工审核）
    
    适用于高置信度场景或测试环境。
    
    流程：segment → grade → persist → notify → END
    
    Args:
        checkpointer: PostgreSQL Checkpointer（可选）
        
    Returns:
        编译后的 Graph
    """
    logger.info("创建简化版试卷批改 Graph")
    
    graph = StateGraph(GradingGraphState)
    
    # 添加节点
    graph.add_node("segment", segment_node)
    graph.add_node("grade", grade_node)
    graph.add_node("persist", persist_node)
    graph.add_node("notify", notify_node)
    
    # 添加边
    graph.set_entry_point("segment")
    graph.add_edge("segment", "grade")
    graph.add_edge("grade", "persist")
    graph.add_edge("persist", "notify")
    graph.add_edge("notify", END)
    
    # 编译
    compile_kwargs = {}
    if checkpointer:
        compile_kwargs["checkpointer"] = checkpointer
    
    compiled_graph = graph.compile(**compile_kwargs)
    
    logger.info("简化版试卷批改 Graph 已编译")
    
    return compiled_graph
