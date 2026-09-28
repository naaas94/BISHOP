"""Unit tests for GET /stats/overview and read_stats_overview."""

from __future__ import annotations

import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

_REPO_ROOT = Path(__file__).resolve().parent.parent
_QUERY_API_ROOT = _REPO_ROOT / "services" / "query-api"
_STATE_WORKER_ROOT = _REPO_ROOT / "services" / "state-worker"


def _run_migrations(db_path: str) -> None:
    import importlib

    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            del sys.modules[name]

    sw_path = str(_STATE_WORKER_ROOT)
    qa_path = str(_QUERY_API_ROOT)
    removed_qa = False
    if qa_path in sys.path:
        sys.path.remove(qa_path)
        removed_qa = True

    inserted = sw_path not in sys.path
    if inserted:
        sys.path.insert(0, sw_path)
    try:
        db_mod = importlib.import_module("app.db")
        db_mod.run_migrations(db_path)
    finally:
        if inserted:
            sys.path.remove(sw_path)
        if removed_qa:
            sys.path.insert(0, qa_path)
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]


def _bucket_count(buckets: list[dict], label: str) -> int:
    for bucket in buckets:
        if bucket["label"] == label:
            return int(bucket["count"])
    return 0


@pytest.fixture
def stats_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_path = tmp_path / "bishop.db"
    _run_migrations(str(db_path))

    path_str = str(_QUERY_API_ROOT)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

    now = datetime.now(tz=UTC)
    today_iso = now.replace(hour=12, minute=0, second=0, microsecond=0).isoformat()
    ten_days_ago = (now - timedelta(days=10)).isoformat()
    recent_ts = now.isoformat()

    conn = sqlite3.connect(str(db_path))
    manifest_rows = [
        (
            "src-rej-1",
            "arxiv",
            "https://example.com/r1",
            "Rejected one",
            now.isoformat(),
            "professional",
            "RELEVANCE_REJECTED",
            0,
        ),
        (
            "src-rej-2",
            "github",
            "https://example.com/r2",
            "Rejected two",
            now.isoformat(),
            "professional",
            "RELEVANCE_REJECTED",
            0,
        ),
        (
            "src-pass",
            "rss",
            "https://example.com/p",
            "Passed",
            now.isoformat(),
            "professional",
            "RELEVANCE_PASSED",
            1,
        ),
        (
            "src-scrape-q",
            "hn",
            "https://example.com/sq",
            "Scrape queued",
            now.isoformat(),
            "personal",
            "SCRAPE_QUEUED",
            1,
        ),
        (
            "src-esc",
            "arxiv",
            "https://example.com/e",
            "Escalated",
            now.isoformat(),
            "professional",
            "ESCALATION_FLAGGED",
            None,
        ),
    ]
    for row in manifest_rows:
        conn.execute(
            """
            INSERT INTO manifest (
                source_id, source, url, title, discovered_at, domain,
                processing_state, relevance_decision
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row,
        )

    entry_rows = [
        (
            "e1",
            "arxiv:1",
            "arxiv",
            "https://arxiv.org/1",
            "Entry one",
            "body one",
            today_iso,
            "professional",
            "1.0.0",
            "batch-pf",
            "ok",
            "unread",
            0,
            "INDEXED",
            0.95,
            '["RAG", "eval"]',
            "paper",
        ),
        (
            "e2",
            "github:2",
            "github",
            "https://github.com/2",
            "Entry two",
            "body two",
            today_iso,
            "professional",
            "1.0.0",
            "batch-pf",
            "ok",
            "reading",
            0,
            "INDEXED",
            0.85,
            '["RAG"]',
            "repo",
        ),
        (
            "e3",
            "rss:3",
            "rss",
            "https://rss.example/3",
            "Entry three",
            "body three",
            today_iso,
            "personal",
            "1.0.0",
            "batch-pf",
            "ok",
            "read",
            0,
            "INDEXED",
            0.05,
            None,
            None,
        ),
    ]
    for row in entry_rows:
        conn.execute(
            """
            INSERT INTO entries (
                id, source_id, source, url, title, content_raw, ingested_at, domain,
                profile_version, pre_filter_batch_id, pre_filter_rationale,
                reading_status, flagged_for_review, processing_state,
                relevance_score, tags, entry_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row,
        )

    batch_rows = [
        (
            "b-complete-pf",
            "pre_filter",
            "professional",
            "1.0.0",
            "hash1",
            "complete",
            now.isoformat(),
            10,
            8,
            2,
        ),
        (
            "b-complete-e2",
            "enrichment_stage2",
            "professional",
            "1.0.0",
            "hash2",
            "complete",
            now.isoformat(),
            5,
            5,
            0,
        ),
        (
            "b-pending-pf",
            "pre_filter",
            "personal",
            "1.0.0",
            "hash3",
            "pending",
            now.isoformat(),
            0,
            0,
            0,
        ),
    ]
    for row in batch_rows:
        conn.execute(
            """
            INSERT INTO batches (
                batch_id, batch_type, domain, profile_version, profile_render_hash,
                status, created_at, entry_count, passed_count, failed_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row,
        )

    conn.execute(
        """
        INSERT INTO error_log (
            id, source_id, attempt_number, state_at_failure, error_class,
            message, is_retriable, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("err-1", "src-rej-1", 1, "SCRAPE_QUEUED", "http_error", "502", 1, recent_ts),
    )
    conn.execute(
        """
        INSERT INTO error_log (
            id, source_id, attempt_number, state_at_failure, error_class,
            message, is_retriable, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("err-2", "src-rej-2", 2, "SCRAPE_QUEUED", "http_error", "503", 1, recent_ts),
    )
    conn.execute(
        """
        INSERT INTO error_log (
            id, source_id, attempt_number, state_at_failure, error_class,
            message, is_retriable, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "err-old",
            "src-pass",
            1,
            "RELEVANCE_QUEUED",
            "timeout",
            "slow",
            1,
            ten_days_ago,
        ),
    )
    conn.commit()
    conn.close()

    import app.stats_reader as stats_reader_mod  # noqa: WPS433
    from app.routers import stats as stats_router  # noqa: WPS433

    monkeypatch.setattr(stats_reader_mod, "SQLITE_DB_PATH", str(db_path))
    monkeypatch.setattr(
        stats_reader_mod,
        "harvest_db_path",
        lambda: tmp_path / "harvest-absent" / "ledger.sqlite",
    )

    app = FastAPI()
    app.include_router(stats_router.router)
    return TestClient(app)


def test_stats_overview_aggregates(stats_client: TestClient) -> None:
    response = stats_client.get("/stats/overview")
    assert response.status_code == 200
    data = response.json()

    assert data["manifest_total"] == 5
    assert data["entries_total"] == 3
    assert data["indexed_total"] == 3
    assert data["pre_filter_decided"] == 4
    assert data["pre_filter_passed"] == 2

    funnel = data["funnel"]
    assert len(funnel) == 13
    assert _bucket_count(funnel, "Relevance rejected") == 2
    assert _bucket_count(funnel, "Escalated") == 1
    assert _bucket_count(funnel, "Indexed") == 0

    queue = data["queue_depth"]
    assert _bucket_count(queue, "SCRAPE_QUEUED") == 1

    hist = data["relevance_histogram"]
    assert len(hist) == 10
    en_dash = "\u2013"
    assert _bucket_count(hist, f"0.9{en_dash}1.0") == 1
    assert _bucket_count(hist, f"0.8{en_dash}0.9") == 1
    assert _bucket_count(hist, f"0.0{en_dash}0.1") == 1

    assert _bucket_count(data["by_domain"], "professional") == 2
    assert _bucket_count(data["by_domain"], "personal") == 1
    assert _bucket_count(data["by_entry_type"], "(unset)") == 1

    assert _bucket_count(data["top_tags"], "RAG") == 2
    assert _bucket_count(data["top_tags"], "eval") == 1

    assert _bucket_count(data["reading_status"], "unread") == 1
    assert _bucket_count(data["reading_status"], "reading") == 1
    assert _bucket_count(data["reading_status"], "read") == 1

    ingest = data["ingest_by_day"]
    today_key = datetime.now(tz=UTC).date().isoformat()
    assert ingest[-1]["date"] == today_key
    assert ingest[-1]["count"] == 3
    assert [bucket["label"] for bucket in ingest[-1]["by_source"]] == [
        "arxiv",
        "github",
        "rss",
    ]
    assert sum(bucket["count"] for bucket in ingest[-1]["by_source"]) == 3
    assert ingest[0]["count"] == 0
    assert ingest[0]["by_source"] == []
    expected_days = (datetime.now(tz=UTC).date() - (datetime.now(tz=UTC) - timedelta(days=30)).date()).days + 1
    assert len(ingest) == expected_days

    assert data["pre_filter_parked"] == 0
    assert data["pre_filter_proceeded"] == 2

    assert _bucket_count(data["batches_by_status"], "complete") == 2
    assert _bucket_count(data["batches_by_status"], "pending") == 1
    assert data["batches_total"] == 3

    recent = data["recent_errors"]
    assert _bucket_count(recent, "http_error") == 2
    assert _bucket_count(recent, "timeout") == 0

    assert data["harvest_sidecar_present"] is False
    assert data["harvest_pool_size"] == 0
    assert data["harvest_unreleased"] == 0
    assert data["harvest_released_today"] == 0
    assert data["harvest_projected_usd_today"] == 0.0


def test_read_stats_overview_missing_db_returns_zeros(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path_str = str(_QUERY_API_ROOT)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

    import app.stats_reader as stats_reader_mod  # noqa: WPS433
    from bishop_shared.harvest_economics import load_harvest_economics

    monkeypatch.setattr(
        stats_reader_mod,
        "harvest_db_path",
        lambda: tmp_path / "harvest-absent" / "ledger.sqlite",
    )
    missing = tmp_path / "does-not-exist.db"
    overview = stats_reader_mod.read_stats_overview(db_path=str(missing))
    assert overview.manifest_total == 0
    assert overview.batches_total == 0
    assert overview.harvest_sidecar_present is False
    assert overview.harvest_pool_size == 0
    assert overview.pre_filter_parked == 0
    assert overview.pre_filter_proceeded == 0
    assert overview.scrape_exceptions == []
    econ = load_harvest_economics(_REPO_ROOT / "config" / "harvest" / "economics.yaml")
    assert overview.harvest_n_cap == econ.n_cap
    assert overview.harvest_projected_usd_today == 0.0
    assert len(overview.relevance_histogram) == 10
    assert all(b.count == 0 for b in overview.relevance_histogram)


def _patch_harvest_db_path(
    monkeypatch: pytest.MonkeyPatch, ledger: Path
):
    path_str = str(_QUERY_API_ROOT)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
    import app.stats_reader as stats_reader_mod  # noqa: WPS433

    monkeypatch.setattr(
        "bishop_shared.harvest_ledger.HARVEST_DB_PATH", str(ledger)
    )
    monkeypatch.setattr(stats_reader_mod, "harvest_db_path", lambda: ledger)
    return stats_reader_mod


def test_read_stats_overview_harvest_sidecar_pool_size(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "bishop.db"
    _run_migrations(str(db_path))

    from bishop_shared.harvest_ledger import (
        HarvestCandidate,
        connect_rw,
        upsert_candidates,
    )

    ledger = tmp_path / "ledger.sqlite"
    now = datetime.now(tz=UTC)
    conn = connect_rw(ledger)
    try:
        upsert_candidates(
            conn,
            [
                HarvestCandidate(
                    source_id="github:acme/demo",
                    source="github",
                    url="https://github.com/acme/demo",
                    title="demo",
                )
            ],
            now=now,
        )
    finally:
        conn.close()

    monkeypatch.delenv("BISHOP_HARVEST_DAILY_BUDGET_USD", raising=False)
    stats_reader_mod = _patch_harvest_db_path(monkeypatch, ledger)
    overview = stats_reader_mod.read_stats_overview(db_path=str(db_path))
    assert overview.harvest_sidecar_present is True
    assert overview.harvest_pool_size == 1
    assert overview.harvest_unreleased == 1
    assert overview.harvest_released_today == 0
    assert overview.harvest_projected_usd_today == 0.0


def test_read_stats_overview_projected_usd_excludes_paper_reserve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "bishop.db"
    _run_migrations(str(db_path))

    from bishop_shared.harvest_economics import load_harvest_economics
    from bishop_shared.harvest_ledger import (
        HarvestCandidate,
        connect_rw,
        mark_released,
        upsert_candidates,
    )

    ledger = tmp_path / "ledger.sqlite"
    now = datetime.now(tz=UTC)
    conn = connect_rw(ledger)
    try:
        upsert_candidates(
            conn,
            [
                HarvestCandidate(
                    source_id="github:acme/released",
                    source="github",
                    url="https://github.com/acme/released",
                    title="released",
                )
            ],
            now=now,
        )
        mark_released(conn, ["github:acme/released"], now=now)
    finally:
        conn.close()

    monkeypatch.delenv("BISHOP_HARVEST_DAILY_BUDGET_USD", raising=False)
    stats_reader_mod = _patch_harvest_db_path(monkeypatch, ledger)
    overview = stats_reader_mod.read_stats_overview(db_path=str(db_path))
    econ = load_harvest_economics(_REPO_ROOT / "config" / "harvest" / "economics.yaml")
    assert overview.harvest_sidecar_present is True
    assert overview.harvest_released_today == 1
    assert overview.harvest_projected_usd_today == pytest.approx(econ.blended_github_usd)
    assert overview.harvest_projected_usd_today == pytest.approx(
        overview.harvest_released_today * econ.blended_github_usd
    )
    assert overview.harvest_projected_usd_today != pytest.approx(
        econ.blended_github_usd + econ.paper_reserve_usd
    )
    scrape = stats_reader_mod.read_scrape_stats(db_path=str(db_path))
    assert scrape.github_released_today == 1


def test_read_stats_overview_corrupt_harvest_sidecar_zeros(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "bishop.db"
    _run_migrations(str(db_path))
    ledger = tmp_path / "ledger.sqlite"
    ledger.write_text("not a sqlite database", encoding="utf-8")
    stats_reader_mod = _patch_harvest_db_path(monkeypatch, ledger)
    overview = stats_reader_mod.read_stats_overview(db_path=str(db_path))
    assert overview.harvest_sidecar_present is False
    assert overview.harvest_pool_size == 0
    assert overview.harvest_projected_usd_today == 0.0


def test_stats_harvest_missing_sidecar_zeros(stats_client: TestClient) -> None:
    response = stats_client.get("/stats/harvest")
    assert response.status_code == 200
    data = response.json()
    assert data["sidecar_present"] is False
    assert data["pool_size"] == 0
    assert data["unreleased_liability_usd"] == 0.0
    assert data["forecast_ready"] is False
    from bishop_shared.harvest_economics import load_harvest_economics

    econ = load_harvest_economics(_REPO_ROOT / "config" / "harvest" / "economics.yaml")
    assert data["n_cap"] == econ.n_cap


def test_read_harvest_stats_liability_overshoot_and_forecast(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "bishop.db"
    _run_migrations(str(db_path))
    conn = sqlite3.connect(str(db_path))
    now = datetime.now(tz=UTC)
    conn.execute(
        """
        INSERT INTO manifest (
            source_id, source, url, title, discovered_at, domain, processing_state
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "github:queued/one",
            "github",
            "https://github.com/queued/one",
            "queued",
            now.isoformat(),
            "professional",
            "DISCOVERED",
        ),
    )
    conn.execute(
        """
        INSERT INTO manifest (
            source_id, source, url, title, discovered_at, domain, processing_state
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "github:queued/two",
            "github",
            "https://github.com/queued/two",
            "queued two",
            now.isoformat(),
            "professional",
            "RELEVANCE_QUEUED",
        ),
    )
    conn.commit()
    conn.close()

    from bishop_shared.harvest_economics import load_harvest_economics
    from bishop_shared.harvest_ledger import (
        HarvestCandidate,
        HarvestRun,
        connect_rw,
        mark_released,
        record_run,
        set_cursor,
        upsert_candidates,
    )

    ledger = tmp_path / "ledger.sqlite"
    stamp = now
    conn = connect_rw(ledger)
    try:
        rows = [
            HarvestCandidate(
                source_id=f"github:pool/{i}",
                source="github",
                url=f"https://github.com/pool/{i}",
                title=f"pool {i}",
            )
            for i in range(5)
        ]
        upsert_candidates(conn, rows, now=stamp)
        mark_released(conn, [rows[0].source_id, rows[1].source_id], now=stamp)
        set_cursor(
            conn,
            "github",
            next_window_start="2024-12-15T00:00:00Z",
            harvest_until="2026-09-20T00:00:00Z",
            now=stamp,
            walk_direction="backward",
            high_water="2026-09-27T00:00:00Z",
        )
        windows = [
            ("2026-09-20T00:00:00Z", "2026-09-22T00:00:00Z", 200, False),
            ("2026-09-22T00:00:00Z", "2026-09-24T00:00:00Z", 400, False),
            ("2026-09-24T00:00:00Z", "2026-09-27T00:00:00Z", 900, False),
            ("2026-09-21T00:00:00Z", "2026-09-23T00:00:00Z", 1000, True),
        ]
        for start, end, total, incomplete in windows:
            record_run(
                conn,
                HarvestRun(
                    source="github",
                    query="pushed:x stars:>10",
                    window_start=start,
                    window_end=end,
                    total_count=total,
                    incomplete_results=incomplete,
                    pages_fetched=1,
                    items_upserted=total,
                    http_status=200,
                    ratelimit_remaining=10,
                    ratelimit_reset=None,
                    started_at=start,
                    finished_at=end,
                ),
            )
    finally:
        conn.close()

    monkeypatch.setenv("BISHOP_HARVEST_DAILY_BUDGET_USD", "4.52")
    stats_reader_mod = _patch_harvest_db_path(monkeypatch, ledger)
    harvest = stats_reader_mod.read_harvest_stats(db_path=str(db_path))
    econ = load_harvest_economics(_REPO_ROOT / "config" / "harvest" / "economics.yaml")
    assert harvest.sidecar_present is True
    assert harvest.pool_size == 5
    assert harvest.unreleased == 3
    assert harvest.released_today == 2
    assert harvest.unreleased_liability_usd == pytest.approx(3 * econ.blended_github_usd)
    assert harvest.pool_modeled_usd == pytest.approx(5 * econ.blended_github_usd)
    assert harvest.github_in_queue == 2
    assert harvest.n_cap == 4712
    assert harvest.tap_open is True
    assert harvest.released_overshoot is False
    assert harvest.days_to_drain == 1
    assert harvest.forecast_ready is True
    assert harvest.forecast_complete_windows == 3
    assert harvest.forecast_incomplete_windows == 1
    assert harvest.forecast_median_rate == 200.0
    assert harvest.walk_direction == "backward"

    overview = stats_reader_mod.read_stats_overview(db_path=str(db_path))
    assert overview.harvest_unreleased_liability_usd == pytest.approx(
        harvest.unreleased_liability_usd
    )
    assert overview.harvest_tap_open is True


def test_read_harvest_stats_tap_closed_on_overshoot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "bishop.db"
    _run_migrations(str(db_path))
    from bishop_shared.harvest_ledger import (
        HarvestCandidate,
        connect_rw,
        mark_released,
        upsert_candidates,
    )

    ledger = tmp_path / "ledger.sqlite"
    now = datetime.now(tz=UTC)
    conn = connect_rw(ledger)
    try:
        rows = [
            HarvestCandidate(
                source_id=f"github:over/{i}",
                source="github",
                url=f"https://github.com/over/{i}",
                title=f"over {i}",
            )
            for i in range(3)
        ]
        upsert_candidates(conn, rows, now=now)
        mark_released(conn, [row.source_id for row in rows], now=now)
    finally:
        conn.close()

    monkeypatch.setenv("BISHOP_HARVEST_DAILY_BUDGET_USD", "0.92")
    stats_reader_mod = _patch_harvest_db_path(monkeypatch, ledger)
    harvest = stats_reader_mod.read_harvest_stats(db_path=str(db_path))
    assert harvest.n_cap == 0
    assert harvest.tap_killed is True
    assert harvest.tap_open is False
    assert harvest.days_to_drain is None

    monkeypatch.setenv("BISHOP_HARVEST_DAILY_BUDGET_USD", "4.52")
    harvest = stats_reader_mod.read_harvest_stats(db_path=str(db_path))
    assert harvest.n_cap == 4712
    assert harvest.released_today == 3
    assert harvest.released_overshoot is False
    assert harvest.tap_open is True

    from bishop_shared.harvest_economics import load_harvest_economics

    monkeypatch.setenv("BISHOP_HARVEST_DAILY_BUDGET_USD", "0.922")
    econ = load_harvest_economics(_REPO_ROOT / "config" / "harvest" / "economics.yaml")
    harvest = stats_reader_mod.read_harvest_stats(db_path=str(db_path))
    assert harvest.n_cap == econ.n_cap
    assert harvest.n_cap == 2
    assert harvest.released_today == 3
    assert harvest.released_overshoot is True
    assert harvest.tap_open is False
    assert harvest.slots_remaining == 0
    assert harvest.released_fill_pct == 100.0


def test_stats_scrape_missing_state_returns_sources(
    stats_client: TestClient,
) -> None:
    response = stats_client.get("/stats/scrape")
    assert response.status_code == 200
    data = response.json()
    assert data["caught_up"] is False
    assert data["lag_source"] is None
    names = [row["source"] for row in data["sources"]]
    assert names[0] == "arxiv"
    assert "paperswithcode" in names
    pwc = next(row for row in data["sources"] if row["source"] == "paperswithcode")
    assert pwc["dead"] is True
    assert data["github_released_today"] is None


def test_read_scrape_stats_lag_and_discovered_today(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "bishop.db"
    _run_migrations(str(db_path))
    now = datetime.now(tz=UTC)
    fresh = (now - timedelta(hours=1)).isoformat()
    stale = (now - timedelta(hours=20)).isoformat()
    dead_lag = (now - timedelta(hours=100)).isoformat()
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        INSERT INTO scraper_state (source, last_successful_run_at, updated_at)
        VALUES (?, ?, ?)
        """,
        ("arxiv", fresh, now.isoformat()),
    )
    conn.execute(
        """
        INSERT INTO scraper_state (source, last_successful_run_at, updated_at)
        VALUES (?, ?, ?)
        """,
        ("github", stale, now.isoformat()),
    )
    conn.execute(
        """
        INSERT INTO scraper_state (source, last_successful_run_at, updated_at)
        VALUES (?, ?, ?)
        """,
        ("paperswithcode", dead_lag, now.isoformat()),
    )
    conn.execute(
        """
        INSERT INTO manifest (
            source_id, source, url, title, discovered_at, domain, processing_state
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "arxiv:today",
            "arxiv",
            "https://arxiv.org/abs/today",
            "today",
            now.isoformat(),
            "professional",
            "DISCOVERED",
        ),
    )
    conn.commit()
    conn.close()

    path_str = str(_QUERY_API_ROOT)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
    import app.stats_reader as stats_reader_mod  # noqa: WPS433

    monkeypatch.setattr(stats_reader_mod, "SQLITE_DB_PATH", str(db_path))
    monkeypatch.delenv("BISHOP_SCRAPER_SCHEDULE_INTERVAL_SEC", raising=False)
    monkeypatch.setenv("BISHOP_BACKFILL_WINDOW_OVERRIDE_DAYS", "60")
    scrape = stats_reader_mod.read_scrape_stats(db_path=str(db_path))
    assert scrape.overlay_window_days == 60
    assert scrape.schedule_interval_sec == 21600
    assert scrape.lag_source == "github"
    assert scrape.max_lag_hours == pytest.approx(20.0, abs=0.2)
    assert scrape.caught_up is False
    github = next(row for row in scrape.sources if row.source == "github")
    assert github.stale is True
    arxiv = next(row for row in scrape.sources if row.source == "arxiv")
    assert arxiv.stale is False
    assert arxiv.discovered_today == 1
    assert arxiv.in_queue == 1
    pwc = next(row for row in scrape.sources if row.source == "paperswithcode")
    assert pwc.dead is True
    assert scrape.discovered_today == 1

    overview = stats_reader_mod.read_stats_overview(db_path=str(db_path))
    assert overview.scrape_lag_source == "github"
    assert overview.scrape_caught_up is False
    names = [row.source for row in overview.scrape_exceptions]
    assert names[0] == "github"
    assert names[1] == "arxiv"
    assert "paperswithcode" not in names
    assert overview.scrape_exceptions[0].stale is True
    assert overview.scrape_exceptions[1].in_queue == 1
    assert overview.scrape_exceptions[1].stale is False
    assert scrape.github_released_today is None
    assert overview.today_discovered == 1


def test_read_today_stats_utc_window_excludes_yesterday(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "bishop.db"
    _run_migrations(str(db_path))
    now = datetime.now(tz=UTC)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = (midnight - timedelta(hours=1)).isoformat()
    today_ts = now.isoformat()
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        INSERT INTO manifest (
            source_id, source, url, title, discovered_at, domain, processing_state
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "arxiv:today",
            "arxiv",
            "https://arxiv.org/abs/today",
            "today",
            today_ts,
            "professional",
            "DISCOVERED",
        ),
    )
    conn.execute(
        """
        INSERT INTO manifest (
            source_id, source, url, title, discovered_at, domain, processing_state
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "arxiv:yesterday",
            "arxiv",
            "https://arxiv.org/abs/yest",
            "yesterday",
            yesterday,
            "professional",
            "INDEXED",
        ),
    )
    conn.execute(
        """
        INSERT INTO manifest (
            source_id, source, url, title, discovered_at, domain, processing_state
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "arxiv:indexed-today",
            "arxiv",
            "https://arxiv.org/abs/idx",
            "indexed today cohort",
            today_ts,
            "professional",
            "INDEXED",
        ),
    )
    conn.execute(
        """
        INSERT INTO entries (
            id, source_id, source, url, title, content_raw, ingested_at, domain,
            profile_version, pre_filter_batch_id, pre_filter_rationale,
            reading_status, flagged_for_review, processing_state
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "e-today",
            "arxiv:today-entry",
            "arxiv",
            "https://arxiv.org/abs/e",
            "entry today",
            "body",
            today_ts,
            "professional",
            "1.0.0",
            "b",
            "ok",
            "unread",
            0,
            "INDEXED",
        ),
    )
    conn.execute(
        """
        INSERT INTO entries (
            id, source_id, source, url, title, content_raw, ingested_at, domain,
            profile_version, pre_filter_batch_id, pre_filter_rationale,
            reading_status, flagged_for_review, processing_state
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "e-yest",
            "arxiv:yest-entry",
            "arxiv",
            "https://arxiv.org/abs/ey",
            "entry yest",
            "body",
            yesterday,
            "professional",
            "1.0.0",
            "b",
            "ok",
            "unread",
            0,
            "INDEXED",
        ),
    )
    conn.execute(
        """
        INSERT INTO batches (
            batch_id, batch_type, domain, profile_version, profile_render_hash,
            status, created_at, completed_at, entry_count, passed_count, failed_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "b-today",
            "pre_filter",
            "professional",
            "1.0.0",
            "h",
            "complete",
            today_ts,
            today_ts,
            1,
            1,
            0,
        ),
    )
    conn.execute(
        """
        INSERT INTO batches (
            batch_id, batch_type, domain, profile_version, profile_render_hash,
            status, created_at, completed_at, entry_count, passed_count, failed_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "b-yest",
            "pre_filter",
            "professional",
            "1.0.0",
            "h",
            "complete",
            yesterday,
            yesterday,
            1,
            1,
            0,
        ),
    )
    conn.execute(
        """
        INSERT INTO error_log (
            id, source_id, attempt_number, state_at_failure, error_class,
            message, is_retriable, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("err-today", "arxiv:today", 1, "DISCOVERED", "http_error", "502", 1, today_ts),
    )
    conn.execute(
        """
        INSERT INTO error_log (
            id, source_id, attempt_number, state_at_failure, error_class,
            message, is_retriable, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("err-yest", "arxiv:yesterday", 1, "DISCOVERED", "http_error", "502", 1, yesterday),
    )
    conn.commit()
    conn.close()

    path_str = str(_QUERY_API_ROOT)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
    import app.stats_reader as stats_reader_mod  # noqa: WPS433

    monkeypatch.setattr(stats_reader_mod, "SQLITE_DB_PATH", str(db_path))
    monkeypatch.setattr(
        stats_reader_mod,
        "harvest_db_path",
        lambda: tmp_path / "harvest-absent" / "ledger.sqlite",
    )
    today = stats_reader_mod.read_today_stats(db_path=str(db_path))
    assert today.utc_day == midnight.date().isoformat()
    assert today.discovered_today == 2
    assert today.indexed_cohort_today == 1
    assert today.entries_ingested_today == 1
    assert today.batches_completed_today == 1
    assert today.in_queue_today == 1
    assert next(b.count for b in today.discovered_by_source if b.label == "arxiv") == 2
    assert next(b.count for b in today.errors_today if b.label == "http_error") == 1
    assert next(b.count for b in today.funnel if b.label == "Discovered") == 1
    assert next(b.count for b in today.funnel if b.label == "Indexed") == 1
    assert today.harvest_sidecar_present is False
    assert today.scrape_caught_up is False
    assert today.scrape_in_queue == 1
    assert today.schedule_interval_sec == 21600
    assert any(row.source == "arxiv" and row.in_queue == 1 for row in today.scrape_exceptions)


def test_read_today_stats_missing_db_zeros(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path_str = str(_QUERY_API_ROOT)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
    import app.stats_reader as stats_reader_mod  # noqa: WPS433

    monkeypatch.setattr(
        stats_reader_mod,
        "harvest_db_path",
        lambda: tmp_path / "harvest-absent" / "ledger.sqlite",
    )
    missing = tmp_path / "does-not-exist.db"
    today = stats_reader_mod.read_today_stats(db_path=str(missing))
    assert today.discovered_today == 0
    assert today.entries_ingested_today == 0
    assert today.indexed_cohort_today == 0
    assert today.batches_completed_today == 0
    assert today.harvest_sidecar_present is False
    assert today.funnel
    assert all(b.count == 0 for b in today.funnel)
    assert today.scrape_caught_up is False
    assert today.scrape_in_queue == 0
    assert today.scrape_exceptions == []
    assert today.schedule_interval_sec == 21600


def test_pre_filter_proceeded_excludes_parked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "bishop.db"
    _run_migrations(str(db_path))
    now = datetime.now(tz=UTC).isoformat()
    conn = sqlite3.connect(str(db_path))
    rows = [
        (
            "src-parked",
            "arxiv",
            "https://example.com/parked",
            "Parked",
            now,
            "professional",
            "RELEVANCE_PARKED",
            1,
        ),
        (
            "src-pass",
            "github",
            "https://example.com/pass",
            "Passed",
            now,
            "professional",
            "INDEXED",
            1,
        ),
        (
            "src-rej",
            "arxiv",
            "https://example.com/rej",
            "Rejected",
            now,
            "professional",
            "RELEVANCE_REJECTED",
            0,
        ),
    ]
    for row in rows:
        conn.execute(
            """
            INSERT INTO manifest (
                source_id, source, url, title, discovered_at, domain,
                processing_state, relevance_decision
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row,
        )
    conn.commit()
    conn.close()

    path_str = str(_QUERY_API_ROOT)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
    import app.stats_reader as stats_reader_mod  # noqa: WPS433

    monkeypatch.setattr(stats_reader_mod, "SQLITE_DB_PATH", str(db_path))
    monkeypatch.setattr(
        stats_reader_mod,
        "harvest_db_path",
        lambda: tmp_path / "harvest-absent" / "ledger.sqlite",
    )
    overview = stats_reader_mod.read_stats_overview(db_path=str(db_path))
    assert overview.pre_filter_decided == 3
    assert overview.pre_filter_passed == 2
    assert overview.pre_filter_parked == 1
    assert overview.pre_filter_proceeded == 1
