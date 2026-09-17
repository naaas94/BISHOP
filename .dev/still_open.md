# Still open — program backlog

Consolidated open and half-open items from audits (M0–M7), milestone handoffs, decision logs, `CHANGELOG.MD`, ops notes, and live validation. Audit debt and ops follow-ups only — milestone feature work lives in milestone plans, not here.

**Machine-readable product index:** repo-root `product-backlog.yaml` (PB-* ids; OPEN-* / FU-* are foreign keys into this file and `incident-log.yaml`). Harvest mill (PB-011) is product, not this hygiene list — pickup `harvest-pool-next.md`.

**Last verified:** 2026-09-14 · Python 3.14 · pytest 8.4.2 · win32 · HEAD

**How gates work:** Milestone exit criteria are enforced by `scripts/verify-m<N>.sh` slices (often with subprocess isolation). Monolithic `pytest tests/` is **not** a binding gate but is the hygiene bar for “program green.”

**Current monolithic suite (sanity check, 2026-09-14):** 811 passed, 87 failed, 14 errors, 4 skipped — still dominated by OPEN-002 (`app` namespace collision). Two isolated hold-gate lags (OPEN-021) and one compose-override discovery fail (OPEN-022) are **not** collision. OPEN-001 is closed (escalations test now expects the ALERT sibling).

**M7 binding gate:** `scripts/verify-m7.sh` equivalent → **136 passed** (green).

---

## Quick index

