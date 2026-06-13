# M3 — Pre-filter Slice · Auditor §8 Handoff

**Plan:** `m3-prefilter` v1.0  
**Status:** Complete — ready for adversarial audit  
**Charter slice:** `.dev/bishop_program_charter.md` L235–282  
**Normative spec:** `bishop_spec_0_6.md` v1.5.0 (tracked)

---

## §8.1 Completion snapshot

**Tree SHA:** `1d2a89d2d2d734880a88eb145092da74254cefca`

**Tracked-tree cleanliness at implementation SHA:** `git status` clean at `1d2a89d` (T1–T6 code committed).

**Handoff recording note:** This file and the plan §8 back-reference were authored after `1d2a89d`. Auditor should treat `1d2a89d` as the implementation anchor; read handoff/plan §8 from the commit that adds them, or from working tree if handoff lands in a follow-up commit.

**Executor commit chain** (`e07d285`…`1d2a89d`):

| Commit | Subtask | Summary |
|--------|---------|---------|
| `e07d285` | T1 | G3 gate — `bishop_shared/anthropic_config.py`, `verify-g3.sh`, mocked/live probe tests |
| `6a93194` | T2 | NL profile YAML + `profile_renderer.py`, seed scripts, renderer tests |
| `303bd22` | T3 | State-worker batch lifecycle API (`POST/PATCH /batches`, timeout), `m3_001` migration |
| `b098170` | T4 | `pre-filter-worker` — poll, hash verify, Anthropic submit, batch register |
| `e50786e` | T5 | `batch-poller` v1 — startup scan, Anthropic poll, results POST, timeout |
| `1d2a89d` | T6 | Compose `:m3` tags, `verify-m3.sh`, integration gate, stub removal tests |

**Primary automated verification (M3 gate — run at handoff recording):**

```
Command: python -m pytest tests/test_state_worker_contract.py tests/test_state_worker_health.py tests/test_constants.py tests/test_verify_g3.py tests/test_verify_m3.py tests/test_profile_renderer.py tests/test_prefilter_config.py tests/test_prefilter_client.py tests/test_prefilter_anthropic_client.py tests/test_prefilter_loop.py tests/test_batch_poller_config.py tests/test_batch_poller_startup.py tests/test_batch_poller_loop.py tests/test_state_worker_batches_register.py tests/test_m3_integration.py tests/test_anthropic_config.py -v --tb=short
Environment: win32, Python 3.14.2, pytest 9.0.2
Result: 90 passed, 37 warnings (alembic DeprecationWarning), exit code 0
```

**Equivalent verify-m3.sh slices (pytest parity):**

```
G2 slice:  33 passed (test_state_worker_contract + health + constants)
M3 slice:  57 passed (verify_m3 + profile + prefilter + poller + batches_register + integration)
G3 gate:   covered by test_verify_g3.py (SKIP live probe when ANTHROPIC_API_KEY absent)
```

**Equivalent bash gate:**

```
Command: scripts/verify-m3.sh
```

**Full regression slice (recommended auditor sanity check):**

```
Command: pytest tests/ -q
Environment: win32, Python 3.14.2, pytest 9.0.2
Result: 262 passed, 1 failed, exit code 1
Failure: tests/test_state_worker_routers_escalations.py::test_escalations_returns_flagged_entry_with_error_log
  — pre-existing M1 T8 side-effect (ALERT sibling row in error_log); not introduced by M3
```

**Live Docker gate:** Not executed at handoff recording. CHANGELOG defers live `docker compose up pre-filter-worker batch-poller state-worker` smoke to manual validation.

**Live G3 probe:** Not executed at handoff recording (`ANTHROPIC_API_KEY` absent). `verify-g3.sh` exits 0 with SKIP in CI; unit tests mock the probe.

---

## §8.2 Artifact chain

Read order for auditor. `git show 1d2a89d:<path>` at implementation SHA unless noted.

