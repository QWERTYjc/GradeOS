"""add rule_patches table

Revision ID: add_rule_patches_table
Revises: add_grading_logs_table
Create Date: 2025-12-20 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'add_rule_patches_table'
down_revision: Union[str, None] = 'add_grading_logs_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 rule_patches 表
    
    用于存储规则补丁的版本、内容、部署状态等信息。
    验证：需求 10.1, 10.2
    """
    # 创建 rule_patches 表
    op.create_table(
        'rule_patches',
        sa.Column('patch_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('patch_type', sa.String(20), nullable=False, comment='补丁类型：rule/prompt/exemplar'),
        sa.Column('version', sa.String(20), nullable=False, unique=True, comment='版本号'),
        sa.Column('description', sa.Text, nullable=False, comment='补丁描述'),
        sa.Column('content', postgresql.JSONB, nullable=False, comment='补丁内容（具体格式取决于补丁类型）'),
        sa.Column('source_pattern_id', sa.String(100), nullable=True, comment='来源失败模式ID'),
        sa.Column('status', sa.String(20), nullable=False, server_default='candidate', comment='补丁状态：candidate/testing/deployed/rolled_back'),
        sa.Column('dependencies', postgresql.JSONB, nullable=False, server_default='[]', comment='依赖的其他补丁版本'),
        
        # 部署信息
        sa.Column('deployed_at', sa.TIMESTAMP(timezone=True), nullable=True, comment='部署时间'),
        sa.Column('deployment_scope', sa.String(20), nullable=True, comment='部署范围：canary/full'),
        sa.Column('rolled_back_at', sa.TIMESTAMP(timezone=True), nullable=True, comment='回滚时间'),
        
        # 测试结果
        sa.Column('regression_result', postgresql.JSONB, nullable=True, comment='回归测试结果'),
        
        # 时间戳
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        
        comment='规则补丁表：存储从失败模式生成的规则补丁'
    )
    
    # 创建索引
    op.create_index('idx_patches_status', 'rule_patches', ['status'], comment='按状态查询补丁')
    op.create_index('idx_patches_version', 'rule_patches', ['version'], unique=True, comment='按版本号查询补丁')
    op.create_index('idx_patches_created', 'rule_patches', ['created_at'], comment='按创建时间查询补丁')
    op.create_index('idx_patches_deployed', 'rule_patches', ['deployed_at'], comment='按部署时间查询补丁')


def downgrade() -> None:
    """删除 rule_patches 表"""
    op.drop_index('idx_patches_deployed', table_name='rule_patches')
    op.drop_index('idx_patches_created', table_name='rule_patches')
    op.drop_index('idx_patches_version', table_name='rule_patches')
    op.drop_index('idx_patches_status', table_name='rule_patches')
    op.drop_table('rule_patches')
