"""Unit tests for state-worker entry write routers (T4)."""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

_REPO_ROOT = Path(__file__).resolve().parent.parent
_STATE_WORKER_ROOT = _REPO_ROOT / "services" / "state-worker"

for path in (_STATE_WORKER_ROOT, _REPO_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from app.db import close_pool, get_db, init_pool, run_migrations  # noqa: E402
from app.enums import DomainEnum, EntryTypeEnum, ProcessingState, SourceEnum  # noqa: E402
from app.models.http import (  # noqa: E402
    EnrichmentStage1EntryWire,
    ManifestBatchEntryWire,
    PreFilterResultEntryWire,
)
from app.transitions import (  # noqa: E402
    apply_pre_filter_results,
    claim_entries_poll,
    claim_manifest_poll,
    ingest_manifest_batch,
    mark_enrichment_stage1_submitted,
    record_failure,
)
from app.routers.entries import router  # noqa: E402

_NOW = datetime(2026, 6, 11, 12, 0, 0, tzinfo=UTC)
_SOURCE = "arxiv:2301.00001"


def _wire_entry(source_id: str = _SOURCE) -> ManifestBatchEntryWire:
    return ManifestBatchEntryWire(
        source_id=source_id,
        source=SourceEnum.ARXIV,
        url="https://arxiv.org/abs/2301.00001",
        title="Test Paper",
        abstract="An abstract",
        published_at=_NOW,
        domain=DomainEnum.PROFESSIONAL.value,
    )


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "bishop.db"
    run_migrations(str(db_path))
    return db_path


@pytest.fixture
def client(temp_db: Path):
    async def _setup() -> None:
        await init_pool(str(temp_db), size=1)

    asyncio.run(_setup())
    app = FastAPI()
    app.include_router(router)
    yield TestClient(app)
    asyncio.run(close_pool())


async def _seed_discovered(conn, source_id: str = _SOURCE) -> None:
    result = await ingest_manifest_batch(conn, [_wire_entry(source_id)])
    assert result.inserted == 1


async def _advance_to_relevance_passed(conn, source_id: str = _SOURCE) -> None:
    await _seed_discovered(conn, source_id)
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


async def _advance_to_scrape_queued(conn, source_id: str = _SOURCE) -> None:
    await _advance_to_relevance_passed(conn, source_id)
    await claim_manifest_poll(conn, ProcessingState.RELEVANCE_PASSED)


def test_post_content_creates_entry(client: TestClient) -> None:
    async def _seed() -> None:
        async with get_db() as conn:
            await _advance_to_scrape_queued(conn)

    asyncio.run(_seed())
    response = client.post(
        "/entries/content",
        json={"source_id": _SOURCE, "content_raw": "full paper body"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["processing_state"] == ProcessingState.SCRAPED.value
    assert body["entry_id"]


def test_post_content_provenance_incomplete_returns_409(client: TestClient) -> None:
    async def _seed() -> None:
        async with get_db() as conn:
            await _seed_discovered(conn)
            await conn.execute(
                """
                UPDATE manifest SET
                    processing_state = ?,
                    relevance_decision = 1
                WHERE source_id = ?
                """,
                (ProcessingState.RELEVANCE_PASSED.value, _SOURCE),
            )
            await conn.commit()

    asyncio.run(_seed())
    response = client.post(
        "/entries/content",
        json={"source_id": _SOURCE, "content_raw": "body"},
    )
    assert response.status_code == 409
    assert response.json() == {
        "error": "provenance_incomplete",
        "source_id": _SOURCE,
    }


def test_post_content_invalid_transition_returns_409(client: TestClient) -> None:
    """Falsifier: DISCOVERED manifest accepts content POST without invalid_transition."""
    async def _seed() -> None:
        async with get_db() as conn:
            await _seed_discovered(conn)

    asyncio.run(_seed())
    response = client.post(
        "/entries/content",
        json={"source_id": _SOURCE, "content_raw": "body"},
    )
    assert response.status_code == 409
    body = response.json()
    assert body["error"] == "invalid_transition"
    assert body["source_id"] == _SOURCE
    assert body["from_state"] == ProcessingState.DISCOVERED.value
    assert body["to_state"] == ProcessingState.SCRAPED.value


def test_post_pre_filter_results_returns_counts(client: TestClient) -> None:
    async def _seed() -> None:
        async with get_db() as conn:
            await _seed_discovered(conn)
            await claim_manifest_poll(conn, ProcessingState.DISCOVERED)

    asyncio.run(_seed())
    response = client.post(
        "/manifest/pre-filter-results",
        json={
            "batch_id": "batch-1",
            "profile_version": "1.0.0",
            "entries": [
                {
                    "source_id": _SOURCE,
                    "decision": 1,
                    "pre_filter_rationale": "Relevant",
                }
            ],
        },
    )
    assert response.status_code == 200
    assert response.json() == {"updated": 1, "passed": 1, "rejected": 0}


def test_post_enrichment_stage1_results_returns_204(client: TestClient) -> None:
    async def _seed() -> None:
        async with get_db() as conn:
            await _advance_to_scrape_queued(conn)
            from app.transitions import create_entry_from_content

            await create_entry_from_content(conn, _SOURCE, "body")
            await claim_entries_poll(conn, ProcessingState.SCRAPED)
            await mark_enrichment_stage1_submitted(conn, [_SOURCE], "enrich-batch-1")

    asyncio.run(_seed())
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
    assert response.content == b""


def test_post_enrichment_stage2_results_returns_204(client: TestClient) -> None:
    async def _seed() -> None:
        async with get_db() as conn:
            await _advance_to_scrape_queued(conn)
            from app.transitions import (
                apply_enrichment_stage1_results,
                create_entry_from_content,
                mark_enrichment_stage2_submitted,
            )

            await create_entry_from_content(conn, _SOURCE, "body")
            await claim_entries_poll(conn, ProcessingState.SCRAPED)
            await mark_enrichment_stage1_submitted(conn, [_SOURCE], "enrich-batch-1")
            await apply_enrichment_stage1_results(
                conn,
                "enrich-batch-1",
                [
                    EnrichmentStage1EntryWire(
                        source_id=_SOURCE,
                        success=True,
                        summary="Dense summary",
                    )
                ],
            )
            await claim_entries_poll(conn, ProcessingState.ENRICHMENT_STAGE2_QUEUED)
            await mark_enrichment_stage2_submitted(conn, [_SOURCE], "enrich-batch-2")

    asyncio.run(_seed())
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


def test_post_entries_indexed_returns_204(client: TestClient) -> None:
    async def _seed() -> None:
        async with get_db() as conn:
            await _advance_to_scrape_queued(conn)
            from app.transitions import create_entry_from_content

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

    asyncio.run(_seed())
    response = client.post(
        "/entries/indexed",
        json={"source_id": _SOURCE},
    )
    assert response.status_code == 204


def test_post_entries_failed_returns_204(client: TestClient) -> None:
    async def _seed() -> None:
        async with get_db() as conn:
            await _advance_to_scrape_queued(conn)
            from app.transitions import create_entry_from_content

            await create_entry_from_content(conn, _SOURCE, "body")

    asyncio.run(_seed())
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


def test_post_entries_retry_returns_processing_state(client: TestClient) -> None:
    async def _seed() -> None:
        async with get_db() as conn:
            await _advance_to_scrape_queued(conn)
            from app.transitions import create_entry_from_content

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

    asyncio.run(_seed())
    response = client.post(
        "/entries/retry",
        json={"source_id": _SOURCE},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source_id"] == _SOURCE
    assert body["processing_state"] == ProcessingState.SCRAPED.value


def test_post_entries_not_found_returns_404(client: TestClient) -> None:
    response = client.post(
        "/entries/indexed",
        json={"source_id": "missing:999"},
    )
    assert response.status_code == 404
    assert response.json() == {"error": "not_found", "source_id": "missing:999"}
