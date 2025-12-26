"""add_exemplars_table

Revision ID: add_exemplars_001
Revises: 3b23880c1112
Create Date: 2025-12-20 08:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'add_exemplars_001'
down_revision: Union[str, None] = '3b23880c1112'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    创建判例记忆库表
    
    用于存储老师确认的正确批改示例，支持向量检索。
    验证：需求 4.1
    """
    # 启用 pgvector 扩展
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    
    # 创建 exemplars 表
    op.create_table(
        'exemplars',
        sa.Column('exemplar_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('question_type', sa.String(50), nullable=False, comment='题目类型（objective/stepwise/essay）'),
        sa.Column('question_image_hash', sa.String(64), nullable=False, comment='题目图片哈希值'),
        sa.Column('student_answer_text', sa.Text, nullable=False, comment='学生答案文本'),
        sa.Column('score', sa.Numeric(5, 2), nullable=False, comment='得分'),
        sa.Column('max_score', sa.Numeric(5, 2), nullable=False, comment='满分'),
        sa.Column('teacher_feedback', sa.Text, nullable=False, comment='教师评语'),
        sa.Column('teacher_id', postgresql.UUID(as_uuid=True), nullable=False, comment='确认教师ID'),
        sa.Column('confirmed_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()'), comment='确认时间'),
        sa.Column('usage_count', sa.Integer, nullable=False, server_default=sa.text('0'), comment='使用次数'),
        sa.Column('embedding', sa.Text, nullable=True, comment='向量嵌入（pgvector格式）'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'))
    )
    
    # 创建常规索引
    op.create_index('idx_exemplars_type', 'exemplars', ['question_type'])
    op.create_index('idx_exemplars_teacher', 'exemplars', ['teacher_id'])
    op.create_index('idx_exemplars_hash', 'exemplars', ['question_image_hash'])
    op.create_index('idx_exemplars_confirmed', 'exemplars', ['confirmed_at'])
    op.create_index('idx_exemplars_usage', 'exemplars', ['usage_count'])
    
    # 创建向量索引（使用 IVFFlat 算法，适合大规模向量检索）
    # 注意：向量索引需要在有数据后创建，这里先创建表结构
    # 实际使用时需要先插入一些数据，然后执行：
    # CREATE INDEX idx_exemplars_embedding ON exemplars USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
    
    # 创建更新时间触发器
    op.execute("""
        CREATE OR REPLACE FUNCTION update_exemplars_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    op.execute("""
        CREATE TRIGGER trigger_exemplars_updated_at
        BEFORE UPDATE ON exemplars
        FOR EACH ROW
        EXECUTE FUNCTION update_exemplars_updated_at();
    """)


def downgrade() -> None:
    """删除判例记忆库表"""
    op.execute('DROP TRIGGER IF EXISTS trigger_exemplars_updated_at ON exemplars')
    op.execute('DROP FUNCTION IF EXISTS update_exemplars_updated_at()')
    op.drop_table('exemplars')
    # 注意：不删除 pgvector 扩展，因为可能被其他表使用
