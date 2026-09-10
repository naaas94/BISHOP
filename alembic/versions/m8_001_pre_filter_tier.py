"""Add nullable pre_filter_tier to manifest and entries for gate-1 core/peripheral.

Revision ID: m8_001_pre_filter_tier
Revises: m3_001_batch_source_ids
Create Date: 2026-09-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "m8_001_pre_filter_tier"
down_revision: Union[str, None] = "m3_001_batch_source_ids"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("manifest", sa.Column("pre_filter_tier", sa.Text(), nullable=True))
    op.add_column("entries", sa.Column("pre_filter_tier", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("entries", "pre_filter_tier")
    op.drop_column("manifest", "pre_filter_tier")
