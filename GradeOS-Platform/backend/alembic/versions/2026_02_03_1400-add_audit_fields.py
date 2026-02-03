"""add_audit_fields

Revision ID: add_audit_fields
Revises: add_confession_and_page_images
Create Date: 2026-02-03 14:00:00.000000+00:00

说明：批改和审计一体化改造
- 移除 confession 节点
- 在批改结果中添加 audit 字段
- 添加批次级别的审计统计字段
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "add_audit_fields"
down_revision: Union[str, None] = "add_confession_and_page_images"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    添加 audit 相关字段
    
    改造说明：
    - 批改和审计一体化：批改时直接生成 audit 信息
    - audit 字段存储为 JSONB，包含：
      * confidence: 置信度 (0-1)
      * uncertainties: 不确定点列表
      * risk_flags: 风险标签列表
      * needs_review: 是否需要人工复核
    """
    
    # 1. 在 student_grading_results 表添加题目级别的 audit 字段
    # 注意：question_details 是 JSONB 字段，audit 信息嵌套在其中，不需要单独列
    # 只需要添加批次级别的汇总字段
    
    # 2. 添加批次级别的审计汇总字段
    op.execute(
        """
        ALTER TABLE grading_history
        ADD COLUMN IF NOT EXISTS questions_need_review INTEGER DEFAULT 0,
        ADD COLUMN IF NOT EXISTS avg_confidence DECIMAL(3, 2) DEFAULT 1.0,
        ADD COLUMN IF NOT EXISTS high_risk_count INTEGER DEFAULT 0;
        """
    )
    
    # 3. 创建索引以优化按 needs_review 查询
    # 注意：PostgreSQL 支持 JSONB 索引
    op.execute(
        """
        DO $$
        BEGIN
            -- 为 student_grading_results 表的 question_details 中的 audit.needs_review 创建 GIN 索引
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes 
                WHERE tablename = 'student_grading_results' 
                AND indexname = 'idx_question_details_needs_review'
            ) THEN
                CREATE INDEX idx_question_details_needs_review 
                ON student_grading_results 
                USING GIN ((question_details -> 'audit' -> 'needs_review'));
            END IF;
        END $$;
        """
    )
    
    # 4. 为批次汇总字段创建索引
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_grading_history_needs_review "
        "ON grading_history(questions_need_review) WHERE questions_need_review > 0;"
    )
    
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_grading_history_avg_confidence "
        "ON grading_history(avg_confidence) WHERE avg_confidence < 0.7;"
    )


def downgrade() -> None:
    """回滚迁移"""
    
    # 删除索引
    op.execute("DROP INDEX IF EXISTS idx_grading_history_avg_confidence")
    op.execute("DROP INDEX IF EXISTS idx_grading_history_needs_review")
    op.execute("DROP INDEX IF EXISTS idx_question_details_needs_review")
    
    # 删除批次汇总字段
    op.execute(
        """
        ALTER TABLE grading_history
        DROP COLUMN IF EXISTS questions_need_review,
        DROP COLUMN IF EXISTS avg_confidence,
        DROP COLUMN IF EXISTS high_risk_count;
        """
    )
