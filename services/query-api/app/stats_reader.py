"""Read-only SQLite aggregate stats for query-api."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TypedDict

from bishop_shared.constants import SQLITE_DB_PATH
from bishop_shared.enums import SourceEnum
from bishop_shared.harvest_economics import (
    days_to_drain,
    load_harvest_economics,
    modeled_usd,
    remaining_slots,
)
from bishop_shared.harvest_forecast import (
    compute_walk_forecast,
    empty_walk_forecast,
    parse_harvest_iso,
)
from bishop_shared.harvest_ledger import (
    connect_ro,
    harvest_db_path,
    list_harvest_runs,
    read_cursor,
    read_pool_stats,
)
from bishop_shared.scraper_config import (
    BACKFILL_CONFIG,
    DEAD_SCRAPE_SOURCES,
    SCRAPE_SOURCE_ORDER,
    backfill_enabled,
    overlay_window_days,
    schedule_interval_sec,
)

from app.models import (
    DailyCount,
    HarvestStats,
    ScrapeExceptionRow,
    ScrapeSourceRow,
    ScrapeStats,
    StatBucket,
    StatsOverview,
    TodayStats,
)

_GITHUB_QUEUE_STATES = ("DISCOVERED", "RELEVANCE_QUEUED")
_HARVEST_SOURCE = SourceEnum.GITHUB.value
_SCRAPE_NOTES: dict[str, str] = {
    SourceEnum.GITHUB.value: (
        "Incremental still writes DISCOVERED. Harvest mill is a sibling."
    ),
    SourceEnum.HUGGINGFACE.value: "Incremental only. Not rewound.",
    SourceEnum.PAPERSWITHCODE.value: "API dead.",
}

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
    harvest_unreleased_liability_usd: float
    harvest_tap_open: bool


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


def _source_rank(source: str) -> tuple[int, str]:
    try:
        return (SCRAPE_SOURCE_ORDER.index(source), source)
    except ValueError:
        return (len(SCRAPE_SOURCE_ORDER), source)


def _ordered_source_buckets(counts: dict[str, int]) -> list[StatBucket]:
    names = sorted(counts, key=_source_rank)
    return [StatBucket(label=name, count=counts[name]) for name in names]


def _zero_fill_ingest(
    counts_by_date: dict[str, int],
    *,
    now: datetime,
    by_source_by_date: dict[str, list[StatBucket]] | None = None,
) -> list[DailyCount]:
    by_source_by_date = by_source_by_date or {}
    cutoff_date = (now - timedelta(days=30)).date()
    today = now.date()
    result: list[DailyCount] = []
    day = cutoff_date
    while day <= today:
        key = day.isoformat()
        result.append(
            DailyCount(
                date=key,
                count=counts_by_date.get(key, 0),
                by_source=list(by_source_by_date.get(key, [])),
            )
        )
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
        harvest_unreleased_liability_usd=0.0,
        harvest_tap_open=False,
        scrape_max_lag_hours=0.0,
        scrape_lag_source=None,
        scrape_caught_up=False,
        scrape_exceptions=[],
        today_discovered=0,
        pre_filter_parked=0,
        pre_filter_proceeded=0,
    )


def _harvest_stats(*, now: datetime, github_in_queue: int = 0) -> _HarvestFields:
    """Sidecar pool + projected GitHub spend. Missing file or sqlite → zeros."""
    fields: _HarvestFields = {
        "harvest_pool_size": 0,
        "harvest_unreleased": 0,
        "harvest_released_today": 0,
        "harvest_n_cap": 0,
        "harvest_budget_usd": 0.0,
        "harvest_projected_usd_today": 0.0,
        "harvest_sidecar_present": False,
        "harvest_unreleased_liability_usd": 0.0,
        "harvest_tap_open": False,
    }
    blended = 0.0
    n_cap = 0
    try:
        econ = load_harvest_economics()
        n_cap = econ.n_cap
        fields["harvest_n_cap"] = n_cap
        fields["harvest_budget_usd"] = econ.daily_budget_usd
        blended = econ.blended_github_usd
    except (FileNotFoundError, OSError, KeyError, ValueError):
        blended = 0.0
        n_cap = 0

    path = harvest_db_path()
    if not path.is_file():
        fields["harvest_tap_open"] = (
            remaining_slots(
                n_cap=n_cap, released_today=0, github_in_queue=github_in_queue
            )
            > 0
        )
        return fields
    try:
        conn = connect_ro(path)
        try:
            pool = read_pool_stats(conn, now=now)
        finally:
            conn.close()
    except sqlite3.Error:
        fields["harvest_tap_open"] = (
            remaining_slots(
                n_cap=n_cap, released_today=0, github_in_queue=github_in_queue
            )
            > 0
        )
        return fields

    fields["harvest_sidecar_present"] = True
    fields["harvest_pool_size"] = pool.pool_size
    fields["harvest_unreleased"] = pool.unreleased
    fields["harvest_released_today"] = pool.released_today
    fields["harvest_projected_usd_today"] = modeled_usd(
        count=pool.released_today, blended=blended
    )
    fields["harvest_unreleased_liability_usd"] = modeled_usd(
        count=pool.unreleased, blended=blended
    )
    fields["harvest_tap_open"] = (
        remaining_slots(
            n_cap=n_cap,
            released_today=pool.released_today,
            github_in_queue=github_in_queue,
        )
        > 0
    )
    return fields


def _count_github_in_queue(conn: sqlite3.Connection) -> int:
    placeholders = ",".join("?" * len(_GITHUB_QUEUE_STATES))
    try:
        return _fetch_scalar(
            conn,
            f"""
            SELECT COUNT(*) FROM manifest
            WHERE source = ?
              AND processing_state IN ({placeholders})
            """,
            (_HARVEST_SOURCE, *_GITHUB_QUEUE_STATES),
        )
    except sqlite3.Error:
        return 0


def _empty_harvest_stats(*, generated_at: datetime) -> HarvestStats:
    return HarvestStats(generated_at=generated_at)


def read_harvest_stats(
    *,
    db_path: str | Path | None = None,
) -> HarvestStats:
    """Pool liability, mill walk, and faucet. Missing sidecar or yaml → zeros."""
    generated_at = datetime.now(tz=UTC)
    github_in_queue = 0
    bishop_path = Path(str(db_path or SQLITE_DB_PATH))
    if bishop_path.is_file():
        uri = f"file:{bishop_path.as_posix()}?mode=ro"
        try:
            bishop_conn = sqlite3.connect(uri, uri=True)
            bishop_conn.row_factory = sqlite3.Row
            try:
                github_in_queue = _count_github_in_queue(bishop_conn)
            finally:
                bishop_conn.close()
        except sqlite3.Error:
            github_in_queue = 0

    blended = 0.0
    n_cap = 0
    budget_usd = 0.0
    paper_reserve_usd = 0.0
    github_budget_usd = 0.0
    try:
        econ = load_harvest_economics()
        blended = econ.blended_github_usd
        n_cap = econ.n_cap
        budget_usd = econ.daily_budget_usd
        paper_reserve_usd = econ.paper_reserve_usd
        github_budget_usd = econ.github_budget_usd
    except (FileNotFoundError, OSError, KeyError, ValueError):
        blended = 0.0
        n_cap = 0

    sidecar_path = harvest_db_path()
    if not sidecar_path.is_file():
        remaining = remaining_slots(
            n_cap=n_cap, released_today=0, github_in_queue=github_in_queue
        )
        return HarvestStats(
            generated_at=generated_at,
            sidecar_present=False,
            blended_github_usd=blended,
            days_to_drain=days_to_drain(unreleased=0, n_cap=n_cap),
            n_cap=n_cap,
            budget_usd=budget_usd,
            paper_reserve_usd=paper_reserve_usd,
            github_budget_usd=github_budget_usd,
            github_in_queue=github_in_queue,
            slots_remaining=remaining,
            tap_open=remaining > 0,
            tap_killed=n_cap == 0,
        )

    try:
        conn = connect_ro(sidecar_path)
        try:
            pool = read_pool_stats(conn, now=generated_at)
            cursor = read_cursor(conn, _HARVEST_SOURCE)
            runs = list_harvest_runs(conn, _HARVEST_SOURCE)
        finally:
            conn.close()
    except sqlite3.Error:
        remaining = remaining_slots(
            n_cap=n_cap, released_today=0, github_in_queue=github_in_queue
        )
        empty = _empty_harvest_stats(generated_at=generated_at)
        return empty.model_copy(
            update={
                "blended_github_usd": blended,
                "n_cap": n_cap,
                "budget_usd": budget_usd,
                "paper_reserve_usd": paper_reserve_usd,
                "github_budget_usd": github_budget_usd,
                "github_in_queue": github_in_queue,
                "slots_remaining": remaining,
                "tap_open": remaining > 0,
                "tap_killed": n_cap == 0,
                "days_to_drain": days_to_drain(unreleased=0, n_cap=n_cap),
            }
        )

    remaining = remaining_slots(
        n_cap=n_cap,
        released_today=pool.released_today,
        github_in_queue=github_in_queue,
    )
    walk = (
        compute_walk_forecast(cursor, runs, blended_usd=blended)
        if cursor is not None
        else empty_walk_forecast()
    )
    fill_pct = 0.0
    if n_cap > 0:
        fill_pct = min(100.0, pool.released_today / n_cap * 100.0)

    return HarvestStats(
        generated_at=generated_at,
        sidecar_present=True,
        pool_size=pool.pool_size,
        unreleased=pool.unreleased,
        unreleased_liability_usd=modeled_usd(count=pool.unreleased, blended=blended),
        pool_modeled_usd=modeled_usd(count=pool.pool_size, blended=blended),
        blended_github_usd=blended,
        days_to_drain=days_to_drain(unreleased=pool.unreleased, n_cap=n_cap),
        n_cap=n_cap,
        budget_usd=budget_usd,
        paper_reserve_usd=paper_reserve_usd,
        github_budget_usd=github_budget_usd,
        released_today=pool.released_today,
        github_in_queue=github_in_queue,
        slots_remaining=remaining,
        tap_open=remaining > 0,
        tap_killed=n_cap == 0,
        released_overshoot=n_cap > 0 and pool.released_today > n_cap,
        released_fill_pct=fill_pct,
        modeled_usd_today=modeled_usd(count=pool.released_today, blended=blended),
        walk_direction=walk.walk_direction,
        floor_at=walk.floor_at,
        harvest_until=walk.harvest_until,
        high_water=walk.high_water,
        cursor_updated_at=walk.cursor_updated_at,
        unwalked_days=walk.unwalked_days,
        walked_recent_days=walk.walked_recent_days,
        window_span_days=walk.window_span_days,
        walked_pct=walk.walked_pct,
        forecast_ready=walk.forecast_ready,
        forecast_complete_windows=walk.complete_windows,
        forecast_incomplete_windows=walk.incomplete_windows,
        forecast_median_rate=walk.median_rate,
        forecast_upper_rate=walk.upper_rate,
        forecast_median_usd=walk.median_usd,
        forecast_upper_usd=walk.upper_usd,
    )


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


def _utc_midnight(now: datetime) -> datetime:
    return now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


def _pin_window_days(source: str) -> int:
    config = BACKFILL_CONFIG.get(source)
    return config.window_days if config is not None else 0


def _build_scrape_sources(
    conn: sqlite3.Connection | None,
    *,
    now: datetime,
) -> list[ScrapeSourceRow]:
    interval_hours = schedule_interval_sec() / 3600.0
    cursors: dict[str, tuple[str | None, str | None]] = {}
    discovered: dict[str, int] = {}
    queued: dict[str, int] = {}
    if conn is not None:
        try:
            for row in conn.execute(
                "SELECT source, last_successful_run_at, updated_at FROM scraper_state"
            ):
                cursors[str(row[0])] = (
                    str(row[1]) if row[1] is not None else None,
                    str(row[2]) if row[2] is not None else None,
                )
            midnight = _utc_midnight(now).isoformat()
            for row in conn.execute(
                """
                SELECT source, COUNT(*) FROM manifest
                WHERE discovered_at >= ?
                GROUP BY source
                """,
                (midnight,),
            ):
                discovered[str(row[0])] = int(row[1])
            placeholders = ",".join("?" * len(_GITHUB_QUEUE_STATES))
            for row in conn.execute(
                f"""
                SELECT source, COUNT(*) FROM manifest
                WHERE processing_state IN ({placeholders})
                GROUP BY source
                """,
                _GITHUB_QUEUE_STATES,
            ):
                queued[str(row[0])] = int(row[1])
        except sqlite3.Error:
            cursors = {}
            discovered = {}
            queued = {}

    rows: list[ScrapeSourceRow] = []
    for source in SCRAPE_SOURCE_ORDER:
        last_raw, updated_raw = cursors.get(source, (None, None))
        last_dt = parse_harvest_iso(last_raw)
        lag_hours: float | None = None
        if last_dt is not None:
            lag_hours = max(0.0, (now - last_dt).total_seconds() / 3600.0)
        dead = source in DEAD_SCRAPE_SOURCES
        stale = (
            (not dead)
            and lag_hours is not None
            and interval_hours > 0
            and lag_hours > 2 * interval_hours
        )
        fill_pct = 0.0
        if lag_hours is not None and interval_hours > 0:
            fill_pct = min(100.0, lag_hours / (2 * interval_hours) * 100.0)
        rows.append(
            ScrapeSourceRow(
                source=source,
                last_successful_run_at=last_raw,
                updated_at=updated_raw,
                lag_hours=lag_hours,
                lag_fill_pct=fill_pct,
                pin_window_days=_pin_window_days(source),
                discovered_today=discovered.get(source, 0),
                in_queue=queued.get(source, 0),
                dead=dead,
                stale=stale,
                note=_SCRAPE_NOTES.get(source),
            )
        )
    return rows


def _scrape_glance(sources: list[ScrapeSourceRow]) -> dict[str, float | str | bool | None]:
    live = [
        row
        for row in sources
        if not row.dead and row.lag_hours is not None
    ]
    if not live:
        return {
            "scrape_max_lag_hours": 0.0,
            "scrape_lag_source": None,
            "scrape_caught_up": False,
        }
    worst = max(live, key=lambda row: row.lag_hours or 0.0)
    interval_hours = schedule_interval_sec() / 3600.0
    caught_up = all(
        (row.lag_hours or 0.0) <= interval_hours for row in live
    )
    return {
        "scrape_max_lag_hours": worst.lag_hours or 0.0,
        "scrape_lag_source": worst.source,
        "scrape_caught_up": caught_up,
    }


def _scrape_exceptions(sources: list[ScrapeSourceRow]) -> list[ScrapeExceptionRow]:
    rows = [
        ScrapeExceptionRow(
            source=row.source,
            lag_hours=row.lag_hours,
            discovered_today=row.discovered_today,
            in_queue=row.in_queue,
            stale=row.stale,
        )
        for row in sources
        if (not row.dead) and (row.stale or row.in_queue > 0)
    ]
    rows.sort(key=lambda row: (not row.stale, -row.in_queue, row.source))
    return rows


def _github_released_today(*, now: datetime) -> int | None:
    path = harvest_db_path()
    if not path.is_file():
        return None
    try:
        conn = connect_ro(path)
        try:
            pool = read_pool_stats(conn, now=now)
        finally:
            conn.close()
    except sqlite3.Error:
        return None
    return pool.released_today


def read_scrape_stats(*, db_path: str | Path | None = None) -> ScrapeStats:
    """Incremental cursors and today's inserts. Missing DB → empty sources."""
    generated_at = datetime.now(tz=UTC)
    sources: list[ScrapeSourceRow] = []
    path = Path(str(db_path or SQLITE_DB_PATH))
    if path.is_file():
        uri = f"file:{path.as_posix()}?mode=ro"
        try:
            conn = sqlite3.connect(uri, uri=True)
            conn.row_factory = sqlite3.Row
            try:
                sources = _build_scrape_sources(conn, now=generated_at)
            finally:
                conn.close()
        except sqlite3.Error:
            sources = _build_scrape_sources(None, now=generated_at)
    else:
        sources = _build_scrape_sources(None, now=generated_at)

    glance = _scrape_glance(sources)
    return ScrapeStats(
        generated_at=generated_at,
        schedule_interval_sec=schedule_interval_sec(),
        overlay_window_days=overlay_window_days(),
        backfill_enabled=backfill_enabled(),
        max_lag_hours=float(glance["scrape_max_lag_hours"] or 0.0),
        lag_source=(
            str(glance["scrape_lag_source"])
            if glance["scrape_lag_source"] is not None
            else None
        ),
        caught_up=bool(glance["scrape_caught_up"]),
        discovered_today=sum(row.discovered_today for row in sources),
        in_queue=sum(row.in_queue for row in sources),
        github_released_today=_github_released_today(now=generated_at),
        sources=sources,
    )


