# M5 — Enrichment Slice · Auditor §8 Handoff

**Plan:** `m5-enrichment` v1.0  
**Status:** Complete — ready for adversarial audit  
**Charter slice:** `.dev/bishop_program_charter.md` L332–382  
**Normative spec:** `bishop_spec_0_6.md` v1.5.0 (tracked)

---

## §8.1 Completion snapshot

**Tree SHA:** `0331dd5e34855657207ad2035158492d03a019ca`

**Tracked-tree cleanliness at implementation SHA:** `git status` clean at `0331dd5` (T1–T6 code committed).

**Handoff recording note:** This file is authored after `0331dd5`. Auditor should treat `0331dd5` as the implementation anchor; read handoff from the commit that adds it, or from working tree if handoff lands in a follow-up commit.

**Executor commit chain** (`f1782e9`…`0331dd5`):

| Commit | Subtask | Summary |
|--------|---------|---------|
| `f1782e9` | T1 | `bishop_shared` enrichment utilities — truncation, taxonomy, prompts, parsers, `ANTHROPIC_MODEL_ENRICHMENT` |
| `54f7610` | T2 | State-worker hub — `register_batch` submit hooks, enrichment timeout dispatch, OOV wire + persistence |
| `073ff4e` | T3 | `enrichment-batcher` service + Task A (poll `SCRAPED`, Call 1 submit, POST `enrichment_stage1`) |
| `47c7d91` | T4 | Task B (poll `ENRICHMENT_STAGE2_QUEUED`, profile hash verify, Call 2 + `cache_control`, dual-task main) |
| `31027b3` | T5 | `batch-poller` v2 — all batch types, enrichment parsers, result POST, startup scan |
| `0331dd5` | T6 | `verify-m5.sh`, compose `:m5` tags, M5 integration e2e + gate tests |

**Primary automated verification (M5 gate — run at handoff recording):**

```
Command: python -m pytest tests/test_state_worker_contract.py tests/test_state_worker_health.py tests/test_constants.py tests/test_enrichment_truncation.py tests/test_tag_taxonomy.py tests/test_enrichment_prompts.py tests/test_enrichment_parsers.py tests/test_state_worker_enrichment_hub.py tests/test_enrichment_batcher_config.py tests/test_enrichment_batcher_stage1_loop.py tests/test_enrichment_batcher_stage2_loop.py tests/test_batch_poller_startup.py tests/test_batch_poller_enrichment.py tests/test_batch_poller_loop.py tests/test_m5_integration.py tests/test_verify_m5.py -v --tb=short
Environment: win32, Python 3.14.2, pytest 9.0.2
Result: 105 passed, 39 warnings (alembic DeprecationWarning), exit code 0
```

**Equivalent verify-m5.sh slices (pytest parity):**

```
G2 slice:  33 passed (test_state_worker_contract + health + constants)
M5 slice:  75 passed (verify_m5 + anthropic_config + enrichment_* + batch_poller_* + m5_integration)
Combined unique modules in gate: 108 test executions across both slices (33 + 75)
```

**Equivalent bash gate:**

```
Command: scripts/verify-m5.sh
```

**Full regression slice (recommended auditor sanity check):**

```
Command: pytest tests/ -q
Environment: win32, Python 3.14.2, pytest 9.0.2
Result: 368 passed, 1 failed, exit code 1
Failure: tests/test_state_worker_routers_escalations.py::test_escalations_returns_flagged_entry_with_error_log
  — pre-existing M1 T8 side-effect (ALERT sibling row in error_log); not introduced by M5
```

**Live Docker gate:** Not executed at handoff recording. CHANGELOG defers live `docker compose up enrichment-batcher batch-poller state-worker` smoke to manual validation (M3/M4 pattern).

---

## §8.2 Artifact chain

Read order for auditor. `git show 0331dd5:<path>` at implementation SHA unless noted.

