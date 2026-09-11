## Completion Brief

- **Subtask ID · Status:** T11 · complete

- **Files changed:**
 - `scripts/verify-m8.sh`
 - `tests/test_verify_m8.py`
 - `CHANGELOG.MD`

- **Tests run + result:**
 - `python -m pytest tests/test_verify_m8.py -v --tb=short` — **12 passed**
 - `python -m pytest tests/test_state_worker_reading_status.py tests/test_state_worker_permanent_fail.py tests/test_query_api_routes_entry_actions.py tests/test_ui_escalations.py tests/test_ui_explorer.py tests/test_scraper_adapters.py -v --tb=short` — **22 passed**
 - Mutation falsifier: removed `tests/test_state_worker_reading_status.py` from script → `test_runs_all_m8_state_worker_test_modules` **failed**; reverted → **passed**

- **Commit SHA:** `f4a793b183c2f636e47e7ebc52c46c2b55beec97`

- **Changelog entry location:** `CHANGELOG.MD` → section `## m8-hardening-scale — 2026-09-10` (T11 bullet)

- **Decision log path:** N/A (standard tier)

- **Kill-criterion evidence:**
 - All seven required modules present in `scripts/verify-m8.sh` — verified by `test_runs_all_m8_*` + `test_runs_verify_m8_self_test` (12/12 green)
 - No `BISHOP_G6_MANUAL=1` in script — `test_does_not_export_g6_manual_flag` passed
 - `test_does_not_require_docker` and `test_exits_nonzero_on_failure` — passed (unchanged)
 - T9 landed — no `len(ADAPTER_REGISTRY)==1` in `tests/test_scraper_adapters.py`; `test_scraper_adapters.py` added to gate
 - No G6 structural ID edits, no `enrichment_prompts.py`, no frozen-adjacent paths touched — `git show --name-only HEAD` = 3 files only
 - Script/test tuple sync — same seven module strings in both files; mutation-checked

- **Summary:** T11 closes audit F3 by extending `scripts/verify-m8.sh` with three new pytest blocks (state-worker ops, query-api/UI, gate self-test) plus `tests/test_scraper_adapters.py` in the scraper block. `tests/test_verify_m8.py` now enforces gate completeness via `STATE_WORKER_TEST_MODULES`, `QUERY_UI_TEST_MODULES`, and `GATE_SELF_TEST_MODULES` tuples mirroring the existing `SCRAPER_TEST_MODULES` pattern. G6 stays structural-only with no `BISHOP_G6_MANUAL=1` reference. Committed as `f4a793b` with only the three declared files.
