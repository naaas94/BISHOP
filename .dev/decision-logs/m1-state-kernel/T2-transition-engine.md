# T2 — transition engine

**Plan:** m1-state-kernel · **Date:** 2026-06-11

## Chosen approach

- **Module:** `services/state-worker/app/transitions.py` owns all state-machine writes — atomic poll claims, ingest, pre-filter, content creation, enrichment H3 sequences, failure/retry handling, and sweep helpers consumed by T3–T5.
- **Atomic claims:** Single-transaction `BEGIN` → `SELECT` → `UPDATE` → `COMMIT` for manifest and entry poll maps per §6.2; `VECTOR_WRITE_QUEUED` read-only poll returns `transitioned_to: null`.
- **H3:** Explicit `await conn.execute("BEGIN")` / `commit()` / `rollback()` for enrichment stage1/2 success paths (COMPLETE → field writes → next QUEUED).
- **N3:** `normalize_failure_state()` maps `*_SUBMITTED` → `*_FAILED` before ErrorLog insert; enrichment batch failure paths use this helper.
- **Provenance:** `assert_pre_filter_provenance()` raises `ProvenanceIncompleteError` when any of `profile_version`, `pre_filter_batch_id`, `pre_filter_rationale` is null on manifest.
- **Retry:** `RETRY_TARGET_MAP` (§6.2 _FAILED states) plus `MANUAL_RETRY_TARGET_MAP` (§14.2 extended table) via `resolve_retry_target()`; `run_retry_sweep()` scans manifest `next_retry_at` / `retry_count`.
- **Lock-state sweep:** `run_lock_state_recovery_sweep()` applies `LOCK_STATE_SWEEP_RESETS`; age proxy uses `discovered_at` (manifest locks) and `ingested_at` (entry locks) because §7 has no `state_entered_at` column.
- **Pipeline sync:** When an `entries` row exists, manifest `processing_state` is updated alongside entry transitions after Stage 3.
- **Submission helpers:** `mark_enrichment_stage1_submitted()` / `mark_enrichment_stage2_submitted()` bridge claim → `_SUBMITTED` (no dedicated §9.1 route; workers call via future batch hooks / internal use).
- **Row access:** `_prepare_conn()` sets `aiosqlite.Row` factory on pooled connections at first read (T1 pool does not set this).

## Alternatives rejected

- **`async with conn` for H3 transactions:** Rejected — spec §6.2 explicitly forbids; connection context manager is not a transaction boundary in aiosqlite.
- **Separate `state_entered_at` migration for sweep age:** Rejected in T2 scope — would require T1 schema amendment; proxy timestamps documented as load-bearing assumption.
- **Retry counters on `entries` table:** Rejected — §7 places `retry_count` / `next_retry_at` on manifest only; sweep and failure paths update manifest as authority.

## Assumptions made

- Lock-state sweep age uses `discovered_at` / `ingested_at` as stand-ins for time-in-lock; legitimate long-running claims before submit are protected by the 15-minute default threshold, not timestamp precision.
- `record_failure()` routes fatal/escalation outcomes to manifest `processing_state`; entry row mirrors failed or escalation state when present.
- Default retry backoff uses 60s base with exponential doubling and ±20% jitter (`DEFAULT_RETRY_BASE_DELAY_SEC`); per-source adapter backoff (§15) is a separate layer.
- Idempotent re-post of enrichment success when already at target work-ready state is a silent no-op.

## Items deferred

- **Concurrent double-writer SQLite claim races:** Out of scope — single-writer discipline assumes only state-worker claims via REST (plan load-bearing assumption).
- **H3 rollback under real SQLite constraint violation mid-sequence:** Covered by unit test patching `_h3_enrichment_stage1_success` failure before commit; full integration fault injection deferred to T6 contract suite.
- **`state_entered_at` column for precise sweep timing:** Deferred to post-M1 schema revision if operational false-positive resets appear.
