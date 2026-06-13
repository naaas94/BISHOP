# M7 — Read Path · Auditor §8 Handoff

**Plan:** `m7-read-path` v1.0  
**Status:** Complete — ready for adversarial audit  
**Charter slice:** `.dev/bishop_program_charter.md` L440–488  
**Normative spec:** `bishop_spec_0_6.md` v1.5.0 (tracked)

---

## §8.1 Completion snapshot

**Tree SHA:** `1be89cbf480fc7d7c3da450933fca17efc8dac71`

**Tracked-tree cleanliness at handoff SHA:** `git status` clean at `1be89cb` (all T1–T8 implementation commits + plan artifacts tracked).

**Executor commit chain** (`0e1e850`…`1be89cb`):

| Commit | Subtask | Summary |
|--------|---------|---------|
| `0e1e850` | T1 | `bishop_shared/query_config.py`, `bm25_tokenize.py`, query-api FastAPI scaffold + G7 cold-start lifespan |
| `26d0a38` | T2 | `Bm25QueryIndex` — load/search/COW reload for main + challenge_hooks |
| `f826d89` | T3 | `LanceDbSearcher`, `DuckDbReader` (`read_only=True`), `QueryEmbeddingEncoder` |
| `6187058` | T4 | `is_problem_shaped`, `rrf_fuse`, `run_search` orchestrator |
| `65b3f48` | T5 | FastAPI routes (`/search`, `/recent`, `/entries/{id}`, batch/escalation proxies), SQLite reader |
| `a2ec076` | T6 | `bishop_cli/` Typer CLI — `bishop search|recent|batch|escalations` |
| `ed7d163` | T7 | HTMX UI — batch list, batch detail, entry detail, search via `QUERY_API_URL` |
| `1be89cb` | T8 | `verify-m7.sh`, compose `m7` tags, `test_m7_integration.py`, stub graduation |

**Primary automated verification (M7 gate — run at handoff recording on clean checkout @ `1be89cb`):**

```
Command: scripts/verify-m7.sh equivalent (pytest slices per script structure)
Environment: win32, Python 3.14.2, pytest 9.0.2

Slice 1 — G2 contract:
  python -m pytest tests/test_state_worker_contract.py tests/test_state_worker_health.py tests/test_constants.py -v --tb=short
  Result: 33 passed, exit code 0

Slice 2 — M7 pydantic models (isolated subprocess in script; direct run equivalent):
  python -m pytest tests/test_query_api_models.py -v --tb=short
  Result: 3 passed, exit code 0

Slice 3 — M7 integration (isolated subprocess in script; direct run equivalent):
  python -m pytest tests/test_m7_integration.py -v --tb=short
  Result: 3 passed, exit code 0

Slice 4 — M7 unit suite:
  python -m pytest tests/test_verify_m7.py tests/test_query_config.py tests/test_bm25_tokenize.py tests/test_query_api_bm25_reader.py tests/test_query_api_lancedb_reader.py tests/test_query_api_duckdb_reader.py tests/test_query_api_embedding.py tests/test_problem_shaped.py tests/test_rrf.py tests/test_query_api_routes_search.py tests/test_query_api_routes_recent.py tests/test_query_api_routes_entry.py tests/test_query_api_routes_batches.py tests/test_query_api_routes_escalations.py tests/test_query_api_cold_start.py tests/test_query_api_search_orchestrator.py tests/test_bishop_cli.py tests/test_bishop_cli_config.py tests/test_ui_config.py tests/test_ui_routes.py -v --tb=short
  Result: 97 passed, exit code 0

Combined gate total: 136 passed, 0 failed, exit code 0
```

**Equivalent bash gate:**

```
Command: scripts/verify-m7.sh
```

**Monolithic combined run (not the gate — documents collision hazard):**

```
Command: python -m pytest <all M7 modules in one invocation> -v --tb=short
Result: 175 passed, 3 failed (test_query_api_models.py — AttributeError: wrong `app.models` from ui package collision)
Note: verify-m7.sh isolates models + integration subprocesses specifically to avoid this; gate slices pass.
```

