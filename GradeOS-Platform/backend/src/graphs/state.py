"""LangGraph Graph State 定义

本模块定义了用于 LangGraph 编排的状态类型，用于替代 Temporal 工作流。
"""

from typing import TypedDict, List, Dict, Any, Optional, Annotated
from datetime import datetime
import operator


def last_value(current: Any, new: Any) -> Any:
    """取最新值的 reducer，用于处理并发更新时只保留最后一个值"""
    return new if new is not None else current


class GradingGraphState(TypedDict, total=False):
    """批改 Graph 状态定义
    
    用于 LangGraph 的状态管理，包含批改任务的完整生命周期信息。
    total=False 表示所有字段都是可选的，支持增量更新。
    
    Requirements: 2.1
    """
    
    # ===== 基础信息 =====
    job_id: str                          # 任务唯一标识符
    submission_id: str                   # 提交 ID
    exam_id: str                         # 考试 ID
    student_id: str                      # 学生 ID
    
    # ===== 输入数据 =====
    inputs: Dict[str, Any]               # 输入数据（文件路径、配置等）
    grading_mode: Optional[str]  # standard/assist_teacher/assist_student
    file_paths: List[str]                # 试卷文件路径列表
    rubric: str                          # 评分细则文本
    
    # ===== 进度信息 =====
    progress: Dict[str, Any]             # 进度详情（各阶段完成情况）
    current_stage: str                   # 当前执行阶段
    percentage: float                    # 完成百分比 (0.0-100.0)
    
    # ===== 执行结果 =====
    artifacts: Dict[str, Any]            # 中间产物（分割后的题目、图像等）
    grading_results: List[Dict[str, Any]]  # 各题目批改结果列表
    total_score: float                   # 总分
    max_total_score: float               # 满分
    
    # ===== 错误处理 =====
    errors: List[Dict[str, Any]]         # 错误记录列表
    retry_count: int                     # 当前重试次数
    
    # ===== 时间戳 =====
    timestamps: Dict[str, str]           # 各阶段时间戳（ISO 格式）
    
    # ===== 人工介入 =====
    needs_review: bool                   # 是否需要人工审核
    review_result: Optional[Dict[str, Any]]  # 人工审核结果
    
    # ===== 外部事件 =====
    external_event: Optional[Dict[str, Any]]  # 外部事件数据（用于 resume）
    
    # ===== 多智能体相关 =====
    pending_questions: List[Dict[str, Any]]  # 待处理题目队列
    completed_questions: List[str]       # 已完成题目 ID 列表
    active_agent: Optional[str]          # 当前活跃的智能体类型
    agent_results: Dict[str, Any]        # 各智能体的执行结果