| Path | Resolves at `0331dd5` | Notes |
|------|----------------------|-------|
| `.dev/plans/m5-enrichment/context-map.md` | Yes | Scout SHA `406ff61` — **stale** vs implementation; treat interface inventory as prediction |
| `.dev/plans/m5-enrichment/plan.md` | Yes | v1.0 |
| `.dev/plans/m5-enrichment/handoff.md` | **No** at `0331dd5` — follow-up commit | This file |
| `.dev/plans/m5-enrichment/packets/T1.md` … `T6.md` | Yes | Executor packets |
| `.dev/decision-logs/m5-enrichment/T1-enrichment-shared-utilities.md` | Yes | |
| `.dev/decision-logs/m5-enrichment/T2-state-worker-enrichment-hub.md` | Yes | |
| `.dev/decision-logs/m5-enrichment/T4-call2-cache-control.md` | Yes | |
| `.dev/plans/m4-content/handoff.md` | Yes | M5 entry gate |
| `.dev/architecture/bishop/` | Yes @ pre-M5 | Post-M5 architecture refresh per charter §7 **not yet run** |
| `bishop_spec_0_6.md` | Yes | Binding normative reference |
| `CHANGELOG.MD` | Yes | M5 T1–T6 entries |
| `bishop_shared/enrichment_config.py` | Yes | T1 |
| `bishop_shared/tag_taxonomy.py` | Yes | T1 |
| `bishop_shared/content_truncation.py` | Yes | T1 |
| `bishop_shared/enrichment_prompts.py` | Yes | T1 |
| `bishop_shared/enrichment_parsers.py` | Yes | T1 |
| `bishop_shared/anthropic_config.py` | Yes | T1 alias |
| `services/state-worker/app/transitions.py` | Yes | T2 hub |
| `services/enrichment-batcher/app/` | Yes | T3/T4 |
| `services/enrichment-batcher/Dockerfile` | Yes | CMD `python -m app.main` |
| `services/batch-poller/app/loop.py` | Yes | T5 v2 dispatch |
| `services/batch-poller/app/startup.py` | Yes | T5 all batch types |
| `docker-compose.yml` | Yes | `bishop/enrichment-batcher:m5`, `bishop/batch-poller:m5` |
| `scripts/verify-m5.sh` | Yes | |
| `tests/test_m5_integration.py` | Yes | |
| `tests/test_verify_m5.py` | Yes | |

---

## §8.3 §2 evidence

