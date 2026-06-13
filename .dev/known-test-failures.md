# Known test failures (program hygiene)

Tracked failures from full-suite `pytest tests/` runs that are **not** introduced by the current milestone gate and do **not** indicate regressions in milestone-scoped behavior. Milestone handoffs reference this file instead of duplicating root-cause prose.

**Last verified:** 2026-06-13 · Python 3.14.2 · pytest 9.0.2 · win32

---

## OPEN-001 — escalations router expects single `error_log` row

| Field | Value |
|-------|-------|
| **Test** | `tests/test_state_worker_routers_escalations.py::test_escalations_returns_flagged_entry_with_error_log` |
| **Introduced by** | M1 T8 §14.3 alert dual-write (`emit_alert` sibling row) — test predates amendment |
| **Milestone blocking** | No — M2–M5 gates exclude this module; handoffs record as inherited hygiene |
| **Implementation verdict** | **Correct** — failure is stale test expectation, not router/transition bug |

### Symptom

Full suite: **368 passed, 1 failed** (~19s).

```
AssertionError: assert 2 == 1
 +  where 2 = len([{'error_class': 'HTTPStatusError', ...}, {'error_class': 'ALERT', ...}])
```

At line 103 the test asserts `len(entries[0]["error_log"]) == 1` after `GET /escalations`.

### Seed scenario

`_seed_escalation` ingests one manifest row, then calls `record_failure` with:

- `state_at_failure=SCRAPE_QUEUED`
- `error_class="HTTPStatusError"`
- `http_status=404`
- `message="Not found"`
- `is_retriable=True`

### Root cause

1. **404 triggers escalation despite `is_retriable=True`.**  
   `ESCALATION_HTTP_STATUSES = {401, 403, 404, 422}` in `services/state-worker/app/transitions.py`. Branch `elif not is_retriable or http_status in ESCALATION_HTTP_STATUSES` sets `target = ESCALATION_FLAGGED` and `alert_type = "escalation_flagged"`.

2. **`record_failure` dual-writes per §14.3.**  
   It inserts the operational failure row (`HTTPStatusError`), then calls `emit_alert`, which inserts a second `error_log` row with `error_class = "ALERT"`. See `.dev/decision-logs/m1-state-kernel/T8-alert-logging.md` — sibling rows are intentional; mutating the failure row to ALERT was explicitly rejected.

3. **`GET /escalations` returns all rows.**  
   `services/state-worker/app/routers/escalations.py` selects `SELECT * FROM error_log WHERE source_id = ? ORDER BY timestamp` with no filter on `error_class`. Both rows are correct API output for an escalated entry.

### What already passes

- `tests/test_state_worker_alerts.py` — `emit_alert` dual-write, `record_failure` → ALERT row on escalation paths
- Milestone gates (G2, M2–M5 slices) — do not include `test_state_worker_routers_escalations.py`

### Fix options (when hygiene is scheduled)

**Option A (recommended):** Update the escalations router test to expect two rows and assert both:

- `error_log[0]["error_class"] == "HTTPStatusError"` and `message == "Not found"`
- one sibling with `error_class == "ALERT"` and the same `message`

**Option B:** Filter `ALERT` rows in the escalations router if the UI panel should show only operational failures — requires spec/UI confirmation; not justified by current §14.3 decision log.

### References

- `.dev/decision-logs/m1-state-kernel/T8-alert-logging.md`
- `.dev/plans/m4-content/handoff.md` §8.1 (first full-suite recording)
- `.dev/plans/m5-enrichment/handoff.md` §8.1, §8.4
- `.dev/audits/2026-06-12-m2-discovery.md` — inherited failure note
