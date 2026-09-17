# Known test failures (program hygiene)

Tracked failures from full-suite `pytest tests/` runs that are **not** introduced by the current milestone gate and do **not** indicate regressions in milestone-scoped behavior. Milestone handoffs reference this file instead of duplicating root-cause prose.

**Last verified:** 2026-09-14 · Python 3.14 · pytest 8.4.2 · win32

**2026-09-14 full suite:** 811 passed, 87 failed, 14 errors, 4 skipped. Three classes — see OPEN-002 (collision, ~98 tests), OPEN-021 (M5 hold gate, 2 isolated), OPEN-022 (compose override, 1 isolated). OPEN-001 is **closed**.

Also tracked in `.dev/still_open.md` (program backlog).

---

## OPEN-001 — escalations router expects single `error_log` row

| Field | Value |
|-------|-------|
| **Status** | **Closed 2026-09-13** — assertion is now `len(error_log) == 2` |
| **Test** | `tests/test_state_worker_routers_escalations.py::test_escalations_returns_flagged_entry_with_error_log` |
| **Introduced by** | M1 T8 §14.3 alert dual-write (`emit_alert` sibling row) — test predates amendment |
| **Milestone blocking** | No — M2–M5 gates exclude this module; handoffs record as inherited hygiene |
| **Implementation verdict** | **Correct** — failure was stale test expectation, not router/transition bug |

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

**Closed:** Option A landed (2026-09-13). Historical write-up kept so handoffs that cite this file still resolve.

---

## OPEN-002 — monolithic pytest `app` namespace collision

| Field | Value |
|-------|-------|
| **Status** | Open — mechanism re-diagnosed 2026-09-14 |
| **Tests** | ~98 later tests across state-worker / vector-writer / query-api models (not the dashboard tests themselves) |
| **Milestone blocking** | No — `verify-m*.sh` slices stay green |
| **Implementation verdict** | **Harness** — not a product regression |

### Symptom

`python -m pytest tests/ -q` → 87 failed + 14 errors. Dominant messages: `No module named 'app.db'` / `app.index_entry` / `app.transitions`; wrong-service `app.config` / `app.models` attributes.

### Root cause (2026-09-14)

1. Every service is imported as top-level `app`. No `conftest.py` isolation.
2. **Poisoners:** `tests/test_query_api_routes_entry.py` and `tests/test_query_api_stats.py` wipe `app.*`, import query-api, leave it on `sys.path` and in `sys.modules`. Search/UI tests save-restore-and-pop and do not poison.
3. **Namespace vs regular package:** `services/state-worker/app` and `services/vector-writer/app` have no `__init__.py`. query-api does. Once query-api is on `sys.path`, `import app` binds to query-api even if vector-writer is earlier. Reproduced outside pytest; `importlib.invalidate_caches()` does not help.
4. Victims re-resolve dotted names at fixture/call time (`monkeypatch.setattr("app.db.SQLITE_DB_PATH", ...)`, `import app.index_entry`). Collection-time bindings still work.

Isolation: contract alone 26 passed; entry+contract 11F+12E; stats+contract same; search+contract and UI+contract all pass; entry+vector-writer-loop 9F (`app.index_entry`).

Dashboard stats/UI tests pass. Stats copied the leaky entry pattern → additional poisoner, same class.

### Fix (when hygiene is scheduled)

Make entry/stats use the search/UI helper. Optionally add `app/__init__.py` to state-worker and vector-writer. Full write-up: `.dev/still_open.md` OPEN-002.

---

## OPEN-021 — M5 integration stale vs T9-bis hold gate

| Field | Value |
|-------|-------|
| **Status** | Open |
| **Tests** | `tests/test_m5_integration.py::test_m5_e2e_five_entries_reach_vector_write_queued_with_enrichment_fields`, `::test_m5_startup_scan_registers_enrichment_stage1_in_flight` |
| **Milestone blocking** | No — M5 verify slice likely excludes or still passes other M5 tests |
| **Implementation verdict** | **Stale fixture** — product hold gate is correct; tests fail **in isolation** |

### Symptom

`assert len(matches) == 1` with `matches == []` at `_in_flight_enrichment_batch` after `stage1_cycle`.

### Root cause

T9-bis set `ENRICHMENT_STAGE1_MIN_BATCH_SIZE` default **10**. M5 e2e seeds **5** entries; startup scan seeds **1**. One cycle, no hold-clock advance → no submit → no in-flight batch. Unit tests already monkeypatch min to 1.

### Fix

Override min to 1 on `integration_client`, or raise `_ENTRY_COUNT` to 10 and override the 1-entry test. See `.dev/still_open.md` OPEN-021.

---

## OPEN-022 — compose override breaks default-discovery test

| Field | Value |
|-------|-------|
| **Status** | Open |
| **Test** | `tests/test_sqlite_named_volume.py::test_default_compose_discovery_ignores_named_volume_override` |
| **Milestone blocking** | No |
| **Implementation verdict** | **Environment / tracked override** — fails **in isolation** |

### Symptom

`assert default_cfg == base_cfg` — `docker compose config` (auto-loads `docker-compose.override.yml`) ≠ `-f docker-compose.yml`.

### Root cause

Tracked temporary `docker-compose.override.yml` remounts `sqlite_live`. Compose auto-loads that filename. The named-volume overlay is *not* auto-loaded and is not the trigger.

### Fix

Retire/untrack the override (incident FU-002) or narrow the test to only forbid `docker-compose.override.named-volume.yml` being auto-discovered. See `.dev/still_open.md` OPEN-022.
