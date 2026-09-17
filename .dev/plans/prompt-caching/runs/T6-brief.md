## Completion Brief

- **Subtask ID · Status:** T6 · complete
- **Files changed:** `bishop_shared/enrichment_prompts.py`, `services/enrichment-batcher/app/anthropic_batch_client.py`, `services/enrichment-batcher/app/stage1_loop.py`, `tests/test_enrichment_prompts.py`, `tests/test_enrichment_batcher_stage1_loop.py`, `CHANGELOG.MD`, `.dev/decision-logs/prompt-caching/T6-call1-wiring.md` — exactly the packet's declared Files to touch, confirmed via `git status --porcelain` before commit.
- **Tests run + result:** `pytest tests/test_enrichment_prompts.py tests/test_enrichment_batcher_stage1_loop.py` → 24 passed. Full suite `pytest tests/ -m "not heavy"` before vs. after this diff: identical 88 failed / 14 errors baseline (pre-existing state-worker/vector-writer test-isolation pollution, confirmed via stash/pop comparison); 774→784 passed, the +10 being exactly this subtask's own new tests. Mutation check: inverted `_verify_rubric_hash`'s comparison → 4 rubric-abort falsifiers failed as expected, then reverted and re-confirmed green.
- **Commit SHA:** `ba49bb1` — "T6 (prompt-caching): wire enrichment Call 1 to cached system blocks (cache key B)"
- **Changelog entry location:** `CHANGELOG.MD`, under `## prompt-caching — 2026-09-12`, new `- T6 (...)` bullet.
- **Decision log path:** `.dev/decision-logs/prompt-caching/T6-call1-wiring.md`
- **Kill-criterion evidence:**
 - `_profile_render_hash` did not start calling `compute_profile_hash` — proven by `test_profile_render_hash_no_recompute_regression` + `test_profile_render_hash_does_not_import_compute_profile_hash`, and confirmed by diff (function body untouched).
 - No CRITICAL alert on rubric abort — proven by `test_stage1_cycle_rubric_hash_mismatch_aborts_without_anthropic_call` asserting no record with `levelno >= CRITICAL`.
 - Appendix A schema text/taxonomy unchanged — confirmed by `git diff` showing the f-string body is byte-identical, only reassigned to a variable; `test_call1_includes_taxonomy` re-pointed at `blocks[0]["text"]` per the packet's own instruction.
 - Row 9 (no inline `cache_control` literal in my diff) — `enrichment_prompts.py` only calls `cached_system_blocks()`, never constructs the dict itself; the pre-existing red offender (`build_call2_system_prompt`, T7's scope) is unchanged and remains T10's closure item.

This subtask converted enrichment Call 1's system prompt to Anthropic's cache-key-B content-block shape (`[call1_system, call1_rubric]`, single breakpoint on the last block) and added stage 1's first rubric hash-or-abort gate — log-only per the row 12 asymmetry, with the existing hold-clock no-starvation discipline preserved — while leaving `build_requests`'s frozen signature, `_profile_render_hash`'s no-recompute behavior, and T7's `build_call2_system_prompt` completely untouched.
