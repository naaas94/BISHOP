# T2 — LanceDB store and embedding encoder

**Plan:** m6-indexing · **Date:** 2026-06-13

## Chosen approach

- **LanceDB schema:** Plan Flag 3 resolution — table `entries`, idempotency on `source_id`; columns `source_id`, `vector` (fixed `float32[384]`), `title`, `summary`, `domain`, `tags`, `challenge_hooks`, `relevance_score` (nullable). Explicit PyArrow schema on first `create_table`.
- **Idempotency:** `exists(source_id)` uses `table.search().where("source_id = '…'").limit(1)`; `write` returns `False` when duplicate (no second row).
- **EmbeddingEncoder:** Wraps `SentenceTransformer(EMBEDDING_MODEL)` with injectable model for unit tests; validates output length against `EMBEDDING_DIM`.

## Alternatives rejected

- **Implicit schema from first row only:** Rejected — without explicit `float32[384]` list type, LanceDB could infer variable-length vectors and break dimension contract on later writes.
- **Overwrite on duplicate source_id:** Rejected — spec §5.6 check-before-write requires skip, not replace; duplicate vectors degrade retrieval.

## Assumptions made

- LanceDB `search().where(...).limit(1)` without a query vector is supported for scalar-only existence checks (plan §0 Flag 3 filter API).
- `relevance_score` nullable maps to Arrow `float32` with null values; query-api M7 filtering tolerates nulls.

## Items deferred

- **Scalar index on source_id:** Not required for M6 single-writer volume; add if existence checks become hot path.
- **SQL injection hardening beyond quote-escape:** `source_id` is internal pipeline identifier; parameterized filter API deferred if LanceDB exposes it.
