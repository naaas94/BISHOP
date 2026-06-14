# Batch-poller Anthropic SDK namespace hotfix

**Date:** 2026-06-13  
**Scope:** batch-poller  
**Trigger:** `bishop-batch-poller-1` exited on startup with `AttributeError: 'Anthropic' object has no attribute 'batches'` after pre-filter successfully submitted two `messages.batches` jobs.

## Problem

Pre-filter-worker and enrichment-batcher submit batches via `client.messages.batches.create(...)`. Batch-poller polled via `client.batches.retrieve(...)` and `client.batches.results(...)`.

In `anthropic==0.109.1` (pinned `anthropic>=0.40` in batch-poller requirements), the Messages Batch API lives only under `client.messages.batches`. There is no top-level `client.batches`. The poller crashed on the first poll cycle after loading in-flight batches from state-worker.

Unit and integration tests injected `FakeAnthropicClient` or mocked `AnthropicBatchPollerClient` at the protocol layer, so the wrong SDK path never executed in CI.

## Decision

Align batch-poller with submitters:

- `client.messages.batches.retrieve(external_batch_id)`
- `client.messages.batches.results(external_batch_id)`

Add `tests/test_batch_poller_anthropic_client.py` asserting those paths on a mocked SDK client.

## Rationale

**Why not upgrade/downgrade anthropic?** The installed SDK already exposes `messages.batches` with `retrieve` and `results`. This is a caller namespace bug, not a missing feature or version skew.

**Why minimal two-line fix?** Status parsing and result extraction in `anthropic.py` are unchanged; only the SDK entry points were wrong.

## Alternatives considered

| Option | Rejected because |
|--------|------------------|
| Add top-level `client.batches` shim in poller | Reinvents SDK surface; diverges from official API and other services |
| Mock-only fix in tests without code change | Does not unblock live G4 pipeline |
| Change pre-filter to a hypothetical top-level batches API | Submit path already works; would break working code |

## Files touched

- `services/batch-poller/app/clients/anthropic.py`
- `tests/test_batch_poller_anthropic_client.py` (new)

## Recovery

Rebuild and restart poller only: `docker compose up -d --build batch-poller`. Existing SQLite `submitted` batches with valid `external_batch_id` are picked up on startup scan; no DB reset required unless 48h timeout fires during extended downtime.

## Deferred

- Live Anthropic poll in integration gate (same deferral as M3 T5 decision log).
