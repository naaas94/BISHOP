## Completion Brief

- **Subtask ID · Status:** T11 · complete
- **Files changed:** `services/pre-filter-worker/app/config.py`, `services/enrichment-batcher/app/config.py`, `tests/test_prefilter_config.py`, `tests/test_enrichment_batcher_config.py`, `.dev/llm-models-and-cache.md`, `.dev/caching_strategy.md`, `.dev/decision-logs/prompt-caching/T9-bis-batch-amortization.md`, `CHANGELOG.MD` — matches the declared Files to touch exactly (`git diff --name-only HEAD~1..HEAD`).
- **Tests run + result:** `pytest tests/test_prefilter_config.py tests/test_enrichment_batcher_config.py` → 18 passed (12 pre-existing + 6 new). `pytest tests/test_prefilter_loop.py tests/test_enrichment_batcher_stage1_loop.py tests/test_enrichment_batcher_stage2_loop.py` → 41 passed, unchanged. Declared full command `pytest tests/ -m "not heavy"` → 800 passed / 87 failed / 14 errors, consistent with the pre-existing baseline pollution T1-bis's decision log already documents (isolated reruns confirm none of the failures touch my files).
- **Commit SHA:** `31b68f19a6dd86efe880cc24becce876cf90dc77`
- **Changelog entry location:** `CHANGELOG.MD`, under `## prompt-caching — 2026-09-12`, appended as the last bullet in that section (own isolated hunk, verified via `git diff --cached CHANGELOG.MD` before commit).
- **Decision log path:** No new T11 log (standard tier). Supersession banner added to `.dev/decision-logs/prompt-caching/T9-bis-batch-amortization.md` immediately above the Chosen-approach 120-defaults table (first mention), per contract.

**Kill-criterion evidence:**
- Three production defaults read 30: `services/pre-filter-worker/app/config.py` and `services/enrichment-batcher/app/config.py` diffs (120→30 ×3); `pytest tests/test_prefilter_config.py tests/test_enrichment_batcher_config.py` — 18 passed, six new MAX_HOLD tests among them.
- Point-literal `== 30`: confirmed by reading the six new test bodies — all assert `== 30` / `== 45`, no interval.
- No loop files or loop-test injections in diff: `git diff --name-only` shows none of `loop.py`/`stage1_loop.py`/`stage2_loop.py`/their test files.
- No production path outside the two `config.py` files edited: confirmed by the file list above.
- First-mention banner: banner placed directly before the "Chosen approach" defaults table, not appended at file end (verified by reading the diff).
- D6: no `bishop_spec_0_6.md` edit; `.dev/caching_strategy.md` diff shows only a new prose paragraph in §12b, no checkbox in §18 touched.
- Row 20: no frozen path in diff.
- Runner ledger: `runs/ledger.md` / `runs/execution-summary.md` not touched.
- No compose-env workaround, no warmup/heartbeat/loop-logic change introduced.
- Mutation checks: reverted `PREFILTER_MAX_HOLD_MINUTES` default to 120 → `test_prefilter_max_hold_minutes_default` failed as expected, then reverted clean; swapped stage1's env-var name to stage2's key → `test_enrichment_stage1_max_hold_minutes_env_override` failed as expected (catches a real stage1/stage2 key-swap regression), then reverted clean — both confirmed via post-revert green reruns.

**Summary:** T11 retuned the three landed `MAX_HOLD_MINUTES` idle-flush defaults from 120 to 30 across pre-filter and both enrichment stages so a quiet trickle-path flush stays inside Anthropic's 1-hour cache TTL with margin, added and mutation-verified six new config tests closing the row-18 default/env-override gap for those keys without touching any loop logic, hold-clock semantics, batch-size/poll-interval assertions, or frozen/spec surfaces, updated the two docs and banner-superseded the relevant table in T9-bis's decision log, and landed the whole slice in a single clean commit (`31b68f1`) confined exactly to the packet's declared files.
