# Audit Report — m5-enrichment

**Audit document revision:** 1 (initial)  
**Date:** 2026-06-13  
**Plan version:** 1.0  
**Audit HEAD:** `0331dd5e34855657207ad2035158492d03a019ca` (implementation anchor)  
**Auditor focus areas:**
1. **Integration seams** (mandatory) — seeded from context-map §Coupling surfaces and plan §5.4 (C1–C7): `register_batch` atomic submit hook; batch-poller `custom_id` join; profile hash gate on Call 2; startup scan + `TRACKED_BATCH_TYPES`; pre_filter regression in extended `poll_once`; enrichment-batcher dual-task scheduler vs state-worker poll/claim states.
2. **Failure paths** — orphaned Anthropic batch on POST `/batches` failure after submit (M3 CR-1 pattern); enrichment results POST non-2xx skip batch complete; 48h timeout → `_FAILED`; G3 / model-string fatal; profile hash mismatch abort.
3. **Edge cases** — OOV persistence when `entry_type` absent; truncation empty-body on malformed `content_raw`; unknown `batch_type` rejection logging; markdown-fenced JSON in model responses.

---

## 1. Audit metadata

| Field | Value |
|-------|-------|
| Task | M5 — Enrichment Slice (`enrichment-batcher`, `batch-poller` v2, `bishop_shared` enrichment utilities, state-worker hub) |
| Charter slice | `.dev/bishop_program_charter.md` L332–382 |
| Context map | `.dev/plans/m5-enrichment/context-map.md` — readiness **CONDITIONAL** at scout time |
| Scout SHA | `406ff61be94ede050257d582fdd8f7f521dab1c2` |
| Implementation SHA | `0331dd5e34855657207ad2035158492d03a019ca` |
| Provenance | **Diverged** — six implementation commits (`f1782e9`…`0331dd5`) post-scout |
| Scout working tree | **clean** |
| Audit working tree | **dirty** — `?? .dev/plans/m5-enrichment/handoff.md` |
| Phase 0 discipline | Task statement + §2 contracts and code/tests read before handoff, decision logs, and changelog narrative |
| Re-audit | No — initial audit |

---

## 2. Provenance log

### SHA comparison

| Check | Result |
|-------|--------|
| Scout SHA vs implementation HEAD | **Diverged** (`406ff61` → `0331dd5`) |
| Expected | Yes — entire M5 surface landed post-scout |

**`context-map-stale` (major, F-001):** All `direct` rows in context-map §File map diverged from scout SHA. Scout listed M0 `stub_main.py` enrichment-batcher, pre_filter-only batch-poller, unimplemented submit hooks, and zero enrichment tests; implementation now ships full service packages, hub transitions, and M5 test suite. Findings against scout `suspect_modified` predictions and ambiguity flags are **stale-qualified** — outcomes verified against `0331dd5`, not scout-time absence.

**Diverged files (representative `direct` scope):** `services/enrichment-batcher/app/`, `services/batch-poller/app/loop.py`, `services/batch-poller/app/startup.py`, `services/batch-poller/app/models.py`, `services/state-worker/app/transitions.py`, `services/state-worker/app/models/http.py`, `bishop_shared/enrichment_*.py`, `bishop_shared/content_truncation.py`, `bishop_shared/tag_taxonomy.py`, `docker-compose.yml`, `scripts/verify-m5.sh`, all `tests/test_enrichment_*.py`, `tests/test_m5_integration.py`, `tests/test_batch_poller_enrichment.py`, `tests/test_state_worker_enrichment_hub.py`.

### Working-tree state

| Check | Result |
|-------|--------|
| Scout-time dirty paths | None (clean) |
| Audit-time dirty paths | `?? .dev/plans/m5-enrichment/handoff.md` (untracked) |

### Scout grep coverage

Context-map §Coupling surfaces recorded patterns for: `batch_type` / `enrichment_stage`, `PRE_FILTER_BATCH_TYPE`, `ANTHROPIC_MODEL_PREFILTER`, `canonical_hash` / `profile_render_hash`, `POST /entries/enrichment`, `mark_enrichment_stage`, `oov_tags`, `cache_control`, `tiktoken`, `custom_id`, `BISHOP_G3_VERIFIED`. Plan §5.4 hidden couplings use the same vocabulary. **No `scout-incomplete` gaps** identified.

