# M2 — Discovery Slice · Auditor §8 Handoff

**Plan:** `m2-discovery` v1.1  
**Status:** Complete — ready for adversarial audit  
**Charter slice:** `.dev/bishop_program_charter.md` L184–231  
**Normative spec:** `bishop_spec_0_6.md` v1.5.0 (tracked)

---

## §8.1 Completion snapshot

**Tree SHA:** `0954ea8d4bc9b48b271a500d2b6a5004150365c2`

**Tracked-tree cleanliness at implementation SHA:** `git status` clean (all T1–T5 implementation artifacts committed).

**Handoff recording note:** `.dev/plans/m2-discovery/` (plan, context-map, packets, this handoff) was **untracked** at `0954ea8`. Auditor should read implementation at `0954ea8` and plan artifacts from the commit that adds this directory, or from working tree if handoff lands in a follow-up commit.

**Executor commit chain** (`7e8be99`…`0954ea8`):

| Commit | Subtask | Summary |
|--------|---------|---------|
| `febf62c` | T1 | `bishop_shared/enums.py`, scraper config, DTOs, `StateWorkerClient`, Dockerfile skeleton |
| `5c3c45a` | T2 | `SourceAdapter` ABC, Arxiv-only `ADAPTER_REGISTRY`, `RateLimit`, token bucket |
| `fa98e72` | T3 | `failure_envelope`, exception types, §6.3 classification |
| `d6c94bc` | T4 | `ArxivAdapter` Atom export API + fixture tests |
| `0954ea8` | T5 | `scrape_cycle`, scheduler, `bishop/scraper:m2`, `verify-m2.sh`, loop tests |

**Primary automated verification (M2 gate — run at handoff recording):**

```
Command: python -m pytest tests/test_state_worker_contract.py tests/test_state_worker_health.py tests/test_constants.py tests/test_scraper_adapters.py tests/test_scraper_arxiv_adapter.py tests/test_scraper_client.py tests/test_scraper_config.py tests/test_scraper_failure_envelope.py tests/test_scraper_loop.py tests/test_scraper_models.py tests/test_scraper_rate_limit.py tests/test_shared_enums.py tests/test_verify_m2.py -v --tb=short
Environment: win32, Python 3.12.3, pytest 8.4.2
Result: 78 passed, 27 warnings (alembic DeprecationWarning), exit code 0
```

**Equivalent bash gate:**

```
Command: scripts/verify-m2.sh
```

**Full regression slice (recommended auditor sanity check):**

```
Command: pytest tests/ -q
Environment: win32, Python 3.12.3, pytest 8.4.2
Result: 197 passed, 1 failed, exit code 1
Failure: tests/test_state_worker_routers_escalations.py::test_escalations_returns_flagged_entry_with_error_log
  — pre-existing M1 T8 side-effect (ALERT sibling row in error_log); not introduced by M2
```

**Live Docker gate:** Not executed at handoff recording. CHANGELOG defers live `docker compose up scraper state-worker` smoke to manual validation.

---

## §8.2 Artifact chain

Read order for auditor. `git show 0954ea8:<path>` at implementation SHA unless noted.

| Path | Resolves at `0954ea8` | Notes |
|------|----------------------|-------|
| `.dev/plans/m2-discovery/context-map.md` | **No** — untracked | Scout SHA `7e8be99`; stale vs implementation — treat interface inventory as prediction |
| `.dev/plans/m2-discovery/plan.md` | **No** — untracked | v1.1 Complete + §8 embedded |
| `.dev/plans/m2-discovery/handoff.md` | **No** — untracked | This file |
| `.dev/plans/m2-discovery/packets/T1.md` … `T5.md` | **No** — untracked | Executor packets |
| `.dev/decision-logs/m2-discovery/T1-scraper-foundation.md` | Yes | |
| `.dev/decision-logs/m2-discovery/T2-adapter-registry.md` | Yes | |
| `.dev/decision-logs/m2-discovery/T4-arxiv-atom-api.md` | Yes | T3 standard tier — no decision log |
| `bishop_spec_0_6.md` | Yes | Binding normative reference |
| `CHANGELOG.MD` | Yes | M2 T1–T5 entries |
| `bishop_shared/enums.py` | Yes | |
| `services/scraper/app/` | Yes | Full scraper package |
| `services/scraper/Dockerfile` | Yes | CMD `python -m app.main` |
| `docker-compose.yml` | Yes | `bishop/scraper:m2` |
| `scripts/verify-m2.sh` | Yes | |
| `tests/test_scraper_*.py`, `tests/test_shared_enums.py`, `tests/test_verify_m2.py` | Yes | |
| `.dev/plans/m1-state-kernel/plan.md` | Yes | M2 entry gate G2 source |

