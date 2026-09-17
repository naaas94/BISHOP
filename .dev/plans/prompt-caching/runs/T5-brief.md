## Completion Brief

- **Subtask ID · Status:** T5 · complete

- **Files changed:**
 - `services/pre-filter-worker/app/anthropic_batch_client.py`
 - `services/pre-filter-worker/app/loop.py`
 - `tests/test_prefilter_anthropic_client.py`
 - `tests/test_prefilter_loop.py`
 - `CHANGELOG.MD`

- **Tests run + result:** `pytest tests/test_prefilter_anthropic_client.py tests/test_prefilter_loop.py -m "not heavy"` — **18 passed**

- **Commit SHA:** `eb9b873ae849e722817e7ad611cee4de8c4434a9`

- **Changelog entry location:** `CHANGELOG.MD` → section `## prompt-caching — 2026-09-12` → T5 bullet

- **Decision log path:** n/a (standard tier)

- **Kill-criterion evidence:**
 - **No plain-string `system`:** `test_build_requests_custom_id_encodes_source_id` asserts `isinstance(params["system"], list)`; `test_build_requests_retired_system_prompt_kwarg_raises_type_error` asserts retired kwarg raises `TypeError`
 - **Rubric abort before Anthropic:** `test_prefilter_cycle_rubric_hash_mismatch_aborts_with_critical_alert` (mutation-checked: disabling the guard makes this test fail)
 - **`emit_profile_hash_mismatch_alert` unchanged:** profile mismatch test still patches/alerts via existing path; no edits to `alerts.py`
 - **Line 73 replacement:** `test_build_requests_custom_id_encodes_source_id` asserts block shape + breakpoint on last block
 - **No inline `cache_control`:** grep over `services/pre-filter-worker/**` — zero hits; blocks come from `cached_system_blocks` only

- **Contract-binding evidence (selected):**
 - Row 1/9/10: `cached_system_blocks` via `test_build_requests_cache_breakpoint_on_last_block_only`, `test_build_requests_custom_id_encodes_source_id`
 - Row 5: `system_blocks` kwarg + retired `system_prompt` TypeError test
 - Row 11: `test_build_requests_all_entries_share_identical_system_blocks`
 - Row 12: `test_prefilter_cycle_rubric_hash_mismatch_aborts_with_critical_alert`
 - Row 21: pytest `-m "not heavy"` on declared test files
 - Adversarial micro-pass: mutation-checked rubric abort falsifier (`test_prefilter_cycle_rubric_hash_mismatch_aborts_with_critical_alert`); row 8 token-floor deferred to T10 (T2 sized annex; wired-prefix proof at closure)

- **Summary:** Pre-filter Anthropic batches now use cache key A: `params.system` is a two-block list `[profile_render, prefilter_rubric_body]` built through `cached_system_blocks()` with `cache_control` + `ttl: "1h"` on the last block only. `build_requests` / submit paths take `system_blocks` instead of the retired `system_prompt` string. `prefilter_cycle` verifies the rubric hash before submit (ERROR log + CRITICAL `rubric_hash_mismatch` alert on mismatch, matching the profile guard pattern without altering profile alert behaviour). Tests cover block shape, breakpoint placement, batch identity, retired-kwarg breakage, and a mutation-checked rubric-abort falsifier.
