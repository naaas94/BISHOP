"""Unit tests for vector-writer index_entry orchestration (M6 T5)."""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from bishop_shared.enums import DomainEnum, SourceEnum
from bishop_shared.indexing_config import EMBEDDING_DIM

_REPO_ROOT = Path(__file__).resolve().parent.parent
_VECTOR_WRITER_ROOT = _REPO_ROOT / "services" / "vector-writer"


def _load_index_entry_stack() -> tuple[ModuleType, ModuleType, ModuleType]:
    saved_app_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "app" or name.startswith("app.")
    }
    for name in saved_app_modules:
        del sys.modules[name]

    repo_str = str(_REPO_ROOT)
    worker_str = str(_VECTOR_WRITER_ROOT)
    path_state: list[str] = []
    for path_str in (worker_str, repo_str):
        if path_str not in sys.path:
            sys.path.insert(0, path_str)
            path_state.append(path_str)

    try:
        import app.index_entry as index_mod  # noqa: WPS433
        import app.models as models_mod  # noqa: WPS433
        import app.state_worker_client as client_mod  # noqa: WPS433
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.modules.update(saved_app_modules)
        for path_str in path_state:
            sys.path.remove(path_str)

    return index_mod, models_mod, client_mod


def _sample_entry(models: ModuleType) -> object:
    return models.EntryPollRow(
        source_id="arxiv:2401.00001",
        source=SourceEnum.ARXIV,
        url="https://arxiv.org/abs/2401.00001",
        title="Hybrid Retrieval",
        published_at=datetime(2024, 1, 15, tzinfo=UTC),
        ingested_at=datetime(2024, 1, 16, 12, 0, tzinfo=UTC),
        domain=DomainEnum.PROFESSIONAL,
        profile_version="1.0.0",
        pre_filter_batch_id="batch-1",
        pre_filter_rationale="Relevant",
        summary="Dense and sparse search combined.",
        concepts=["vector search"],
        tags=["retrieval"],
        challenge_hooks=["sparse document graphs"],
        relevance_score=0.92,
        processing_state="VECTOR_WRITE_QUEUED",
    )


class _FakeEncoder:
    def encode(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * EMBEDDING_DIM for _text in texts]


def _mock_stores(index_mod: ModuleType) -> MagicMock:
    lancedb = MagicMock()
    lancedb.exists.return_value = False
    lancedb.write.return_value = True

    bm25 = MagicMock()
    bm25.has_document.return_value = False
    bm25.add_main = MagicMock()
    bm25.add_challenge_hooks = MagicMock()
    bm25.persist = MagicMock()

    duckdb = MagicMock()
    duckdb.upsert = MagicMock()

    stores = MagicMock(spec=index_mod.IndexStores)
    stores.encoder = _FakeEncoder()
    stores.lancedb = lancedb
    stores.duckdb = duckdb
    stores.bm25_for.return_value = bm25
    return stores


def test_index_entry_posts_indexed_after_all_stores_succeed() -> None:
    index_mod, models, client_mod = _load_index_entry_stack()
    entry = _sample_entry(models)
    stores = _mock_stores(index_mod)
    state_client = MagicMock(spec=client_mod.StateWorkerClient)
    state_client.post_indexed = AsyncMock()
    state_client.post_failed = AsyncMock()

    async def _run() -> bool:
        return await index_mod.index_entry(entry, stores, state_client)

    assert asyncio.run(_run()) is True
    stores.lancedb.write.assert_called_once()
    stores.bm25_for.return_value.persist.assert_called_once()
    stores.duckdb.upsert.assert_called_once()
    state_client.post_indexed.assert_awaited_once()
    state_client.post_failed.assert_not_awaited()


