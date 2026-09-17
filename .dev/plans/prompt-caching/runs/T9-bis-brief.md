**Completion Brief**

- **Subtask ID · Status:** T9-bis · complete
- **Files changed:** `services/pre-filter-worker/app/config.py`, `services/pre-filter-worker/app/loop.py`, `services/enrichment-batcher/app/config.py`, `services/enrichment-batcher/app/stage1_loop.py`, `services/enrichment-batcher/app/stage2_loop.py`, `tests/test_prefilter_loop.py`, `tests/test_enrichment_batcher_stage1_loop.py`, `tests/test_enrichment_batcher_stage2_loop.py`, `tests/test_enrichment_batcher_config.py`, `CHANGELOG.MD`, `.dev/decision-logs/prompt-caching/T9-bis-batch-amortization.md` — confirmed via `git status --porcelain` against staged/committed tree, subset of declared Files to touch.
- **Tests run:** `pytest tests/test_enrichment_batcher_config.py tests/test_prefilter_loop.py tests/test_enrichment_batcher_stage1_loop.py tests/test_enrichment_batcher_stage2_loop.py` → **37 passed**. Full `pytest tests/ -m "not heavy"` also run: 88 failed / 770 passed — confirmed via `git stash` against baseline that these failures (state-worker/vector-writer/query-api/sqlite areas, none touched by this diff) pre-exist and are unrelated to this subtask.
- **Commit SHA:** `c47248e`
- **Changelog entry location:** `CHANGELOG.MD`, under `## prompt-caching — 2026-09-12`, new `T9-bis (...)` bullet appended after the T3 entry.
- **Decision log path:** `.dev/decision-logs/prompt-caching/T9-bis-batch-amortization.md`
- **Kill-criterion evidence:**
 - Deadline reachable on every path (incl. permanent below-min inflow): `test_prefilter/stage1/stage2_cycle_submits_below_minimum_after_max_hold_deadline` — positive; mutation-checked by forcing `deadline_reached = False`, confirmed failing, reverted.
 - Hash/G3 abort cannot extend the hold indefinitely (C9): `test_prefilter/stage2_cycle_hash_abort_does_not_extend_hold_deadline`, `test_stage1_cycle_g3_abort_does_not_extend_hold_deadline` — mutation-checked by resetting `_hold_started_at` inside the abort branch, confirmed failing, reverted.
 - No `content_truncation.py` touch, no Anthropic per-request-limit assumption change: `git diff --name-only` shows neither file touched.
 - No `getattr`-papered defaults: all nine new keys parsed via the existing `_int_from_env` path in each service's `config.py`.
 - Amendment mechanical post-check: `pytest tests/test_enrichment_batcher_config.py` → 6/6 passed, only the two named assertions changed (`git diff` confirms).
- **Summary:** T9-bis picks up T9's HALTed scope from a clean slate, adding a per-gate minimum-volume/maximum-hold amortization mechanism to the pre-filter, enrichment-stage1, and enrichment-stage2 loops (raising the enrichment batch-size defaults 10→50 along the way), with the hold clock designed so a persistent hash/G3 abort can never convert a temporary block into permanent starvation — a property proven with mutation-checked negative tests in all three loop test files, plus the amendment-round-2 fix to the two pinned config-default assertions that originally caused T9's HALT.