### Plan-artifact provenance (`git show 0331dd5:<path>`)

| Artifact | At `0331dd5` | On disk @ audit | Notes |
|----------|--------------|-----------------|-------|
| `.dev/plans/m5-enrichment/context-map.md` | present | present | Scout SHA stale |
| `.dev/plans/m5-enrichment/plan.md` | present | present | §8 still "Pending execution" placeholder |
| `.dev/plans/m5-enrichment/handoff.md` | **absent** | present (untracked) | Canonical §8.1–§8.6 for auditor |
| `.dev/plans/m5-enrichment/packets/T1.md` … `T6.md` | present | present | |
| `.dev/decision-logs/m5-enrichment/T1-enrichment-shared-utilities.md` | present | present | |
| `.dev/decision-logs/m5-enrichment/T2-state-worker-enrichment-hub.md` | present | present | |
| `.dev/decision-logs/m5-enrichment/T4-call2-cache-control.md` | present | present | |
| `.dev/plans/m4-content/handoff.md` | present | present | M5 entry gate |
| `.dev/bishop_program_charter.md` | present | present | |
| `bishop_spec_0_6.md` | present | present | |
| `CHANGELOG.MD` | present | present | M5 T1–T6 section |
| `scripts/verify-m5.sh` | present | present | |
| Implementation paths (handoff §8.2 table) | present | present | Verified via diff `406ff61..0331dd5` |

**Findings filed in Phase 0.5:** F-001, F-002, F-003

---

## 3. Context chain completeness

| Artifact | Provided | Limits |
|----------|----------|--------|
| Context map | Yes | Stale vs implementation SHA |
| Task statement / §2 contracts | Yes | Phase 0 inputs |
| Orchestrator plan (full) | Yes | §8 placeholder uncommitted at `0331dd5` |
| Handoff §8 | Yes (working tree) | Not in HEAD |
| Packets T1–T6 | Yes | In HEAD |
| Decision logs T1, T2, T4 | Yes | T3/T5/T6 standard tier — no logs required |
| Changelog M5 section | Yes | |
| Charter / rationale | Yes | Charter M5 slice binding |
| M4 handoff | Yes | Entry gate reference |
| Codebase diff `406ff61..0331dd5` | Yes | 51 files, +5671 lines |
| Test suite | Executed at audit time | See Phase 2 |

---

## 4. Cold-read log

Pinned findings from narrative-blind Phase 0 (task statement + §2 + code/tests only):

| ID | Severity guess | Surface | Finding |
|----|----------------|---------|---------|
| CR-01 | positive | `transitions.py:register_batch` | BatchRecord insert + `mark_enrichment_stage*_submitted` share one `BEGIN`/`COMMIT` transaction — atomic submit hook |
| CR-02 | medium | `stage1_loop.py` / `stage2_loop.py` | Anthropic submit succeeds then POST `/batches` failure returns without compensating cancel — orphaned external batch risk |
| CR-03 | medium | `transitions.py:_h3_enrichment_stage1_success` L1070 | OOV insert gated on `item.entry_type is not None`; stripped tags dropped if type absent |
| CR-04 | low | `stage1_loop.py` L109–114 | Non-`PROFESSIONAL` domain aborts cycle — charter personal-domain deferral enforced in code |
| CR-05 | low | `batch-poller/app/loop.py` `_merge_tracked` / `_handle_batch_complete` else | `enrichment_batch_rejected` still logged for unknown `batch_type` strings |
| CR-06 | process | `.dev/plans/m5-enrichment/handoff.md` | On disk but absent from `0331dd5` — audit archaeology gap |
| CR-07 | process | `plan.md` §8 | Still reads "Pending execution" at implementation SHA |
| CR-08 | low | `enrichment_parsers.py` | Regex JSON extraction may miss markdown-fenced nested objects |
| CR-09 | observation | `stage1_loop.py:ensure_g3_verified` | Calls `verify_model_string()` probing `ANTHROPIC_MODEL_PREFILTER`; enrichment submits use `ANTHROPIC_MODEL_ENRICHMENT` (same literal today) |
| CR-10 | low | enrichment-batcher loops | Log `extra.event` values (`state_worker_error`, `empty_poll`, `unsupported_domain`, `missing_summary`) outside §2 declared event set |

