**Subtask ID** · **Status:** T2 · complete

**Files changed:**
- `services/scraper/app/loop.py`
- `tests/test_scraper_loop.py`
- `tests/test_harvest_github.py`
- `CHANGELOG.MD` (skill-required changelog; subset of Files to touch plus this file)

**Tests run + result:** `pytest tests/test_scraper_loop.py tests/test_scraper_config.py tests/test_harvest_github.py -k "not test_harvest_http_client_uses_30s_timeout" -q` → **50 passed, 1 deselected**. Mutation-check: `test_scrape_cycle_no_longer_calls_harvest_github_slices` failed after injecting `harvest_github_slices` into `loop.py`, then the mutation was reverted.

**Commit SHA:** `4411142f9b9e9b1184e5eefed8eb4226b0d884bc`

**Changelog entry location:** `CHANGELOG.MD` → `## harvest-mill-loop — 2026-09-17` → T2 bullet

**Decision log path:** n/a (standard tier)

**Kill-criterion evidence:**
- `rg "harvest_github_slices|BISHOP_HARVEST_ENABLED|BISHOP_HARVEST_SLICE_BUDGET_SEC" services/scraper/app/loop.py` → no hits
- `tests/test_scraper_loop.py` has no `loop_mod.harvest_github_slices` and no `patch.object(loop_mod, "BISHOP_HARVEST_ENABLED"` → no hits
- Scoped pytest fully green (50 passed; `test_harvest_http_client_uses_30s_timeout` deselected as specified)

**Summary:** Removed the harvest hitchhike from `scrape_cycle` (imports of `harvest_github_slices` / `BISHOP_HARVEST_ENABLED` / `BISHOP_HARVEST_SLICE_BUDGET_SEC` and the 90s `httpx` mill block), kept `import httpx` for `_scrape_adapter`, dropped the six `BISHOP_HARVEST_ENABLED` patches and deleted `test_scrape_cycle_harvest_failure_still_posts_discovered`, and added the source-grep falsifier. Repo-wide production `harvest_github_slices` is now only the definition in `harvest_github.py`; `harvest_slice_failed` remains only in plan/packet prose. The mill’s own asyncio loop is T3.
