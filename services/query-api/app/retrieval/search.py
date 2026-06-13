"""Search orchestrator wiring BM25, dense, and challenge_hooks channels (M7 T4)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.embedding import QueryEmbeddingEncoder
from app.retrieval.problem_shaped import is_problem_shaped
from app.retrieval.rrf import rrf_fuse
from app.stores.bm25_reader import Bm25QueryIndex
from app.stores.duckdb_reader import DuckDbReader
from app.stores.lancedb_reader import LanceDbSearcher

ChannelName = Literal["bm25_main", "dense", "bm25_hooks"]

DEFAULT_CHANNEL_K = 20
DEFAULT_HIT_CAP = 20


@dataclass(frozen=True)
class SearchOrchestrationResult:
    query: str
    problem_shaped: bool
    channels_active: list[ChannelName]
    hits: list[tuple[str, float]]


def _metadata_filters_active(
    *,
    source: str | None,
    tags: list[str] | None,
    min_relevance: float | None,
    days: int | None,
    entry_type: str | None,
    reading_status: str | None,
) -> bool:
    return any(
        value is not None
        for value in (
            source,
            tags,
            min_relevance,
            days,
            entry_type,
            reading_status,
        )
    )


def _ranked_ids(
    ranked: list[tuple[str, float]],
    allowed: set[str] | None,
) -> list[str]:
    if allowed is None:
        return [source_id for source_id, _ in ranked]
    return [source_id for source_id, _ in ranked if source_id in allowed]


def run_search(
    *,
    query: str,
    bm25: Bm25QueryIndex,
    dense: LanceDbSearcher,
    metadata: DuckDbReader,
    encoder: QueryEmbeddingEncoder,
    domain: str | None = None,
    source: str | None = None,
    tags: list[str] | None = None,
    min_relevance: float | None = None,
    days: int | None = None,
    entry_type: str | None = None,
    reading_status: str | None = None,
    channel_k: int = DEFAULT_CHANNEL_K,
    hit_cap: int = DEFAULT_HIT_CAP,
) -> SearchOrchestrationResult:
    """Run channels 1–3 with DuckDB metadata pre-filter and RRF fusion."""
    problem_shaped = is_problem_shaped(query)
    channels_active: list[ChannelName] = ["bm25_main", "dense"]
    if problem_shaped:
        channels_active.append("bm25_hooks")

    allowed: set[str] | None = None
    if _metadata_filters_active(
        source=source,
        tags=tags,
        min_relevance=min_relevance,
        days=days,
        entry_type=entry_type,
        reading_status=reading_status,
    ):
        candidate_ids = metadata.filter_source_ids(
            domain=domain,
            source=source,
            tags=tags,
            min_relevance=min_relevance,
            days=days,
            entry_type=entry_type,
            reading_status=reading_status,
        )
        if not candidate_ids:
            return SearchOrchestrationResult(
                query=query,
                problem_shaped=problem_shaped,
                channels_active=channels_active,
                hits=[],
            )
        allowed = set(candidate_ids)

    bm25_main = _ranked_ids(
        bm25.search(query, channel_k, channel="main"),
        allowed,
    )
    vector = encoder.encode_query(query)
    dense_hits = _ranked_ids(
        dense.search(vector, channel_k, domain=domain),
        allowed,
    )

    rank_lists = [bm25_main, dense_hits]
    if problem_shaped:
        rank_lists.append(
            _ranked_ids(
                bm25.search(query, channel_k, channel="challenge_hooks"),
                allowed,
            )
        )

    fused = rrf_fuse(rank_lists)
    if hit_cap > 0:
        fused = fused[:hit_cap]

    return SearchOrchestrationResult(
        query=query,
        problem_shaped=problem_shaped,
        channels_active=channels_active,
        hits=fused,
    )
