"""辅助批改数据库表定义"""

from sqlalchemy import Column, String, Integer, Float, JSON, DateTime, Text, Enum as SQLEnum, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()


class AnalysisStatus(enum.Enum):
    """分析状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AssistantAnalysisReport(Base):
    """辅助分析报告表"""
    __tablename__ = "assistant_analysis_reports"
    
    # 主键
    analysis_id = Column(String(64), primary_key=True, comment="分析 ID")
    
    # 关联信息
    submission_id = Column(String(64), nullable=True, index=True, comment="关联提交 ID")
    student_id = Column(String(64), nullable=True, index=True, comment="学生 ID")
    subject = Column(String(64), nullable=True, index=True, comment="科目")
    
    # 分析结果（JSON 格式）
    understanding = Column(JSON, nullable=True, comment="理解分析结果")
    errors = Column(JSON, nullable=True, comment="错误列表")
    suggestions = Column(JSON, nullable=True, comment="建议列表")
    deep_analysis = Column(JSON, nullable=True, comment="深度分析结果")
    report = Column(JSON, nullable=True, comment="完整报告")
    
    # 报告信息
    report_url = Column(String(512), nullable=True, comment="报告存储 URL")
    status = Column(
        SQLEnum(AnalysisStatus),
        default=AnalysisStatus.PENDING,
        nullable=False,
        index=True,
        comment="分析状态"
    )
    
    # 进度信息
    current_stage = Column(String(64), nullable=True, comment="当前阶段")
    percentage = Column(Float, default=0.0, comment="完成百分比")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, comment="创建时间")
    started_at = Column(DateTime, nullable=True, comment="开始时间")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")
    
    # 错误信息
    error_message = Column(Text, nullable=True, comment="错误信息")
    retry_count = Column(Integer, default=0, comment="重试次数")
    
    # 索引
    __table_args__ = (
        {"comment": "辅助批改分析报告表"}
    )


class AssistantErrorRecord(Base):
    """错误记录表（细粒度存储）"""
    __tablename__ = "assistant_error_records"
    
    # 主键
    error_id = Column(String(64), primary_key=True, comment="错误 ID")
    
    # 关联
    analysis_id = Column(
        String(64),
        ForeignKey("assistant_analysis_reports.analysis_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="关联分析 ID"
    )
    
    # 错误信息
    error_type = Column(
        SQLEnum("calculation", "logic", "concept", "writing", name="error_type_enum"),
        nullable=False,
        comment="错误类型"
    )
    description = Column(Text, nullable=False, comment="错误描述")
    severity = Column(
        SQLEnum("high", "medium", "low", name="error_severity_enum"),
        nullable=False,
        comment="严重程度"
    )
    
    # 位置信息（JSON 格式）
    location = Column(JSON, nullable=True, comment="错误位置")
    
    # 关联信息
    affected_steps = Column(JSON, nullable=True, comment="影响的步骤")
    correct_approach = Column(Text, nullable=True, comment="正确的做法")
    context = Column(Text, nullable=True, comment="上下文")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, comment="创建时间")
    
    __table_args__ = (
        {"comment": "辅助批改错误记录表"}
    )


class AssistantSuggestion(Base):
    """建议记录表（细粒度存储）"""
    __tablename__ = "assistant_suggestions"
    
    # 主键
    suggestion_id = Column(String(64), primary_key=True, comment="建议 ID")
    
    # 关联
    analysis_id = Column(
        String(64),
        ForeignKey("assistant_analysis_reports.analysis_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="关联分析 ID"
    )
    related_error_id = Column(String(64), nullable=True, comment="关联错误 ID")
    
    # 建议信息
    suggestion_type = Column(
        SQLEnum("correction", "improvement", "alternative", name="suggestion_type_enum"),
        nullable=False,
        comment="建议类型"
    )
    description = Column(Text, nullable=False, comment="建议描述")
    example = Column(Text, nullable=True, comment="示例")
    priority = Column(
        SQLEnum("high", "medium", "low", name="suggestion_priority_enum"),
        nullable=False,
        comment="优先级"
    )
    
    # 扩展信息
    resources = Column(JSON, nullable=True, comment="学习资源列表")
    expected_improvement = Column(Text, nullable=True, comment="预期改进效果")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, comment="创建时间")
    
    __table_args__ = (
        {"comment": "辅助批改建议记录表"}
    )


# ==================== 数据库迁移脚本 ====================


MIGRATION_SQL = """
-- 创建辅助分析报告表
CREATE TABLE IF NOT EXISTS assistant_analysis_reports (
    analysis_id VARCHAR(64) PRIMARY KEY,
    submission_id VARCHAR(64),
    student_id VARCHAR(64),
    subject VARCHAR(64),
    understanding JSONB,
    errors JSONB,
    suggestions JSONB,
    deep_analysis JSONB,
    report JSONB,
    report_url VARCHAR(512),
    status VARCHAR(20) DEFAULT 'pending',
    current_stage VARCHAR(64),
    percentage FLOAT DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_assistant_reports_submission ON assistant_analysis_reports(submission_id);
CREATE INDEX IF NOT EXISTS idx_assistant_reports_student ON assistant_analysis_reports(student_id);
CREATE INDEX IF NOT EXISTS idx_assistant_reports_subject ON assistant_analysis_reports(subject);
CREATE INDEX IF NOT EXISTS idx_assistant_reports_status ON assistant_analysis_reports(status);
CREATE INDEX IF NOT EXISTS idx_assistant_reports_created ON assistant_analysis_reports(created_at);

-- 创建错误记录表
CREATE TABLE IF NOT EXISTS assistant_error_records (
    error_id VARCHAR(64) PRIMARY KEY,
    analysis_id VARCHAR(64) NOT NULL,
    error_type VARCHAR(20) NOT NULL,
    description TEXT NOT NULL,
    severity VARCHAR(10) NOT NULL,
    location JSONB,
    affected_steps JSONB,
    correct_approach TEXT,
    context TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (analysis_id) REFERENCES assistant_analysis_reports(analysis_id) ON DELETE CASCADE
);

-- 创建错误记录索引
CREATE INDEX IF NOT EXISTS idx_assistant_errors_analysis ON assistant_error_records(analysis_id);
CREATE INDEX IF NOT EXISTS idx_assistant_errors_type ON assistant_error_records(error_type);
CREATE INDEX IF NOT EXISTS idx_assistant_errors_severity ON assistant_error_records(severity);

-- 创建建议记录表
CREATE TABLE IF NOT EXISTS assistant_suggestions (
    suggestion_id VARCHAR(64) PRIMARY KEY,
    analysis_id VARCHAR(64) NOT NULL,
    related_error_id VARCHAR(64),
    suggestion_type VARCHAR(20) NOT NULL,
    description TEXT NOT NULL,
    example TEXT,
    priority VARCHAR(10) NOT NULL,
    resources JSONB,
    expected_improvement TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (analysis_id) REFERENCES assistant_analysis_reports(analysis_id) ON DELETE CASCADE
);

-- 创建建议记录索引
CREATE INDEX IF NOT EXISTS idx_assistant_suggestions_analysis ON assistant_suggestions(analysis_id);
CREATE INDEX IF NOT EXISTS idx_assistant_suggestions_type ON assistant_suggestions(suggestion_type);
CREATE INDEX IF NOT EXISTS idx_assistant_suggestions_priority ON assistant_suggestions(priority);

-- 添加注释
COMMENT ON TABLE assistant_analysis_reports IS '辅助批改分析报告表';
COMMENT ON TABLE assistant_error_records IS '辅助批改错误记录表';
COMMENT ON TABLE assistant_suggestions IS '辅助批改建议记录表';
"""


# ==================== 数据库操作辅助函数 ====================


def create_tables(engine):
    """创建所有表
    
    Args:
        engine: SQLAlchemy 引擎
    """
    Base.metadata.create_all(engine)


def drop_tables(engine):
    """删除所有表（谨慎使用）
    
    Args:
        engine: SQLAlchemy 引擎
    """
    Base.metadata.drop_all(engine)


def init_database(engine):
    """初始化数据库（创建表和索引）
    
    Args:
        engine: SQLAlchemy 引擎
    """
    # 创建表
    create_tables(engine)
    
    # 执行迁移 SQL（创建额外索引和注释）
    with engine.connect() as conn:
        # 分割 SQL 语句并执行
        statements = [s.strip() for s in MIGRATION_SQL.split(';') if s.strip()]
        for statement in statements:
            if statement:
                try:
                    conn.execute(statement)
                except Exception as e:
                    print(f"Warning: Failed to execute statement: {e}")
        conn.commit()
