# T3 — BM25 rank-bm25 choice

**Plan:** m6-indexing · **Date:** 2026-06-13

## Chosen approach

- **Library:** `rank-bm25` (`BM25Okapi`) with in-memory corpus + `source_ids` list, pickle-serialized to `index.pkl` under each per-domain subdirectory (`main/`, `challenge_hooks/`).
- **Locking:** Single `filelock.FileLock` at `{domain_root}/.bm25_write.lock` covers main add, challenge_hooks add, and persist — no per-subdir locks.
- **Persistence:** `persist()` calls `bishop_shared.atomic_persist` separately for main and hooks payloads; BM25 object rebuilt from corpus on load (not pickled directly).
- **Corpus text:** Main index joins `title`, `summary`, `concepts`, `tags`, `challenge_hooks` (space-separated, lowercased token split); hooks index indexes `challenge_hooks` only.
- **Idempotency:** `has_document(source_id)` reads main index; `add_main` / `add_challenge_hooks` raise `ValueError` on duplicate `source_id`.

## Alternatives rejected

- **tantivy-py:** Rejected per orchestrator Flag 1 resolution — native on-disk WAL reduces atomic-wrapper need but higher startup complexity and no M6 executor packet; incompatible on-disk format with plan binding.
- **Pickling `BM25Okapi` directly:** Rejected — rebuild from stored corpus on load is smaller and avoids rank-bm25 internal pickle fragility across versions.
- **Separate lock files per subdir:** Rejected per spec §8.4 and kill criteria — risks deadlock and torn dual-index state.

## Assumptions made

- Single vector-writer writer per domain at runtime; file lock guards restart overlap, not multi-writer throughput.
- Whitespace tokenization is sufficient for M6 MVP BM25 recall; field-weight tuning deferred.
- `rank-bm25` corpus rebuild on each add is acceptable at M6 entry volume (incremental add API absent).

## Items deferred

- **Concurrent lock contention integration test:** T6 `test_bm25_lock_contention.py`.
- **Corrupt/truncated pickle recovery:** No explicit repair path; operator must delete bad `index.pkl` — acceptable for MVP single-writer volume.
- **BM25 field weights:** Spec leaves weights to implementation; uniform tokenization only for M6.
