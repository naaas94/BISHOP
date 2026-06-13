# M4 — Content Slice · Auditor §8 Handoff

**Plan:** `m4-content` v1.0  
**Status:** Complete — ready for adversarial audit  
**Charter slice:** `.dev/bishop_program_charter.md` L286–328  
**Normative spec:** `bishop_spec_0_6.md` v1.5.0 (tracked)

---

## §8.1 Completion snapshot

**Tree SHA:** `117d62f989e48e667fb24b3c0ccf7969f0c467d3`

**Tracked-tree cleanliness at implementation SHA:** `git status` clean at `117d62f` (T1–T4 code committed).

**Handoff recording note:** This file is authored after `117d62f`. Auditor should treat `117d62f` as the implementation anchor; read handoff from the commit that adds it, or from working tree if handoff lands in a follow-up commit.

**Executor commit chain** (`0d6238f`…`117d62f`):

| Commit | Subtask | Summary |
|--------|---------|---------|
| `0d6238f` | T1 | `ArxivAdapter.fetch_content` — HTML fetch + title/abstract fallback, helpers, unit tests, decision log |
| `5d843dd` | T2 | `content-scraper` service — poll loop, failure mapping, vendored `scraper_app/`, Dockerfile CMD `python -m app.main` |
| `2f200fb` | T3 | M4 provenance exit-gate regression tests (enrichment NULL at SCRAPED, 409 envelope, poll-claim path) |
| `117d62f` | T4 | `verify-m4.sh`, compose `:m4` tag, integration SCRAPED + SCRAPE_FAILED tests, stub-removal falsifier |

**Primary automated verification (M4 gate — run at handoff recording):**

```
Command: python -m pytest tests/test_state_worker_contract.py tests/test_state_worker_health.py tests/test_constants.py tests/test_verify_m4.py tests/test_arxiv_fetch_content.py tests/test_content_scraper_config.py tests/test_content_scraper_client.py tests/test_content_scraper_failure_mapping.py tests/test_content_scraper_loop.py tests/test_m4_provenance_contract.py tests/test_m4_integration.py -v --tb=short
Environment: win32, Python 3.14.2, pytest 9.0.2
Result: 75 passed, 32 warnings (alembic DeprecationWarning), exit code 0
```

**Equivalent verify-m4.sh slices (pytest parity):**

```
G2 slice:  33 passed (test_state_worker_contract + health + constants)
M4 slice:  42 passed (verify_m4 + arxiv_fetch_content + content_scraper_* + m4_provenance + m4_integration)
```

**Equivalent bash gate:**

```
Command: scripts/verify-m4.sh
```

**Full regression slice (recommended auditor sanity check):**

```
Command: pytest tests/ -q
Environment: win32, Python 3.14.2, pytest 9.0.2
Result: 304 passed, 1 failed, exit code 1
Failure: tests/test_state_worker_routers_escalations.py::test_escalations_returns_flagged_entry_with_error_log
  — pre-existing M1 T8 side-effect (ALERT sibling row in error_log); not introduced by M4
```

**Live Docker gate:** Not executed at handoff recording. CHANGELOG defers live `docker compose up content-scraper state-worker` smoke to manual validation (M3 pattern).

---

## §8.2 Artifact chain

Read order for auditor. `git show 117d62f:<path>` at implementation SHA unless noted.

