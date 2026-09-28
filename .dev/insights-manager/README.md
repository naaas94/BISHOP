# Insights Manager

**Status:** standing function, founded 2026-09-27. Not a page, not a route, not a backlog item.
**Serves:** the operator (singular — same person who writes the adapters and reads the corpus).
**Founding evidence:** `.dev/decision-logs/ops/2026-09-27-reporting-persona-review.md` (verdict **(ii) keep, re-scoped**).
**Supersedes as a location:** `REPORTING.md` (persona brief). Its doctrine is carried here, corrected — see `corrections.md`.

## What this is for

Bishop's pages answer **"is the pipe moving now"**. They read stocks on a now-clock. Nobody else in the org answers **"what happened to a fixed set of rows, followed forward"**.

That job is the *follow-forward join*: manifest × `pre_filter_tier` × entries × batches × harvest ledger, over a frozen window, with a denominator. The first run (2026-09-27) found three things no page could show:

- The GitHub `$N` tap yields about 18× fewer INDEXED per row than incremental GitHub. That lands one week before PB-012 plans to make the tap the only GitHub path.
- 75% of passes park, and 0 of 968 parked rows have ever been promoted.
- The harvest pool grew on every observed day, but `/harvest` days-to-drain assumes it won't.

Each finding changed or questioned a decision owned by *another* doc. That is the whole job: **name the population, compute the rate, route the verdict to its owner**.

## What it must never become

- **A page author.** Never touch `/dashboard`, `/today`, `/scrape`, `/harvest`, `/landed`, or anything under `services/ui/`. No `stats_reader.py` or `Stats*` changes. The 2026-09-27 dashboard densification came from this hat's instinct. The fence is the reason this is a separate function and not merged into the pipeline-operator hat.
- **A decider.** It never bumps the pin, edits `config/harvest/economics.yaml`, or decides PB-012. It writes a finding and an ask. The owner doc decides.
- **A second gate.** Per-source numbers are reporting, not routing. A per-source finding goes to `config/source-notes/<source>.md` as dated intel, and to eval as a labeling request. It never becomes a per-source threshold proposal (option 3 is not earned).
- **Eval.** It never computes precision or recall, and never treats live yield as gold. It *nominates* anomalous live slices for eval (PB-008) to freeze and label.
- **An attention pass.** PB-013 (must-look, digest, parked promote-vs-leave) consumes this function's sizing. It is not designed here.
- **A schema author.** No Alembic revision, no columns, no `processing_state` past `INDEXED`. When a question needs a column that doesn't exist (`indexed_at`, `promoted_at`, per-result usage), write the proxy and its lie down in `glossary.md`, and route the column ask to its owner.
- **A meeting.** No brainstorm sessions as a gate. The operator's cost per run is reading one run file.

## Why re-scope, not kill

Killing it is cheapest in words and most expensive in outcome. Without the E2 run, the tap-yield gap would have gone into the PB-012 cutover unseen. Keeping `REPORTING.md` as-is keeps its escape hatch ("reporting cannot start until a good week is picked"), its page ambitions, and three false premises (see `corrections.md`: R9, R10, R11). The review kept the **discipline** and cut the **persona apparatus**:

- The surfaces table and page plan are cut, and so is the chart contract (that belongs to `.dev/ui/design.md` if a page is ever earned).
- The brainstorm gate and the eval rows are cut.
- **Added:** the forcing function the brief never had (below).

## Rules of the function

