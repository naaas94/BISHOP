"""Add source_ids JSON column to batches for timeout/restart recovery.

Revision ID: m3_001_batch_source_ids
Revises: m1_001_initial_schema
Create Date: 2026-06-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "m3_001_batch_source_ids"
down_revision: Union[str, None] = "m1_001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "batches",
        sa.Column("source_ids", sa.Text(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("batches", "source_ids")
