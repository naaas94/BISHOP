# Orchestrator plan — harvest-mill-loop

**Plan version:** v1
**run_status:** complete
**Mode:** standard (no charter stub)
**Context map:** `.dev/plans/harvest-mill-loop/context-map.md` (already at its promoted path — no `_pending` move needed)
**Packets:** `.dev/plans/harvest-mill-loop/packets/T1.md` … `T4.md`
**DAG (machine surface):** `.dev/plans/harvest-mill-loop/dag.json`

---

## 0. Context map intake

- **Path consumed:** `.dev/plans/harvest-mill-loop/context-map.md`
- **Readiness verdict:** CONDITIONAL
- **Scope-area labels flagged:** Flag 1 (ownership — dual-call vs single call site), Flag 2 (vocabulary_collision — mill-interval env), Flag 3 (implicit/ownership — Search rate-limiter buckets), Flag 4 (missing_test_coverage — no gather-of-mill test)
- **Skill version / commit SHA the map was generated against:** pre-plan-exploration v0.7 @ `9afcb991f3a041b3e1dbf676508706861de0dd76` (branch `dev`, dirty). Verified at plan time: `services/scraper/app/main.py`, `loop.py`, `harvest_github.py`, `config.py`, `harvest_release.py`, `docker-compose.yml`, `.env.example`, `tests/test_scraper_loop.py`, `tests/test_harvest_github.py`, `tests/test_scraper_config.py` were re-read directly during planning (2026-09-17) — no drift found from the map's characterization of any of these files.

**Numbered dispositions (map instructions, ambiguity flags, and handoff notes):**

1. **Flag 1 (ownership — dual-call risk)** → `resolved`. Decision: `scrape_cycle` (`loop.py`) stops calling `harvest_github_slices` entirely; the only production call site becomes the new `_mill_loop` in `main.py`. No dual-call state is shipped. See §2 Types/interfaces and T2/T3.
2. **Flag 2 (vocabulary_collision — mill sleep env)** → `resolved`. Decision: new constant `BISHOP_HARVEST_MILL_INTERVAL_SEC` (default `5`), read directly via `os.environ` in `services/scraper/app/config.py` like `BISHOP_HARVEST_WINDOW_DAYS` / `BISHOP_HARVEST_SLICE_BUDGET_SEC` / `BISHOP_HARVEST_QUERY_ID` today — **not** added to `docker-compose.yml` or `.env.example`. This matches the existing precedent: none of those three sibling harvest-tuning envs has compose/`.env.example` passthrough either. `BISHOP_HARVEST_SLICE_BUDGET_SEC` (default `90`, unchanged) continues to bound each mill iteration's Search-walk duration; `BISHOP_HARVEST_MILL_INTERVAL_SEC` is the new sleep between iterations of the mill's own loop (replacing the old "wait `BISHOP_SCRAPER_SCHEDULE_INTERVAL_SEC` (6h)" coupling to the scrape tick).
3. **Flag 3 (implicit/ownership — Search rate-limiter buckets)** → `resolved`. Decision: no change. Mill keeps its own private `_SEARCH_RATE_LIMIT` (`harvest_github.py`, 1 call/2s, reconstructed fresh every `harvest_github_slices` invocation) fully separate from `GitHubAdapter`'s `SOURCE_RATE_LIMITS` (5000/h REST budget) used by incremental `fetch_manifest`. This plan does not introduce in-process sharing of either bucket.
4. **Flag 4 (missing_test_coverage — no 3-loop gather test)** → `checklist row`. T3 adds a wiring test asserting `run_scheduler` gathers scrape, release, **and** mill loops (see §2 Tests row, T3 kill criteria).
5. **Orchestrator handoff note — "Copyable pattern is `_release_loop`"** → `resolved`. `_mill_loop` follows `_release_loop`'s shape exactly: `while True: try: <one tick> except Exception: logger.exception(...) finally-implicit; await asyncio.sleep(<interval>)`. It does **not** gate on `BISHOP_HARVEST_ENABLED` itself — `harvest_github_slices` already no-ops when the flag is off (same as `release_once` self-gating inside `_release_loop`).
6. **Orchestrator handoff note — "Daily ingest must stay live"** → `resolved`. `_scrape_loop` and its `SCRAPER_SCHEDULE_INTERVAL_SEC` cadence are untouched; only the harvest hitchhike sub-block is removed from `scrape_cycle`.
7. **Kill-criterion candidate — "no `economics.yaml` `daily_budget_usd` change"** → `checklist row`. `config/harvest/economics.yaml` is not in any subtask's Files to touch. T4's kill criteria explicitly forbids touching it.
8. **Kill-criterion candidate — "no `post_manifest_batch` from mill"** → `checklist row`. Unaffected — this plan does not touch `harvest_github.py`'s body; `tests/test_harvest_github.py::test_harvest_does_not_call_post_manifest_batch` already pins this and is left passing, untouched by any subtask.
9. **Kill-criterion candidate — "no new worker"** → `checklist row`. Confirmed by design: `_mill_loop` is a third coroutine inside the existing `scraper` service's `asyncio.gather`, not a new compose service, new Dockerfile, or new entrypoint.
10. **Kill-criterion candidate — "harvest exceptions must not fail incremental scrape if hitchhike remains even briefly"** → `resolved` (moot). Hitchhike is fully removed, not left briefly; `scrape_cycle` no longer has any harvest-related code path to fail. The prior isolation test (`test_scrape_cycle_harvest_failure_still_posts_discovered`) is deleted as part of T2 because its scenario no longer exists (see §2 Tests row and T2 Outputs).
11. **Dirty-tree warning — "Mill code paths were not in the truncated dirty list at scout time — verify at orch §0"** → `resolved`. Verified directly during planning via `git status --porcelain` against `services/scraper/app/main.py`, `loop.py`, `harvest_github.py`, `config.py`, `docker-compose.yml`, `tests/test_harvest_github.py`, `tests/test_scraper_loop.py`, `tests/test_compose.py`: **all clean** (no local modifications). This plan is starting from a clean baseline on these files.
12. **query-api note — "`_harvest_stats` zeros on sqlite3.Error; mill WAL not enabled today"** → `deferred (rationale)`. Out of scope per the map's explicit exclusion (`services/query-api/**` is `adjacent`, not `direct`); no subtask touches `stats_reader.py` or `connect_rw`'s pragma set. No follow-up ID needed — this is pre-existing behavior the mill's own-loop cadence does not change (mill already wrote to the same sidecar from inside `scrape_cycle` before this plan).