---

## 5. Findings table

| ID | Severity | Type | Phase | Subtask | Description |
|----|----------|------|-------|---------|-------------|
| F-001 | major | context-map-stale | 0.5 | — | Scout SHA `406ff61` diverged from implementation `0331dd5` on all direct-scope files |
| F-002 | major | artifact-not-in-HEAD | 0.5 | T6 | `handoff.md` on disk but not in `0331dd5`; breaks post-merge §8 archaeology |
| F-003 | minor | process-violation | 1 | T6 | `plan.md` §8 still "Pending execution" at HEAD though T1–T6 landed |
| F-004 | observation | — | 2 | — | Full suite: pre-existing M1 `test_escalations_returns_flagged_entry_with_error_log` failure (2 error_log rows vs 1) |
| F-005 | minor | contract-violation | 2 | T3/T4 | enrichment-batcher emits log events not in plan §2 logging contract |
| F-006 | minor | coverage-gap | 3, 5 | T2 | OOV rows skipped when `entry_type` is None — deferred in T2 decision log; no negative test |
| F-007 | minor | coverage-gap | 5 | T6 | Live docker compose smoke not in `verify-m5.sh` — explicitly deferred per plan T6 risks |
| F-008 | minor | coverage-gap | 3, 5 | T1 | Markdown code-fence JSON extraction deferred; no adversarial parser test |
| F-009 | minor | coverage-gap | 5 | T6 | Malformed Call 2 partial-failure not in full e2e — unit falsifiers only; deferred per CHANGELOG T6 |

**No critical findings.** M5 gate pytest slice green; no intent violations, security flaws, or M5-introduced regressions identified.

---

## 6. Detailed findings (above minor)

### F-001 — context-map-stale (major)

**Expected:** Scout map reflects pre-M5 state at `406ff61`.  
**Found:** Six commits (`f1782e9`…`0331dd5`) landed the full enrichment pipeline. Interface inventory rows describing absent `app/` package, pre_filter-only poller, and unwired `register_batch` are obsolete.  
**Evidence:** `git diff --stat 406ff61..HEAD` — 51 files; context-map provenance header SHA `406ff61`.  
**Action:** M6 pre-plan must re-explore at fresh SHA (handoff and charter §7 already note this).

### F-002 — artifact-not-in-HEAD (major)

**Expected:** Plan §8 handoff populated after T6 completion and committed for audit archaeology.  
**Found:** `.dev/plans/m5-enrichment/handoff.md` exists on working tree with complete §8.1–§8.6 but `git show 0331dd5:.dev/plans/m5-enrichment/handoff.md` fails. `git status` shows `?? handoff.md`.  
**Evidence:** Handoff self-documents follow-up commit intent (L16). M4 audit accepted same pattern as waiver.  
**Action:** Commit handoff before M6 orchestration; auditor re-pass not required once committed.

---

## 7. Phase 2 — Test execution

**Working tree SHA:** `0331dd5e34855657207ad2035158492d03a019ca` (matches handoff §8.1)

### M5 gate (binding)

```
Command: python -m pytest tests/test_state_worker_contract.py tests/test_state_worker_health.py tests/test_constants.py tests/test_enrichment_truncation.py tests/test_tag_taxonomy.py tests/test_enrichment_prompts.py tests/test_enrichment_parsers.py tests/test_state_worker_enrichment_hub.py tests/test_enrichment_batcher_config.py tests/test_enrichment_batcher_stage1_loop.py tests/test_enrichment_batcher_stage2_loop.py tests/test_batch_poller_startup.py tests/test_batch_poller_enrichment.py tests/test_batch_poller_loop.py tests/test_m5_integration.py tests/test_verify_m5.py -v --tb=short
Environment: win32, Python 3.14.2, pytest 9.0.2
Result: 105 passed, 39 warnings (alembic DeprecationWarning), exit code 0
```

### Full regression slice

```
Command: python -m pytest tests/ -q --tb=short
Environment: win32, Python 3.14.2, pytest 9.0.2
Result: 368 passed, 1 failed, exit code 1
Failure: tests/test_state_worker_routers_escalations.py::test_escalations_returns_flagged_entry_with_error_log
  AssertionError: assert 2 == 1  (operational HTTPStatusError row + ALERT sibling from M1 T8 dual-write)
```

