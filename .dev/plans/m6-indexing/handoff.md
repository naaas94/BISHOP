# M6 — Indexing Slice · Auditor §8 Handoff

**Plan:** `m6-indexing` v1.0  
**Status:** Complete — ready for adversarial audit  
**Charter slice:** `.dev/bishop_program_charter.md` L386–436  
**Normative spec:** `bishop_spec_0_6.md` v1.5.0 (tracked)

---

## §8.1 Completion snapshot

**Tree SHA:** `01d58c2979cef25913d47102022162158eddee9b`

**Tracked-tree cleanliness at implementation SHA:** `git status` clean at `01d58c2` for all implementation commits (T1–T6 code committed).

**Handoff recording note:** This file and sibling plan artifacts (`.dev/plans/m6-indexing/plan.md`, `context-map.md`, `packets/`) are authored after `01d58c2` and are **not yet tracked** at the implementation SHA. Auditor should treat `01d58c2` as the **implementation anchor**; read handoff from the commit that adds it, or from working tree if handoff lands in a follow-up commit.

**Executor commit chain** (`494db2c`…`01d58c2`):

| Commit | Subtask | Summary |
|--------|---------|---------|
| `494db2c` | T1 | `bishop_shared` indexing contracts — `indexing_config`, `atomic_persist`, N1 embed text, store paths |
| `74a782e` | T2 | `EmbeddingEncoder` + `LanceDbStore` with `source_id` check-before-write |
| `0d0c717` | T3 | Pin `rank-bm25` + `filelock` in vector-writer requirements |
| `456112e` | T3 | `Bm25DualIndex` — dual corpus, domain lock, atomic pickle persist |
| `d23e99c` | T4 | `DuckDbMirror` — `entries_mirror` DDL, `INSERT OR REPLACE` upsert |
| `6fb6844` | T5 | `vector-writer` service — poll, `index_entry`, scheduler, Dockerfile `app.main` |
| `01d58c2` | T6 | `verify-m6.sh`, compose `m6` tag + `stop_grace_period`, integration + G5 fixture gate |

**Primary automated verification (M6 gate — run at handoff recording):**

```
Command: python -m pytest tests/test_state_worker_contract.py tests/test_state_worker_health.py tests/test_constants.py tests/test_indexing_config.py tests/test_atomic_persist.py tests/test_vector_writer_embedding.py tests/test_lancedb_store.py tests/test_bm25_store.py tests/test_duckdb_mirror.py tests/test_vector_writer_config.py tests/test_vector_writer_models.py tests/test_vector_writer_index_entry.py tests/test_vector_writer_loop.py tests/test_bm25_lock_contention.py tests/test_duckdb_concurrent_read.py tests/test_m6_integration.py tests/test_g5_quality_gate.py tests/test_verify_m6.py -v --tb=short
Environment: win32, Python 3.14.2, pytest 9.0.2
Result: 87 passed, 1 skipped (test_g5_quality_gate_live — heavy, requires BISHOP_G5_LIVE=1), 32 warnings (alembic DeprecationWarning; PytestUnknownMarkWarning for @pytest.mark.heavy), exit code 0
```

**Equivalent verify-m6.sh slices (pytest parity):**

```
G2 slice:  33 passed (test_state_worker_contract + health + constants)
M6 slice:  54 passed, 1 skipped (verify_m6 + indexing_* + vector_writer_* + bm25_lock + duckdb_concurrent + g5 fixture + m6_integration; heavy live excluded)
Combined unique modules in gate: 87 test executions in single combined run
```

**Equivalent bash gate:**

```
Command: scripts/verify-m6.sh
```

**Full regression slice (recommended auditor sanity check):**

```
Command: pytest tests/ -q
Environment: win32, Python 3.14.2, pytest 9.0.2
Result: 422 passed, 1 skipped, 2 failed, exit code 1
Failures:
  - tests/test_state_worker_routers_escalations.py::test_escalations_returns_flagged_entry_with_error_log
    — pre-existing M1 T8 side-effect (ALERT sibling row in error_log); not introduced by M6
  - tests/test_state_worker_config.py::test_config_env_round_trip
    — passes in isolation; fails in full-suite order (likely env pollution between tests); not introduced by M6
```

**Live Docker gate:** Not executed at handoff recording. CHANGELOG defers live `docker compose up vector-writer state-worker` smoke to manual validation (M3/M4/M5 pattern).

---

## §8.2 Artifact chain

Read order for auditor. `git show 01d58c2:<path>` at implementation SHA unless noted.

