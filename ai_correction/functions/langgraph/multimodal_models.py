#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多模态数据模型 - 支持文本、图片、PDF等多种模态的统一表示
设计目标：消除OCR依赖，直接支持LLM视觉能力
"""

from typing import TypedDict, List, Dict, Any, Optional, Literal
from datetime import datetime
from pathlib import Path


# ==================== 多模态文件模型 ====================

class MultiModalFile(TypedDict):
    """
    多模态文件统一表示
    支持类型：文本、图片、PDF、Word文档
    """
    file_path: str                    # 原始文件路径
    modality_type: Literal['text', 'image', 'pdf_text', 'pdf_image', 'document']
    content_representation: Any       # 内容表示（根据模态不同而不同）
    metadata: Dict[str, Any]          # 元数据（文件大小、格式、编码等）


# ==================== 🆕 深度协作数据模型 ====================

class StudentInfo(TypedDict):
    """学生信息模型（用于批次管理）"""
    student_id: str                   # 学号或自动生成ID
    name: str                         # 学生姓名
    class_name: Optional[str]         # 班级名称
    answer_files: List[str]           # 该学生的答案文件路径列表
    detection_confidence: float       # 识别置信度（0-1）
    detection_method: str             # 识别方法（vision/filename/manual）


class BatchInfo(TypedDict):
    """批次信息模型（用于并行处理规划）"""
    batch_id: str                     # 批次唯一标识
    students: List[StudentInfo]       # 本批次包含的学生列表
    question_range: str               # 题目范围（"Q1-Q3"或"all"）
    estimated_tokens: int             # 预估token消耗
    parallel_priority: int            # 并行优先级（数字越大优先级越高）


class CompressedCriterion(TypedDict):
    """压缩版评分点（用于Token优化）"""
    id: str                           # 评分点ID
    desc: str                         # 简短描述
    pts: float                        # 分值
    tree: Dict[str, Any]              # 决策树
    quick: str                        # 快速检查方法


class RubricPackage(TypedDict):
    """批次专属评分包（由RubricMasterAgent生成）"""
    batch_id: str                     # 目标批次ID
    compressed_criteria: List[CompressedCriterion]  # 压缩版评分点列表
    decision_trees: Dict[str, Dict]   # 评分点ID -> 决策树映射
    quick_checks: Dict[str, str]      # 评分点ID -> 快速检查方法
    total_points: float               # 总分
    reference_examples: Optional[Dict[str, Dict]]  # 参考示例（满分/零分）


class CompressedQuestion(TypedDict):
    """压缩版题目（用于Token优化）"""
    id: str                           # 题目ID
    compressed_text: str              # 压缩后的题目文本
    type: str                         # 题型
    key_formulas: Optional[List[str]] # 关键公式
    key_concepts: Optional[List[str]] # 关键概念


class QuestionContextPackage(TypedDict):
    """批次专属题目上下文包（由QuestionContextAgent生成）"""
    batch_id: str                     # 目标批次ID
    compressed_questions: List[CompressedQuestion]  # 压缩版题目列表
    quick_reference: Dict[str, str]   # 题目ID -> 极简描述
    shared_context: Optional[str]     # 共享背景信息
    
    
class TextContent(TypedDict):
    """文本内容表示"""
    text: str                         # 纯文本内容
    encoding: str                     # 文本编码
    language: Optional[str]           # 语言（可选）


class ImageContent(TypedDict):
    """图片内容表示（用于Vision API）"""
    base64_data: str                  # base64编码的图片数据
    mime_type: str                    # MIME类型（image/jpeg, image/png等）
    width: Optional[int]              # 图片宽度（可选）
    height: Optional[int]             # 图片高度（可选）


class PDFTextContent(TypedDict):
    """PDF文本内容表示（纯文本PDF）"""
    text: str                         # 提取的文本内容
    page_count: int                   # 页数
    extraction_method: str            # 提取方法（PyPDF2等）


class PDFImageContent(TypedDict):
    """PDF图片内容表示（扫描版PDF或用户偏好使用Vision）"""
    pages: List[ImageContent]         # 每页转换为图片
    page_count: int                   # 页数
    conversion_method: str            # 转换方法


class DocumentContent(TypedDict):
    """Word文档内容表示"""
    text: str                         # 提取的文本内容
    has_images: bool                  # 是否包含图片
    extraction_method: str            # 提取方法（python-docx等）


# ==================== 理解结果模型 ====================

class QuestionUnderstanding(TypedDict):
    """题目理解结果"""
    question_id: str                  # 题目唯一标识
    question_text: str                # 题目文本（文本化表示）
    key_requirements: List[str]       # 关键要求列表
    context: Dict[str, Any]           # 上下文信息
    difficulty_level: Optional[str]   # 难度级别（可选）
    subject: Optional[str]            # 学科（可选）
    modality_source: str              # 来源模态（text/vision）


class AnswerUnderstanding(TypedDict):
    """答案理解结果"""
    answer_id: str                    # 答案唯一标识
    answer_text: str                  # 答案文本（文本化表示）
    key_points: List[str]             # 关键答题点列表
    structure: Dict[str, Any]         # 答案结构分析
    completeness: Optional[str]       # 完整性评估（可选）
    modality_source: str              # 来源模态（text/vision）


class RubricUnderstanding(TypedDict):
    """评分标准理解结果"""
    rubric_id: str                    # 标准唯一标识
    criteria: List['GradingCriterion'] # 评分标准列表
    total_points: float               # 总分
    grading_rules: Dict[str, Any]     # 评分规则
    strictness_guidance: Optional[str] # 严格程度指导（可选）


class GradingCriterion(TypedDict, total=False):
    """单个评分标准（详细版）"""
    criterion_id: str                 # 评分点唯一标识
    question_id: Optional[str]       # 题目编号（如Q1, Q2等）
    description: str                 # 评分点描述
    detailed_requirements: Optional[str]  # 详细要求（具体说明需要什么才能得分）
    points: float                     # 分值
    standard_answer: Optional[str]    # 标准答案或标准步骤（如果有）
    evaluation_method: str            # 评估方法（exact_match/semantic/calculation/step_check等）
    scoring_criteria: Optional[Dict[str, str]]  # 得分条件（full_credit/partial_credit/no_credit）
    alternative_methods: Optional[List[str]]  # 另类解法列表
    keywords: Optional[List[str]]     # 关键词（可选）
    required_elements: Optional[List[str]]  # 必需元素（可选）
    common_mistakes: Optional[List[str]]  # 常见错误列表（可选）


# ==================== 评估结果模型 ====================

class CriteriaEvaluation(TypedDict, total=False):
    """单个评分点的评估结果（详细版）"""
    criterion_id: str                 # 对应的评分点ID
    max_score: float                  # 满分
    score_earned: float               # 实际得分
    is_met: bool                      # 是否满足
    satisfaction_level: Literal['完全满足', '部分满足', '未满足']  # 满足程度
    student_work: Optional[str]        # 学生的作答情况详细描述（包括公式、步骤、计算过程、中间结果、最终答案）
    justification: str                # 评分理由（详细说明为什么给这个分数，包括学生答案与标准答案的对比）
    matched_criterion: Optional[str]   # 符合评分标准的哪一项（如：'正确应用指数运算法则，得到a^10'）
    feedback: Optional[str]           # 具体反馈意见（针对该评分点的具体建议）
    evidence: List[str]               # 证据列表（从答案中提取的关键部分，包括具体计算式、中间结果、最终答案）
    suggestions: Optional[List[str]]  # 改进建议（可选）


# ==================== 增强的状态模型字段 ====================

class MultiModalGradingStateExtension(TypedDict):
    """
    对GradingState的多模态扩展字段
    这些字段将被添加到现有的GradingState中
    """
    
    # 多模态文件信息
    question_multimodal_files: List[MultiModalFile]
    answer_multimodal_files: List[MultiModalFile]
    marking_multimodal_files: List[MultiModalFile]
    
    # 理解结果
    question_understanding: Optional[QuestionUnderstanding]
    answer_understanding: Optional[AnswerUnderstanding]
    rubric_understanding: Optional[RubricUnderstanding]
    
    # 评估结果
    criteria_evaluations: List[CriteriaEvaluation]
    
    # 处理元数据
    multimodal_processing_metadata: Dict[str, Any]


# ==================== 工具函数 ====================

def create_multimodal_file(
    file_path: str,
    modality_type: str,
    content_representation: Any,
    **metadata
) -> MultiModalFile:
    """
    创建MultiModalFile对象的工厂函数
    
    Args:
        file_path: 文件路径
        modality_type: 模态类型
        content_representation: 内容表示
        **metadata: 额外的元数据
    
    Returns:
        MultiModalFile对象
    """
    path = Path(file_path)
    
    default_metadata = {
        'file_name': path.name,
        'file_size': path.stat().st_size if path.exists() else 0,
        'file_extension': path.suffix,
        'created_at': datetime.now().isoformat(),
    }
    
    default_metadata.update(metadata)
    
    return MultiModalFile(
        file_path=file_path,
        modality_type=modality_type,
        content_representation=content_representation,
        metadata=default_metadata
    )


def create_text_content(text: str, encoding: str = 'utf-8', language: Optional[str] = None) -> TextContent:
    """创建文本内容对象"""
    return TextContent(
        text=text,
        encoding=encoding,
        language=language
    )


def create_image_content(
    base64_data: str,
    mime_type: str,
    width: Optional[int] = None,
    height: Optional[int] = None
) -> ImageContent:
    """创建图片内容对象"""
    return ImageContent(
        base64_data=base64_data,
        mime_type=mime_type,
        width=width,
        height=height
    )


def create_grading_criterion(
    criterion_id: str,
    description: str,
    points: float,
    evaluation_method: str = 'semantic',
    **kwargs
) -> GradingCriterion:
    """创建评分标准对象"""
    return GradingCriterion(
        criterion_id=criterion_id,
        description=description,
        points=points,
        evaluation_method=evaluation_method,
        keywords=kwargs.get('keywords'),
        required_elements=kwargs.get('required_elements')
    )


def create_criteria_evaluation(
    criterion_id: str,
    is_met: bool,
    score_earned: float,
    justification: str,
    evidence: List[str],
    satisfaction_level: Optional[str] = None,
    **kwargs
) -> CriteriaEvaluation:
    """创建评分点评估结果对象"""
    if satisfaction_level is None:
        if is_met:
            satisfaction_level = '完全满足'
        elif score_earned > 0:
            satisfaction_level = '部分满足'
        else:
            satisfaction_level = '不满足'
    
    return CriteriaEvaluation(
        criterion_id=criterion_id,
        is_met=is_met,
        satisfaction_level=satisfaction_level,
        score_earned=score_earned,
        justification=justification,
        evidence=evidence,
        suggestions=kwargs.get('suggestions')
    )
