"""add runs table for langgraph

Revision ID: add_runs_table_for_langgraph
Revises: add_rule_patches_table
Create Date: 2025-12-24 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'add_runs_table_for_langgraph'
down_revision: Union[str, None] = 'add_rule_patches_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 runs 表用于 LangGraph Orchestrator"""
    
    # 创建 runs 表
    op.create_table(
        'runs',
        sa.Column('run_id', sa.Text(), nullable=False),
        sa.Column('graph_name', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('input_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('output_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('run_id')
    )
    
    # 创建索引
    op.create_index('idx_runs_graph_name', 'runs', ['graph_name'])
    op.create_index('idx_runs_status', 'runs', ['status'])
    op.create_index('idx_runs_created_at', 'runs', ['created_at'])
    
    # 创建 attempts 表（用于记录重试历史）
    op.create_table(
        'attempts',
        sa.Column('attempt_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('run_id', sa.Text(), nullable=False),
        sa.Column('attempt_number', sa.Integer(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('attempt_id'),
        sa.ForeignKeyConstraint(['run_id'], ['runs.run_id'], ondelete='CASCADE')
    )
    
    # 创建索引
    op.create_index('idx_attempts_run_id', 'attempts', ['run_id'])


def downgrade() -> None:
    """删除 runs 和 attempts 表"""
    op.drop_index('idx_attempts_run_id', table_name='attempts')
    op.drop_table('attempts')
    
    op.drop_index('idx_runs_created_at', table_name='runs')
    op.drop_index('idx_runs_status', table_name='runs')
    op.drop_index('idx_runs_graph_name', table_name='runs')
    op.drop_table('runs')
