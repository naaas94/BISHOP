# Audit — harvest-mill-loop

**Audit date:** 2026-09-17
**Auditor skill:** auditor-review v1.0 · **Fan-out policy:** operating-posture v0.5
**Plan audited:** `.dev/plans/harvest-mill-loop/plan.md` v1 (`run_status: complete`; §8 still `audit_status: not_run`)
**HEAD at audit:** `dc90d83518402c87059c7144633d512369895e30` — confirmed via `git rev-parse HEAD`.
**Charter binding:** none (plan mode: standard). No §Milestone handoff.

## Audit metadata

- **Context map:** `.dev/plans/harvest-mill-loop/context-map.md`, scout SHA `9afcb991f3a041b3e1dbf676508706861de0dd76`, readiness **CONDITIONAL**.
- **Focus areas chosen (Phase 4):** (1) **Integration seams** (mandatory — scout Surfaces 1–7), (2) **Concurrency / ordering** (mill vs scrape Search + mill vs release sqlite; this is the load-bearing change from 90s/6h hitchhike to 90s/5s sibling loop), (3) **Failure paths** (`_mill_loop` exception swallow, `BISHOP_HARVEST_ENABLED` no-op).
- **Operating-posture disclosure:** Phase 0.5 provenance greps and two pytest runs (naive full `pytest -q` + mill-scoped command) were dispatched to Grok 4.6 high subagents against a detached worktree at `dc90d83`. Severity, intent-drift vs coverage-gap, and the verdict are this agent's.
- **Not a re-audit.** No prior harvest-mill-loop audit file.

---

## §Provenance log (Phase 0.5)

- **Context map path / readiness:** `.dev/plans/harvest-mill-loop/context-map.md`, CONDITIONAL at planning.
- **SHA comparison:** **diverged.** Scout pin `9afcb991`. Audit HEAD `dc90d83`. Direct-scope files that changed on `9afcb991..HEAD`: `services/scraper/app/config.py`, `loop.py`, `main.py`, `tests/test_harvest_github.py`, `tests/test_scraper_config.py`, `tests/test_scraper_loop.py`. Unchanged in that range: `harvest_github.py`, `harvest_release.py`, `docker-compose.yml`, `tests/test_compose.py`, `bishop_shared/harvest_ledger.py`, `bishop_shared/constants.py`. Filed **F1** `context-map-stale`.
- **Working-tree state at scout time:** dirty (harvest pickup / decision-log / backlog / AGENTS / CHANGELOG / economics.yaml / operator-next plan). Mill code paths were clean at scout; orch §0 disposition 11 re-verified. At **audit** time the working tree is dirty again (`CHANGELOG.MD`, `harvest-pool-next.md`, `product-backlog.yaml`, `AGENTS.md`, `config/harvest/economics.yaml`, other ops notes, plus uncommitted run briefs). Code findings below are against **HEAD `dc90d83`**, not the dirty overlay. `dirty-state caveat` on any finding that would be read from working-tree markdown: **F6/F7**.
- **Scout grep coverage:** scout recorded `harvest_github_slices`, `BISHOP_HARVEST_`, `BISHOP_SCRAPER_SCHEDULE_INTERVAL_SEC`, `BISHOP_HARVEST_SLICE_BUDGET_SEC`, `scrape_cycle`, `asyncio.gather`, `/manifest/batch`, harvest ledger paths, Search URL, `SOURCE_RATE_LIMITS`, `ManifestIngestEntry`. No `scout-incomplete` for missing §5.4 vocabulary; `BISHOP_HARVEST_MILL_INTERVAL_SEC` did not exist at scout time.
- **Plan-artifact provenance** (`git cat-file -e HEAD:<path>`):

| Artifact | Status |
|---|---|
| `context-map.md`, `plan.md`, `dag.json`, packets T1–T4 | present-in-HEAD |
| `.dev/decision-logs/ops/harvest-mill-loop.md` | present-in-HEAD |
| `CHANGELOG.MD`, `harvest-pool-next.md`, `product-backlog.yaml`, `tests/test_product_backlog.py` | present-in-HEAD |
| `runs/ledger.md`, `runs/execution-summary.md` | present-in-HEAD **but content is the 22:45Z pre-flight halt**, not the completed run |
| `runs/T1-brief.md` … `T4-brief.md` | **on-disk-only** (absent-from-HEAD) |

  Closure SHA: plan §8.1 is still `TBD` / `audit_status: not_run`. Code closure used for this audit is T4 commit `dc90d83`. Filed **F2** `artifact-not-in-HEAD`.