Consumption mapping (context map → this plan): §File map direct rows → §4 Files to touch; §Interface inventory `suspect_modified` rows (`scrape_cycle`, `run_scheduler`, `_scrape_loop`) → §2 seed; §Coupling surfaces 1/2/3/4/5/6 → confirmed as unaffected by this plan's scope (mill's ledger/rate-limit/DB-path/no-DISCOVERED-post behavior is untouched code — only the call site moves); Surface 3 and Surface 7 → directly resolved by this plan (that is the plan's purpose); §Ambiguity flags → dispositions 1–4 above; §Prior reasoning → PB-011's own summary text is reproduced verbatim in §1 below, not contradicted.

---

## 1. Task statement

Move the GitHub harvest mill (`harvest_github_slices`) off its current hitchhike inside `scrape_cycle` (90s slice budget, then a 6h wait for the next scrape tick) and give it its own third `asyncio` loop inside the existing `scraper` process's `run_scheduler`, sibling to `_scrape_loop` and `_release_loop`. The mill keeps writing unpaid closed-range GitHub Search results into the harvest sidecar (`ledger.sqlite`) until its cursor (`next_window_start`) reaches `harvest_until`, now decoupled from the scrape schedule so the 2-year backfill walk is not starved to ~90s every 6 hours.

**Non-goals** (verbatim from the context map's task description):
- Not a new worker / compose service.
- Not the `$2` → `$3` daily-budget faucet change (`config/harvest/economics.yaml` `daily_budget_usd` stays untouched).
- Not the GitHub incremental cutover (PB-012) — incremental `fetch_manifest` keeps POSTing `DISCOVERED` exactly as today.
- Not paper/LW/OR/SS exhaust into the sidecar.
- Not a Hugging Face rewind.
- Not widening `ManifestIngestEntry`.

No charter governs this plan (mode: standard); §1 charter-binding fields are not applicable.

---

## 2. Shared contracts

| Topic | Content |
|---|---|
| Types / interfaces | See table below |
| Error envelope | `_mill_loop` catches `Exception` broadly per tick and logs via `logger.exception(event="harvest_mill_failed")`, then sleeps and retries — identical shape to `_release_loop`'s `event="harvest_release_failed"` handling. No new exception types. |
| Naming | New symbol: `_mill_loop` (function, `services/scraper/app/main.py`), matching the existing `_scrape_loop` / `_release_loop` naming convention. New constant: `BISHOP_HARVEST_MILL_INTERVAL_SEC` (`services/scraper/app/config.py`), matching the existing `BISHOP_HARVEST_*` prefix convention. |
| Logging | New structured event `harvest_mill_failed` (mirrors `harvest_release_failed`). The retired event `harvest_slice_failed` (previously logged from inside `scrape_cycle`'s hitchhike block) is removed — grep-confirmed nowhere else in the repo references that literal (dashboards, tests, or docs) before removal. |
| Tests | pytest + `pytest-asyncio`. Locations: `tests/test_scraper_config.py` (new constant), `tests/test_scraper_loop.py` (hitchhike-patch cleanup + new 3-loop gather wiring test), `tests/test_harvest_github.py` (delete obsolete hitchhike-isolation test; relocate the 30s-httpx-timeout source assertion from `loop.py` to `main.py`). |
| CLI surface | N/A — no CLI flags or subcommands are introduced, removed, or consumed by any subtask. |

**Types / interfaces (typed-surface binding table):**

| Symbol | Binding site | Owning subtask | Test | Enforcement |
|---|---|---|---|---|
| `BISHOP_HARVEST_MILL_INTERVAL_SEC` | module-level constant, `services/scraper/app/config.py`, via `_int_from_env("BISHOP_HARVEST_MILL_INTERVAL_SEC", 5)` | T1 | `tests/test_scraper_config.py::test_harvest_mill_interval_default`, `::test_harvest_mill_interval_env_override` | pytest-enforced |
| `_mill_loop` | module-function, `services/scraper/app/main.py`, signature `() -> None` (async) | T3 | `tests/test_scraper_loop.py::test_scheduler_invokes_scrape_release_and_mill` (asserts `hasattr(main_mod, "_mill_loop")` and that `run_scheduler`'s gather completes only when all three loops have started) | pytest-enforced |
| `run_scheduler` | module-function, `services/scraper/app/main.py`, signature unchanged `() -> None` — body extended to `asyncio.gather(_scrape_loop(client), _release_loop(client), _mill_loop())` | T3 | same as above | pytest-enforced |
| `scrape_cycle` | module-function, `services/scraper/app/loop.py`, signature unchanged `(client: StateWorkerClient \| None = None) -> None` — body loses the harvest hitchhike sub-block only | T2 | `tests/test_harvest_github.py::test_scrape_cycle_no_longer_calls_harvest_github_slices` (source-grep falsifier, mirrors the existing `test_harvest_does_not_call_post_manifest_batch` style) plus all pre-existing `scrape_cycle` tests in `tests/test_scraper_loop.py` passing without patching `BISHOP_HARVEST_ENABLED` | pytest-enforced |

**Error envelope row — enforcement:** `docs-structural`. No semantic falsifier — waived: the exception-swallow behavior of `_release_loop` (the pattern `_mill_loop` copies verbatim) has no dedicated test today either; adding one only for the new mill loop would be an inconsistent, unrequested precedent relative to its sibling. The wiring test (T3) does prove the loop *starts*; it does not prove exception-swallow specifically.

**Naming row — enforcement:** pytest-enforced (via the `hasattr(main_mod, "_mill_loop")` assertion named above).

**"No pin exists" claim — grep-scope-qualified.** The claim "no compose/`.env.example` pin exists today for `BISHOP_HARVEST_WINDOW_DAYS` / `BISHOP_HARVEST_SLICE_BUDGET_SEC` / `BISHOP_HARVEST_QUERY_ID`" (used to justify not adding one for `BISHOP_HARVEST_MILL_INTERVAL_SEC` either) was established by: (a) a full-text grep of `docker-compose.yml` for `BISHOP_HARVEST_` (only `BISHOP_HARVEST_DAILY_BUDGET_USD` and `BISHOP_HARVEST_ENABLED` present), and (b) a full-text grep of `.env.example` for `HARVEST` (same two keys only). Not an id-scoped grep on a single test file.

**Declared vs operative test command (T2 ↔ T3 sequencing).** Because `tests/test_harvest_github.py::test_harvest_http_client_uses_30s_timeout` asserts the literal `"httpx.Timeout(30.0)"` against `loop.py`'s source today, and T2 deletes that literal from `loop.py` (it lives inside the removed hitchhike block) while T3 is the subtask that re-introduces the literal into `main.py`'s source, the full suite is **expected to be red between T2 landing and T3 landing** on this one test. T2's own verification command is scoped: `pytest tests/test_scraper_loop.py tests/test_scraper_config.py tests/test_harvest_github.py -k "not test_harvest_http_client_uses_30s_timeout" -q`. T3's verification command is the unscoped full command: `pytest tests/test_scraper_loop.py tests/test_scraper_config.py tests/test_harvest_github.py -q`, which must be fully green — that is the plan's real gate, not T2's scoped run.

---

## 3. Dependency DAG

```
T1 (config.py: new env const) ---\
                                   +--> T3 (main.py: mill loop + decision log) --> T4 (changelog/backlog/pickup closure)
T2 (loop.py: remove hitchhike) --/
```

- **Hard edges:** `T1 --> T3`, `T2 --> T3`, `T3 --> T4`.
- **Parallel group:** `{T1, T2}` — **throughput-only** (no HALT-isolation claim; T1 and T2 touch disjoint files and have no runtime dependency on each other — they only both feed T3).
- **Soft dependencies:** none.
- **Gate nodes:** none — every node in this plan owns a packet.

---

## 4. Subtask specs

### T1 — config.py: new mill-interval constant

- **Scope:** Add `BISHOP_HARVEST_MILL_INTERVAL_SEC` (int, env-backed, default `5`) to `services/scraper/app/config.py`, following the existing `_int_from_env` pattern used by `BISHOP_HARVEST_WINDOW_DAYS` / `BISHOP_HARVEST_SLICE_BUDGET_SEC`. Add default + override tests.
- **Files to touch:** `services/scraper/app/config.py`, `tests/test_scraper_config.py`.
- **Contract bindings:** Types/interfaces row 1 (`BISHOP_HARVEST_MILL_INTERVAL_SEC`).
- **Inputs:** none.
- **Outputs:**
  - `services/scraper/app/config.py`: add, immediately after the `BISHOP_HARVEST_QUERY_ID` assignment:
    ```python
    BISHOP_HARVEST_MILL_INTERVAL_SEC = _int_from_env("BISHOP_HARVEST_MILL_INTERVAL_SEC", 5)
    ```
  - `tests/test_scraper_config.py`: add two tests following the existing `test_backfill_inter_chunk_delay_default` / `_env_override` pair's shape:
    - `test_harvest_mill_interval_default` — `monkeypatch.delenv("BISHOP_HARVEST_MILL_INTERVAL_SEC", raising=False)`; assert `config.BISHOP_HARVEST_MILL_INTERVAL_SEC == 5`.
    - `test_harvest_mill_interval_env_override` — `monkeypatch.setenv("BISHOP_HARVEST_MILL_INTERVAL_SEC", "20")`; assert `config.BISHOP_HARVEST_MILL_INTERVAL_SEC == 20`.
- **Kill criteria:** Halt if `BISHOP_HARVEST_MILL_INTERVAL_SEC` already exists anywhere in the repo under a different spelling (re-grep before adding — this plan's own pre-dispatch grep found none). Halt if `_int_from_env` does not exist or its signature differs from `(name: str, default: int) -> int`.
- **Log tier:** standard (contract-anchor override — this constant is consumed by T3).
- **Model class:** mechanical — single-file, additive, no design fork.
- **Risks & mitigations:** None beyond the default-value choice (`5`), which is a plan-level decision recorded in T3's decision log, not a T1 risk.

### T2 — loop.py: remove the scrape_cycle hitchhike

- **Scope:** Remove the harvest hitchhike sub-block from `scrape_cycle` in `services/scraper/app/loop.py` (the `if BISHOP_HARVEST_ENABLED: try: ... harvest_github_slices(...) except Exception: logger.exception("github harvest failed", ...)` block), drop the now-unused imports it required, and repair every test that assumed the hitchhike existed.
- **Files to touch:** `services/scraper/app/loop.py`, `tests/test_scraper_loop.py`, `tests/test_harvest_github.py`.
- **Contract bindings:** Types/interfaces row 4 (`scrape_cycle`). Declared vs operative test command note in §2 applies to this subtask's own verification run.
- **Inputs:** none (does not need T1's new constant).
- **Outputs:**
  - `services/scraper/app/loop.py`:
    - Remove the line `from app.harvest_github import harvest_github_slices`.
    - In the `from app.config import (...)` block, remove the two lines `BISHOP_HARVEST_ENABLED,` and `BISHOP_HARVEST_SLICE_BUDGET_SEC,`. Leave `BISHOP_BACKFILL_CHUNK_DAYS`, `BISHOP_BACKFILL_ENABLED`, `BISHOP_BACKFILL_INTER_CHUNK_DELAY_SEC`, `BISHOP_BACKFILL_WINDOW_OVERRIDE_DAYS` untouched — they are unrelated backfill constants still used elsewhere in the file.
    - **Do not** remove the module-level `import httpx` — it is still required by `_scrape_adapter`'s `except httpx.HTTPStatusError as exc:` clause, which is unrelated to the removed block (see §5.4 hidden coupling #2).
    - Remove the entire hitchhike sub-block from `scrape_cycle` (the `if BISHOP_HARVEST_ENABLED:` through the matching `except Exception: logger.exception("github harvest failed", extra={"event": "harvest_slice_failed"})`), so that after the `for AdapterClass in ADAPTER_REGISTRY:` loop, `scrape_cycle` proceeds directly to `logger.info("scrape cycle complete", ...)`.
  - `tests/test_scraper_loop.py`: remove the line `patch.object(loop_mod, "BISHOP_HARVEST_ENABLED", False),` from each of its six occurrences (inside the `with (...)` blocks of `test_scrape_cycle_posts_batch_and_updates_state`, `test_scrape_cycle_skips_state_update_on_batch_failure`, `test_scrape_cycle_rerun_reports_skipped_idempotent_rows`, `test_scrape_cycle_survives_429_via_failure_envelope`, `test_scrape_cycle_logs_permanent_failure_and_continues`, `test_scrape_cycle_escalatable_failure_skips_batch`). Each `with (...)` block keeps its `patch.object(loop_mod, "ADAPTER_REGISTRY", ...)` line.
  - `tests/test_harvest_github.py`:
    - Delete `test_scrape_cycle_harvest_failure_still_posts_discovered` in full (its scenario — a harvest failure inside `scrape_cycle` — no longer exists once the hitchhike is removed; it currently patches `loop_mod.harvest_github_slices`, an attribute this subtask deletes).
    - Add a new falsifier test near `test_harvest_does_not_call_post_manifest_batch`:
      ```python
      def test_scrape_cycle_no_longer_calls_harvest_github_slices() -> None:
          """Falsifier: hitchhike removed — scrape_cycle must not import/call the mill."""
          source = (
              _REPO_ROOT / "services" / "scraper" / "app" / "loop.py"
          ).read_text(encoding="utf-8")
          assert "harvest_github_slices" not in source
      ```
    - **Do not** touch `test_harvest_http_client_uses_30s_timeout` in this subtask — its relocation to `main.py` is T3's Output (see §2 Declared vs operative test command).
- **Kill criteria:** Halt if, after the edit, `grep -n "harvest_github_slices\|BISHOP_HARVEST_ENABLED\|BISHOP_HARVEST_SLICE_BUDGET_SEC" services/scraper/app/loop.py` returns any hit. Halt if any test in `tests/test_scraper_loop.py` still references `loop_mod.harvest_github_slices` or `patch.object(loop_mod, "BISHOP_HARVEST_ENABLED"`. Run `pytest tests/test_scraper_loop.py tests/test_scraper_config.py tests/test_harvest_github.py -k "not test_harvest_http_client_uses_30s_timeout" -q` and halt if it is not fully green (the one deselected test is expected-red until T3 lands, per §2).
- **Log tier:** standard (contract-anchor override — `scrape_cycle`'s behavior is consumed by `_scrape_loop`/tests; this is a real behavior change even though line-count is small).
- **Model class:** standard — behavior-changing deletion across three files with cross-file test coupling; not purely mechanical.
- **Risks & mitigations:** Risk — an executor could over-remove (e.g. drop the whole `import httpx` line, or the whole `from app.config import (...)` block). Mitigation — the Outputs above name the exact lines to remove and the exact lines to keep.

### T3 — main.py: give harvest its own asyncio loop

- **Scope:** Add `_mill_loop` to `services/scraper/app/main.py`, wire it into `run_scheduler`'s `asyncio.gather` as a third sibling task, relocate the 30s-httpx-timeout source assertion from `loop.py` to `main.py`, add the 3-loop gather wiring test, and write the architectural decision log for this plan's four resolved ambiguity flags.
- **Files to touch:** `services/scraper/app/main.py`, `tests/test_scraper_loop.py`, `tests/test_harvest_github.py`, `.dev/decision-logs/ops/harvest-mill-loop.md` (new).
- **Contract bindings:** Types/interfaces rows 2 and 3 (`_mill_loop`, `run_scheduler`). Error envelope row. Naming row. Declared vs operative test command note in §2 (this subtask's verification is the **unscoped** full command).
- **Inputs:** T1's `BISHOP_HARVEST_MILL_INTERVAL_SEC` (consumed as an import). T2's removal of the hitchhike (this subtask's decision log must reference the post-T2 state of `loop.py` as the "before" state it is replacing).
- **Outputs:**
  - `services/scraper/app/main.py`:
    - Add imports: `import httpx`; `from datetime import UTC, datetime, timedelta`; `from app.config import (BISHOP_HARVEST_MILL_INTERVAL_SEC, BISHOP_HARVEST_RELEASE_INTERVAL_SEC, BISHOP_HARVEST_SLICE_BUDGET_SEC, SCRAPER_SCHEDULE_INTERVAL_SEC)` (replacing the current narrower `from app.config import (...)` import — keep both existing names, add the two new ones); `from app.harvest_github import harvest_github_slices`.
    - Add, after `_release_loop`:
      ```python
      async def _mill_loop() -> None:
          """Own-cadence GitHub Search harvest — no longer hitchhikes on scrape_cycle."""
          while True:
              try:
                  deadline = datetime.now(UTC) + timedelta(
                      seconds=BISHOP_HARVEST_SLICE_BUDGET_SEC
                  )
                  async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as harvest_client:
                      await harvest_github_slices(
                          http_client=harvest_client,
                          deadline=deadline,
                      )
              except Exception:
                  logger.exception(
                      "github harvest mill tick failed",
                      extra={"event": "harvest_mill_failed"},
                  )
              await asyncio.sleep(BISHOP_HARVEST_MILL_INTERVAL_SEC)
      ```
    - Update `run_scheduler`'s docstring to "Run scrape, harvest-release, and harvest-mill loops until cancelled." and its `asyncio.gather(...)` call to `asyncio.gather(_scrape_loop(client), _release_loop(client), _mill_loop())`.
  - `tests/test_scraper_loop.py`: rename `test_scheduler_invokes_scrape_and_release` to `test_scheduler_invokes_scrape_release_and_mill`. Add a third fake coroutine (`milled = asyncio.Event()`; `async def fake_mill(*args, **kwargs): milled.set(); await asyncio.Event().wait()`) patched onto `main_mod.harvest_github_slices` via `patch.object(main_mod, "harvest_github_slices", side_effect=fake_mill)` inside the existing nested `with` blocks; extend the `asyncio.gather(scraped.wait(), released.wait(), milled.wait())` call (still under `asyncio.wait_for(..., timeout=2)`). Also add, in the same test or as a standalone one-line test, `assert callable(main_mod._mill_loop)` to pin the naming contract.
  - `tests/test_harvest_github.py`: update `test_harvest_http_client_uses_30s_timeout` to read `main.py`'s source instead of `loop.py`'s:
    ```python
    def test_harvest_http_client_uses_30s_timeout() -> None:
        """Live GitHub Search exceeded httpx's 5s default; harvest must not."""
        source = (_REPO_ROOT / "services" / "scraper" / "app" / "main.py").read_text(
            encoding="utf-8"
        )
        assert "httpx.Timeout(30.0)" in source
        assert "async with httpx.AsyncClient()" not in source
    ```
  - `.dev/decision-logs/ops/harvest-mill-loop.md` (new, architectural): alternatives considered and chosen for Flags 1–4 (single call site vs dual-call; new env vs reusing `BISHOP_HARVEST_SLICE_BUDGET_SEC`/`BISHOP_HARVEST_RELEASE_INTERVAL_SEC`; separate vs shared Search rate-limiter buckets; the `5`s default rationale — bounded by the mill's own internal 1-req/2s Search throttle, so a short inter-tick sleep does not risk 429s), assumptions made, and deferred items (compose/`.env.example` passthrough deferred as out-of-scope-by-precedent, not forgotten).
- **Kill criteria:** Halt if `main_mod.harvest_github_slices` is not a direct, patchable module-level name (i.e., if the import is aliased or wrapped) — the wiring test depends on `patch.object(main_mod, "harvest_github_slices", ...)` working exactly as `main_mod.scrape_cycle` / `main_mod.release_once` already do today. Run `pytest tests/test_scraper_loop.py tests/test_scraper_config.py tests/test_harvest_github.py -q` (unscoped) and halt if it is not fully green — this is the plan's real full-suite gate (see §2). Halt if the decision log does not exist at `.dev/decision-logs/ops/harvest-mill-loop.md` before this subtask is marked done.
- **Log tier:** architectural (new control-flow pattern — a third `asyncio.gather` task with a mill-vs-tap loop-shape choice; multiple real options existed for Flags 1–3). **Decision log path:** `.dev/decision-logs/ops/harvest-mill-loop.md`.
- **Model class:** architectural — introduces a new coroutine pattern plus a design decision with real alternatives; warrants a reasoning-capable build per operating-posture.
- **Risks & mitigations:** Highest re-plan risk in this plan (see §5.3) — an executor could shape `_mill_loop` to gate on `BISHOP_HARVEST_ENABLED` itself (mirroring `_scrape_loop`'s style) instead of relying on `harvest_github_slices`'s own internal early-return (mirroring `_release_loop`'s style), which the wiring test would not catch since it patches `harvest_github_slices` directly regardless of the surrounding guard. Mitigation — the Outputs code block above is written to be copied verbatim, not paraphrased; the executor's kill criteria include a byte-parity expectation against this exact block.

### T4 — Close out: decision log cross-links, changelog, and backlog

- **Scope:** Land the single consolidated CHANGELOG.MD bullet for this feature, update `harvest-pool-next.md`'s status/next-sequence narrative to reflect the mill loop landing, and flip `product-backlog.yaml` PB-011's status.
- **Files to touch:** `CHANGELOG.MD`, `harvest-pool-next.md`, `product-backlog.yaml`.
- **Contract bindings:** none beyond the general narrative-alignment obligation (back-annotate any prose this plan's landing makes stale).
- **Inputs:** T3's decision log path (`.dev/decision-logs/ops/harvest-mill-loop.md`) and landed `main.py`/`loop.py` state (T2, T3).
- **Outputs:**
  - `CHANGELOG.MD`: one bullet under the current date/section, e.g.: "Harvest GitHub mill now runs as its own asyncio loop (`_mill_loop`, `BISHOP_HARVEST_MILL_INTERVAL_SEC` default 5s) instead of hitchhiking `scrape_cycle`'s 90s/6h tick; `scrape_cycle` no longer calls `harvest_github_slices`. See `.dev/decision-logs/ops/harvest-mill-loop.md`."
  - `harvest-pool-next.md`: update the top **Status** line and the "Cadence (as-built, wrong vs philosophy)" section to note the mill now has its own loop (cross-link the new decision log); move the "Harvest mill loop (PB-011)" bullet out of **Deferred** into a landed note; leave PB-012 (cutover), paper/LW/OR/SS exhaust, and mechanical-drops items untouched in **Deferred**.
  - `product-backlog.yaml`: PB-011 `status: next` → `status: shipped`, `updated:` bumped to today's date. **Do not** change PB-012's `status: deferred`.
- **Kill criteria:** Halt if `config/harvest/economics.yaml` appears in `git diff --stat` for this subtask (forbidden — see §0 disposition 7). Halt if PB-012's `status` field is touched. Halt if the CHANGELOG bullet is added anywhere other than under the current dated section (no duplicate/competing bullets from T1–T3 — this plan consolidates to one bullet, owned here).
- **Log tier:** standard (narrative/backlog edits with a forbidden-file kill criterion, not purely mechanical).
- **Model class:** mechanical — prose/YAML edits with no code, but the "do not touch these two things" constraint makes a spot-check by a standard-capability reviewer worthwhile; mechanical build is still sufficient given the explicit kill criteria.
- **Risks & mitigations:** Risk — narrative drift if `harvest-pool-next.md`'s "Deferred" section is edited loosely. Mitigation — the Outputs bullet above names exactly which line moves and which stay.

---

## 5. Adversarial pass

**Lens used:** packet-only executor persona (each of T1–T4 was answered as if the executor sees only its own packet + the executor SKILL.md).

### 5.1 Rejected decompositions

Considered merging T2 (hitchhike removal) and T3 (mill loop addition) into a single subtask, since they are the two halves of the same behavioral move and both touch `tests/test_scraper_loop.py` / `tests/test_harvest_github.py`. Rejected because: (a) it would force one subtask to carry both a `standard`-tier deletion and an `architectural`-tier new-pattern-plus-decision-log, muddying the log-tier signal; (b) it would prevent T1 from running in parallel with the removal half of the work; (c) keeping them separate makes the "declared vs operative test command" red-window between them an explicit, auditable contract-row instead of an invisible in-subtask implementation detail.

### 5.2 Load-bearing assumptions

1. `(scrape_cycle's only production call to harvest_github_slices is the hitchhike block at loop.py | services/scraper/app/loop.py:135-148 (scrape_cycle) + context-map §Interface inventory "consumed_by: scrape_cycle" | if an untracked second call site exists, removing only this one leaves a hidden dual-call state | T2,T3)` — **derived** (premise: a repo-wide grep for `harvest_github_slices` during planning found exactly two non-test references — the import and call inside `loop.py`'s `scrape_cycle` — and no others; falsifiable by T2's own kill-criterion re-grep before landing).
2. `(BISHOP_HARVEST_MILL_INTERVAL_SEC has no compose/.env.example passthrough by design, matching the existing unexposed WINDOW_DAYS/SLICE_BUDGET/QUERY_ID envs | docker-compose.yml scraper environment block (lines 33-41) + .env.example lines 31-33 | if the operator actually needs day-to-day tuning of mill cadence via .env, this plan ships a knob reachable only via direct container env override | T1,T4)` — **invariant** (operator-locked precedent already established by the first harvest landing; changing it is a plan amendment, not an executor judgment call).
3. `(test_harvest_http_client_uses_30s_timeout's literal moves from loop.py to main.py in the same wave, so the suite is expected-red between T2 landing and T3 landing | tests/test_harvest_github.py::test_harvest_http_client_uses_30s_timeout | if T2 and T3 are ever dispatched in separate sessions rather than back-to-back, an intermediate CI run will show this test failing and could be mistaken for a T2 regression | T2,T3)` — **derived** (premise: T2 removes the only occurrence of the literal `"httpx.Timeout(30.0)"` from `loop.py`; falsifiable by grepping `loop.py` post-T2 for that literal).
4. `(harvest_github.py's rate limiter and httpx client are reconstructed fresh on every deadline-bounded call, so a short 5s BISHOP_HARVEST_MILL_INTERVAL_SEC does not accumulate open connections or limiter state across mill loop iterations | services/scraper/app/harvest_github.py:_harvest_into (limiter = TokenBucketRateLimiter(...) per call) + main.py's async with httpx.AsyncClient(...) per iteration | a future edit hoisting the limiter or http client to module/loop scope would need to re-evaluate the 5s interval choice for connection reuse or limiter-state carryover | T3)` — **invariant** (locked by `harvest_github.py`'s current implementation, which this plan does not touch; re-open only if that file changes).

### 5.3 Highest re-plan risk

**T3.** It is the only subtask combining a new control-flow pattern (third `asyncio.gather` task), a cross-subtask config dependency (T1's new constant), a sequenced-file dependency (T2's prior edits to the same two test files), and the architectural decision log. **Named failure mode:** an executor could shape `_mill_loop` to gate explicitly on `BISHOP_HARVEST_ENABLED` at the loop level (mirroring `_scrape_loop`'s style, which has no such gate itself but is unconditionally scheduled) instead of relying on `harvest_github_slices`'s own internal early-return (mirroring `_release_loop`'s style, which also has no loop-level gate and instead lets `release_once` self-gate) — the wiring test in T3 patches `harvest_github_slices` directly and would pass under either shape, so a guard-placement divergence from the packet's literal code block would ship undetected by that test alone.

### 5.4 Hidden couplings

1. `(tests/test_scraper_loop.py and tests/test_harvest_github.py are each touched by both T2 and T3 | tests/test_scraper_loop.py (6 patch-removal edits + 1 renamed/extended wiring test), tests/test_harvest_github.py (1 test deletion + 1 test relocation) | parallel dispatch of T2 and T3 would produce a merge conflict or a silently-lost edit on the shared test files | T2,T3)` — **confirmed** (both subtasks' Outputs above name overlapping tests/line-ranges in the same two files). **Bound:** hard edge `T2 --> T3` in the DAG; no parallel dispatch of this pair.
2. `(loop.py's module-level "import httpx" is also required by _scrape_adapter's unrelated "except httpx.HTTPStatusError" clause | services/scraper/app/loop.py (import httpx; _scrape_adapter exception handling ~line 214) | an executor removing the hitchhike block could over-eagerly strip the whole "import httpx" line, breaking the unrelated exception handler | T2)` — **confirmed** (grep of `loop.py` shows `httpx.HTTPStatusError` used independently of the removed block). **Bound:** T2's Outputs explicitly state "Do not remove the module-level `import httpx`."
3. `(BISHOP_HARVEST_ENABLED is still imported and used independently inside harvest_github.py and harvest_release.py | services/scraper/app/harvest_github.py:29, services/scraper/app/harvest_release.py:12 | removing loop.py's local import of BISHOP_HARVEST_ENABLED (T2) must not be conflated with removing the constant from config.py itself | T1,T2)` — **confirmed** (grep shows the constant referenced independently in three files today; only `loop.py`'s import is in scope for T2). **Bound:** T1's Files to touch never edits this constant's definition; T2's kill criteria scope the removal to `loop.py`'s own import line only.

---

## 6. Executor packets

Packets are self-contained and saved at `.dev/plans/harvest-mill-loop/packets/T1.md` … `T4.md`. Each carries the required YAML frontmatter (`subtask_id`, `tier`, `model_class`, `skills`, `decision_log_path` where applicable). A byte-parity check was performed between this plan's §4 concrete-edit blocks (the `_mill_loop` code block in particular) and each packet's copy before finalizing — no drift.

`dag.json` (machine surface) is at `.dev/plans/harvest-mill-loop/dag.json`, carrying `plan_version: "v1"`, matching this header.

---

## 7. Amendment subtasks

None yet — this is the initial plan version (v1). Any post-dispatch kill-criterion failure, audit finding, or scope change routes through this section in a future plan revision per the skill's amendment rules.

---

## 8. Auditor handoff

**Status:** not yet applicable — no subtask has been dispatched or landed as of this plan version. This section is a pre-authenticated skeleton per the skill's audit-pre-authentication rule; all vocabulary below is intentionally outside the typed audit vocabulary until the auditor has actually run.

- **8.1 Completion snapshot:** `audit_status: not_run`. Tree SHA, verification command, and result: **TBD — filled at closure**, after T1–T4 land and a clean-checkout `pytest tests/test_scraper_loop.py tests/test_scraper_config.py tests/test_harvest_github.py -q` run completes.
- **8.2 Artifact chain:** `.dev/plans/harvest-mill-loop/context-map.md`, `.dev/plans/harvest-mill-loop/plan.md` (this file), `.dev/plans/harvest-mill-loop/packets/T1.md`–`T4.md`, `.dev/decision-logs/ops/harvest-mill-loop.md` (produced by T3). All must `git show HEAD:<path>` successfully at the closure SHA before handoff is valid.
- **8.3 §2 evidence:** to be filled at closure — per-row landed signal (file:symbol + proving test) for each row in §2's typed-surface binding table.
- **8.4 §5 disposition:** to be filled at closure — each §5.2/§5.4 item marked `closed` / `open` / `treat-as-prediction` with evidence.
- **8.5 Cold-read seeds (recommended for the auditor's Phase 0 read):** `services/scraper/app/main.py`, `services/scraper/app/loop.py`, `tests/test_scraper_loop.py::test_scheduler_invokes_scrape_release_and_mill`, `tests/test_harvest_github.py::test_scrape_cycle_no_longer_calls_harvest_github_slices`, `.dev/decision-logs/ops/harvest-mill-loop.md`.
- **8.6 Audit remediation cross-link:** N/A — no §7 amendments have fired in this plan version.
