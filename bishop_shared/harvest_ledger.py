"""Harvest sidecar SQLite — GitHub pool, not bishop.db.

Single writer: scraper. query-api opens ``mode=ro``. Upsert on ``source_id``.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from bishop_shared.constants import HARVEST_DB_PATH, SQLITE_BUSY_TIMEOUT_MS

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS candidates (
    source_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    abstract TEXT,
    github_id INTEGER,
    full_name TEXT,
    owner_login TEXT,
    owner_type TEXT,
    owner_id INTEGER,
    created_at TEXT,
    updated_at TEXT,
    pushed_at TEXT,
    is_fork INTEGER,
    archived INTEGER,
    disabled INTEGER,
    language TEXT,
    license_spdx TEXT,
    stargazers_count INTEGER,
    forks_count INTEGER,
    open_issues_count INTEGER,
    size_kb INTEGER,
    topics_json TEXT,
    homepage TEXT,
    default_branch TEXT,
    visibility TEXT,
    search_score REAL,
    harvest_query_id TEXT,
    extras_json TEXT,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    released_at TEXT
);

CREATE TABLE IF NOT EXISTS harvest_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    query TEXT NOT NULL,
    window_start TEXT,
    window_end TEXT,
    total_count INTEGER,
    incomplete_results INTEGER,
    pages_fetched INTEGER,
    items_upserted INTEGER,
    http_status INTEGER,
    ratelimit_remaining INTEGER,
    ratelimit_reset TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS harvest_cursor (
    source TEXT PRIMARY KEY,
    next_window_start TEXT,
    harvest_until TEXT,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_candidates_released_at ON candidates (released_at);
CREATE INDEX IF NOT EXISTS ix_candidates_pushed_at ON candidates (pushed_at);
"""


@dataclass
class HarvestCandidate:
    source_id: str
    source: str
    url: str
    title: str
    abstract: str | None = None
    github_id: int | None = None
    full_name: str | None = None
    owner_login: str | None = None
    owner_type: str | None = None
    owner_id: int | None = None
    created_at: str | None = None
    updated_at: str | None = None
    pushed_at: str | None = None
    is_fork: bool | None = None
    archived: bool | None = None
    disabled: bool | None = None
    language: str | None = None
    license_spdx: str | None = None
    stargazers_count: int | None = None
    forks_count: int | None = None
    open_issues_count: int | None = None
    size_kb: int | None = None
    topics_json: str | None = None
    homepage: str | None = None
    default_branch: str | None = None
    visibility: str | None = None
    search_score: float | None = None
    harvest_query_id: str | None = None
    extras_json: str | None = None


@dataclass(frozen=True)
class HarvestRun:
    source: str
    query: str
    window_start: str | None
    window_end: str | None
    total_count: int | None
    incomplete_results: bool
    pages_fetched: int
    items_upserted: int
    http_status: int | None
    ratelimit_remaining: int | None
    ratelimit_reset: str | None
    started_at: str
    finished_at: str


@dataclass(frozen=True)
class HarvestPoolStats:
    pool_size: int
    unreleased: int
    released_today: int


def harvest_db_path() -> Path:
    raw = os.environ.get("BISHOP_HARVEST_DB_PATH")
    if raw:
        return Path(raw)
    return Path(HARVEST_DB_PATH)


def connect_rw(path: Path | str | None = None) -> sqlite3.Connection:
    db = Path(path) if path is not None else harvest_db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
    init_schema(conn)
    return conn


def connect_ro(path: Path | str | None = None) -> sqlite3.Connection:
    db = Path(path) if path is not None else harvest_db_path()
    uri = f"file:{db.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def _as_int_flag(value: bool | None) -> int | None:
    if value is None:
        return None
    return 1 if value else 0


def upsert_candidates(
    conn: sqlite3.Connection,
    rows: list[HarvestCandidate],
    *,
    now: datetime,
) -> int:
    """Insert or refresh harvest fields. Never clears ``released_at``."""
    stamp = _iso(now)
    upserted = 0
    for row in rows:
        conn.execute(
            """
            INSERT INTO candidates (
                source_id, source, url, title, abstract,
                github_id, full_name, owner_login, owner_type, owner_id,
                created_at, updated_at, pushed_at,
                is_fork, archived, disabled, language, license_spdx,
                stargazers_count, forks_count, open_issues_count, size_kb,
                topics_json, homepage, default_branch, visibility, search_score,
                harvest_query_id, extras_json, first_seen_at, last_seen_at, released_at
            ) VALUES (
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, NULL
            )
            ON CONFLICT(source_id) DO UPDATE SET
                source=excluded.source,
                url=excluded.url,
                title=excluded.title,
                abstract=excluded.abstract,
                github_id=excluded.github_id,
                full_name=excluded.full_name,
                owner_login=excluded.owner_login,
                owner_type=excluded.owner_type,
                owner_id=excluded.owner_id,
                created_at=excluded.created_at,
                updated_at=excluded.updated_at,
                pushed_at=excluded.pushed_at,
                is_fork=excluded.is_fork,
                archived=excluded.archived,
                disabled=excluded.disabled,
                language=excluded.language,
                license_spdx=excluded.license_spdx,
                stargazers_count=excluded.stargazers_count,
                forks_count=excluded.forks_count,
                open_issues_count=excluded.open_issues_count,
                size_kb=excluded.size_kb,
                topics_json=excluded.topics_json,
                homepage=excluded.homepage,
                default_branch=excluded.default_branch,
                visibility=excluded.visibility,
                search_score=excluded.search_score,
                harvest_query_id=excluded.harvest_query_id,
                extras_json=excluded.extras_json,
                last_seen_at=excluded.last_seen_at
            """,
            (
                row.source_id,
                row.source,
                row.url,
                row.title,
                row.abstract,
                row.github_id,
                row.full_name,
                row.owner_login,
                row.owner_type,
                row.owner_id,
                row.created_at,
                row.updated_at,
                row.pushed_at,
                _as_int_flag(row.is_fork),
                _as_int_flag(row.archived),
                _as_int_flag(row.disabled),
                row.language,
                row.license_spdx,
                row.stargazers_count,
                row.forks_count,
                row.open_issues_count,
                row.size_kb,
                row.topics_json,
                row.homepage,
                row.default_branch,
                row.visibility,
                row.search_score,
                row.harvest_query_id,
                row.extras_json,
                stamp,
                stamp,
            ),
        )
        upserted += 1
    conn.commit()
    return upserted


