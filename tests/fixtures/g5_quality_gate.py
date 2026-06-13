"""Frozen G5 quality-gate fixture entries and query map (M6 T6)."""

from __future__ import annotations

from bishop_shared.indexing_config import build_embed_text

# Spec §8.4 / cold-start step 9 example phrasings (bishop_spec_0_6.md L576, L1437).
G5_FIXTURE_QUERIES: tuple[tuple[str, str], ...] = (
    ("hybrid retrieval for sparse document graphs", "arxiv:2506.00001"),
    ("stateful LLM agent crash recovery", "arxiv:2506.00002"),
    ("dense vector indexing latency optimization", "arxiv:2506.00003"),
)

G5_FIXTURE_ENTRIES: tuple[dict[str, object], ...] = (
    {
        "source_id": "arxiv:2506.00001",
        "title": "Hybrid Sparse-Dense Retrieval for Document Graphs",
        "summary": "Combines BM25 and dense vectors for sparse document graph retrieval.",
        "concepts": ["hybrid retrieval", "sparse graphs", "bm25"],
        "tags": ["retrieval", "graphs"],
        "challenge_hooks": [
            "hybrid retrieval for sparse document graphs",
            "when to rebuild vector indices",
        ],
        "fixture_dim": 0,
    },
    {
        "source_id": "arxiv:2506.00002",
        "title": "Crash Recovery for Stateful LLM Agents",
        "summary": "Checkpointing and restart semantics for long-running agent loops.",
        "concepts": ["agents", "crash recovery", "state machines"],
        "tags": ["agents", "reliability"],
        "challenge_hooks": [
            "stateful LLM agent crash recovery",
            "idempotent tool replay after restart",
        ],
        "fixture_dim": 1,
    },
    {
        "source_id": "arxiv:2506.00003",
        "title": "Latency-Aware Dense Vector Indexing",
        "summary": "Optimizing embedding index build and query latency in production RAG.",
        "concepts": ["vector indexing", "latency", "embeddings"],
        "tags": ["indexing", "performance"],
        "challenge_hooks": [
            "dense vector indexing latency optimization",
            "batch vs streaming index updates",
        ],
        "fixture_dim": 2,
    },
    {
        "source_id": "arxiv:2506.00099",
        "title": "Unrelated Topic: Weather Forecasting",
        "summary": "Numerical weather models unrelated to retrieval or agents.",
        "concepts": ["meteorology"],
        "tags": ["weather"],
        "challenge_hooks": ["precipitation nowcasting"],
        "fixture_dim": 50,
    },
)


def fixture_embed_text(entry: dict[str, object]) -> str:
    return build_embed_text(
        str(entry["title"]),
        str(entry["summary"]),
        list(entry["challenge_hooks"]),  # type: ignore[arg-type]
    )


def fixture_vector_keys() -> dict[str, int]:
    """Map embed text and G5 queries to orthogonal fixture dimensions."""
    mapping: dict[str, int] = {}
    for entry in G5_FIXTURE_ENTRIES:
        dim = int(entry["fixture_dim"])
        mapping[fixture_embed_text(entry)] = dim
        mapping[str(entry["source_id"])] = dim
    for query, source_id in G5_FIXTURE_QUERIES:
        mapping[query] = mapping[source_id]
    return mapping
