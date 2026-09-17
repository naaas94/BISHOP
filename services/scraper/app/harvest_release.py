"""GitHub harvest release tap — ledger rows into DISCOVERED, budget-capped."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import httpx
import sqlite3

from app.config import BISHOP_HARVEST_ENABLED, BISHOP_HARVEST_RELEASE_BATCH
from app.models import ManifestIngestEntry
from app.state_worker_client import StateWorkerClient
from bishop_shared.enums import DomainEnum, SourceEnum
from bishop_shared.harvest_economics import load_harvest_economics, remaining_slots
from bishop_shared.harvest_ledger import (
    connect_rw,
    count_released_today,
    harvest_db_path,
    mark_released,
    select_release_batch,
)

logger = logging.getLogger(__name__)

_QUEUE_STATES = ["DISCOVERED", "RELEVANCE_QUEUED"]
_FRESHNESS_HOURS = 48


async def release_once(
    client: StateWorkerClient,
    *,
    db_path: Path | None = None,
) -> None:
    """Select a budget-capped ledger batch and POST it as DISCOVERED."""
    if not BISHOP_HARVEST_ENABLED:
        return

    econ = load_harvest_economics()
    n_cap = econ.n_cap
    if n_cap == 0:
        logger.info("harvest tap closed", extra={"event": "harvest_tap_closed"})
        return

    github_in_queue = await client.count_manifest(
        source=SourceEnum.GITHUB.value,
        states=list(_QUEUE_STATES),
    )
    path = db_path if db_path is not None else harvest_db_path()
    now = datetime.now(UTC)
    conn = connect_rw(path)
    try:
        released_today = count_released_today(conn, now=now)
        remaining = remaining_slots(
            n_cap=n_cap,
            released_today=released_today,
            github_in_queue=github_in_queue,
        )
        limit = min(BISHOP_HARVEST_RELEASE_BATCH, remaining)
        if limit <= 0:
            return
        rows = select_release_batch(
            conn,
            now=now,
            limit=limit,
            freshness_hours=_FRESHNESS_HOURS,
        )
        if len(rows) > BISHOP_HARVEST_RELEASE_BATCH:
            rows = rows[:BISHOP_HARVEST_RELEASE_BATCH]
        if not rows:
            return
        entries = [_row_to_entry(row) for row in rows]
        source_ids = [entry.source_id for entry in entries]
        try:
            result = await client.post_manifest_batch(entries)
        except httpx.HTTPError:
            logger.exception(
                "harvest release post failed",
                extra={
                    "event": "harvest_release_http_failed",
                    "n_selected": len(entries),
                },
            )
            return
        mark_released(conn, source_ids, now=now)
        n_created = result.inserted
        n_skipped = result.skipped
        n_remaining = remaining_slots(
            n_cap=n_cap,
            released_today=count_released_today(conn, now=now),
            github_in_queue=github_in_queue + n_created,
        )
        logger.info(
            "harvest release tick",
            extra={
                "event": "harvest_release",
                "n_cap": n_cap,
                "released_today": released_today,
                "github_in_queue": github_in_queue,
                "n_selected": len(entries),
                "n_created": n_created,
                "n_skipped": n_skipped,
                "n_remaining": n_remaining,
                "budget_usd": econ.daily_budget_usd,
            },
        )
    finally:
        conn.close()


def _row_to_entry(row: sqlite3.Row) -> ManifestIngestEntry:
    return ManifestIngestEntry(
        source_id=row["source_id"],
        source=SourceEnum.GITHUB,
        url=row["url"],
        title=row["title"],
        abstract=row["abstract"],
        published_at=_parse_pushed_at(row["pushed_at"]),
        domain=DomainEnum.PROFESSIONAL,
    )


def _parse_pushed_at(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
