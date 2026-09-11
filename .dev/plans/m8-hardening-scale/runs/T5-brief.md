# T5 brief

**Subtask ID:** T5  
**Status:** complete  
**Files changed:** `services/state-worker/app/transitions.py`, `services/state-worker/app/routers/entries.py`, `services/state-worker/app/models/http.py`, `tests/test_state_worker_reading_status.py`, `tests/test_state_worker_permanent_fail.py`, `tests/test_state_worker_contract.py`, `CHANGELOG.MD`, `.dev/decision-logs/m8-hardening-scale/T5-state-worker-ops.md`  
**Tests run:** `pytest tests -k state_worker` — 157 passed  
**Commit SHA:** `97c963b909dc21fad88681c987848a6dc5f0ec8c`  
**Changelog:** `CHANGELOG.MD` · `## m8-hardening-scale — 2026-09-10`  
**Decision log:** `.dev/decision-logs/m8-hardening-scale/T5-state-worker-ops.md`  
**Kill-criterion evidence:** Routes register; `reading_status` column present; flags 1–2 implemented; 409 guards mutation-checked.  
**Summary:** state-worker `PATCH /entries/{source_id}/reading-status` and `POST /entries/permanent-fail` landed. Existing retry/failed semantics unchanged.
