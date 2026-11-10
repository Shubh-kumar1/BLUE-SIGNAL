"""Add a durable PostgreSQL queue for report analysis.

Revision ID: 0003_durable_ai_jobs
Revises: 0002_image_classification
Create Date: 2026-11-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_durable_ai_jobs"
down_revision: Union[str, None] = "0002_image_classification"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column("image_filename", sa.String(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="queued", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("report_id"),
    )
    op.create_index(
        "ix_ai_jobs_status_created_at",
        "ai_jobs",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_jobs_status_created_at", table_name="ai_jobs")
    op.drop_table("ai_jobs")
