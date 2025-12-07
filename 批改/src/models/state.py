"""LangGraph 智能体状态定义"""

from typing import TypedDict, List, Dict, Any, Optional
from .grading import RubricMappingItem


class GradingState(TypedDict, total=False):
    """批改智能体状态
    
    使用 TypedDict 定义 LangGraph 状态，支持类型检查
    total=False 表示所有字段都是可选的
    """
    
    # ===== 静态输入 =====
    question_image: str  # Base64 编码的题目图像
    rubric: str  # 评分细则文本
    standard_answer: Optional[str]  # 标准答案（可选）
    max_score: float  # 满分
    
    # ===== 动态推理数据 =====
    vision_analysis: str  # 视觉分析结果（学生解题步骤描述）
    rubric_mapping: List[Dict[str, Any]]  # 评分点映射列表
    initial_score: float  # 初始评分
    reasoning_trace: List[str]  # 推理轨迹
    critique_feedback: Optional[str]  # 反思反馈
    
    # ===== 最终输出 =====
    final_score: float  # 最终得分
    confidence: float  # 置信度（0.0-1.0）
    visual_annotations: List[Dict[str, Any]]  # 视觉标注
    student_feedback: str  # 给学生的反馈
    
    # ===== 控制标志 =====
    revision_count: int  # 修正次数
    is_finalized: bool  # 是否已最终化
    error: Optional[str]  # 错误信息（如果有）


class WorkflowInput(TypedDict):
    """工作流输入"""
    submission_id: str
    student_id: str
    exam_id: str
    file_paths: List[str]


class QuestionGradingInput(TypedDict):
    """题目批改输入"""
    submission_id: str
    question_id: str
    image_b64: str
    rubric: str
    max_score: float
    standard_answer: Optional[str]