| Path | Resolves at `117d62f` | Notes |
|------|----------------------|-------|
| `.dev/plans/m4-content/context-map.md` | Yes | Scout SHA `a072787` — **stale** vs implementation; treat interface inventory as prediction |
| `.dev/plans/m4-content/plan.md` | Yes | v1.0 |
| `.dev/plans/m4-content/handoff.md` | **No** at `117d62f` — follow-up commit | This file |
| `.dev/plans/m4-content/packets/T1.md` … `T4.md` | Yes | Executor packets |
| `.dev/decision-logs/m4-content/T1-arxiv-fetch-content.md` | Yes | |
| `.dev/decision-logs/m4-content/T2-content-scraper-vendor-layout.md` | Yes | |
| `.dev/plans/m3-prefilter/handoff.md` | Yes | M4 entry gate |
| `.dev/architecture/bishop/` | Yes @ `241514e` | Post-M4 refresh in plan commit; stale vs `117d62f` only if code drift after arch commit |
| `bishop_spec_0_6.md` | Yes | Binding normative reference |
| `CHANGELOG.MD` | Yes | M4 T1–T4 entries |
| `services/scraper/app/adapters/arxiv.py` | Yes | T1 `fetch_content` |
| `services/content-scraper/app/` | Yes | Full worker package |
| `services/content-scraper/Dockerfile` | Yes | `scraper_app` vendor + `python -m app.main` |
| `docker-compose.yml` | Yes | `bishop/content-scraper:m4` |
| `scripts/verify-m4.sh` | Yes | |
| `tests/test_arxiv_fetch_content.py` | Yes | |
| `tests/test_content_scraper_*.py` | Yes | |
| `tests/test_m4_provenance_contract.py` | Yes | |
| `tests/test_m4_integration.py` | Yes | |
| `tests/test_verify_m4.py` | Yes | |

---

## §8.3 §2 evidence

| §2 binding | Landed artifact | Proof test |
|------------|-----------------|------------|
| `ArxivAdapter.fetch_content` | `services/scraper/app/adapters/arxiv.py:L238+` | `test_fetch_content_uses_html_on_success`, `test_fetch_content_falls_back_on_404` |
| `parse_raw_id_from_source_id` | `arxiv.py:L141+` | `test_parse_raw_id_from_source_id` |
| `fetch_arxiv_html_text` | `arxiv.py:L188+` | `test_fetch_arxiv_html_text_returns_stripped_text` |
| `compose_fallback_content` | `arxiv.py:L182+` | `test_compose_fallback_content_with_abstract` |
| `strip_html_to_text` | `arxiv.py:L175+` | `test_strip_html_to_text_ignores_script_and_style` |
| `ARXIV_HTML_BASE_URL` | `arxiv.py:L21` | wired in `fetch_arxiv_html_text` |
| Adapter contract (no M4 stub) | `tests/test_scraper_adapters.py` | `test_source_adapter_contract` expects real content |
| `ManifestPollEntry` | `services/content-scraper/app/models.py` | `test_manifest_poll_entry_round_trip` |
| `CONTENT_SCRAPE_BATCH_SIZE` default 10 | `config.py:L17` | `test_content_scrape_batch_size_default` |
| `CONTENT_SCRAPE_POLL_INTERVAL_SEC` default 120 | `config.py:L18` | `test_content_scrape_poll_interval_default` |
| `STATE_WORKER_BASE_URL` | `config.py:L7` | `test_state_worker_url_default` |
| `poll_relevance_passed` | `state_worker_client.py:L32+` | `test_poll_relevance_passed_calls_wire_route` |
| `post_content` | `state_worker_client.py:L45+` | `test_post_content_posts_wire_payload` |
| `post_failed` | `state_worker_client.py:L53+` | `test_post_failed_posts_wire_payload` |
| `resolve_adapter` | `adapter_resolver.py:L14+` | `test_content_scrape_cycle_unknown_source_skips_entry` |
| `map_adapter_exception_to_failed` | `failure_mapping.py:L17+` | `tests/test_content_scraper_failure_mapping.py` (4 cases) |
| `content_scrape_cycle` | `loop.py:L31+` | `test_content_scrape_cycle_happy_path_posts_content`, failure + empty poll tests |
| `failure_envelope` wrap | `loop.py:L74-78` | happy path asserts `failure_envelope` called with `fetch_content` |
| `scraper_app` vendor layout | `Dockerfile:L11-15` | `test_scraper_app_fetch_content_importable_via_vendor_layout` |
| CMD `python -m app.main` | `Dockerfile:L19` | `test_content_scraper_uses_real_main_entrypoint` |
| `assert_pre_filter_provenance` (M1, verified T3) | `transitions.py:L194+`, invoked `L779` | `test_m4_create_entry_from_content_calls_assert_pre_filter_provenance` |
| Enrichment fields NULL at SCRAPED | `create_entry_from_content` insert path | `test_m4_create_entry_leaves_enrichment_fields_sql_null` |
| Provenance 409 envelope | `entries.py` router | `test_m4_post_content_provenance_incomplete_returns_409` |
| Poll claim → SCRAPE_QUEUED | manifest poll + content POST | `test_m4_content_post_after_poll_claim_uses_scrape_queued_state` |
| Compose `bishop/content-scraper:m4` | `docker-compose.yml:L54` | `tests/test_compose.py` tag matrix |
| M4 gate script | `scripts/verify-m4.sh` | `tests/test_verify_m4.py` |
| E2e SCRAPED + `content_raw` | integration harness | `test_m4_e2e_content_scrape_cycle_reaches_scraped_with_content_raw` |
| E2e SCRAPE_FAILED + `is_retriable` | integration harness | `test_m4_e2e_retriable_fetch_failure_yields_scrape_failed_and_error_log` |
| Decision logs T1/T2 | `.dev/decision-logs/m4-content/` | Present at HEAD |