1. **Every question has `{population, window, success, grain}`.** If a slot is missing, it is not a question yet. Terms are in `glossary.md`. Use them exactly.
2. **Every run ends in a routed verdict, or it is not done.** A run file lists each finding with an owner doc and an ask. "Interesting, no owner" goes in the run file as *noted*, not in the registry.
3. **At most one run per week.** No standing cadence is promised; a run happens when a decision is about to be made (e.g., before PB-012 moves) or a queued item's blocker clears.
4. **Numbers are frozen at run time.** Write the UTC read time and the DB paths. Do not re-probe old numbers to "confirm". Live rows move; a new read is a new run.
5. **Check uptime before picking a window.** The discovery clock records Bishop's uptime, not the world. 2026-09-22 has zero rows because the host was down. Pick settled, uptime-clean windows, or say why not.
6. **Read-only, always.** `mode=ro` on `bishop.db` and on the harvest sidecar. Never from `services/ui`. Never write either file.
7. **Two dollars, never one card.** Blend `$` (modeled, `economics.yaml`) and Anthropic `$` (billed, PB-002) are different series. Label which one. Compare a model *parameter* to an *observed rate*, not dollars to dollars.
8. **A page is earned only after three runs have asked the same question.** Until then, the answer lives in a run file. When it is earned, the page goes through `.dev/ui/` the normal way; this function writes the definition, not the HTML.

## Files

| File | What it holds |
|------|---------------|
| `README.md` | This charter: why, never-list, rules, founding gap. |
| `current_state.md` | Dated snapshot of where the work stands. The 2026-09-27 entry includes the operator question about a production insights org. |
| `glossary.md` | Stock / flow / cohort / pass / proceeded / parked / promoted, two clocks, two dollars, the INDEXED-in-cohort proxy and its lie. |
| `corrections.md` | Errata for `REPORTING.md` (R1–R12). Read before trusting any line of the brief. |
| `findings.yaml` | Registry: one row per routed finding (status `routed` / `acted` / `stale` / `dropped`), plus `queued` next runs with their blockers. |
| `queries/` | Promoted, parameterized read-only probes. One question per file. `queries/README.md` has the index. |
| `runs/` | One file per run. Frozen numbers, windows, findings emitted. `runs/_template.md` is the shape. |

Scratch that seeded this folder stays at `.dev/scratch/reporting-e1/`. It is provenance for run 001, not the reuse path.

## Founding state (2026-09-27) and what closed each gap

| Before | Gap | Closed by |
|--------|-----|-----------|
| `REPORTING.md`: a persona brief mostly written as prohibitions | No forcing function; the role could never be late | Rules 2–3 above |
| One review run, three decision-changing findings, routed in the review's §5 | Routing lived in one decision log's table. Nothing tracked pickup or staleness | `findings.yaml` |
| `.dev/scratch/reporting-e1/*.py`: hard-coded days, one-off | No versioning or reuse; a later agent would rewrite the joins, and the tier/promote logic with them | `queries/` |
| Cadence was one sentence in a decision log | Not enforced anywhere an agent would look | Rules 3–4 above |
| R1–R12 corrections lived only in the review | A future agent reads `REPORTING.md` and repeats R9 to R11 | `corrections.md` + a banner on `REPORTING.md` |
| The language block defined parked/proceeded by state, on one clock | Promoted rows migrate silently; publication-week questions answered on the discovery clock | `glossary.md` (tier-based, two clocks) |

## Deliberately not built

- **A Cursor rule.** `AGENTS.md` points here, and that is enough until an agent ignores the folder once. Then add `.cursor/rules/bishop-insights.mdc`, not before.
- **A run scheduler or automation.** A cadence ceiling ("at most one per week"), not a floor. Automating it would produce runs without a decision to feed.
- **Any `GET /stats/*` or page.** Rule 8.
- **A metrics store / saved results.** Run files hold frozen numbers as prose tables. A results DB is a warehouse by another name.

## How to run one

1. Read `findings.yaml` → `queued`. Pick the item whose blocker has cleared, or the decision that is about to be made.
2. Write the question in `{population, window, success, grain}` in a new `runs/<date>-r<NNN>.md` from `_template.md`.
3. Run the matching `queries/*.py` (or add one: one question per file, with a docstring that has the four slots).
4. Freeze the numbers, write the findings, and route each one. Add rows to `findings.yaml`, and update the status of any older row this run touched.
5. Do not edit the owner docs. The run file and the registry are the whole output.
