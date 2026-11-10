"""Persist CLIP image-classification results.

Revision ID: 0002_image_classification
Revises: 0001_initial_schema
Create Date: 2026-11-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_image_classification"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "reports",
        sa.Column("image_classification", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("reports", "image_classification")