| Path | Resolves at `1d2a89d` | Notes |
|------|----------------------|-------|
| `.dev/plans/m3-prefilter/context-map.md` | Yes | Scout SHA `6d36e73` — **stale** vs implementation; treat interface inventory as prediction |
| `.dev/plans/m3-prefilter/plan.md` | Yes | v1.0 Complete |
| `.dev/plans/m3-prefilter/handoff.md` | **No** at `1d2a89d` — follow-up commit | This file |
| `.dev/plans/m3-prefilter/packets/T1.md` … `T6.md` | Yes | Executor packets |
| `.dev/decision-logs/m3-prefilter/T2-profile-renderer.md` | Yes | |
| `.dev/decision-logs/m3-prefilter/T3-batch-lifecycle-api.md` | Yes | |
| `.dev/plans/m2-discovery/handoff.md` | Yes | M3 entry gate |
| `bishop_spec_0_6.md` | Yes | Binding normative reference |
| `CHANGELOG.MD` | Yes | M3 T1–T6 entries |
| `bishop_shared/anthropic_config.py` | Yes | |
| `bishop_shared/profile_renderer.py` | Yes | |
| `config/profiles/professional_v1.0.0.yaml` | Yes | Committed `canonical_hash` |
| `scripts/verify-g3.sh`, `scripts/verify-g3.ps1` | Yes | |
| `scripts/verify-m3.sh` | Yes | |
| `scripts/seed-profiles.sh`, `scripts/seed-profiles.ps1` | Yes | |
| `alembic/versions/m3_001_batch_source_ids.py` | Yes | |
| `services/state-worker/app/routers/batches.py` | Yes | POST/PATCH/timeout extensions |
| `services/pre-filter-worker/app/` | Yes | Full pre-filter package |
| `services/batch-poller/app/` | Yes | Full batch-poller v1 package |
| `docker-compose.yml` | Yes | `bishop/pre-filter-worker:m3`, `bishop/batch-poller:m3` |
| `tests/test_profile_renderer.py`, `tests/test_prefilter_*.py` | Yes | |
| `tests/test_batch_poller_*.py`, `tests/test_state_worker_batches_register.py` | Yes | |
| `tests/test_verify_m3.py`, `tests/test_m3_integration.py` | Yes | |

---

## §8.3 §2 evidence

| §2 binding | Landed artifact | Proof test |
|------------|-----------------|------------|
| `ANTHROPIC_MODEL_PREFILTER` | `bishop_shared/anthropic_config.py:L8` | `test_prefilter_model_string_pinned` |
| `ANTHROPIC_API_KEY` / `get_anthropic_api_key()` | `anthropic_config.py` | `test_api_key_from_env` |
| `verify_model_string()` | `anthropic_config.py:L18+` | `test_verify_g3.py`, `test_verify_model_string_*` |
| G3 gate script | `scripts/verify-g3.sh` | `tests/test_verify_g3.py` |
| `compute_profile_hash()` | `bishop_shared/profile_renderer.py:L74+` | `test_hash_matches_canonical_in_yaml`, `test_hash_uses_json_canonical_dict_not_raw_yaml_bytes` |
| `render_profile_prompt()` | `profile_renderer.py:L90+` | `test_prompt_deterministic` |
| `load_profile()` | `profile_renderer.py` | `test_load_professional_profile` |
| `resolve_profile_path(domain)` | `profile_renderer.py:L51+` | `test_resolve_profile_path_professional` |
| `ProfileDocument` pydantic model | `profile_renderer.py` | `test_profile_document_round_trip` |
| Repo profile YAML | `config/profiles/professional_v1.0.0.yaml` | `test_load_professional_profile` |
| Seed scripts | `scripts/seed-profiles.sh`, `.ps1` | Manual; compose volume overlay documented in T2 decision log |
| `BatchRegisterRequest` / `BatchRegisterResponse` | `services/state-worker/app/models/http.py` | `test_post_batches_registers_submitted` |
| `BatchPatchRequest` | `http.py` | `test_patch_batches_updates_status_and_counts` |
| `BatchRecord.source_ids` + migration | `m3_001_batch_source_ids.py`, domain model | `test_batch_record_source_ids_round_trip` |
| `POST /batches` → 201 submitted | `routers/batches.py:L98+` | `test_post_batches_registers_submitted` |
| Duplicate `batch_id` → 409 | `transitions.py:register_batch` | `test_post_batches_duplicate_returns_409` |
| `PATCH /batches/{batch_id}` | `routers/batches.py:L114+` | `test_patch_batches_updates_status_and_counts` |
| `POST /batches/{batch_id}/timeout` | `routers/batches.py:L127+` | `test_post_batch_timeout_resets_relevance_queued` |
| `GET /batches?status=submitted,processing` | `routers/batches.py:L143+` | `test_startup_scan_*`, `test_get_batches_contract` |
| `PREFILTER_BATCH_SIZE` default 50 | `services/pre-filter-worker/app/config.py:L17` | `test_prefilter_batch_size_default` |
| `PREFILTER_POLL_INTERVAL_SEC` default 60 | `config.py:L18` | `test_prefilter_poll_interval_default` |
| Pre-filter `StateWorkerClient` | `state_worker_client.py` | `tests/test_prefilter_client.py` |
| `AnthropicBatchClient` custom_id=source_id | `anthropic_batch_client.py:L45` | `test_build_requests_custom_id_equals_source_id` |
| `prefilter_cycle()` hash mismatch abort | `loop.py:L82+` | `test_prefilter_cycle_hash_mismatch_aborts_without_anthropic` |
| G3 gate before submit | `loop.py` + `config.py:G3_DEV_BYPASS` | `test_ensure_g3_verified_blocks_without_bypass_or_key` |
| Anthropic 400 → no batch register | `loop.py` + client | `test_prefilter_cycle_anthropic_400_skips_batch_registration` |
| 20-entry batch assembly | `loop.py` | `test_prefilter_cycle_twenty_entry_batch_assembly` |
| `BATCH_POLL_INTERVAL_SEC` default 120 | `services/batch-poller/app/config.py:L17` | `test_batch_poll_interval_default` |
| `BATCH_TIMEOUT_HOURS` default 48 | `config.py:L18` | `test_batch_timeout_hours_default` |
| `startup_scan()` pre_filter only | `startup.py:L27+` | `test_startup_scan_filters_pre_filter_only` |
| Restart recovery | `startup.py` + integration | `test_startup_scan_restart_recovery_registers_in_flight_batch`, `test_m3_startup_scan_registers_pre_seeded_in_flight_batch` |
| Malformed JSON → reject decision | `loop.py:parse_pre_filter_response` | `test_parse_pre_filter_response_malformed_json_counts_as_reject` |
| Results POST + PATCH complete | `loop.py` | `test_poll_once_posts_results_and_patches_complete` |
| Timeout calls POST /timeout | `loop.py` | `test_poll_once_timeout_calls_post_timeout_endpoint` |
| Results non-2xx skips PATCH | `loop.py` | `test_poll_once_pre_filter_results_non_2xx_skips_patch_complete` |
| Anthropic failed → PATCH failed | `loop.py` | `test_poll_once_anthropic_failed_patches_batch_failed` |
| `poll_loop` invokes startup_scan first | `loop.py:L297` | `test_poll_loop_invokes_startup_scan_before_first_cycle` |
| Enrichment batch_type rejected | `loop.py:L43`, `startup.py:L13` | `test_startup_scan_filters_pre_filter_only` |
| Image tags `:m3` | `docker-compose.yml:L38,L85` | `test_compose.py` milestone tag matrix |
| M3 gate script | `scripts/verify-m3.sh` | `tests/test_verify_m3.py` |
| Stub removal | real `app/main.py` in both workers | `test_m3_worker_uses_real_main_entrypoint` |
| E2e pass+reject same batch | integration harness | `test_m3_e2e_twenty_entry_batch_pass_and_reject` |
| Decision logs T2/T3 | `.dev/decision-logs/m3-prefilter/` | Present at HEAD |