| §2 binding | Landed artifact | Proof test |
|------------|-----------------|------------|
| `ANTHROPIC_MODEL_ENRICHMENT` | `bishop_shared/anthropic_config.py:L9` | `test_enrichment_model_alias_matches_prefilter` |
| `ENRICHMENT_TRUNCATION_MAX_TOKENS` | `bishop_shared/enrichment_config.py:L5` | `test_max_tokens_constant` |
| `TAG_TAXONOMY` / `validate_tags` | `bishop_shared/tag_taxonomy.py` | `test_taxonomy_matches_spec_literals`, `test_validate_tags_strips_oov` |
| `truncate_content_for_call1` | `bishop_shared/content_truncation.py:L105+` | `test_paper_strategy_abstract_plus_body_clamped`, `test_clamp_fixture_exactly_4000_tokens` |
| `build_call1_system_prompt` | `bishop_shared/enrichment_prompts.py:L24+` | `test_call1_includes_taxonomy` |
| `build_call2_system_prompt` + `cache_control` | `bishop_shared/enrichment_prompts.py:L52-L75` | `test_call2_system_has_cache_control` |
| `parse_call1_response` / `parse_call2_response` | `bishop_shared/enrichment_parsers.py` | `tests/test_enrichment_parsers.py` |
| `EnrichmentStage1EntryWire.oov_tags_stripped` | `services/state-worker/app/models/http.py:L54` | `test_enrichment_stage1_wire_accepts_oov_tags_stripped` |
| `register_batch` enrichment submit hook | `services/state-worker/app/transitions.py:L387-L397` | `test_register_batch_stage1_moves_entries_to_submitted`, `test_register_batch_stage2_moves_entries_to_submitted` |
| `apply_batch_timeout` enrichment paths | `services/state-worker/app/transitions.py:L506-L533` | `test_batch_timeout_stage1_submitted_to_failed`, `test_batch_timeout_stage2_submitted_to_failed` |
| `_insert_oov_tags_log` | `services/state-worker/app/transitions.py:L961+`, invoked `L1070+` | `test_stage1_results_persist_oov_tags_log` |
| `ENRICHMENT_STAGE1_BATCH_TYPE` / `TRACKED_BATCH_TYPES` | `services/batch-poller/app/models.py:L11-L17` | `test_enrichment_batch_type_constants`, `test_startup_scan_tracks_all_batch_types` |
| `ENRICHMENT_STAGE1_BATCH_SIZE` default 10 | `services/enrichment-batcher/app/config.py:L17` | `test_enrichment_stage1_batch_size_default` |
| `ENRICHMENT_STAGE2_BATCH_SIZE` default 10 | `services/enrichment-batcher/app/config.py:L18` | `test_enrichment_stage2_batch_size_default` |
| `ENRICHMENT_POLL_INTERVAL_SEC` default 120 | `services/enrichment-batcher/app/config.py:L19` | `test_enrichment_poll_interval_default` |
| `stage1_cycle()` | `services/enrichment-batcher/app/stage1_loop.py` | `test_stage1_cycle_happy_path_registers_enrichment_stage1_batch` |
| `stage2_cycle()` | `services/enrichment-batcher/app/stage2_loop.py` | `test_stage2_cycle_happy_path_registers_enrichment_stage2_batch`, `test_stage2_cycle_hash_mismatch_aborts_without_anthropic` |
| Dual-task scheduler | `services/enrichment-batcher/app/main.py:L16-L27` | stage1+stage2 loop tests; integration e2e |
| `startup_scan()` v2 | `services/batch-poller/app/startup.py` | `test_startup_scan_registers_enrichment_stage1_in_flight` |
| `poll_once()` enrichment dispatch | `services/batch-poller/app/loop.py:L458-L461` | `test_poll_once_enrichment_stage1_posts_results_and_patches_complete`, stage2 variant |
| OOV in batch-poller wire | `services/batch-poller/app/loop.py` (stage1 handler) | `test_poll_once_stage1_includes_oov_tags_stripped_in_wire` |
| Compose `bishop/enrichment-batcher:m5` | `docker-compose.yml:L69` | `tests/test_compose.py` tag matrix |
| Compose `bishop/batch-poller:m5` | `docker-compose.yml:L85` | same |
| M5 gate script | `scripts/verify-m5.sh` | `tests/test_verify_m5.py` |
| E2e 5-entry VECTOR_WRITE_QUEUED | `tests/test_m5_integration.py` | `test_m5_e2e_five_entries_reach_vector_write_queued_with_enrichment_fields` |
| E2e ENRICHMENT_STAGE2 double-poll | same | `test_m5_double_poll_stage2_queued_empty_while_claimed_held` |
| E2e enrichment startup scan | same | `test_m5_startup_scan_registers_enrichment_stage1_in_flight` |
| Decision logs T1/T2/T4 | `.dev/decision-logs/m5-enrichment/` | Present at HEAD |

---

## §8.4 §5 disposition

### §5.2 load-bearing assumptions