**M5 did not touch escalations surfaces** (`git log 406ff61..HEAD -- tests/test_state_worker_routers_escalations.py` empty). Same failure documented in M2/M3/M4 handoffs and audits. **Not filed as M5 `contract-violation` critical** — program hygiene debt (F-004 observation).

### Contract compliance summary

| Contract area | Status |
|---------------|--------|
| §2 typed surfaces | All rows verified with named proof tests green |
| Typed config admission | `BISHOP_ENRICHMENT_STAGE*_BATCH_SIZE`, `BISHOP_ENRICHMENT_POLL_INTERVAL_SEC`, `BISHOP_G3_VERIFIED` — env parse + round-trip tests in `test_enrichment_batcher_config.py` |
| Error envelope literals | `model_string_fatal`, `profile_hash_mismatch`, `batch_timeout`, `enrichment_batch_complete`, `enrichment_batch_rejected` — byte-equal in shipped code |
| Batch type strings | `enrichment_stage1`, `enrichment_stage2` match `BatchTypeEnum` |
| `cache_control: {type: ephemeral}` | Present in `build_call2_system_prompt` first block |
| `custom_id` = `source_id` | `anthropic_batch_client.py` L53, L97 |
| Compose tags | `bishop/enrichment-batcher:m5`, `bishop/batch-poller:m5` — `docker-compose.yml` + `test_compose.py` |
| Hub sole-writer | No SQLite writes outside state-worker; batch-poller POSTs results only |
| Non-goals | No changes to scraper, content-scraper, pre-filter-worker, vector-writer, query-api, ui in M5 diff |

---

## 8. Phase 3 — Decision log audit

| Log | Chosen approach landed? | Rejected alternatives avoided? | Deferred items honored? | Stale prose? |
|-----|-------------------------|-------------------------------|------------------------|--------------|
| T1 | Yes — tiktoken, per-source truncation, taxonomy, prompts, parsers | Yes | HF live e2e, fence stripping deferred — not silently absorbed | Clean |
| T2 | Yes — transactional submit hook, timeout dispatch, OOV wire | Yes — no direct SQLite from poller | Router 409 envelope deferred — hub tests cover transitions | Clean |
| T4 | Yes — dual-task `gather`, hash verify, title+summary Call 2 | Yes — no full content_raw in Call 2 | CRITICAL alert on hash mismatch deferred; packet files-to-touch gap closed in code | Clean |

**Process note:** T3/T5/T6 assigned standard log tier — no decision logs required. Architectural decisions in T3/T5 are straightforward wiring without undocumented divergence.

**Narrative-concealment check:** Cold-read CR-02 (orphaned batch) acknowledged in CHANGELOG T3 and plan §5.2. CR-03 (OOV entry_type gate) documented in T2 decision log deferrals. No concealment.

---

## 9. Adversarial test log

### Focus 1 — Integration seams (context-map §Coupling surfaces)

| Scenario | Expected | Actual | Result |
|----------|----------|--------|--------|
| C1 POST `/batches` atomic register + submit | Entries `_SUBMITTED` in same txn as BatchRecord | `register_batch` L387–398 | **passes** |
| C2 `apply_batch_timeout` enrichment dispatch | `_SUBMITTED` → `_FAILED` | L506–537 + hub tests | **passes** |
| C3 `custom_id` = `source_id` join | Poller maps results by source_id | Client + integration e2e | **passes** |
| C4 `profile_render_hash` on stage2 | Mismatch aborts before Anthropic | `stage2_loop._verify_profile_hash` + test | **passes** |
| C5 T3/T4 file collision | Sequential land; coherent `main.py` | commits `073ff4e` → `47c7d91` | **passes** |
| C6 Compose m0 → m5 | compose tests green | `docker-compose.yml` L69, L85 | **passes** |
| C7 pre_filter regression | Existing loop tests green | 7/7 `test_batch_poller_loop.py` in gate | **passes** |
| Surface 7 OOV persistence | Rows in `oov_tags_log` via state-worker | `_insert_oov_tags_log` in H3 txn; e2e asserts ≥1 row | **passes** (with entry_type present) |
| Surface 8 startup scan all types | Enrichment in-flight recovered | `startup.py` + `test_m5_startup_scan_*` | **passes** |
| Dual-task scheduler vs poll states | Stage1 polls SCRAPED; stage2 polls STAGE2_QUEUED→CLAIMED | `main.py` `asyncio.gather` + double-poll test | **passes** |

