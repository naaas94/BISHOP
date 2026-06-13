"""Unit tests for GET /entries/{source_id} (M7 T5)."""

from __future__ import annotations

import sqlite3
import sys
from datetime import UTC, datetime
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


@pytest.fixture
def entry_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_path = tmp_path / "bishop.db"
    _run_migrations(str(db_path))

    path_str = str(_QUERY_API_ROOT)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

    import sqlite3

    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        INSERT INTO entries (
            id, source_id, source, url, title, content_raw, ingested_at, domain,
            profile_version, pre_filter_batch_id, pre_filter_rationale,
            reading_status, flagged_for_review, processing_state
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "entry-1",
            "arxiv:2401.00001",
            "arxiv",
            "https://arxiv.org/abs/2401.00001",
            "Test Entry",
            "Full raw content body",
            datetime(2026, 6, 13, tzinfo=UTC).isoformat(),
            "professional",
            "v1",
            "batch-1",
            "relevant",
            "unread",
            0,
            "INDEXED",
        ),
    )
    conn.commit()
    conn.close()

    from app.routers import entries as entries_router  # noqa: WPS433
    import app.sqlite_reader as sqlite_reader_mod  # noqa: WPS433

    monkeypatch.setattr(sqlite_reader_mod, "SQLITE_DB_PATH", str(db_path))

    app = FastAPI()
    app.include_router(entries_router.router)
    with TestClient(app) as client:
        yield client


def test_entry_returns_full_record(entry_client: TestClient) -> None:
    response = entry_client.get("/entries/arxiv:2401.00001")
    assert response.status_code == 200
    body = response.json()
    assert body["source_id"] == "arxiv:2401.00001"
    assert body["content_raw"] == "Full raw content body"
    assert body["title"] == "Test Entry"


def test_entry_not_found_returns_404(entry_client: TestClient) -> None:
    response = entry_client.get("/entries/arxiv:missing")
    assert response.status_code == 404
    body = response.json()
    assert body["error"] == "not_found"
    assert body["source_id"] == "arxiv:missing"


def test_read_entry_opens_sqlite_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Falsifier: SQLite entry reader opens a writable connection."""
    db_path = tmp_path / "bishop.db"
    _run_migrations(str(db_path))

    path_str = str(_QUERY_API_ROOT)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

    from app import sqlite_reader  # noqa: WPS433

    monkeypatch.setattr(sqlite_reader, "SQLITE_DB_PATH", str(db_path))
    original_connect = sqlite3.connect
    seen_uri: list[str] = []

    def _spy_connect(database, *args, **kwargs):
        seen_uri.append(str(database))
        return original_connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite_reader.sqlite3, "connect", _spy_connect)
    sqlite_reader.read_entry("arxiv:missing")
    assert seen_uri
    assert "mode=ro" in seen_uri[0]
