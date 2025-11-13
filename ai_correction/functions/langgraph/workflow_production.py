#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生产级 LangGraph 工作流 - 逐题批改，流式处理
"""

from typing import Dict, Any, TypedDict, Annotated
from langgraph.graph import StateGraph, END
import operator


class GradingState(TypedDict):
    """批改状态"""
    # 输入
    question_files: list
    answer_files: list
    marking_files: list
    
    # 解析结果
    questions: list
    answers: list
    marking_scheme: dict
    student_info: dict
    
    # 分析结果
    analyzed_questions: list
    interpreted_rubric: dict
    
    # 批改结果
    grading_results: list
    
    # 聚合结果
    aggregated_results: dict
    statistics: dict
    
    # 持久化
    task_id: int
    
    # 状态
    parse_status: str
    analysis_status: str
    rubric_status: str
    grading_status: str
    aggregation_status: str
    persistence_status: str
    
    # 错误
    parse_errors: list
    analysis_errors: list
    rubric_errors: list
    grading_errors: list
    aggregation_errors: list
    persistence_errors: list
    
    # 流式输出
    stream_output: Annotated[list, operator.add]


def create_production_workflow(llm_client=None, db_manager=None):
    """
    创建生产级工作流
    
    Args:
        llm_client: LLM 客户端
        db_manager: 数据库管理器
        
    Returns:
        编译后的工作流
    """
    from .agents.input_parser import InputParserAgent
    from .agents.question_analyzer import QuestionAnalyzerAgent, QuestionGraderAgent
    from .agents.result_aggregator import ResultAggregatorAgent, RubricInterpreterAgent

    # 初始化 Agent
    input_parser = InputParserAgent(llm_client)  # 传递 LLM 客户端以支持图片OCR
    question_analyzer = QuestionAnalyzerAgent()
    rubric_interpreter = RubricInterpreterAgent()
    question_grader = QuestionGraderAgent(llm_client)
    result_aggregator = ResultAggregatorAgent()

    # 数据持久化（可选）
    data_persistence = None
    if db_manager:
        from ..database import DataPersistenceAgent
        data_persistence = DataPersistenceAgent(db_manager)
    
    # 定义节点函数
    def parse_input(state: GradingState) -> GradingState:
        """解析输入"""
        print("📄 正在解析输入文件...")
        result = input_parser.parse(state)
        result['stream_output'] = [{'step': 'parse', 'status': result.get('parse_status')}]
        return result
    
    def analyze_questions(state: GradingState) -> Dict:
        """分析题目"""
        print("🔍 正在分析题目特征...")
        result = question_analyzer.analyze(state)
        # 只返回修改的字段，避免并发冲突
        return {
            'questions': result.get('questions'),
            'analysis_status': result.get('analysis_status'),
            'analysis_errors': result.get('analysis_errors', []),
            'stream_output': [{'step': 'analyze', 'status': result.get('analysis_status')}]
        }

    def interpret_rubric(state: GradingState) -> Dict:
        """解释评分标准"""
        print("📋 正在解析评分标准...")
        result = rubric_interpreter.interpret(state)
        # 只返回修改的字段，避免并发冲突
        return {
            'interpreted_rubric': result.get('interpreted_rubric'),
            'rubric_status': result.get('rubric_status'),
            'rubric_errors': result.get('rubric_errors', []),
            'stream_output': [{'step': 'rubric', 'status': result.get('rubric_status')}]
        }
    
    def grade_questions(state: GradingState) -> Dict:
        """逐题批改"""
        print("✍️ 正在逐题批改...")
        print(f"DEBUG: answers = {state.get('answers', [])}")
        print(f"DEBUG: marking_scheme = {state.get('marking_scheme', {})}")
        result = question_grader.grade(state)
        print(f"DEBUG: grading_results = {result.get('grading_results', [])}")
        print(f"DEBUG: grading_status = {result.get('grading_status')}")

        # 流式输出每道题的结果
        stream_outputs = []
        for i, gr in enumerate(result.get('grading_results', [])):
            stream_outputs.append({
                'step': 'grading',
                'question_id': gr['question_id'],
                'progress': f"{i+1}/{len(result.get('grading_results', []))}",
                'score': gr['score']
            })

        # 只返回修改的字段，避免并发冲突
        return {
            'grading_results': result.get('grading_results'),
            'grading_status': result.get('grading_status'),
            'grading_errors': result.get('grading_errors', []),
            'stream_output': stream_outputs
        }
    
    def aggregate_results(state: GradingState) -> Dict:
        """聚合结果"""
        print("📊 正在聚合结果...")
        print(f"DEBUG: grading_results = {state.get('grading_results', [])}")
        result = result_aggregator.aggregate(state)
        print(f"DEBUG: aggregation_status = {result.get('aggregation_status')}")
        print(f"DEBUG: aggregation_errors = {result.get('aggregation_errors', [])}")
        # 只返回修改的字段，避免并发冲突
        return {
            'aggregated_results': result.get('aggregated_results'),
            'statistics': result.get('statistics'),
            'aggregation_status': result.get('aggregation_status'),
            'aggregation_errors': result.get('aggregation_errors', []),
            'stream_output': [{'step': 'aggregate', 'status': result.get('aggregation_status')}]
        }
    
    def persist_data(state: GradingState) -> Dict:
        """持久化数据"""
        if data_persistence:
            print("💾 正在保存数据...")
            result = data_persistence.persist(state)
            # 只返回修改的字段，避免并发冲突
            return {
                'persistence_status': result.get('persistence_status'),
                'persistence_errors': result.get('persistence_errors', []),
                'stream_output': [{'step': 'persist', 'status': result.get('persistence_status')}]
            }
        else:
            print("⏭️ 跳过数据持久化（未配置数据库）")
            return {
                'persistence_status': 'skipped',
                'stream_output': [{'step': 'persist', 'status': 'skipped'}]
            }

    # 创建工作流图
    workflow = StateGraph(GradingState)

    # 添加节点
    workflow.add_node("parse_input", parse_input)
    workflow.add_node("analyze_questions", analyze_questions)
    workflow.add_node("interpret_rubric", interpret_rubric)
    workflow.add_node("grade_questions", grade_questions)
    workflow.add_node("aggregate_results", aggregate_results)
    workflow.add_node("persist_data", persist_data)

    # 定义边
    workflow.set_entry_point("parse_input")

    # 解析后并行执行分析和解释
    workflow.add_edge("parse_input", "analyze_questions")
    workflow.add_edge("parse_input", "interpret_rubric")

    # 分析和解释完成后批改
    workflow.add_edge("analyze_questions", "grade_questions")
    workflow.add_edge("interpret_rubric", "grade_questions")

    # 批改完成后聚合
    workflow.add_edge("grade_questions", "aggregate_results")
    
    # 聚合完成后持久化
    workflow.add_edge("aggregate_results", "persist_data")
    
    # 持久化完成后结束
    workflow.add_edge("persist_data", END)
    
    # 编译工作流
    app = workflow.compile()
    
    return app


def run_grading_workflow(
    question_files: list,
    answer_files: list,
    marking_files: list = None,
    llm_client=None,
    db_manager=None,
    stream: bool = True
):
    """
    运行批改工作流
    
    Args:
        question_files: 题目文件列表
        answer_files: 答案文件列表
        marking_files: 评分标准文件列表
        llm_client: LLM 客户端
        db_manager: 数据库管理器
        stream: 是否流式输出
        
    Returns:
        批改结果
    """
    # 创建工作流
    app = create_production_workflow(llm_client, db_manager)
    
    # 初始状态
    initial_state = {
        'question_files': question_files,
        'answer_files': answer_files,
        'marking_files': marking_files or [],
        'stream_output': []
    }
    
    # 运行工作流
    if stream:
        # 流式输出
        for output in app.stream(initial_state):
            yield output
    else:
        # 一次性输出
        result = app.invoke(initial_state)
        return result


def format_grading_result(state: GradingState) -> str:
    """
    格式化批改结果为 Markdown（使用新的格式化器）

    Args:
        state: 批改状态

    Returns:
        Markdown 格式的结果
    """
    from .result_formatter import format_grading_result_v2

    grading_results = state.get('grading_results', [])
    aggregated_results = state.get('aggregated_results', {})

    return format_grading_result_v2(grading_results, aggregated_results)

