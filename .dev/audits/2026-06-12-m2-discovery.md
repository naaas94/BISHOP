# Audit Report — m2-discovery

**Audit document revision:** 1 (initial)  
**Date:** 2026-06-12  
**Plan version:** 1.1 (working tree; untracked at HEAD)  
**Audit HEAD:** `0954ea8d4bc9b48b271a500d2b6a5004150365c2`  
**Auditor focus areas:**
1. **Integration seams** (mandatory) — seeded from context-map §Coupling surfaces; M2 is scraper ↔ state-worker HTTP wire + compose image-tag matrix.
2. **Failure paths** — `failure_envelope` classification, loop error branches, batch POST failure guard.
3. **Edge cases** — first-run `since` resolution, empty Atom feed, idempotency on re-run.

---

## 1. Audit metadata

| Field | Value |
|-------|-------|
| Task | M2 — Discovery Slice (`scraper` service) |
| Context map | `.dev/plans/m2-discovery/context-map.md` — readiness **READY** at scout time (plan §0 records **CONDITIONAL**) |
| Scout SHA | `7e8be997a7697c09ce46d36dc9f31f497680c577` |
| Audit SHA | `0954ea8d4bc9b48b271a500d2b6a5004150365c2` |
| Provenance | **Diverged** — five implementation commits (`febf62c`…`0954ea8`) post-scout |
| Scout working tree | **clean** |
| Audit working tree | **dirty** — `?? .dev/plans/m2-discovery/` (plan, context-map, handoff, packets untracked) |
| Phase 0 discipline | Completed before narrative artifacts (task statement + §2 only, then code/tests) |
| Pytest (auditor run) | **78 passed** M2 gate slice; **45 passed** scraper-only slice |
| Re-audit | No — initial audit |

---

## 2. Provenance log

### SHA comparison

| Check | Result |
|-------|--------|
| Scout SHA vs audit HEAD | **Diverged** (`7e8be99` → `0954ea8`) |
| Expected | Yes — scout baseline was pre-M2; all scraper implementation landed post-scout |

**`context-map-stale` (major, F-001):** Every `direct` row in context-map §File map (`services/scraper/*`, `bishop_shared/enums.py`, `tests/test_scraper_*.py`, `scripts/verify-m2.sh`, `docker-compose.yml`, etc.) diverged from scout SHA. Scout inventory listed planned symbols as "not yet on disk"; implementation now exists. Findings against scout `suspect_modified` predictions are **stale-qualified** — outcomes verified against current HEAD, not scout-time absence.

### Working-tree state

| Check | Result |
|-------|--------|
| Scout-time dirty paths | None (clean) |
| Audit-time dirty paths | `?? .dev/plans/m2-discovery/` — entire plan directory untracked |

### Scout grep coverage

Context-map §Coupling surfaces recorded patterns for: `STATE_WORKER_URL`, `ManifestBatchEntryWire` / `manifest/batch`, `scraper-state`, `SourceEnum` / `"arxiv"`, `bishop/scraper:m0`, `RateLimit` / `SOURCE_RATE_LIMITS`, `ADAPTER_REGISTRY`, `PermanentFailureError` / `RETRIABLE_HTTP`. Plan §5.4 hidden couplings use the same vocabulary. **No `scout-incomplete` gaps** identified.

### Plan-artifact provenance (`git show HEAD:<path>`)

| Artifact | HEAD | On disk | Notes |
|----------|------|---------|-------|
| `.dev/plans/m2-discovery/context-map.md` | **absent** | present | Scout artifact never committed |
| `.dev/plans/m2-discovery/plan.md` | **absent** | present | v1.1 Complete + §8 embedded |
| `.dev/plans/m2-discovery/handoff.md` | **absent** | present | Canonical §8.1–§8.6 for auditor |
| `.dev/plans/m2-discovery/packets/T1.md` … `T5.md` | **absent** | present | Executor packets |
| `.dev/decision-logs/m2-discovery/T1-scraper-foundation.md` | present | present | |
| `.dev/decision-logs/m2-discovery/T2-adapter-registry.md` | present | present | |
| `.dev/decision-logs/m2-discovery/T4-arxiv-atom-api.md` | present | present | T3 standard tier — no log (expected) |
| `CHANGELOG.MD` | present | present | M2 T1–T5 section |
| `scripts/verify-m2.sh` | present | present | |
| `bishop_shared/enums.py` | present | present | |
| `services/scraper/app/` | present | present | Full package |
| `tests/test_scraper_*.py`, `tests/test_shared_enums.py`, `tests/test_verify_m2.py` | present | present | |