| Path | Resolves at `01d58c2` | Notes |
|------|----------------------|-------|
| `.dev/plans/m6-indexing/context-map.md` | **No** — follow-up commit | Scout SHA `ac991e9` — **stale** vs implementation; treat interface inventory as prediction |
| `.dev/plans/m6-indexing/plan.md` | **No** — follow-up commit | v1.0 |
| `.dev/plans/m6-indexing/handoff.md` | **No** — this file | Follow-up commit |
| `.dev/plans/m6-indexing/packets/T1.md` … `T6.md` | **No** — follow-up commit | Executor packets |
| `.dev/decision-logs/m6-indexing/T1-indexing-shared-contracts.md` | Yes | |
| `.dev/decision-logs/m6-indexing/T2-lancedb-encoder.md` | Yes | |
| `.dev/decision-logs/m6-indexing/T3-bm25-rank-bm25-choice.md` | Yes | |
| `.dev/plans/m5-enrichment/handoff.md` | Yes | M6 entry gate |
| `.dev/architecture/bishop/` | Yes @ pre-M6 | Post-M6 architecture refresh per charter §7 **not yet run** |
| `bishop_spec_0_6.md` | Yes | Binding normative reference |
| `CHANGELOG.MD` | Yes | M6 T1–T6 entries |
| `bishop_shared/indexing_config.py` | Yes | T1 |
| `bishop_shared/atomic_persist.py` | Yes | T1 |
| `services/vector-writer/app/` | Yes | T2–T5 |
| `services/vector-writer/requirements.txt` | Yes | T2–T5 |
| `services/vector-writer/Dockerfile` | Yes | CMD `python -m app.main` |
| `docker-compose.yml` | Yes | `bishop/vector-writer:m6`, `stop_grace_period: 30s` |
| `scripts/verify-m6.sh` | Yes | |
| `tests/test_m6_integration.py` | Yes | |
| `tests/test_g5_quality_gate.py` | Yes | |
| `tests/fixtures/g5_quality_gate.py` | Yes | |
| `tests/test_verify_m6.py` | Yes | |

---

## §8.3 §2 evidence

| §2 binding | Landed artifact | Proof test |
|------------|-----------------|------------|
| `EMBEDDING_MODEL` | `bishop_shared/indexing_config.py:L10` | `test_embedding_model_pinned` |
| `EMBEDDING_DIM` | `bishop_shared/indexing_config.py:L11` | `test_embedding_dim` |
| `build_embed_text` | `bishop_shared/indexing_config.py:L33-L39` | `test_build_embed_text_n1`, `test_build_embed_text_none_hooks` |
| `LANCEDB_DIR` / `LANCEDB_TABLE_NAME` | `bishop_shared/indexing_config.py:L17-L18` | `test_store_paths_match_constants` |
| `DUCKDB_PATH` | `bishop_shared/indexing_config.py:L20-L21` | same |
| `bm25_domain_root` + subdirs + lock name | `bishop_shared/indexing_config.py:L23-L30` | same |
| `atomic_persist` | `bishop_shared/atomic_persist.py:L11-L26` | `tests/test_atomic_persist.py` |
| `EmbeddingEncoder` | `services/vector-writer/app/embedding.py` | `tests/test_vector_writer_embedding.py` |
| `LanceDbStore` / `LanceRow` | `services/vector-writer/app/stores/lancedb_store.py` | `tests/test_lancedb_store.py` |
| `Bm25DualIndex` | `services/vector-writer/app/stores/bm25_store.py` | `tests/test_bm25_store.py` |
| `DuckDbMirror` / `entries_mirror` | `services/vector-writer/app/stores/duckdb_mirror.py:L15-L41` | `tests/test_duckdb_mirror.py` |
| `EntryPollRow` (no `content_raw`) | `services/vector-writer/app/models.py:L15-L35` | `test_entry_poll_row_has_no_content_raw_field` |
| `VECTOR_WRITE_POLL_STATE` | `services/vector-writer/app/config.py` | `test_vector_write_poll_state_default` |
| `VECTOR_WRITE_BATCH_SIZE` / poll interval | `services/vector-writer/app/config.py` | `tests/test_vector_writer_config.py` |
| `index_entry` ordering | `services/vector-writer/app/index_entry.py:L86-L188` | `tests/test_vector_writer_index_entry.py` |
| `index_cycle` | `services/vector-writer/app/loop.py:L15-L54` | `tests/test_vector_writer_loop.py` |
| `G5_FIXTURE_QUERIES` | `tests/fixtures/g5_quality_gate.py:L8-L12` | `test_g5_fixture_queries_count`, `test_g5_quality_gate_fixture` |
| Compose `bishop/vector-writer:m6` | `docker-compose.yml:L101` | `tests/test_compose.py::test_image_tags_use_milestone_convention` |
| `stop_grace_period: 30s` | `docker-compose.yml:L102` | `tests/test_compose.py::test_vector_writer_stop_grace_period` |
| Stub graduation | `tests/test_service_stubs.py` `T2_M6_REAL_WORKER_SERVICES` | `test_m6_worker_uses_real_main_entrypoint` |
| M6 gate script | `scripts/verify-m6.sh` | `tests/test_verify_m6.py` |
| E2e INDEXED + three stores | `tests/test_m6_integration.py` | `test_m6_e2e_vector_write_queued_reaches_indexed_with_three_stores` |
| LanceDB idempotent re-index | same | `test_m6_idempotent_reindex_skips_duplicate_lancedb_vector` |
| BM25 lock contention | `tests/test_bm25_lock_contention.py` | `test_second_writer_waits_on_domain_lock` |
| DuckDB read_only after release | `tests/test_duckdb_concurrent_read.py` | `test_read_only_connection_after_mirror_releases_write` |
| Decision logs T1/T2/T3 | `.dev/decision-logs/m6-indexing/` | Present at HEAD |

