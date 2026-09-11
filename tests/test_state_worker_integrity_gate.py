"""Startup SQLite integrity gate (check_integrity / enforce_integrity / lifespan)."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_STATE_WORKER_ROOT = _REPO_ROOT / "services" / "state-worker"

for path in (_STATE_WORKER_ROOT, _REPO_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from app.db import (  # noqa: E402
    SqliteIntegrityError,
    check_integrity,
    enforce_integrity,
    run_migrations,
)
from app.main import app, lifespan  # noqa: E402


def _good_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "bishop.db"
    run_migrations(str(db_path))
    return db_path


def _tear_pages(db_path: Path) -> None:
    """Keep a valid SQLite header but overwrite pages — mirrors the live incident."""
    with db_path.open("r+b") as fh:
        fh.seek(100)
        fh.write(b"\xde\xad\xbe\xef" * 1024)


def _write_non_sqlite_header(db_path: Path) -> None:
    raw = db_path.read_bytes()
    db_path.write_bytes(b"NOT-A-SQLITE-FILE"[:16].ljust(16, b"\x00") + raw[16:])


def _corrupt_db(tmp_path: Path) -> Path:
    """Return a path whose check_integrity result is not ['ok']. Verified, not assumed."""
    db_path = _good_db(tmp_path)
    _tear_pages(db_path)
    torn = check_integrity(str(db_path))
    if torn != ["ok"]:
        return db_path
    _write_non_sqlite_header(db_path)
    garbage = check_integrity(str(db_path))
    assert garbage != ["ok"], (
        "corrupt fixture failed to produce a failing integrity check "
        f"(torn={torn!r}, garbage={garbage!r})"
    )
    return db_path


def test_check_integrity_ok_on_migrated_db(tmp_path: Path) -> None:
    db_path = _good_db(tmp_path)
    assert check_integrity(str(db_path)) == ["ok"]


def test_check_integrity_missing_file_does_not_create(tmp_path: Path) -> None:
    db_path = tmp_path / "does-not-exist.db"
    assert check_integrity(str(db_path)) == ["ok"]
    assert not db_path.exists()


def test_check_integrity_zero_byte_file(tmp_path: Path) -> None:
    db_path = tmp_path / "empty.db"
    db_path.write_bytes(b"")
    assert check_integrity(str(db_path)) == ["ok"]
    assert db_path.stat().st_size == 0


def test_check_integrity_torn_pages_fails(tmp_path: Path) -> None:
    db_path = _good_db(tmp_path)
    _tear_pages(db_path)
    torn = check_integrity(str(db_path))
    # Proof the fixture is real: at least this mutation or the header fallback fails.
    if torn == ["ok"]:
        _write_non_sqlite_header(db_path)
        torn = check_integrity(str(db_path))
    assert torn != ["ok"]


def test_check_integrity_non_sqlite_header_unreadable(tmp_path: Path) -> None:
    db_path = _good_db(tmp_path)
    _write_non_sqlite_header(db_path)
    result = check_integrity(str(db_path))
    assert result != ["ok"]
    assert result[0].startswith("unreadable:")


def test_enforce_integrity_raises_on_corrupt_not_on_good(tmp_path: Path) -> None:
    good = _good_db(tmp_path / "good")
    enforce_integrity(str(good))

    corrupt = _corrupt_db(tmp_path / "bad")
    with pytest.raises(SqliteIntegrityError):
        enforce_integrity(str(corrupt))


def test_enforce_integrity_logs_hint_when_snapshots_absent(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    corrupt = _corrupt_db(tmp_path)
    # Alembic fileConfig(disable_existing_loggers=True) disables app.db after
    # run_migrations in this fixture. Production calls enforce_integrity first.
    db_logger = logging.getLogger("app.db")
    db_logger.disabled = False
    db_logger.addHandler(caplog.handler)
    caplog.set_level(logging.ERROR, logger="app.db")
    try:
        with pytest.raises(SqliteIntegrityError):
            enforce_integrity(str(corrupt))
        assert "python scripts/sqlite_restore.py --latest" in caplog.text
        assert "missing" in caplog.text.lower()
        assert any(
            getattr(record, "event", None) == "sqlite_integrity_failed"
            for record in caplog.records
        )
    finally:
        db_logger.removeHandler(caplog.handler)


def test_integrity_pragma_quick_check_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BISHOP_SQLITE_INTEGRITY_PRAGMA", "quick_check")
    db_path = _good_db(tmp_path)
    assert check_integrity(str(db_path)) == ["ok"]


def test_integrity_pragma_bogus_value_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BISHOP_SQLITE_INTEGRITY_PRAGMA", "nope")
    db_path = _good_db(tmp_path)
    with pytest.raises(ValueError, match="BISHOP_SQLITE_INTEGRITY_PRAGMA"):
        check_integrity(str(db_path))


def test_lifespan_aborts_on_corrupt_db_without_migrating(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corrupt = _corrupt_db(tmp_path)
    monkeypatch.setattr("app.db.SQLITE_DB_PATH", str(corrupt))
    migrations_called = {"value": False}

    def spy_run_migrations(*_args: object, **_kwargs: object) -> None:
        migrations_called["value"] = True

    monkeypatch.setattr("app.main.run_migrations", spy_run_migrations)

    async def _enter() -> None:
        async with lifespan(app):
            pass

    with pytest.raises(SqliteIntegrityError):
        asyncio.run(_enter())
    assert migrations_called["value"] is False
