#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Production Workflow - 生产级工作流
实现完整的Orchestrator-Worker工作流图
符合设计文档: AI批改LangGraph Agent架构设计文档
"""

import logging
from typing import Dict, Any, List
from datetime import datetime

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .state import GradingState
from .agents.ingest_input import create_ingest_input_agent
from .agents.extract_via_mm import create_extract_via_mm_agent
from .agents.parse_rubric import create_parse_rubric_agent
from .agents.detect_questions import create_detect_questions_agent
from .agents.decide_batches import create_decide_batches_agent
from .agents.orchestrator_agent import OrchestratorAgent
from .agents.evaluate_batch import create_evaluate_batch_agent
from .agents.aggregate_results import create_aggregate_results_agent
from .agents.build_export_payload import create_build_export_payload_agent
from .agents.push_to_class_system import create_push_to_class_system_agent

logger = logging.getLogger(__name__)


class ProductionWorkflow:
    """
    生产级AI批改工作流
    
    特性:
    - Orchestrator-Worker模式
    - 批次并行处理
    - 双模式支持
    - 完整错误处理
    """
    
    def __init__(self):
        self.graph = None
        self.checkpointer = MemorySaver()
        self._build_workflow()
    
    def _build_workflow(self):
        """构建工作流图"""
        workflow = StateGraph(GradingState)
        
        # 添加所有节点
        workflow.add_node("ingest", create_ingest_input_agent())
        workflow.add_node("extract_mm", create_extract_via_mm_agent())
        workflow.add_node("parse_rubric", create_parse_rubric_agent())
        workflow.add_node("detect_questions", create_detect_questions_agent())
        workflow.add_node("decide_batches", create_decide_batches_agent())
        
        # Orchestrator-Worker 模式核心
        # workflow.add_node("orchestrator", create_orchestrator_agent())
        # workflow.add_node("evaluate_batch_worker", create_evaluate_batch_agent())
        
        # 临时使用模拟并行
        workflow.add_node("evaluate_batches", self._evaluate_all_batches)
        
        # 结果聚合和导出
        workflow.add_node("aggregate", create_aggregate_results_agent())
        workflow.add_node("build_export", create_build_export_payload_agent())
        workflow.add_node("push_to_class", create_push_to_class_system_agent(use_mock=True))
        
        # 设置完整流程
        workflow.set_entry_point("ingest")
        workflow.add_edge("ingest", "extract_mm")
        workflow.add_edge("extract_mm", "parse_rubric")
        workflow.add_edge("parse_rubric", "detect_questions")
        workflow.add_edge("detect_questions", "decide_batches")
        
        # 批次处理分支
        # TODO: 替换为真正的Orchestrator
        # workflow.add_conditional_edges("decide_batches", create_orchestrator_agent())
        workflow.add_edge("decide_batches", "evaluate_batches")
        
        # 结果处理流程
        workflow.add_edge("evaluate_batches", "aggregate")
        workflow.add_edge("aggregate", "build_export")
        workflow.add_edge("build_export", "push_to_class")
        workflow.add_edge("push_to_class", END)
        
        self.graph = workflow.compile(checkpointer=self.checkpointer)
        logger.info("完整生产工作流构建完成 - 包含导出和推送")
    
    async def _evaluate_all_batches(self, state: GradingState) -> GradingState:
        """评估所有批次（模拟并行）"""
        batches = state.get('batches', [])
        evaluations = []
        
        evaluate_agent = create_evaluate_batch_agent()
        
        # 模拟并行处理
        for batch in batches:
            batch_data = {
                'batch_index': batch['batch_index'],
                'questions': [q for q in state.get('questions', []) if q['qid'] in batch['question_ids']],
                'rubric_struct': state.get('rubric_struct', {}),
                'mm_tokens': state.get('mm_tokens', []),
                'mode': state.get('mode', 'professional')
            }
            
            batch_evals = await evaluate_agent(batch_data)
            evaluations.extend(batch_evals)
        
        state['evaluations'] = evaluations
        return state
    
    async def run(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """运行工作流"""
        config = {"configurable": {"thread_id": initial_state.get('task_id', 'default')}}
        
        final_state = None
        async for state in self.graph.astream(initial_state, config=config):
            final_state = state
        
        if final_state:
            result_key = list(final_state.keys())[0]
            return final_state[result_key]
        
        return initial_state


# 全局实例
_workflow = None

def get_production_workflow() -> ProductionWorkflow:
    """获取工作流实例"""
    global _workflow
    if _workflow is None:
        _workflow = ProductionWorkflow()
    return _workflow


async def run_production_grading(
    task_id: str,
    user_id: str,
    question_files: List[str],
    answer_files: List[str],
    marking_files: List[str] = None,
    mode: str = "professional"
) -> Dict[str, Any]:
    """运行生产级批改"""
    initial_state = {
        'task_id': task_id,
        'user_id': user_id,
        'timestamp': datetime.now(),
        'question_files': question_files,
        'answer_files': answer_files,
        'marking_files': marking_files or [],
        'mode': mode,
        'current_step': 'initializing',
        'progress_percentage': 0.0,
        'completion_status': 'in_progress',
        'errors': [],
        'step_results': {}
    }
    
    workflow = get_production_workflow()
    result = await workflow.run(initial_state)
    
    return result