**Findings filed in Phase 0.5:** F-001, F-002

---

## 3. Context chain completeness

| Artifact | Provided | Limits |
|----------|----------|--------|
| Context map | Yes (working tree) | Stale vs implementation SHA; not in HEAD |
| Task statement / §2 contracts | Yes | Phase 0 inputs |
| Orchestrator plan (full) | Yes (working tree v1.1) | Not in HEAD |
| Handoff §8 | Yes (working tree) | Not in HEAD; plan §8 defers to handoff |
| Packets T1–T5 | Yes | Not in HEAD |
| Decision logs T1, T2, T4 | Yes | In HEAD; T3 standard tier — no log (expected) |
| Changelog | Yes | In HEAD |
| Codebase | Yes | T1–T5 commits on main |
| Test suite | Yes | 78/78 M2 gate green at audit time |

Phase 0 completed before handoff, decision logs, and plan prose beyond §1–§2.

---

## 4. Cold-read log (pinned)

1. **`registry.py` T4 bootstrap stub** — `except ImportError` inline `ArxivAdapter` with `NotImplementedError("T4")` remains after `arxiv.py` landed; dead path at HEAD.
2. **`loop.py` empty-manifest path** — WARNING logged on empty fetch, but `post_manifest_batch([])` and `post_scraper_state` still run; could advance `last_successful_run_at` on a zero-row ArXiv 200 response.
3. **`RetryExhaustedError` loop branch untested** — `loop.py` L73–81 handles exhaustion; no matching test in `tests/test_scraper_loop.py` (CHANGELOG T5 defers).
4. **Plan §5.4 C4 disproof overclaimed** — plan prose cites "T4 test asserting limiter acquire called before httpx request"; no `acquire` / rate-limiter assertion in `tests/test_scraper_arxiv_adapter.py`.
5. **`BISHOP_ARXIV_MAX_RESULTS`** — implemented in `arxiv.py`; default `100` asserted in fixture fetch test; no env-override round-trip test in §2 table.
6. **Plan directory untracked** — implementation SHA `0954ea8` has all code committed but `.dev/plans/m2-discovery/` is `??` in working tree.

---

## 5. Findings table

| ID | Severity | Type | Phase | Subtask | Description |
|----|----------|------|-------|---------|-------------|
| F-001 | major | context-map-stale | 0.5 | — | Scout SHA `7e8be99` predates all M2 implementation; §File map predictions stale-qualified |
| F-002 | major | artifact-not-in-HEAD | 0.5 | orch | Plan, handoff, context-map, packets exist on disk but absent from `HEAD` |
| F-003 | minor | process-violation | 1 | orch | Context-map readiness **READY** vs plan §0 intake **CONDITIONAL** — undocumented mismatch |
| F-004 | minor | coverage-gap | 5 | T5 | `RetryExhaustedError` branch in `loop.py` has no loop-level test (CHANGELOG defers) |
| F-005 | minor | coverage-gap | 2 | T4 | `BISHOP_ARXIV_MAX_RESULTS` env override has no dedicated admission test |
| F-006 | minor | prediction-divergence | 1 | orch | Plan §5.4 C4 "disproven by" cites acquire-order unit test that does not exist |
| F-007 | observation | — | 4 | T5 | Empty manifest still updates `scraper_state` — acceptable per §10.3 success path but worth M3 awareness |
| F-008 | observation | — | 0 | T2 | `registry.py` ImportError bootstrap is dead code post-T4 |
| F-009 | minor | decision-log-stale | 3 | T1 | T1 log still says "stub CMD retained until T5" without supersession banner |

---

## 6. Detailed findings (above minor)

### F-001 — context-map-stale (major)

**Expected:** Context map at scout SHA reflects pre-implementation state; orchestrator acknowledged CONDITIONAL readiness and frozen flag resolutions in plan §0.

**Found:** Scout SHA `7e8be99`; implementation HEAD `0954ea8`. All 22 in-scope file-map rows for scraper implementation are post-scout creations or modifications. Interface inventory "planned symbols not yet on disk" are now landed.

**Evidence:** `git diff 7e8be99..0954ea8 --stat` — 37 files, +2042 lines. Handoff §8.2 documents staleness.

**Action:** Re-scout before M3 pre-plan (charter §7 housekeeping). Not a code defect.

---

### F-002 — artifact-not-in-HEAD (major)