class BatchGradingGraphState(TypedDict, total=False):
    """批量批改 Graph 状态定义
    
    用于批量处理多份试卷的并行批改场景。
    
    工作流：
    接收文件 → 图像预处理 → 解析评分标准 → 可配置分批批改 → 跨页题目合并 → 学生分割 → 结果审核 → 导出结果
    
    Requirements: 3.1, 3.2, 3.3, 3.4, 5.1, 5.4, 8.1, 8.2, 8.3, 8.4, 8.5, 10.1
    """
    
    # ===== 基础信息 =====
    batch_id: str                        # 批次唯一标识符
    exam_id: str                         # 考试 ID
    api_key: str                         # API Key
    subject: str                         # 科目标识（用于记忆隔离）
                                         # 例如: economics, physics, mathematics, advanced_mathematics
    
    # ===== 输入数据 =====
    inputs: Dict[str, Any]               # 批量输入数据
    grading_mode: Annotated[Optional[str], last_value]  # standard/assist_teacher/assist_student
    pdf_path: str                        # 批量 PDF 文件路径
    rubric: str                          # 评分细则文本
    answer_images: List[str]             # 答题图像列表（base64 或路径）
    rubric_images: List[str]             # 评分标准图像列表
    student_mapping: List[Dict[str, Any]]  # 前端提供的学生映射（可选）
    
    # ===== 预处理结果 =====
    processed_images: List[str]          # 预处理后的图像
    parsed_rubric: Dict[str, Any]        # 解析后的评分标准

    # ===== 索引层输出 =====
    index_results: Dict[str, Any]        # 索引结果（按页题目信息与学生映射）
    student_page_map: Dict[int, str]     # 页面 -> 学生标识映射
    indexed_students: List[Dict[str, Any]]  # 索引阶段识别的学生信息
    index_unidentified_pages: List[int]  # 未识别学生的页面
    
    # ===== 批改结果（使用 add reducer 聚合并行结果）=====
    grading_results: Annotated[List[Dict[str, Any]], operator.add]  # 各页批改结果
    
    # ===== 跨页题目合并结果 (Requirements: 8.1, 8.2, 8.3, 8.4, 8.5) =====
    merged_questions: List[Dict[str, Any]]  # 合并后的题目结果列表
    cross_page_questions: List[Dict[str, Any]]  # 跨页题目信息列表
    
    # ===== 批次配置与进度 (Requirements: 3.1, 3.4, 10.1) =====
    batch_config: Dict[str, Any]         # 批次配置（batch_size, max_workers 等）
    batch_progress: Annotated[Dict[str, Any], last_value]  # 批次进度信息（使用 last_value reducer 处理并发）
    batch_retry_needed: Annotated[Dict[str, Any], last_value]   # 需要重试的批次信息（使用 last_value reducer 处理并发）

    # ===== 批改结果核验 =====
    
    # ===== 学生聚合（基于索引）=====
    student_boundaries: List[Dict[str, Any]]  # 学生试卷边界列表
    student_results: Annotated[List[Dict[str, Any]], operator.add]  # 按学生聚合的结果（使用 add reducer 聚合并行结果）
    
    # ===== 审核结果 =====
    review_summary: Dict[str, Any]       # 审核摘要
    review_result: Optional[Dict[str, Any]]  # 人工审核结果
    rubric_review_result: Optional[Dict[str, Any]]  # 评分标准审核结果

    # ===== 逻辑复核结果 =====
    logic_review_results: List[Dict[str, Any]]  # 逻辑复核摘要/修正记录

    # ===== 汇总报告 =====
    class_report: Dict[str, Any]        # 班级总结报告
    
    # ===== 导出数据 =====
    export_data: Dict[str, Any]          # 导出数据
    
    # ===== 旧字段（兼容）=====
    detected_students: List[str]         # 检测到的学生 ID 列表
    submission_jobs: Annotated[List[Dict[str, Any]], operator.add]  # 兼容旧代码
    completed_submissions: List[str]     # 已完成的提交 ID 列表
    failed_submissions: List[Dict[str, Any]]  # 失败的提交记录
    batch_results: List[Dict[str, Any]]  # 批量批改结果（兼容）
    
    # ===== 进度信息 =====
    progress: Dict[str, Any]             # 批量进度信息
    current_stage: str                   # 当前阶段
    percentage: float                    # 完成百分比
    
    # ===== 聚合结果 =====
    artifacts: Dict[str, Any]            # 批量产物
    
    # ===== 错误处理 =====
    errors: List[Dict[str, Any]]         # 错误列表
    retry_count: int                     # 重试次数
    
    # ===== 时间戳 =====
    timestamps: Dict[str, str]           # 时间戳记录


class RuleUpgradeGraphState(TypedDict, total=False):
    """规则升级 Graph 状态定义
    
    用于自演化规则挖掘、补丁生成、回归测试、部署流程。
    
    Requirements: 2.1
    """
    
    # ===== 基础信息 =====
    upgrade_id: str                      # 升级任务 ID
    trigger_type: str                    # 触发类型（scheduled/manual）
    
    # ===== 输入数据 =====
    inputs: Dict[str, Any]               # 输入配置
    time_window: Dict[str, str]          # 数据时间窗口
    
    # ===== 规则挖掘 =====
    mined_rules: List[Dict[str, Any]]    # 挖掘出的规则列表
    rule_candidates: List[Dict[str, Any]]  # 候选规则
    
    # ===== 补丁生成 =====
    generated_patches: List[Dict[str, Any]]  # 生成的补丁列表
    patch_metadata: Dict[str, Any]       # 补丁元数据
    
    # ===== 回归测试 =====
    test_results: List[Dict[str, Any]]   # 测试结果列表
    regression_detected: bool            # 是否检测到回归
    
    # ===== 部署 =====
    deployment_status: str               # 部署状态
    deployed_version: Optional[str]      # 已部署版本号
    rollback_triggered: bool             # 是否触发回滚
    
    # ===== 进度信息 =====
    progress: Dict[str, Any]             # 进度详情
    current_stage: str                   # 当前阶段
    percentage: float                    # 完成百分比
    
    # ===== 结果 =====
    artifacts: Dict[str, Any]            # 产物
    
    # ===== 错误处理 =====
    errors: List[Dict[str, Any]]         # 错误列表
    retry_count: int                     # 重试次数
    
    # ===== 时间戳 =====
    timestamps: Dict[str, str]           # 时间戳