---

## Context chain completeness

| Artifact | Provided |
|---|---|
| Context map | yes |
| Plan §1 + §2 (Phase 0) then full plan (Phase 1+) | yes |
| Packets T1–T4 | yes (HEAD) |
| Decision log T3 | yes (HEAD) |
| Changelog `## harvest-mill-loop — 2026-09-17` | yes (HEAD) |
| Codebase at `dc90d83` | yes |
| Test suite | yes — full naive `pytest` (pre-existing `app` collision) + mill-scoped command on a clean worktree |
| Executor briefs | on disk, **not** in HEAD |
| Plan §8 filled snapshot | **missing** (skeleton) |

Phase 0 completed and was pinned before decision log, changelog, context-map coupling prose, and packets-beyond-§2 were consumed.

---

## §Cold-read log (Phase 0)

Allowed inputs only: task statement, plan §2, `git diff 8c3b3a7..dc90d83` on code/tests.

1. `config.py` adds `BISHOP_HARVEST_MILL_INTERVAL_SEC = _int_from_env(..., 5)`. Tests cover default, override, and empty-string `ValueError`. Matches §2 typed surface.
2. `loop.py` `scrape_cycle` no longer calls `harvest_github_slices`. `import httpx` remains (needed by `_scrape_adapter`). Hitchhike isolation test deleted; replaced by a **source-grep** falsifier that does not execute `scrape_cycle`.
3. `main.py` adds `_mill_loop`: per-tick `httpx.Timeout(30.0)`, deadline from `BISHOP_HARVEST_SLICE_BUDGET_SEC`, sleep `BISHOP_HARVEST_MILL_INTERVAL_SEC`, `event="harvest_mill_failed"`, gathered as third sibling. Module docstring still says "scrape and release" only.
4. `_mill_loop` does not take `StateWorkerClient` and does not call `post_manifest_batch` — mill stays unpaid sidecar fill.
5. Mill and scrape now overlap in-process. Search 429 / sqlite busy are live, not 90s-per-6h leftovers.
6. Extra file `tests/test_product_backlog.py` pins PB-011 shipped / PB-012 deferred / pickup language / changelog marker.
7. `test_mill_loop_does_not_gate_on_harvest_enabled` is a source-slice assertion, not a runtime `BISHOP_HARVEST_ENABLED=0` run of `_mill_loop`.
8. No `_mill_loop` test injects an exception to prove swallow-and-sleep (contract waived in §2).

---

## Findings table

| ID | Severity | Type | Phase | Subtask | One-line |
|---|---|---|---|---|---|
| F1 | major (non-blocking; intended delta) | context-map-stale | 0.5 | orch | Scout SHA `9afcb991` ≠ HEAD `dc90d83` on the mill files the plan was written to change |
| F2 | **major (blocking)** | artifact-not-in-HEAD | 0.5 | plan-runner | HEAD `runs/ledger.md` + `execution-summary.md` still say pre-flight halt; T1–T4 briefs exist on disk only |
| F3 | minor | intent-drift | 1 | T4 / orch | Pickup Deferred PB-012 line still says "while harvest only moves every 6h" after mill loop landed (packet forbade rewriting that bullet) |
| F4 | minor | undeclared-change / prediction-divergence | 1 | T1–T3 | `CHANGELOG.MD` edited in T1–T3 though those packets' Files to touch omitted it; T4 also added `tests/test_product_backlog.py` via executor §2.2 |
| F5 | minor | coverage-gap | 5 | T2 | `test_scrape_cycle_no_longer_calls_harvest_github_slices` is source-grep only (disclosed in T2 changelog) |
| F6 | observation | decision-log-stale | 3 | T3 (deferred) | `.dev/decision-logs/ops/harvest-pool-first-landing.md` still describes hitchhike; T3 named this as out-of-files-to-touch follow-up |
| F7 | observation | process-violation (disclosed) | 1 | T4 | `AGENTS.md` still says next code is PB-011; T4 deferred to auditor-review |
| F8 | observation | process-violation (pre-existing) | 2 | — | Naive `pytest -q` at repo root: 87 failed / 16 errors from `app` package shadowing; mill-scoped suite 57 passed |