| ID | Priority | Status | One-liner |
|----|----------|--------|-----------|
| [OPEN-001](#open-001--escalations-test-stale-error_log-count) | P0 | **Closed 2026-09-13** | Escalations test now asserts `len(error_log) == 2` |
| [OPEN-002](#open-002--monolithic-pytest-app-namespace-collision) | P0 | Open | Full `pytest tests/` breaks after multi-service `app` imports |
| [OPEN-003](#open-003--m6-integration-sysmodules-leak) | P0 | Half-open | M6 harness teardown insufficient; poisons state-worker config test |
| [OPEN-004](#open-004--charter-g4-full-e2e-arxiv--indexed) | P1 | Open | Manual charter exit gate; not automated |
| [OPEN-007](#open-007--sqlite-hardening-post-corruption) | P1 | Mostly closed | Hardening landed 2026-09-11; named volume / query-api HTTP-only remain |
| [OPEN-008](#open-008--batch-claim-release-on-failures) | P2 | Half-open | Orphan/residual claims on submit 400 / register 409 |
| [OPEN-009](#open-009--orphan-external-anthropic-batch) | P2 | Waived-deferred | Submit succeeds, state-worker register fails — no cancel |
| [OPEN-010](#open-010--live-g3-anthropic-model-probe) | P2 | Open | `verify-g3.sh` SKIPs without API key |
| [OPEN-011](#open-011--env-example-host-ports) | P2 | Open | Fresh onboarding: compose publishes no host ports |
| [OPEN-012](#open-012--architecture-folder-stale) | P2 | Open | Post-M7 `.dev/architecture/bishop/` not refreshed |
| [OPEN-013](#open-013--live-docker-compose-smoke) | P3 | Waived-deferred | Never automated M3–M7; manual ops validation |
| [OPEN-014](#open-014--verify-g2-omits-alert-tests) | P3 | Open | Alert proof outside G2 script path |
| [OPEN-015](#open-015--scraper-retry-exhausted-loop-test) | P3 | Deferred | Loop branch untested; envelope test exists |
| [OPEN-016](#open-016--m1-unwired-alert-types) | P3 | Deferred | T8 taxonomy partially wired |
| [OPEN-017](#open-017--domain-only-search-bm25-scope) | P3 | Deferred | T4: BM25 not scoped when only `domain` filter set |
| [OPEN-018](#open-018--sqlite-wal-contention-test) | P3 | Mostly closed | Multi-process WAL harness landed; Windows bind-mount still untestable |
| [OPEN-019](#open-019--misc-coverage--docs-gaps) | P4 | Mixed | Small tests/docs deferred across milestones |
| [OPEN-020](#open-020--spec-normative-gaps) | P4 | Deferred | Spec §8.3 DuckDB prose; parent fsync; etc. |
| [OPEN-021](#open-021--m5-integration-stale-vs-t9-bis-hold-gate) | P1 | Open | M5 e2e still seeds 5/1 entries; min batch size is now 10 |
| [OPEN-022](#open-022--compose-override-yml-breaks-discovery-test) | P2 | Open | Tracked `docker-compose.override.yml` makes default `compose config` ≠ base |
| [OPEN-023](#open-023--ingest-content-risk-prompt-injection--href--size) | P3 | Deferred | Seed map of untrusted ingest → LLM/index/UI; no RCE; tackle when convenient |

---

## P0 — Test hygiene (do first)

### OPEN-001 — Escalations test stale `error_log` count

| Field | Value |
|-------|-------|
| **Status** | **Closed 2026-09-13** — test now asserts `len(error_log) == 2` with HTTPStatusError + ALERT sibling |
| **Also tracked** | `.dev/known-test-failures.md` OPEN-001 (historical write-up; mark closed there) |
| **Audit** | M1 re-audit F-013; inherited M2–M7 waivers; architecture `open-questions.md` 1.4.0 closed the matching question |

**What (historical):** `tests/test_state_worker_routers_escalations.py::test_escalations_returns_flagged_entry_with_error_log` asserted `len(error_log) == 1`. Implementation correctly returned **2** rows after M1 T8. **Fix landed:** assertion is `== 2`.

**Why it matters:** Wire shape is operational failure + `ALERT` sibling per T8 decision log. Stale test hides intended contract.

**Anchors:**
- Test: `tests/test_state_worker_routers_escalations.py` (line ~103)
- Router: `services/state-worker/app/routers/escalations.py` (unfiltered `SELECT * FROM error_log`)
- Transitions: `services/state-worker/app/transitions.py` — `record_failure` + `emit_alert`
- Decision: `.dev/decision-logs/m1-state-kernel/T8-alert-logging.md`
- Passing alerts: `tests/test_state_worker_alerts.py`

**Recommended fix (Option A):** Expect 2 rows; assert `HTTPStatusError` + `ALERT` with same `message`.

**Option B (product change):** Filter `ALERT` in router — needs spec/UI sign-off; rejected by T8 decision log.

**Validate:** `python -m pytest tests/test_state_worker_routers_escalations.py -q`

---

### OPEN-002 — Monolithic pytest `app` namespace collision

| Field | Value |
|-------|-------|
| **Status** | Open (worsened post-M7; mechanism re-diagnosed 2026-09-14) |
| **Also tracked** | `.dev/known-test-failures.md` OPEN-002; architecture `known-coupling-surfaces.md` (shared `app` package) |
| **Audit** | M7 F-005; M7 handoff §8.1, §8.4 |

**What:** Nine services each use a top-level `app` package. Monolithic `pytest tests/` loads multiple into `sys.modules['app']` → ImportError / wrong config.

**2026-09-14 re-diagnosis (do not treat as 87 product regressions):**

1. **Leaky poisoners.** `tests/test_query_api_routes_entry.py` and `tests/test_query_api_stats.py` wipe every `app.*` from `sys.modules`, import query-api’s `app`, then **never restore** modules and **never pop** `services/query-api` from `sys.path`. Search/UI tests use save-restore-and-pop and do **not** poison (entry+contract dies; search+contract and UI+contract stay green).
2. **Namespace vs regular package.** `state-worker` and `vector-writer` have **no** `app/__init__.py` (PEP 420 namespace). query-api **does**. Once query-api is anywhere on `sys.path`, `import app` binds to query-api even if vector-writer is *earlier* on the path. Reproduced outside pytest; `importlib.invalidate_caches()` does not change it.
3. **Victim pattern.** Later tests that re-resolve dotted names (`monkeypatch.setattr("app.db.SQLITE_DB_PATH", ...)`, `import app.index_entry`) fail. Collection-time bindings (`from app.main import app` → route-surface test) still pass.

**2026-09-14 suite:** 811 passed / 87 failed / 14 errors / 4 skipped. Collision cluster ≈98 tests: `app.db` (30), `app.index_entry` (32), `app.transitions` (15), plus missing attrs on the wrong `app.config` / `app.models`. Dashboard stats/UI tests themselves pass; stats copied the leaky entry pattern so it is a **new poisoner of the same class**, not a new class.

**Baseline:** Pre-M7 @ `e207960` had 2 failures (escalations + M6 leak). Post-M7: ~63+ failures/errors from collision alone. 2026-09-14 count is higher because more query-api/UI tests exist (including the leaky stats file).

**Why it matters:** “Full suite green” is misleading; CI/policy needs a single authoritative command.

**Anchors:**
- Mitigation: `scripts/verify-m7.sh` (subprocess for `test_query_api_models.py`, `test_m7_integration.py`)
- Handoff: `.dev/plans/m7-read-path/handoff.md` §8.1 monolithic note
- Good pattern: `tests/test_query_api_routes_search.py` `_clear_app_modules` / `_restore_app_modules`
- Leaky pattern: `tests/test_query_api_routes_entry.py`, `tests/test_query_api_stats.py`

**Fix options:**
1. **Harness (smallest):** Make entry/stats (and any other leaky file) use the search/UI save-restore-and-pop helper. Session `conftest.py` that asserts `app` is gone between files would lock it.
2. **Equalize packages:** Add empty `app/__init__.py` to state-worker and vector-writer so they are regular packages and stop losing to query-api. Does **not** alone fix leftover-path order.
3. **Policy:** Document that only `verify-m*.sh` slices are binding; monolithic is best-effort.
4. **Structural:** Rename packages (`state_worker_app`, etc.) — large diff; avoid unless necessary.
5. **Subprocess isolation:** Extend verify-script pattern to additional collision-prone test modules.

**Validate:** `python -m pytest tests/test_query_api_routes_entry.py tests/test_state_worker_contract.py -q` must go green; then `python -m pytest tests/ -q`.

---

### OPEN-003 — M6 integration `sys.modules` leak

| Field | Value |
|-------|-------|
| **Status** | Half-open — teardown added but insufficient |
| **Audit** | M6 F-004 |

**What:** `tests/test_m6_integration.py` loads vector-writer `app.*` via `_load_vector_writer_stack()`. Running before `tests/test_state_worker_config.py::test_config_env_round_trip` loads `services/vector-writer/app/config.py` instead of state-worker config.

**Anchors:**
- `tests/test_m6_integration.py` — `_load_vector_writer_stack()` (save/restore in `finally`)
- Reference pattern: `tests/test_vector_writer_loop.py` (fixture teardown)
- Audit: `.dev/audits/2026-06-13-m6-indexing.md` F-004

**Fix:** Extend M6 fixture to fully restore after each test (or subprocess-isolate M6 integration like M7). Mirror vector-writer loop test pattern.

**Validate:**
```text
python -m pytest tests/test_m6_integration.py tests/test_state_worker_config.py::test_config_env_round_trip -q
```
Should pass in either order.

---

### OPEN-021 — M5 integration stale vs T9-bis hold gate

| Field | Value |
|-------|-------|
| **Status** | Open |
| **Also tracked** | `.dev/known-test-failures.md` OPEN-021 |
| **Not** | OPEN-002 — these two fail **in isolation** |

**What:** After prompt-caching T9-bis, `ENRICHMENT_STAGE1_MIN_BATCH_SIZE` defaults to **10** and `stage1_cycle` holds below that until `MAX_HOLD_MINUTES`. `tests/test_m5_integration.py` still seeds **5** entries (e2e) and **1** entry (startup scan), never overrides the min, and never advances the hold clock. One cycle → no Anthropic submit → no in-flight `enrichment_stage1` batch → `assert len(matches) == 1` with `matches == []`.

**Why it matters:** Looks like a pipeline regression; product is doing what T9-bis specified. Unit tests in `test_enrichment_batcher_stage1_loop.py` already monkeypatch the min to 1; the M5 fixture was never updated.

**Anchors:**
- `services/enrichment-batcher/app/config.py` — `ENRICHMENT_STAGE1_MIN_BATCH_SIZE` default 10
- `services/enrichment-batcher/app/stage1_loop.py` — hold-and-return when `held_count < MIN` and deadline not reached
- `tests/test_m5_integration.py` — `_ENTRY_COUNT = 5`; startup scan uses `_source_ids(1)`
- Decision: `.dev/decision-logs/prompt-caching/T9-bis-batch-amortization.md`

**Recommended fix:** In `integration_client`, set stage-1/stage-2 min batch size to 1 (same as the unit tests), **or** raise `_ENTRY_COUNT` to 10 and give the startup-scan test a min override.

**Validate:**
```text
python -m pytest tests/test_m5_integration.py::test_m5_e2e_five_entries_reach_vector_write_queued_with_enrichment_fields tests/test_m5_integration.py::test_m5_startup_scan_registers_enrichment_stage1_in_flight -q
```

---

## P1 — Charter gates & ops

### OPEN-004 — Charter G4 full e2e ArXiv → INDEXED

| Field | Value |
|-------|-------|
| **Status** | Open (manual) |
| **Audit** | M7 F-006 |

**What:** Single live run: discovery → pre-filter → content → enrichment → index → searchable. Not in `verify-m7.sh`.

**Anchors:**
- Charter: `.dev/bishop_program_charter.md` (M7 exit gates)
- Handoff: `.dev/plans/m7-read-path/handoff.md` §8.1, §8.4 Flag 5

**Validate:** Manual docker compose pipeline run; document result in handoff or ops note.

---

### OPEN-007 — SQLite hardening (post-corruption)

| Field | Value |
|-------|-------|
| **Status** | Mostly closed 2026-09-11 — see remaining table below |
| **Incidents** | 2026-06-13 — `bishop.db` replaced with ArXiv HTML; clean reset per ops log. 2026-09-11 — torn btree/overflow pages; **salvaged, root-caused, hardened** |

**What:** June's session exposed an unsafe multi-consumer sqlite volume layout on Windows bind mounts and the hardening was deferred. September's second corruption forced it, and also found the actual root cause: a sweep raised mid-write and `get_db()` returned the connection to the pool with its write transaction open, holding the single WAL write lock and 500-ing every route while `/health` stayed green. Deferred `BEGIN` (which bypasses `busy_timeout` on upgrade) and Alembic's `disable_existing_loggers=True` (which silenced every app logger at startup) were contributing defects.

**Anchors:**
- Ops log (authoritative): `.dev/decision-logs/ops/sqlite-snapshot-and-integrity-gate.md`
- Standing note: `.dev/sqlite.md` (snapshot/restore usage)
- June ops note: `.dev/db_hardening.md`; June reset: `.dev/decision-logs/ops/bishop-db-corrupt-clean-reset.md`
- Salvage tool: `scripts/sqlite_salvage.py`; rotator: `scripts/sqlite_snapshot.py`; restore: `scripts/sqlite_restore.py`
- Compose: sqlite now mounted on **state-worker** (rw) and **query-api** (ro) only

**Closed 2026-09-11:**

| Change | Where | State |
|--------|-------|-------|
| `PRAGMA integrity_check` on startup, refusing to start | state-worker lifespan, before Alembic | Done |
| `PRAGMA busy_timeout` on pool init + migration engine | `app/db.py` | Done |
| Remove sqlite mount from **batch-poller** | `docker-compose.yml` | Done |
| `/health/db` with real I/O + 503, compose healthcheck uses it | state-worker + compose | Done |
| Refuse startup if DB fails integrity (supersedes "refuse compose up") | `app/db.py` | Done |
| Integrity-gated snapshots, 30 min, 24h TTL + restore script | `scripts/`, task `BishopSqliteSnapshot` | Done |
| Pooled-connection transaction leak / `row_factory` / `BEGIN IMMEDIATE` | `app/db.py`, `app/transitions.py` | Done |
| App loggers silenced by migrations | `alembic/env.py` | Done |

**Still open (needs an operator decision, tracked here):**

| Change | Where | Priority | Note |
|--------|-------|----------|------|
| query-api entry reads via state-worker HTTP (not direct sqlite) | `sqlite_reader.py` + proxy route | Medium | Larger M7 seam cut; keeps ro mount today |
| Move sqlite to a Docker **named volume** | compose + all `.dev/sqlite.md` recipes | Medium | **Proposal + tooling landed 2026-09-11** (`.dev/decision-logs/ops/sqlite-named-volume-migration.md`): `--volume` mode on `sqlite_snapshot.py`/`sqlite_restore.py`, opt-in `docker-compose.override.named-volume.yml`, `tests/test_sqlite_named_volume.py` (10/10 pass against real throwaway volumes). **Cutover itself is a pending operator action** — `docker-compose.yml` was deliberately not modified and the live bind mount is still in use. Runbook + rollback in the proposal doc §4–5. |
| Cut the 5-connection aiosqlite pool | `app/db.py` | Low | Contention gone after `BEGIN IMMEDIATE`; may no longer be warranted. Measure before cutting |
| Move `content_raw` out of SQLite (blob dir + atomic persist) | spec + vector/content paths | Low | Would shrink the overflow pages that tore; spec change, proposal only |
| Re-pre-filter the ~136 manifest rows lost to torn pages | ops | Low | Free to re-discover, paid to re-decide; not authorised |

**Deferred (ops):** Automated backup; forensics on quarantined volume; integrity gate in verify scripts.

**Validate:** After changes — compose up, corrupt-file injection test, concurrent read during write stress (Windows bind mount).

---

### OPEN-022 — `docker-compose.override.yml` breaks discovery test

| Field | Value |
|-------|-------|
| **Status** | Open |
| **Also tracked** | `.dev/known-test-failures.md` OPEN-022; `incident-log.yaml` 2026-09-12 FU-002 |
| **Not** | OPEN-002 — fails **in isolation** |

**What:** `tests/test_sqlite_named_volume.py::test_default_compose_discovery_ignores_named_volume_override` asserts `docker compose config` == `docker compose -f docker-compose.yml config`. Compose auto-loads a file literally named `docker-compose.override.yml`. This repo **tracks** a temporary override remounting `sqlite_live` after the Docker Desktop WAL-handle leak. Default render therefore differs from base; the named-volume overlay (`docker-compose.override.named-volume.yml`) is **not** the trigger.

**Why it matters:** The test is correct about the named-volume filename. It is now also a tripwire that any committed `docker-compose.override.yml` fails CI/hygiene.

**Anchors:**
- `docker-compose.override.yml` — sqlite_live remount; comment says remove once handles are gone
- `tests/test_sqlite_named_volume.py` L367–381
- Incident FU-002: move live file back under `sqlite/` or cut over to named-volume runbook

**Recommended fix:** gitignore / untrack the temporary override once sqlite_live is retired, **or** teach the test that a present `docker-compose.override.yml` is allowed and only forbid the named-volume filename being auto-loaded.

**Validate:** `python -m pytest tests/test_sqlite_named_volume.py::test_default_compose_discovery_ignores_named_volume_override -q`

---

## P2 — Pipeline residual & onboarding

### OPEN-008 — Batch claim release on failures

| Field | Value |
|-------|-------|
| **Status** | Half-open — sweep/orphan fixes landed 2026-06-13; claim release still deferred |


**What:** Entries can remain in `RELEVANCE_QUEUED` (or enrichment QUEUED states) until lock-state sweep when batch submit/register fails.

**Partial mitigation (landed):**
- `register_batch` 409 → batch marked `failed` (batch-poller)
- Sweep skips `RELEVANCE_QUEUED` referenced by active batches
- See CHANGELOG `batch-poller orphan-batch resilience`

**Still open:**
1. **Pre-filter claim release on `invalid_source_state` 409** after Anthropic submit
2. **QUEUED claim release on Anthropic submit 400** (custom_id / model errors)
3. **Per-entry partial apply** for mixed batch membership on results POST

**Anchors:**
- `.dev/decision-logs/m3-batch-pipeline/batch-custom-id-encoding.md` — Deferred
- `.dev/decision-logs/m3-batch-pipeline/batch-poller-orphan-batch-resilience.md` — Deferred
- `.dev/decision-logs/ops/bishop-db-corrupt-clean-reset.md` — Deferred
- Pre-filter: `services/pre-filter-worker/app/loop.py`
- State-worker: `services/state-worker/app/transitions.py` — `register_batch`, sweeps

**Validate:** Adversarial tests — submit 400 / register 409 → entries return to pollable state without 48h sweep wait.

---

### OPEN-009 — Orphan external Anthropic batch

| Field | Value |
|-------|-------|
| **Status** | Waived-deferred (M3–M5 audits) |

**What:** `prefilter_cycle` / `stage1_loop` / `stage2_loop` call Anthropic submit **before** `POST /batches`. Register failure leaves external batch with no compensating cancel.

**Anchors:**
- M3 audit CR-1 / F-004
- M5 audit CR-02; CHANGELOG T3 enrichment-batcher
- Tests document behavior: `test_prefilter_cycle_state_worker_register_error_skips_after_anthropic`

**Fix (if needed):** Compensating cancel call, or register-before-submit reorder (larger design change).

---

### OPEN-010 — Live G3 Anthropic model-string probe

| Field | Value |
|-------|-------|
| **Status** | Open for production; waived for milestone gates |
| **Audit** | M3 F-003 |

**What:** Charter requires live model string verification. `scripts/verify-g3.sh` exits 0 with SKIP when `ANTHROPIC_API_KEY` absent. Mocked tests pass; constant `claude-haiku-4-5-20251001` pinned.

**Anchors:**
- `scripts/verify-g3.sh`, `tests/test_verify_g3.py`
- `bishop_shared/anthropic_config.py` — `verify_model_string()`
- M3 handoff waivers; `.dev/decision-logs/m3-batch-pipeline/batch-custom-id-encoding.md` — G3 batch probe deferred

**Validate:** Run `scripts/verify-g3.sh` once with real `ANTHROPIC_API_KEY` before production deploy.

---

### OPEN-011 — `.env.example` host ports

| Field | Value |
|-------|-------|
| **Status** | Open since M0 |
| **Audit** | M0 F-003; decision log T4 deferral |

**What:** Without `QUERY_API_HOST_PORT` / `UI_HOST_PORT`, `docker compose --env-file .env.example` publishes no host ports → README quick-start breaks (8080/8081 unreachable).

**Anchors:**
- `.env.example` — only `BISHOP_DATA_ROOT` (+ API key comment) today
- `docker-compose.yml` — `ports: "${QUERY_API_HOST_PORT}:8000"`, UI port
- `bishop_shared/constants.py` — defaults 8080/8081
- `.dev/decision-logs/m0-workshop/T4-compose-skeleton.md` — Items deferred
- `.dev/audits/2026-06-09-m0-workshop.md` F-003

**Fix:** Add to `.env.example`:
```env
QUERY_API_HOST_PORT=8080
UI_HOST_PORT=8081
```

**Validate:** `docker compose --env-file .env.example config` shows published ports.

---

### OPEN-012 — Architecture folder stale

| Field | Value |
|-------|-------|
| **Status** | Open |
| **Charter** | §7 housekeeping after each milestone |

**What:** `.dev/architecture/bishop/` predates M7 landing (query-api, ui, cli, m7 tags). Scraper/ui rows understate M4/M7 landed state.

**Anchors:**
- `.dev/plans/m7-read-path/handoff.md` §8.4
- Skill: `project-architecture` for refresh procedure

**Validate:** `module-map.md`, `integration-seams.md`, `public-interface-inventory.md` reflect HEAD.

---

## P3 — Coverage gaps & waived deferrals

### OPEN-023 — Ingest content risk (prompt injection, href, unbounded body)

| Field | Value |
|-------|-------|
| **Status** | Deferred — documented 2026-09-16; not an incident; no code change |
| **Also tracked** | `product-backlog.yaml` PB-009; architecture `open-questions.md` 1.6.0 |
| **Write-up** | `.dev/decision-logs/ops/ingest-content-risk-seed.md` |

**What:** Public titles, abstracts, READMEs, and LessWrong HTML are untrusted and reach Claude as the user turn (Gate 1, Call 1), then Call-1 summaries hop into Call 2 and into embeddings. No tool-use, no command exec, no generative RAG. Realistic impact is corpus integrity and batch spend, not a shell. Also: no `max_length` on `content_raw`; UI renders stored `url` as `href` without an http(s) allowlist; UI/query-api publish host ports with no auth.

**Why it is P3:** Local-first single-operator box. Jinja autoescape, parameterized SQL, host-fixed content fetches, and trusted-only prompt-cache prefixes already close the RCE/SSRF/SQLi class.

**Suggested later probes (do not start until a packet owns this):**
1. Frozen adversarial eval through Gate 1 / Call 1 / Call 2 before changing prompts
2. http(s) allowlist on stored URLs
3. Wire / response size cap on `content_raw`
4. LAN bind/auth only if this host is not single-operator

**Anchors:**
- Decision log: `.dev/decision-logs/ops/ingest-content-risk-seed.md`
- Architecture: `open-questions.md` 1.6.0, `known-coupling-surfaces.md` 1.7.0, `external-input-sources.md` 1.4.1, `integration-seams.md` 1.3.1
- Canvas: ingest-content-risk canvas beside chat (not in `.dev/architecture/`)

**Do not:** invent `failure-taxonomy.md` cause-class IDs until the owner names them.

---

### OPEN-013 — Live Docker compose smoke

| Field | Value |
|-------|-------|
| **Status** | Waived-deferred M3–M7 |

**What:** No CI/automated `docker compose up` e2e in verify scripts. Manual validation before ops deploy.

**Anchors:** Every milestone CHANGELOG T6/T8 line; all audit F-006/F-007/F-009 patterns.

**Suggested manual checklist:** state-worker healthy → scraper cycle → pre-filter batch → content → enrichment → vector-writer → `bishop search`.

---

### OPEN-014 — `verify-g2.sh` omits alert tests

| Field | Value |
|-------|-------|
| **Status** | Open |
| **Audit** | M1 re-audit F-014 |

**Anchors:** `scripts/verify-g2.sh`, `tests/test_state_worker_alerts.py`

**Fix:** Add alerts module to G2 script, or document intentional split (contract gate vs logging gate).

---

### OPEN-015 — Scraper `RetryExhaustedError` loop-level test

| Field | Value |
|-------|-------|
| **Status** | Deferred |
| **Audit** | M2 F-004 |

**What:** `services/scraper/app/loop.py` handles retry exhaustion; `tests/test_scraper_failure_envelope.py` covers envelope only.

**Anchors:** `.dev/audits/2026-06-12-m2-discovery.md`; M2 CHANGELOG T5 deferral

**Fix:** `test_scrape_cycle_retry_exhausted_skips_batch_and_state` (name from audit).

---

### OPEN-016 — M1 unwired §14.3 alert types

| Field | Value |
|-------|-------|
| **Status** | Deferred per T8 decision log |

**Not wired in `record_failure` / `emit_alert`:**
- `profile_hash_mismatch` — enrichment-batcher logs event only (T4 decision log)
- `batch_timeout_48h`, `batch_abort` — batch-poller / M5 scope

**Anchors:** `.dev/decision-logs/m1-state-kernel/T8-alert-logging.md` — Items deferred

---

### OPEN-017 — Domain-only search BM25 scope

| Field | Value |
|-------|-------|
| **Status** | Deferred |
| **Audit** | M7 CR-02; T4 decision log |

**What:** When `GET /search` has only `domain` param, `run_search` applies LanceDB `where` but BM25 searches full domain corpus without DuckDB pre-filter.

**Anchors:**
- `services/query-api/app/retrieval/search.py`
- `.dev/decision-logs/m7-read-path/T4-rrf-problem-shaped.md` — Items deferred

**Fix only if:** recall gaps reported in production.

---

### OPEN-018 — SQLite WAL contention adversarial test

| Field | Value |
|-------|-------|
| **Status** | Mostly closed 2026-09-11 — real multi-process concurrency is covered; the Windows bind-mount environment is not |
| **Handoff** | M7 §8.4 — `mode=ro` only; contention not exercised |

**Covered now:**
- `tests/test_state_worker_pool_transaction_leak.py` — writer-side pool leak (borrower raises mid-write must not hold the WAL write lock). `BEGIN IMMEDIATE` + `busy_timeout` landed (see OPEN-007).
- `tests/test_sqlite_wal_concurrency.py` — 5 writer **processes** (spawn, matching compose's separate containers) plus 1 `mode=ro` reader process against one tmp_path WAL file, migrated via `run_migrations`. Writers use the production write shape (`BEGIN IMMEDIATE`, read-then-write on `manifest`/`entries`/`scraper_state`, `COMMIT`, `PRAGMA busy_timeout` = `SQLITE_BUSY_TIMEOUT_MS`). Reader mirrors `services/query-api/app/sqlite_reader.py` (`file:{path}?mode=ro`, `SELECT * FROM manifest WHERE processing_state = ?`, `SELECT COUNT(*) FROM entries`). Assertions: every writer reaches its full commit count, `PRAGMA integrity_check == ["ok"]`, committed row count equals the sum of intended inserts, reader completed a meaningful number of successful reads *during* the writers (not after), wall-clock bounded by a harness `join(timeout=45)` (no `pytest-timeout` in this repo), and spawned PIDs are proven dead after reap. Live: a 4-minute loaded run produced zero `database is locked`.

**Still missing (cannot be closed in-process):** no test runs against a Windows Docker bind mount, which is the environment where the pages actually tore. That is a host/volume property, not something pytest can fabricate. **This harness does not prove the bind-mount is now safe** — only that the application's lock-handling logic is correct under real OS-level concurrent access to the file on whatever filesystem the test happens to run on (here: a pytest `tmp_path` on the Windows host NTFS, not a compose bind mount). Named-volume migration remains the OPEN-007 follow-up for the tearing class.

**Deferred-BEGIN diagnostic:** `test_wal_multiprocess_deferred_begin_diagnostic` is skip-marked. On this host it consistently needed more client-side `OperationalError` retries than `BEGIN IMMEDIATE` (12–21 vs 0 across four consecutive runs) — consistent with lock-upgrade bypassing `busy_timeout` — but writers still completed and integrity stayed `ok`, so the retry delta is not a stable CI falsifier.

**Anchors:** `services/query-api/app/sqlite_reader.py`; `tests/test_sqlite_wal_concurrency.py`; `tests/test_state_worker_pool_transaction_leak.py`; M7 CHANGELOG T5 deferral; ties to OPEN-007.

---

## P4 — Small gaps & doc nits

### OPEN-019 — Misc coverage & docs gaps

| Item | Anchors | Notes |
|------|---------|-------|
| README Python **3.11+** vs `pyproject.toml` **≥3.12** | `README.md`, `pyproject.toml` | M0 F-008 |
| `BISHOP_ARXIV_MAX_RESULTS` env override untested | `services/scraper/app/adapters/arxiv.py` | M2 F-005 |
| `STATE_WORKER_URL` override untested (content-scraper) | `services/content-scraper/app/config.py` | M4 F-007 |
| Escalatable 404 e2e through content-scraper loop | M4 F-003; unit mapping exists | Optional |
| Content POST 409 loop branches | `.dev/decision-logs/m4-content/T2-content-scraper-vendor-layout.md` | Router tests cover envelopes |
| Malformed Atom entries (missing id/title) | `.dev/decision-logs/m2-discovery/T4-arxiv-atom-api.md` | Silent skip; no test |
| Token-bucket `calls > 1` burst test | `.dev/decision-logs/m2-discovery/T2-adapter-registry.md` | `calls=1` only |
| `registry.py` ImportError bootstrap dead code post-T4 | `services/scraper/app/adapters/registry.py` | M2 F-008 observation |
| Enrichment-batcher auxiliary log events outside §2 | M5 F-005 | Ops-only; benign |
| OOV insert when `entry_type` is None | `.dev/decision-logs/m5-enrichment/T2-state-worker-enrichment-hub.md` | Edge case |
| Markdown-fence JSON in enrichment parsers | `.dev/decision-logs/m5-enrichment/T1-enrichment-shared-utilities.md` | Add stripper if production needs |
| Corrupt BM25 pickle recovery | `.dev/decision-logs/m6-indexing/T3-bm25-rank-bm25-choice.md` | Operator deletes `index.pkl` |
| UI dedicated error partial for all pages | CHANGELOG M7 T7 | Inline errors work |
| Per-channel score attribution in search response | CHANGELOG M7 T8 | `channels_active` tested |
| Tags filter AND-all-tags | `.dev/decision-logs/m7-read-path/T3-lancedb-duckdb-embedding.md` | OR semantics today |
| HF model download on first live encode | M7 T3 decision log | Docker cache comment pattern |
| `stub_started` logging not asserted in pytest | M0 F-005 | Stubs implement it |
| `scripts/init-volumes.ps1` untested | M0 F-007 | Manual only |
| `scripts/verify-g1.sh` end-to-end not run on Windows | M0 F-004 | Needs bash + Docker |
| T1 decision log stub-CMD supersession banner | `.dev/decision-logs/m2-discovery/T1-scraper-foundation.md` | M2 F-009 |
| `manual_retry` ORDER BY with ALERT row tie-break | M1 re-audit CR2-04 | Benign observation |
| `pytest.mark.heavy` not registered | `pyproject.toml` | Warning only |
| M5 batches router `invalid_transition` HTTP envelope | `.dev/decision-logs/m5-enrichment/T2-state-worker-enrichment-hub.md` | Hub tests cover transitions |
| Concurrent BM25 reload stress test | `.dev/decision-logs/m7-read-path/T2-bm25-reader.md` | COW unit tests sufficient for M7 |
| CHECK constraints on `processing_state` in DB | `.dev/decision-logs/m1-state-kernel/T1-schema-foundation.md` | App-layer enum only |
| `state_entered_at` for sweep timing | `.dev/decision-logs/m1-state-kernel/T2-transition-engine.md` | Post-M1 if false positives |

---

### OPEN-020 — Spec normative gaps (docs-only deferrals)

| Item | Anchors |
|------|---------|
| Spec §8.3 DuckDB mixed-mode rule not amended | `.dev/decision-logs/m7-read-path/duckdb-search-concurrency.md` — implemented in code, spec prose stale |
| Parent-directory fsync before `os.replace` | `.dev/decision-logs/m6-indexing/T1-indexing-shared-contracts.md` |
| Named Docker volume for `duckdb/` on Windows | duckdb-search-concurrency decision log |
| Phase 2 spec `phase2_verdict: CONDITIONAL` cycle 3 | `bishop_spec_0_6.md` header — design process, not implementation |

---

## Recently closed (do not re-open without regression)

| Item | Closed by |
|------|-----------|
| DuckDB concurrent read / search 500 `Conflicting lock` | CHANGELOG 2026-06-13; `duckdb-search-concurrency.md`; commit `34bad72` area |
| M1 §14.3 alert dual-write (F-004) | T8 `alerts.py` + tests |
| Batch-poller Anthropic SDK namespace | CHANGELOG hotfix; decision log |
| Batch `custom_id` encoding (400 mislogs) | `bishop_shared/batch_custom_id.py` |
| Batch-poller orphan retry loops (partial) | 2026-06-13 resilience CHANGELOG |
| M7 handoff not in HEAD (F-002) | Committed — `git show HEAD:.dev/plans/m7-read-path/handoff.md` works |
| Plan artifact archaeology M2–M6 handoffs | Committed at HEAD |
| Post-outage orphan-batch triage | Moot after DB clean reset (ops log) |
| OPEN-001 escalations `error_log` count | Test now asserts 2 (HTTPStatusError + ALERT); architecture open-questions 1.4.0 |

---

## Suggested tackle order

1. **OPEN-021** — M5 fixture min-batch override (~5 min); two isolated fails
2. **OPEN-002** — entry/stats save-restore-and-pop (same helper as search/UI); optionally add `app/__init__.py` on state-worker + vector-writer
3. **OPEN-003** — M6 fixture isolation (same class as OPEN-002)
4. **OPEN-022** — retire or gitignore `docker-compose.override.yml`, or narrow the discovery test
5. **OPEN-011** — `.env.example` two lines
6. **OPEN-007** — named-volume cutover still pending operator action
7. **OPEN-010** — one live G3 run when API key available
8. **OPEN-004** — manual G4 pipeline run when docker stack is up
9. **OPEN-008** — if live pipeline shows stuck `RELEVANCE_QUEUED` rows
10. **OPEN-012** — architecture refresh when convenient
11. **OPEN-023** — ingest content risk when convenient (eval slice before prompt changes; cheap url/size caps independent)
12. **OPEN-019** — opportunistic small fixes

---

## Maintenance

When closing an item:
1. Fix code/docs/tests
2. Remove or update section here
3. Update `.dev/known-test-failures.md` if test-related
4. Add one line to `CHANGELOG.MD`
5. If audit waiver: note in next milestone handoff §8.6

When adding new deferrals from milestone execution: append with `OPEN-0XX` id and link decision log.