---

## §8.4 §5 disposition

### §5.2 load-bearing assumptions

| Tuple | Disposition | Evidence |
|-------|-------------|----------|
| M1 mark_indexed + VECTOR_WRITE_QUEUED poll exemption correct | **closed** | No state-worker edits in M6; `test_m6_e2e_*` reaches INDEXED via `POST /entries/indexed`; existing M1 contract tests unchanged |
| check-before-write idempotency without claim lock | **closed** | `test_m6_idempotent_reindex_skips_duplicate_lancedb_vector`; `lancedb_skip_duplicate` / `bm25_skip_duplicate` logging in `index_entry.py` |
| sentence-transformers 384-dim vectors | **treat-as-prediction** | Unit tests mock encoder; `test_g5_quality_gate_live` skipped in CI — manual `BISHOP_G5_LIVE=1` required for real MiniLM probe |
| M5 entries have summary + challenge_hooks for embed | **closed** | M6 integration seeds non-null enrichment fields; `build_embed_text` exercised in index path |
| rank-bm25 pickle reload stable | **closed** | `tests/test_bm25_store.py` persist/reload cycle; corrupt-pickle recovery deferred per T3 decision log |

### §5.4 hidden couplings

| Tuple | Disposition | Evidence |
|-------|-------------|----------|
| VECTOR_WRITE_QUEUED poll omits content_raw | **closed** | `EntryPollRow` has no `content_raw`; `test_entry_poll_row_has_no_content_raw_field` |
| single domain BM25 lock covers main + hooks + persist | **closed** | `Bm25DualIndex` uses one `BM25_LOCK_NAME` at domain root; `test_bm25_lock_contention.py` |
| DuckDB write vs query-api read_only | **treat-as-prediction** | `test_read_only_connection_after_mirror_releases_write` passes; concurrent RW+RO mixed-mode documented as unsupported — M7 must open `read_only=True` only after writer releases |
| Compose tag m0 → m6 | **closed** | `docker-compose.yml`, `test_compose.py` |
| test_service_stubs stub classification | **closed** | `T2_M6_REAL_WORKER_SERVICES` + Dockerfile CMD `app.main` |
| T2/T3/T4 requirements.txt collision | **closed** | Single consolidated `requirements.txt` at T5; no merge conflict |
| sentence-transformers model download at start | **treat-as-prediction** | Dockerfile comment L13; CI mocks encoder; first container start untested in gate |

### Context-map flags (§0 orch resolutions)

| Flag | Resolution | Disposition |
|------|------------|-------------|
| 1 BM25 library | rank-bm25 + atomic_persist | **closed** |
| 2 DuckDB DDL | `entries_mirror` per plan | **closed** |
| 3 LanceDB schema | table `entries`, source_id idempotency | **closed** |
| 4 G5 automation | fixture gate + optional live heavy | **closed** (fixture); live **open** until manual run |
| 5 No state-worker changes | honored | **closed** |
| 6 stop_grace_period | compose 30s | **closed** |

### Auditor hygiene (non-blocking unless policy requires)

- Context map scout SHA (`ac991e9`) stale vs implementation (`01d58c2`) — expected; M7 pre-plan should re-explore.
- Plan artifacts (context-map, plan, packets, handoff) untracked at implementation SHA — commit before auditor `git show` chain is fully green.
- Post-M6 `.dev/architecture/` refresh not committed — charter §7 housekeeping pending.
- Full-suite `test_escalations_returns_flagged_entry_with_error_log` failure inherited from M1 T8 — **open** for program hygiene, **not M6 blocking**.
- `test_state_worker_config.py::test_config_env_round_trip` flaky in full suite — **open**, passes isolated; not M6-introduced.
- Live docker compose e2e not automated in `verify-m6.sh` (deferred per CHANGELOG T6).
- `pytest.mark.heavy` not registered in `pyproject.toml` — PytestUnknownMarkWarning only; gate excludes heavy via `-m "not heavy"`.
- G5 live semantic quality on real MiniLM not executed at handoff — charter G5 subjective gate satisfied by fixture map for merge; owner should run `BISHOP_G5_LIVE=1` before M7 entry.
- BM25 `add_main` / `add_challenge_hooks` / `persist` acquire domain lock in separate `with` blocks (not one continuous hold) — acceptable for single-writer MVP; T3 decision log documents single lock file, not single critical section.
- `services/vector-writer/stub_main.py` remains in tree but Dockerfile CMD uses `app.main` — stub unused at runtime (same pattern as other services post-M0).

