# T1-bis brief

**Subtask ID:** T1-bis  
**Status:** complete

- **Files changed:**
  - `bishop_shared/scraper_config.py` (new)
  - `services/scraper/app/rate_limit.py`
  - `tests/test_scraper_config_shared.py` (new)
  - `tests/test_scraper_rate_limit.py`
  - `tests/test_scraper_arxiv_adapter.py`
  - `CHANGELOG.MD`
  - `.dev/decision-logs/m8-hardening-scale/T1-adapter-foundation.md`
  - `services/scraper/app/config.py` and `services/scraper/app/adapters/arxiv.py` left byte-unchanged
- **Tests run:** `tests/test_scraper_config_shared.py`, `tests/test_scraper_rate_limit.py`, `tests/test_scraper_arxiv_adapter.py`, `tests/test_scraper_config.py` — 38 passed. Frozen-adjacent suite 79 passed, 1 skipped.
- **Commit SHA:** `7fd52b97f4ba5a54e3f7299cd85c0ea1e10977d9`
- **Changelog entry location:** `CHANGELOG.MD`, `## m8-hardening-scale — 2026-09-10`
- **Decision log path:** `.dev/decision-logs/m8-hardening-scale/T1-adapter-foundation.md`
- **Kill-criterion evidence:** SourceEnum keys match BACKFILL_CONFIG / schedules / rate limits (pytest). 7-day incremental pin untouched (`arxiv.py` empty diff). No T8 env keys. Frozen-adjacent `git diff` empty. Flag-4 falsifier mutation-checked then reverted.
- **Summary:** Landed shared `BACKFILL_CONFIG` (§18.2, 7 sources), `SOURCE_RATE_LIMITS`, and `SOURCE_SCHEDULE_INTERVAL_SEC` without changing incremental ArXiv window or the category gate. Runtime wiring deferred to T8 / T2–T4.
