"""Tests for scripts/sqlite_restore.py (import via spec_from_file_location,
same pattern as tests/test_g6_prefilter_gold.py loading scripts/replay_prefilter.py).
"""

from __future__ import annotations

import importlib.util
import logging
import sqlite3
import sys
from pathlib import Path

import pytest

from bishop_shared.constants import SQLITE_DB_FILENAME, SQLITE_SNAPSHOT_DIRNAME

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SNAPSHOT_SCRIPT = _REPO_ROOT / "scripts" / "sqlite_snapshot.py"
_RESTORE_SCRIPT = _REPO_ROOT / "scripts" / "sqlite_restore.py"


def _load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


snap = _load_script("sqlite_snapshot", _SNAPSHOT_SCRIPT)
restore = _load_script("sqlite_restore", _RESTORE_SCRIPT)


def _make_db(path: Path, names: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
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


def _pre_restore_mains(db_dir: Path) -> list[Path]:
    return [
        p
        for p in db_dir.glob(f"{SQLITE_DB_FILENAME}.pre-restore-*")
        if not p.name.endswith("-wal") and not p.name.endswith("-shm")
    ]


def _run_main(monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> None:
    monkeypatch.setattr(sys, "argv", ["sqlite_restore.py", *argv])
    restore.main()


def test_restore_refuses_when_compose_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / SQLITE_DB_FILENAME
    _make_db(db_path, ["live"])
    snapshot = tmp_path / "snap.db"
    _make_db(snapshot, ["snap"])
    original = db_path.read_bytes()
    monkeypatch.setattr(restore, "compose_is_up", lambda: True)

    with pytest.raises(SystemExit) as exc:
        _run_main(monkeypatch, ["--db", str(db_path), "--file", str(snapshot)])

    assert exc.value.code == 2
    assert db_path.read_bytes() == original


def test_restore_proceeds_when_compose_unknown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    db_path = tmp_path / SQLITE_DB_FILENAME
    _make_db(db_path, ["live"])
    snapshot = tmp_path / "snap.db"
    _make_db(snapshot, ["from-snap"])
    monkeypatch.setattr(restore, "compose_is_up", lambda: None)

    with caplog.at_level(logging.WARNING):
        _run_main(monkeypatch, ["--db", str(db_path), "--file", str(snapshot)])

    assert _query_names(db_path) == ["from-snap"]
    assert "restore_compose_unknown" in caplog.text
    assert "uncertainty" in caplog.text.lower() or "unknown" in caplog.text.lower()


def test_restore_refuses_corrupt_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / SQLITE_DB_FILENAME
    _make_db(db_path, ["live"])
    original = db_path.read_bytes()
    snapshot = tmp_path / "bad.db"
    snapshot.write_bytes(b"not a database")
    monkeypatch.setattr(restore, "compose_is_up", lambda: False)

    with pytest.raises(SystemExit) as exc:
        _run_main(monkeypatch, ["--db", str(db_path), "--file", str(snapshot)])

    assert exc.value.code == 3
    assert db_path.read_bytes() == original


def test_restore_happy_path_replaces_and_preserves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / SQLITE_DB_FILENAME
    _make_db(db_path, ["original"])
    original = db_path.read_bytes()
    wal = Path(str(db_path) + "-wal")
    shm = Path(str(db_path) + "-shm")
    wal.write_bytes(b"stale-wal")
    shm.write_bytes(b"stale-shm")
    snapshot = tmp_path / "good.db"
    _make_db(snapshot, ["restored"])
    monkeypatch.setattr(restore, "compose_is_up", lambda: False)

    _run_main(monkeypatch, ["--db", str(db_path), "--file", str(snapshot)])

    assert _query_names(db_path) == ["restored"]
    assert not wal.exists()
    assert not shm.exists()
    preserved = _pre_restore_mains(tmp_path)
    assert len(preserved) == 1
    assert preserved[0].read_bytes() == original


def test_restore_dry_run_changes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / SQLITE_DB_FILENAME
    _make_db(db_path, ["live"])
    original = db_path.read_bytes()
    wal = Path(str(db_path) + "-wal")
    wal.write_bytes(b"wal")
    snapshot = tmp_path / "good.db"
    _make_db(snapshot, ["snap"])
    monkeypatch.setattr(restore, "compose_is_up", lambda: False)

    _run_main(monkeypatch, ["--db", str(db_path), "--file", str(snapshot), "--dry-run"])

    assert db_path.read_bytes() == original
    assert wal.exists()
    assert _pre_restore_mains(tmp_path) == []


def test_restore_latest_picks_newest_passing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / SQLITE_DB_FILENAME
    _make_db(db_path, ["live"])
    snapshot_dir = tmp_path / SQLITE_SNAPSHOT_DIRNAME
    snapshot_dir.mkdir()
    older = snapshot_dir / "bishop-20200101-120000.db"
    newer = snapshot_dir / "bishop-20260911-120000.db"
    _make_db(older, ["older"])
    _make_db(newer, ["newer-passing"])
    monkeypatch.setattr(restore, "compose_is_up", lambda: False)

    _run_main(monkeypatch, ["--db", str(db_path), "--latest", "--snapshot-dir", str(snapshot_dir)])

    assert _query_names(db_path) == ["newer-passing"]


def test_restore_exits_nonzero_if_installed_fails_integrity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / SQLITE_DB_FILENAME
    _make_db(db_path, ["live"])
    snapshot = tmp_path / "good.db"
    _make_db(snapshot, ["snap"])
    monkeypatch.setattr(restore, "compose_is_up", lambda: False)
    real_ok = restore.integrity_ok

    def fail_live_only(path: Path) -> tuple[bool, list[str]]:
        if path == db_path:
            return False, ["injected post-restore failure"]
        return real_ok(path)

    monkeypatch.setattr(restore, "integrity_ok", fail_live_only)

    with pytest.raises(SystemExit) as exc:
        _run_main(monkeypatch, ["--db", str(db_path), "--file", str(snapshot)])

    assert exc.value.code == 4
