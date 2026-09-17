"""Read-only SQLite aggregate stats for query-api."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TypedDict

from bishop_shared.constants import SQLITE_DB_PATH
from bishop_shared.harvest_economics import load_harvest_economics
from bishop_shared.harvest_ledger import connect_ro, harvest_db_path, read_pool_stats

from app.models import DailyCount, StatBucket, StatsOverview

FUNNEL_DEFINITIONS: list[tuple[str, tuple[str, ...]]] = [
    ("Discovered", ("DISCOVERED",)),
    ("Relevance queued", ("RELEVANCE_QUEUED",)),
    ("Relevance passed", ("RELEVANCE_PASSED",)),
    ("Relevance rejected", ("RELEVANCE_REJECTED",)),
    ("Relevance parked", ("RELEVANCE_PARKED",)),
    ("Scrape", ("SCRAPE_QUEUED", "SCRAPED")),
    (
        "Enrichment stage 1",
        (
            "ENRICHMENT_STAGE1_QUEUED",
            "ENRICHMENT_STAGE1_SUBMITTED",
            "ENRICHMENT_STAGE1_COMPLETE",
        ),
    ),
    (
        "Enrichment stage 2",
        (
            "ENRICHMENT_STAGE2_QUEUED",
            "ENRICHMENT_STAGE2_CLAIMED",
            "ENRICHMENT_STAGE2_SUBMITTED",
            "ENRICHMENT_STAGE2_COMPLETE",
        ),
    ),
    ("Vector write queued", ("VECTOR_WRITE_QUEUED",)),
    ("Indexed", ("INDEXED",)),
    (
        "Failed",
        (
            "SCRAPE_FAILED",
            "ENRICHMENT_STAGE1_FAILED",
            "ENRICHMENT_STAGE2_FAILED",
            "VECTOR_WRITE_FAILED",
        ),
    ),
    ("Escalated", ("ESCALATION_FLAGGED",)),
    ("Permanently failed", ("PERMANENTLY_FAILED",)),
]

_QUEUE_SUFFIXES = ("_QUEUED", "_SUBMITTED", "_CLAIMED")


class _HarvestFields(TypedDict):
    harvest_pool_size: int
    harvest_unreleased: int
    harvest_released_today: int
    harvest_n_cap: int
    harvest_budget_usd: float
    harvest_projected_usd_today: float
    harvest_sidecar_present: bool


def _relevance_histogram_labels() -> list[str]:
    return [f"{i / 10:.1f}\u2013{(i + 1) / 10:.1f}" for i in range(10)]


def _build_funnel(manifest_state_counts: dict[str, int]) -> list[StatBucket]:
    return [
        StatBucket(
            label=label,
            count=sum(manifest_state_counts.get(state, 0) for state in states),
        )
        for label, states in FUNNEL_DEFINITIONS
    ]


def _build_queue_depth(manifest_state_counts: dict[str, int]) -> list[StatBucket]:
    buckets: list[StatBucket] = []
    for state, count in manifest_state_counts.items():
        if count <= 0:
            continue
        if any(state.endswith(suffix) for suffix in _QUEUE_SUFFIXES):
            buckets.append(StatBucket(label=state, count=count))
    buckets.sort(key=lambda b: b.count, reverse=True)
    return buckets


def _zero_fill_ingest(
    counts_by_date: dict[str, int],
    *,
    now: datetime,
) -> list[DailyCount]:
    cutoff_date = (now - timedelta(days=30)).date()
    today = now.date()
    result: list[DailyCount] = []
    day = cutoff_date
    while day <= today:
        key = day.isoformat()
        result.append(DailyCount(date=key, count=counts_by_date.get(key, 0)))
        day += timedelta(days=1)
    return result


def _zeroed_histogram() -> list[StatBucket]:
    return [
        StatBucket(label=label, count=0) for label in _relevance_histogram_labels()
    ]


def _empty_stats_overview(*, generated_at: datetime) -> StatsOverview:
    return StatsOverview(
        generated_at=generated_at,
        manifest_total=0,
        entries_total=0,
        indexed_total=0,
        pre_filter_decided=0,
        pre_filter_passed=0,
        funnel=_build_funnel({}),
        queue_depth=[],
        relevance_histogram=_zeroed_histogram(),
        by_domain=[],
        by_source=[],
        by_entry_type=[],
        top_tags=[],
        reading_status=[],
        ingest_by_day=_zero_fill_ingest({}, now=generated_at),
        batches_total=0,
        batches_by_status=[],
        batches_by_type=[],
        recent_errors=[],
        harvest_pool_size=0,
        harvest_unreleased=0,
        harvest_released_today=0,
        harvest_n_cap=0,
        harvest_budget_usd=0.0,
        harvest_projected_usd_today=0.0,
        harvest_sidecar_present=False,
    )


def _harvest_stats(*, now: datetime) -> _HarvestFields:
    """Sidecar pool + projected GitHub spend. Missing file or sqlite → zeros."""
    fields: _HarvestFields = {
        "harvest_pool_size": 0,
        "harvest_unreleased": 0,
        "harvest_released_today": 0,
        "harvest_n_cap": 0,
        "harvest_budget_usd": 0.0,
        "harvest_projected_usd_today": 0.0,
        "harvest_sidecar_present": False,
    }
    blended = 0.0
    try:
        econ = load_harvest_economics()
        fields["harvest_n_cap"] = econ.n_cap
        fields["harvest_budget_usd"] = econ.daily_budget_usd
        blended = econ.blended_github_usd
    except (FileNotFoundError, OSError, KeyError, ValueError):
        blended = 0.0

    path = harvest_db_path()
    if not path.is_file():
        return fields
    try:
        conn = connect_ro(path)
        try:
            pool = read_pool_stats(conn, now=now)
        finally:
            conn.close()
    except sqlite3.Error:
        return fields

    fields["harvest_sidecar_present"] = True
    fields["harvest_pool_size"] = pool.pool_size
    fields["harvest_unreleased"] = pool.unreleased
    fields["harvest_released_today"] = pool.released_today
    fields["harvest_projected_usd_today"] = pool.released_today * blended
    return fields


def _fetch_manifest_state_counts(conn: sqlite3.Connection) -> dict[str, int]:
    cursor = conn.execute(
        "SELECT processing_state, COUNT(*) FROM manifest GROUP BY processing_state"
    )
    return {str(row[0]): int(row[1]) for row in cursor.fetchall()}


def _fetch_scalar(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> int:
    row = conn.execute(sql, params).fetchone()
    return int(row[0]) if row is not None else 0


def _fetch_label_count_pairs(
    conn: sqlite3.Connection,
    sql: str,
    params: tuple = (),
) -> list[StatBucket]:
    cursor = conn.execute(sql, params)
    return [StatBucket(label=str(row[0]), count=int(row[1])) for row in cursor.fetchall()]


def read_stats_overview(*, db_path: str | Path | None = None) -> StatsOverview:
    """Aggregate pipeline and corpus stats from Bishop SQLite (read-only)."""
    generated_at = datetime.now(tz=UTC)
    path = Path(str(db_path or SQLITE_DB_PATH))
    if not path.is_file():
        empty = _empty_stats_overview(generated_at=generated_at)
        harvest = _harvest_stats(now=generated_at)
        return empty.model_copy(update=dict(harvest))

    uri = f"file:{path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        manifest_state_counts = _fetch_manifest_state_counts(conn)

        manifest_total = _fetch_scalar(conn, "SELECT COUNT(*) FROM manifest")
        entries_total = _fetch_scalar(conn, "SELECT COUNT(*) FROM entries")
        indexed_total = _fetch_scalar(
            conn,
            "SELECT COUNT(*) FROM entries WHERE processing_state = 'INDEXED'",
        )
        pre_filter_decided = _fetch_scalar(
            conn,
            "SELECT COUNT(*) FROM manifest WHERE relevance_decision IS NOT NULL",
        )
        pre_filter_passed = _fetch_scalar(
            conn,
            "SELECT COUNT(*) FROM manifest WHERE relevance_decision = 1",
        )

        hist_labels = _relevance_histogram_labels()
        hist_counts = {i: 0 for i in range(10)}
        cursor = conn.execute(
            """
            SELECT
                CASE
                    WHEN relevance_score >= 1.0 THEN 9
                    ELSE CAST(relevance_score * 10 AS INTEGER)
                END AS bucket,
                COUNT(*) AS n
            FROM entries
            WHERE relevance_score IS NOT NULL
            GROUP BY bucket
            """
        )
        for row in cursor.fetchall():
            bucket = int(row[0])
            if 0 <= bucket <= 9:
                hist_counts[bucket] = int(row[1])
        relevance_histogram = [
            StatBucket(label=hist_labels[i], count=hist_counts[i]) for i in range(10)
        ]

        by_domain = _fetch_label_count_pairs(
            conn,
            """
            SELECT domain, COUNT(*) AS n
            FROM entries
            GROUP BY domain
            ORDER BY n DESC
            """,
        )
        by_source = _fetch_label_count_pairs(
            conn,
            """
            SELECT source, COUNT(*) AS n
            FROM entries
            GROUP BY source
            ORDER BY n DESC
            """,
        )
        by_entry_type = _fetch_label_count_pairs(
            conn,
            """
            SELECT COALESCE(entry_type, '(unset)') AS label, COUNT(*) AS n
            FROM entries
            GROUP BY label
            ORDER BY n DESC
            """,
        )
        top_tags = _fetch_label_count_pairs(
            conn,
            """
            SELECT je.value AS tag, COUNT(*) AS n
            FROM entries, json_each(entries.tags) je
            GROUP BY je.value
            ORDER BY n DESC
            LIMIT 15
            """,
        )
        reading_status = _fetch_label_count_pairs(
            conn,
            """
            SELECT reading_status, COUNT(*) AS n
            FROM entries
            GROUP BY reading_status
            ORDER BY n DESC
            """,
        )

        ingest_cutoff = (generated_at - timedelta(days=30)).isoformat()
        ingest_rows = conn.execute(
            """
            SELECT date(ingested_at) AS d, COUNT(*) AS n
            FROM entries
            WHERE ingested_at >= ?
            GROUP BY d
            """,
            (ingest_cutoff,),
        ).fetchall()
        ingest_map = {str(row[0]): int(row[1]) for row in ingest_rows}
        ingest_by_day = _zero_fill_ingest(ingest_map, now=generated_at)

        batches_total = _fetch_scalar(conn, "SELECT COUNT(*) FROM batches")
        batches_by_status = _fetch_label_count_pairs(
            conn,
            """
            SELECT status, COUNT(*) AS n
            FROM batches
            GROUP BY status
            ORDER BY n DESC
            """,
        )
        batches_by_type = _fetch_label_count_pairs(
            conn,
            """
            SELECT batch_type, COUNT(*) AS n
            FROM batches
            GROUP BY batch_type
            ORDER BY n DESC
            """,
        )

        errors_cutoff = (generated_at - timedelta(days=7)).isoformat()
        recent_errors = _fetch_label_count_pairs(
            conn,
            """
            SELECT error_class, COUNT(*) AS n
            FROM error_log
            WHERE timestamp >= ?
            GROUP BY error_class
            ORDER BY n DESC
            """,
            (errors_cutoff,),
        )

        harvest = _harvest_stats(now=generated_at)
        return StatsOverview(
            generated_at=generated_at,
            manifest_total=manifest_total,
            entries_total=entries_total,
            indexed_total=indexed_total,
            pre_filter_decided=pre_filter_decided,
            pre_filter_passed=pre_filter_passed,
            funnel=_build_funnel(manifest_state_counts),
            queue_depth=_build_queue_depth(manifest_state_counts),
            relevance_histogram=relevance_histogram,
            by_domain=by_domain,
            by_source=by_source,
            by_entry_type=by_entry_type,
            top_tags=top_tags,
            reading_status=reading_status,
            ingest_by_day=ingest_by_day,
            batches_total=batches_total,
            batches_by_status=batches_by_status,
            batches_by_type=batches_by_type,
            recent_errors=recent_errors,
            **harvest,
        )
    finally:
        conn.close()