---

## §8.4 §5 disposition

### §5.2 load-bearing assumptions

| Tuple | Disposition | Evidence |
|-------|-------------|----------|
| ArXiv fetch_content useful without PDF/LaTeX | **treat-as-prediction** | HTML+fallback landed and tested mocked; live ArXiv HTML coverage not gated in CI |
| M1 provenance + Entry creation complete for M4 | **closed** | T3 regression tests; no state-worker code changes |
| content-scraper sole `POST /entries/content` writer in M4 | **closed** | Only content-scraper loop posts content; discovery scraper unchanged |
| SCRAPE_QUEUED + is_retriable → SCRAPE_FAILED | **closed** | `test_m4_e2e_retriable_fetch_failure_yields_scrape_failed_and_error_log` |
| vendored scraper_app matches T1 fetch_content | **closed** | `test_scraper_app_fetch_content_importable_via_vendor_layout`; Dockerfile COPY full `services/scraper/app` |

### §5.4 hidden couplings

| Tuple | Disposition | Evidence |
|-------|-------------|----------|
| C1 T1 scraper source vs Docker COPY scraper_app | **closed** | Dockerfile copies `services/scraper/app` → `scraper_app/`; vendor import test |
| C2 poll claim SCRAPE_QUEUED → content POST source_id | **closed** | `test_m4_content_post_after_poll_claim_uses_scrape_queued_state`, integration e2e |
| C3 M3 provenance required before content POST | **closed** | integration seeds pre-filter results; provenance 409 test |
| C4 compose tag matrix m4 | **closed** | `tests/test_compose.py` |
| C5 sys.modules app collision in integration tests | **closed** | `test_m4_integration.py` uses isolated loader + temp vendor dir; 2/2 integration tests pass |

### Context-map flags (§0 orch resolutions)

| Flag | Resolution | Disposition |
|------|------------|-------------|
| 1 ArXiv full-content strategy | T1 HTML + fallback | **closed** |
| 2 Adapter vendoring | T2 `scraper_app/` + sed rewrite | **closed** |
| 3 Missing content-scraper tests | T2 unit + T4 integration | **closed** |
| 4 Poll DTO → ingest DTO | `_poll_entry_to_ingest` in `loop.py` | **closed** |

### Auditor hygiene (non-blocking unless policy requires)

