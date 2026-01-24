"""initial_schema

Revision ID: abea6430ff73
Revises: 
Create Date: 2025-12-07 10:47:42.417019+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'abea6430ff73'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    # Create submissions table
    op.create_table(
        'submissions',
        sa.Column('submission_id', postgresql.UUID(as_uuid=True), primary_key=True, 
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('exam_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('student_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='UPLOADED'),
        sa.Column('total_score', sa.Numeric(5, 2), nullable=True),
        sa.Column('max_total_score', sa.Numeric(5, 2), nullable=True),
        sa.Column('file_paths', postgresql.JSONB, nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()')),
        sa.CheckConstraint(
            "status IN ('UPLOADED', 'SEGMENTING', 'GRADING', 'REVIEWING', 'COMPLETED', 'REJECTED')",
            name='valid_status'
        )
    )
    
    # Create indexes for submissions
    op.create_index('idx_submissions_exam', 'submissions', ['exam_id'])
    op.create_index('idx_submissions_student', 'submissions', ['student_id'])
    op.create_index('idx_submissions_status', 'submissions', ['status'])
    
    # Create grading_results table
    op.create_table(
        'grading_results',
        sa.Column('submission_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('question_id', sa.String(50), nullable=False),
        sa.Column('score', sa.Numeric(5, 2), nullable=True),
        sa.Column('max_score', sa.Numeric(5, 2), nullable=True),
        sa.Column('confidence_score', sa.Numeric(3, 2), nullable=True),
        sa.Column('visual_annotations', postgresql.JSONB, nullable=True),
        sa.Column('agent_trace', postgresql.JSONB, nullable=True),
        sa.Column('student_feedback', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('submission_id', 'question_id'),
        sa.ForeignKeyConstraint(['submission_id'], ['submissions.submission_id'])
    )
    
    # Create indexes for grading_results
    op.create_index('idx_grading_results_confidence', 'grading_results', ['confidence_score'])
    # Create GIN index for JSONB columns
    op.create_index('idx_grading_results_agent_trace', 'grading_results', ['agent_trace'], 
                    postgresql_using='gin')
    op.create_index('idx_grading_results_feedback', 'grading_results', ['student_feedback'], 
                    postgresql_using='gin')
    
    # Create rubrics table
    op.create_table(
        'rubrics',
        sa.Column('rubric_id', postgresql.UUID(as_uuid=True), primary_key=True, 
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('exam_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('question_id', sa.String(50), nullable=False),
        sa.Column('rubric_text', sa.Text, nullable=False),
        sa.Column('max_score', sa.Numeric(5, 2), nullable=False),
        sa.Column('scoring_points', postgresql.JSONB, nullable=False),
        sa.Column('standard_answer', sa.Text, nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()')),
        sa.UniqueConstraint('exam_id', 'question_id', name='uq_rubrics_exam_question')
    )
    
    # Create langgraph_checkpoints table
    op.create_table(
        'langgraph_checkpoints',
        sa.Column('thread_id', sa.String(255), nullable=False),
        sa.Column('checkpoint_id', sa.String(255), nullable=False),
        sa.Column('parent_checkpoint_id', sa.String(255), nullable=True),
        sa.Column('checkpoint_data', postgresql.JSONB, nullable=False),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('thread_id', 'checkpoint_id')
    )
    
    # Create index for langgraph_checkpoints
    op.create_index('idx_checkpoints_thread', 'langgraph_checkpoints', ['thread_id'])
    
    # Create human_reviews table
    op.create_table(
        'human_reviews',
        sa.Column('review_id', postgresql.UUID(as_uuid=True), primary_key=True, 
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('submission_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('question_id', sa.String(50), nullable=True),
        sa.Column('reviewer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('action', sa.String(20), nullable=False),
        sa.Column('override_score', sa.Numeric(5, 2), nullable=True),
        sa.Column('override_feedback', sa.Text, nullable=True),
        sa.Column('review_comment', sa.Text, nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['submission_id'], ['submissions.submission_id'])
    )
    
    # Create index for human_reviews
    op.create_index('idx_reviews_submission', 'human_reviews', ['submission_id'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('human_reviews')
    op.drop_table('langgraph_checkpoints')
    op.drop_table('rubrics')
    op.drop_table('grading_results')
    op.drop_table('submissions')