def create_initial_grading_state(
    job_id: str,
    submission_id: str,
    exam_id: str,
    student_id: str,
    file_paths: List[str],
    rubric: str
) -> GradingGraphState:
    """创建初始批改状态
    
    Args:
        job_id: 任务 ID
        submission_id: 提交 ID
        exam_id: 考试 ID
        student_id: 学生 ID
        file_paths: 文件路径列表
        rubric: 评分细则
        
    Returns:
        初始化的 GradingGraphState
    """
    return GradingGraphState(
        job_id=job_id,
        submission_id=submission_id,
        exam_id=exam_id,
        student_id=student_id,
        inputs={
            "file_paths": file_paths,
            "rubric": rubric
        },
        file_paths=file_paths,
        rubric=rubric,
        progress={},
        current_stage="initialized",
        percentage=0.0,
        artifacts={},
        grading_results=[],
        total_score=0.0,
        max_total_score=0.0,
        errors=[],
        retry_count=0,
        timestamps={
            "created_at": datetime.now().isoformat()
        },
        needs_review=False,
        review_result=None,
        external_event=None,
        pending_questions=[],
        completed_questions=[],
        active_agent=None,
        agent_results={}
    )


def create_initial_batch_state(
    batch_id: str,
    exam_id: str,
    pdf_path: str,
    rubric: str
) -> BatchGradingGraphState:
    """创建初始批量批改状态
    
    Args:
        batch_id: 批次 ID
        exam_id: 考试 ID
        pdf_path: PDF 文件路径
        rubric: 评分细则
        
    Returns:
        初始化的 BatchGradingGraphState
    """
    return BatchGradingGraphState(
        batch_id=batch_id,
        exam_id=exam_id,
        inputs={
            "pdf_path": pdf_path,
            "rubric": rubric
        },
        pdf_path=pdf_path,
        rubric=rubric,
        index_results={},
        student_page_map={},
        indexed_students=[],
        index_unidentified_pages=[],
        student_boundaries=[],
        detected_students=[],
        submission_jobs=[],
        completed_submissions=[],
        failed_submissions=[],
        progress={},
        current_stage="initialized",
        percentage=0.0,
        artifacts={},
        batch_results=[],
        errors=[],
        retry_count=0,
        timestamps={
            "created_at": datetime.now().isoformat()
        }
    )


def create_initial_upgrade_state(
    upgrade_id: str,
    trigger_type: str,
    time_window: Dict[str, str]
) -> RuleUpgradeGraphState:
    """创建初始规则升级状态
    
    Args:
        upgrade_id: 升级任务 ID
        trigger_type: 触发类型
        time_window: 时间窗口
        
    Returns:
        初始化的 RuleUpgradeGraphState
    """
    return RuleUpgradeGraphState(
        upgrade_id=upgrade_id,
        trigger_type=trigger_type,
        inputs={
            "time_window": time_window
        },
        time_window=time_window,
        mined_rules=[],
        rule_candidates=[],
        generated_patches=[],
        patch_metadata={},
        test_results=[],
        regression_detected=False,
        deployment_status="pending",
        deployed_version=None,
        rollback_triggered=False,
        progress={},
        current_stage="initialized",
        percentage=0.0,
        artifacts={},
        errors=[],
        retry_count=0,
        timestamps={
            "created_at": datetime.now().isoformat()
        }
    )


# ==================== 辅助批改状态定义 ====================


