"""M6 integration tests — mocked e2e across state-worker and vector-writer (T6)."""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import aiosqlite
import duckdb
import httpx
import pytest
from fastapi.testclient import TestClient

from bishop_shared.enums import DomainEnum, SourceEnum
from bishop_shared.indexing_config import (
    BM25_CHALLENGE_HOOKS_SUBDIR,
    BM25_MAIN_SUBDIR,
    EMBEDDING_DIM,
    LANCEDB_TABLE_NAME,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_STATE_WORKER_ROOT = _REPO_ROOT / "services" / "state-worker"
_VECTOR_WRITER_ROOT = _REPO_ROOT / "services" / "vector-writer"

for path in (_STATE_WORKER_ROOT, _REPO_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from app.db import run_migrations  # noqa: E402
from app.enums import ProcessingState  # noqa: E402
from app.main import app  # noqa: E402
from app.models.http import (  # noqa: E402
    ManifestBatchEntryWire,
    PreFilterResultEntryWire,
)
from app.transitions import (  # noqa: E402
    apply_pre_filter_results,
    claim_manifest_poll,
    create_entry_from_content,
    ingest_manifest_batch,
)

_NOW = datetime(2026, 6, 13, 16, 0, 0, tzinfo=UTC)
_SOURCE_IDS = ("arxiv:2506.01001", "arxiv:2506.01002")
_BATCH_ID = "m6-integration-batch"


def _patch_db_path(monkeypatch: pytest.MonkeyPatch, db_path: Path) -> None:
    monkeypatch.setattr("app.db.SQLITE_DB_PATH", str(db_path))


def _patch_store_paths(
    monkeypatch: pytest.MonkeyPatch,
    data_root: Path,
) -> tuple[Path, Path, Path]:
    lancedb_dir = data_root / "lancedb"
    duckdb_dir = data_root / "duckdb"
    bm25_dir = data_root / "bm25"
    lancedb_dir.mkdir(parents=True)
    duckdb_dir.mkdir(parents=True)
    bm25_dir.mkdir(parents=True)

    monkeypatch.setattr("bishop_shared.indexing_config.bm25_domain_root", lambda domain: bm25_dir / domain)

    worker_str = str(_VECTOR_WRITER_ROOT)
    if worker_str not in sys.path:
        sys.path.insert(0, worker_str)
    import app.stores.bm25_store as bm25_store_mod  # noqa: WPS433
    import app.stores.duckdb_mirror as duckdb_mirror_mod  # noqa: WPS433

    monkeypatch.setattr(bm25_store_mod, "bm25_domain_root", lambda domain: bm25_dir / domain)
    monkeypatch.setattr(duckdb_mirror_mod, "DUCKDB_PATH", str(duckdb_dir / "bishop.duckdb"))

    return lancedb_dir, duckdb_dir, bm25_dir


def _load_vector_writer_stack() -> tuple[ModuleType, ModuleType, ModuleType, ModuleType, ModuleType, ModuleType]:
    saved = {
        name: module
        for name, module in sys.modules.items()
        if name == "app" or name.startswith("app.")
    }
    for name in saved:
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
        import app.loop as loop_mod  # noqa: WPS433
        import app.models as models_mod  # noqa: WPS433
        import app.state_worker_client as client_mod  # noqa: WPS433
        import app.stores.duckdb_mirror as duckdb_mod  # noqa: WPS433
        import app.stores.lancedb_store as lancedb_mod  # noqa: WPS433
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.modules.update(saved)
        for path_str in path_state:
            sys.path.remove(path_str)

    return loop_mod, models_mod, client_mod, index_mod, lancedb_mod, duckdb_mod


class _MockEncoder:
    def encode(self, texts: list[str]) -> list[list[float]]:
        return [[0.1 + (idx * 0.01)] * EMBEDDING_DIM for idx, _text in enumerate(texts)]


async def _seed_vector_write_queued(db_path: Path, source_ids: tuple[str, ...]) -> None:
    conn = await aiosqlite.connect(str(db_path))
    await conn.execute("PRAGMA journal_mode=WAL")
    try:
        await ingest_manifest_batch(
            conn,
            [
                ManifestBatchEntryWire(
                    source_id=source_id,
                    source=SourceEnum.ARXIV,
                    url=f"https://arxiv.org/abs/{source_id.removeprefix('arxiv:')}",
                    title=f"M6 Integration Paper {source_id}",
                    abstract="An abstract for indexing.",
                    published_at=_NOW,
                    domain=DomainEnum.PROFESSIONAL.value,
                )
                for source_id in source_ids
            ],
        )
        await claim_manifest_poll(conn, ProcessingState.DISCOVERED)
        await apply_pre_filter_results(
            conn,
            _BATCH_ID,
            "1.0.0",
            [
                PreFilterResultEntryWire(
                    source_id=source_id,
                    decision=1,
                    pre_filter_rationale="Relevant for M6 integration.",
                )
                for source_id in source_ids
            ],
        )
        await claim_manifest_poll(conn, ProcessingState.RELEVANCE_PASSED)
        for source_id in source_ids:
            await create_entry_from_content(conn, source_id, "full paper body for m6")
        for index, source_id in enumerate(source_ids):
            await conn.execute(
                """
                UPDATE entries SET
                    processing_state = ?,
                    summary = ?,
                    concepts = ?,
                    tags = ?,
                    entry_type = ?,
                    challenge_hooks = ?,
                    relevance_score = ?,
                    enrichment_stage1_batch_id = ?,
                    enrichment_stage2_batch_id = ?
                WHERE source_id = ?
                """,
                (
                    ProcessingState.VECTOR_WRITE_QUEUED.value,
                    f"Dense technical summary for {source_id}.",
                    json.dumps(["retrieval", "indexing"]),
                    json.dumps(["RAG", "hybrid-retrieval"]),
                    "paper",
                    json.dumps(
                        [
                            "hybrid retrieval for sparse document graphs",
                            f"challenge hook {index}",
                        ]
                    ),
                    0.85 + (index * 0.01),
                    "m6-s1-batch",
                    "m6-s2-batch",
                    source_id,
                ),
            )
            await conn.execute(
                "UPDATE manifest SET processing_state = ? WHERE source_id = ?",
                (ProcessingState.VECTOR_WRITE_QUEUED.value, source_id),
            )
        await conn.commit()
    finally:
        await conn.close()


async def _entry_state(db_path: Path, source_id: str) -> str | None:
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            "SELECT processing_state FROM entries WHERE source_id = ?",
            (source_id,),
        )
        row = await cursor.fetchone()
    return row[0] if row else None


def _lance_row_count(lancedb_dir: Path, source_id: str) -> int:
    _, _, _, _, lancedb_mod, _ = _load_vector_writer_stack()
    store = lancedb_mod.LanceDbStore(lancedb_dir)
    table = store._db.open_table(LANCEDB_TABLE_NAME)
    escaped = source_id.replace("'", "''")
    return len(table.search().where(f"source_id = '{escaped}'").limit(5).to_list())


def _bm25_files_exist(bm25_dir: Path, source_id: str) -> bool:
    domain_root = bm25_dir / DomainEnum.PROFESSIONAL.value
    main_path = domain_root / BM25_MAIN_SUBDIR / "index.pkl"
    hooks_path = domain_root / BM25_CHALLENGE_HOOKS_SUBDIR / "index.pkl"
    return main_path.is_file() and hooks_path.is_file()


def _duckdb_has_row(duckdb_dir: Path, source_id: str) -> bool:
    db_path = duckdb_dir / "bishop.duckdb"
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        row = conn.execute(
            "SELECT 1 FROM entries_mirror WHERE source_id = ?",
            [source_id],
        ).fetchone()
        return row is not None
    finally:
        conn.close()


@pytest.fixture
def integration_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "bishop.db"
    data_root = tmp_path / "data"
    _patch_db_path(monkeypatch, db_path)
    lancedb_dir, duckdb_dir, bm25_dir = _patch_store_paths(monkeypatch, data_root)
    monkeypatch.setattr("app.sweeps.SWEEP_INTERVAL_SEC", 3600.0)
    run_migrations(str(db_path))
    asyncio.run(_seed_vector_write_queued(db_path, _SOURCE_IDS))
    with TestClient(app) as client:
        yield client, db_path, lancedb_dir, duckdb_dir, bm25_dir


def test_m6_e2e_vector_write_queued_reaches_indexed_with_three_stores(
    integration_env: tuple[TestClient, Path, Path, Path, Path],
) -> None:
    """Contract: VECTOR_WRITE_QUEUED entries → mocked encoder → INDEXED + LanceDB/BM25/DuckDB."""
    client, db_path, lancedb_dir, duckdb_dir, bm25_dir = integration_env
    loop_mod, _, client_mod, index_mod, lancedb_mod, duckdb_mod = _load_vector_writer_stack()

    lancedb = lancedb_mod.LanceDbStore(lancedb_dir)
    duckdb_mirror = duckdb_mod.DuckDbMirror(duckdb_dir / "bishop.duckdb")
    stores = index_mod.IndexStores(
        encoder=_MockEncoder(),
        lancedb=lancedb,
        duckdb=duckdb_mirror,
    )

    async def _run_cycle() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            sw_client = client_mod.StateWorkerClient(client=http)
            await loop_mod.index_cycle(state_client=sw_client, stores=stores)

    asyncio.run(_run_cycle())
    duckdb_mirror.close()

    for source_id in _SOURCE_IDS:
        assert asyncio.run(_entry_state(db_path, source_id)) == ProcessingState.INDEXED.value
        assert _lance_row_count(lancedb_dir, source_id) == 1
        assert _bm25_files_exist(bm25_dir, source_id)
        assert _duckdb_has_row(duckdb_dir, source_id)


def test_m6_idempotent_reindex_skips_duplicate_lancedb_vector(
    integration_env: tuple[TestClient, Path, Path, Path, Path],
) -> None:
    """Falsifier: re-index after store writes must not create a second LanceDB row."""
    client, db_path, lancedb_dir, duckdb_dir, bm25_dir = integration_env
    loop_mod, _, client_mod, index_mod, lancedb_mod, duckdb_mod = _load_vector_writer_stack()

    lancedb = lancedb_mod.LanceDbStore(lancedb_dir)
    duckdb_mirror = duckdb_mod.DuckDbMirror(duckdb_dir / "bishop.duckdb")
    stores = index_mod.IndexStores(
        encoder=_MockEncoder(),
        lancedb=lancedb,
        duckdb=duckdb_mirror,
    )

    async def _run_cycle() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            sw_client = client_mod.StateWorkerClient(client=http)
            await loop_mod.index_cycle(state_client=sw_client, stores=stores)

    asyncio.run(_run_cycle())
    source_id = _SOURCE_IDS[0]
    assert _lance_row_count(lancedb_dir, source_id) == 1

    async def _reset_to_queued() -> None:
        async with aiosqlite.connect(db_path) as conn:
            await conn.execute(
                "UPDATE entries SET processing_state = ? WHERE source_id = ?",
                (ProcessingState.VECTOR_WRITE_QUEUED.value, source_id),
            )
            await conn.execute(
                "UPDATE manifest SET processing_state = ? WHERE source_id = ?",
                (ProcessingState.VECTOR_WRITE_QUEUED.value, source_id),
            )
            await conn.commit()

    asyncio.run(_reset_to_queued())
    asyncio.run(_run_cycle())

    assert _lance_row_count(lancedb_dir, source_id) == 1
    assert asyncio.run(_entry_state(db_path, source_id)) == ProcessingState.INDEXED.value
