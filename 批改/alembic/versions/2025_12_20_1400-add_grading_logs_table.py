"""add_grading_logs_table

Revision ID: add_grading_logs_001
Revises: add_calibration_001
Create Date: 2025-12-20 14:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'add_grading_logs_001'
down_revision: Union[str, None] = 'add_calibration_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    创建批改日志表
    
    用于记录每次批改的完整上下文，包括提取、规范化、匹配、评分各阶段的详细信息，
    以及老师改判记录，用于后续分析和规则升级。
    验证：需求 8.1
    """
    # 创建 grading_logs 表
    op.create_table(
        'grading_logs',
        sa.Column('log_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()'), comment='日志唯一标识'),
        sa.Column('submission_id', postgresql.UUID(as_uuid=True), nullable=False, comment='提交ID'),
        sa.Column('question_id', sa.String(50), nullable=False, comment='题目ID'),
        
        # 提取阶段
        sa.Column('extracted_answer', sa.Text, nullable=True, comment='提取的答案文本'),
        sa.Column('extraction_confidence', sa.Numeric(3, 2), nullable=True, comment='提取置信度（0.00-1.00）'),
        sa.Column('evidence_snippets', postgresql.JSONB, nullable=True, comment='证据片段列表'),
        
        # 规范化阶段
        sa.Column('normalized_answer', sa.Text, nullable=True, comment='规范化后的答案'),
        sa.Column('normalization_rules_applied', postgresql.JSONB, nullable=True, comment='应用的规范化规则列表'),
        
        # 匹配阶段
        sa.Column('match_result', sa.Boolean, nullable=True, comment='匹配结果（True/False）'),
        sa.Column('match_failure_reason', sa.Text, nullable=True, comment='匹配失败原因'),
        
        # 评分阶段
        sa.Column('score', sa.Numeric(5, 2), nullable=True, comment='评分结果'),
        sa.Column('max_score', sa.Numeric(5, 2), nullable=True, comment='满分值'),
        sa.Column('confidence', sa.Numeric(3, 2), nullable=True, comment='评分置信度（0.00-1.00）'),
        sa.Column('reasoning_trace', postgresql.JSONB, nullable=True, comment='推理过程追踪'),
        
        # 改判信息
        sa.Column('was_overridden', sa.Boolean, nullable=False, server_default=sa.text('FALSE'), comment='是否被改判'),
        sa.Column('override_score', sa.Numeric(5, 2), nullable=True, comment='改判后的分数'),
        sa.Column('override_reason', sa.Text, nullable=True, comment='改判原因'),
        sa.Column('override_teacher_id', postgresql.UUID(as_uuid=True), nullable=True, comment='改判教师ID'),
        sa.Column('override_at', sa.TIMESTAMP(timezone=True), nullable=True, comment='改判时间'),
        
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), comment='创建时间')
    )
    
    # 创建索引
    op.create_index('idx_grading_logs_submission', 'grading_logs', ['submission_id'])
    op.create_index('idx_grading_logs_override', 'grading_logs', ['was_overridden'], postgresql_where=sa.text('was_overridden = TRUE'))
    op.create_index('idx_grading_logs_created', 'grading_logs', ['created_at'])
    op.create_index('idx_grading_logs_question', 'grading_logs', ['question_id'])
    
    # 添加约束：置信度必须在 0.0-1.0 之间
    op.execute("""
        ALTER TABLE grading_logs
        ADD CONSTRAINT check_extraction_confidence_range
        CHECK (extraction_confidence IS NULL OR (extraction_confidence >= 0.0 AND extraction_confidence <= 1.0))
    """)
    
    op.execute("""
        ALTER TABLE grading_logs
        ADD CONSTRAINT check_confidence_range
        CHECK (confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0))
    """)
    
    # 添加约束：如果被改判，必须有改判信息
    op.execute("""
        ALTER TABLE grading_logs
        ADD CONSTRAINT check_override_completeness
        CHECK (
            (was_overridden = FALSE) OR
            (was_overridden = TRUE AND override_score IS NOT NULL AND override_reason IS NOT NULL AND override_teacher_id IS NOT NULL AND override_at IS NOT NULL)
        )
    """)


def downgrade() -> None:
    """删除批改日志表"""
    op.drop_table('grading_logs')