**Expected:** Plan §8 declares handoff artifact binding; plan directory is the auditable orchestration record.

**Found:** `git show HEAD:.dev/plans/m2-discovery/plan.md` → fatal (not in HEAD). Same for `handoff.md`, `context-map.md`, and all five packets. Decision logs and implementation **are** in HEAD.

**Evidence:** `git status --short` → `?? .dev/plans/m2-discovery/`. Handoff §8.1–§8.2 explicitly records this gap.

**Action:** Commit `.dev/plans/m2-discovery/` (plan v1.1, context-map, handoff, packets) before M2 merge sign-off / M3 entry. Breaks post-merge audit archaeology until fixed.

---

## 7. Adversarial test log

**Focus 1 — Integration seams (context-map §Coupling surfaces)**

| Scenario | Expected | Actual | Result |
|----------|----------|--------|--------|
| C1 — `domain: "professional"` on batch wire | `ArxivAdapter.domain = PROFESSIONAL`; serializes to `"professional"` | `test_parse_atom_feed_maps_manifest_fields`, `test_fetch_manifest_parses_fixture_atom_xml` assert `DomainEnum.PROFESSIONAL` | **passes** |
| C2 — compose image tag `bishop/scraper:m2` | `docker-compose.yml` + `test_compose.py` matrix | `image: bishop/scraper:m2`; `test_image_tags_use_milestone_convention` branch `tag = "m2"` | **passes** |
| C3 — idempotency via state-worker skip | Re-run surfaces `skipped >= 1` | `test_scrape_cycle_rerun_reports_skipped_idempotent_rows` mocks client returning `skipped=1` on second batch; G2 contract covers state-worker ingest skip | **passes** |
| C4 — rate limiter inside adapter before HTTP | `acquire()` before `client.get` in `arxiv.py` | Code at `arxiv.py:L165–166`; no unit test mocks `acquire` call order | **unknown** (code inspection consistent; plan disproof claim overstated — F-006) |
| Surface 1 — `STATE_WORKER_URL` compose wiring | scraper env points at healthy state-worker | `docker-compose.yml:L28–32` | **passes** |
| Surface 2 — manifest wire field parity | DTO fields match `ManifestBatchEntryWire` | `models.py` field set matches `http.py:L17–24`; client uses `model_dump(mode="json")` | **passes** |

**Focus 2 — Failure paths**

| Scenario | Expected | Actual | Result |
|----------|----------|--------|--------|
| 429 retried inside envelope, cycle survives | No unhandled exception; batch posted after recovery | `test_429_retried`, `test_scrape_cycle_survives_429_via_failure_envelope` | **passes** |
| 400 → `PermanentFailureError`, no batch | Log + skip adapter | `test_400_raises_permanent_failure_immediately`, `test_scrape_cycle_logs_permanent_failure_and_continues` | **passes** |
| 403 → `EscalatableError`, no batch/state update | Skip adapter | `test_scrape_cycle_escalatable_failure_skips_batch` | **passes** |
| Batch POST non-2xx → no scraper_state update | §2 error envelope | `test_scrape_cycle_skips_state_update_on_batch_failure` | **passes** |
| Retry exhaustion at loop level | Log ERROR, skip state update | Handler at `loop.py:L73–81`; no loop test | **unknown** (F-004) |

**Focus 3 — Edge cases**

| Scenario | Expected | Actual | Result |
|----------|----------|--------|--------|
| First-run `since` = now − 7 days | Plan flag 3 / `ARXIV_BACKFILL_WINDOW_DAYS` default 7 | `test_resolve_effective_since_uses_backfill_window`, `test_arxiv_backfill_window_default` | **passes** |
| Incremental `since=last_run` | Loop passes snapshot timestamp | `test_scrape_cycle_posts_batch_and_updates_state` asserts `since=_LAST_RUN` | **passes** |
| Empty Atom feed | Empty list, no crash | `test_fetch_manifest_empty_feed_returns_empty_list` | **passes** (adapter only) |
| Empty manifest → scraper_state | Not specified in §2 | Loop still calls `post_scraper_state` after empty batch | **unknown** (F-007 observation) |
| Malformed Atom entry (missing id/title) | Skipped silently | T4 decision log defers; no test | **unknown** (documented deferral) |

---

## 8. Coverage gap list (prioritized)

