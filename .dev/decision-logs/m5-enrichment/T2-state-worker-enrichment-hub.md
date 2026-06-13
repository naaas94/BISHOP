# T2 — State-worker enrichment hub

**Plan:** m5-enrichment · **Date:** 2026-06-13

## Chosen approach

- **`register_batch` submit hook:** After `BatchRecord` insert, dispatch `mark_enrichment_stage*_submitted` by `batch_type` inside a single SQLite transaction (`BEGIN` / `COMMIT` / `ROLLBACK`). Core transition logic extracted to `_apply_enrichment_stage*_submitted` (no commit); public `mark_*` helpers commit for direct/test callers.
- **`apply_batch_timeout` dispatch:** `pre_filter` retains RELEVANCE_QUEUED → DISCOVERED; `enrichment_stage1` / `enrichment_stage2` transition `_SUBMITTED` → `_FAILED` via `_record_enrichment_failure` with `commit=False`, then one batch-level commit.
- **OOV persistence:** Optional `oov_tags_stripped` on `EnrichmentStage1EntryWire`; `_insert_oov_tags_log` runs inside the H3 stage1 success transaction when `entry_type` is present; `review_status=pending`.

## Alternatives rejected

- **Separate REST route for submit transitions:** Rejected — plan Flag 1 resolution binds submit wiring to `POST /batches` extension only.
- **Direct `_FAILED` SQL without `record_failure` on timeout:** Rejected — timeout should write `error_log` and honor retry mapping like other enrichment failures.
- **OOV insert outside H3 transaction:** Rejected — would allow orphaned log rows if field writes roll back.

## Assumptions made

- Batch-poller sends `entry_type` whenever `oov_tags_stripped` is non-empty (parser always sets type on success).
- `InvalidTransitionError` from `register_batch` is tested at transition layer; batches router 409 mapping is unchanged (out of T2 files-to-touch).

## Items deferred

- **Batches router `invalid_transition` envelope for enrichment register:** Transition tests cover behavior; HTTP 409 mapping deferred to orchestrator if e2e requires it.
- **OOV insert when `entry_type` is None:** Skipped silently — no row without typed surface per §7.5 schema.
