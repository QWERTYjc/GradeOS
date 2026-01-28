"""辅助批改 LangGraph 工作流

提供深度分析和智能纠错功能，不依赖评分标准。

工作流：
初始化 → 理解分析 → 错误识别 → 建议生成 → 深度分析 → 报告生成 → 完成
"""

import logging
import os
from typing import Dict, Any
from datetime import datetime

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from src.graphs.state import AssistantGradingState


logger = logging.getLogger(__name__)


# ==================== 配置 ====================


ASSISTANT_GRADING_CONFIG = {
    "max_workers": 2,  # 最大并发数（低于主系统）
    "timeout_seconds": 300,  # 超时时间（5 分钟）
    "retry_limit": 2,  # 重试限制
    "priority": "low",  # 优先级（低于主系统）
}


# ==================== 节点实现（占位符）====================


async def understand_assignment_node(state: AssistantGradingState) -> Dict[str, Any]:
    """
    理解作业内容节点
    
    目标：
    - 识别知识点
    - 分析题目类型
    - 理解解题思路
    - 提取逻辑链条
    """
    from src.services.assistant_analyzer import AssistantAnalyzer
    
    analysis_id = state["analysis_id"]
    logger.info(f"[AssistantGrading] 开始理解分析: analysis_id={analysis_id}")
    
    try:
        # 调用分析引擎
        analyzer = AssistantAnalyzer()
        try:
            understanding_result = await analyzer.analyze_understanding(
                images=state["image_base64_list"],
                subject=state.get("subject"),
                context_info=state.get("context_info"),
            )
        finally:
            await analyzer.close()
        
        # 转换为字典格式
        understanding = {
            "knowledge_points": [
                {
                    "name": kp.name,
                    "category": kp.category,
                    "confidence": kp.confidence,
                }
                for kp in understanding_result.knowledge_points
            ],
            "question_types": understanding_result.question_types,
            "solution_approaches": understanding_result.solution_approaches,
            "logic_chain": understanding_result.logic_chain,
            "difficulty_level": understanding_result.difficulty_level.value,
            "estimated_time_minutes": understanding_result.estimated_time_minutes,
        }
        
        logger.info(f"[AssistantGrading] 理解分析完成: analysis_id={analysis_id}, knowledge_points={len(understanding['knowledge_points'])}")
        
        return {
            "understanding": understanding,
            "current_stage": "understood",
            "percentage": 25.0,
            "timestamps": {
                **state.get("timestamps", {}),
                "understood_at": datetime.now().isoformat()
            }
        }
    
    except Exception as e:
        logger.error(f"[AssistantGrading] 理解分析失败: {e}", exc_info=True)
        return {
            "processing_errors": state.get("processing_errors", []) + [
                {
                    "stage": "understand",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
            ],
            "retry_count": state.get("retry_count", 0) + 1
        }


async def identify_errors_node(state: AssistantGradingState) -> Dict[str, Any]:
    """
    错误识别节点
    
    目标：
    - 识别计算错误
    - 识别逻辑错误
    - 识别概念错误
    - 识别书写错误
    """
    from src.services.error_detector import ErrorDetector
    
    analysis_id = state["analysis_id"]
    logger.info(f"[AssistantGrading] 开始错误识别: analysis_id={analysis_id}")
    
    try:
        # 调用错误检测器
        detector = ErrorDetector()
        try:
            error_records = await detector.detect_errors(
                images=state["image_base64_list"],
                understanding=state.get("understanding", {}),
            )
        finally:
            await detector.close()
        
        # 转换为字典格式
        errors = [
            {
                "error_id": err.error_id,
                "error_type": err.error_type.value,
                "description": err.description,
                "severity": err.severity.value,
                "location": {
                    "page": err.location.page,
                    "region": err.location.region,
                    "step_number": err.location.step_number,
                    "coordinates": err.location.coordinates,
                },
                "affected_steps": err.affected_steps,
                "correct_approach": err.correct_approach,
                "context": err.context,
            }
            for err in error_records
        ]
        
        logger.info(f"[AssistantGrading] 错误识别完成: analysis_id={analysis_id}, 发现 {len(errors)} 个错误")
        
        return {
            "errors": errors,
            "current_stage": "errors_identified",
            "percentage": 50.0,
            "timestamps": {
                **state.get("timestamps", {}),
                "errors_identified_at": datetime.now().isoformat()
            }
        }
    
    except Exception as e:
        logger.error(f"[AssistantGrading] 错误识别失败: {e}", exc_info=True)
        return {
            "processing_errors": state.get("processing_errors", []) + [
                {
                    "stage": "identify_errors",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
            ],
            "retry_count": state.get("retry_count", 0) + 1
        }


async def generate_suggestions_node(state: AssistantGradingState) -> Dict[str, Any]:
    """
    建议生成节点
    
    目标：
    - 为每个错误生成纠正建议
    - 生成改进建议
    - 生成替代方案
    """
    from src.services.suggestion_generator import SuggestionGenerator
    from src.models.assistant_models import ErrorRecord, ErrorType, Severity, ErrorLocation
    
    analysis_id = state["analysis_id"]
    logger.info(f"[AssistantGrading] 开始建议生成: analysis_id={analysis_id}")
    
    try:
        # 转换错误列表为 ErrorRecord 对象
        errors = []
        for err_dict in state.get("errors", []):
            try:
                error_record = ErrorRecord(
                    error_id=err_dict["error_id"],
                    error_type=ErrorType(err_dict["error_type"]),
                    description=err_dict["description"],
                    severity=Severity(err_dict["severity"]),
                    location=ErrorLocation(**err_dict["location"]),
                    affected_steps=err_dict.get("affected_steps", []),
                    correct_approach=err_dict.get("correct_approach"),
                    context=err_dict.get("context"),
                )
                errors.append(error_record)
            except Exception as e:
                logger.warning(f"[AssistantGrading] 跳过无效错误记录: {e}")
                continue
        
        # 调用建议生成器
        generator = SuggestionGenerator()
        try:
            suggestion_records = await generator.generate_suggestions(
                errors=errors,
                understanding=state.get("understanding", {}),
            )
        finally:
            await generator.close()
        
        # 转换为字典格式
        suggestions = [
            {
                "suggestion_id": sugg.suggestion_id,
                "related_error_id": sugg.related_error_id,
                "suggestion_type": sugg.suggestion_type.value,
                "description": sugg.description,
                "example": sugg.example,
                "priority": sugg.priority.value,
                "resources": sugg.resources,
                "expected_improvement": sugg.expected_improvement,
            }
            for sugg in suggestion_records
        ]
        
        logger.info(f"[AssistantGrading] 建议生成完成: analysis_id={analysis_id}, 生成 {len(suggestions)} 条建议")
        
        return {
            "suggestions": suggestions,
            "current_stage": "suggestions_generated",
            "percentage": 75.0,
            "timestamps": {
                **state.get("timestamps", {}),
                "suggestions_generated_at": datetime.now().isoformat()
            }
        }
    
    except Exception as e:
        logger.error(f"[AssistantGrading] 建议生成失败: {e}", exc_info=True)
        return {
            "processing_errors": state.get("processing_errors", []) + [
                {
                    "stage": "generate_suggestions",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
            ],
            "retry_count": state.get("retry_count", 0) + 1
        }


async def deep_analysis_node(state: AssistantGradingState) -> Dict[str, Any]:
    """
    深度分析节点
    
    目标：
    - 评估理解程度
    - 评估逻辑连贯性
    - 评估完整性
    - 生成学习建议
    """
    analysis_id = state["analysis_id"]
    logger.info(f"[AssistantGrading] 开始深度分析: analysis_id={analysis_id}")
    
    try:
        # 基于现有结果进行深度分析
        understanding = state.get("understanding", {})
        errors = state.get("errors", [])
        suggestions = state.get("suggestions", [])
        
        # 计算各项评分
        # 理解程度评分：基于知识点数量和置信度
        knowledge_points = understanding.get("knowledge_points", [])
        if knowledge_points:
            avg_confidence = sum(kp.get("confidence", 0.5) for kp in knowledge_points) / len(knowledge_points)
            understanding_score = min(100.0, avg_confidence * 100.0 + len(knowledge_points) * 5)
        else:
            understanding_score = 50.0
        
        # 逻辑连贯性评分：基于逻辑链条和错误数量
        logic_chain = understanding.get("logic_chain", [])
        logic_errors = sum(1 for err in errors if err.get("error_type") == "logic")
        if logic_chain:
            logic_coherence = max(0.0, 100.0 - logic_errors * 15 - (5 - len(logic_chain)) * 5)
        else:
            logic_coherence = 50.0
        
        # 完整性评分：基于解题步骤和错误
        solution_approaches = understanding.get("solution_approaches", [])
        completeness = max(0.0, 100.0 - len(errors) * 10 + len(solution_approaches) * 5)
        
        # 总分
        overall_score = (understanding_score + logic_coherence + completeness) / 3.0
        
        # 优点和不足
        strengths = []
        weaknesses = []
        
        if overall_score >= 75:
            strengths.append("对知识点理解较好")
        if len(logic_chain) >= 3:
            strengths.append("逻辑推理完整")
        if len(errors) == 0:
            strengths.append("未发现明显错误")
        
        if len(errors) > 0:
            weaknesses.append(f"发现 {len(errors)} 个错误")
        if logic_coherence < 70:
            weaknesses.append("逻辑推理需要加强")
        if completeness < 70:
            weaknesses.append("答题完整性不足")
        
        # 学习建议
        learning_recommendations = [
            {
                "category": "巩固基础",
                "description": "回顾相关知识点",
                "action_items": ["重新学习相关章节", "完成练习题"]
            }
        ]
        
        # 成长潜力
        if overall_score >= 80:
            growth_potential = "high"
        elif overall_score >= 60:
            growth_potential = "medium"
        else:
            growth_potential = "low"
        
        # 下一步计划
        next_steps = [
            "针对错误进行改正",
            "加强薄弱知识点的学习",
            "完成类似题目的练习"
        ]
        
        deep_analysis = {
            "understanding_score": round(understanding_score, 2),
            "understanding_score_reasoning": f"基于 {len(knowledge_points)} 个知识点的理解程度",
            "logic_coherence": round(logic_coherence, 2),
            "logic_coherence_reasoning": f"发现 {logic_errors} 个逻辑错误",
            "completeness": round(completeness, 2),
            "completeness_reasoning": f"基于 {len(solution_approaches)} 个解题步骤",
            "overall_score": round(overall_score, 2),
            "strengths": strengths,
            "weaknesses": weaknesses,
            "learning_recommendations": learning_recommendations,
            "growth_potential": growth_potential,
            "next_steps": next_steps
        }
        
        logger.info(f"[AssistantGrading] 深度分析完成: analysis_id={analysis_id}, overall_score={overall_score:.1f}")
        
        return {
            "deep_analysis": deep_analysis,
            "current_stage": "deep_analyzed",
            "percentage": 90.0,
            "timestamps": {
                **state.get("timestamps", {}),
                "deep_analyzed_at": datetime.now().isoformat()
            }
        }
    
    except Exception as e:
        logger.error(f"[AssistantGrading] 深度分析失败: {e}", exc_info=True)
        return {
            "processing_errors": state.get("processing_errors", []) + [
                {
                    "stage": "deep_analysis",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
            ],
            "retry_count": state.get("retry_count", 0) + 1
        }


async def generate_report_node(state: AssistantGradingState) -> Dict[str, Any]:
    """
    报告生成节点
    
    目标：
    - 汇总所有分析结果
    - 生成结构化报告
    - 保存报告到数据库
    """
    analysis_id = state["analysis_id"]
    logger.info(f"[AssistantGrading] 开始报告生成: analysis_id={analysis_id}")
    
    try:
        # 汇总所有结果
        understanding = state.get("understanding", {})
        errors = state.get("errors", [])
        suggestions = state.get("suggestions", [])
        deep_analysis = state.get("deep_analysis", {})
        
        # 生成报告
        report = {
            "metadata": {
                "analysis_id": analysis_id,
                "submission_id": state.get("submission_id"),
                "student_id": state.get("student_id"),
                "subject": state.get("subject"),
                "created_at": state.get("timestamps", {}).get("created_at"),
                "completed_at": datetime.now().isoformat(),
                "version": "1.0"
            },
            "summary": {
                "overall_score": deep_analysis.get("overall_score", 0.0),
                "total_errors": len(errors),
                "high_severity_errors": sum(1 for e in errors if e.get("severity") == "high"),
                "total_suggestions": len(suggestions),
                "estimated_completion_time_minutes": understanding.get("estimated_time_minutes", 0),
                "actual_difficulty": understanding.get("difficulty_level", "medium")
            },
            "understanding": understanding,
            "errors": errors,
            "suggestions": suggestions,
            "deep_analysis": deep_analysis,
            "action_plan": {
                "immediate_actions": [
                    sugg.get("description")
                    for sugg in suggestions
                    if sugg.get("priority") == "high"
                ][:3],
                "short_term_goals": [
                    sugg.get("description")
                    for sugg in suggestions
                    if sugg.get("priority") == "medium"
                ][:3],
                "long_term_goals": deep_analysis.get("next_steps", [])[:3],
            }
        }
        
        # TODO: 保存到数据库
        # from src.db.assistant_tables import AssistantAnalysisReport
        # await save_to_database(report)
        
        report_url = None  # TODO: 如果需要，生成报告 URL
        
        logger.info(f"[AssistantGrading] 报告生成完成: analysis_id={analysis_id}, overall_score={report['summary']['overall_score']:.1f}")
        
        return {
            "report": report,
            "report_url": report_url,
            "current_stage": "completed",
            "percentage": 100.0,
            "timestamps": {
                **state.get("timestamps", {}),
                "completed_at": datetime.now().isoformat()
            }
        }
    
    except Exception as e:
        logger.error(f"[AssistantGrading] 报告生成失败: {e}", exc_info=True)
        return {
            "processing_errors": state.get("processing_errors", []) + [
                {
                    "stage": "generate_report",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
            ],
            "retry_count": state.get("retry_count", 0) + 1
        }


# ==================== 工作流构建 ====================


def create_assistant_grading_graph(checkpointer=None):
    """
    创建辅助批改工作流图
    
    Args:
        checkpointer: 检查点保存器（用于持久化和恢复）
        
    Returns:
        编译后的工作流图
    """
    logger.info("[AssistantGrading] 创建辅助批改工作流图")
    
    # 创建图
    graph = StateGraph(AssistantGradingState)
    
    # 添加节点
    graph.add_node("understand", understand_assignment_node)
    graph.add_node("identify_errors", identify_errors_node)
    graph.add_node("generate_suggestions", generate_suggestions_node)
    graph.add_node("deep_analysis", deep_analysis_node)
    graph.add_node("generate_report", generate_report_node)
    
    # 设置入口
    graph.set_entry_point("understand")
    
    # 添加边（线性流程）
    graph.add_edge("understand", "identify_errors")
    graph.add_edge("identify_errors", "generate_suggestions")
    graph.add_edge("generate_suggestions", "deep_analysis")
    graph.add_edge("deep_analysis", "generate_report")
    graph.add_edge("generate_report", END)
    
    # 编译图
    compiled_graph = graph.compile(
        checkpointer=checkpointer,
        # 中断点（可选，用于人工介入）
        # interrupt_before=["generate_report"],
    )
    
    logger.info("[AssistantGrading] 辅助批改工作流图创建完成")
    return compiled_graph


# ==================== 便捷函数 ====================


async def run_assistant_grading(
    analysis_id: str,
    images: list[str],
    submission_id: str | None = None,
    student_id: str | None = None,
    subject: str | None = None,
    context_info: dict[str, Any] | None = None,
    checkpointer=None,
) -> Dict[str, Any]:
    """
    运行辅助批改分析
    
    Args:
        analysis_id: 分析任务 ID
        images: 作业图片 Base64 列表
        submission_id: 关联提交 ID（可选）
        student_id: 学生 ID（可选）
        subject: 科目（可选）
        context_info: 上下文信息（可选）
        checkpointer: 检查点保存器（可选）
        
    Returns:
        最终状态
    """
    from src.graphs.state import create_initial_assistant_state
    
    # 创建初始状态
    initial_state = create_initial_assistant_state(
        analysis_id=analysis_id,
        images=images,
        submission_id=submission_id,
        student_id=student_id,
        subject=subject,
        context_info=context_info,
    )
    
    # 创建工作流图
    graph = create_assistant_grading_graph(checkpointer=checkpointer)
    
    # 配置
    config = {
        "configurable": {
            "thread_id": analysis_id,
        },
        "recursion_limit": 10,
    }
    
    # 运行工作流
    logger.info(f"[AssistantGrading] 开始运行工作流: analysis_id={analysis_id}")
    
    final_state = None
    async for state in graph.astream(initial_state, config=config):
        final_state = state
        logger.debug(f"[AssistantGrading] 工作流状态更新: {state}")
    
    logger.info(f"[AssistantGrading] 工作流完成: analysis_id={analysis_id}")
    
    return final_state
