# T6 brief

**Subtask ID:** T6  
**Status:** complete  
**Files changed:** query-api entries router, search.py, sqlite_reader.py; UI main + templates (escalations, explorer, entry_detail); tests for entry actions, UI escalations/explorer, search orchestrator; CHANGELOG.MD  
**Tests run:** 34 passed  
**Commit SHA:** `fb7e7e2180cbae1c15ef20a295c722c199584ad9`  
**Changelog:** `CHANGELOG.MD` · `## m8-hardening-scale — 2026-09-10`  
**Kill-criterion evidence:** T5 routes at 97c963b; SQLite reading_status filter mutation-checked; UI does not call state-worker.  
**Summary:** query-api proxies for retry / permanent-fail / reading-status; UI `/escalations`, `/explorer`, entry reading-status. Search filter uses SQLite.