---

## §8.3 §2 evidence

| §2 binding | Landed artifact | Proof test |
|------------|-----------------|------------|
| `SourceEnum`, `DomainEnum` | `bishop_shared/enums.py` | `test_shared_enums_match_state_worker` |
| `ManifestIngestEntry`, batch/state DTOs | `services/scraper/app/models.py` | `test_manifest_ingest_entry_round_trip` |
| `STATE_WORKER_BASE_URL` | `services/scraper/app/config.py:L7` | `test_state_worker_url_default` |
| `ARXIV_CATEGORIES` | `config.py:L9` | `test_arxiv_categories_default` |
| `ARXIV_BACKFILL_WINDOW_DAYS` default 7 | `config.py:L19` | `test_arxiv_backfill_window_default` |
| `SCRAPER_SCHEDULE_INTERVAL_SEC` default 21600 | `config.py:L20` | `test_schedule_interval_default` |
| `StateWorkerClient` | `state_worker_client.py` | `tests/test_scraper_client.py` |
| `RateLimit`, `SOURCE_RATE_LIMITS` arxiv | `rate_limit.py:L22–29` | `test_arxiv_rate_limit_matches_spec` |
| `TokenBucketRateLimiter` | `rate_limit.py:L33+` | `test_token_bucket_throttles` |
| `SourceAdapter` ABC | `adapters/base.py` | `test_source_adapter_contract` |
| `fetch_content` → `NotImplementedError("M4")` | `adapters/base.py:L28–30` | `test_source_adapter_contract` |
| `ADAPTER_REGISTRY` Arxiv-only | `adapters/registry.py:L30` | `test_registry_contains_only_arxiv` |
| `failure_envelope` | `failure_envelope.py` | `tests/test_scraper_failure_envelope.py` |
| `RETRIABLE_HTTP` / `ESCALATABLE_HTTP` | `failure_envelope.py:L24–25` | `test_429_retried`, `test_403_escalatable` |
| `ArxivAdapter` Atom API | `adapters/arxiv.py` | `tests/test_scraper_arxiv_adapter.py` |
| `make_source_id` | `adapters/base.py:L32–34` | `test_make_source_id` |
| Rate limiter inside adapter (§15.3) | `adapters/arxiv.py:L165–166` (`acquire` before `get`) | `test_token_bucket_throttles` + code inspection |
| `scrape_cycle` §10.3 | `loop.py` | `test_scrape_cycle_posts_batch_and_updates_state` |
| `run_scheduler` | `main.py:L15–23` | `test_scheduler_invokes_cycle` |
| Image tag `bishop/scraper:m2` | `docker-compose.yml` | `test_image_tags_use_milestone_convention` |
| M2 gate script | `scripts/verify-m2.sh` | `tests/test_verify_m2.py` |
| Idempotency on re-run | `loop.py` + state-worker skip | `test_scrape_cycle_rerun_reports_skipped_idempotent_rows` |
| 429 absorbed without crash | `loop.py` + envelope | `test_scrape_cycle_survives_429_via_failure_envelope` |
| Permanent failure logged, loop continues | `loop.py:L62–63` | `test_scrape_cycle_logs_permanent_failure_and_continues` |
| Scraper state updated only after batch POST | `loop.py:L51–60` | `test_scrape_cycle_skips_state_update_on_batch_failure` |

---

## §8.4 §5 disposition

### §5.2 load-bearing assumptions

| Tuple | Disposition | Evidence |
|-------|-------------|----------|
| G2 state-worker contract tests pass at M2 start | **closed** | G2 slice in `verify-m2.sh`; 25 passed in gate run |
| ArXiv Atom export API available | **treat-as-prediction** | CI uses fixtures only; live API not gated in pytest |
| Scraper does not import state-worker `app` | **closed** | Scraper Dockerfile copies `bishop_shared` + `services/scraper/app` only |
| `ADAPTER_REGISTRY` exactly ArxivAdapter | **closed** | `registry.py` + `test_registry_contains_only_arxiv` |
| First-run `since` uses 7-day default | **closed** | `config.py` + `resolve_effective_since` + config test |

### §5.4 hidden couplings

