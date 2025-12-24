"""LangGraph Graph State 定义

本模块定义了用于 LangGraph 编排的状态类型，用于替代 Temporal 工作流。
"""

from typing import TypedDict, List, Dict, Any, Optional, Annotated
from datetime import datetime
import operator


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
    接收文件 → 图像预处理 → 解析评分标准 → 固定分批批改 → 学生分割 → 结果审核 → 导出结果
    
    Requirements: 5.1, 5.4
    """
    
    # ===== 基础信息 =====
    batch_id: str                        # 批次唯一标识符
    exam_id: str                         # 考试 ID
    api_key: str                         # API Key
    
    # ===== 输入数据 =====
    inputs: Dict[str, Any]               # 批量输入数据
    pdf_path: str                        # 批量 PDF 文件路径
    rubric: str                          # 评分细则文本
    answer_images: List[str]             # 答题图像列表（base64 或路径）
    rubric_images: List[str]             # 评分标准图像列表
    
    # ===== 预处理结果 =====
    processed_images: List[str]          # 预处理后的图像
    parsed_rubric: Dict[str, Any]        # 解析后的评分标准
    
    # ===== 批改结果（使用 add reducer 聚合并行结果）=====
    grading_results: Annotated[List[Dict[str, Any]], operator.add]  # 各页批改结果
    
    # ===== 学生分割（批改后）=====
    student_boundaries: List[Dict[str, Any]]  # 学生试卷边界列表
    student_results: List[Dict[str, Any]]     # 按学生聚合的结果
    
    # ===== 审核结果 =====
    review_summary: Dict[str, Any]       # 审核摘要
    
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