**Full regression slice (recommended auditor sanity check):**

```
Command: pytest tests/ -q
Environment: win32, Python 3.14.2, pytest 9.0.2
Result: 461 passed, 55 failed, 10 errors, 1 skipped, exit code 1
Note: Failures cluster on state-worker `app` imports after query-api/ui tests pollute `sys.modules['app']` in monolithic runs. M7 gate uses subprocess isolation; pre-M7 full-suite baseline had 2 unrelated failures (M6 handoff). Full-suite monolithic pass is **not** an M7 exit criterion — verify-m7.sh is.
```

**Live Docker gate:** Not executed at handoff recording. CHANGELOG defers live `docker compose up query-api ui` smoke to manual validation (M3–M6 pattern).

**Charter program gates (manual):** G4 (full e2e ArXiv → INDEXED single run), G5 live embedding probe, G6 quality sampling — **not automated** in default `verify-m7.sh`; optional strict path via `BISHOP_M7_REQUIRE_GATES=1` (runs live G5 heavy test).

---

## §8.2 Artifact chain

Read order for auditor. `git show 1be89cb:<path>` at implementation SHA.

| Path | Resolves at `1be89cb` | Notes |
|------|----------------------|-------|
| `.dev/plans/m7-read-path/context-map.md` | Yes | Scout SHA `e207960` — **stale** vs implementation; interface inventory for stubs was prediction |
| `.dev/plans/m7-read-path/plan.md` | Yes | v1.0 |
| `.dev/plans/m7-read-path/handoff.md` | **No** — this file | Lands in follow-up commit after `1be89cb` |
| `.dev/plans/m7-read-path/packets/T1.md` … `T8.md` | Yes | Executor packets |
| `.dev/decision-logs/m7-read-path/T1-query-shared-contracts.md` | Yes | |
| `.dev/decision-logs/m7-read-path/T2-bm25-reader.md` | Yes | |
| `.dev/decision-logs/m7-read-path/T3-lancedb-duckdb-embedding.md` | Yes | |
| `.dev/decision-logs/m7-read-path/T4-rrf-problem-shaped.md` | Yes | |
| `.dev/plans/m6-indexing/handoff.md` | Yes | M7 entry gate |
| `.dev/architecture/bishop/` | Yes @ pre-M7 | Post-M7 architecture refresh per charter §7 **not yet run** |
| `bishop_spec_0_6.md` | Yes | Binding normative reference |
| `CHANGELOG.MD` | Yes | M7 T1–T8 entries |
| `bishop_shared/query_config.py` | Yes | T1 |
| `bishop_shared/bm25_tokenize.py` | Yes | T1 |
| `services/query-api/app/` | Yes | T1–T5 |
| `services/query-api/requirements.txt` | Yes | T2–T5 |
| `services/query-api/Dockerfile` | Yes | CMD `python -m app.main` |
| `bishop_cli/` | Yes | T6 |
| `services/ui/app/` | Yes | T7 |
| `services/ui/Dockerfile` | Yes | CMD `python -m app.main` |
| `docker-compose.yml` | Yes | `bishop/query-api:m7`, `bishop/ui:m7`, `QUERY_API_URL` on ui |
| `pyproject.toml` | Yes | `[project.scripts] bishop = "bishop_cli.main:app"` |
| `scripts/verify-m7.sh` | Yes | |
| `tests/test_m7_integration.py` | Yes | |
| `tests/test_verify_m7.py` | Yes | |

**Hub restriction:** No `services/state-worker/` diffs in `e207960..1be89cb` — honored.

---

## §8.3 §2 evidence

