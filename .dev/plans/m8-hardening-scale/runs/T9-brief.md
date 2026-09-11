## Completion Brief

- **Subtask ID · Status:** T9 · complete

- **Files changed:**
  - `tests/test_scraper_adapters.py`
  - `tests/test_scraper_loop.py`
  - `CHANGELOG.MD`

- **Tests run + result:**
  - `pytest tests/test_scraper_adapters.py tests/test_scraper_loop.py::test_registry_lists_all_expected_sources -v` → **3 passed**
  - Mutation check: temporarily removed `SemanticScholarAdapter` from `ADAPTER_REGISTRY` → both new tests **failed**; reverted before commit

- **Commit SHA:** `be02414`

- **Changelog entry location:** `CHANGELOG.MD` → section `## m8-hardening-scale — 2026-09-10` → T9 bullet

- **Decision log path:** N/A (standard tier)

- **Kill-criterion evidence:**
  - Stale `len(ADAPTER_REGISTRY) == 1` assertion removed — `test_registry_contains_all_expected_adapters` asserts seven-way `SourceEnum` membership instead
  - `test_source_adapter_contract` untouched and passing
  - `test_registry_lists_all_expected_sources` asserts membership for arxiv, github, huggingface, lesswrong, openreview, paperswithcode, semantic_scholar against live `ADAPTER_REGISTRY`
  - No edits to `registry.py`, adapter modules, or frozen-adjacent paths — staged diff contained only the three declared files

- **Summary:** Closed audit F2 by replacing the M2-era single-adapter registry test with `test_registry_contains_all_expected_adapters`, which asserts all seven landed adapters via `SourceEnum` membership and class presence. Added the previously declared-but-missing `test_registry_lists_all_expected_sources` in `test_scraper_loop.py`. Only test files and changelog were touched; `registry.py` was left unchanged. Both tests were mutation-checked and pass against the T8-bis seven-adapter registry at HEAD. T11 is unblocked to add `tests/test_scraper_adapters.py` to `verify-m8.sh`.