def record_run(conn: sqlite3.Connection, run: HarvestRun) -> None:
    conn.execute(
        """
        INSERT INTO harvest_runs (
            source, query, window_start, window_end, total_count,
            incomplete_results, pages_fetched, items_upserted, http_status,
            ratelimit_remaining, ratelimit_reset, started_at, finished_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run.source,
            run.query,
            run.window_start,
            run.window_end,
            run.total_count,
            1 if run.incomplete_results else 0,
            run.pages_fetched,
            run.items_upserted,
            run.http_status,
            run.ratelimit_remaining,
            run.ratelimit_reset,
            run.started_at,
            run.finished_at,
        ),
    )
    conn.commit()


def get_cursor(conn: sqlite3.Connection, source: str) -> sqlite3.Row | None:
    cursor = conn.execute(
        "SELECT * FROM harvest_cursor WHERE source = ?",
        (source,),
    )
    return cursor.fetchone()


def set_cursor(
    conn: sqlite3.Connection,
    source: str,
    *,
    next_window_start: str,
    harvest_until: str,
    now: datetime,
) -> None:
    stamp = _iso(now)
    conn.execute(
        """
        INSERT INTO harvest_cursor (source, next_window_start, harvest_until, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(source) DO UPDATE SET
            next_window_start=excluded.next_window_start,
            harvest_until=excluded.harvest_until,
            updated_at=excluded.updated_at
        """,
        (source, next_window_start, harvest_until, stamp),
    )
    conn.commit()


def select_release_batch(
    conn: sqlite3.Connection,
    *,
    now: datetime,
    limit: int,
    freshness_hours: int = 48,
) -> list[sqlite3.Row]:
    """Unreleased rows: rolling freshness first, then older, both by pushed_at desc."""
    if limit <= 0:
        return []
    cutoff = _iso(now - timedelta(hours=freshness_hours))
    cursor = conn.execute(
        """
        SELECT * FROM candidates
        WHERE released_at IS NULL
        ORDER BY
            CASE WHEN pushed_at IS NOT NULL AND pushed_at >= ? THEN 0 ELSE 1 END,
            CASE WHEN pushed_at IS NULL THEN 1 ELSE 0 END,
            pushed_at DESC
        LIMIT ?
        """,
        (cutoff, limit),
    )
    return list(cursor.fetchall())


def mark_released(
    conn: sqlite3.Connection,
    source_ids: list[str],
    *,
    now: datetime,
) -> None:
    if not source_ids:
        return
    stamp = _iso(now)
    conn.executemany(
        """
        UPDATE candidates
        SET released_at = ?
        WHERE source_id = ? AND released_at IS NULL
        """,
        [(stamp, source_id) for source_id in source_ids],
    )
    conn.commit()


def count_released_today(conn: sqlite3.Connection, *, now: datetime) -> int:
    midnight = now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    row = conn.execute(
        "SELECT COUNT(*) FROM candidates WHERE released_at >= ?",
        (_iso(midnight),),
    ).fetchone()
    return int(row[0]) if row is not None else 0


def read_pool_stats(conn: sqlite3.Connection, *, now: datetime) -> HarvestPoolStats:
    pool_size = int(conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0])
    unreleased = int(
        conn.execute(
            "SELECT COUNT(*) FROM candidates WHERE released_at IS NULL"
        ).fetchone()[0]
    )
    return HarvestPoolStats(
        pool_size=pool_size,
        unreleased=unreleased,
        released_today=count_released_today(conn, now=now),
    )


def dumps_extras(payload: dict[str, Any]) -> str:
    return json.dumps(payload, default=str, separators=(",", ":"))


def _iso(value: datetime) -> str:
    utc = value.astimezone(UTC)
    return utc.isoformat().replace("+00:00", "Z")
