**Subtask ID:** T1 · **Status:** complete

**Files changed:** `services/scraper/app/config.py`, `tests/test_scraper_config.py`, `CHANGELOG.MD` (skill-mandated changelog; subset of Files to touch plus §3)

**Tests run + result:** `pytest tests/test_scraper_config.py` — 34 passed (includes `test_harvest_mill_interval_default`, `test_harvest_mill_interval_env_override`, `test_harvest_mill_interval_empty_env_raises`). Falsifier mutation-checked: swapping `_int_from_env` for `_optional_int_from_env(...) or 5` made `test_harvest_mill_interval_empty_env_raises` fail (`DID NOT RAISE ValueError`); reverted.

**Commit SHA:** `1948a72972c7961d2563eb3d9b32d17f5b875577`

**Changelog entry location:** `CHANGELOG.MD` → `## harvest-mill-loop — 2026-09-17` → T1 bullet

**Decision log path:** n/a (standard tier)

**Kill-criterion evidence:**
- No pre-existing `BISHOP_HARVEST_MILL*` source constant under another spelling: `rg "BISHOP_HARVEST_MILL"` before the edit hit only plan/packet prose; after the edit, `services/` has only `BISHOP_HARVEST_MILL_INTERVAL_SEC` in `config.py`.
- `_int_from_env` exists at `services/scraper/app/config.py:12` with signature `(name: str, default: int) -> int`.
- `docker-compose.yml` / `.env.example` untouched: not in `git show --name-only HEAD`; `rg BISHOP_HARVEST_MILL_INTERVAL` in both files is empty.

**Summary:** Added `BISHOP_HARVEST_MILL_INTERVAL_SEC = _int_from_env("BISHOP_HARVEST_MILL_INTERVAL_SEC", 5)` immediately after `BISHOP_HARVEST_QUERY_ID`, plus the two contract tests and an empty-env `ValueError` falsifier so the helper cannot silently become optional-or-default. `BISHOP_HARVEST_ENABLED` is unchanged. The mill loop itself is out of scope for T1.
