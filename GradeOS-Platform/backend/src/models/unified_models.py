"""
GradeOS 统一数据模型
基于 后端数据库需求文档_基于API整合.md 设计
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


# ============ 枚举类型 ============

class UserType(str, Enum):
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"


class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class AssignmentStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CLOSED = "closed"
    ARCHIVED = "archived"


class GradingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    AI_GRADED = "ai_graded"
    TEACHER_REVIEWED = "teacher_reviewed"
    COMPLETED = "completed"
    FAILED = "failed"


class ErrorSeverity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ============ 用户认证模块 ============

class User(BaseModel):
    """用户表"""
    user_id: str
    username: str
    password_hash: str
    email: Optional[str] = None
    phone: Optional[str] = None
    user_type: UserType
    real_name: Optional[str] = None
    avatar_url: Optional[str] = None
    status: UserStatus = UserStatus.ACTIVE
    last_login_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class UserProfile(BaseModel):
    """用户配置表"""
    profile_id: Optional[int] = None
    user_id: str
    grade: Optional[str] = None
    school: Optional[str] = None
    class_id: Optional[str] = None
    subject: Optional[str] = None
    preferences: Dict[str, Any] = Field(default_factory=dict)
    learning_style: Optional[str] = None
    language: str = "zh-CN"
    theme: str = "light"
    notifications: bool = True


# ============ 班级管理模块 ============

class Class(BaseModel):
    """班级表"""
    class_id: str
    class_name: str
    teacher_id: str
    grade_level: Optional[str] = None
    subject: Optional[str] = None
    semester: Optional[str] = None
    invite_code: str
    student_count: int = 0
    max_students: int = 50
    is_active: bool = True
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class StudentClassRelation(BaseModel):
    """学生班级关系表"""
    id: Optional[int] = None
    student_id: str
    class_id: str
    join_date: datetime = Field(default_factory=datetime.utcnow)
    status: str = "active"
    is_admin: bool = False


# ============ 作业管理模块 ============

class Assignment(BaseModel):
    """作业表"""
    assignment_id: str
    homework_id: Optional[str] = None  # 兼容 API
    class_id: str
    teacher_id: str
    title: str
    description: Optional[str] = None
    subject: Optional[str] = None
    total_questions: int = 0
    max_score: float = 100.0
    status: AssignmentStatus = AssignmentStatus.DRAFT
    publish_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    allow_late_submission: bool = False
    max_attempts: int = 1
    instructions: Optional[str] = None
    requirements: Optional[str] = None
    attachment_urls: List[str] = Field(default_factory=list)
    rubric_data: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AssignmentSubmission(BaseModel):
    """作业提交表"""
    submission_id: str
    assignment_id: str
    student_id: str
    attempt_number: int = 1
    answer_files: List[str] = Field(default_factory=list)
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
    grading_status: GradingStatus = GradingStatus.PENDING
    grading_mode: str = "standard"
    total_score: Optional[float] = None
    max_score: Optional[float] = None
    percentage: Optional[float] = None
    grade_level: Optional[str] = None
    is_late: bool = False
    teacher_comment: Optional[str] = None
    teacher_adjusted_score: Optional[float] = None
    is_reviewed: bool = False
    reviewed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ============ AI 批改模块 ============

class GradingTask(BaseModel):
    """批改任务表"""
    task_id: str
    submission_id: str
    student_id: str
    subject: Optional[str] = None
    total_questions: int = 0
    status: str = "pending"
    ai_model: str = "google/gemini-2.5-flash-lite"
    processing_mode: str = "standard"
    confidence_score: Optional[float] = None
    processing_time_ms: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


class GradingResult(BaseModel):
    """批改结果表"""
    result_id: Optional[int] = None
    task_id: str
    question_id: str
    question_no: Optional[int] = None
    score: float
    max_score: float
    is_correct: Optional[bool] = None
    feedback: Optional[str] = None
    strategy: Optional[str] = None
    confidence: Optional[float] = None
    error_type: Optional[str] = None
    suggestion: Optional[str] = None
    correct_answer: Optional[str] = None
    annotations: Dict[str, Any] = Field(default_factory=dict)
    coordinates: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ============ 错题分析模块 ============

class ErrorRecord(BaseModel):
    """错题记录表"""
    error_id: str
    analysis_id: Optional[str] = None
    student_id: str
    question_id: Optional[str] = None
    subject: Optional[str] = None
    question_type: Optional[str] = None
    original_question: Dict[str, Any] = Field(default_factory=dict)
    student_answer: Optional[str] = None
    student_solution_steps: List[Dict[str, Any]] = Field(default_factory=list)
    correct_answer: Optional[str] = None
    error_type: Optional[str] = None
    error_severity: Optional[ErrorSeverity] = None
    root_cause: Optional[str] = None
    knowledge_points: List[str] = Field(default_factory=list)
    knowledge_gaps: List[Dict[str, Any]] = Field(default_factory=list)
    detailed_analysis: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class LearningRecommendation(BaseModel):
    """学习建议表"""
    recommendation_id: str
    student_id: str
    analysis_id: Optional[str] = None
    recommendation_type: Optional[str] = None
    content: Optional[str] = None
    resources: List[Dict[str, Any]] = Field(default_factory=list)
    immediate_actions: List[Dict[str, Any]] = Field(default_factory=list)
    practice_exercises: List[Dict[str, Any]] = Field(default_factory=list)
    learning_strategies: List[str] = Field(default_factory=list)
    learning_path: Dict[str, Any] = Field(default_factory=dict)
    priority: int = 1
    status: str = "pending"
    feedback_rating: Optional[int] = None
    feedback_comment: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None


# ============ 知识图谱模块 ============

class KnowledgePoint(BaseModel):
    """知识点表"""
    concept_id: str
    concept_name: str
    point_name: str
    subject: Optional[str] = None
    chapter: Optional[str] = None
    difficulty: Optional[str] = None
    difficulty_level: Optional[int] = None
    description: Optional[str] = None
    parent_point_id: Optional[str] = None
    prerequisites: List[str] = Field(default_factory=list)
    related_points: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class StudentKnowledgeMastery(BaseModel):
    """学生知识掌握表"""
    mastery_id: Optional[int] = None
    student_id: str
    concept_id: str
    mastery_level: float = 0.0
    correct_count: int = 0
    total_count: int = 0
    last_assignment_id: Optional[str] = None
    last_score: Optional[float] = None
    last_evaluated_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ============ 统计分析模块 ============

class ClassStatistics(BaseModel):
    """班级统计表"""
    stat_id: str
    class_id: str
    assignment_id: Optional[str] = None
    class_name: Optional[str] = None
    total_students: int = 0
    submitted_count: int = 0
    graded_count: int = 0
    average_score: Optional[float] = None
    max_score: Optional[float] = None
    min_score: Optional[float] = None
    median_score: Optional[float] = None
    pass_rate: Optional[float] = None
    score_distribution: Dict[str, int] = Field(default_factory=dict)
    common_errors: List[Dict[str, Any]] = Field(default_factory=list)
    error_distribution: List[Dict[str, Any]] = Field(default_factory=list)
    knowledge_mastery: Dict[str, Any] = Field(default_factory=dict)
    teaching_suggestions: List[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class SystemLog(BaseModel):
    """系统日志表"""
    log_id: Optional[int] = None
    user_id: Optional[str] = None
    action: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_data: Dict[str, Any] = Field(default_factory=dict)
    response_status: Optional[int] = None
    processing_time_ms: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