class AssistantGradingState(TypedDict, total=False):
    """辅助批改状态定义
    
    用于深度分析学生作业，不依赖评分标准（Rubric）。
    与主批改系统并行运行，专注于理解作业内容、发现错误、提供改进建议。
    
    工作流：
    初始化 → 理解分析 → 错误识别 → 建议生成 → 深度分析 → 报告生成 → 完成
    """
    
    # ===== 基础信息 =====
    analysis_id: str                          # 分析任务唯一标识符
    submission_id: Optional[str]              # 关联的提交 ID（可选）
    student_id: Optional[str]                 # 学生 ID（可选）
    subject: Optional[str]                    # 科目标识
    
    # ===== 输入数据 =====
    inputs: Dict[str, Any]                    # 输入数据（原始输入）
    image_paths: List[str]                    # 作业图片路径列表
    image_base64_list: List[str]              # 图片 Base64 编码列表
    context_info: Optional[Dict[str, Any]]    # 上下文信息（可选）
    
    # ===== 理解分析结果 =====
    understanding: Dict[str, Any]             # 作业理解结果
    # {
    #   "knowledge_points": [...],  # 识别的知识点
    #   "question_types": [...],    # 题目类型
    #   "solution_approaches": [...],  # 解题思路
    #   "logic_chain": [...],       # 逻辑链条
    # }
    
    # ===== 错误识别结果 =====
    errors: List[Dict[str, Any]]              # 错误记录列表
    # [
    #   {
    #     "error_id": "err_001",
    #     "error_type": "calculation|logic|concept|writing",
    #     "description": "错误描述",
    #     "severity": "high|medium|low",
    #     "location": {...}
    #   }
    # ]
    
    # ===== 改进建议结果 =====
    suggestions: List[Dict[str, Any]]         # 改进建议列表
    # [
    #   {
    #     "suggestion_id": "sug_001",
    #     "suggestion_type": "correction|improvement|alternative",
    #     "description": "建议内容",
    #     "priority": "high|medium|low"
    #   }
    # ]
    
    # ===== 深度分析结果 =====
    deep_analysis: Dict[str, Any]             # 深度分析结果
    # {
    #   "understanding_score": 85.0,
    #   "logic_coherence": 80.0,
    #   "completeness": 90.0,
    #   "overall_score": 85.0,
    #   "strengths": [...],
    #   "weaknesses": [...]
    # }
    
    # ===== 最终报告 =====
    report: Dict[str, Any]                    # 完整分析报告
    report_url: Optional[str]                 # 报告 URL（如果已导出）
    
    # ===== 进度信息 =====
    progress: Dict[str, Any]                  # 进度详情
    current_stage: str                        # 当前执行阶段
    percentage: float                         # 完成百分比 (0.0-100.0)
    
    # ===== 错误处理 =====
    processing_errors: List[Dict[str, Any]]   # 处理过程中的错误
    retry_count: int                          # 重试次数
    
    # ===== 时间戳 =====
    timestamps: Dict[str, str]                # 各阶段时间戳（ISO 格式）


def create_initial_assistant_state(
    analysis_id: str,
    images: List[str],
    submission_id: Optional[str] = None,
    student_id: Optional[str] = None,
    subject: Optional[str] = None,
    context_info: Optional[Dict[str, Any]] = None,
) -> AssistantGradingState:
    """创建初始辅助分析状态
    
    Args:
        analysis_id: 分析任务 ID
        images: 图片 Base64 编码列表
        submission_id: 提交 ID（可选，用于关联主批改）
        student_id: 学生 ID（可选）
        subject: 科目标识（可选）
        context_info: 上下文信息（可选）
        
    Returns:
        初始化的 AssistantGradingState
    """
    return AssistantGradingState(
        analysis_id=analysis_id,
        submission_id=submission_id,
        student_id=student_id,
        subject=subject,
        inputs={
            "images": images,
            "context_info": context_info,
        },
        image_base64_list=images,
        image_paths=[],
        context_info=context_info or {},
        understanding={},
        errors=[],
        suggestions=[],
        deep_analysis={},
        report={},
        report_url=None,
        progress={
            "initialized": True,
            "understand_completed": False,
            "errors_identified": False,
            "suggestions_generated": False,
            "deep_analysis_completed": False,
            "report_generated": False,
        },
        current_stage="initialized",
        percentage=0.0,
        processing_errors=[],
        retry_count=0,
        timestamps={
            "created_at": datetime.now().isoformat()
        },
    )
