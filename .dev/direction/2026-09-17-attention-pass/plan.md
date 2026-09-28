# Operator next-steps — Bishop — 2026-09-17 (attention pass)

Dump: ad hoc pass over validated entries (and maybe parked) that flags must-looks or digests a range; persist everything, idempotent, no re-process; later a nicer home feed; later news/other signals. Pickup: park it. Open fork: may be a **separate consumer** of Bishop stores rather than a Bishop mill.

Durable copy of this run. Skill persist class: `.dev/direction/<date>-<slug>/` (owner `operator-next-steps`). Bishop `data-contract-registry.md` has no row for this — no schema yet. `.dev/architecture/dev_flow/data-contract-registry.md` is not in this repo; do not mint it as part of this park.

## Source map

| Track | Status | Where it already lives |
|---|---|---|
| Hygiene / audit | Open next-queue | `.dev/still_open.md`, `.dev/known-test-failures.md` |
| Product index | PB-011 mill `next`; this idea filed `idea` | `product-backlog.yaml` PB-013 (new), PB-010 sibling |
| Overlay / ops | Overlay still revert-or-promote | `.dev/decision-logs/ops/soft-launch-precision-overlay.md` |
| Already-scoped | MCP pantry/kitchen; spec daily digest deferred | `mcp-agent-tool-notes.md`, `.dev/decision-logs/ops/mcp-consumer-extraction.md`, `bishop_spec_0_6.md` §23, `.dev/architecture/bishop/open-questions.md` (extract vs VDB) |
| Charter | M9 gated | `.dev/bishop_program_charter.md`, `.dev/plans/m9-source-expansion/proposal.md` |
| Live UI | Dashboard is ops; `/recent` unused | `.dev/ui/agent-reference.md` |
| This dump | Parked write-up | `.dev/decision-logs/ops/attention-pass-consumer.md` |

## Placement of operator bets

| Bet | Placed against | Verdict |
|---|---|---|
| Ad hoc must-look / digest over INDEXED in a date range | spec §23 daily digest; Call 1/2 already leave cards (`summary`, `challenge_hooks`, `value_rationale`); PB-010 consumption sidecar | exists — **attention / consumption layer**, not ingest stage 3. Do not fold text into Call 1/2 or the VDB |
| Same pass on parked | overlay `RELEVANCE_PARKED` / `/parked` | overlay — **different population** (title+abstract, no scrape, no enrichment). Cheap promote-vs-leave, not a digest of validated knowledge |
| Idempotent persist of the pass | harvest ledger skip-if-done; MCP v2 sidecar keyed by `source_id`; `INDEXED` terminal; `reading_status` is human | exists pattern — sidecar / consumer store, **not** a new `processing_state` |
| Nicer landing / home feed | `/` → `/dashboard` is ops stats; query-api `GET /recent` unused by UI; spec §23 daily digest deferred until steady state | later — new reading surface once the store has rows. Do not restyle the dashboard into a magazine |
| Scale Bishop to news / other digests or signals | M9 source-expansion proposal; charter G7 / open Qs | **not earned**. Digest mill does not unlock adapters. News still has to become `ManifestIngestEntry` and survive gate 1 |
| Separate consumer of Bishop stores (query-api / SQLite ro / harvest sidecar) so Bishop stays pantry-focused | `.dev/decision-logs/ops/mcp-consumer-extraction.md` pantry vs kitchen | **new fork**, parked as the cleaner option. Not locked. Sibling of PB-010, not a collapse into it |

## Load-bearing facts

- `processing_state` stops at `INDEXED`. Do not add a successor for “digested.” `reading_status` (`unread` / `reading` / `read` / `archived`) is the human flag — do not reuse it for agent/consumer consumption.
- Parked rows never paid scrape or Call 1/2. A mill that takes “validated + parked” as one input will either enrich parked (spend) or treat INDEXED as if it still needs a gate.
- Single SQLite writer is `state-worker`. Harvest already lives in a **sidecar** (`${BISHOP_DATA_ROOT}/harvest/ledger.sqlite`), not `bishop.db`. A consumer store can follow that pattern without widening `ManifestIngestEntry` or entries columns.
- Architecture **data-contract-registry** (`.dev/architecture/bishop/data-contract-registry.md`) is for live contracts. No row until a schema exists. Do not edit that folder for a parked idea (OPEN-012 is “when convenient”).
- Related open question already on file: extract vs VDB / consumption sidecar closes when a few hand-scouts exist (PB-010). This dump does not close it.

## Sequence

**This week:** unchanged — `/parked` walk against the overlay note; hygiene OPEN-021 / PB-004 if convenient. Harvest mill (PB-011) stays next **code**, not this sitting.

**Not this sitting:** PB-013. No mill, no feed UI, no news adapters, no MCP.

**Pickup (when you want this):** a few **hand** passes on a date range of INDEXED (and separately parked if useful). Persist the artifacts. Then schema. Then pick the open fork (Bishop-owned job vs separate consumer). Feed UI after the store has rows a human would open. News/signals only after M9 is earned, as pantry adapters.

## Do not

- Start this mill, a home-feed restyle of `/dashboard`, MCP, or M9 in the same sitting as overlay/harvest work.
- Collapse PB-013 into PB-010, or into Call 1/2 / N1 embed / `processing_state` past `INDEXED`.
- Treat parked and INDEXED as one population.
- Wire “we have a digest job” to RSS/news adapters.
- Add a contract row to `.dev/architecture/bishop/data-contract-registry.md` before a schema exists.
- Invent a third product index. Pickup is PB-013 + the ops write-up.

## Filing proposals

| Proposed id | Title | Status |
|---|---|---|
| PB-013 | Attention pass / digest consumer (sidecar; not ingest) | **filed** `idea` in `product-backlog.yaml` |

Write-up: `.dev/decision-logs/ops/attention-pass-consumer.md`. Pointers: `mcp-agent-tool-notes.md`, `AGENTS.md`, `CHANGELOG.MD`.

---

## Conversation (parked, 2026-09-17)

The spine is right: ingest stays the pantry; a later pass turns “this survived the gates” into “this is worth your attention”; persist so you never pay twice; a home surface reads that store.

Call 1/2 already leave a card. `/dashboard` is an ops funnel. `GET /recent` exists and the UI never uses it. Spec §23 already names a daily digest as deferred. MCP notes already say: Bishop is the pantry; a sidecar remembers “we looked.”

The new thing is not another enrichment call. It is a **consumption layer**.

**INDEXED** already paid scrape + Call 1 + Call 2 + embed. A second pass is ranking and synthesis. Folding that text back into `summary` / hooks / the vector poisons later retrieval.

**Parked** is overlay-only: title + abstract. A pass there is a cheap second look at the inbox (promote vs leave). Promote still goes through `POST /parked/promote`.

**Persist:** harvest skip-if-done + MCP v2 sidecar shape. Writes through state-worker *if* this stays inside Bishop; a separate consumer can own its own store and only **read** query-api / `bishop.db` `mode=ro`. That is the cleaner-focus fork.

**Home feed** later: what to look at, not how the pipes are doing. `/dashboard` stays ops.

**News** is M9 (source class), not a child of the digest job.

Split in your head: (1) ad hoc you run it → (2) schema the artifact → (3) feed UI → (4) news only after M9. Open fork at (2): Bishop mill vs separate consumer of stores.
