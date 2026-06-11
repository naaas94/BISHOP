"""Initial M1 schema — six tables per spec §7.

Revision ID: m1_001_initial_schema
Revises:
Create Date: 2026-06-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "m1_001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "manifest",
        sa.Column("source_id", sa.Text(), primary_key=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("abstract", sa.Text(), nullable=True),
        sa.Column("published_at", sa.Text(), nullable=True),
        sa.Column("discovered_at", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("profile_version", sa.Text(), nullable=True),
        sa.Column("pre_filter_batch_id", sa.Text(), nullable=True),
        sa.Column("relevance_decision", sa.Integer(), nullable=True),
        sa.Column("pre_filter_rationale", sa.Text(), nullable=True),
        sa.Column("processing_state", sa.Text(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_retry_at", sa.Text(), nullable=True),
    )

    op.create_table(
        "entries",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content_raw", sa.Text(), nullable=False),
        sa.Column("published_at", sa.Text(), nullable=True),
        sa.Column("ingested_at", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("profile_version", sa.Text(), nullable=False),
        sa.Column("pre_filter_batch_id", sa.Text(), nullable=False),
        sa.Column("pre_filter_rationale", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("concepts", sa.Text(), nullable=True),
        sa.Column("tags", sa.Text(), nullable=True),
        sa.Column("entry_type", sa.Text(), nullable=True),
        sa.Column("challenge_hooks", sa.Text(), nullable=True),
        sa.Column("enrichment_stage1_batch_id", sa.Text(), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("relevance_reason", sa.Text(), nullable=True),
        sa.Column("value_rationale", sa.Text(), nullable=True),
        sa.Column("enrichment_stage2_batch_id", sa.Text(), nullable=True),
        sa.Column("references", sa.Text(), nullable=True),
        sa.Column("cited_by", sa.Text(), nullable=True),
        sa.Column("reading_status", sa.Text(), nullable=False, server_default="unread"),
        sa.Column("flagged_for_review", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processing_state", sa.Text(), nullable=False),
    )
    op.create_index("ix_entries_source_id", "entries", ["source_id"], unique=True)

    op.create_table(
        "batches",
        sa.Column("batch_id", sa.Text(), primary_key=True),
        sa.Column("batch_type", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("profile_version", sa.Text(), nullable=False),
        sa.Column("profile_render_hash", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("submitted_at", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.Text(), nullable=True),
        sa.Column("entry_count", sa.Integer(), nullable=False),
        sa.Column("passed_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("top_entries", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("external_batch_id", sa.Text(), nullable=True),
    )

    op.create_table(
        "error_log",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("state_at_failure", sa.Text(), nullable=False),
        sa.Column("error_class", sa.Text(), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_retriable", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.Text(), nullable=False),
        sa.Column("next_retry_at", sa.Text(), nullable=True),
    )
    op.create_index("ix_error_log_source_id", "error_log", ["source_id"])

    op.create_table(
        "oov_tags_log",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("tag_value", sa.Text(), nullable=False),
        sa.Column("entry_type", sa.Text(), nullable=False),
        sa.Column("enrichment_batch_id", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.Text(), nullable=False),
        sa.Column("review_status", sa.Text(), nullable=False),
    )

    op.create_table(
        "scraper_state",
        sa.Column("source", sa.Text(), primary_key=True),
        sa.Column("last_successful_run_at", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("scraper_state")
    op.drop_table("oov_tags_log")
    op.drop_index("ix_error_log_source_id", table_name="error_log")
    op.drop_table("error_log")
    op.drop_table("batches")
    op.drop_index("ix_entries_source_id", table_name="entries")
    op.drop_table("entries")
    op.drop_table("manifest")
