"""add_calibration_profiles_table

Revision ID: add_calibration_001
Revises: add_exemplars_001
Create Date: 2025-12-20 12:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'add_calibration_001'
down_revision: Union[str, None] = 'add_exemplars_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    创建校准配置表
    
    用于存储教师/学校的个性化评分配置，包括扣分规则、容差设置和措辞模板。
    验证：需求 6.1
    """
    # 创建 calibration_profiles 表
    op.create_table(
        'calibration_profiles',
        sa.Column('profile_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()'), comment='配置唯一标识'),
        sa.Column('teacher_id', postgresql.UUID(as_uuid=True), nullable=False, unique=True, comment='教师ID'),
        sa.Column('school_id', postgresql.UUID(as_uuid=True), nullable=True, comment='学校ID（可选）'),
        sa.Column('deduction_rules', postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"), comment='扣分规则（错误类型 -> 扣分值）'),
        sa.Column('tolerance_rules', postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"), comment='容差规则列表'),
        sa.Column('feedback_templates', postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"), comment='评语模板（场景 -> 模板）'),
        sa.Column('strictness_level', sa.Numeric(3, 2), nullable=False, server_default=sa.text('0.5'), comment='严格程度（0.0-1.0）'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), comment='创建时间'),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), comment='更新时间')
    )
    
    # 创建索引
    op.create_index('idx_calibration_teacher', 'calibration_profiles', ['teacher_id'])
    op.create_index('idx_calibration_school', 'calibration_profiles', ['school_id'])
    op.create_index('idx_calibration_created', 'calibration_profiles', ['created_at'])
    
    # 创建更新时间触发器
    op.execute("""
        CREATE OR REPLACE FUNCTION update_calibration_profiles_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    op.execute("""
        CREATE TRIGGER trigger_calibration_profiles_updated_at
        BEFORE UPDATE ON calibration_profiles
        FOR EACH ROW
        EXECUTE FUNCTION update_calibration_profiles_updated_at();
    """)
    
    # 添加约束：strictness_level 必须在 0.0-1.0 之间
    op.execute("""
        ALTER TABLE calibration_profiles
        ADD CONSTRAINT check_strictness_level_range
        CHECK (strictness_level >= 0.0 AND strictness_level <= 1.0)
    """)


def downgrade() -> None:
    """删除校准配置表"""
    op.execute('DROP TRIGGER IF EXISTS trigger_calibration_profiles_updated_at ON calibration_profiles')
    op.execute('DROP FUNCTION IF EXISTS update_calibration_profiles_updated_at()')
    op.drop_table('calibration_profiles')