| Priority | Gap | Kill criterion / contract | Test exists? |
|----------|-----|---------------------------|--------------|
| P1 | Plan artifacts not in HEAD | Audit archaeology | N/A — process (F-002) |
| P2 | `RetryExhaustedError` loop branch | T5 CHANGELOG deferral | No — envelope exhaustion tested in T3 only (F-004) |
| P3 | `BISHOP_ARXIV_MAX_RESULTS` env override | Plan §2 wire (binding narrative) | Default only in fetch test (F-005) |
| P4 | Rate-limiter acquire order in adapter | Plan §5.4 C4 | Code only (F-006) |
| P5 | Live `docker compose up scraper state-worker` | Charter runnable checkpoint | Deferred per CHANGELOG T5 / handoff §8.1 |
| P6 | Malformed Atom entries | T4 decision log deferral | No |
| P7 | Multi-token burst throttle (`calls=3`) | T2 decision log deferral | `test_token_bucket_throttles` uses `calls=1` only |

G2 charter kill criteria for M2 (429, idempotency, enum drift, arxiv-only registry, compose tag): **covered and passing**.

---

## 9. Intent traceability (Phase 1 summary)

**Task statement → code:** `SourceAdapter` ABC, Arxiv-only registry, rate limits, failure envelope, `StateWorkerClient`, scrape loop, scheduler — **landed**. Non-goals respected: no state-worker edits, no non-ArXiv adapters, `fetch_content` → `NotImplementedError("M4")`, no `fetch_content` implementation.

**Cold-read reconciliation:** Handoff §8.5 seeds align with cold-read items 2–6. Handoff §8.4 correctly notes C4 closed via code inspection (not acquire-order test) — partially reconciles F-006 but plan §5.4 prose still overclaims. No concealment of F-002 (handoff §8.1–§8.2 explicit).

**Map-to-plan — file map → §4 files to touch:** All scout `direct` rows appear in subtask file lists. `stub_main.py` deleted per flag 5 — matches plan T5 scope.

**Map-to-plan — packets → diff:** Implementation diff matches packet file lists per commit chain; test files beyond packets are expected (verify-m2, compose, service_stubs amendment).

**Map-to-plan — interface inventory → §2:** All planned M2 symbols landed with named §2 tests except `BISHOP_ARXIV_MAX_RESULTS` (wire narrative only).

**Prior reasoning → §2:** M1 decision to keep enums in state-worker only — plan §0 flag 1 resolution (`bishop_shared/enums.py`) supersedes without contradiction. G2 gate unchanged.

**Non-goals:** No violations detected in diff `7e8be99..0954ea8`.

---

## 10. Contract compliance (Phase 2 summary)

| Contract area | Status |
|---------------|--------|
| Types / interfaces (§2 table) | **pass** — symbols at declared paths; tests named in §2 exist and pass |
| Typed-surface admission | **pass** — `STATE_WORKER_URL`, `BISHOP_ARXIV_BACKFILL_WINDOW_DAYS`, `BISHOP_SCRAPER_SCHEDULE_INTERVAL_SEC` env round-trips tested; `BISHOP_ARXIV_MAX_RESULTS` admitted in `arxiv.py` but env override untested (F-005) |
| Error envelope | **pass** — RETRIABLE/ESCALATABLE sets match §2; loop guards batch failure |
| Naming | **pass** — `services/scraper/app/`, `bishop/scraper:m2`, test prefixes |
| Logging | **pass** — `event` fields `scrape_cycle_start`, `scrape_cycle_complete`, `permanent_failure`, `escalatable_failure`, `retry_exhausted` match §2 |
| Literal-string parity | **pass** — `NotImplementedError("M4")`, route strings, `ARXIV_EXPORT_API_URL`, frozensets |
| CLI / gate | **pass** — `scripts/verify-m2.sh` + `tests/test_verify_m2.py` |

---

## 11. Decision log audit (Phase 3 summary)

| Log | Chosen approach landed? | Issues |
|-----|-------------------------|--------|
| T1 | Yes — enums, client, config, DTOs, Dockerfile copies `bishop_shared` | F-009 stale prose on stub CMD |
| T2 | Yes — ABC, registry, rate limits, token bucket | Bootstrap stub retained per log assumption |
| T4 | Yes — Atom API, query shape, since resolution, in-adapter limiter | Malformed-entry deferral honored |
| T3 | N/A — standard tier, no log | Correct tier assignment |

Rejected alternatives avoided: no state-worker enum import, no seven-adapter registry, no RSS for M2.

---

## 12. Scout-prediction reconciliation

