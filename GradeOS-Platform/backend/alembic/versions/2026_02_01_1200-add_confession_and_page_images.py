"""add_confession_and_page_images

Revision ID: add_confession_and_page_images
Revises: add_grading_history_tables
Create Date: 2026-02-01 12:00:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "add_confession_and_page_images"
down_revision: Union[str, None] = "add_grading_history_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ensure student_grading_results uses confession column
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'student_grading_results' AND column_name = 'self_report'
          ) AND NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'student_grading_results' AND column_name = 'confession'
          ) THEN
            ALTER TABLE student_grading_results RENAME COLUMN self_report TO confession;
          END IF;
        END $$;
        """
    )
    op.execute("ALTER TABLE student_grading_results ADD COLUMN IF NOT EXISTS confession TEXT;")
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'student_grading_results' AND column_name = 'self_report'
          ) AND EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'student_grading_results' AND column_name = 'confession'
          ) THEN
            UPDATE student_grading_results
              SET confession = COALESCE(confession, self_report)
              WHERE self_report IS NOT NULL;
            ALTER TABLE student_grading_results DROP COLUMN self_report;
          END IF;
        END $$;
        """
    )

    # Create grading_page_images table for page image indexes (idempotent)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS grading_page_images (
            id UUID PRIMARY KEY,
            grading_history_id UUID NOT NULL,
            student_key VARCHAR(200) NOT NULL,
            page_index INTEGER NOT NULL,
            file_id VARCHAR(200),
            file_url TEXT,
            content_type VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (grading_history_id) REFERENCES grading_history(id) ON DELETE CASCADE,
            CONSTRAINT unique_page_image UNIQUE (grading_history_id, student_key, page_index)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_page_images_history ON grading_page_images(grading_history_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_page_images_student ON grading_page_images(grading_history_id, student_key)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_page_images_file_id ON grading_page_images(file_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_page_images_file_id")
    op.execute("DROP INDEX IF EXISTS idx_page_images_student")
    op.execute("DROP INDEX IF EXISTS idx_page_images_history")
    op.execute("DROP TABLE IF EXISTS grading_page_images")

    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'student_grading_results' AND column_name = 'confession'
          ) AND NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'student_grading_results' AND column_name = 'self_report'
          ) THEN
            ALTER TABLE student_grading_results RENAME COLUMN confession TO self_report;
          END IF;
        END $$;
        """
    )
