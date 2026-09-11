# M8 — Hardening and Scale · Auditor §8 Handoff

**Plan:** `m8-hardening-scale` v1.5  
**Plan `run_status`:** `amended` (not `complete` — G7 wet-run still open)  
**Charter slice:** `.dev/bishop_program_charter.md` L492–540  
**Normative spec:** `bishop_spec_0_6.md` v1.5.0 (tracked)  
**`audit_status`:** `accepted-with-waivers`  
**Audit:** `.dev/audits/2026-09-11-m8-hardening-scale.md` revision 2 (supersedes `.dev/audits/2026-09-10-m8-hardening-scale.md` revision 1)

This handoff is the charter §7 seed for any later work. It does **not** declare the M0–M8 program closed. Charter G7 (“backfill running and producing `INDEXED` entries without pipeline errors”) is **not** recorded as passed.

---

## §8.1 Completion snapshot

**Code SHA (last implementation):** `9f183675d6a713d76c3f822dcabb813f012d5c4d` (T10-bis)

**Plan-artifact / ceremony SHA:** `9983927a0804fdb8a4e00da5a9cb5aeb39aa051f`  
(verify worktree SHA: `e42207556c10924033aa72dff50ffbf6c2332352` — same tree plus later §8.1 count-fill commit)

**Executor commit chain (implementation, not docs):**

| Commit | Subtask | Summary |
|--------|---------|---------|
| `7fd52b9` | T1-bis | Shared `BACKFILL_CONFIG` / rate limits / schedule; incremental ArXiv stays 7 |
| `7a836cb` | T2 | HF + PwC adapters (typed `HUGGINGFACE_TOKEN` deferred) |
| `c6bd205` | T3 | Semantic Scholar + GitHub |
| `3a4dd2f` | T4 | OpenReview + LessWrong (GET-only after GraphQL probe) |
| `97c963b` | T5 | `PATCH …/reading-status`, `POST /entries/permanent-fail` |
| `fb7e7e2` | T6 | query-api proxies + UI `/escalations`, `/explorer` |
| `b064f72` | T7 | G5 wrapper, G6 gold bind, enrichment template |
| `43a8bc4` | T8-bis | 7-adapter `ADAPTER_REGISTRY`, chunked backfill, `verify-m8.sh` |
| `be02414` | T9 | Registry test rewrite + `test_registry_lists_all_expected_sources` (F2) |
| `ba2ad79` | T12 | Compose `bishop/scraper:m8` + `bishop/ui:m8` (F4) |
| `f4a793b` | T11 | `verify-m8.sh` gate completeness (F3) |
| `9f18367` | T10-bis | Typed `HUGGINGFACE_TOKEN` + setattr header test (F1) |

T1, T8, T10 halted; packets retained unmodified. Do not re-dispatch.

**Primary automated verification:**

```
Command: bash scripts/verify-m8.sh
Environment: detached worktree @ e422075; BISHOP_G6_MANUAL unset
Result: passed=135 failed=0 skipped=1 errors=0 exit=0
Skip: tests/test_scraper_adapters_lesswrong.py::test_probe_lesswrong_api_live
```

Auditor revision 2 independently re-ran the same gate at HEAD `9983927` (code-identical to `e422075`) and the isolated full suite (750 collected, 0 failures under per-service isolation).

**Live Docker / G7 wet-run:** **not executed.** `BISHOP_BACKFILL_*` compose keys and chunking are landed (T8-bis). Charter G7 “backfill running / all-sources e2e producing `INDEXED`” remains an operator cluster-runtime check. This handoff does not record a `docker compose up` result.

---

## Landed contracts

Copied from audit revision 2 `landed_contracts` (re-derived from live code there, not from plan prose):

