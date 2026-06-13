"""Per-entry indexing orchestration across LanceDB, BM25, and DuckDB."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import httpx
from filelock import Timeout

from app.config import VECTOR_WRITE_POLL_STATE
from app.embedding import EmbeddingEncoder
from app.models import EntryPollRow, FailedPostRequest, IndexedPostRequest
from app.state_worker_client import StateWorkerClient
from app.stores.bm25_store import Bm25DualIndex
from app.stores.duckdb_mirror import DuckDbMirror, EntryMirrorRow
from app.stores.lancedb_store import LanceDbStore, LanceRow
from bishop_shared.indexing_config import build_embed_text

logger = logging.getLogger(__name__)


@dataclass
class IndexStores:
    encoder: EmbeddingEncoder
    lancedb: LanceDbStore
    duckdb: DuckDbMirror
    _bm25_by_domain: dict[str, Bm25DualIndex] = field(default_factory=dict)

    def bm25_for(self, domain: str) -> Bm25DualIndex:
        if domain not in self._bm25_by_domain:
            self._bm25_by_domain[domain] = Bm25DualIndex(domain)
        return self._bm25_by_domain[domain]


async def _post_index_failed(
    state_client: StateWorkerClient,
    entry: EntryPollRow,
    *,
    error_class: str,
    message: str,
    http_status: int | None = None,
) -> None:
    try:
        await state_client.post_failed(
            FailedPostRequest(
                source_id=entry.source_id,
                state_at_failure=VECTOR_WRITE_POLL_STATE,
                error_class=error_class,
                http_status=http_status,
                message=message,
                is_retriable=True,
            )
        )
    except httpx.HTTPStatusError as exc:
        logger.error(
            "state-worker failed POST error",
            extra={
                "source_id": entry.source_id,
                "domain": entry.domain.value,
                "http_status": exc.response.status_code,
                "event": "state_worker_error",
            },
        )


def _mirror_row_from_entry(entry: EntryPollRow) -> EntryMirrorRow:
    return EntryMirrorRow(
        source_id=entry.source_id,
        source=entry.source.value,
        url=entry.url,
        title=entry.title,
        published_at=entry.published_at,
        ingested_at=entry.ingested_at,
        domain=entry.domain.value,
        entry_type=entry.entry_type,
        relevance_score=entry.relevance_score,
        reading_status=entry.reading_status,
        summary=entry.summary,
        tags=entry.tags,
        concepts=entry.concepts,
        challenge_hooks=entry.challenge_hooks,
    )


async def index_entry(
    entry: EntryPollRow,
    stores: IndexStores,
    state_client: StateWorkerClient,
) -> bool:
    """Write all index stores then POST /entries/indexed. Returns True on indexed signal success."""
    domain = entry.domain.value
    try:
        embed_text = build_embed_text(entry.title, entry.summary or "", entry.challenge_hooks)
        vector = stores.encoder.encode([embed_text])[0]

        lance_row = LanceRow(
            source_id=entry.source_id,
            vector=vector,
            title=entry.title,
            summary=entry.summary or "",
            domain=domain,
            tags=list(entry.tags or []),
            challenge_hooks=list(entry.challenge_hooks or []),
            relevance_score=entry.relevance_score,
        )
        if stores.lancedb.exists(entry.source_id):
            logger.info(
                "lancedb duplicate skipped",
                extra={
                    "source_id": entry.source_id,
                    "domain": domain,
                    "event": "lancedb_skip_duplicate",
                },
            )
        else:
            stores.lancedb.write(lance_row)

        bm25 = stores.bm25_for(domain)
        if bm25.has_document(entry.source_id):
            logger.info(
                "bm25 duplicate skipped",
                extra={
                    "source_id": entry.source_id,
                    "domain": domain,
                    "event": "bm25_skip_duplicate",
                },
            )
        else:
            bm25.add_main(
                entry.source_id,
                entry.title,
                entry.summary or "",
                entry.concepts,
                entry.tags,
                entry.challenge_hooks,
            )
            bm25.add_challenge_hooks(entry.source_id, entry.challenge_hooks)
            bm25.persist()

        stores.duckdb.upsert(_mirror_row_from_entry(entry))
    except Timeout:
        logger.error(
            "bm25 lock timeout during index",
            extra={
                "source_id": entry.source_id,
                "domain": domain,
                "event": "bm25_lock_timeout",
            },
        )
        await _post_index_failed(
            state_client,
            entry,
            error_class="Bm25LockTimeout",
            message="BM25 domain lock timeout during index write",
        )
        return False
    except Exception as exc:
        logger.error(
            "index store write failed",
            extra={
                "source_id": entry.source_id,
                "domain": domain,
                "error_class": type(exc).__name__,
                "event": "index_write_failed",
            },
        )
        await _post_index_failed(
            state_client,
            entry,
            error_class=type(exc).__name__,
            message=str(exc),
        )
        return False

    try:
        await state_client.post_indexed(IndexedPostRequest(source_id=entry.source_id))
    except httpx.HTTPStatusError as exc:
        logger.critical(
            "indexed signal failed after stores written",
            extra={
                "source_id": entry.source_id,
                "domain": domain,
                "http_status": exc.response.status_code,
                "event": "indexed_signal_failed",
            },
        )
        return False

    logger.info(
        "entry indexed",
        extra={
            "source_id": entry.source_id,
            "domain": domain,
            "event": "entry_indexed",
        },
    )
    return True
