**Subtask ID** · **Status:** T3 · complete

**Files changed:** `services/scraper/app/main.py`, `tests/test_scraper_loop.py`, `tests/test_harvest_github.py`, `.dev/decision-logs/ops/harvest-mill-loop.md`, `CHANGELOG.MD` (skill-mandated changelog; subset of Files to touch plus §3)

**Tests run + result:** `pytest tests/test_scraper_loop.py tests/test_scraper_config.py tests/test_harvest_github.py -q` — **53 passed**. Mutation-checked: removing `_mill_loop()` from `asyncio.gather` made `test_scheduler_invokes_scrape_release_and_mill` fail (`TimeoutError`); inserting `if BISHOP_HARVEST_ENABLED:` in `_mill_loop` made `test_mill_loop_does_not_gate_on_harvest_enabled` fail; both reverted.

**Commit SHA:** `6a5eadfec0d6654bffb8fa57a9df11887e9f1698`

**Changelog entry location:** `CHANGELOG.MD` → `## harvest-mill-loop — 2026-09-17` → T3 bullet

**Decision log path:** `.dev/decision-logs/ops/harvest-mill-loop.md`

**Kill-criterion evidence:**
- `harvest_github_slices` is a direct module-level import (`from app.harvest_github import harvest_github_slices`, no alias); `test_scheduler_invokes_scrape_release_and_mill` patches `main_mod.harvest_github_slices` and passed.
- Unscoped pytest fully green: 53 passed.
- Decision log exists at `.dev/decision-logs/ops/harvest-mill-loop.md` (in commit `6a5eadf`).
- `BISHOP_HARVEST_MILL_INTERVAL_SEC` already in `services/scraper/app/config.py`; `main.py` imports it and does not redefine it.

**Summary:** Added `_mill_loop` as a third `asyncio.gather` sibling in the existing scraper process so GitHub Search harvest walks on its own 5s rest / 90s slice cadence with a fresh 30s httpx client per tick, instead of waiting on the 6h scrape clock. Single call site, no `BISHOP_HARVEST_ENABLED` gate around the tick (`harvest_github_slices` still no-ops internally), `harvest_mill_failed` on exception then retry. Relocated the 30s-timeout source assertion to `main.py`; wiring test proves all three loops start.
