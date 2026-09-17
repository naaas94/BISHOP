## HALT Report

**Subtask ID:** T1

**HALT reason:** Kill criterion — "A kill criterion implies observable behavior (test, scan, scripted check) but cannot be satisfied or falsified within Files to touch and Contract bindings" (also matches "You find coupling to another subtask the DAG did not declare").

**What I discovered:** §2 row 9 ("Single emitter") is bound to T1 and its packet-specified falsifier is exact: `tests/test_prompt_cache.py::test_no_inline_cache_control_literals` must tree-grep `bishop_shared/**` and `services/**` (excluding `prompt_cache.py`) for any `cache_control` dict literal and assert **zero hits**, with no legacy carve-out named anywhere in §2 or the Deferred-rows table (rows 23–25 don't cover this).

I implemented that test exactly as specified and it fails today: `bishop_shared/enrichment_prompts.py::build_call2_system_prompt` (lines 66–70) already constructs an inline `{"type": "ephemeral"}` `cache_control` literal, and it is **live production code** — `services/enrichment-batcher/app/anthropic_batch_client.py:94` calls it on the real Call 2 wire path today. That module and its caller are not in T1's Files to touch; per §2 row 5, Call 2's `build_stage2_requests` (which supersedes this function) is owned by **T7**. So the row-9 falsifier T1 is contractually required to ship green cannot pass without either (a) editing files scoped to T7, or (b) unilaterally narrowing row 9's stated grep scope to exempt this legacy call site — both are prohibited (no editing outside Files to touch; no self-adjudicated contract narrowing).

**What the orchestrator needs to decide:** One of:
1. Re-scope row 9's falsifier (a plan/contract amendment) to exclude specific pre-migration legacy call sites, naming T7 as the landing gate that closes the exemption when it migrates Call 2 off `build_call2_system_prompt`; or
2. Move ownership/timing of the row-9 sweep test itself from T1 to T10 (post-migration closure), since it can only be meaningfully green after T5/T6/T7 land; or
3. Expand T1's Files-to-touch to also migrate `enrichment_prompts.py`/`anthropic_batch_client.py` now (which conflicts with T7's declared ownership of that surface and its own contract row 5 obligations, so likely undesirable).

**Partial work, if any (uncommitted, in the working tree):**
- New: `bishop_shared/prompt_cache.py`, `bishop_shared/rubric_assets.py`, `scripts/rubric_hash.py`, `config/prompts/README.md`, `tests/test_prompt_cache.py`, `tests/test_rubric_assets.py`
- Modified: `bishop_shared/profile_renderer.py` (added `include_output` kwarg, byte-identical default confirmed), `tests/test_profile_renderer.py` (extended), `services/pre-filter-worker/Dockerfile`, `services/enrichment-batcher/Dockerfile` (added `COPY config/prompts`), `services/pre-filter-worker/requirements.txt`, `services/enrichment-batcher/requirements.txt`, `services/batch-poller/requirements.txt`, `pyproject.toml` (anthropic pin `>=0.40` → `>=0.100`)
- `config/profiles/professional_v1.2.0_soft_launch.yaml` was already tracked and committed at HEAD (packet's "untracked → git add" premise was stale; `git ls-files` confirms it's tracked, no action needed).
- All of the above pass their own tests (`pytest tests/test_prompt_cache.py tests/test_rubric_assets.py tests/test_profile_renderer.py` → 38 passed) **except** `test_no_inline_cache_control_literals`, which is the one failing due to the discovered coupling above.
- Nothing has been committed (working tree left dirty per HALT protocol); the checkout is otherwise unrelated to AGENTS.md/.cursor/rules changes already present at session start.
