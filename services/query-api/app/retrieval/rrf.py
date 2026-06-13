"""Reciprocal Rank Fusion for multi-channel retrieval (M7 T4)."""

from __future__ import annotations

from bishop_shared.query_config import RRF_K


def rrf_fuse(
    rank_lists: list[list[str]],
    k: int = RRF_K,
) -> list[tuple[str, float]]:
    """Fuse ranked source_id lists with RRF; absent docs contribute 0 per §16.2."""
    scores: dict[str, float] = {}
    for ranked in rank_lists:
        for rank, source_id in enumerate(ranked, start=1):
            scores[source_id] = scores.get(source_id, 0.0) + (1.0 / (k + rank))

    return sorted(scores.items(), key=lambda item: item[1], reverse=True)
