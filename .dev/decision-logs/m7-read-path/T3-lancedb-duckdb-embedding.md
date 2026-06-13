# T3 — LanceDB, DuckDB readers, and query embedding

**Plan:** m7-read-path · **Date:** 2026-06-13

## Chosen approach

- **LanceDbSearcher:** `services/query-api/app/stores/lancedb_reader.py` connects to `LANCEDB_DIR`, opens M6 `entries` table, runs cosine top-k via `table.search(vector).metric("cosine")`, optional `domain` SQL filter, returns `list[tuple[source_id, score]]` with score `1 - _distance`; empty list when table missing or on dimension mismatch raises `ValueError`.
- **DuckDbReader:** `services/query-api/app/stores/duckdb_reader.py` opens `DUCKDB_PATH` with `read_only=True`, reads `entries_mirror` DDL from M6 mirror; `filter_source_ids` applies structured predicates (domain, source, tags via `json_each`, min_relevance, days on `ingested_at`, entry_type, reading_status); `recent` returns `RecentEntry` rows ordered by `ingested_at` desc; empty when file or table missing.
- **QueryEmbeddingEncoder:** `services/query-api/app/embedding.py` wraps `SentenceTransformer(EMBEDDING_MODEL)` with injectable model; `encode_query(text)` encodes the raw query string (not N1 `build_embed_text` concat) and validates `EMBEDDING_DIM`.
- **Requirements:** `services/query-api/requirements.txt` pins `duckdb>=1.0`, `lancedb>=0.17.0`, `sentence-transformers>=2.7.0`, `pyarrow>=15.0` matching vector-writer lower bounds (plan Flag 6).

## Alternatives rejected

- **Import vector-writer `EmbeddingEncoder` / `LanceDbStore` in query-api runtime:** Rejected per plan Flag 1 — read modules live under query-api; M6 writer stores are test-only seed helpers.
- **DuckDB read-write connection for metadata reads:** Rejected — kill criterion requires `read_only=True`; mixed RW/RO on same file risks lock conflicts with vector-writer.
- **Query-time N1 concat for dense search:** Rejected — contract binds raw query string encoding; index-time N1 concat remains vector-writer-only.

## Assumptions made

- LanceDB cosine `_distance` is on [0, 2] for normalized embeddings; `1 - distance` preserves rank order for RRF channel input (T4 consumes ordered lists).
- DuckDB `ingested_at` ISO VARCHAR comparisons are valid for M6 mirror rows written via `datetime.isoformat()`.
- Tags filter uses OR semantics across requested tags (entry matches if any tag hits); AND-all-tags deferred to T5 if API requires it.

## Items deferred

- **LanceDB parameterized domain filter:** Quote-escape matches M6 `lancedb_store.exists` pattern; parameterized API deferred if LanceDB exposes it.
- **DuckDB read_only while vector-writer holds write connection:** M6 `test_duckdb_concurrent_read.py` documents DuckDB mixed-mode limitation; steady-state assumes writer releases connection between upserts.
- **HF model cache in Docker:** Documented in Dockerfile comment pattern from vector-writer; first `encode_query` without injectable model downloads `all-MiniLM-L6-v2`.

## Files added

- `tests/test_query_api_lancedb_reader.py`, `tests/test_query_api_duckdb_reader.py`, `tests/test_query_api_embedding.py` (sanctioned per executor §2.2 test-naming convention).
