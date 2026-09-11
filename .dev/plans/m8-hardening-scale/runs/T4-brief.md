# T4 brief

**Subtask ID:** T4  
**Status:** complete  
**Files changed:** `services/scraper/app/adapters/openreview.py`, `services/scraper/app/adapters/lesswrong.py`, `tests/test_scraper_adapters_openreview.py`, `tests/test_scraper_adapters_lesswrong.py`, `.dev/decision-logs/m8-hardening-scale/T4-openreview-lesswrong.md`, `CHANGELOG.MD`  
**Tests run:** 20 passed, 1 skipped (live probe opt-in)  
**Commit SHA:** `3a4dd2f0b21261132a7c513b74f379193c4a88c9`  
**Changelog:** `CHANGELOG.MD` · `## m8-hardening-scale — 2026-09-10`  
**Decision log:** `.dev/decision-logs/m8-hardening-scale/T4-openreview-lesswrong.md`  
**Kill-criterion evidence:** OpenReview mocked URL test passes; LessWrong live probe succeeded (GET); flag 3 applied; registry untouched.  
**Summary:** OpenReview search adapter and GET-only LessWrong adapter landed after a successful GraphQL probe. T8 remains sole registry merger.