---

## §8.4 §5 disposition

### §5.2 load-bearing assumptions

| Tuple | Disposition | Evidence |
|-------|-------------|----------|
| M1 `apply_pre_filter_results` accepts RELEVANCE_QUEUED entries | **closed** | `test_post_manifest_pre_filter_results_contract`, `test_m3_e2e_twenty_entry_batch_pass_and_reject` |
| Anthropic `custom_id` = `source_id` | **closed** | `test_build_requests_custom_id_equals_source_id`, e2e integration maps results |
| G3 model string `claude-haiku-4-5-20251001` valid | **treat-as-prediction** | Pinned constant + mocked probe; live API not gated without `ANTHROPIC_API_KEY` |
| `batches.source_ids` migration before workers | **closed** | `m3_001` in contract tests + `test_post_batch_timeout_resets_relevance_queued` |
| Profile hash uses JSON canonical dict not prompt text | **closed** | `test_hash_uses_json_canonical_dict_not_raw_yaml_bytes`, `test_prefilter_cycle_hash_mismatch_aborts_without_anthropic` |

### §5.4 hidden couplings

| Tuple | Disposition | Evidence |
|-------|-------------|----------|
| C1 compose profiles volume shadows image COPY | **closed** | `seed-profiles` scripts + T2 decision log; `docker-compose.yml` profiles mount documented |
| C2 batch_id UUID consistency across register/results | **closed** | `test_prefilter_cycle_happy_path_registers_batch`, `test_m3_e2e_twenty_entry_batch_pass_and_reject` |
| C3 compose image tag matrix m0→m3 for two services | **closed** | `tests/test_compose.py` tag matrix includes pre-filter-worker:m3, batch-poller:m3 |
| C4 batch-poller sqlite volume tempts direct DB read | **closed** | No `sqlite`/`aiosqlite` imports in `services/batch-poller/`; HTTP-only clients |
| C5 lock-state sweep RELEVANCE_QUEUED→DISCOVERED race | **treat-as-prediction** | Spec G4 caveat accepted; sweep test exists in M1 contract suite; no M3-specific race test |

