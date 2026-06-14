# Batch API custom_id encoding

**Date:** 2026-06-13  
**Scope:** pre-filter-worker, enrichment-batcher, batch-poller  
**Trigger:** Live pre-filter-worker logs showed `model_string_fatal` on every `messages.batches.create` 400 while G3 (`messages.create`) passed.

## Problem

BISHOP canonical `source_id` values use `source:raw_id` (e.g. `arxiv:2406.00001`, `github:owner/repo`). Pre-filter and enrichment batch submitters set Anthropic `requests[].custom_id` to the raw `source_id`.

Anthropic Batch API requires:

```
^[a-zA-Z0-9_-]{1,64}$
```

Colon, dot, and slash in canonical IDs violate that constraint. The API returns HTTP 400 `invalid_request_error` on `custom_id`, not on the model string.

`submit_*_batch_or_fatal` treated **any** `BadRequestError` as `model_string_fatal`, which masked the real failure in Docker logs. G3 only probes `messages.create`, so it cannot catch Batch-only validation rules.

## Decision

Introduce shared bijective encoding in `bishop_shared/batch_custom_id.py`:

- **Encode** at batch submit: `source_id_to_batch_custom_id(source_id)` → URL-safe base64 without padding.
- **Lookup** at batch poll: index Anthropic results by encoded `custom_id`, keyed from `batch.source_ids` via the same encode function.
- **Decode** helper (`batch_custom_id_to_source_id`) for tests and debugging only; production poll path never needs reverse lookup without the batch's `source_ids` list.

Classify HTTP 400 batch submit errors in `bishop_shared/anthropic_batch_errors.py` (`batch_custom_id_rejected` vs `model_string_fatal` vs `batch_submit_rejected`).

## Rationale

**Why base64url, not character substitution?** A naive `:` → `_`, `.` → `_` mapping is human-readable but not bijective when `raw_id` can contain underscores (GitHub) or when multiple punctuation types collapse to `_`. Base64url is reversible, uses only `[A-Za-z0-9_-]`, and keeps typical arxiv/github IDs well under the 64-character cap.

**Why not change canonical `source_id`?** `source_id` is the primary key across SQLite, DuckDB, LanceDB, BM25 pickles, and REST contracts. Changing it would ripple through the entire system for an Anthropic wire-format constraint.

**Length bound:** Encoding supports `source_id` strings up to 48 UTF-8 bytes (≈64 base64 chars). Canonical IDs in spec are far shorter; exceeding the limit raises `ValueError` at submit time.

## Alternatives considered

| Option | Rejected because |
|--------|------------------|
| Keep `custom_id = source_id`, change G3 to probe batches | Does not fix invalid wire payload |
| Store `custom_id → source_id` map on `BatchRecord` | Extra schema + migration for a deterministic encoding |
| Hash `source_id` (SHA256 prefix) | Not reversible without side table |

## Files touched

- `bishop_shared/batch_custom_id.py` (new)
- `bishop_shared/anthropic_batch_errors.py` (new)
- `services/pre-filter-worker/app/anthropic_batch_client.py`
- `services/enrichment-batcher/app/anthropic_batch_client.py`
- `services/batch-poller/app/loop.py`
- Model docstrings in pre-filter-worker and enrichment-batcher

## Deferred

- G3 extension with a minimal `messages.batches.create` smoke probe (encode one dummy `custom_id`).
- Release `RELEVANCE_QUEUED` / enrichment QUEUED claims when batch submit returns 400 (entries currently wait for lock-state sweep).