- `BackfillConfig`, `BACKFILL_CONFIG`, `SOURCE_SCHEDULE_INTERVAL_SEC` — `bishop_shared/scraper_config.py`
- `SOURCE_RATE_LIMITS` (7 sources) — `services/scraper/app/rate_limit.py`
- `BISHOP_BACKFILL_ENABLED`, `BISHOP_BACKFILL_CHUNK_DAYS`, `BISHOP_BACKFILL_INTER_CHUNK_DELAY_SEC`, `GITHUB_TOKEN`, `SEMANTIC_SCHOLAR_API_KEY`, `HUGGINGFACE_TOKEN` — `services/scraper/app/config.py`
- Six non-ArXiv adapters — `services/scraper/app/adapters/{huggingface,paperswithcode,semantic_scholar,github,openreview,lesswrong}.py`
- `ADAPTER_REGISTRY` (7) — `services/scraper/app/adapters/registry.py` + `tests/test_scraper_adapters.py::test_registry_contains_all_expected_adapters` + `tests/test_scraper_loop.py::test_registry_lists_all_expected_sources`
- `compute_backfill_chunk_starts`, `_run_backfill_chunks` — `services/scraper/app/loop.py`
- Reading-status + permanent-fail HTTP models/routes — state-worker `http.py`, `entries.py`, `transitions.py`
- query-api proxies — `services/query-api/app/routers/entries.py`
- UI `/escalations`, `/explorer` — `services/ui/app/main.py`
- `scripts/verify-m8.sh` — T11-complete vs declared test surfaces
- G6 prefilter gold — `tests/test_g6_prefilter_gold.py`
- G6 enrichment sampling — `.dev/quality/g6-enrichment-template.md` (7/10, owner-waived)

Compose tags: `bishop/scraper:m8`, `bishop/ui:m8`.

---

## Waivers (accepted residual risk)

| ID | Residual |
|----|----------|
| F5 | query-api `READING_STATUS_VALUES` frozenset vs `ReadingStatusEnum` |
| F6 | Overlapping backfill chunk windows |
| F7 | `.dev/architecture/bishop/` partial refresh — landing gate = `project-architecture` pass (not run in this closeout) |
| F8 | G6 Call 1 hook quality; follow-up `g6-call1-hooks-iteration` |
| F9 | HF `fetch_content` Authorization not separately asserted |
| PF1 | Context map stale; follow-up `m8-context-map-refresh` |
| PF2 | Scout coupling tuples lack literal grep patterns |

---

## Explicitly still open (not this closeout)

1. **G7 wet-run** — enable `BISHOP_BACKFILL_ENABLED=1`, watch chunked all-sources ingest to `INDEXED`, no pipeline-error spike. Operator/cluster.
2. **Charter `Status: Active`** and plan `run_status: amended` stay until G7 is recorded (or the owner waives the wet reading in writing).
3. **Architecture folder** (F7) — charter §7 “re-run project-architecture” not executed here.
4. **Context-map refresh** (`m8-context-map-refresh`).
5. **Call 1 hooks** (`g6-call1-hooks-iteration`).

---

## Artifact chain (read order)

| Path | Notes |
|------|-------|
| `.dev/plans/m8-hardening-scale/plan.md` | v1.5; ceremony `audit_status: accepted-with-waivers` |
| `.dev/audits/2026-09-11-m8-hardening-scale.md` | Revision 2 |
| `.dev/audits/2026-09-10-m8-hardening-scale.md` | Revision 1 historical |
| `.dev/plans/m8-hardening-scale/dag.json` | `plan_version: "1.5"` |
| `.dev/plans/m8-hardening-scale/packets/` | T1…T12 including bis |
| `.dev/plans/m8-hardening-scale/runs/` | Ledger + briefs + execution-summary |
| `.dev/decision-logs/m8-hardening-scale/` | T1, T4, T5, T8 |
| `.dev/plans/m7-read-path/handoff.md` | M8 entry |
| `.dev/bishop_program_charter.md` | v0.1.0; still Active |
| `CHANGELOG.MD` | M8 T-bullets |
| `.dev/changelogs/M8-hardening-scale.md` | This closeout |

`.dev/plans/m9-source-expansion/proposal.md` is **not** an M8 deliverable and is **not** a charter M9. See that file: proposal v0.1, pre-M8 corpus thesis, stale vs landed M8 adapters.

---

## Charter §7 housekeeping this closeout

- [x] Auditor §8 recorded (`accepted-with-waivers`)
- [x] This `handoff.md`
- [x] `.dev/changelogs/M8-hardening-scale.md`
- [x] Decision logs already exist for architectural nodes
- [ ] Architecture folder refresh (F7 — deferred)
- [ ] Clean tree at a single handoff SHA (this file lands in the closeout commit)
- [ ] G7 wet-run + `docker compose` result (explicitly out of this closeout)