| Scout prediction | Type | Description (verbatim) | Outcome | Finding |
|------------------|------|------------------------|---------|---------|
| Surface 1 | confirmed coupling | `STATE_WORKER_URL` compose → scraper client | **verified** | — |
| Surface 2 | confirmed coupling | Manifest batch wire field names / domain strings | **verified** | — |
| Surface 3 | confirmed coupling | `source_id` format `arxiv:{raw_id}` | **verified** | — |
| Surface 4 | confirmed coupling | Docker image tag `bishop/scraper:m2` | **verified** | — |
| Surface 5 | confirmed coupling | `last_successful_run_at` null → backfill window | **verified** | — |
| Surface 6 | suspected coupling | Rate limiter vs failure envelope ordering | **verified** (code) | F-006 plan prose |
| Surface 7 | suspected coupling | Shared enum ownership | **verified** | — |
| Flag 1 | ambiguity | Enum sharing via `bishop_shared` vs duplicate | **verified** | plan §0 resolution |
| Flag 2 | ambiguity | Atom export API vs RSS | **verified** | T4 decision log |
| Flag 3 | ambiguity | 7-day vs 60-day first-run window | **verified** | config default 7 |
| Flag 4 | ambiguity | No scraper tests | **verified** | 8 test modules added |
| Flag 5 | ambiguity | `stub_main.py` deprecation | **verified** | deleted; Dockerfile CMD updated |
| Flag 6 | ambiguity | M1 `handoff.md` absent | **not-tested** | informational only |
| `SourceAdapter` etc. | suspect_modified | Planned symbols not on disk at scout | **verified** | stale-qualified |
| `stub_main.main` | suspect_modified | M0 stub entrypoint | **verified** | file removed |

---

## 13. Verdict

**`pass-with-conditions`**

M2 implementation matches the task statement and §2 shared contracts. The automated gate (`78 passed` M2 slice at audit time) exercises every §2 row with a named test except the `BISHOP_ARXIV_MAX_RESULTS` env override. Integration seams with state-worker wire shapes, compose tagging, and idempotency semantics compose correctly at the unit-test layer; G2 contract tests guard the state-worker side. No critical findings or contract violations in shipped code.

**Conditions before M2 merge sign-off / M3 entry:**

1. **F-002 (major)** — Commit `.dev/plans/m2-discovery/` (plan v1.1, context-map, handoff, packets T1–T5) so `git show HEAD:<path>` resolves for audit archaeology.
2. **F-004 (minor)** — Add `test_scrape_cycle_retry_exhausted_skips_batch_and_state` (or accept deferral with explicit §8 waiver referencing CHANGELOG T5 line).
3. **F-009 (minor)** — Banner-supersede T1 decision log stub-CMD prose.

**Accepted without blocking:**

- **F-001** — context-map staleness; re-scout before M3 pre-plan.
- **F-003** — readiness label mismatch; reconcile in committed plan §0 or context-map header.
- **F-005** — `BISHOP_ARXIV_MAX_RESULTS` env override test optional for M2 smoke scope.
- **F-006, F-007, F-008** — observations; handoff §8.4 partially documents C4 and empty-parse behavior.
- Live Docker compose e2e — deferred per plan test policy and CHANGELOG.
- Inherited M1 `test_escalations_returns_flagged_entry_with_error_log` failure — program hygiene, not M2 scope (handoff §8.1).

**Upgrade to `pass`:** Resolve F-002 + address F-004 or document explicit waiver in committed handoff §8.6.

---

## 14. Auditor execution notes

Commands run at audit time:

```
git rev-parse HEAD  → 0954ea8d4bc9b48b271a500d2b6a5004150365c2
git status --short  → ?? .dev/plans/m2-discovery/
python -m pytest tests/test_state_worker_contract.py tests/test_state_worker_health.py tests/test_constants.py tests/test_scraper_adapters.py tests/test_scraper_arxiv_adapter.py tests/test_scraper_client.py tests/test_scraper_config.py tests/test_scraper_failure_envelope.py tests/test_scraper_loop.py tests/test_scraper_models.py tests/test_scraper_rate_limit.py tests/test_shared_enums.py tests/test_verify_m2.py -q  → 78 passed
python -m pytest tests/test_scraper_adapters.py … tests/test_verify_m2.py -v  → 45 passed (scraper slice)
git show HEAD:.dev/plans/m2-discovery/plan.md  → fatal (not in HEAD)
```

Diff scope reviewed: `git diff 7e8be99..0954ea8` (commits `febf62c` T1 through `0954ea8` T5).
