#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LangGraph 状态定义 - 基于Orchestrator-Worker模式
支持批次并行处理、多模态token坐标、双模式批改
符合设计文档: AI批改LangGraph Agent架构设计文档

多模态增强版本：
- 新增多模态文件字段
- 新增理解结果字段（Question/Answer/Rubric Understanding）
- 新增基于标准的评估结果字段
"""

from typing import TypedDict, List, Dict, Any, Optional, Annotated
from datetime import datetime
import operator

# 导入多模态数据模型
try:
    from .multimodal_models import (
        MultiModalFile,
        QuestionUnderstanding,
        AnswerUnderstanding,
        RubricUnderstanding,
        GradingCriterion,
        CriteriaEvaluation,
        # 🆕 深度协作数据模型
        StudentInfo,
        BatchInfo,
        RubricPackage,
        QuestionContextPackage
    )
except ImportError:
    # 如果导入失败，使用占位类型
    MultiModalFile = Dict[str, Any]
    QuestionUnderstanding = Dict[str, Any]
    AnswerUnderstanding = Dict[str, Any]
    RubricUnderstanding = Dict[str, Any]
    GradingCriterion = Dict[str, Any]
    CriteriaEvaluation = Dict[str, Any]
    StudentInfo = Dict[str, Any]
    BatchInfo = Dict[str, Any]
    RubricPackage = Dict[str, Any]
    QuestionContextPackage = Dict[str, Any]

# Reducer函数：用于处理并发更新，返回最后一个非None值
def _set_last_value(left: Optional[Dict[str, Any]], right: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Reducer函数：返回最后一个非None值"""
    return right if right is not None else left

