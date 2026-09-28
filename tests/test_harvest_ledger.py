"""Harvest economics + sidecar ledger tests."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from bishop_shared.harvest_economics import (
    days_to_drain,
    load_harvest_economics,
    modeled_usd,
    remaining_slots,
)
from bishop_shared.harvest_ledger import (
    HarvestCandidate,
    connect_rw,
    get_cursor,
    harvest_db_path,
    init_schema,
    mark_released,
    read_pool_stats,
    select_release_batch,
    upsert_candidates,
)

_REPO = Path(__file__).resolve().parent.parent
_ECON = _REPO / "config" / "harvest" / "economics.yaml"
_NOW = datetime(2026, 9, 17, 15, 0, 0, tzinfo=UTC)


def test_worked_example_n_cap() -> None:
    econ = load_harvest_economics(_ECON)
    assert econ.daily_budget_usd == 2.0
    assert abs(econ.blended_github_usd - 0.000764) < 1e-12
    assert abs(econ.paper_reserve_usd - 0.92) < 1e-12
    assert econ.n_cap == 1413


def test_env_zero_budget_kills_n_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BISHOP_HARVEST_DAILY_BUDGET_USD", "0")
    econ = load_harvest_economics(_ECON)
    assert econ.n_cap == 0


def test_harvest_db_path_env_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "custom-ledger.sqlite"
    monkeypatch.setenv("BISHOP_HARVEST_DB_PATH", str(target))
    assert harvest_db_path() == target


def test_remaining_slots_queue_and_released() -> None:
    assert remaining_slots(n_cap=1413, released_today=0, github_in_queue=1000) == 413
    assert remaining_slots(n_cap=1413, released_today=1413, github_in_queue=0) == 0
    assert remaining_slots(n_cap=1413, released_today=50, github_in_queue=50) == 1363


def test_remaining_slots_overshoot_is_closed() -> None:
    assert remaining_slots(n_cap=4712, released_today=14136, github_in_queue=0) == 0


def test_days_to_drain_and_modeled_usd() -> None:
    econ = load_harvest_economics(_ECON)
    assert days_to_drain(unreleased=103417, n_cap=4712) == 22
    assert days_to_drain(unreleased=0, n_cap=4712) == 0
    assert days_to_drain(unreleased=100, n_cap=0) is None
    assert modeled_usd(count=103417, blended=econ.blended_github_usd) == pytest.approx(
        103417 * econ.blended_github_usd
    )
    assert modeled_usd(count=0, blended=econ.blended_github_usd) == 0.0


def test_upsert_and_recency_select(tmp_path: Path) -> None:
    conn = connect_rw(tmp_path / "ledger.sqlite")
    try:
        old = HarvestCandidate(
            source_id="github:old/repo",
            source="github",
            url="https://github.com/old/repo",
            title="old",
            pushed_at="2024-01-01T00:00:00Z",
        )
        fresh = HarvestCandidate(
            source_id="github:new/repo",
            source="github",
            url="https://github.com/new/repo",
            title="new",
            pushed_at=(_NOW - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        upsert_candidates(conn, [old, fresh], now=_NOW)
        batch = select_release_batch(conn, now=_NOW, limit=1)
        assert batch[0]["source_id"] == "github:new/repo"
        mark_released(conn, ["github:new/repo"], now=_NOW)
        stats = read_pool_stats(conn, now=_NOW)
        assert stats.pool_size == 2
        assert stats.unreleased == 1
        assert stats.released_today == 1
        again = select_release_batch(conn, now=_NOW, limit=10)
        assert [row["source_id"] for row in again] == ["github:old/repo"]
    finally:
        conn.close()


def test_upsert_does_not_clear_released_at(tmp_path: Path) -> None:
    conn = connect_rw(tmp_path / "ledger.sqlite")
    try:
        row = HarvestCandidate(
            source_id="github:keep/release",
            source="github",
            url="https://github.com/keep/release",
            title="keep",
            stargazers_count=11,
        )
        upsert_candidates(conn, [row], now=_NOW)
        mark_released(conn, ["github:keep/release"], now=_NOW)
        row.stargazers_count = 99
        upsert_candidates(conn, [row], now=_NOW + timedelta(hours=1))
        stored = conn.execute(
            "SELECT stargazers_count, released_at FROM candidates WHERE source_id = ?",
            ("github:keep/release",),
        ).fetchone()
        assert stored["stargazers_count"] == 99
        assert stored["released_at"] is not None
    finally:
        conn.close()


def test_cursor_walk_columns_alter_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "old-cursor.sqlite"
    raw = sqlite3.connect(db)
    try:
        raw.execute(
            """
            CREATE TABLE harvest_cursor (
                source TEXT PRIMARY KEY,
                next_window_start TEXT,
                harvest_until TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )
        raw.execute(
            """
            INSERT INTO harvest_cursor
            (source, next_window_start, harvest_until, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                "github",
                "2024-12-15T20:18:40Z",
                "2026-09-17T14:18:40Z",
                "2026-09-27T09:45:20Z",
            ),
        )
        raw.commit()
    finally:
        raw.close()

    conn = connect_rw(db)
    try:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(harvest_cursor)")}
        assert "walk_direction" in columns
        assert "high_water" in columns
        row = get_cursor(conn, "github")
        assert row is not None
        assert row["next_window_start"] == "2024-12-15T20:18:40Z"
        assert row["walk_direction"] is None
        assert row["high_water"] is None
        init_schema(conn)
        again = get_cursor(conn, "github")
        assert again is not None
        assert again["next_window_start"] == "2024-12-15T20:18:40Z"
        assert again["harvest_until"] == "2026-09-17T14:18:40Z"
    finally:
        conn.close()
