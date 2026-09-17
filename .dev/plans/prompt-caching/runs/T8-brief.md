## Completion Brief

- **Subtask ID · Status:** T8 · complete

- **Files changed:**
 - `services/batch-poller/app/clients/anthropic.py`
 - `services/batch-poller/app/models.py`
 - `services/batch-poller/app/loop.py`
 - `tests/test_batch_poller_anthropic_client.py`
 - `tests/test_batch_poller_loop.py`
 - `tests/test_batch_poller_enrichment.py`
 - `CHANGELOG.MD`

- **Tests run + result:**
 - `pytest tests/test_batch_poller_anthropic_client.py tests/test_batch_poller_loop.py tests/test_batch_poller_enrichment.py -m "not heavy" -v` → **33 passed**
 - Full suite `pytest tests/ -m "not heavy"` → batch-poller tests green; 86 failures pre-existing (state-worker/vector-writer isolation, expected-red `test_no_inline_cache_control_literals` from T1-bis)

- **Commit SHA:** `c8fc67d6253dcde7f4959d95e9ca6f674e76aa06`

- **Changelog entry location:** `CHANGELOG.MD` under `## prompt-caching — 2026-09-12`

- **Decision log path:** n/a (standard tier)

- **Kill-criterion evidence:**
 - **LogRecord collision:** `test_cache_usage_log_keys_do_not_collide_with_log_record_reserved` — five keys disjoint from reserved attributes
 - **Three-stage seam (model → extract → log):** `test_anthropic_batch_result_item_round_trip_with_usage`, `test_fetch_batch_results_extracts_message_usage`, `test_poll_once_pre_filter_completion_logs_cache_usage_keys` (+ stage1/stage2 caplog tests)
 - **Batch-level only (no per-entry custom_id re-derive):** `aggregate_batch_cache_usage()` sums `raw_results` list directly; mutation-checked via `test_aggregate_batch_cache_usage_sums_across_results`
 - **No BatchRecord/schema change:** diff confined to poller model/client/loop only; no `domain.py` / `alembic/**` touched
 - **Zero-cache warning:** `test_poll_once_pre_filter_zero_cache_usage_emits_warning` (positive) + `test_poll_once_pre_filter_nonzero_cache_usage_skips_zero_warning` (negative)

- **Summary:** T8 wires Anthropic prompt-cache observability into the batch-poller: `AnthropicBatchResultItem` gains four optional usage fields, `fetch_batch_results` extracts them from `message.usage`, `aggregate_batch_cache_usage` sums at batch level, and all three `_handle_*_complete` handlers log `cache_read_tokens`, `cache_write_tokens`, `input_tokens`, `output_tokens`, and `cache_hit_ratio` via `_log_batch_cache_usage`, emitting a `cache_read_zero` warning when both cache counters are zero. This gives G1 a log-based falsifier for cache enablement without any schema or wire changes.
