# T2 — BM25 query reader

**Plan:** m7-read-path · **Date:** 2026-06-13

## Chosen approach

- **`Bm25QueryIndex`:** One class per domain loads `main/index.pkl` and `challenge_hooks/index.pkl` under `bm25_domain_root(domain)`; `search(query, k, channel=...)` uses shared `tokenize_bm25` and `rank_bm25.BM25Okapi.get_scores`.
- **Copy-on-write reload:** `reload_cow()` builds fresh `_LoadedIndex` frozen snapshots then swaps `self._main` / `self._hooks` references; corrupt/EOF pickle during reload logs `event=bm25_reload_failed` and retains the prior snapshot.
- **Background reload:** `start_background_reload()` asyncio loop sleeps `BM25_RELOAD_INTERVAL_SEC` (override for tests) and calls `reload_cow()`; wiring into FastAPI lifespan deferred to T5.

## Alternatives rejected

- **Import `Bm25DualIndex` from vector-writer:** Rejected per plan Flag 1 — query-api reads pickles independently via shared path constants and payload schema only.
- **In-place corpus mutation on reload:** Rejected per spec §8.4 G5 — concurrent searches could observe partial state.

## Assumptions made

- T4 orchestrator passes `channel="challenge_hooks"` on the existing `search()` method for Channel 3; default `channel="main"` preserves the contract call shape `search(query, k)`.
- Initial `load()` raises on schema mismatch (fail-fast at startup); `reload_cow()` is lenient and keeps the old index on transient writer races.

## Items deferred

- **Lifespan registration of `start_background_reload`:** T5 owns query-api startup wiring after store readers are composed.
- **Concurrent read during reload stress test:** Object-identity COW falsifier covered in unit tests; threaded load test deferred — single-threaded asyncio query-api assumed for M7.
