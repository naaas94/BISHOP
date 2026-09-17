# Operator next-steps — Bishop — 2026-09-17

Dump was “what next?” with no extra bets. This sequences what the notes already call next; it does not start a build.

## Source map

| Track | Status | Where it already lives |
|---|---|---|
| Hygiene / audit | Open next-queue; suite is not the merge gate | `.dev/still_open.md`, `.dev/known-test-failures.md` |
| Product index | PB-011 mill `next`; PB-012 cutover deferred; 1 shipped; rest idea/deferred | `product-backlog.yaml`, `harvest-pool-next.md` |
| Overlay / ops | Overlay still revert-or-promote; sqlite salvage closed; named-volume not cut over | `.dev/decision-logs/ops/soft-launch-precision-overlay.md`, `sqlite-named-volume-migration.md`, `incident-log.yaml` (FU-001–004 open, incidents closed) |
| Taste / eval | Option 1 live; option 3 not earned; harvest tap live, mill hitchhiker | `repo-gate-next.md`, `harvest-pool-next.md`, `config/source-notes/`, `eval/prefilter_v0/`, `eval/github_repo_gate_v0/` |
| Charter | M0–M8 in program; M9 gated | `.dev/bishop_program_charter.md`, `.dev/plans/m9-source-expansion/proposal.md` |
| Already-scoped | MCP notes; persist-vendor; ingest-risk seed | `mcp-agent-tool-notes.md`, `.dev/persist-vendor-payloads.md`, OPEN-023 / PB-009 |
| Live UI / data | Dashboard + harvest card recipe | `.dev/ui/`, `.dev/ui/harvest-dashboard.md`, `.dev/sqlite.md` |
| Prompt-caching | Plan complete; T12 warmup needs image rebuild | `.dev/plans/prompt-caching/runs/execution-summary.md` |

## Placement of operator bets

No new operator bets. Index items that would drop:

| Bet | Placed against | Verdict |
|---|---|---|
| Confirm harvest tap, then mill loop, then GitHub cutover | `harvest-pool-next.md`, PB-011 / PB-012 | tap is live (1413/`N_cap` 2026-09-17). Next code is the mill loop. Cutover waits on that. |
| Overlay first-week revert vs promote | `.dev/decision-logs/ops/soft-launch-precision-overlay.md` | overlay — not spec; judge after spend + inbox, do not silent-promote |
| GitHub quality / option 2–3 | `repo-gate-next.md` | option 1 live; 2 optional; 3 **not earned** |
| MCP v1 | `product-backlog.yaml` PB-010, `mcp-agent-tool-notes.md` | idea — notes exist; not this week’s build |
| Token $ on dashboard | PB-002, `.dev/persist-vendor-payloads.md` | idea — schema first; harvest card is projected $ |
| Eval-on-dashboard | PB-008 | idea |
| query-api HTTP-only | PB-007 / OPEN-007 | idea |
| Named-volume cutover | PB-006, named-volume decision log, FU-002 | deferred — operator cutover, not a coding slice |
| Ingest content risk | PB-009 / OPEN-023 | deferred |
| M9 non-paper source | charter + `.dev/plans/m9-source-expansion/proposal.md` | not earned (G7 unrecorded; Q2/Q3 open) |

## Load-bearing facts

- Incremental GitHub still POSTs `DISCOVERED`. Harvest fills the sidecar in parallel. **Tap is live** (`released_today` hit `N_cap` 2026-09-17). Cutover is gated on **PB-011 mill loop filling**, not on more dashboard work (`.dev/decision-logs/ops/harvest-pool-first-landing.md`).
- Harvest mill is a 90s hitchhiker on `scrape_cycle` then **6h** sleep (`BISHOP_SCRAPER_SCHEDULE_INTERVAL_SEC=21600`). A flat ~2k pool is not “done” and is not `N_cap` pausing harvest. Cursor was still 2024-09-21 of a 2y walk.
- Dashboard harvest is `released_today * blended_github_usd` ($2/day default). Zeros mean sidecar file missing or `query-api`/`ui` not rebuilt — not “the tap is empty.” Full `N_cap` with leftover unreleased means the tap is closed for the day (`.dev/ui/harvest-dashboard.md`).
- Soft-launch parked overlay is still not the intended machine. Option 1 pickup says do not revert it as part of GitHub shape work. Lookback 60d is overlay env, not `BACKFILL_CONFIG`.
- One gate-1 pin until an eval earns a split. Source notes are not a second profile. Do not rewind Hugging Face. Papers with Code API is dead.
- `bishop.db` has one writer (`state-worker`). Harvest ledger is `${BISHOP_DATA_ROOT}/harvest/`, not manifest.

## Sequence

**This week:**
1. **PB-011** harvest mill loop — GitHub sidecar fill independent of the 6h scrape clock. Same scraper process. Do not invent a new worker.
2. Walk `/parked` + inbox quality against the overlay note (first-week window is now; harvest tap already changed the GitHub mix). Decide later; do not revert or promote in the same sitting.
3. Hygiene that does not fight harvest: **OPEN-021 / PB-004** (M5 fixtures still seed 5/1 vs min-batch 10). ~5 minutes; still_open tackle #1.

**After PB-011 is filling:** GitHub incremental cutover (PB-012; ledger-only harvest; `DISCOVERED` is the $N tap only). Do not dump the pool. Do not start paper exhaust until this exists.

**After overlay spend + inbox are judged:** either the revert path or a promote packet that owns enum + spec + eval replay. Not a silent pin change.

**After the pool mix is visible:** mechanical drops / extra rank (`harvest-pool-next.md` deferred on purpose). Option 2 (`stars` / language) only if you still want a coarse fetch filter; it does not replace Shape 2.

**Index items already `next` (hygiene):** OPEN-021 / PB-004 → OPEN-002 / PB-003 → OPEN-003 → OPEN-022 / PB-005 / FU-002 (sqlite_live override) → OPEN-011. Named-volume (OPEN-007 / PB-006) stays operator cutover. OPEN-008 only if live `RELEVANCE_QUEUED` is stuck.

## Do not

- Start GitHub cutover, paper exhaust, or a second LLM pre-pre-filter this week (cutover is PB-012, after the mill).
- Option 3 / GitHub-only profile / second pin / `BACKFILL_CONFIG` rewrite.
- Rewind Hugging Face; treat PwC as live; HTML-scrape a PwC replacement.
- Build MCP (PB-010). Hand-scout a few Bishop hits first if you want the experiment the notes name.
- Invent UI token fields (PB-002) or a new telemetry stack. Live surface is `/dashboard` + harvest sidecar.
- M9. Charter graph/digest/reranker/Ollama/Postgres.
- Re-run the 93-card GitHub pass. Raise `stars:>50` as the slop filter.
- Query-api writes, widen `ManifestIngestEntry` for stars, commit harvest candidate rows.
- Refresh `.dev/architecture/bishop/` as if it were product work (OPEN-012, when convenient).

## Filing

| Proposed id | Title | Status |
|---|---|---|
| PB-011 | Harvest mill loop | filed `next` in `product-backlog.yaml` |
| PB-012 | GitHub harvest incremental cutover | filed `deferred` until PB-011 fills |

Harvest mill vs cutover: `.dev/decision-logs/ops/harvest-pool-first-landing.md`. Overlay stay/revert stays in the ops decision log — do not file it as a feature.
