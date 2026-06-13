"""Unit tests for query-api G7 cold-start and health scaffold (M7 T1)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_REPO_ROOT = Path(__file__).resolve().parent.parent
_QUERY_API_ROOT = _REPO_ROOT / "services" / "query-api"


def _clear_app_modules() -> dict:
    saved = {
        name: module
        for name, module in sys.modules.items()
        if name == "app" or name.startswith("app.")
    }
    for name in saved:
        del sys.modules[name]
    return saved


def _restore_app_modules(saved: dict, inserted_path: str | None) -> None:
    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            del sys.modules[name]
    sys.modules.update(saved)
    if inserted_path is not None:
        sys.path.remove(inserted_path)


def _load_lifespan_module():
    saved = _clear_app_modules()
    path_str = str(_QUERY_API_ROOT)
    inserted = None
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = path_str

    try:
        import app.lifespan as lifespan_mod  # noqa: WPS433
    finally:
        _restore_app_modules(saved, inserted)

    return lifespan_mod


def _load_main_module():
    saved = _clear_app_modules()
    path_str = str(_QUERY_API_ROOT)
    inserted = None
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = path_str

    try:
        import app.main as main_mod  # noqa: WPS433
    finally:
        _restore_app_modules(saved, inserted)

    return main_mod


def _patch_lifespan_paths(
    lifespan_mod,
    tmp_path: Path,
    *,
    bm25_exists: bool = False,
    lance_exists: bool = False,
    duck_exists: bool = False,
) -> None:
    lancedb_dir = tmp_path / "lancedb"
    duckdb_dir = tmp_path / "duckdb"
    lancedb_dir.mkdir(parents=True, exist_ok=True)
    duckdb_dir.mkdir(parents=True, exist_ok=True)
    if bm25_exists:
        (tmp_path / "bm25" / "professional").mkdir(parents=True, exist_ok=True)
    if lance_exists:
        (lancedb_dir / "entries.lance").mkdir(parents=True, exist_ok=True)
    duck_path = duckdb_dir / "bishop.duckdb"
    if duck_exists:
        duck_path.write_bytes(b"\x00")

    lifespan_mod.bm25_domain_root = lambda domain: tmp_path / "bm25" / domain
    lifespan_mod.LANCEDB_DIR = str(lancedb_dir)
    lifespan_mod.DUCKDB_PATH = str(duck_path)


def test_cold_start_warns_on_missing_stores(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    lifespan_mod = _load_lifespan_module()
    _patch_lifespan_paths(lifespan_mod, tmp_path)

    probe_logger = logging.getLogger("test.query_api.cold_start")
    with caplog.at_level(logging.WARNING, logger=probe_logger.name):
        state = lifespan_mod.cold_start_init(probe_logger)

    assert state.bm25_ready is False
    assert state.lancedb_ready is False
    assert state.duckdb_ready is False

    warn_records = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warn_records) == 3
    events = {record.event for record in warn_records}  # type: ignore[attr-defined]
    assert events == {"store_cold_start_empty"}
    channels = {record.channel for record in warn_records}  # type: ignore[attr-defined]
    assert channels == {"bm25_main", "dense", "metadata"}


def test_cold_start_no_warn_when_stores_present(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Falsifier: cold-start emits false-positive WARN when stores exist."""
    lifespan_mod = _load_lifespan_module()
    _patch_lifespan_paths(
        lifespan_mod,
        tmp_path,
        bm25_exists=True,
        lance_exists=True,
        duck_exists=True,
    )

    probe_logger = logging.getLogger("test.query_api.cold_start_present")
    with caplog.at_level(logging.WARNING, logger=probe_logger.name):
        state = lifespan_mod.cold_start_init(probe_logger)

    assert state.bm25_ready is True
    assert state.lancedb_ready is True
    assert state.duckdb_ready is True
    assert not any(
        getattr(record, "event", None) == "store_cold_start_empty"
        for record in caplog.records
    )


def test_health_returns_200_ok(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    saved = _clear_app_modules()
    path_str = str(_QUERY_API_ROOT)
    inserted = None
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = path_str

    try:
        import app.lifespan as lifespan_mod  # noqa: WPS433
        import app.main as main_mod  # noqa: WPS433

        _patch_lifespan_paths(lifespan_mod, tmp_path)
        monkeypatch.setattr(main_mod, "cold_start_init", lifespan_mod.cold_start_init)

        with TestClient(main_mod.app) as client:
            response = client.get("/health")
    finally:
        _restore_app_modules(saved, inserted)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_startup_lifespan_does_not_raise_on_empty_stores(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Falsifier: missing BM25/LanceDB/DuckDB paths crash startup instead of WARN."""
    saved = _clear_app_modules()
    path_str = str(_QUERY_API_ROOT)
    inserted = None
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = path_str

    try:
        import app.lifespan as lifespan_mod  # noqa: WPS433
        import app.main as main_mod  # noqa: WPS433

        _patch_lifespan_paths(lifespan_mod, tmp_path)
        monkeypatch.setattr(main_mod, "cold_start_init", lifespan_mod.cold_start_init)

        with TestClient(main_mod.app) as client:
            response = client.get("/health")
    finally:
        _restore_app_modules(saved, inserted)

    assert response.status_code == 200