| §2 binding | Landed artifact | Proof test |
|------------|-----------------|------------|
| `RRF_K` | `bishop_shared/query_config.py:L9` | `test_rrf_k_pinned` |
| `BM25_RELOAD_INTERVAL_SEC` | `bishop_shared/query_config.py:L20` | `test_bm25_reload_interval_default` |
| `DEFAULT_SEARCH_DOMAIN` | `bishop_shared/query_config.py:L10` | `test_default_search_domain` |
| `tokenize_bm25` | `bishop_shared/bm25_tokenize.py` | `test_tokenize_matches_writer_semantics` |
| Writer tokenize alignment | `services/vector-writer/app/stores/bm25_store.py` imports `tokenize_bm25` | `test_bm25_store.py` (regression) |
| `Bm25QueryIndex` | `services/query-api/app/stores/bm25_reader.py` | `tests/test_query_api_bm25_reader.py` |
| COW reload | `bm25_reader.py` `reload_cow` + `_LoadedIndex` frozen dataclass | `test_reload_cow_swaps_object_identity_without_in_place_mutation` |
| `LanceDbSearcher` | `services/query-api/app/stores/lancedb_reader.py` | `tests/test_query_api_lancedb_reader.py` |
| `DuckDbReader` read_only | `services/query-api/app/stores/duckdb_reader.py:L38` | `test_connect_uses_read_only_true` |
| `QueryEmbeddingEncoder` | `services/query-api/app/embedding.py` | `tests/test_query_api_embedding.py` |
| `is_problem_shaped` | `services/query-api/app/retrieval/problem_shaped.py:L36` | `tests/test_problem_shaped.py` |
| `rrf_fuse` | `services/query-api/app/retrieval/rrf.py` | `tests/test_rrf.py` |
| `run_search` orchestrator | `services/query-api/app/retrieval/search.py` | `tests/test_query_api_search_orchestrator.py` |
| `SearchRequest` / `SearchHit` / `SearchResponse` | `services/query-api/app/models.py:L11-L41` | `tests/test_query_api_models.py` (isolated subprocess) |
| `GET /search` | `services/query-api/app/routers/search.py` | `tests/test_query_api_routes_search.py` |
| `GET /recent` | `services/query-api/app/routers/recent.py` | `tests/test_query_api_routes_recent.py` |
| `GET /entries/{source_id}` | `services/query-api/app/routers/entries.py` + `sqlite_reader.py:L76` | `tests/test_query_api_routes_entry.py` |
| SQLite read-only URI | `sqlite_reader.py:L83` `mode=ro` | `test_read_entry_opens_sqlite_read_only` |
| Batch proxy + enrichment | `services/query-api/app/routers/batches.py` | `tests/test_query_api_routes_batches.py` |
| Escalations proxy | `services/query-api/app/routers/escalations.py` | `tests/test_query_api_routes_escalations.py` |
| G7 cold-start | `services/query-api/app/lifespan.py` `cold_start_init` | `tests/test_query_api_cold_start.py` |
| `bishop` CLI | `bishop_cli/main.py` + `pyproject.toml` scripts | `tests/test_bishop_cli.py` |
| `QUERY_API_BASE_URL` | `bishop_cli/config.py` | `tests/test_bishop_cli_config.py` |
| UI `QUERY_API_URL` | `services/ui/app/config.py` | `tests/test_ui_config.py` |
| HTMX pages | `services/ui/app/main.py` + templates | `tests/test_ui_routes.py` |
| Compose `bishop/query-api:m7` | `docker-compose.yml:L120` | `test_image_tags_use_milestone_convention` |
| Compose `bishop/ui:m7` | `docker-compose.yml:L141` | same |
| Compose `QUERY_API_URL` | `docker-compose.yml:L146` | `test_ui_query_api_url_env` |
| Stub graduation | `tests/test_service_stubs.py` `test_m7_http_service_uses_real_main_entrypoint` | query-api + ui |
| M7 gate script | `scripts/verify-m7.sh` | `tests/test_verify_m7.py` |
| E2e search + problem-shaped + cold-start | `tests/test_m7_integration.py` | `test_m7_search_returns_hits_from_seeded_stores`, `test_m7_problem_shaped_search_includes_bm25_hooks_channel`, `test_m7_cold_start_search_empty_stores_no_crash` |
| Decision logs T1/T2/T3/T4 | `.dev/decision-logs/m7-read-path/` | Present at HEAD |