| Tuple | Disposition | Evidence |
|-------|-------------|----------|
| C1 domain `"professional"` on batch wire | **closed** | `ArxivAdapter.domain = PROFESSIONAL`; arxiv adapter tests assert domain |
| C2 compose image tag matrix m0/m1/m2 | **closed** | `test_compose.py` updated for scraper `:m2` |
| C3 idempotency via state-worker skip | **closed** | `test_scrape_cycle_rerun_reports_skipped_idempotent_rows` |
| C4 rate limiter inside adapter | **closed** | `arxiv.py:L165` acquire before HTTP; not a separate acquire-order unit test |
| C5 httpx/respx in dev deps | **closed** | `pyproject.toml` optional-deps dev |

### Context-map flags (§0)

| Flag | Disposition |
|------|-------------|
| 1 Enum sharing via `bishop_shared` | **closed** |
| 2 Atom export API | **closed** |
| 3 7-day backfill default | **closed** |
| 4 No scraper tests | **closed** |
| 5 stub deprecation | **closed** — `stub_main.py` removed; `test_scraper_uses_real_main_entrypoint` |
| 6 M1 handoff.md absent | **treat-as-prediction** — unchanged from M1 |

### Pre-execution orch decisions

User confirmed plan defaults 2026-06-12 (enum sharing, Atom API, 7-day window, asyncio scheduler, `fetch_content` M4 stub).

### Auditor hygiene (non-blocking unless policy requires)

- No architectural decision log for T3 (standard tier — per plan).
- `.dev/architecture/bishop/` not post-M2 refreshed (charter §7 housekeeping deferred).
- Live docker compose e2e not automated in `verify-m2.sh` (deferred per CHANGELOG T5).
- `registry.py` retains T1 bootstrap `ImportError` stub — dead path after T4; harmless.
- Malformed Atom entries without `id`/`title` silently skipped — documented in T4 decision log.
- Full-suite `test_escalations_returns_flagged_entry_with_error_log` failure inherited from M1 T8 — **open** for program hygiene, **not M2 blocking**.

---

## §8.5 Cold-read seeds

Narrative-blind Phase 0 — contract-vs-code drift surfaces:

1. `services/scraper/app/loop.py` — §10.3 cycle ordering, error branches, scraper_state update guard
2. `services/scraper/app/adapters/arxiv.py` — Atom query construction, `resolve_effective_since`, rate limiter placement
3. `services/scraper/app/failure_envelope.py` — RETRIABLE/ESCALATABLE sets vs spec §6.3
4. `services/scraper/app/state_worker_client.py` — wire JSON shapes vs M1 `http.py`
5. `bishop_shared/enums.py` — drift from `services/state-worker/app/enums.py`
6. `tests/test_scraper_loop.py` — M2 exit-gate falsifiers (429, idempotency, permanent failure)

---

## §8.6 Audit remediation cross-link

Absent — no §7 amendments fired during M2 v1.0.

---

## Landed contracts summary (M3 pre-plan seed)

**Symbols extended (new in M2):**

- `SourceAdapter` ABC — `services/scraper/app/adapters/base.py`
- `ADAPTER_REGISTRY` — `services/scraper/app/adapters/registry.py` (Arxiv only)
- `ArxivAdapter` — `services/scraper/app/adapters/arxiv.py`
- `failure_envelope`, `PermanentFailureError`, `EscalatableError`, `RetryExhaustedError`
- `RateLimit`, `SOURCE_RATE_LIMITS`, `TokenBucketRateLimiter`
- `StateWorkerClient` — manifest batch + scraper-state HTTP client
- `ManifestIngestEntry` and related scraper wire DTOs
- `bishop_shared.enums.SourceEnum`, `DomainEnum` (cross-service; state-worker not refactored)
- `scrape_cycle`, `run_scheduler`
- Compose `bishop/scraper:m2`; `scripts/verify-m2.sh`

**M2 exit gate:** `scripts/verify-m2.sh` / M2 pytest slice green (78 tests).

**M3 entry gate:** M2 checkpoint — scraper produces `DISCOVERED` manifest rows; G3 (Anthropic model string) blocks M3 LLM work only.

**Runnable checkpoint (charter):** `docker compose up scraper state-worker` → scraper calls ArXiv → `POST /manifest/batch` → manifest rows at `DISCOVERED`; `scraper_state` updated; re-run idempotent; 429 retried in envelope (unit-tested; live ArXiv optional manual).
