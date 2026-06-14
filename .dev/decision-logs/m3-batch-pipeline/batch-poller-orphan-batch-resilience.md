# Batch-poller orphan-batch resilience and sweep coupling

**Date:** 2026-06-13  
**Scope:** batch-poller, state-worker  
**Trigger:** After fixing `messages.batches` SDK path, live compose showed `409 Conflict` on `POST /manifest/pre-filter-results` for stale in-flight batches and `httpx.ReadTimeout` crashing the poller (exit 1, no restart).

## Problem

1. **Poller crash on transport errors:** `_handle_pre_filter_complete` caught only `httpx.HTTPStatusError`. `ReadTimeout` on bulk result POST (50 entries) propagated and killed the container. Compose had no `restart` policy.

2. **Orphan batches after poller downtime:** Lock-state sweep (`RELEVANCE_QUEUED → DISCOVERED` after `STUCK_THRESHOLD_SEC`) used `discovered_at` only and ignored in-flight `batches` rows. Entries were released while `submitted` batch records remained. Fixed poller fetched Anthropic results but `apply_pre_filter_results` returned `409 invalid_transition` for `DISCOVERED` entries — retried every poll cycle forever.

3. **Duplicate Anthropic submits:** `register_batch` for `pre_filter` did not verify manifest state. After sweep reset, pre-filter re-polled the same `DISCOVERED` entries and registered new batches for already-submitted Anthropic work.

## Decision

**batch-poller**

- Catch `httpx.RequestError` (includes `ReadTimeout`) on all results POST paths; log and retry next cycle without exiting.
- On `409` with `error: invalid_transition`, PATCH batch `failed` and drop from tracked set (`stale_batch_results_rejected`).
- `StateWorkerClient` default timeout 60s via `BISHOP_STATE_WORKER_HTTP_TIMEOUT_SEC`.
- `restart: unless-stopped` on batch-poller in compose.

**state-worker**

- `register_batch` for `pre_filter`: require every `source_id` ∈ `RELEVANCE_QUEUED`; else `409 invalid_source_state`.
- `run_lock_state_recovery_sweep`: skip `RELEVANCE_QUEUED` entries whose `source_id` appears in any `submitted` / `processing` / `pending` batch.

## Rationale

**Why fail stale batches on invalid_transition?** Results are undeliverable without manual state repair; marking `failed` stops infinite Anthropic result re-fetch and POST loops.

**Why not fail on ReadTimeout?** Transient state-worker slowness (SQLite, concurrent workers); same batch should retry.

**Why register-time validation?** Pre-filter submits to Anthropic before `POST /batches`; validation at registration still blocks duplicate batch rows when sweep has already released claims — pre-filter logs 409 and does not accumulate orphan rows (orphaned Anthropic spend on submit-before-register path unchanged per M3 CR-1).

**Why sweep/batch coupling only for RELEVANCE_QUEUED?** Matches manifest lock-state sweep scope; enrichment entry lock states use different reset map.

## Alternatives considered

| Option | Rejected because |
|--------|------------------|
| Auto-apply results from DISCOVERED on poll | Violates transition engine; masks sweep/orphan bug |
| Extend sweep threshold only | Does not fix overlap when poller down > threshold |
| Idempotent pre-filter-results for DISCOVERED | Would skip provenance transitions and batch_id binding |

## Files touched

- `services/batch-poller/app/config.py`
- `services/batch-poller/app/clients/state_worker.py`
- `services/batch-poller/app/loop.py`
- `services/state-worker/app/transitions.py`
- `services/state-worker/app/routers/batches.py`
- `docker-compose.yml`
- `tests/test_batch_poller_loop.py`, `tests/test_batch_poller_config.py`
- `tests/test_state_worker_batches_register.py`, `tests/test_state_worker_transitions.py`

## Recovery (existing poisoned DB)

Orphan `submitted` batches from the outage window: restart poller — new code marks them `failed` on next `invalid_transition`. Re-run pre-filter for remaining `DISCOVERED` entries. No migration required.

## Deferred

- Pre-filter submit-before-register orphan on `invalid_source_state` 409 (release claim without new Anthropic submit).
- Per-entry partial apply for pre-filter-results when batch membership is mixed.