---

## Detailed findings (above minor)

### F1 — `context-map-stale` (major, non-blocking)

**Expected:** scout SHA equals audit HEAD, or plan §8.2 names a refresh/deferral follow-up.
**Found:** map generated at `9afcb991`; mill implementation commits `1948a72`–`dc90d83` changed the scout's `direct` files. This is the designed outcome of executing the plan, same disposition as `.dev/audits/2026-09-11-m8-hardening-scale.md` PF1. Plan §8.2 was never filled (still skeleton), so there is no named `harvest-mill-loop-context-map-refresh` follow-up in the plan.
**Action:** report, do not re-explore in this pass. Does not block merge of the mill code by itself.

### F2 — `artifact-not-in-HEAD` (major, **blocking**)

**Expected:** a later reader of `git show HEAD:.dev/plans/harvest-mill-loop/runs/` can recover per-subtask commits and that the DAG completed.
**Found:**

- `HEAD:.dev/plans/harvest-mill-loop/runs/ledger.md` ends at T1–T4 `blocked_by=preflight:plan-absent`.
- `HEAD:.../execution-summary.md` says **Run status: halted @ pre-flight**.
- Completed-run ledger/summary and `T1-brief.md`–`T4-brief.md` are working-tree only.

Code commits T1–T4 **are** in HEAD (`1948a72`, `4411142`, `6a5eadf`, `dc90d83`). The mill implementation is recoverable from `git log`. The **run record** is not. That is the auditor's merge-archaeology surface.
**Action:** commit updated `runs/ledger.md`, `runs/execution-summary.md`, and the four briefs (or delete the halt-era files from HEAD if the operator wants run state gitignored — then say so in the plan). Until then, do not treat this plan as archive-complete.

---

## Adversarial test log (Phase 4)

### Focus 1 — Integration seams (scout surfaces)

| Surface | Result | Notes |
|---|---|---|
| 1 Search quota mill vs incremental | **passes** (residual 429 as designed) | Separate limiters kept (Flag 3 / alt (c)). Mill `_search` `raise_for_status` → `_mill_loop` `except Exception` logs `harvest_mill_failed` and sleeps. Incremental GitHub stays on `failure_envelope`. Not serialized; not a silent share of `SOURCE_RATE_LIMITS`. |
| 2 ledger.sqlite mill vs 60s release | **unknown** (no new test) | `connect_rw` still `busy_timeout` only, no WAL. Overlap **increased** (90s/5s vs 90s/6h). Orch §0 deferred WAL. Not an `adversarial-fail` against shipped mill body (`harvest_github.py` untouched). Flag for coverage as observation under F8 class, not a new major. |
| 3 hitchhike starvation | **passes** | Hitchhike removed; mill has own sleep. |
| 4 HARVEST_DB_PATH / volume | **passes** (untouched) | Compose harvest volume unchanged; mill still uses `harvest_db_path()`. |
| 5 mill never POSTs DISCOVERED | **passes** | `harvest_github.py` untouched; `test_harvest_does_not_call_post_manifest_batch` still present; `_mill_loop` has no `StateWorkerClient`. |
| 6 SOURCE_RATE_LIMITS vs Search 30/min | **passes** | `_SEARCH_RATE_LIMIT` still 1/2s; `test_harvest_uses_search_rate_limit_not_rest_budget` still present. |
| 7 gather three tasks / shared client | **ruled-out** | Mill uses its own `AsyncClient` per tick and does not share the scrape/release `StateWorkerClient`. Scout's disproof path holds. |

### Focus 2 — Concurrency

- **Scenario:** scrape GitHub `fetch_manifest` (Search) overlapping `_mill_loop` Search.
- **Expected:** mill does not use REST 5000/h bucket; failures do not cancel `_scrape_loop`.
- **Actual:** separate tasks in `asyncio.gather`; mill exceptions stay inside `_mill_loop`; scrape exceptions stay inside `_scrape_adapter`. **passes**.
- **Scenario:** mill `connect_rw` held across a 90s walk vs release `connect_rw` every 60s.
- **Expected:** busy_timeout or SQLITE_BUSY logged, not process crash.
- **Actual:** not exercised by tests. **unknown**.

