# T4 — RRF fusion and problem-shaped retrieval

**Plan:** m7-read-path · **Date:** 2026-06-13

## Chosen approach

- **`is_problem_shaped`:** Case-insensitive §16.3 prefix `startswith` checks on stripped query plus substring content signals; intentionally broad per spec.
- **`rrf_fuse`:** Standard RRF `Σ 1/(k + rank)` with 1-indexed ranks; default `k` imported from `bishop_shared.query_config.RRF_K` (60).
- **`run_search`:** DuckDB metadata predicates as **pre-filter** (plan Flag 4) — when any structured filter is set, `filter_source_ids` runs first; empty candidate set short-circuits without channel calls. Channels 1–2 always run; channel 3 (`bm25_hooks`) only when problem-shaped. Inactive channel 3 is omitted from `rank_lists` (not passed as empty list to fusion). Results capped at 20.

## Alternatives rejected

- **Post-filter metadata on fused hits:** Rejected per plan Flag 4 binding — interactive search pre-filters candidates before retrieval channels.
- **Semantic classifier for problem-shaped detection:** Rejected — spec §16.3 mandates heuristic prefix + content signals only.
- **Passing channel BM25/dense raw scores into RRF:** Rejected — §16.2 RRF uses rank positions only; channel scores are discarded before fusion.

## Assumptions made

- When no metadata filters are provided, DuckDB pre-filter is skipped (channels search full index scope); domain alone on `GET /search` is applied via LanceDB `where` and optional DuckDB when combined with other filters in T5.
- `run_search` returns `source_id` + `rrf_score` tuples only; T5 enriches hits with title/summary from DuckDB/SQLite.
- Channel internal k and final hit cap both default to 20 per contract.

## Items deferred

- **Domain-only DuckDB pre-filter:** When only `domain` is set without other metadata predicates, orchestrator does not call `filter_source_ids`; LanceDB domain filter suffices for dense channel; T5 may extend if recall gaps appear.
- **Concurrent search logging (`event=search_dispatch`):** T5 route layer owns structured INFO logs per contract.
