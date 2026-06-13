# T3 — batch lifecycle API

**Plan:** m3-prefilter · **Date:** 2026-06-13

## Chosen approach

- **Registration:** `POST /batches` accepts client-supplied `batch_id` (UUID from pre-filter-worker), persists `BatchRecord` with `status=submitted`, `submitted_at=now`, and `source_ids` JSON column (`alembic m3_001`). Duplicate `batch_id` returns **409** `batch_conflict` (idempotency contract).
- **Lifecycle patch:** `PATCH /batches/{batch_id}` updates `status`, optional `passed_count`/`failed_count`/`completed_at`/`external_batch_id`; returns `BatchDetailResponse`. Shared by pre-filter and future enrichment batch types (M5).
- **Timeout:** `POST /batches/{batch_id}/timeout` sets batch `status=batch_timed_out` and transitions manifest rows in `RELEVANCE_QUEUED` whose `source_id` is in stored `source_ids` → `DISCOVERED` (plan Flag 2 resolution; no `RELEVANCE_FAILED` in §6.1). Idempotent when already `batch_timed_out` (`entries_reset=0`).
- **Transition ownership:** All batch and manifest writes stay in `transitions.py`; routers delegate only. No worker SQLite access (hub single-writer preserved).

### Derived wire models (undocumented §9.1 bodies)

| Endpoint | Request | Response |
|----------|---------|----------|
| `POST /batches` | `BatchRegisterRequest` | `BatchRegisterResponse`: `{batch_id, status}` — **201** |
| `PATCH /batches/{batch_id}` | `BatchPatchRequest` | `BatchDetailResponse` — **200** |
| `POST /batches/{batch_id}/timeout` | — | `BatchTimeoutResponse`: `{batch_id, status, entries_reset}` — **200** |

## Alternatives rejected

- **UPSERT on duplicate `batch_id`:** Rejected — kill criterion requires explicit 409; silent no-op would hide double-submit bugs from pre-filter-worker.
- **`RELEVANCE_FAILED` or terminal state on timeout:** Rejected — `ProcessingState` has no relevance failure state; `DISCOVERED` matches lock-state sweep semantics and enables retry (plan §5.2 assumption).
- **Infer `source_ids` from manifest `pre_filter_batch_id` at timeout:** Rejected — batch is registered before results land; `pre_filter_batch_id` is unset on queued rows. Persisting `source_ids` at registration is required for restart recovery (context-map Flag 3).

## Assumptions made

- `source_ids` in `POST /batches` matches manifest rows already transitioned to `RELEVANCE_QUEUED` by pre-filter-worker poll claim; T3 does not re-validate manifest membership at registration time.
- Timeout on `pending` batches is allowed (same as `submitted`/`processing`) so batch-poller can call timeout without a separate status branch.
- `GET /batches/{batch_id}` returns `source_ids` via extended `BatchRecord` after migration; no separate wire DTO.

## Items deferred

- **Registration-time manifest state validation:** pre-filter-worker owns claim-before-submit ordering; state-worker does not 409 on `source_ids` not in `RELEVANCE_QUEUED` — deferred to T4 integration tests.
- **Partial PATCH field merge semantics for `external_batch_id`:** null/absent means “leave unchanged”; explicit empty string not used in M3 wire.
