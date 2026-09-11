# T3 brief

**Subtask ID:** T3  
**Status:** complete  
**Files changed:** `services/scraper/app/adapters/semantic_scholar.py`, `services/scraper/app/adapters/github.py`, `services/scraper/app/config.py` (positive drift), `tests/test_scraper_adapters_semantic_scholar.py`, `tests/test_scraper_adapters_github.py`, `tests/test_scraper_config.py` (positive drift), `CHANGELOG.MD`  
**Tests run:** 20 passed  
**Commit SHA:** `c6bd205b5d2270682a3e87cfb4d21df28e34b37f`  
**Changelog:** `CHANGELOG.MD` · `## m8-hardening-scale — 2026-09-10`  
**Decision log:** none  
**Kill-criterion evidence:** GitHub pagination capped (`BISHOP_GITHUB_MAX_PAGES` default 10); `test_fetch_manifest_stops_at_max_pages` mutation-checked.  
**Summary:** Semantic Scholar and GitHub adapters landed, export-only. Tokens wired in config.py (positive drift vs packet Files-to-touch, disclosed in changelog).