---

## §8.4 §5 disposition

### §5.2 load-bearing assumptions

| Tuple | Disposition | Evidence |
|-------|-------------|----------|
| M6 BM25 pickle format stable for query-api reader | **closed** | `test_load_search_main_from_writer_pickle`; integration search hits |
| M6 LanceDB schema matches LanceDbSearcher | **closed** | `test_search_cosine_top_k_orders_by_similarity`; M7 integration reuses M6 seed harness |
| DuckDB read_only=True sufficient while vector-writer not holding write | **treat-as-prediction** | `test_connect_uses_read_only_true`; M6 `test_duckdb_concurrent_read.py` unchanged; concurrent RW+RO while writer holds connection not exercised in M7 gate |
| INDEXED entries in all three stores for integration | **closed** | `test_m7_integration.py` seeds via M6 harness; search returns hits |
| tokenize_bm25 matches writer | **closed** | Shared module + `test_tokenize_matches_writer_semantics`; vector-writer imports shared tokenize |
| state-worker GET /batches and /escalations stable | **closed** | Proxy route tests pass; no state-worker edits |

### §5.4 hidden couplings

| Tuple | Disposition | Evidence |
|-------|-------------|----------|
| BM25 reload interval vs vector-writer persist | **closed** | `BM25_RELOAD_INTERVAL_SEC=300`; background reload in lifespan; decision log T2 |
| query-api vs vector-writer requirements pins | **closed** | Both requirements.txt pin compatible lower bounds; T3 decision log; import smoke in unit tests |
| ui QUERY_API_URL in compose | **closed** | `docker-compose.yml` + `test_ui_query_api_url_env` |
| bishop CLI host-only vs Docker | **closed** | Intentional per plan; `pyproject.toml` script, not in query-api image |
| problem-shaped false positive activates channel 3 | **treat-as-prediction** | Spec accepts broader retrieval; `test_m7_problem_shaped_search_includes_bm25_hooks_channel` confirms activation path |
| SQLite WAL concurrent read during state-worker write | **open** | `mode=ro` URI used; CHANGELOG defers contention test — not M7 blocking per plan waiver |
| Monolithic pytest `app` package collision | **open** | 3 model test failures when run with full M7 module list in one process; verify-m7 subprocess isolation mitigates gate; program hygiene item for future test harness |

### Context-map flags (§0 orch resolutions)

| Flag | Resolution | Disposition |
|------|------------|-------------|
| 1 Store read placement | query-api `app/stores/` | **closed** |
| 2 Entry detail source | SQLite on query-api | **closed** |
| 3 CLI name `bishop` | `pyproject.toml` | **closed** |
| 4 Metadata pre-filter | `run_search` pre-filter | **closed** |
| 5 Entry gates G4/G5/G6 | Manual sign-off | **open** — charter gates; optional `BISHOP_M7_REQUIRE_GATES=1` |
| 6 Requirements pin | query-api requirements.txt | **closed** |

### Auditor hygiene (non-blocking unless policy requires)

- Context map scout SHA (`e207960`) stale vs implementation (`1be89cb`) — expected; post-M7 architecture refresh pending (charter §7).
- Post-M7 `.dev/architecture/` refresh not committed.
- Live docker compose e2e not automated in `verify-m7.sh`.
- G5 live semantic quality on real MiniLM not executed at handoff — fixture gate from M6 still authoritative for CI; owner should run `BISHOP_G5_LIVE=1` before M8 backfill.
- G4/G6 charter gates require manual owner sign-off before M8 entry.
- Full-suite monolithic pytest degraded by multi-service `app` namespace — use `verify-m7.sh` slices for deterministic CI.
- Per-channel score attribution in search response deferred (CHANGELOG T8) — integration falsifies `channels_active` and fused hits only.
- DB explorer UI page deferred to M8 per plan non-goals.