### Focus 3 — Failure paths

- **Scenario:** `harvest_github_slices` raises.
- **Expected:** log `harvest_mill_failed`, sleep, retry (packet + §2).
- **Actual:** code matches. No pytest. Plan waived. **passes** as code-read; coverage waived (see §2 Error envelope).
- **Scenario:** `BISHOP_HARVEST_ENABLED=0`.
- **Expected:** mill loop still scheduled; inner function returns immediately.
- **Actual:** `harvest_github.py` still early-returns; `_mill_loop` has no `if BISHOP_HARVEST_ENABLED`. Source test `test_mill_loop_does_not_gate_on_harvest_enabled`. **passes**.

Seams waiver: **not waived** — map couplings are real; all confirmed tuples were checked.

---

## Coverage gap list

| Priority | Gap | Disposition |
|---|---|---|
| Low | T2 hitchhike removal is grep-not-exec (`F5`) | Disclosed; T3 wiring test is the execution-path proof |
| Low | `_mill_loop` exception swallow | Plan-waived; sibling `_release_loop` also untested |
| Low | SQLITE_BUSY mill vs tap under 90s/5s cadence | Pre-existing ledger API; cadence makes overlap more likely; no mill-plan test |
| n/a | Flag 4 gather-of-three | **Closed** by `test_scheduler_invokes_scrape_release_and_mill` |

Kill criteria vs tests:

- T1: env default/override + empty-env — covered.
- T2: `rg` no mill symbols in `loop.py`; scoped pytest — covered at T2 commit; confirmed 57 passed at `dc90d83`.
- T3: patchable `harvest_github_slices`; unscoped mill pytest; decision log path; import-not-redefine interval — covered.
- T4: no `economics.yaml` in `git show --stat` of `dc90d83`; PB-012 still `deferred`; changelog marker in one dated section — covered by `tests/test_product_backlog.py`.

---

## Phase 2 — Test execution

**SHA:** detached worktree at `dc90d83518402c87059c7144633d512369895e30` (not the dirty main tree).

**Naive full suite** (skill-mandatory first action):

- Command: `pytest -q --color=no` (cwd worktree; `pyproject.toml` `testpaths = ["tests"]`, no `heavy` marker)
- Collected 964 · **857 passed, 87 failed, 4 skipped, 16 errors**, exit 1, 60.08s
- Failures are `app.db` / `app.transitions` / `app.index_entry` / `app.models` **cross-service import collisions**, plus m5 batch listing and compose path-absolute diffs. Same class documented in the M8 audit. **None of the mill files appear in the failed/error list.**
- **Not** recorded as a mill `contract-violation` critical. Observation **F8**.

**Plan-declared + T4 closeout command** (operative gate):

- Command: `pytest tests/test_scraper_loop.py tests/test_scraper_config.py tests/test_harvest_github.py tests/test_product_backlog.py -q --color=no`
- **57 passed, 0 failed, 0 skipped, 0 errors, exit 0**

### §2 contract compliance (code at HEAD)

| Row | Result |
|---|---|
| `BISHOP_HARVEST_MILL_INTERVAL_SEC` `_int_from_env(..., 5)` in `config.py` | holds; tests named in §2 plus empty-env falsifier |
| `_mill_loop() -> None` async in `main.py` | holds; `test_mill_loop_symbol_exists` / gather wiring |
| `run_scheduler` gathers three loops | holds |
| `scrape_cycle` hitchhike removed | holds; grep + T2 falsifier |
| Error envelope `harvest_mill_failed` | **byte-equal** in `main.py`; waived semantic test |
| Naming `_mill_loop`, `BISHOP_HARVEST_*` | holds |
| Logging retired `harvest_slice_failed` | gone from `services/`; remains only in plan/packet prose |
| CLI | N/A |
| Compose / `.env.example` mill interval | absent at HEAD, as contracted |
| `economics.yaml` / Dockerfile / new worker | not in `8c3b3a7..dc90d83` mill diff |

