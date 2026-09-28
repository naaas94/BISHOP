# Attention pass / digest consumer (parked)

**Date:** 2026-09-17  
**Scope:** product — consumption layer over INDEXED (and maybe parked); home feed later; news/signals not this idea  
**Status:** Documented, parked. No mill, no schema, no UI, no code.

Tracked as **PB-013** (`idea`). Pickup: `.dev/direction/2026-09-17-attention-pass/plan.md`. Sibling, not collapse: PB-010 / `mcp-agent-tool-notes.md`.

## Verdict

Bishop stays the **shared pantry** (scrape → gate → enrich → index → query). An **attention pass** is a later consumer: given a range of survivors, persist must-look flags and/or a short digest so a rerun is a no-op, and so a home feed can read that store.

Do not make this ingest stage 3. Do not extend `processing_state` past `INDEXED`. Do not reuse `reading_status`. Do not fold digest text into Call 1/2 fields, `challenge_hooks`, or the N1 embed. Do not treat parked and INDEXED as one mill input. Do not treat this as M9 (news adapters).

**Open fork (not locked):** implement as a Bishop-owned job (sidecar via state-worker, harvest-ledger pattern) **or** as a **separate consumer** that only reads query-api / SQLite `mode=ro` (and maybe the harvest sidecar) and owns its own store + UI. Operator lean 2026-09-17: separate consumer may keep Bishop cleaner and more focused. Decide after a few hand passes, not before.

## What already exists

| Surface | What it is | Why it is not this |
|---|---|---|
| Call 1/2 card | `summary`, `concepts`, `tags`, `challenge_hooks`, `relevance_score`, `value_rationale` | Per-item enrichment. Not cross-range ranking or “look at this now.” |
| `/dashboard` | Ops funnel (`GET /stats/overview`) | Pipeline glance, not a reading feed. |
| `GET /recent` | query-api “what landed,” unused by UI | Candidate **read** for a feed; not a digest store. |
| `/parked` | Overlay inbox: `RELEVANCE_PARKED`, title+abstract, promote | Different population. No scrape, no Call 1/2. |
| Spec §23 daily digest | Named deferred surface after backfill/steady state | The named home for a later reading surface. Not earned. |
| PB-010 MCP + scout sidecar | Read-only retrieval; later `record_scout` against `source_id` | Same pantry/kitchen doctrine. Different job (agent tool + visit/scout vs operator attention/digest/feed). |
| Harvest ledger | Sidecar, skip-if-exists, not `bishop.db` | Pattern to copy for idempotent persist. Not this feature. |
| M9 source expansion | Non-paper source class into `ManifestIngestEntry` | News/signals still have to enter the pantry. A digest job does not unlock adapters. |

## Layers (do not collapse)

| Layer | Population | Job |
|---|---|---|
| Ingest | manifest → entries | Gates + cards. Stops at `INDEXED`. |
| Attention pass | INDEXED in a range | Must-look / skip / short digest. Idempotent. Persisted. |
| Parked second look | `RELEVANCE_PARKED` | Cheap promote-vs-leave. Separate prompt, spend, write (`POST /parked/promote`). Overlay — not spec until overlay is promoted. |
| Home feed | rows the pass already wrote | Reading landing. New page; `/dashboard` stays ops. |
| News / extra signals | new adapters | M9. Pantry expansion, not a child of the digest job. |

## Persist / idempotency

- Key by identity (`source_id` and/or pass-run + range). Skip if already processed.
- Append-only events beat a boolean `digested` (same lesson as scouted_empty vs scouted_kept).
- If Bishop-owned: sidecar, not entries columns; writes through state-worker; query-api `mode=ro`.
- If separate consumer: that process never receives `STATE_WORKER_URL` unless it is explicitly posting promote/reading-status; default is read-only query-api.
- Architecture `data-contract-registry.md`: **no row until a schema exists.**

## Build order (when unparked)

1. Hand pass on a date range of INDEXED (optionally a separate parked pass). Persist the artifacts.
2. Schema against real outputs. Pick Bishop mill vs separate consumer.
3. Idempotent job. Then feed UI if the store has rows worth opening.
4. News/signals only after M9 is earned.

Experiment before mill — same bar as PB-010 v2.

## Related

- `.dev/direction/2026-09-17-attention-pass/plan.md`
- `product-backlog.yaml` PB-013
- `mcp-agent-tool-notes.md` (PB-010; do not collapse)
- `.dev/decision-logs/ops/mcp-consumer-extraction.md`
- `bishop_spec_0_6.md` §23 daily digest
- `.dev/ui/agent-reference.md` (`GET /recent` unused)
- `.dev/plans/m9-source-expansion/proposal.md` (not this)
