# T1 — Indexing shared contracts

**Plan:** m6-indexing · **Date:** 2026-06-13

## Chosen approach

- **Path constants:** Derived from `BISHOP_VOLUME_MOUNTS` container paths in `bishop_shared/constants.py`, mirroring the `SQLITE_DB_PATH` pattern (`LANCEDB_DIR`, `DUCKDB_PATH`, `bm25_domain_root`).
- **Embed text:** `build_embed_text` implements spec N1 (`title\nsummary\n` + space-joined `challenge_hooks`); `None` hooks coerced to `[]` so poll rows with missing hooks do not raise at encode time.
- **Atomic persist:** Shared `bishop_shared/atomic_persist.py` — `tempfile.mkstemp` in target parent, `serialize_fn` writes bytes, `flush` + `fsync`, `os.replace`; temp cleaned on failure.

## Alternatives rejected

- **In-place target overwrite:** Rejected per spec §8.4 S4 — crash mid-write yields unrecoverable corrupt index; T1 wrapper enforces temp + replace.
- **Store-local atomic helpers:** Rejected — single shared utility consumed by BM25 (T3) and keeps persistence semantics in one test surface.

## Assumptions made

- DuckDB filename `bishop.duckdb` under the duckdb mount matches charter/plan contract (`DUCKDB_PATH`); T4 mirror DDL uses this path.
- `challenge_hooks or []` guard is compatible with spec N1 when hooks are always populated post-M5; guard only affects `None`, not empty list.

## Items deferred

- **Directory fsync before replace:** Spec S4 names file `fsync` only; parent-directory durability on ext4 deferred — acceptable for MVP single-writer BM25.
- **Concurrent readers during replace:** POSIX `rename` atomicity assumed; query-api BM25 load is M7.
