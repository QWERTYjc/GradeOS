"""add_stream_events_table

Revision ID: 3b23880c1112
Revises: b061af4f20aa
Create Date: 2025-12-19 18:32:54.682195+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '3b23880c1112'
down_revision: Union[str, None] = 'b061af4f20aa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    创建流式事件表
    
    用于支持断点续传功能，存储流式推送的事件。
    验证：需求 1.4
    """
    # 创建 stream_events 表
    op.create_table(
        'stream_events',
        sa.Column('event_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('stream_id', sa.String(100), nullable=False),
        sa.Column('sequence_number', sa.Integer, nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('event_data', postgresql.JSONB, nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()')),
        sa.UniqueConstraint('stream_id', 'sequence_number', name='uq_stream_sequence')
    )
    
    # 创建索引
    op.create_index('idx_stream_events_stream', 'stream_events', ['stream_id', 'sequence_number'])
    op.create_index('idx_stream_events_created', 'stream_events', ['created_at'])


def downgrade() -> None:
    """删除流式事件表"""
    op.drop_table('stream_events')
