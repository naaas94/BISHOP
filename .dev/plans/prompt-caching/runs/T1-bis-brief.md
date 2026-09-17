## Completion Brief

- **Subtask ID · Status:** T1-bis · **complete**
- **Files changed:** `bishop_shared/prompt_cache.py` (new), `bishop_shared/rubric_assets.py` (new), `scripts/rubric_hash.py` (new), `config/prompts/README.md` (new), `tests/test_prompt_cache.py` (new), `tests/test_rubric_assets.py` (new, includes one added falsifier), `bishop_shared/profile_renderer.py` (modified), `tests/test_profile_renderer.py` (modified), `services/pre-filter-worker/Dockerfile`, `services/enrichment-batcher/Dockerfile`, `services/pre-filter-worker/requirements.txt`, `services/enrichment-batcher/requirements.txt`, `services/batch-poller/requirements.txt`, `pyproject.toml` (all modified), `CHANGELOG.MD` (new section + bullet), `.dev/decision-logs/prompt-caching/T1-bis-cache-and-rubric-contract.md` (new). `AGENTS.md` and `.cursor/rules/windows-file-tools.mdc` deliberately left unstaged.
- **Tests run + result:** `pytest tests/test_prompt_cache.py tests/test_rubric_assets.py tests/test_profile_renderer.py` → 39 passed, 1 expected-red (`test_no_inline_cache_control_literals`, exactly one offender: `bishop_shared/enrichment_prompts.py`). Full suite `pytest tests/ -m "not heavy"` → 86 failed, 744 passed, 3 skipped, 1 deselected, 14 errors — differential stash/restore confirmed 85 failures + 14 errors pre-exist on the baseline tree (unrelated `state-worker`/`vector-writer`/`query-api` test-pollution), net-new is +21 passed / +1 expected-red. `docker build -f services/pre-filter-worker/Dockerfile .` → exit 0.
- **Commit SHA:** `8d9af018faaa0c09bb96d7a5daf34fd2f0d928d3`
- **Changelog entry location:** `CHANGELOG.MD`, new `## prompt-caching — 2026-09-12` section, T1-bis bullet.
- **Decision log path:** `.dev/decision-logs/prompt-caching/T1-bis-cache-and-rubric-contract.md`
- **Kill-criterion evidence:**
 - `cached_system_blocks` no-aliasing invariant: `test_two_calls_are_equal_but_not_aliased` (green).
 - `anthropic>=0.100` satisfied in-env: `python -c "import anthropic; print(anthropic.__version__)"` → `0.100.0`.
 - Dockerfile builds: `docker build -f services/pre-filter-worker/Dockerfile .` → exit 0, `COPY config/prompts` layer present.
 - Soft-launch profile tracked at HEAD: `git ls-files config/profiles/professional_v1.2.0_soft_launch.yaml` → non-empty.
 - `render_profile_prompt` default byte-identical: `test_default_render_is_byte_identical_to_pre_change_pin` (green, pinned length/SHA-256).
 - No row-20 frozen path touched: staged-file enumeration (`git status --porcelain`) contains none of the row-20 list.
 - Row-9 specific expected-red: `pytest tests/test_prompt_cache.py::test_no_inline_cache_control_literals` → 1 failed, offender = `bishop_shared\enrichment_prompts.py` only.
 - Full suite: counts above; only row-9 test is a net-new red.
 - Commit exists before reporting done: SHA above.
- **Summary:** T1-bis consumed T1's halted-but-uncommitted working tree unchanged, re-verified every original kill criterion (SDK ttl support, Dockerfile bake, tracked profile file, byte-identical default render) plus the amendment's own row-9 falsifier (confirmed red with exactly the one expected, already-known offender in `enrichment_prompts.py`, owned by T7), ran a stash/restore differential to prove the full suite's 85 other failures are pre-existing environment noise rather than caused by this diff, added and mutation-checked one adversarial falsifier for an uncovered `scripts/rubric_hash.py` error path, and committed the entire slice (`8d9af01`) so T2, T3, T4, T8, and T9 can now proceed.