| Tuple | Disposition | Evidence |
|-------|-------------|----------|
| M1 enrichment result POST + H3 transitions correct for M5 | **closed** | `test_m5_e2e_five_entries_reach_vector_write_queued_with_enrichment_fields`; existing M1 contract tests unchanged |
| `register_batch` extension sufficient for submit transitions | **closed** | `test_register_batch_stage1_moves_entries_to_submitted`; integration e2e reaches `_SUBMITTED` → results → terminal states |
| tiktoken cl100k_base acceptable for 4000-token ceiling | **treat-as-prediction** | Unit clamp tests pass; live `challenge_hooks` quality not gated in CI (charter G6 deferred to M8) |
| M4 `content_raw` sufficient for paper truncation | **treat-as-prediction** | E2e uses synthetic `content_raw`; live ArXiv HTML truncation path not exercised in CI |
| G3 model string valid at execution time | **treat-as-prediction** | CI mocks Anthropic; `ensure_g3_verified` + `BISHOP_G3_VERIFIED` bypass pattern from M3 |

### §5.4 hidden couplings

| Tuple | Disposition | Evidence |
|-------|-------------|----------|
| C1 POST /batches atomic register + mark submitted | **closed** | `transitions.py:L387-L397`; hub + integration tests |
| C2 `apply_batch_timeout` batch_type dispatch | **closed** | `test_batch_timeout_stage1_submitted_to_failed`; `test_poll_once_enrichment_stage1_timeout_calls_post_timeout_endpoint` |
| C3 Anthropic `custom_id` = `source_id` join | **closed** | Stage loop tests assert registration; integration e2e result join |
| C4 `profile_render_hash` on stage2 registration | **closed** | `test_stage2_cycle_hash_mismatch_aborts_without_anthropic` |
| C5 T3/T4 file collision on enrichment-batcher | **closed** | Sequential commits `073ff4e` → `47c7d91`; single coherent `app/main.py` dual-task |
| C6 Compose tag m3 → m5 | **closed** | `tests/test_compose.py` |
| C7 pre_filter loop regression | **closed** | All 7 `test_batch_poller_loop.py` tests pass at handoff recording |

### Context-map flags (§0 orch resolutions)

| Flag | Resolution | Disposition |
|------|------------|-------------|
| 1 Submit transition wiring | T2 `register_batch` hook | **closed** |
| 2 OOV persistence | T1 parser + T2 wire/persist | **closed** |
| 3 Truncation without entry_type | T1 source-based strategies | **closed** (HF model-card branch unit-tested; M5 e2e arxiv-only) |
| 4 No enrichment-batcher tests | T3/T4/T6 tests | **closed** |
| 5 batch-poller v2 filter | T5 `TRACKED_BATCH_TYPES` | **closed** |
| 6 T3/T4 sequencing | T3 → T4 DAG honored | **closed** |

### Auditor hygiene (non-blocking unless policy requires)

- Context map scout SHA (`406ff61`) stale vs implementation (`0331dd5`) — expected; M6 pre-plan should re-explore.
- Full-suite `test_escalations_returns_flagged_entry_with_error_log` failure inherited from M1 T8 — **open** for program hygiene, **not M5 blocking**.
- Live docker compose e2e not automated in `verify-m5.sh` (deferred per CHANGELOG T6).
- Orphaned Anthropic batch on POST /batches failure after submit — documented M3 CR-1 pattern; no compensating cancel in M5.
- `invalid_transition` on enrichment `POST /batches` may surface as unhandled 500 — deferred per T2 decision log; hub tests cover transition errors directly.
- Malformed Call 2 partial-failure in full e2e — deferred per CHANGELOG T6; unit falsifiers in `test_batch_poller_enrichment.py`.
- Post-M5 `.dev/architecture/` refresh not committed — charter §7 housekeeping pending.
- `services/enrichment-batcher/stub_main.py` remains in tree but Dockerfile CMD uses `app.main` — stub unused at runtime (same pattern as other services post-M0).

---

## §8.5 Cold-read seeds

Narrative-blind Phase 0 — contract-vs-code drift surfaces:

