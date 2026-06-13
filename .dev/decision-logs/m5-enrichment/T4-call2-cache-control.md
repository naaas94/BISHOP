# T4 — enrichment-batcher Call 2 loop and cache_control

**Subtask:** T4 (m5-enrichment)  
**Date:** 2026-06-13

## Chosen approach

- Added `stage2_cycle()` in `services/enrichment-batcher/app/stage2_loop.py`: poll `ENRICHMENT_STAGE2_QUEUED`, verify profile hash via `compute_profile_hash` vs YAML `canonical_hash` (pre-filter-worker pattern), submit Call 2 Anthropic batch with `build_call2_system_prompt` (ephemeral `cache_control` on profile block), register `enrichment_stage2` batch via state-worker.
- Extended `AnthropicBatchClient` with `build_stage2_requests` / `submit_stage2_batch`; Call 2 user message uses **title + summary only** — never `content_raw`.
- Dual-task scheduler in `main.py` runs `asyncio.gather(stage1_cycle, stage2_cycle)` each interval on a shared `StateWorkerClient`.
- Supporting package surfaces (`config.py` `ENRICHMENT_STAGE2_BATCH_SIZE`, `models.py` `Stage2BatchEntry` / `enrichment_stage2` batch type, `state_worker_client.poll_stage2_queued_entries`) required by plan §2 but omitted from packet files-to-touch; implemented to satisfy contract bindings.

## Alternatives rejected

- **Reuse stage1 `_profile_render_hash` (canonical only, no compute):** Rejected — Call 2 must detect tampered profile at batch time per error envelope; pre-filter `compute_profile_hash` comparison is the binding pattern.
- **Sequential stage1 then stage2 per tick:** Rejected — plan charter specifies dual asyncio tasks; `gather` allows both stages to progress within the same poll interval.
- **Omit `cache_control` when profile is short:** Rejected — spec Appendix A requires ephemeral cache on profile block; Anthropic may no-op below caching threshold.

## Assumptions made

- Poll response for `ENRICHMENT_STAGE2_QUEUED` includes `summary` from Call 1 completion (state-worker `Entry` serialization).
- M5 professional domain only; personal domain enrichment remains deferred per charter.
- Packet files-to-touch list is incomplete relative to §2 `ENRICHMENT_STAGE2_BATCH_SIZE` and poll/register surfaces; `config.py`, `models.py`, `state_worker_client.py` deltas are contract-required extensions of the T3 scaffold.

## Items deferred

- **Profile below Anthropic caching threshold:** `cache_control` still emitted per spec; caching may be no-op until profile grows — acceptable per plan risk note.
- **CRITICAL alert on profile hash mismatch:** enrichment-batcher logs `event=profile_hash_mismatch` only; pre-filter-worker emits `emit_profile_hash_mismatch_alert` — not in T4 error envelope for enrichment-batcher.
- **Orchestrator packet files-to-touch amendment:** supporting `app/` files touched beyond explicit T4 list; no functional gap.
