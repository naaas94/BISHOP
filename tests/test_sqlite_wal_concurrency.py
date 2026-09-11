"""OPEN-018: genuine multi-process WAL contention against one on-disk file.

Compose runs writers (state-worker) and a mode=ro reader (query-api) as
separate OS processes. Existing pool tests interleave aiosqlite calls on one
asyncio loop and never overlap two sqlite3 C calls, so they cannot exercise
OS-level lock scheduling. This harness does: N writer processes plus one
reader process, each with its own connection, racing the same WAL file.

This is not a Windows-bind-mount test. Bind-mount page tearing is an
environment property pytest cannot fabricate. Passing here proves the
application's lock-handling logic under real concurrent file access on
whatever filesystem the test happens to run on — not that a Docker bind
mount is safe.
"""

from __future__ import annotations

import ctypes
import os
import sqlite3
import sys
import time
import traceback
from multiprocessing import Queue, get_context
from multiprocessing.synchronize import Event as MpEvent
from pathlib import Path
from queue import Empty
from typing import Any

import pytest

from bishop_shared.constants import SQLITE_BUSY_TIMEOUT_MS

# 5 writers match the production aiosqlite pool size. 40 commits each ⇒ 200
# write transactions, enough to contend, short enough to stay under ~30s.
_N_WRITERS = 5
_ITERS_PER_WRITER = 40
_MIN_READER_SUCCESSES = 20
# Hard bound implemented here — pyproject.toml has no pytest-timeout plugin.
_HARNESS_JOIN_TIMEOUT_S = 45.0
_WALL_CLOCK_CEILING_S = 60.0
_MAX_RETRIES_PER_TXN = 12
_RETRY_BACKOFF_S = 0.01
_REAP_JOIN_S = 2.0
_QUEUE_DRAIN_S = 2.0
_SEED_DISCOVERED = 8

_MANIFEST_INSERT = """
INSERT INTO manifest (
    source_id, source, url, title, discovered_at, domain, processing_state
) VALUES (?, ?, ?, ?, ?, ?, ?)
"""
_ENTRIES_INSERT = """
INSERT INTO entries (
    id, source_id, source, url, title, content_raw, ingested_at,
    domain, profile_version, pre_filter_batch_id, pre_filter_rationale,
    reading_status, flagged_for_review, processing_state
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def _pid_is_alive(pid: int) -> bool:
    """Portable liveness check for a PID we ourselves spawned."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        process_query_limited_information = 0x1000
        still_active = 259
        handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return int(exit_code.value) == still_active
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _reap(procs: list[Any]) -> None:
    """Terminate, then kill, every process that is still alive."""
    for proc in procs:
        if proc.is_alive():
            proc.terminate()
    for proc in procs:
        proc.join(timeout=_REAP_JOIN_S)
        if proc.is_alive():
            proc.kill()
            proc.join(timeout=_REAP_JOIN_S)


def _writer_main(
    db_path: str,
    writer_id: int,
    n_iters: int,
    begin_sql: str,
    busy_timeout_ms: int,
    result_queue: Queue[dict[str, Any]],
) -> None:
    """OS-process writer: BEGIN, read-then-write, COMMIT. Windows-spawn safe."""
    payload: dict[str, Any] = {
        "role": "writer",
        "writer_id": writer_id,
        "successes": 0,
        "retries": 0,
        "error": None,
    }
    conn: sqlite3.Connection | None = None
    try:
        # isolation_level=None: we issue BEGIN ourselves (production does too).
        conn = sqlite3.connect(db_path)
        conn.isolation_level = None
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(f"PRAGMA busy_timeout = {busy_timeout_ms}")
        for i in range(n_iters):
            source_id = f"wal:{writer_id}:{i}"
            attempt = 0
            while True:
                try:
                    conn.execute(begin_sql)
                    # Claim-shaped read-then-write: SELECT before DML so a
                    # deferred BEGIN holds a shared lock and must upgrade.
                    conn.execute(
                        "SELECT * FROM manifest WHERE processing_state = ?",
                        ("DISCOVERED",),
                    ).fetchall()
                    conn.execute("SELECT COUNT(*) FROM entries").fetchone()
                    conn.execute(
                        _MANIFEST_INSERT,
                        (
                            source_id,
                            "arxiv",
                            f"https://arxiv.org/abs/{source_id}",
                            f"wal {source_id}",
                            "2026-09-11T00:00:00+00:00",
                            "professional",
                            "DISCOVERED",
                        ),
                    )
                    conn.execute(
                        _ENTRIES_INSERT,
                        (
                            f"e-{source_id}",
                            source_id,
                            "arxiv",
                            f"https://arxiv.org/abs/{source_id}",
                            f"wal {source_id}",
                            "body",
                            "2026-09-11T00:00:00+00:00",
                            "professional",
                            "v1",
                            "batch-wal",
                            "relevant",
                            "unread",
                            0,
                            "INDEXED",
                        ),
                    )
                    conn.execute(
                        "INSERT OR REPLACE INTO scraper_state (source, updated_at) "
                        "VALUES (?, ?)",
                        (f"wal-writer-{writer_id}", "2026-09-11T00:00:00+00:00"),
                    )
                    conn.execute("COMMIT")
                    payload["successes"] += 1
                    break
                except sqlite3.OperationalError as exc:
                    try:
                        conn.execute("ROLLBACK")
                    except sqlite3.Error:
                        pass
                    msg = str(exc).lower()
                    transient = "locked" in msg or "busy" in msg
                    if not transient:
                        raise
                    attempt += 1
                    payload["retries"] += 1
                    if attempt > _MAX_RETRIES_PER_TXN:
                        raise
                    time.sleep(_RETRY_BACKOFF_S * attempt)
    except Exception:
        payload["error"] = traceback.format_exc()
    finally:
        if conn is not None:
            try:
                conn.close()
            except sqlite3.Error:
                pass
        result_queue.put(payload)