1. `services/state-worker/app/transitions.py` — `register_batch` enrichment BEGIN/COMMIT, `apply_batch_timeout` batch_type dispatch, `_insert_oov_tags_log`
2. `bishop_shared/content_truncation.py` — paper vs default truncation strategies and 4000-token clamp
3. `services/enrichment-batcher/app/stage1_loop.py` — poll `SCRAPED`, truncation, Anthropic submit, batch registration ordering
4. `services/enrichment-batcher/app/stage2_loop.py` — profile hash gate, Call 2 user message (title+summary only), batch registration
5. `services/batch-poller/app/loop.py` — batch_type dispatch, enrichment result POST, OOV wire field population
6. `tests/test_m5_integration.py` — charter exit-gate falsifiers (5-entry e2e, double-poll, OOV log, startup scan)

---

## §8.6 Audit remediation cross-link

Absent — no §7 amendments fired during M5 v1.0.

---

## Landed contracts summary (M6 pre-plan seed)

**Symbols extended (new in M5):**

- `bishop_shared` enrichment modules: `enrichment_config`, `tag_taxonomy`, `content_truncation`, `enrichment_prompts`, `enrichment_parsers`
- `ANTHROPIC_MODEL_ENRICHMENT` — alias pinned to G3 model string
- State-worker hub: `register_batch` enrichment submit in transaction; `apply_batch_timeout` enrichment `_FAILED` paths; `EnrichmentStage1EntryWire.oov_tags_stripped`; `_insert_oov_tags_log`
- `enrichment-batcher` service: `stage1_cycle`, `stage2_cycle`, dual-task `run_scheduler`, G3 gate, profile hash verify (Call 2)
- Config: `ENRICHMENT_STAGE1_BATCH_SIZE`, `ENRICHMENT_STAGE2_BATCH_SIZE`, `ENRICHMENT_POLL_INTERVAL_SEC`
- `batch-poller` v2: `TRACKED_BATCH_TYPES`, enrichment handlers, `post_enrichment_stage1_results`, `post_enrichment_stage2_results`
- Compose `bishop/enrichment-batcher:m5`, `bishop/batch-poller:m5`
- `scripts/verify-m5.sh`

**M5 exit gate:** `scripts/verify-m5.sh` / M5 pytest slice green (105 tests in single combined run; 108 across G2+M5 gate slices). Integration demonstrates 5 entries at `VECTOR_WRITE_QUEUED` with enrichment fields populated, OOV row in `oov_tags_log`, `ENRICHMENT_STAGE2_QUEUED` double-poll empty while peer holds `ENRICHMENT_STAGE2_CLAIMED`, and enrichment startup scan recovery.

**M6 entry gate:** M5 checkpoint — entries at `VECTOR_WRITE_QUEUED` with all enrichment fields populated; G3 model string verified (from M3). Runnable path: `enrichment-batcher` + `batch-poller` + `state-worker` with mocked or live Anthropic per environment.

**Runnable checkpoint (charter):** `enrichment-batcher` Task A polls `SCRAPED`, submits Call 1; `batch-poller` posts stage1 results → `ENRICHMENT_STAGE2_QUEUED`; Task B submits Call 2; poller posts stage2 results → `VECTOR_WRITE_QUEUED` with OOV logs and both enrichment `BatchRecord` types.

---

## Read-only review summary (orchestrator)

**Intent alignment:** All six charter contract surfaces addressed — dual asyncio enrichment tasks, Call 1/2 prompts with truncation and taxonomy, OOV parser + persistence, batch-poller v2 with startup scan for enrichment types, state transitions through `VECTOR_WRITE_QUEUED`. Hub restriction honored: state-worker remains sole SQLite writer; no new REST routes beyond wire extension on existing enrichment result POST.

**Non-goals:** No vector-writer, LanceDB, DuckDB, BM25, query-api, or ui changes. Personal domain enrichment deferred.

**Highest residual risk:** Truncation + prompt quality on live ArXiv HTML `content_raw` at scale (plan §5.2 treat-as-prediction) — acceptable for M5 gate; charter G6 quality sampling owns downstream validation before backfill.

**Verdict:** Ready for adversarial audit at SHA `0331dd5`.
