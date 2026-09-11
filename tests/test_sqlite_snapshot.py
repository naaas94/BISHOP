"""Tests for scripts/sqlite_snapshot.py (import via spec_from_file_location,
same pattern as tests/test_g6_prefilter_gold.py loading scripts/replay_prefilter.py).
"""

from __future__ import annotations

import importlib.util
import logging
import os
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from bishop_shared.constants import (
    SQLITE_DB_FILENAME,
    SQLITE_SNAPSHOT_DIRNAME,
    SQLITE_SNAPSHOT_PREFIX,
    SQLITE_SNAPSHOT_SUFFIX,
    SQLITE_SNAPSHOT_TIMESTAMP_FORMAT,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SNAPSHOT_SCRIPT = _REPO_ROOT / "scripts" / "sqlite_snapshot.py"


def _load_snapshot_module():
    spec = importlib.util.spec_from_file_location("sqlite_snapshot", _SNAPSHOT_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


snap = _load_snapshot_module()


def _make_db(path: Path, names: list[str], *, wal: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    if wal:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA wal_autocheckpoint=0")
    conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
    conn.executemany("INSERT INTO items (name) VALUES (?)", [(n,) for n in names])
    conn.commit()
    conn.close()


def _query_names(path: Path) -> list[str]:
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        rows = conn.execute("SELECT name FROM items ORDER BY id").fetchall()
    finally:
        conn.close()
    return [row[0] for row in rows]


def _tmp_litter(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return [
        p
        for p in directory.iterdir()
        if p.name.startswith(".bishop-snapshot.") or p.suffix == ".tmp"
    ]


def test_take_snapshot_writes_named_file_with_matching_rows(tmp_path: Path) -> None:
    db_path = tmp_path / SQLITE_DB_FILENAME
    _make_db(db_path, ["alpha", "beta"])
    now = datetime(2026, 9, 11, 12, 0, 0)
    snapshot_dir = tmp_path / SQLITE_SNAPSHOT_DIRNAME

    written = snap.take_snapshot(db_path, snapshot_dir, now=now)

    expected = snapshot_dir / (
        f"{SQLITE_SNAPSHOT_PREFIX}"
        f"{now.strftime(SQLITE_SNAPSHOT_TIMESTAMP_FORMAT)}"
        f"{SQLITE_SNAPSHOT_SUFFIX}"
    )
    assert written == expected
    assert expected.is_file()
    assert _query_names(expected) == ["alpha", "beta"]
    assert _tmp_litter(snapshot_dir) == []


def test_take_snapshot_includes_wal_rows_without_checkpoint(tmp_path: Path) -> None:
    db_path = tmp_path / SQLITE_DB_FILENAME
    # Last-close on Windows checkpoints and removes -wal; keep the writer open
    # so committed-but-uncheckpointed pages stay in the WAL (the shutil.copy case).
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA wal_autocheckpoint=0")
    conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO items (name) VALUES ('from-wal')")
    conn.commit()
    wal_path = Path(str(db_path) + "-wal")
    try:
        assert wal_path.is_file()
        assert wal_path.stat().st_size > 0
        snapshot_dir = tmp_path / SQLITE_SNAPSHOT_DIRNAME
        written = snap.take_snapshot(
            db_path, snapshot_dir, now=datetime(2026, 9, 11, 12, 1, 0)
        )
        assert written is not None
        assert _query_names(written) == ["from-wal"]
        assert _tmp_litter(snapshot_dir) == []
    finally:
        conn.close()


def test_take_snapshot_corrupt_source_creates_no_snapshot(tmp_path: Path) -> None:
    db_path = tmp_path / SQLITE_DB_FILENAME
    db_path.write_bytes(b"this is not a sqlite database" * 8)
    snapshot_dir = tmp_path / SQLITE_SNAPSHOT_DIRNAME

    result = snap.take_snapshot(db_path, snapshot_dir)

    assert result is None
    assert not snapshot_dir.exists() or list(snapshot_dir.glob("bishop-*.db")) == []
    assert _tmp_litter(snapshot_dir) == []


def test_take_snapshot_failed_integrity_deletes_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / SQLITE_DB_FILENAME
    _make_db(db_path, ["keep"])
    snapshot_dir = tmp_path / SQLITE_SNAPSHOT_DIRNAME
    real_ok = snap.integrity_ok

    def fail_temp_only(path: Path) -> tuple[bool, list[str]]:
        if path.name.startswith(".bishop-snapshot.") or path.suffix == ".tmp":
            return False, ["injected integrity failure"]
        return real_ok(path)

    monkeypatch.setattr(snap, "integrity_ok", fail_temp_only)

    result = snap.take_snapshot(db_path, snapshot_dir)

    assert result is None
    assert list(snapshot_dir.glob("bishop-*.db")) == []
    assert _tmp_litter(snapshot_dir) == []


def test_take_snapshot_missing_or_empty_source_returns_none(tmp_path: Path) -> None:
    snapshot_dir = tmp_path / SQLITE_SNAPSHOT_DIRNAME
    missing = snap.take_snapshot(tmp_path / "nope.db", snapshot_dir)
    assert missing is None

    empty = tmp_path / SQLITE_DB_FILENAME
    empty.write_bytes(b"")
    result = snap.take_snapshot(empty, snapshot_dir)
    assert result is None
    assert not snapshot_dir.exists() or list(snapshot_dir.glob("bishop-*.db")) == []


def test_prune_snapshots_deletes_old_keeps_fresh_and_mtime_fallback(tmp_path: Path) -> None:
    snapshot_dir = tmp_path / SQLITE_SNAPSHOT_DIRNAME
    snapshot_dir.mkdir()
    now = datetime(2026, 9, 11, 12, 0, 0)

    old = snapshot_dir / "bishop-20200101-000000.db"
    old.write_bytes(b"old")
    fresh = snapshot_dir / f"bishop-{now.strftime(SQLITE_SNAPSHOT_TIMESTAMP_FORMAT)}.db"
    fresh.write_bytes(b"fresh")

    unparseable_old = snapshot_dir / "bishop-not-a-timestamp.db"
    unparseable_old.write_bytes(b"stale-unparsed")
    old_mtime = (now - timedelta(hours=48)).timestamp()
    os.utime(unparseable_old, (old_mtime, old_mtime))

    unparseable_fresh = snapshot_dir / "bishop-also-unparseable.db"
    unparseable_fresh.write_bytes(b"fresh-unparsed")
    os.utime(unparseable_fresh, (now.timestamp(), now.timestamp()))

    deleted = snap.prune_snapshots(snapshot_dir, 24, now=now)

    assert old in deleted
    assert unparseable_old in deleted
    assert not old.exists()
    assert not unparseable_old.exists()
    assert fresh.exists()
    assert unparseable_fresh.exists()


def test_prune_snapshots_does_not_delete_live_or_unrelated(tmp_path: Path) -> None:
    snapshot_dir = tmp_path / SQLITE_SNAPSHOT_DIRNAME
    snapshot_dir.mkdir()
    live = snapshot_dir / SQLITE_DB_FILENAME
    wal = snapshot_dir / f"{SQLITE_DB_FILENAME}-wal"
    shm = snapshot_dir / f"{SQLITE_DB_FILENAME}-shm"
    notes = snapshot_dir / "readme.txt"
    old_snap = snapshot_dir / "bishop-20200101-000000.db"
    for path, payload in (
        (live, b"live"),
        (wal, b"wal"),
        (shm, b"shm"),
        (notes, b"notes"),
        (old_snap, b"old"),
    ):
        path.write_bytes(payload)

    snap.prune_snapshots(snapshot_dir, 24, now=datetime(2026, 9, 11, 12, 0, 0))

    assert live.read_bytes() == b"live"
    assert wal.read_bytes() == b"wal"
    assert shm.read_bytes() == b"shm"
    assert notes.read_bytes() == b"notes"
    assert not old_snap.exists()


def test_newest_passing_snapshot_skips_corrupt_newer(tmp_path: Path) -> None:
    snapshot_dir = tmp_path / SQLITE_SNAPSHOT_DIRNAME
    snapshot_dir.mkdir()
    older = snapshot_dir / "bishop-20200101-120000.db"
    _make_db(older, ["older-ok"])
    newer = snapshot_dir / "bishop-20260911-120000.db"
    newer.write_bytes(b"corrupt newer snapshot")

    chosen = snap.newest_passing_snapshot(snapshot_dir)

    assert chosen == older
    assert _query_names(chosen) == ["older-ok"]


def test_resolve_db_path_honors_db_then_env_then_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    explicit = tmp_path / "custom.db"
    monkeypatch.setenv("BISHOP_DATA_ROOT", str(tmp_path / "from-env"))
    assert snap.resolve_db_path(str(explicit)) == explicit

    monkeypatch.delenv("BISHOP_DATA_ROOT", raising=False)
    monkeypatch.setenv("BISHOP_DATA_ROOT", str(tmp_path / "from-env"))
    assert snap.resolve_db_path(None) == tmp_path / "from-env" / "sqlite" / SQLITE_DB_FILENAME

    secret = "sk-ant-fake-do-not-leak-other-key"
    monkeypatch.delenv("BISHOP_DATA_ROOT", raising=False)
    monkeypatch.setattr(snap, "ROOT", tmp_path)
    (tmp_path / ".env").write_text(
        f"BISHOP_DATA_ROOT={tmp_path / 'from-dotenv'}\nANTHROPIC_API_KEY={secret}\n",
        encoding="utf-8",
    )
    with caplog.at_level(logging.DEBUG):
        resolved = snap.resolve_db_path(None)
    assert resolved == tmp_path / "from-dotenv" / "sqlite" / SQLITE_DB_FILENAME
    assert secret not in str(resolved)
    assert secret not in caplog.text
    captured = capsys.readouterr()
    assert secret not in captured.out
    assert secret not in captured.err
