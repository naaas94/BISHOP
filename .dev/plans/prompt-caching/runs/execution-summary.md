# Execution summary — prompt-caching

**Scope:** full; rank-1 `{T2, T3, T4, T8, T9}` ran in parallel; rank-2 `{T5, T6, T7}` ran in parallel
**Plan SHA at start / at end:** `70c5501` / `5704555` (v1.5.0; T10-bis later back-filled plan.md §8)
**Run status:** complete (G1 gate-satisfied; T11 landed)

## Node outcomes
| ID | Status | model_class | Commit SHA | Summary |
|---|---|---|---|---|
| T1 | halted | architectural | not committed | Row-9 grep vs live Call 2 emitter; continued by T1-bis |
| T1-bis | complete | architectural | `8d9af01` | Shared cache/rubric contract; row-9 test expected-red |
| T2 | complete | architectural | `d0f37d3` | Pre-filter rubric annex (cache key A) |
| T3 | complete | architectural | `c6d9f80` | Call 1 rubric annex (cache key B) |
| T4 | complete | architectural | `e4b7e9d` | Call 2 rubric annex (cache key C) |
| T5 | complete | standard | `eb9b873` | Pre-filter cache key A wiring |
| T6 | complete | architectural | `ba49bb1` | Call 1 cache key B wiring |
| T7 | halted | architectural | not committed | Packet §6 supersession banner; continued by T7-bis |
| T7-bis | complete | architectural | `1fe3ef4` | Call 2 cache key C wiring + M5 first-mention supersession banner |
| T8 | complete | standard | `c8fc67d` | Poller cache-usage observability |
| T9 | halted | architectural | not committed | Files-to-touch omission; continued by T9-bis |
| T9-bis | complete | architectural | `c47248e` | Batch amortization + config-test pin 10→50 |
| T10 | halted | standard | not committed | Row 20 frozen-path `git log b919fdb..HEAD` non-empty; continued by T10-bis |
| T10-bis | complete | standard | `21c8e3d` (substantive `370c0cd`) | Token-floor gate, docs, §8, closure report |
| T11 | complete | standard | `31b68f1` | Idle-flush MAX_HOLD 120→30 |
| G1 | gate-satisfied | gate | — | Cache key A. Second post-rebuild complete `ebc1c3be`: `cache_read_tokens=276150`. Not re-opened. |
| T12 | complete (direct impl., not orchestrator-dispatched) | standard | — | FU-CACHE-WARMUP-01 sync warmup ping (all 3 keys) + `BISHOP_SCRAPER_SCHEDULE_INTERVAL_SEC` 6h→45min. See `.dev/decision-logs/prompt-caching/T12-cache-warmup-ping.md`. **Requires image rebuild to take effect — not live until `docker compose up -d --build`.** |

**Post-close note (2026-09-15):** this plan's v1.5.0 banner named `FU-CACHE-WARMUP-01` out of scope. T12 lands it directly (operator-approved after an adversarial review, not via a new orchestrator packet/dispatch round) — see the CHANGELOG `prompt-caching — 2026-09-15` entry and the T12 decision log for the rejected batch-based-warmup alternative and the still-unverified live assumption (sync/batch cache-namespace sharing).

## G1 evidence (operator live, 2026-09-12)

Containers rebuilt and up from `2026-09-12T22:17:36Z` (`bishop-pre-filter-worker-1`, `bishop-enrichment-batcher-1`, `bishop-batch-poller-1` among others). Compose stdout `INFO:app.loop:batch complete` does **not** print T8 extra keys (`logging.basicConfig`); numbers below are the Anthropic `message.usage` totals on the same results the poller fetched at those complete events. No `event=cache_read_zero` warning was emitted.

Post-rebuild `pre_filter` (cache key A), submitted after poller start, completed in order:

| # | batch_id | external_batch_id | submitted (UTC) | cache_write | cache_read |
|---|---|---|---|---|---|
| 1 | `774583c2-1243-4cc7-880f-b7976d394c9d` | `msgbatch_0166j9e1nPHnqg6YYngT85CM` | 22:17:40 | 226443 | 49707 |
| 2 | `ebc1c3be-84dd-4522-b4f2-a23b58c233a9` | `msgbatch_0123h5r5nfNTw8ce3P8pQK3f` | 22:18:41 | 0 | **276150** |
| 3 | `9ca7a1a9-4649-48fe-824b-7f1d01403710` | `msgbatch_01DkceEMVv1FAvz3YXc1cyH3` | 22:19:42 | 0 | 276150 |
| 4 | `d300d0a4-5db3-412e-8cb3-3c7a112542d9` | `msgbatch_01V3pUpcgdKwBgzShR2Ko9Z5` | 22:20:44 | 0 | 276150 |

PASS criterion: second batch on the same cache key has `cache_read_tokens > 0`. Enrichment keys B/C were not required for this close.

## Completion snapshot (auditor Phase 0.5 / Phase 2 input)
- Final tree SHA: `31b68f19a6dd86efe880cc24becce876cf90dc77`
- Per-node commit SHAs: T1 none; T1-bis `8d9af01`; T2 `d0f37d3`; T3 `c6d9f80`; T4 `e4b7e9d`; T5 `eb9b873`; T6 `ba49bb1`; T7 none; T7-bis `1fe3ef4`; T8 `c8fc67d`; T9 none; T9-bis `c47248e`; T10 none; T10-bis `370c0cd` + `21c8e3d`; T11 `31b68f1`
- Artifact paths produced this run: `.dev/plans/prompt-caching/runs/ledger.md`, `T1-brief.md`, `T1-bis-brief.md`, `T2-brief.md`, `T3-brief.md`, `T4-brief.md`, `T5-brief.md`, `T6-brief.md`, `T7-brief.md`, `T7-bis-brief.md`, `T8-brief.md`, `T9-brief.md`, `T9-bis-brief.md`, `T10-brief.md`, `T10-bis-brief.md`, `T11-brief.md`, `execution-summary.md`; `.dev/plans/prompt-caching/artifacts/T10-closure-report.md`
- Decision logs: `.dev/decision-logs/prompt-caching/T1-bis-cache-and-rubric-contract.md`, `T2-prefilter-rubric.md`, `T3-call1-rubric.md`, `T4-call2-rubric.md`, `T6-call1-wiring.md`, `T7-bis-call2-breakpoint-move.md`, `T9-bis-batch-amortization.md`
- Verification command declared by the plan (not run by this skill): `pytest tests/ -m "not heavy"`

## Open items
- [ ] Rebuild `pre-filter-worker` and `enrichment-batcher` so the 30-minute idle-flush defaults take effect (image-baked via `config.py`, not compose env)
- [ ] Auditor-review offered, not invoked
- Halted originals T1 / T7 / T9 / T10 are historical records; not re-dispatched
- T10-bis named gap in plan.md §8.4: `A5, A6, C1–C10 (excl. C11/C12), C13` recorded as unresolved because dispatch forbade reading plan §5
- Warmup deferred as `FU-CACHE-WARMUP-01`