Typed-surface three legs for `BISHOP_HARVEST_MILL_INTERVAL_SEC`: (a) module constant, (b) `_int_from_env` parse (empty string raises, not `or 5`), (c) default + override tests. **holds**.

---

## Phase 1 — Intent traceability (after cold read)

- Intent (unbounded mill + `$N` tap, mill off the 6h scrape clock, same scraper process) → plan §1 → T1 config, T2 remove hitchhike, T3 `_mill_loop`, T4 narrative. **Construction = completion** for `_mill_loop`: `run_scheduler` `asyncio.gather(..., _mill_loop())` is the path the wiring test waits on.
- Non-goals: no new compose service; `economics.yaml` untouched in mill commits; no PB-012 cutover in scraper adapters; no HF rewind; `ManifestIngestEntry` untouched. **honored**.
- Map `direct` files not in §4: `harvest_github.py`, `adapters/github.py`, `harvest_ledger.py`, `constants.py`, `queries.yaml`, `Dockerfile`, `docker-compose.yml` — orch §0 Flag 2 + "only call site moves" documents the narrowing. Not a silent drop of mill *loop* scope.
- `_scrape_loop` scout `suspect_modified`: **not modified**. Prediction overreach; orch §2 did not list it. `prediction-divergence` observation only (not tabled; inventory miss, not shipped defect).

Phase 3: T3 decision log **matches** code (single call site, dedicated sleep env, separate Search limiter, 5s default, no `BISHOP_HARVEST_ENABLED` on the loop). Rejected dual-call is absent. Deferred items were not absorbed except T1–T3 changelog extras (**F4**).

---

## Verdict

**`fail`**

Blocking: **F2** (`artifact-not-in-HEAD`). HEAD still archives a halted run. Commit the completed ledger, execution summary, and T1–T4 briefs (or an explicit gitignore + plan note). Then re-audit under re-audit discipline.

Non-blocking majors: **F1** (map stale because the mill files changed — intended).

Minor / observation: F3–F8. Do not block the mill *code* on those; F3/F7 are leftover operator-doc lines T4 was told not to rewrite or that sat outside Files to touch.

This auditor does **not** edit the plan. Closure-ceremony field writes are **not** listed: ceremony applies on a passing audit.

---

## Scout-prediction reconciliation

| Scout prediction | Description (verbatim gist) | Outcome | Finding |
|---|---|---|---|
| ambiguity Flag 1 | After mill loop, does `scrape_cycle` still call mill? | **verified** — single call site in `_mill_loop` | — |
| ambiguity Flag 2 | What env is mill sleep? | **verified** — new `BISHOP_HARVEST_MILL_INTERVAL_SEC` default 5, no compose pin | — |
| ambiguity Flag 3 | Shared vs two Search buckets? | **verified** — two buckets as today | — |
| ambiguity Flag 4 | Test that `run_scheduler` gathers mill? | **verified** — `test_scheduler_invokes_scrape_release_and_mill` | — |
| Surface 1 confirmed | mill concurrent with incremental Search → 429 | **verified** handled (separate limiters + mill catch) | — |
| Surface 2 confirmed | mill vs release SQLITE_BUSY | **not-tested** (busy_timeout only; overlap increased) | obs in Phase 4 |
| Surface 3 confirmed | hitchhike 90s/6h starvation | **verified** removed | — |
| Surface 4 confirmed | HARVEST_DB_PATH / volume | **verified** untouched | — |
| Surface 5 confirmed | mill never posts DISCOVERED | **verified** | — |
| Surface 6 confirmed | not SOURCE_RATE_LIMITS | **verified** | — |
| Surface 7 suspected | third gather shares client/limiter/sqlite | **ruled-out** | — |
| `scrape_cycle` / `run_scheduler` suspect_modified | | **verified** modified as planned | — |
| `_scrape_loop` suspect_modified | | **prediction-divergence** (unchanged) | not filed (inventory over-predict) |

---

## Closure notes for operator

- Mill **code** at `dc90d83` matches plan §1/§2. Rebuild `scraper` (`bishop/scraper:m8`) before expecting live 5s mill ticks.
- Re-audit after F2 is committed. Do not archive the plan tree until verdict is `pass` or `pass-with-conditions`.