### Context-map flags (§0 orch resolutions)

| Flag | Resolution | Disposition |
|------|------------|-------------|
| 1 Batch registration API | T3 POST/PATCH /batches | **closed** |
| 2 Pre-filter timeout state | T3 timeout → DISCOVERED | **closed** |
| 3 source_ids on restart | T3 migration + wire | **closed** |
| 4 Profile volume overlay | T2 seed scripts + repo path | **closed** |
| 6 Hash algorithm | T2 JSON canonical SHA-256 | **closed** |
| 7 Active profile pointer | T2 hardcoded professional path | **closed** |

### Auditor hygiene (non-blocking unless policy requires)

- Context map scout SHA (`6d36e73`) stale vs implementation (`1d2a89d`) — pre-plan for M4 should re-explore.
- `.dev/architecture/bishop/` not post-M3 refreshed (charter §7 housekeeping deferred).
- Live docker compose e2e not automated in `verify-m3.sh` (deferred per CHANGELOG T6).
- Live G3 Anthropic probe not run at handoff (`ANTHROPIC_API_KEY` absent).
- Full-suite `test_escalations_returns_flagged_entry_with_error_log` failure inherited from M1 T8 — **open** for program hygiene, **not M3 blocking**.
- `BISHOP_G3_VERIFIED=1` dev bypass documented in T4 CHANGELOG — production must not rely on bypass.

---

## §8.5 Cold-read seeds

Narrative-blind Phase 0 — contract-vs-code drift surfaces:

1. `services/state-worker/app/transitions.py` — `register_batch`, `apply_batch_timeout`, `apply_pre_filter_results` ordering and entry state guards
2. `services/state-worker/app/routers/batches.py` — wire shapes vs `http.py` models; 409/404 envelopes
3. `services/pre-filter-worker/app/loop.py` — G3 gate, hash verify abort, Anthropic submit → register ordering
4. `services/batch-poller/app/loop.py` — timeout vs results race, malformed JSON handling, enrichment type guard
5. `bishop_shared/profile_renderer.py` — hash algorithm vs YAML `canonical_hash`; prompt not hashed
6. `tests/test_m3_integration.py` — M3 exit-gate falsifiers (20-entry pass/reject, startup scan restart)

---

## §8.6 Audit remediation cross-link

Absent — no §7 amendments fired during M3 v1.0.

---

## Landed contracts summary (M4 pre-plan seed)

**Symbols extended (new in M3):**

- `ANTHROPIC_MODEL_PREFILTER`, `verify_model_string()` — `bishop_shared/anthropic_config.py`
- `compute_profile_hash()`, `render_profile_prompt()`, `load_profile()`, `resolve_profile_path()` — `bishop_shared/profile_renderer.py`
- `ProfileDocument` — profile renderer module
- `config/profiles/professional_v1.0.0.yaml` — committed NL profile v1.0.0
- State-worker batch lifecycle: `POST /batches`, `PATCH /batches/{batch_id}`, `POST /batches/{batch_id}/timeout`
- `BatchRegisterRequest`, `BatchPatchRequest`, `BatchRecord.source_ids` — state-worker models + `m3_001` migration
- `prefilter_cycle()`, pre-filter `StateWorkerClient`, `AnthropicBatchClient`
- `startup_scan()`, `poll_loop()`, batch-poller `StateWorkerClient`
- Compose `bishop/pre-filter-worker:m3`, `bishop/batch-poller:m3`
- `scripts/verify-g3.sh`, `scripts/verify-m3.sh`, `scripts/seed-profiles.*`

**M3 exit gate:** `scripts/verify-m3.sh` / M3 pytest slice green (90 tests in handoff recording run).

**M4 entry gate:** M3 checkpoint — `DISCOVERED` entries flow through pre-filter to `RELEVANCE_PASSED`/`RELEVANCE_REJECTED` via mocked Anthropic batch path; G3 blocks live LLM without key.

**Runnable checkpoint (charter):** `docker compose up pre-filter-worker batch-poller state-worker` → pre-filter polls DISCOVERED, submits Anthropic batch, registers `BatchRecord`; poller scans in-flight batches on restart, posts results, enforces 48h timeout; profile hash mismatch aborts before Anthropic call (unit-tested; live Anthropic optional manual).
