"""M7 integration tests — seeded INDEXED stores + query-api search (T8)."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import httpx
import pytest
from fastapi.testclient import TestClient

from bishop_shared.indexing_config import EMBEDDING_DIM

_REPO_ROOT = Path(__file__).resolve().parent.parent
_QUERY_API_ROOT = _REPO_ROOT / "services" / "query-api"
_M6_INTEGRATION_PATH = _REPO_ROOT / "tests" / "test_m6_integration.py"
_M6_MODULE_NAME = "bishop_test_m6_integration"
_EXPECTED_SOURCE_IDS = ("arxiv:2506.01001", "arxiv:2506.01002")
_STATE_WORKER_ROOT = _REPO_ROOT / "services" / "state-worker"


def _load_m6_integration_module() -> ModuleType:
    cached = sys.modules.get(_M6_MODULE_NAME)
    if cached is not None and hasattr(cached, "_patch_db_path"):
        return cached

    sys.modules.pop(_M6_MODULE_NAME, None)
    _clear_app_modules()

    service_roots = {
        str(_REPO_ROOT / "services" / name)
        for name in (
            "state-worker",
            "vector-writer",
            "query-api",
            "ui",
            "scraper",
            "content-scraper",
            "pre-filter-worker",
            "batch-poller",
            "enrichment-batcher",
        )
    }
    sys.path = [
        p for p in sys.path if p not in service_roots
    ]
    for path_str in (str(_STATE_WORKER_ROOT), str(_REPO_ROOT)):
        sys.path.insert(0, path_str)

    spec = importlib.util.spec_from_file_location(_M6_MODULE_NAME, _M6_INTEGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[_M6_MODULE_NAME] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(_M6_MODULE_NAME, None)
        raise
    return module


def _clear_app_modules() -> dict[str, ModuleType]:
    saved = {
        name: module
        for name, module in sys.modules.items()
        if name == "app" or name.startswith("app.")
    }
    for name in saved:
        del sys.modules[name]
    return saved


def _restore_app_modules(saved: dict[str, ModuleType], inserted_path: str | None) -> None:
    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            del sys.modules[name]
    sys.modules.update(saved)
    if inserted_path is not None:
        sys.path.remove(inserted_path)


def _patch_index_paths(
    monkeypatch: pytest.MonkeyPatch,
    *,
    lancedb_dir: Path,
    duckdb_dir: Path,
    bm25_dir: Path,
) -> None:
    monkeypatch.setattr(
        "bishop_shared.indexing_config.bm25_domain_root",
        lambda domain: bm25_dir / domain,
    )
    monkeypatch.setattr("bishop_shared.indexing_config.LANCEDB_DIR", str(lancedb_dir))
    monkeypatch.setattr(
        "bishop_shared.indexing_config.DUCKDB_PATH",
        str(duckdb_dir / "bishop.duckdb"),
    )


class _QueryEncoderMock:
    def encode_query(self, text: str) -> list[float]:
        del text
        return [0.1] * EMBEDDING_DIM


async def _run_index_cycle(
    db_path: Path,
    lancedb_dir: Path,
    duckdb_dir: Path,
) -> None:
    m6 = _load_m6_integration_module()

    loop_mod, _, client_mod, index_mod, lancedb_mod, duckdb_mod = m6._load_vector_writer_stack()
    lancedb = lancedb_mod.LanceDbStore(lancedb_dir)
    duckdb_mirror = duckdb_mod.DuckDbMirror(duckdb_dir / "bishop.duckdb")
    stores = index_mod.IndexStores(
        encoder=m6._MockEncoder(),
        lancedb=lancedb,
        duckdb=duckdb_mirror,
    )

    transport = httpx.ASGITransport(app=m6.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        sw_client = client_mod.StateWorkerClient(client=http)
        await loop_mod.index_cycle(state_client=sw_client, stores=stores)

    duckdb_mirror.close()
    del db_path


@pytest.fixture
def indexed_stores(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path]:
    m6 = _load_m6_integration_module()

    db_path = tmp_path / "bishop.db"
    data_root = tmp_path / "data"
    m6._patch_db_path(monkeypatch, db_path)
    lancedb_dir, duckdb_dir, bm25_dir = m6._patch_store_paths(monkeypatch, data_root)
    monkeypatch.setattr("app.sweeps.SWEEP_INTERVAL_SEC", 3600.0)
    m6.run_migrations(str(db_path))
    asyncio.run(m6._seed_vector_write_queued(db_path, m6._SOURCE_IDS))
    with TestClient(m6.app):
        asyncio.run(_run_index_cycle(db_path, lancedb_dir, duckdb_dir))
    return lancedb_dir, duckdb_dir, bm25_dir


@pytest.fixture
def query_api_client(
    indexed_stores: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    lancedb_dir, duckdb_dir, bm25_dir = indexed_stores
    _patch_index_paths(
        monkeypatch,
        lancedb_dir=lancedb_dir,
        duckdb_dir=duckdb_dir,
        bm25_dir=bm25_dir,
    )

    saved = _clear_app_modules()
    path_str = str(_QUERY_API_ROOT)
    inserted = path_str if path_str not in sys.path else None
    if inserted is not None:
        sys.path.insert(0, inserted)

    try:
        import app.main as main_mod  # noqa: WPS433
        import app.stores.bm25_reader as bm25_reader_mod  # noqa: WPS433

        monkeypatch.setattr(
            bm25_reader_mod.Bm25QueryIndex,
            "start_background_reload",
            lambda self, log=None, **kwargs: None,
        )

        with TestClient(main_mod.app) as client:
            client.app.state.stores._encoder = _QueryEncoderMock()
            yield client
    finally:
        _restore_app_modules(saved, inserted)


@pytest.fixture
def cold_start_query_api_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    lancedb_dir = tmp_path / "lancedb"
    duckdb_dir = tmp_path / "duckdb"
    bm25_dir = tmp_path / "bm25"
    lancedb_dir.mkdir(parents=True)
    duckdb_dir.mkdir(parents=True)
    bm25_dir.mkdir(parents=True)

    _patch_index_paths(
        monkeypatch,
        lancedb_dir=lancedb_dir,
        duckdb_dir=duckdb_dir,
        bm25_dir=bm25_dir,
    )

    saved = _clear_app_modules()
    path_str = str(_QUERY_API_ROOT)
    inserted = path_str if path_str not in sys.path else None
    if inserted is not None:
        sys.path.insert(0, inserted)

    try:
        import app.main as main_mod  # noqa: WPS433
        import app.stores.bm25_reader as bm25_reader_mod  # noqa: WPS433

        monkeypatch.setattr(
            bm25_reader_mod.Bm25QueryIndex,
            "start_background_reload",
            lambda self, log=None, **kwargs: None,
        )

        with TestClient(main_mod.app) as client:
            client.app.state.stores._encoder = _QueryEncoderMock()
            yield client
    finally:
        _restore_app_modules(saved, inserted)


def test_m7_search_returns_hits_from_seeded_stores(query_api_client: TestClient) -> None:
    """Contract: INDEXED BM25+LanceDB+DuckDB fixtures yield non-empty /search hits."""
    response = query_api_client.get("/search", params={"q": "hybrid retrieval RAG"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert len(body["hits"]) >= 1
    hit_ids = {hit["source_id"] for hit in body["hits"]}
    assert hit_ids.intersection(set(_EXPECTED_SOURCE_IDS))
    assert "bm25_main" in body["channels_active"]
    assert "dense" in body["channels_active"]


def test_m7_problem_shaped_search_includes_bm25_hooks_channel(
    query_api_client: TestClient,
) -> None:
    """Contract: problem-shaped query activates bm25_hooks in channels_active."""
    response = query_api_client.get(
        "/search",
        params={"q": "how to build hybrid retrieval pipeline"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["problem_shaped"] is True
    assert "bm25_hooks" in body["channels_active"]


def test_m7_cold_start_search_empty_stores_no_crash(
    cold_start_query_api_client: TestClient,
) -> None:
    """Falsifier: G7 cold-start with empty stores crashes /search instead of empty results."""
    response = cold_start_query_api_client.get("/search", params={"q": "hybrid retrieval"})
    assert response.status_code == 200
    body = response.json()
    assert body["hits"] == []
    assert body["total"] == 0