### Focus 2 — Failure paths

| Scenario | Expected | Actual | Result |
|----------|----------|--------|--------|
| POST `/batches` fails after Anthropic submit | ERROR log with `external_batch_id`; no cancel | `stage1_loop` L161–171; CHANGELOG documents CR-1 | **passes** (accepted residual) |
| enrichment-stage*-results non-2xx | Retry next cycle; no PATCH complete | `loop.py` handlers return early on HTTPStatusError | **passes** — `test_poll_once_enrichment_stage1_results_non_2xx_skips_patch_complete` |
| 48h timeout enrichment | POST timeout → entries `_FAILED` | `_handle_timeout` + hub tests | **passes** |
| G3 / model string not verified | Skip cycle; `event=model_string_fatal` | `ensure_g3_verified` + tests | **passes** |
| Profile hash mismatch Call 2 | Abort batch; `event=profile_hash_mismatch` | `stage2_loop` L86–88 | **passes** |

### Focus 3 — Edge cases

| Scenario | Expected | Actual | Result |
|----------|----------|--------|--------|
| OOV tags stripped but `entry_type` None | Spec §7.5 needs entry_type | Skip insert L1070 | **passes** code path; **unknown** product impact — F-006 |
| Empty `content_raw` truncation | Non-empty prompt or graceful failure | Paper strategy may return empty; no explicit guard in stage1 | **unknown** — not gated in CI |
| Unknown `batch_type` in poller | Reject with `enrichment_batch_rejected` | `_merge_tracked` L58–66 | **passes** — intentional for exotic types; not normal enrichment dispatch |
| Markdown-fenced Call 1 JSON | Parse or fail entry | `_JSON_OBJECT_RE` may miss fenced nested JSON | **unknown** — F-008 deferred |

---

## 10. Coverage gap list (prioritized)

| Priority | Gap | Kill criterion / risk | Mitigation |
|----------|-----|----------------------|------------|
| P1 (program) | M1 escalations test expects 1 error_log row | Full suite hygiene | Fix test or document dual-row intent (pre-M5 debt) |
| P2 (deferred) | Live docker compose M5 smoke | T6 risk note | Manual validation before ops deploy (F-007) |
| P3 (deferred) | OOV without `entry_type` | T2 decision log | Add negative test if product requires rows without type |
| P3 (deferred) | Markdown-fence JSON | T1 decision log | Add stripper if production surfaces fenced responses |
| P3 (deferred) | Malformed Call 2 partial batch in e2e | T6 CHANGELOG | Unit falsifiers in `test_batch_poller_enrichment.py` |
| P4 | Truncation quality on live ArXiv HTML | Plan §5.2 treat-as-prediction | Charter G6 / M8 adapter e2e |

All T1–T6 kill criteria with automated observability are covered by the M5 gate slice.

---

## 11. Intent traceability

| Layer | Alignment |
|-------|-----------|
| Charter M5 intent | Dual asyncio enrichment tasks, Call 1/2 prompts, truncation, OOV parser, batch-poller v2, `SCRAPED` → `VECTOR_WRITE_QUEUED` — **aligned** |
| Plan task statement | All six subtasks map to landed code; non-goals respected (no vector-writer, query-api, ui, backfill) |
| Context-map flags 1–6 | All closed per handoff §8.4; verified in code |
| Map → plan files | Greenfield `enrichment-batcher/app/` and new `bishop_shared` modules predicted; landed as planned |
| Packet → diff | T4 touched `config.py`, `models.py`, `state_worker_client.py` beyond packet list — documented in T4 decision log |
| Double-poll exit gate | Charter cites `ENRICHMENT_STAGE2_CLAIMED`; test polls `STAGE2_QUEUED` twice, asserts `transitioned_to=ENRICHMENT_STAGE2_CLAIMED` and second poll empty — **aligned** |

**No `intent-drift` or `narrative-concealment` findings.**

---

## 12. Scout-prediction reconciliation