---

## §8.5 Cold-read seeds

Narrative-blind Phase 0 — contract-vs-code drift surfaces:

1. `services/vector-writer/app/index_entry.py` — store write ordering, idempotent skip paths, indexed vs failed POST
2. `bishop_shared/indexing_config.py` — embedding pin, N1 `build_embed_text`, path constants
3. `services/vector-writer/app/stores/bm25_store.py` — dual-index lock scope, `atomic_persist` usage, corpus field set
4. `services/vector-writer/app/stores/lancedb_store.py` — `exists` check-before-write, explicit 384-dim Arrow schema
5. `services/vector-writer/app/stores/duckdb_mirror.py` — `entries_mirror` DDL and upsert column set
6. `tests/test_m6_integration.py` — charter exit-gate falsifiers (INDEXED + three stores, LanceDB idempotent re-index)

---

## §8.6 Audit remediation cross-link

Absent — no §7 amendments fired during M6 v1.0.

**Pre-declared trigger (unchanged):** If `BISHOP_G5_LIVE=1` live gate fails with pinned MiniLM, route §7 amendment for `nomic-embed-text` upgrade per charter §8.4 L576 before M7.

---

## Landed contracts summary (M7 pre-plan seed)

**Symbols extended (new in M6):**

- `bishop_shared/indexing_config.py` — `EMBEDDING_MODEL`, `EMBEDDING_DIM`, `build_embed_text`, `LANCEDB_DIR`, `LANCEDB_TABLE_NAME`, `DUCKDB_PATH`, `bm25_domain_root`, BM25 subdir/lock constants
- `bishop_shared/atomic_persist.py` — spec S4 atomic write wrapper
- `services/vector-writer/` — full indexing pipeline service
- `EmbeddingEncoder`, `LanceDbStore`, `Bm25DualIndex`, `DuckDbMirror` (`entries_mirror`)
- Poll state `VECTOR_WRITE_QUEUED` (no claim); completion `POST /entries/indexed` (unchanged M1 wire)
- Compose `bishop/vector-writer:m6`, `stop_grace_period: 30s`
- `scripts/verify-m6.sh`
- G5 fixture gate: `tests/fixtures/g5_quality_gate.py`, `G5_FIXTURE_QUERIES` (3 queries)

**M6 exit gate:** `scripts/verify-m6.sh` / M6 pytest slice green (87 passed, 1 heavy skipped). Integration demonstrates `VECTOR_WRITE_QUEUED` → `INDEXED` with LanceDB row, BM25 `main/` + `challenge_hooks/` pickles, DuckDB `entries_mirror` row, and LanceDB duplicate skip on re-index.

**M7 entry gate:** G5 fixture gate passed in CI; charter recommends live G5 probe before read-path work. At least one `INDEXED` entry producible via M6 integration harness. Embedding model + text pin (`all-MiniLM-L6-v2`, N1 concat) are now program-level contracts in `bishop_shared/indexing_config.py`. BM25 directory layout `bm25/{domain}/main/` and `bm25/{domain}/challenge_hooks/` landed.

**Runnable checkpoint (charter):** `vector-writer` polls `GET /entries/poll?state=VECTOR_WRITE_QUEUED`, embeds with pinned model/text, writes LanceDB (check-before-write), updates dual BM25 indices under domain lock with atomic persist, upserts DuckDB mirror, posts `POST /entries/indexed` → `INDEXED` terminal state.

---

## Read-only review summary (orchestrator)

**Intent alignment:** All charter contract surfaces addressed — embedding generation (`all-MiniLM-L6-v2`, 384 dims, N1 text), LanceDB idempotency, BM25 main + challenge_hooks with file lock and S4 atomic persistence, DuckDB `INSERT OR REPLACE`, `POST /entries/indexed` signaling, G5 fixture quality gate. Hub restriction honored: no state-worker REST or transition changes.

**Non-goals:** No query-api, ui, backfill, or BM25 reload. No `nomic-embed-text` upgrade unless live G5 fails.

**Highest residual risk:** Real-world embedding retrieval quality on live ArXiv enrichment output (fixture G5 passes with orthogonal mocked vectors; live MiniLM gate not run at handoff). Second: first Docker start model download latency/offline failure.

**Verdict:** Ready for adversarial audit at SHA `01d58c2`. Recommend committing plan artifacts + this handoff before auditor Phase 0.5 artifact chain validation.