def _reader_main(
    db_path: str,
    stop_event: MpEvent,
    result_queue: Queue[dict[str, Any]],
) -> None:
    """OS-process mode=ro reader, mirroring query-api sqlite_reader.py."""
    payload: dict[str, Any] = {
        "role": "reader",
        "reads": 0,
        "errors": 0,
        "error": None,
    }
    uri = f"file:{Path(db_path).as_posix()}?mode=ro"
    try:
        # Connect-per-query matches read_entry / filter_source_ids.
        while not stop_event.is_set():
            conn = sqlite3.connect(uri, uri=True)
            try:
                conn.execute(
                    "SELECT * FROM manifest WHERE processing_state = ?",
                    ("DISCOVERED",),
                ).fetchall()
                conn.execute("SELECT COUNT(*) FROM entries").fetchone()
                payload["reads"] += 1
            except sqlite3.OperationalError:
                payload["errors"] += 1
            finally:
                conn.close()
    except Exception:
        payload["error"] = traceback.format_exc()
    finally:
        result_queue.put(payload)


def _run_migrations(db_path: Path) -> None:
    repo = Path(__file__).resolve().parent.parent
    state_worker = repo / "services" / "state-worker"
    for extra in (state_worker, repo):
        text = str(extra)
        if text not in sys.path:
            sys.path.insert(0, text)
    from app.db import run_migrations

    run_migrations(str(db_path))