class GradingState(TypedDict):
    """
    LangGraph 批改状态模型
    核心功能:
    - 批次并行处理 (batches, evaluations)
    - 多模态token坐标 (mm_tokens)
    - 学生信息识别 (student_info)
    - 双模式批改 (mode: efficient/professional)
    - 坐标标注 (coordinate_annotations)
    - 知识点挖掘 (knowledge_points)
    """
    
    # ==================== 基础任务信息 ====================
    # 注意：这些字段在并行节点中不应被更新，只应在初始化时设置
    task_id: str
    user_id: str
    assignment_id: str  # 作业标识
    timestamp: datetime
    
    # ==================== 文件信息 ====================
    question_files: List[str]  # 题目文件路径
    answer_files: List[str]    # 学生答案文件路径（作业图片）
    marking_files: List[str]   # 评分标准文件路径
    images: List[str]          # 作业图片列表（完整路径）
    
    # ==================== 🆕 多模态文件信息（新增）====================
    question_multimodal_files: List[Dict[str, Any]]  # 多模态题目文件
    answer_multimodal_files: List[Dict[str, Any]]    # 多模态答案文件
    marking_multimodal_files: List[Dict[str, Any]]   # 多模态评分标准文件
    
    # ==================== 批改参数 ====================
    strictness_level: str      # 严格程度:宽松/中等/严格
    language: str              # 语言:zh/en
    mode: str                  # 批改模式:efficient(高效)/professional(专业)
    target_questions: List[str]  # 需要重点批改的题号（空表示整卷）
    scope_description: str       # 题号范围描述
    scope_warnings: List[str]    # 范围解析警告
    
    # ==================== 多模态提取结果（核心） ====================
    mm_tokens: List[Dict[str, Any]]       # 多模态模型返回的带坐标token列表
    student_info: Dict[str, Any]          # 学生信息(姓名、学号、班级)
    
    # ==================== OCR & Vision 结果（已废弃 - 不再使用） ====================
    # ⚠️ 以下字段已废弃，系统已完全迁移至多模态LLM Vision能力
    # 保留仅为向后兼容，请使用 question_multimodal_files, answer_multimodal_files 替代
    ocr_results: Dict[str, Any]           # [DEPRECATED] OCR 文本识别结果
    image_regions: Dict[str, List[Dict]]  # [DEPRECATED] 图像区域检测结果
    preprocessed_images: Dict[str, str]   # [DEPRECATED] 预处理后的图像路径
    
    # ==================== 评分标准解析 ====================
    rubric_text: str                      # 原始评分标准文本
    rubric_struct: Dict[str, Any]         # 结构化评分规则(JSON格式)
    rubric_data: Dict[str, Any]           # 评分数据（保留兼容性）
    scoring_criteria: List[Dict]          # 评分细则（保留兼容性）
    
    # ==================== 🆕 理解结果（新增）====================
    # 使用Annotated处理并发更新：并行节点会更新这些字段
    # 注意：每个节点只更新自己的键，但LangGraph要求明确声明并发更新
    question_understanding: Annotated[Optional[Dict[str, Any]], _set_last_value]  # 题目理解结果
    answer_understanding: Annotated[Optional[Dict[str, Any]], _set_last_value]    # 答案理解结果
    rubric_understanding: Annotated[Optional[Dict[str, Any]], _set_last_value]    # 评分标准理解结果
    rubric_parsing_result: Optional[Dict[str, Any]]   # 批改标准解析结果（用于输出）
    agent_collaboration: Optional[Dict[str, Any]]     # Agent协作过程信息（用于输出）
    
    # ==================== 题目识别与批次规划 ====================
    questions: List[Dict[str, Any]]       # 题目信息列表(含题号、分值、区域、tokens)
    batches: List[Dict[str, Any]]         # 批次划分方案
    
    # ==================== AI 评分结果 ====================
    evaluations: Annotated[List[Dict[str, Any]], operator.add]  # 各题评分结果列表（支持并行批次累加）
    scoring_results: Dict[str, Any]       # 评分结果（保留兼容性）
    detailed_feedback: Annotated[List[Dict], operator.add]  # 详细反馈（保留兼容性，支持并行累加）

    # ==================== 🆕 基于标准的评估结果（新增）====================
    criteria_evaluations: Annotated[List[Dict[str, Any]], operator.add]  # 基于评分标准的评估结果列表（支持并行累加）

    # ==================== 🎯 坐标标注（核心功能） ====================
    annotations: Annotated[List[Dict[str, Any]], operator.add]  # 标注坐标列表（支持并行累加）
    coordinate_annotations: Annotated[List[Dict], operator.add]  # 坐标标注数据（保留兼容性，支持并行累加）
    error_regions: Annotated[List[Dict], operator.add]  # 错误区域坐标（保留兼容性，支持并行累加）
    cropped_regions: Annotated[List[Dict], operator.add]  # 裁剪区域数据（保留兼容性，支持并行累加）
    
    # ==================== 🧠 知识点挖掘（核心功能） ====================
    knowledge_points: Annotated[List[Dict], operator.add]  # 知识点分析（支持并行累加）
    error_analysis: Dict[str, Any]        # 错题分析
    learning_suggestions: Annotated[List[str], operator.add]  # 学习建议（支持并行累加）
    difficulty_assessment: Dict[str, Any] # 难度评估

    # ==================== 专业模式扩展字段 ====================
    total_score: float                    # 总分
    section_scores: Dict[str, float]      # 各部分分数
    student_evaluation: Dict[str, Any]    # 学生个人评价(专业模式)
    class_evaluation: Dict[str, Any]      # 班级整体评价(专业模式)
    
    # ==================== 导出与集成 ====================
    export_payload: Dict[str, Any]        # 推送至班级系统的数据包
    final_report: Dict[str, Any]          # 最终报告（保留兼容性）
    export_data: Dict[str, Any]           # 导出数据（保留兼容性）
    visualization_data: Dict[str, Any]    # 可视化数据（保留兼容性）
    
    # ==================== 🆕 深度协作相关字段（新增）====================
    students_info: Annotated[List[Any], operator.add]  # 学生信息列表（支持并行累加）
    batches_info: Annotated[List[Any], operator.add]   # 批次规划信息（支持并行累加）
    batch_rubric_packages: Dict[str, Any] # 批次专属评分包 {batch_id: RubricPackage}
    question_context_packages: Dict[str, Any]  # 批次专属题目上下文 {batch_id: QuestionContextPackage}
    grading_results: Annotated[List[Dict[str, Any]], operator.add]  # 所有批改结果（支持并行累加）
    student_reports: Annotated[List[Dict[str, Any]], operator.add]  # 学生报告（支持并行累加）
    class_analysis: Dict[str, Any]         # 班级分析报告
    student_alias_map: Dict[str, str]      # 未命名学生的别名映射
    graded_questions: List[str]            # 实际批改的题目
    skipped_questions: List[str]           # 因范围限制被跳过的题目
    
    # ==================== 处理状态 ====================
    current_step: str                     # 当前步骤
    progress_percentage: float            # 进度百分比(0-100)
    completion_status: str                # 完成状态:in_progress/completed/failed
    completed_at: str                     # 完成时间
    streaming_callback: Any               # 流式传输回调函数（用于实时显示 AI 思考过程）

    # ==================== 错误和步骤记录 ====================
    errors: Annotated[List[Dict[str, Any]], operator.add]  # 错误记录（支持多个节点累加）
    step_results: Dict[str, Any]          # 步骤结果
    
    # ==================== 最终结果 ====================
    final_score: float                    # 最终得分
    grade_level: str                      # 等级评定(A/B/C/D/F)
    warnings: Annotated[List[str], operator.add]  # 警告信息（支持多个节点累加）
    
    # ==================== 元数据 ====================
    processing_time: float                # 处理时间(秒)
    model_versions: Dict[str, str]        # 使用的模型版本
    quality_metrics: Dict[str, float]     # 质量指标


