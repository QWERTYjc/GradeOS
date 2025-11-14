#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多模态批改工作流 - workflow_multimodal.py (重构版)
特性：
1. 深度协作的8个Agent架构
2. 基于学生的批次管理
3. Token极致优化（一次理解，多次使用）
4. 并行处理策略
"""

import logging
from typing import Dict, Any
from datetime import datetime

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .state import GradingState

# 🆕 导入深度协作的Agent
from .agents.orchestrator_agent import OrchestratorAgent
from .agents.student_detection_agent import StudentDetectionAgent
from .agents.batch_planning_agent import BatchPlanningAgent
from .agents.rubric_master_agent import RubricMasterAgent
from .agents.question_context_agent import QuestionContextAgent
from .agents.grading_worker_agent import GradingWorkerAgent
from .agents.result_aggregator_agent import ResultAggregatorAgent
from .agents.class_analysis_agent import ClassAnalysisAgent

# 保留现有的理解Agent（与新架构兼容）
from .agents.multimodal_input_agent import MultiModalInputAgent
from .agents.question_understanding_agent import QuestionUnderstandingAgent
from .agents.answer_understanding_agent import AnswerUnderstandingAgent
from .agents.rubric_interpreter_agent import RubricInterpreterAgent

logger = logging.getLogger(__name__)


class MultiModalGradingWorkflow:
    """
    多模态批改工作流（重构版）
    
    执行流程（深度协作架构）：
    0. OrchestratorAgent - 任务编排
    1. MultiModalInputAgent - 多模态文件处理
    2. 并行执行：
       - QuestionUnderstandingAgent - 题目理解
       - AnswerUnderstandingAgent - 答案理解
       - RubricInterpreterAgent - 评分标准解析
    3. StudentDetectionAgent - 学生信息识别（可选）
    4. BatchPlanningAgent - 批次规划
    5. RubricMasterAgent - 评分标准主控（生成压缩包）
    6. QuestionContextAgent - 题目上下文（生成压缩包）
    7. GradingWorkerAgent - 批改工作（基于压缩包）
    8. ResultAggregatorAgent - 结果聚合
    9. ClassAnalysisAgent - 班级分析（可选）
    """
    
    def __init__(self):
        self.graph = None
        self.checkpointer = MemorySaver()
        self._build_workflow()
    
    def _build_workflow(self):
        """构建工作流图"""
        logger.info("🔧 构建深度协作多模态批改工作流...")
        
        # 创建状态图
        workflow = StateGraph(GradingState)
        
        # 添加Agent节点
        workflow.add_node("orchestrator", OrchestratorAgent())
        workflow.add_node("multimodal_input", MultiModalInputAgent())
        workflow.add_node("question_understanding", QuestionUnderstandingAgent())
        workflow.add_node("answer_understanding", AnswerUnderstandingAgent())
        workflow.add_node("rubric_interpretation", RubricInterpreterAgent())
        workflow.add_node("student_detection", StudentDetectionAgent())
        workflow.add_node("batch_planning", BatchPlanningAgent())
        workflow.add_node("rubric_master", RubricMasterAgent())
        workflow.add_node("question_context", QuestionContextAgent())
        workflow.add_node("grading_worker", GradingWorkerAgent())
        workflow.add_node("result_aggregator", ResultAggregatorAgent())
        workflow.add_node("class_analysis", ClassAnalysisAgent())
        workflow.add_node("finalize", self._finalize_results)
        
        # 设置入口点
        workflow.set_entry_point("orchestrator")
        
        # 定义执行流程
        # 0. 编排 -> 多模态输入
        workflow.add_edge("orchestrator", "multimodal_input")
        
        # 1. 多模态输入 -> 并行理解
        workflow.add_edge("multimodal_input", "question_understanding")
        workflow.add_edge("multimodal_input", "answer_understanding")
        workflow.add_edge("multimodal_input", "rubric_interpretation")
        
        # 2. 理解完成 -> 学生识别（注：LangGraph会等待并行节点完成）
        workflow.add_edge("question_understanding", "student_detection")
        workflow.add_edge("answer_understanding", "student_detection")
        workflow.add_edge("rubric_interpretation", "student_detection")
        
        # 3. 学生识别 -> 批次规划
        workflow.add_edge("student_detection", "batch_planning")
        
        # 4. 批次规划 -> 并行生成压缩包
        workflow.add_edge("batch_planning", "rubric_master")
        workflow.add_edge("batch_planning", "question_context")
        
        # 5. 压缩包生成完成 -> 批改工作
        workflow.add_edge("rubric_master", "grading_worker")
        workflow.add_edge("question_context", "grading_worker")
        
        # 6. 批改完成 -> 结果聚合
        workflow.add_edge("grading_worker", "result_aggregator")
        
        # 7. 结果聚合 -> 班级分析
        workflow.add_edge("result_aggregator", "class_analysis")
        
        # 8. 班级分析 -> 完成
        workflow.add_edge("class_analysis", "finalize")
        
        # 9. 最终化 -> 结束
        workflow.add_edge("finalize", END)
        
        # 编译图
        self.graph = workflow.compile(checkpointer=self.checkpointer)
        
        logger.info("✅ 深度协作多模态批改工作流构建完成")
    
    async def execute(self, initial_state: GradingState) -> GradingState:
        """
        执行工作流
        
        Args:
            initial_state: 初始状态（包含文件路径等信息）
            
        Returns:
            最终状态（包含批改结果）
        """
        logger.info(f"🚀 开始执行多模态批改工作流，任务ID: {initial_state.get('task_id', 'unknown')}")
        
        try:
            # 初始化必要字段
            if 'errors' not in initial_state:
                initial_state['errors'] = []
            if 'step_results' not in initial_state:
                initial_state['step_results'] = {}
            if 'warnings' not in initial_state:
                initial_state['warnings'] = []
            if 'question_multimodal_files' not in initial_state:
                initial_state['question_multimodal_files'] = []
            if 'answer_multimodal_files' not in initial_state:
                initial_state['answer_multimodal_files'] = []
            if 'marking_multimodal_files' not in initial_state:
                initial_state['marking_multimodal_files'] = []
            if 'criteria_evaluations' not in initial_state:
                initial_state['criteria_evaluations'] = []
            # 🆕 深度协作相关字段
            if 'students_info' not in initial_state:
                initial_state['students_info'] = []
            if 'batches_info' not in initial_state:
                initial_state['batches_info'] = []
            if 'batch_rubric_packages' not in initial_state:
                initial_state['batch_rubric_packages'] = {}
            if 'question_context_packages' not in initial_state:
                initial_state['question_context_packages'] = {}
            if 'grading_results' not in initial_state:
                initial_state['grading_results'] = []
            if 'student_reports' not in initial_state:
                initial_state['student_reports'] = []
            if 'class_analysis' not in initial_state:
                initial_state['class_analysis'] = {}
            
            # 设置初始状态
            initial_state['current_step'] = "初始化"
            initial_state['progress_percentage'] = 0.0
            initial_state['completion_status'] = "in_progress"
            
            # 执行工作流
            config = {"configurable": {"thread_id": initial_state.get('task_id', 'default')}}
            
            final_state = None
            async for state in self.graph.astream(initial_state, config):
                # 更新状态
                if state:
                    final_state = state
                    # 获取当前节点名称
                    current_node = list(state.keys())[0] if state else "unknown"
                    logger.info(f"📍 当前节点: {current_node}")
            
            # 标记完成
            if final_state:
                # 获取最终状态值
                final_result = list(final_state.values())[0] if final_state else initial_state
                final_result['completion_status'] = "completed"
                final_result['completed_at'] = str(datetime.now())
                final_result['progress_percentage'] = 100.0
                
                logger.info(f"✅ 工作流执行完成，总分: {final_result.get('total_score', 0)}")
                return final_result
            else:
                raise Exception("工作流执行失败，未返回最终状态")
                
        except Exception as e:
            error_msg = f"工作流执行失败: {str(e)}"
            logger.error(error_msg)
            
            initial_state['completion_status'] = "failed"
            initial_state['errors'].append({
                'step': 'workflow_execution',
                'error': error_msg,
                'timestamp': str(datetime.now())
            })
            
            return initial_state
    
    def _finalize_results(self, state: GradingState) -> GradingState:
        """
        最终化结果
        
        Args:
            state: 当前状态
            
        Returns:
            更新后的状态
        """
        logger.info("🎯 最终化批改结果...")
        
        try:
            state['current_step'] = "最终化结果"
            state['progress_percentage'] = 100.0
            state['completion_status'] = "completed"
            state['completed_at'] = str(datetime.now())
            
            # 生成摘要
            summary = state.get('summary', {})
            total_score = state.get('total_score', 0)
            
            logger.info(f"✅ 批改完成")
            logger.info(f"   总分: {total_score}")
            logger.info(f"   学生数: {summary.get('total_students', 0)}")
            logger.info(f"   平均分: {summary.get('average_score', 0):.1f}")
            
            return state
            
        except Exception as e:
            logger.error(f"最终化失败: {e}")
            state['errors'].append({
                'step': 'finalize',
                'error': str(e),
                'timestamp': str(datetime.now())
            })
            return state


# 创建全局工作流实例
_workflow_instance = None

def get_multimodal_workflow() -> MultiModalGradingWorkflow:
    """获取多模态工作流实例（单例模式）"""
    global _workflow_instance
    if _workflow_instance is None:
        _workflow_instance = MultiModalGradingWorkflow()
    return _workflow_instance


async def run_multimodal_grading(
    task_id: str,
    user_id: str,
    question_files: list,
    answer_files: list,
    marking_files: list,
    strictness_level: str = "中等",
    language: str = "zh"
) -> Dict[str, Any]:
    """
    运行多模态批改工作流（便捷函数）
    
    Args:
        task_id: 任务ID
        user_id: 用户ID
        question_files: 题目文件路径列表
        answer_files: 答案文件路径列表
        marking_files: 评分标准文件路径列表
        strictness_level: 严格程度
        language: 语言
        
    Returns:
        批改结果字典
    """
    # 创建初始状态
    initial_state = GradingState(
        task_id=task_id,
        user_id=user_id,
        assignment_id=f"assignment_{task_id}",
        timestamp=datetime.now(),
        question_files=question_files,
        answer_files=answer_files,
        marking_files=marking_files,
        images=[],
        strictness_level=strictness_level,
        language=language,
        mode="efficient",
        # 初始化必要字段
        mm_tokens=[],
        student_info={},
        ocr_results={},
        image_regions={},
        preprocessed_images={},
        rubric_text="",
        rubric_struct={},
        rubric_data={},
        scoring_criteria=[],
        questions=[],
        batches=[],
        evaluations=[],
        scoring_results={},
        detailed_feedback=[],
        annotations=[],
        coordinate_annotations=[],
        error_regions=[],
        cropped_regions=[],
        knowledge_points=[],
        error_analysis={},
        learning_suggestions=[],
        difficulty_assessment={},
        total_score=0.0,
        section_scores={},
        student_evaluation={},
        class_evaluation={},
        export_payload={},
        final_report={},
        export_data={},
        visualization_data={},
        current_step="",
        progress_percentage=0.0,
        completion_status="pending",
        completed_at="",
        errors=[],
        step_results={},
        final_score=0.0,
        grade_level="",
        warnings=[],
        processing_time=0.0,
        model_versions={},
        quality_metrics={},
        # 多模态字段
        question_multimodal_files=[],
        answer_multimodal_files=[],
        marking_multimodal_files=[],
        question_understanding=None,
        answer_understanding=None,
        rubric_understanding=None,
        criteria_evaluations=[]
    )
    
    # 获取工作流实例并执行
    workflow = get_multimodal_workflow()
    final_state = await workflow.execute(initial_state)
    
    # 返回结果
    return {
        'task_id': final_state.get('task_id'),
        'status': final_state.get('completion_status'),
        'total_score': final_state.get('total_score'),
        'grade_level': final_state.get('grade_level'),
        'detailed_feedback': final_state.get('detailed_feedback'),
        'criteria_evaluations': final_state.get('criteria_evaluations'),
        'errors': final_state.get('errors'),
        'warnings': final_state.get('warnings')
    }