def read_stats_overview(*, db_path: str | Path | None = None) -> StatsOverview:
    """Aggregate pipeline and corpus stats from Bishop SQLite (read-only)."""
    generated_at = datetime.now(tz=UTC)
    path = Path(str(db_path or SQLITE_DB_PATH))
    if not path.is_file():
        empty = _empty_stats_overview(generated_at=generated_at)
        harvest = _harvest_stats(now=generated_at, github_in_queue=0)
        scrape_sources = _build_scrape_sources(None, now=generated_at)
        scrape = _scrape_glance(scrape_sources)
        return empty.model_copy(
            update={
                **dict(harvest),
                **scrape,
                "today_discovered": 0,
                "scrape_exceptions": _scrape_exceptions(scrape_sources),
            }
        )

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
        pre_filter_parked = _fetch_scalar(
            conn,
            "SELECT COUNT(*) FROM manifest WHERE processing_state = 'RELEVANCE_PARKED'",
        )
        pre_filter_proceeded = _fetch_scalar(
            conn,
            """
            SELECT COUNT(*) FROM manifest
            WHERE relevance_decision = 1 AND processing_state != 'RELEVANCE_PARKED'
            """,
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
            SELECT date(ingested_at) AS d, source, COUNT(*) AS n
            FROM entries
            WHERE ingested_at >= ?
            GROUP BY d, source
            """,
            (ingest_cutoff,),
        ).fetchall()
        ingest_map: dict[str, int] = {}
        by_source_map: dict[str, dict[str, int]] = {}
        for row in ingest_rows:
            day = str(row[0])
            source = str(row[1])
            n = int(row[2])
            ingest_map[day] = ingest_map.get(day, 0) + n
            day_sources = by_source_map.setdefault(day, {})
            day_sources[source] = n
        ingest_by_day = _zero_fill_ingest(
            ingest_map,
            now=generated_at,
            by_source_by_date={
                day: _ordered_source_buckets(counts)
                for day, counts in by_source_map.items()
            },
        )

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

        harvest = _harvest_stats(
            now=generated_at,
            github_in_queue=_count_github_in_queue(conn),
        )
        scrape_sources = _build_scrape_sources(conn, now=generated_at)
        scrape = _scrape_glance(scrape_sources)
        return StatsOverview(
            generated_at=generated_at,
            manifest_total=manifest_total,
            entries_total=entries_total,
            indexed_total=indexed_total,
            pre_filter_decided=pre_filter_decided,
            pre_filter_passed=pre_filter_passed,
            pre_filter_parked=pre_filter_parked,
            pre_filter_proceeded=pre_filter_proceeded,
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
            today_discovered=sum(row.discovered_today for row in scrape_sources),
            scrape_exceptions=_scrape_exceptions(scrape_sources),
            **harvest,
            **scrape,
        )
    finally:
        conn.close()


def _in_queue_today_count(state_counts: dict[str, int]) -> int:
    total = 0
    for state, count in state_counts.items():
        if state == "DISCOVERED" or any(state.endswith(suffix) for suffix in _QUEUE_SUFFIXES):
            total += count
    return total


def _today_scrape_attach(
    conn: sqlite3.Connection | None,
    *,
    now: datetime,
) -> dict[str, object]:
    sources = _build_scrape_sources(conn, now=now)
    glance = _scrape_glance(sources)
    discovered_by_source = [
        StatBucket(label=row.source, count=row.discovered_today)
        for row in sorted(
            (row for row in sources if row.discovered_today > 0),
            key=lambda row: (-row.discovered_today, row.source),
        )
    ]
    return {
        **glance,
        "scrape_in_queue": sum(row.in_queue for row in sources),
        "scrape_exceptions": _scrape_exceptions(sources),
        "overlay_window_days": overlay_window_days(),
        "schedule_interval_sec": schedule_interval_sec(),
        "discovered_by_source": discovered_by_source,
        "discovered_today": sum(row.discovered_today for row in sources),
    }


def _faucet_from_harvest(harvest: _HarvestFields) -> dict[str, object]:
    n_cap = harvest["harvest_n_cap"]
    released = harvest["harvest_released_today"]
    fill = min(100.0, released / n_cap * 100.0) if n_cap else 0.0
    return {
        "harvest_sidecar_present": harvest["harvest_sidecar_present"],
        "harvest_released_today": released,
        "harvest_modeled_usd_today": harvest["harvest_projected_usd_today"],
        "harvest_n_cap": n_cap,
        "harvest_tap_open": harvest["harvest_tap_open"],
        "harvest_tap_killed": n_cap == 0,
        "harvest_released_overshoot": n_cap > 0 and released > n_cap,
        "harvest_released_fill_pct": fill,
    }


def read_today_stats(*, db_path: str | Path | None = None) -> TodayStats:
    """UTC-day cohort from bishop.db plus harvest faucet. Missing DB → zeros."""
    generated_at = datetime.now(tz=UTC)
    midnight = _utc_midnight(generated_at)
    midnight_iso = midnight.isoformat()
    utc_day = midnight.date().isoformat()

    def _zeros(
        *,
        github_in_queue: int = 0,
        conn: sqlite3.Connection | None = None,
    ) -> TodayStats:
        faucet = _faucet_from_harvest(
            _harvest_stats(now=generated_at, github_in_queue=github_in_queue)
        )
        scrape = _today_scrape_attach(conn, now=generated_at)
        return TodayStats(
            generated_at=generated_at,
            utc_day=utc_day,
            utc_midnight=midnight_iso,
            funnel=_build_funnel({}),
            **faucet,
            **scrape,
        )

    path = Path(str(db_path or SQLITE_DB_PATH))
    if not path.is_file():
        return _zeros()

    uri = f"file:{path.as_posix()}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
    except sqlite3.Error:
        return _zeros()

    try:
        harvest = _harvest_stats(
            now=generated_at,
            github_in_queue=_count_github_in_queue(conn),
        )
        faucet = _faucet_from_harvest(harvest)
        scrape = _today_scrape_attach(conn, now=generated_at)
        state_counts: dict[str, int] = {}
        try:
            for row in conn.execute(
                """
                SELECT processing_state, COUNT(*) AS n
                FROM manifest
                WHERE discovered_at >= ?
                GROUP BY processing_state
                """,
                (midnight_iso,),
            ):
                state_counts[str(row[0])] = int(row[1])
        except sqlite3.Error:
            state_counts = {}
        entries_ingested_today = _fetch_scalar(
            conn,
            "SELECT COUNT(*) FROM entries WHERE ingested_at >= ?",
            (midnight_iso,),
        )
        batches_completed_today = _fetch_scalar(
            conn,
            "SELECT COUNT(*) FROM batches WHERE completed_at >= ?",
            (midnight_iso,),
        )
        batches_by_status = _fetch_label_count_pairs(
            conn,
            """
            SELECT status, COUNT(*) AS n
            FROM batches
            WHERE completed_at >= ?
            GROUP BY status
            ORDER BY n DESC
            """,
            (midnight_iso,),
        )
        batches_by_type = _fetch_label_count_pairs(
            conn,
            """
            SELECT batch_type, COUNT(*) AS n
            FROM batches
            WHERE completed_at >= ?
            GROUP BY batch_type
            ORDER BY n DESC
            """,
            (midnight_iso,),
        )
        errors_today = _fetch_label_count_pairs(
            conn,
            """
            SELECT error_class, COUNT(*) AS n
            FROM error_log
            WHERE timestamp >= ?
            GROUP BY error_class
            ORDER BY n DESC
            """,
            (midnight_iso,),
        )
        return TodayStats(
            generated_at=generated_at,
            utc_day=utc_day,
            utc_midnight=midnight_iso,
            in_queue_today=_in_queue_today_count(state_counts),
            indexed_cohort_today=state_counts.get("INDEXED", 0),
            entries_ingested_today=entries_ingested_today,
            batches_completed_today=batches_completed_today,
            batches_by_status=batches_by_status,
            batches_by_type=batches_by_type,
            errors_today=errors_today,
            funnel=_build_funnel(state_counts),
            queue_depth=_build_queue_depth(state_counts),
            **faucet,
            **scrape,
        )
    except sqlite3.Error:
        return _zeros(conn=conn)
    finally:
        conn.close()
