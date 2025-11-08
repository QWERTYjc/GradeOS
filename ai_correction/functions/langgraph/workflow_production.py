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
    from ..agents.input_parser import InputParserAgent
    from ..agents.question_analyzer import QuestionAnalyzerAgent, QuestionGraderAgent
    from ..agents.result_aggregator import ResultAggregatorAgent, RubricInterpreterAgent
    from ...database import DataPersistenceAgent, DatabaseManager
    
    # 初始化 Agent
    input_parser = InputParserAgent()
    question_analyzer = QuestionAnalyzerAgent()
    rubric_interpreter = RubricInterpreterAgent()
    question_grader = QuestionGraderAgent(llm_client)
    result_aggregator = ResultAggregatorAgent()
    data_persistence = DataPersistenceAgent(db_manager or DatabaseManager())
    
    # 定义节点函数
    def parse_input(state: GradingState) -> GradingState:
        """解析输入"""
        print("📄 正在解析输入文件...")
        result = input_parser.parse(state)
        result['stream_output'] = [{'step': 'parse', 'status': result.get('parse_status')}]
        return result
    
    def analyze_questions(state: GradingState) -> GradingState:
        """分析题目"""
        print("🔍 正在分析题目特征...")
        result = question_analyzer.analyze(state)
        result['stream_output'] = [{'step': 'analyze', 'status': result.get('analysis_status')}]
        return result
    
    def interpret_rubric(state: GradingState) -> GradingState:
        """解释评分标准"""
        print("📋 正在解析评分标准...")
        result = rubric_interpreter.interpret(state)
        result['stream_output'] = [{'step': 'rubric', 'status': result.get('rubric_status')}]
        return result
    
    def grade_questions(state: GradingState) -> GradingState:
        """逐题批改"""
        print("✍️ 正在逐题批改...")
        result = question_grader.grade(state)
        
        # 流式输出每道题的结果
        stream_outputs = []
        for i, gr in enumerate(result.get('grading_results', [])):
            stream_outputs.append({
                'step': 'grading',
                'question_id': gr['question_id'],
                'progress': f"{i+1}/{len(result.get('grading_results', []))}",
                'score': gr['score']
            })
        
        result['stream_output'] = stream_outputs
        return result
    
    def aggregate_results(state: GradingState) -> GradingState:
        """聚合结果"""
        print("📊 正在聚合结果...")
        result = result_aggregator.aggregate(state)
        result['stream_output'] = [{'step': 'aggregate', 'status': result.get('aggregation_status')}]
        return result
    
    def persist_data(state: GradingState) -> GradingState:
        """持久化数据"""
        print("💾 正在保存数据...")
        result = data_persistence.persist(state)
        result['stream_output'] = [{'step': 'persist', 'status': result.get('persistence_status')}]
        return result
    
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
    格式化批改结果为 Markdown
    
    Args:
        state: 批改状态
        
    Returns:
        Markdown 格式的结果
    """
    aggregated = state.get('aggregated_results', {})
    student_info = aggregated.get('student_info', {})
    
    md = f"""# 📋 AI 批改结果

## 👤 学生信息
- **学号**: {student_info.get('id', 'N/A')}
- **姓名**: {student_info.get('name', 'N/A')}
- **班级**: {student_info.get('class', 'N/A')}

## 📊 总体成绩
- **总分**: {aggregated.get('total_score', 0)}/{aggregated.get('max_score', 0)} 分
- **得分率**: {aggregated.get('percentage', 0):.1f}%
- **等级**: {aggregated.get('grade', 'N/A')}
- **答对题数**: {aggregated.get('correct_count', 0)}/{aggregated.get('question_count', 0)}

{aggregated.get('summary', '')}

## 📝 逐题详情
"""
    
    for i, result in enumerate(aggregated.get('details', []), 1):
        md += f"""
### 第 {result['question_id']} 题
- **得分**: {result['score']}/{result['max_score']} 分
- **批改策略**: {result.get('strategy', 'N/A')}
- **反馈**: {result.get('feedback', '无')}
"""
    
    # 错误分析
    error_analysis = aggregated.get('error_analysis', {})
    if error_analysis.get('total_errors', 0) > 0:
        md += f"""
## ❌ 错误分析
- **错误题数**: {error_analysis['total_errors']}
- **错误率**: {error_analysis['error_rate']*100:.1f}%

### 错误题目
"""
        for error in error_analysis.get('error_questions', []):
            md += f"- 第 {error['question_id']} 题: {error.get('feedback', '无反馈')}\n"
    
    # 知识点分析
    knowledge = aggregated.get('knowledge_analysis', {})
    if knowledge:
        md += "\n## 📚 知识点掌握情况\n"
        for kp, data in knowledge.items():
            md += f"- **{kp}**: 掌握率 {data['mastery_rate']*100:.1f}% ({data['correct']}/{data['total']})\n"
    
    return md

