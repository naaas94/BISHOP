"""Index the columns claim polls filter and sort on.

Revision ID: m8_002_claim_poll_indexes
Revises: m8_001_pre_filter_tier
Create Date: 2026-09-27

claim_manifest_poll and claim_entries_poll take the WAL write lock and then
SELECT * WHERE processing_state = ? ORDER BY discovered_at/ingested_at. Without
these indexes that is a full scan, and on the Docker bind mount an empty scan
held the writer for longer than the 5s busy timeout.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "m8_002_claim_poll_indexes"
down_revision: Union[str, None] = "m8_001_pre_filter_tier"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_manifest_state_discovered",
        "manifest",
        ["processing_state", "discovered_at"],
    )
    op.create_index(
        "ix_entries_state_ingested",
        "entries",
        ["processing_state", "ingested_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_entries_state_ingested", table_name="entries")
    op.drop_index("ix_manifest_state_discovered", table_name="manifest")