def _seed_discovered(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
        for i in range(_SEED_DISCOVERED):
            source_id = f"seed:{i}"
            conn.execute(
                _MANIFEST_INSERT,
                (
                    source_id,
                    "arxiv",
                    f"https://arxiv.org/abs/{source_id}",
                    f"seed {source_id}",
                    "2026-09-11T00:00:00+00:00",
                    "professional",
                    "DISCOVERED",
                ),
            )
        conn.commit()
    finally:
        conn.close()


def _integrity_ok(db_path: Path) -> list[str]:
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute("PRAGMA integrity_check").fetchall()
    finally:
        conn.close()
    return [line for row in rows for line in str(row[0]).splitlines() if line]


def _count(db_path: Path, sql: str) -> int:
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(sql).fetchone()
    finally:
        conn.close()
    assert row is not None
    return int(row[0])


def _run_harness(db_path: Path, begin_sql: str) -> dict[str, Any]:
    """Spawn reader + N writers; join with a hard timeout; always reap."""
    ctx = get_context("spawn")
    result_queue: Queue[dict[str, Any]] = ctx.Queue()
    stop_event = ctx.Event()
    procs: list[Any] = []
    pids: list[int] = []
    started = time.monotonic()
    timed_out = False
    try:
        reader = ctx.Process(
            target=_reader_main,
            args=(str(db_path), stop_event, result_queue),
            name="wal-reader",
        )
        reader.start()
        procs.append(reader)
        if reader.pid is not None:
            pids.append(reader.pid)

        writers = []
        for writer_id in range(_N_WRITERS):
            proc = ctx.Process(
                target=_writer_main,
                args=(
                    str(db_path),
                    writer_id,
                    _ITERS_PER_WRITER,
                    begin_sql,
                    SQLITE_BUSY_TIMEOUT_MS,
                    result_queue,
                ),
                name=f"wal-writer-{writer_id}",
            )
            proc.start()
            procs.append(proc)
            writers.append(proc)
            if proc.pid is not None:
                pids.append(proc.pid)

        deadline = started + _HARNESS_JOIN_TIMEOUT_S
        for proc in writers:
            remaining = deadline - time.monotonic()
            proc.join(timeout=max(0.05, remaining))
            if proc.is_alive():
                timed_out = True

        stop_event.set()
        remaining = deadline - time.monotonic()
        reader.join(timeout=max(0.05, remaining))
        if reader.is_alive():
            timed_out = True

        payloads: list[dict[str, Any]] = []
        drain_deadline = time.monotonic() + _QUEUE_DRAIN_S
        expected = _N_WRITERS + 1
        while len(payloads) < expected and time.monotonic() < drain_deadline:
            try:
                payloads.append(result_queue.get(timeout=0.1))
            except Empty:
                continue

        elapsed = time.monotonic() - started
        leftover_alive = [pid for pid in pids if _pid_is_alive(pid)]
        return {
            "begin_sql": begin_sql,
            "elapsed_s": elapsed,
            "timed_out": timed_out,
            "payloads": payloads,
            "pids": pids,
            "leftover_alive_before_reap": leftover_alive,
        }
    finally:
        stop_event.set()
        _reap(procs)
        leftover_after = [pid for pid in pids if _pid_is_alive(pid)]
        if leftover_after:
            raise RuntimeError(f"zombie PIDs still alive after reap: {leftover_after}")


def _assert_dead(pids: list[int]) -> None:
    leftover = [pid for pid in pids if _pid_is_alive(pid)]
    assert leftover == [], f"zombie PIDs still alive after reap: {leftover}"


def _split_payloads(
    payloads: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    writers = [p for p in payloads if p.get("role") == "writer"]
    readers = [p for p in payloads if p.get("role") == "reader"]
    return writers, readers


def test_wal_multiprocess_begin_immediate_and_ro_reader(tmp_path: Path) -> None:
    """N writer processes + mode=ro reader; BEGIN IMMEDIATE; integrity holds."""
    db_path = tmp_path / "bishop.db"
    _run_migrations(db_path)
    _seed_discovered(db_path)

    result = _run_harness(db_path, "BEGIN IMMEDIATE")
    try:
        assert result["timed_out"] is False, (
            f"harness hit {_HARNESS_JOIN_TIMEOUT_S}s join timeout — "
            "treat as deadlock, not slow contention"
        )
        assert result["elapsed_s"] < _WALL_CLOCK_CEILING_S, (
            f"wall-clock {result['elapsed_s']:.2f}s exceeded "
            f"{_WALL_CLOCK_CEILING_S}s ceiling"
        )

        writers, readers = _split_payloads(result["payloads"])
        assert len(writers) == _N_WRITERS, (
            f"missing writer results: got {len(writers)} of {_N_WRITERS} "
            f"payloads={result['payloads']!r}"
        )
        assert len(readers) == 1, f"missing reader result: {result['payloads']!r}"

        for writer in writers:
            assert writer["error"] is None, (
                f"writer {writer['writer_id']} unrecoverable:\n{writer['error']}"
            )
            assert writer["successes"] == _ITERS_PER_WRITER, (
                f"writer {writer['writer_id']} starved: "
                f"{writer['successes']} / {_ITERS_PER_WRITER} "
                f"(retries={writer['retries']})"
            )

        reader = readers[0]
        assert reader["error"] is None, f"reader died:\n{reader['error']}"
        assert reader["reads"] >= _MIN_READER_SUCCESSES, (
            f"reader completed only {reader['reads']} successful loops "
            f"(errors={reader['errors']}); was it blocked out?"
        )

        assert _integrity_ok(db_path) == ["ok"]

        expected_entries = _N_WRITERS * _ITERS_PER_WRITER
        entry_count = _count(db_path, "SELECT COUNT(*) FROM entries")
        distinct_entries = _count(db_path, "SELECT COUNT(DISTINCT source_id) FROM entries")
        assert entry_count == expected_entries, (
            f"lost or extra writes: entries={entry_count} expected={expected_entries}"
        )
        assert distinct_entries == expected_entries, (
            f"duplicate source_id commits: distinct={distinct_entries} total={entry_count}"
        )
        wal_manifest = _count(
            db_path,
            "SELECT COUNT(*) FROM manifest WHERE source_id LIKE 'wal:%'",
        )
        assert wal_manifest == expected_entries, (
            f"manifest wal: rows={wal_manifest} expected={expected_entries}"
        )
    finally:
        _assert_dead(result["pids"])


@pytest.mark.skip(
    reason=(
        "diagnostic, not a regression gate: deferred BEGIN under the production "
        "busy_timeout (5000ms) plus a client retry loop did not produce "
        "unrecoverable failures or integrity damage. It DID show more "
        "sqlite3.OperationalError retries than BEGIN IMMEDIATE (12-21 vs 0 "
        "across four consecutive local runs) — consistent with lock-upgrade "
        "bypassing busy_timeout — but the retry count is schedule-dependent "
        "and is not a stable CI falsifier. Re-run by removing this skip."
    )
)
def test_wal_multiprocess_deferred_begin_diagnostic(tmp_path: Path) -> None:
    """Same harness with deferred BEGIN — exploratory, not a CI gate.

    Decision log: deferred BEGIN bypasses busy_timeout on lock upgrade.
    Observed locally (2026-09-11, win32, this host): 12-21 client retries
    vs 0 for BEGIN IMMEDIATE, all writers still completed, integrity ok.
    """
    db_path = tmp_path / "bishop.db"
    _run_migrations(db_path)
    _seed_discovered(db_path)

    result = _run_harness(db_path, "BEGIN")
    try:
        writers, readers = _split_payloads(result["payloads"])
        retries = sum(int(w.get("retries") or 0) for w in writers)
        assert result["timed_out"] is False
        assert len(writers) == _N_WRITERS
        assert len(readers) == 1
        assert retries >= 0
    finally:
        _assert_dead(result["pids"])
