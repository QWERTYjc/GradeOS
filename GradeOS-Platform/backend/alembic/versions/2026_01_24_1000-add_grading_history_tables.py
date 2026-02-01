"""add_grading_history_tables

将 SQLite 的 grading_history 和 student_grading_results 表迁移到 PostgreSQL，
确保批改历史在 Railway 部署后持久化。

Revision ID: add_grading_history_tables
Revises: 2025_12_24_1200-add_runs_table_for_langgraph
Create Date: 2026-01-24 10:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'add_grading_history_tables'
down_revision: Union[str, None] = 'add_runs_table_for_langgraph'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 检查表是否已存在的辅助函数
    conn = op.get_bind()
    
    # 批改历史表 - 存储每次批改任务的元数据
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'grading_history')"
    ))
    grading_history_exists = result.scalar()
    
    if not grading_history_exists:
        op.create_table(
            'grading_history',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                      server_default=sa.text('gen_random_uuid()')),
            sa.Column('batch_id', sa.String(255), unique=True, nullable=False),
            sa.Column('class_ids', postgresql.JSONB, nullable=True),  # JSON array of class IDs
            sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()')),
            sa.Column('completed_at', sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
            sa.Column('total_students', sa.Integer, server_default='0'),
            sa.Column('average_score', sa.Numeric(5, 2), nullable=True),
            sa.Column('result_data', postgresql.JSONB, nullable=True),  # 存储 class_report 等
        )
        
        op.create_index('idx_grading_history_batch_id', 'grading_history', ['batch_id'])
        op.create_index('idx_grading_history_status', 'grading_history', ['status'])
        op.create_index('idx_grading_history_created_at', 'grading_history', ['created_at'])
    
    # 学生批改结果表 - 存储每个学生的详细批改结果
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'student_grading_results')"
    ))
    student_results_exists = result.scalar()
    
    if not student_results_exists:
        op.create_table(
            'student_grading_results',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                      server_default=sa.text('gen_random_uuid()')),
            sa.Column('grading_history_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('student_key', sa.String(255), nullable=False),  # 学生标识（姓名或ID）
            sa.Column('class_id', sa.String(255), nullable=True),
            sa.Column('student_id', sa.String(255), nullable=True),
            sa.Column('score', sa.Numeric(5, 2), nullable=True),
            sa.Column('max_score', sa.Numeric(5, 2), nullable=True),
            sa.Column('summary', sa.Text, nullable=True),
            sa.Column('confession', sa.Text, nullable=True),
            sa.Column('result_data', postgresql.JSONB, nullable=True),  # 完整的批改结果 JSON
            sa.Column('imported_at', sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column('revoked_at', sa.TIMESTAMP(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['grading_history_id'], ['grading_history.id'], ondelete='CASCADE'),
        )
        
        op.create_index('idx_student_results_history', 'student_grading_results', ['grading_history_id'])
        op.create_index('idx_student_results_class', 'student_grading_results', ['class_id'])
        op.create_index('idx_student_results_student', 'student_grading_results', ['student_id'])


def downgrade() -> None:
    op.drop_table('student_grading_results')
    op.drop_table('grading_history')