# ==================== 数据模型类 ====================

class MMToken(TypedDict):
    """
    多模态Token数据结构
    多模态大模型返回的带像素坐标的文本片段
    """
    id: str                      # token唯一标识
    text: str                    # 文本内容
    page: int                    # 所在页码(0-based)
    bbox: Dict[str, float]       # 边界框坐标 {x1, y1, x2, y2} 像素坐标
    conf: float                  # 置信度 (0-1)
    line_id: str                 # 同一行标识符


class Question(TypedDict):
    """
    题目信息数据结构
    每道题目的区域和相关token
    """
    qid: str                     # 题号 (Q1, Q2, ...)
    max_score: float             # 最大分值
    region: Dict[str, Any]       # 题目在图像中的区域 {page, start_token_id, end_token_id}
    token_ids: List[str]         # 关联的token ID列表
    keywords: List[str]          # 从评分标准提取的关键词


class Batch(TypedDict):
    """
    批次划分数据结构
    用于并行处理的批次信息
    """
    batch_index: int             # 批次索引(0-based)
    question_ids: List[str]      # 包含的题目ID列表
    estimated_tokens: int        # 预估token数


class Evaluation(TypedDict):
    """
    评分结果数据结构
    支持高效模式和专业模式
    """
    qid: str                          # 题号
    score: float                      # 得分
    max_score: float                  # 最大分值
    label: str                        # 状态: correct/partial/wrong
    rubric_item_id: str               # 触发的评分项ID
    error_token_ids: List[str]        # 错误的token ID列表
    
    # 专业模式扩展字段
    summary: Optional[str]            # 答案摘要(仅专业模式)
    error_analysis: Optional[List[Dict[str, Any]]]  # 错误详情解析(仅专业模式)
    comment: Optional[str]            # 个人评价(仅专业模式)


class Annotation(TypedDict):
    """
    坐标标注数据结构
    用于在图片上标记错误位置
    """
    annotation_id: str           # 标注唯一标识
    qid: str                     # 题号
    page: int                    # 页码
    bbox: Dict[str, float]       # 坐标 {x1, y1, x2, y2} 像素坐标
    hint: str                    # 提示信息(如"计算错误")
    error_type: str              # 错误类型


class KnowledgePoint(TypedDict):
    """
    知识点数据结构
    用于知识点挖掘和分析
    """
    point_id: str                     # 知识点唯一标识
    subject: str                      # 学科(数学/物理/化学等)
    topic: str                        # 主题/知识点名称
    concept: str                      # 概念分类
    difficulty_level: str             # 难度级别: easy/medium/hard
    mastery_status: str               # 掌握状态: good/fair/weak/unknown
    related_errors: List[str]         # 相关错误ID列表
    improvement_suggestions: List[str] # 改进建议列表


class ErrorAnalysis(TypedDict):
    """
    错误分析数据结构
    用于详细的错题分析
    """
    error_id: str                    # 错误唯一标识
    error_type: str                  # 错误类型: calculation/concept/method/logic/careless/incomplete/format
    error_description: str           # 错误描述
    correct_solution: str            # 正确解答
    knowledge_gaps: List[str]        # 知识缺陷列表
    remediation_plan: List[str]      # 补救计划列表
    root_cause: str                  # 根本原因
    severity: str                    # 严重程度: high/medium/low
    confidence: float                # 置信度 (0-1)


# ==================== 兼容性别名 ====================
# 为了保持与现有代码兼容，保留旧的类型别名
AnnotationData = Annotation  # 向后兼容
