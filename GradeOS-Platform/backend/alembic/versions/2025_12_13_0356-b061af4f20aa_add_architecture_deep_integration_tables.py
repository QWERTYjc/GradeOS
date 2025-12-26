"""add_architecture_deep_integration_tables

Revision ID: b061af4f20aa
Revises: abea6430ff73
Create Date: 2025-12-13 03:56:01.695074+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b061af4f20aa'
down_revision: Union[str, None] = 'abea6430ff73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 15.1 创建追踪表迁移 (需求 5.4)
    op.create_table(
        'trace_spans',
        sa.Column('trace_id', sa.String(36), nullable=False),
        sa.Column('span_id', sa.String(36), nullable=False),
        sa.Column('parent_span_id', sa.String(36), nullable=True),
        sa.Column('kind', sa.String(50), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('start_time', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('end_time', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('duration_ms', sa.Integer, nullable=True),
        sa.Column('attributes', postgresql.JSONB, nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='ok'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('trace_id', 'span_id')
    )
    
    # 创建追踪表索引
    op.create_index('idx_trace_spans_trace', 'trace_spans', ['trace_id'])
    op.create_index('idx_trace_spans_time', 'trace_spans', ['start_time'])
    op.create_index(
        'idx_trace_spans_duration', 
        'trace_spans', 
        ['duration_ms'],
        postgresql_where=sa.text('duration_ms > 500')
    )
    
    # 15.2 创建 Saga 事务日志表迁移 (需求 4.5)
    op.create_table(
        'saga_transactions',
        sa.Column('saga_id', sa.String(36), primary_key=True),
        sa.Column('steps', postgresql.JSONB, nullable=False),
        sa.Column('final_status', sa.String(20), nullable=False),
        sa.Column('started_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('completed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'))
    )
    
    # 创建 Saga 事务日志表索引
    op.create_index('idx_saga_status', 'saga_transactions', ['final_status'])
    
    # 15.3 更新检查点表迁移 (需求 9.1, 9.3)
    op.add_column('langgraph_checkpoints', 
                  sa.Column('is_compressed', sa.Boolean, nullable=False, server_default='false'))
    op.add_column('langgraph_checkpoints', 
                  sa.Column('is_delta', sa.Boolean, nullable=False, server_default='false'))
    op.add_column('langgraph_checkpoints', 
                  sa.Column('base_checkpoint_id', sa.String(255), nullable=True))
    op.add_column('langgraph_checkpoints', 
                  sa.Column('data_size_bytes', sa.Integer, nullable=True))
    
    # 15.4 创建工作流状态缓存表迁移 (需求 3.5)
    op.create_table(
        'workflow_state_cache',
        sa.Column('workflow_id', sa.String(255), primary_key=True),
        sa.Column('state', postgresql.JSONB, nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'))
    )


def downgrade() -> None:
    # 按相反顺序删除
    op.drop_table('workflow_state_cache')
    
    # 删除检查点表的新增列
    op.drop_column('langgraph_checkpoints', 'data_size_bytes')
    op.drop_column('langgraph_checkpoints', 'base_checkpoint_id')
    op.drop_column('langgraph_checkpoints', 'is_delta')
    op.drop_column('langgraph_checkpoints', 'is_compressed')
    
    # 删除 Saga 事务日志表
    op.drop_table('saga_transactions')
    
    # 删除追踪表
    op.drop_table('trace_spans')