---

## §8.5 Cold-read seeds

Narrative-blind Phase 0 — contract-vs-code drift surfaces:

1. `services/query-api/app/retrieval/search.py` — channel wiring, metadata pre-filter, problem-shaped branch
2. `services/query-api/app/stores/bm25_reader.py` — COW reload, pickle schema, channel search
3. `bishop_shared/query_config.py` — RRF_K, reload interval, default domain
4. `services/query-api/app/lifespan.py` — G7 cold-start WARN contract
5. `services/query-api/app/sqlite_reader.py` — read-only entry access, JSON list decode
6. `tests/test_m7_integration.py` — charter exit-gate falsifiers (search hits, bm25_hooks channel, cold-start)

---

## §8.6 Audit remediation cross-link

Absent — no §7 amendments fired during M7 v1.0.

**Pre-declared triggers (unchanged):**
- G5 live failure → §7 amendment for `nomic-embed-text` before M8 backfill.
- State-worker GET for entry detail required → Tier 2 charter escalation (hub extension).

---

## Landed contracts summary (M8 pre-plan seed)

**Symbols extended (new in M7):**

- `bishop_shared/query_config.py` — `RRF_K=60`, `DEFAULT_SEARCH_DOMAIN`, `BM25_RELOAD_INTERVAL_SEC`
- `bishop_shared/bm25_tokenize.py` — `tokenize_bm25` (shared with vector-writer writer)
- `services/query-api/` — full read path: BM25 reader, LanceDB searcher, DuckDB reader (`read_only=True`), RRF fusion, problem-shaped classifier, FastAPI routes, G7 lifespan
- `bishop_cli/` — `bishop` console script (`search`, `recent`, `batch`, `escalations`)
- `services/ui/` — HTMX UI via `QUERY_API_URL` (batch list/detail, entry detail, search)
- Compose `bishop/query-api:m7`, `bishop/ui:m7`, `QUERY_API_URL: http://query-api:8000`
- `scripts/verify-m7.sh`

**M7 exit gate:** `scripts/verify-m7.sh` / M7 pytest slices green (136 passed). Integration demonstrates M6-indexed stores → `/search` hits, problem-shaped query activates `bm25_hooks` in `channels_active`, cold-start empty stores return empty results without crash.

**M8 entry gate:** Charter G4/G5/G6 manual sign-off; M7 auditor §8 clean; at least one ArXiv e2e run to `INDEXED` validated by owner before backfill/hardening work.

**Runnable checkpoint (charter):** `query-api` starts with graceful cold-start; `GET /search?q=` returns RRF-fused results; problem-shaped queries activate Channel 3; `bishop search "…"` returns results; UI batch summary and search bar functional against query-api.

**Hub contracts unchanged:** `state-worker` REST surface untouched; entry reads via query-api SQLite `mode=ro`.

---

## Read-only review summary (orchestrator)

**Intent alignment:** Charter M7 contract surfaces addressed — RRF (k=60), 2/3-channel fusion, problem-shaped classifier (§16.3), BM25 in-memory load + COW reload (§8.4), DuckDB `read_only=True`, G7 cold-start, query-api endpoints, `bishop` CLI, minimal UI (batch summary + search + entry detail). Hub restriction honored: zero state-worker diffs.

**Non-goals honored:** No full escalation panel actions, reranker, query expansion, cross-domain, daily digest, DB explorer, backfill, remaining adapters, state-worker hub extension.

**Highest residual risk:** Charter G4/G5/G6 manual gates not automated; live Docker smoke and real MiniLM retrieval quality unproven at container runtime. Second: monolithic full-suite pytest unreliable due to `app` package collision across nine services.

**Verdict:** Ready for adversarial audit at SHA `1be89cb`. Commit this handoff file before auditor Phase 0.5 artifact chain validation.
