"""G2 contract tests — charter exit gate for M1 state-worker (T6)."""

from __future__ import annotations

import asyncio
import sqlite3
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import aiosqlite
import pytest
from fastapi.testclient import TestClient

_REPO_ROOT = Path(__file__).resolve().parent.parent
_STATE_WORKER_ROOT = _REPO_ROOT / "services" / "state-worker"

for path in (_STATE_WORKER_ROOT, _REPO_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from app.db import run_migrations  # noqa: E402
from app.enums import (  # noqa: E402
    BatchStatusEnum,
    BatchTypeEnum,
    DomainEnum,
    EntryTypeEnum,
    ProcessingState,
    SourceEnum,
)
from app.main import app  # noqa: E402
from app.models.domain import BatchRecord  # noqa: E402
from app.models.http import ManifestBatchEntryWire, PreFilterResultEntryWire  # noqa: E402
from app.transitions import (  # noqa: E402
    apply_pre_filter_results,
    claim_manifest_poll,
    create_entry_from_content,
    ingest_manifest_batch,
    record_failure,
)

_NOW = datetime(2026, 6, 11, 12, 0, 0, tzinfo=UTC)
_OLD = _NOW - timedelta(hours=1)
_SOURCE = "arxiv:2301.00001"
_BATCH_ID = "batch-uuid-contract-1"

EXPECTED_TABLES = frozenset(
    {"manifest", "entries", "batches", "error_log", "oov_tags_log", "scraper_state"}
)

SPEC_ROUTE_METHOD_PATHS: frozenset[tuple[str, str]] = frozenset(
    {
        ("POST", "/manifest/batch"),
        ("POST", "/manifest/pre-filter-results"),
        ("POST", "/entries/content"),
        ("POST", "/entries/enrichment-stage1-results"),
        ("POST", "/entries/enrichment-stage2-results"),
        ("POST", "/entries/indexed"),
        ("POST", "/entries/failed"),
        ("POST", "/entries/retry"),
        ("GET", "/manifest/poll"),
        ("GET", "/entries/poll"),
        ("GET", "/scraper-state/{source}"),
        ("POST", "/scraper-state/{source}"),
        ("GET", "/batches"),
        ("GET", "/batches/{batch_id}"),
        ("GET", "/health"),
        ("GET", "/escalations"),
    }
)


def _registered_routes() -> set[tuple[str, str]]:
    routes: set[tuple[str, str]] = set()
    for route in app.routes:
        if not hasattr(route, "methods") or not hasattr(route, "path"):
            continue
        for method in route.methods:
            if method == "HEAD":
                continue
            routes.add((method, route.path))
    return routes


def _batch_payload(source_id: str = _SOURCE) -> dict:
    return {
        "entries": [
            {
                "source_id": source_id,
                "source": SourceEnum.ARXIV.value,
                "url": "https://arxiv.org/abs/2301.00001",
                "title": "Contract Paper",
                "abstract": "An abstract",
                "published_at": _NOW.isoformat().replace("+00:00", "Z"),
                "domain": DomainEnum.PROFESSIONAL.value,
            }
        ]
    }


def _pre_filter_payload() -> dict:
    return {
        "batch_id": "batch-1",
        "profile_version": "1.0.0",
        "entries": [
            {
                "source_id": _SOURCE,
                "decision": 1,
                "pre_filter_rationale": "Relevant",
            }
        ],
    }


def _patch_db_path(monkeypatch: pytest.MonkeyPatch, db_path: Path) -> None:
    monkeypatch.setattr("app.db.SQLITE_DB_PATH", str(db_path))


def _patch_pool_size_one(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.db as db_mod

    real_init = db_mod.init_pool

    async def _init(db_path: str | None = None, size: int = 5) -> None:
        await real_init(db_path, size=1)

    monkeypatch.setattr(db_mod, "init_pool", _init)


def _warmup_pool_row_factory(client: TestClient) -> None:
    """Prime the single pooled connection with aiosqlite.Row (see scraper_state router)."""
    client.get(f"/scraper-state/{SourceEnum.ARXIV.value}")


def _sqlite_set_processing_state(db_path: Path, state: ProcessingState) -> None:
    conn = sqlite3.connect(db_path)
    try:
        value = state.value
        conn.execute(
            "UPDATE entries SET processing_state = ? WHERE source_id = ?",
            (value, _SOURCE),
        )
        conn.execute(
            "UPDATE manifest SET processing_state = ? WHERE source_id = ?",
            (value, _SOURCE),
        )
        conn.commit()
    finally:
        conn.close()


def _http_advance_to_scrape_queued(client: TestClient) -> None:
    client.post("/manifest/batch", json=_batch_payload())
    client.get("/manifest/poll", params={"state": ProcessingState.DISCOVERED.value})
    client.post("/manifest/pre-filter-results", json=_pre_filter_payload())
    client.get("/manifest/poll", params={"state": ProcessingState.RELEVANCE_PASSED.value})


def _http_advance_to_scraped(client: TestClient) -> None:
    _http_advance_to_scrape_queued(client)
    client.post(
        "/entries/content",
        json={"source_id": _SOURCE, "content_raw": "full paper body"},
    )


def _http_advance_to_enrichment_stage1_queued(client: TestClient) -> None:
    _http_advance_to_scraped(client)
    client.get("/entries/poll", params={"state": ProcessingState.SCRAPED.value})


def _http_advance_to_enrichment_stage1_submitted(
    client: TestClient, db_path: Path
) -> None:
    _http_advance_to_enrichment_stage1_queued(client)
    _sqlite_set_processing_state(db_path, ProcessingState.ENRICHMENT_STAGE1_SUBMITTED)
    _warmup_pool_row_factory(client)


async def _insert_batch_row(db_path: Path, batch_id: str = _BATCH_ID) -> None:
    record = BatchRecord(
        batch_id=batch_id,
        batch_type=BatchTypeEnum.PRE_FILTER,
        domain=DomainEnum.PROFESSIONAL,
        profile_version="1.0.0",
        profile_render_hash="abc123",
        status=BatchStatusEnum.SUBMITTED,
        created_at=_NOW,
        entry_count=1,
        passed_count=0,
        failed_count=0,
    )
    async with aiosqlite.connect(db_path) as conn:
        row = record.to_db_row()
        columns = ", ".join(f'"{key}"' for key in row)
        placeholders = ", ".join("?" for _ in row)
        await conn.execute(
            f'INSERT INTO batches ({columns}) VALUES ({placeholders})',
            tuple(row.values()),
        )
        await conn.commit()


@pytest.fixture
def contract_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "bishop.db"
    _patch_db_path(monkeypatch, db_path)
    monkeypatch.setattr("app.sweeps.SWEEP_INTERVAL_SEC", 0.05)
    with TestClient(app) as client:
        yield client, db_path


def test_route_surface_matches_spec() -> None:
    """G2 gate: every §9.1 route is registered on the assembled application."""
    registered = _registered_routes()
    missing = SPEC_ROUTE_METHOD_PATHS - registered
    assert not missing, f"missing routes: {sorted(missing)}"


def test_alembic_migration_clean_from_empty_db(tmp_path: Path) -> None:
    """G2 gate: Alembic upgrade head on empty file creates all six §7 tables."""
    db_path = tmp_path / "fresh.db"
    run_migrations(str(db_path))
    conn = sqlite3.connect(db_path)
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    finally:
        conn.close()
    assert EXPECTED_TABLES.issubset(tables)


def test_manifest_batch_idempotent(contract_client: tuple[TestClient, Path]) -> None:
    """G2 gate: POST /manifest/batch skips duplicate source_id."""
    client, _ = contract_client
    first = client.post("/manifest/batch", json=_batch_payload())
    second = client.post("/manifest/batch", json=_batch_payload())
    assert first.status_code == 200
    assert first.json() == {"inserted": 1, "skipped": 0}
    assert second.status_code == 200
    assert second.json() == {"inserted": 0, "skipped": 1}


def test_manifest_poll_atomic_double_poll_empty(
    contract_client: tuple[TestClient, Path],
) -> None:
    """G2 gate: second GET /manifest/poll returns empty after atomic claim."""
    client, _ = contract_client
    client.post("/manifest/batch", json=_batch_payload())
    first = client.get(
        "/manifest/poll", params={"state": ProcessingState.DISCOVERED.value}
    )
    second = client.get(
        "/manifest/poll", params={"state": ProcessingState.DISCOVERED.value}
    )
    assert first.status_code == 200
    assert first.json()["claimed_count"] == 1
    assert second.status_code == 200
    assert second.json()["claimed_count"] == 0
    assert second.json()["entries"] == []


def test_enrichment_stage1_results_rolls_back_on_mid_sequence_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """G2 gate: POST /entries/enrichment-stage1-results rolls back on H3 failure."""
    db_path = tmp_path / "bishop.db"
    _patch_db_path(monkeypatch, db_path)
    _patch_pool_size_one(monkeypatch)
    monkeypatch.setattr("app.sweeps.SWEEP_INTERVAL_SEC", 0.05)

    async def _boom(*_args, **_kwargs):
        raise RuntimeError("simulated mid-H3 failure")

    with patch("app.transitions._h3_enrichment_stage1_success", side_effect=_boom):
        with TestClient(app, raise_server_exceptions=False) as client:
            _http_advance_to_enrichment_stage1_submitted(client, db_path)
            response = client.post(
                "/entries/enrichment-stage1-results",
                json={
                    "batch_id": "enrich-batch-1",
                    "entries": [
                        {
                            "source_id": _SOURCE,
                            "success": True,
                            "summary": "Dense summary",
                            "concepts": ["RAG"],
                        }
                    ],
                },
            )
    assert response.status_code == 500

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT processing_state, summary FROM entries WHERE source_id = ?",
            (_SOURCE,),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    assert row[0] == ProcessingState.ENRICHMENT_STAGE1_SUBMITTED.value
    assert row[1] is None


def test_lock_state_sweep_resets_stuck_relevance_queued(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """G2 gate: background sweep resets stuck RELEVANCE_QUEUED to DISCOVERED."""
    db_path = tmp_path / "bishop.db"
    _patch_db_path(monkeypatch, db_path)
    monkeypatch.setattr("app.sweeps.SWEEP_INTERVAL_SEC", 0.02)
    monkeypatch.setattr("app.sweeps.STUCK_THRESHOLD_SEC", 60)

    run_migrations(str(db_path))

    async def _seed_stuck() -> None:
        conn = await aiosqlite.connect(str(db_path))
        await conn.execute("PRAGMA journal_mode=WAL")
        try:
            await ingest_manifest_batch(
                conn,
                [
                    ManifestBatchEntryWire(
                        source_id=_SOURCE,
                        source=SourceEnum.ARXIV,
                        url="https://arxiv.org/abs/2301.00001",
                        title="Stuck Paper",
                        abstract="An abstract",
                        published_at=_NOW,
                        domain=DomainEnum.PROFESSIONAL.value,
                    )
                ],
                discovered_at=_OLD,
            )
            await claim_manifest_poll(conn, ProcessingState.DISCOVERED)
            await conn.commit()
        finally:
            await conn.close()

    asyncio.run(_seed_stuck())

    with TestClient(app):
        time.sleep(0.1)

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT processing_state FROM manifest WHERE source_id = ?",
            (_SOURCE,),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    assert row[0] == ProcessingState.DISCOVERED.value


def test_post_manifest_pre_filter_results_contract(
    contract_client: tuple[TestClient, Path],
) -> None:
    client, _ = contract_client
    client.post("/manifest/batch", json=_batch_payload())
    client.get("/manifest/poll", params={"state": ProcessingState.DISCOVERED.value})
    response = client.post(
        "/manifest/pre-filter-results",
        json=_pre_filter_payload(),
    )
    assert response.status_code == 200
    assert response.json() == {"updated": 1, "passed": 1, "rejected": 0}


def test_post_entries_content_contract(contract_client: tuple[TestClient, Path]) -> None:
    client, _ = contract_client
    _http_advance_to_scrape_queued(client)
    response = client.post(
        "/entries/content",
        json={"source_id": _SOURCE, "content_raw": "full paper body"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["processing_state"] == ProcessingState.SCRAPED.value
    assert body["entry_id"]


def test_post_entries_enrichment_stage2_results_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "bishop.db"
    _patch_db_path(monkeypatch, db_path)
    _patch_pool_size_one(monkeypatch)
    monkeypatch.setattr("app.sweeps.SWEEP_INTERVAL_SEC", 0.05)

    with TestClient(app) as client:
        _http_advance_to_enrichment_stage1_submitted(client, db_path)
        stage1 = client.post(
            "/entries/enrichment-stage1-results",
            json={
                "batch_id": "enrich-batch-1",
                "entries": [
                    {
                        "source_id": _SOURCE,
                        "success": True,
                        "summary": "Dense summary",
                    }
                ],
            },
        )
        assert stage1.status_code == 204
        client.get(
            "/entries/poll",
            params={"state": ProcessingState.ENRICHMENT_STAGE2_QUEUED.value},
        )
        _sqlite_set_processing_state(
            db_path, ProcessingState.ENRICHMENT_STAGE2_SUBMITTED
        )
        _warmup_pool_row_factory(client)
        response = client.post(
            "/entries/enrichment-stage2-results",
            json={
                "batch_id": "enrich-batch-2",
                "entries": [
                    {
                        "source_id": _SOURCE,
                        "success": True,
                        "relevance_score": 0.9,
                        "relevance_reason": "Highly relevant",
                        "value_rationale": "Strong signal",
                    }
                ],
            },
        )
    assert response.status_code == 204


def test_post_entries_indexed_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "bishop.db"
    _patch_db_path(monkeypatch, db_path)
    monkeypatch.setattr("app.sweeps.SWEEP_INTERVAL_SEC", 0.05)
    run_migrations(str(db_path))

    async def _seed() -> None:
        conn = await aiosqlite.connect(str(db_path))
        await conn.execute("PRAGMA journal_mode=WAL")
        try:
            await ingest_manifest_batch(
                conn,
                [
                    ManifestBatchEntryWire(
                        source_id=_SOURCE,
                        source=SourceEnum.ARXIV,
                        url="https://arxiv.org/abs/2301.00001",
                        title="Contract Paper",
                        abstract="An abstract",
                        published_at=_NOW,
                        domain=DomainEnum.PROFESSIONAL.value,
                    )
                ],
            )
            await claim_manifest_poll(conn, ProcessingState.DISCOVERED)
            await apply_pre_filter_results(
                conn,
                "batch-1",
                "1.0.0",
                [
                    PreFilterResultEntryWire(
                        source_id=_SOURCE,
                        decision=1,
                        pre_filter_rationale="Relevant",
                    )
                ],
            )
            await claim_manifest_poll(conn, ProcessingState.RELEVANCE_PASSED)
            await create_entry_from_content(conn, _SOURCE, "body")
            await conn.execute(
                "UPDATE entries SET processing_state = ? WHERE source_id = ?",
                (ProcessingState.VECTOR_WRITE_QUEUED.value, _SOURCE),
            )
            await conn.execute(
                "UPDATE manifest SET processing_state = ? WHERE source_id = ?",
                (ProcessingState.VECTOR_WRITE_QUEUED.value, _SOURCE),
            )
            await conn.commit()
        finally:
            await conn.close()

    asyncio.run(_seed())

    with TestClient(app) as client:
        response = client.post("/entries/indexed", json={"source_id": _SOURCE})
    assert response.status_code == 204


def test_post_entries_failed_contract(contract_client: tuple[TestClient, Path]) -> None:
    client, _ = contract_client
    _http_advance_to_scraped(client)
    response = client.post(
        "/entries/failed",
        json={
            "source_id": _SOURCE,
            "state_at_failure": ProcessingState.SCRAPE_QUEUED.value,
            "error_class": "TimeoutError",
            "http_status": None,
            "message": "timeout",
            "is_retriable": True,
        },
    )
    assert response.status_code == 204


def test_post_entries_retry_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "bishop.db"
    _patch_db_path(monkeypatch, db_path)
    monkeypatch.setattr("app.sweeps.SWEEP_INTERVAL_SEC", 0.05)
    run_migrations(str(db_path))

    async def _seed() -> None:
        conn = await aiosqlite.connect(str(db_path))
        await conn.execute("PRAGMA journal_mode=WAL")
        try:
            await ingest_manifest_batch(
                conn,
                [
                    ManifestBatchEntryWire(
                        source_id=_SOURCE,
                        source=SourceEnum.ARXIV,
                        url="https://arxiv.org/abs/2301.00001",
                        title="Contract Paper",
                        abstract="An abstract",
                        published_at=_NOW,
                        domain=DomainEnum.PROFESSIONAL.value,
                    )
                ],
            )
            await claim_manifest_poll(conn, ProcessingState.DISCOVERED)
            await apply_pre_filter_results(
                conn,
                "batch-1",
                "1.0.0",
                [
                    PreFilterResultEntryWire(
                        source_id=_SOURCE,
                        decision=1,
                        pre_filter_rationale="Relevant",
                    )
                ],
            )
            await claim_manifest_poll(conn, ProcessingState.RELEVANCE_PASSED)
            await create_entry_from_content(conn, _SOURCE, "body")
            await record_failure(
                conn,
                source_id=_SOURCE,
                state_at_failure=ProcessingState.ENRICHMENT_STAGE1_SUBMITTED,
                error_class="BatchError",
                http_status=None,
                message="failed",
                is_retriable=True,
            )
            await conn.commit()
        finally:
            await conn.close()

    asyncio.run(_seed())

    with TestClient(app) as client:
        response = client.post("/entries/retry", json={"source_id": _SOURCE})
    assert response.status_code == 200
    assert response.json()["processing_state"] == ProcessingState.SCRAPED.value


async def _seed_vector_write_queued(db_path: Path, source_id: str = _SOURCE) -> None:
    """Seed an entry in VECTOR_WRITE_QUEUED with content_raw stored in SQLite."""
    conn = await aiosqlite.connect(str(db_path))
    await conn.execute("PRAGMA journal_mode=WAL")
    try:
        await ingest_manifest_batch(
            conn,
            [
                ManifestBatchEntryWire(
                    source_id=source_id,
                    source=SourceEnum.ARXIV,
                    url="https://arxiv.org/abs/2301.00001",
                    title="Contract Paper",
                    abstract="An abstract",
                    published_at=_NOW,
                    domain=DomainEnum.PROFESSIONAL.value,
                )
            ],
        )
        await claim_manifest_poll(conn, ProcessingState.DISCOVERED)
        await apply_pre_filter_results(
            conn,
            "batch-1",
            "1.0.0",
            [
                PreFilterResultEntryWire(
                    source_id=source_id,
                    decision=1,
                    pre_filter_rationale="Relevant",
                )
            ],
        )
        await claim_manifest_poll(conn, ProcessingState.RELEVANCE_PASSED)
        await create_entry_from_content(conn, source_id, "full paper body")
        await conn.execute(
            "UPDATE entries SET processing_state = ? WHERE source_id = ?",
            (ProcessingState.VECTOR_WRITE_QUEUED.value, source_id),
        )
        await conn.execute(
            "UPDATE manifest SET processing_state = ? WHERE source_id = ?",
            (ProcessingState.VECTOR_WRITE_QUEUED.value, source_id),
        )
        await conn.commit()
    finally:
        await conn.close()


def test_entries_poll_vector_write_queued_omits_content_raw(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """G2 gate: VECTOR_WRITE_QUEUED poll omits content_raw and does not claim (Flag 3)."""
    db_path = tmp_path / "bishop.db"
    _patch_db_path(monkeypatch, db_path)
    monkeypatch.setattr("app.sweeps.SWEEP_INTERVAL_SEC", 0.05)
    run_migrations(str(db_path))
    asyncio.run(_seed_vector_write_queued(db_path))

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT content_raw FROM entries WHERE source_id = ?",
            (_SOURCE,),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None and row[0] is not None

    with TestClient(app) as client:
        response = client.get(
            "/entries/poll",
            params={"state": ProcessingState.VECTOR_WRITE_QUEUED.value},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["claimed_count"] >= 1
    assert body["transitioned_to"] is None
    assert "content_raw" not in body["entries"][0]
    assert body["entries"][0]["source_id"] == _SOURCE


def test_get_entries_poll_contract(contract_client: tuple[TestClient, Path]) -> None:
    client, _ = contract_client
    _http_advance_to_scraped(client)
    response = client.get(
        "/entries/poll", params={"state": ProcessingState.SCRAPED.value}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["claimed_count"] == 1
    assert body["entries"][0]["content_raw"] == "full paper body"


def test_get_scraper_state_contract(contract_client: tuple[TestClient, Path]) -> None:
    client, _ = contract_client
    response = client.get(f"/scraper-state/{SourceEnum.ARXIV.value}")
    assert response.status_code == 200
    assert response.json()["source"] == SourceEnum.ARXIV.value


def test_post_scraper_state_contract(contract_client: tuple[TestClient, Path]) -> None:
    client, _ = contract_client
    ts = datetime(2026, 6, 8, 10, 0, 0, tzinfo=UTC).isoformat().replace("+00:00", "Z")
    response = client.post(
        f"/scraper-state/{SourceEnum.ARXIV.value}",
        json={"timestamp": ts},
    )
    assert response.status_code == 204
    get_response = client.get(f"/scraper-state/{SourceEnum.ARXIV.value}")
    assert get_response.status_code == 200
    assert get_response.json()["last_successful_run_at"] is not None


def test_get_batches_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "bishop.db"
    _patch_db_path(monkeypatch, db_path)
    monkeypatch.setattr("app.sweeps.SWEEP_INTERVAL_SEC", 0.05)
    run_migrations(str(db_path))
    asyncio.run(_insert_batch_row(db_path))

    with TestClient(app) as client:
        response = client.get("/batches", params={"status": "submitted,processing"})
    assert response.status_code == 200
    assert len(response.json()["batches"]) == 1


def test_get_batch_detail_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "bishop.db"
    _patch_db_path(monkeypatch, db_path)
    monkeypatch.setattr("app.sweeps.SWEEP_INTERVAL_SEC", 0.05)
    run_migrations(str(db_path))
    asyncio.run(_insert_batch_row(db_path))

    with TestClient(app) as client:
        response = client.get(f"/batches/{_BATCH_ID}")
    assert response.status_code == 200
    assert response.json()["batch"]["batch_id"] == _BATCH_ID


def test_get_health_contract(contract_client: tuple[TestClient, Path]) -> None:
    client, _ = contract_client
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_get_escalations_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "bishop.db"
    _patch_db_path(monkeypatch, db_path)
    monkeypatch.setattr("app.sweeps.SWEEP_INTERVAL_SEC", 0.05)
    run_migrations(str(db_path))

    async def _seed() -> None:
        conn = await aiosqlite.connect(str(db_path))
        await conn.execute("PRAGMA journal_mode=WAL")
        try:
            await ingest_manifest_batch(
                conn,
                [
                    ManifestBatchEntryWire(
                        source_id=_SOURCE,
                        source=SourceEnum.ARXIV,
                        url="https://arxiv.org/abs/2301.00001",
                        title="Escalated Paper",
                        abstract="An abstract",
                        published_at=_NOW,
                        domain=DomainEnum.PROFESSIONAL.value,
                    )
                ],
            )
            await record_failure(
                conn,
                source_id=_SOURCE,
                state_at_failure=ProcessingState.SCRAPE_QUEUED,
                error_class="HTTPStatusError",
                http_status=404,
                message="Not found",
                is_retriable=True,
            )
            await conn.commit()
        finally:
            await conn.close()

    asyncio.run(_seed())

    with TestClient(app) as client:
        response = client.get("/escalations")
    assert response.status_code == 200
    entries = response.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["source_id"] == _SOURCE


def test_post_enrichment_stage1_results_success_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract smoke for POST /entries/enrichment-stage1-results happy path."""
    db_path = tmp_path / "bishop.db"
    _patch_db_path(monkeypatch, db_path)
    _patch_pool_size_one(monkeypatch)
    monkeypatch.setattr("app.sweeps.SWEEP_INTERVAL_SEC", 0.05)

    with TestClient(app) as client:
        _http_advance_to_enrichment_stage1_submitted(client, db_path)
        response = client.post(
            "/entries/enrichment-stage1-results",
            json={
                "batch_id": "enrich-batch-1",
                "entries": [
                    {
                        "source_id": _SOURCE,
                        "success": True,
                        "summary": "Dense summary",
                        "concepts": ["RAG"],
                        "tags": ["embeddings"],
                        "entry_type": EntryTypeEnum.PAPER.value,
                        "challenge_hooks": ["latency"],
                    }
                ],
            },
        )
    assert response.status_code == 204