| Scout prediction | Type | Outcome | Finding |
|------------------|------|---------|---------|
| Surface 1 enrichment batch_type strings | confirmed_coupling | verified | — |
| Surface 2 POST /batches without submit transition | confirmed_coupling | verified | F-001 stale-qualified |
| Surface 3 apply_batch_timeout pre_filter-only | confirmed_coupling | verified | F-001 stale-qualified |
| Surface 4 custom_id = source_id | confirmed_coupling | verified | — |
| Surface 5 G3 model string chain | confirmed_coupling | verified | — |
| Surface 6 profile_render_hash stage2 | confirmed_coupling | verified | — |
| Surface 7 oov_tags_log writes | suspected_coupling | verified | T2 wire + H3 insert |
| Surface 8 startup pre_filter filter | confirmed_coupling | verified | — |
| Surface 9 Docker tag m0 | confirmed_coupling | verified | m5 tag |
| Flag 1 submit transition wiring | ambiguity_flag | verified | T2 |
| Flag 2 OOV persistence | ambiguity_flag | verified | T1+T2 |
| Flag 3 truncation without entry_type | ambiguity_flag | verified | source-based default |
| Flag 4 no enrichment-batcher tests | ambiguity_flag | verified | T3/T4/T6 tests |
| Flag 5 batch-poller v2 filter | ambiguity_flag | verified | TRACKED_BATCH_TYPES |
| Flag 6 T3/T4 file collision | ambiguity_flag | verified | sequential DAG |
| `register_batch` suspect_modified | suspect_modified | verified modified as predicted | F-001 stale-qualified |
| `apply_batch_timeout` suspect_modified | suspect_modified | verified modified | F-001 stale-qualified |
| `startup_scan` suspect_modified | suspect_modified | verified modified | F-001 stale-qualified |
| `EnrichmentStage1EntryWire` suspect_modified | suspect_modified | verified — `oov_tags_stripped` added | — |

---

## 13. Verdict

**`pass-with-conditions`**

M5 implementation matches charter intent and plan §2 contracts. The M5 gate (`verify-m5.sh` / 105-test pytest slice) is green at `0331dd5`. Integration falsifiers demonstrate five entries at `VECTOR_WRITE_QUEUED` with enrichment fields populated, OOV log rows, both enrichment `BatchRecord` types, `ENRICHMENT_STAGE2_CLAIMED` double-poll emptiness, and enrichment startup-scan recovery. Hub discipline preserved — state-worker remains sole SQLite writer.

### Conditions (non-blocking)

| ID | Condition |
|----|-----------|
| F-001 | Commit M6 pre-plan context map at fresh SHA before orchestration |
| F-002 | Commit `handoff.md` to HEAD for audit archaeology |
| F-003 | Update `plan.md` §8 status to Complete (housekeeping) |
| F-004 | Program hygiene: fix or waive M1 escalations test independently of M5 |
| F-005 | Accept enrichment-batcher auxiliary log events or extend §2 contract |
| F-006–F-009 | Accepted deferred risks per decision logs and CHANGELOG — no M5 gate change required |

---

## 14. Milestone handoff

```yaml
audit_status: accepted-with-waivers
milestone_id: M5
implementation_sha: 0331dd5e34855657207ad2035158492d03a019ca
audit_verdict: pass-with-conditions
audit_report: .dev/audits/2026-06-13-m5-enrichment.md
```

### Waivers

| Finding | Accepted residual risk |
|---------|------------------------|
| F-001 | Scout predictions stale; M6 pre-plan must re-explore at fresh SHA |
| F-002 | Handoff documents §8.1 results; commit before M6 orchestration |
| F-003 | Plan §8 placeholder does not affect runtime contracts |
| F-004 | M1 escalations router test failure does not affect M5 surfaces |
| F-005 | Auxiliary log events aid ops debugging; no consumer matches them |
| F-006 | OOV without entry_type is edge case; parser always sets type on success path |
| F-007 | Live compose smoke not automated; manual validation before ops deploy (M3/M4 pattern) |
| F-008 | Fence stripping deferred; batch JSON typically raw per Anthropic batch API |
| F-009 | Call 2 partial-failure covered by unit tests; full e2e defers per T6 |

### `landed_contracts` (charter cross-check)

Charter L342–349 surfaces vs implementation:

| Charter surface | Landed |
|-----------------|--------|
| Call 1 prompt template (`summary`, `concepts`, `tags`, `entry_type`, `challenge_hooks`) | Yes — `bishop_shared/enrichment_prompts.py` |
| Call 2 prompt template + `cache_control` on NL profile | Yes — `build_call2_system_prompt` |
| Content truncation helper (tiktoken 4k ceiling, per-source §13.1) | Yes — `bishop_shared/content_truncation.py` |
| OOV tag parser + `oov_tags_log` persistence | Yes — `tag_taxonomy.py` + state-worker H3 insert |
| `ENRICHMENT_STAGE2_CLAIMED` atomic claim | Yes — M1 + `test_m5_double_poll_stage2_queued_empty_while_claimed_held` |
| `batch-poller` all three batch types + startup scan | Yes — `TRACKED_BATCH_TYPES`, `startup.py`, `loop.py` dispatch |
| 48h timeout → `_FAILED` for enrichment stages | Yes — `apply_batch_timeout` + poller timeout handler |
| SUBMITTED → FAILED N3 exercised | Yes — timeout hub tests |

**Extended symbols (plan §2, charter-adjacent):**

- `bishop_shared/enrichment_config.py` — `ENRICHMENT_TRUNCATION_MAX_TOKENS`
- `bishop_shared/enrichment_parsers.py` — `parse_call1_response`, `parse_call2_response`
- `bishop_shared/anthropic_config.py` — `ANTHROPIC_MODEL_ENRICHMENT`
- `services/state-worker/app/transitions.py` — `register_batch` enrichment hook, `apply_batch_timeout` dispatch, `_insert_oov_tags_log`
- `services/state-worker/app/models/http.py` — `EnrichmentStage1EntryWire.oov_tags_stripped`
- `services/enrichment-batcher/app/stage1_loop.py` — `stage1_cycle`
- `services/enrichment-batcher/app/stage2_loop.py` — `stage2_cycle`
- `services/enrichment-batcher/app/main.py` — dual-task `run_scheduler`
- `services/enrichment-batcher/app/config.py` — `ENRICHMENT_STAGE1_BATCH_SIZE`, `ENRICHMENT_STAGE2_BATCH_SIZE`, `ENRICHMENT_POLL_INTERVAL_SEC`
- `services/enrichment-batcher/app/anthropic_batch_client.py` — Call 1/2 submit
- `services/enrichment-batcher/app/state_worker_client.py` — poll + register
- `services/batch-poller/app/models.py` — `ENRICHMENT_STAGE1_BATCH_TYPE`, `ENRICHMENT_STAGE2_BATCH_TYPE`, `TRACKED_BATCH_TYPES`
- `services/batch-poller/app/clients/state_worker.py` — enrichment result POST methods
- Compose `bishop/enrichment-batcher:m5`, `bishop/batch-poller:m5`
- `scripts/verify-m5.sh`

**Charter cross-check:** No charter-listed surface missing from `landed_contracts`. No undeclared charter surface shipped.

### M6 entry gate readiness

| Gate | Status |
|------|--------|
| G3 (model string verified) | Green — G3 gate + bypass pattern; CI mocks Anthropic |
| M5 exit (5 entries `VECTOR_WRITE_QUEUED`, OOV logs, batch records, double-poll, startup scan) | Green — `test_m5_integration.py` |
| M5 gate script | Green — `verify-m5.sh` / 105-test slice |
| Runnable checkpoint (enrichment-batcher + batch-poller + state-worker) | Code present; live smoke **manual** per F-007 |
| Post-M5 architecture refresh | **Not committed** — charter §7 housekeeping pending |

---

## 15. Auditor execution notes

```
git rev-parse HEAD  → 0331dd5e34855657207ad2035158492d03a019ca
git status --short  → ?? .dev/plans/m5-enrichment/handoff.md
python -m pytest <M5 gate paths> -v  → 105 passed
python -m pytest tests/ -q  → 368 passed, 1 failed (M1 escalations)
git show 0331dd5:.dev/plans/m5-enrichment/handoff.md  → fatal (not in HEAD)
```

Diff scope reviewed: `git diff 406ff61..0331dd5` (commits `f1782e9` T1 through `0331dd5` T6).