def test_index_entry_does_not_post_indexed_when_duckdb_fails() -> None:
    """Falsifier: indexed signal must not fire before all three stores succeed."""
    index_mod, models, client_mod = _load_index_entry_stack()
    entry = _sample_entry(models)
    stores = _mock_stores(index_mod)
    stores.duckdb.upsert.side_effect = RuntimeError("duckdb write failed")
    state_client = MagicMock(spec=client_mod.StateWorkerClient)
    state_client.post_indexed = AsyncMock()
    state_client.post_failed = AsyncMock()

    async def _run() -> bool:
        return await index_mod.index_entry(entry, stores, state_client)

    assert asyncio.run(_run()) is False
    state_client.post_indexed.assert_not_awaited()
    state_client.post_failed.assert_awaited_once()
    failed_body = state_client.post_failed.await_args.args[0]
    assert failed_body.state_at_failure == "VECTOR_WRITE_QUEUED"
    assert failed_body.is_retriable is True


def test_index_entry_skips_duplicate_lancedb_and_bm25_writes() -> None:
    index_mod, models, client_mod = _load_index_entry_stack()
    entry = _sample_entry(models)
    stores = _mock_stores(index_mod)
    stores.lancedb.exists.return_value = True
    stores.bm25_for.return_value.has_document.return_value = True
    state_client = MagicMock(spec=client_mod.StateWorkerClient)
    state_client.post_indexed = AsyncMock()
    state_client.post_failed = AsyncMock()

    async def _run() -> bool:
        return await index_mod.index_entry(entry, stores, state_client)

    assert asyncio.run(_run()) is True
    stores.lancedb.write.assert_not_called()
    stores.bm25_for.return_value.add_main.assert_not_called()
    stores.bm25_for.return_value.persist.assert_not_called()
    stores.duckdb.upsert.assert_called_once()
    state_client.post_indexed.assert_awaited_once()


def test_index_entry_returns_false_when_indexed_signal_fails_after_stores() -> None:
    """Falsifier: stores written but POST /entries/indexed non-2xx must not report success."""
    index_mod, models, client_mod = _load_index_entry_stack()
    entry = _sample_entry(models)
    stores = _mock_stores(index_mod)
    state_client = MagicMock(spec=client_mod.StateWorkerClient)
    request = httpx.Request("POST", "http://test/entries/indexed")
    response = httpx.Response(500, request=request)
    state_client.post_indexed = AsyncMock(
        side_effect=httpx.HTTPStatusError("error", request=request, response=response),
    )
    state_client.post_failed = AsyncMock()

    async def _run() -> bool:
        return await index_mod.index_entry(entry, stores, state_client)

    assert asyncio.run(_run()) is False
    state_client.post_failed.assert_not_awaited()


@pytest.fixture
def bm25_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "bm25"

    def _root(domain: str) -> Path:
        return root / domain

    monkeypatch.setattr("bishop_shared.indexing_config.bm25_domain_root", _root)
    return root


def test_index_entry_posts_failed_on_bm25_lock_timeout(bm25_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from filelock import Timeout

    index_mod, models, client_mod = _load_index_entry_stack()

    repo_str = str(_REPO_ROOT)
    worker_str = str(_VECTOR_WRITER_ROOT)
    for path_str in (worker_str, repo_str):
        if path_str not in sys.path:
            sys.path.insert(0, path_str)
    import app.stores.bm25_store as bm25_store_mod  # noqa: WPS433

    monkeypatch.setattr(bm25_store_mod, "bm25_domain_root", lambda domain: bm25_root / domain)

    entry = _sample_entry(models)
    stores = _mock_stores(index_mod)
    real_bm25 = bm25_store_mod.Bm25DualIndex("professional", lock_timeout=0.01)
    stores.bm25_for.return_value = real_bm25
    stores.bm25_for.side_effect = lambda _domain: real_bm25

    monkeypatch.setattr(
        real_bm25,
        "add_main",
        MagicMock(side_effect=Timeout("locked")),
    )

    state_client = MagicMock(spec=client_mod.StateWorkerClient)
    state_client.post_indexed = AsyncMock()
    state_client.post_failed = AsyncMock()

    async def _run() -> bool:
        return await index_mod.index_entry(entry, stores, state_client)

    assert asyncio.run(_run()) is False
    state_client.post_indexed.assert_not_awaited()
    state_client.post_failed.assert_awaited_once()
    failed_body = state_client.post_failed.await_args.args[0]
    assert failed_body.error_class == "Bm25LockTimeout"