- Context map scout SHA (`a072787`) stale vs implementation (`117d62f`) — expected; pre-plan for M5 should re-explore.
- Full-suite `test_escalations_returns_flagged_entry_with_error_log` failure inherited from M1 T8 — **open** for program hygiene, **not M4 blocking**.
- Live docker compose e2e not automated in `verify-m4.sh` (deferred per CHANGELOG T4).
- Malformed `source_id` without colon — deferred per T1 decision log; pipeline assumes canonical form.
- Content POST 409 branches (invalid_transition, provenance) in loop: logs ERROR and continues — covered by state-worker tests; loop branch not separately integration-tested (T2 deferral).

---

## §8.5 Cold-read seeds

Narrative-blind Phase 0 — contract-vs-code drift surfaces:

1. `services/content-scraper/app/loop.py` — poll state, `failure_envelope` wrap, content vs failed POST ordering
2. `services/content-scraper/app/failure_mapping.py` — `is_retriable` mapping vs §6.3 table
3. `services/scraper/app/adapters/arxiv.py` — `fetch_content` HTML URL, fallback composition
4. `services/content-scraper/Dockerfile` — `scraper_app` COPY + sed rewrite completeness
5. `services/state-worker/app/transitions.py` — `create_entry_from_content` provenance assertion + SCRAPED transition guards
6. `tests/test_m4_integration.py` — charter exit-gate falsifiers (SCRAPED `content_raw`, SCRAPE_FAILED + error_log)

---

## §8.6 Audit remediation cross-link

Absent — no §7 amendments fired during M4 v1.0.

---

## Landed contracts summary (M5 pre-plan seed)

**Symbols extended (new in M4):**

- `ArxivAdapter.fetch_content`, `parse_raw_id_from_source_id`, `fetch_arxiv_html_text`, `compose_fallback_content`, `strip_html_to_text` — `services/scraper/app/adapters/arxiv.py`
- `content_scrape_cycle`, `_poll_entry_to_ingest` — `services/content-scraper/app/loop.py`
- `map_adapter_exception_to_failed` — `services/content-scraper/app/failure_mapping.py`
- `resolve_adapter` — `services/content-scraper/app/adapter_resolver.py`
- Content-scraper `StateWorkerClient` — poll `RELEVANCE_PASSED`, POST content/failed
- Config: `CONTENT_SCRAPE_BATCH_SIZE`, `CONTENT_SCRAPE_POLL_INTERVAL_SEC`
- Docker vendored `scraper_app/` package (image-only)
- Compose `bishop/content-scraper:m4`
- `scripts/verify-m4.sh`

**M4 exit gate:** `scripts/verify-m4.sh` / M4 pytest slice green (75 tests in handoff recording run). Integration demonstrates `entries.content_raw` non-null at `SCRAPED` and retriable `SCRAPE_FAILED` with `error_log.is_retriable=1`.

**M5 entry gate:** M4 checkpoint — entries at `SCRAPED` with `content_raw` populated; G3 model string verified (from M3). Pre-filter provenance on manifest rows consumed into `Entry` at content POST.

**Runnable checkpoint (charter):** `docker compose up content-scraper state-worker` → content-scraper polls `RELEVANCE_PASSED`, fetches via ArXiv adapter, POSTs `POST /entries/content`; state-worker creates `Entry` at `SCRAPED` with enrichment fields null and provenance copied from manifest.

---

## Read-only review summary (orchestrator)

**Intent alignment:** All four charter exit criteria addressed in code/tests — `fetch_content` for ArXiv, content-scraper poll loop, provenance assertion (M1 verified, not reimplemented), SCRAPE_FAILED path with `ErrorLog` and `is_retriable`.

**Non-goals:** No state-worker REST extension, no non-ArXiv adapters, no enrichment/indexing paths touched. Hub restriction honored.

**Highest residual risk:** HTML+fallback `content_raw` quality at scale (plan §5.3 T1 prediction) — acceptable for M4 gate; M5 truncation and quality sampling own downstream impact.

**Verdict:** Ready for adversarial audit at SHA `117d62f`.
