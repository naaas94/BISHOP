# Current state

**As of:** 2026-09-27, after the owner-doc filing that followed run r001.
**Charter:** `README.md`. **Registry:** `findings.yaml`. **Frozen numbers:** `runs/2026-09-27-r001.md`.
When this file and the registry disagree on a status, the registry wins. When this file and a run disagree on a number, the run wins.

## What the function is

Bishop's pages answer whether the pipe is moving now. This function answers what happened to a fixed set of rows, followed forward, with a denominator, then routes that rate to the document that already owns the decision.

It is one hat for one operator: this folder, five read-only queries, and a findings registry. The operator runs a script and reads one run file. There is no analyst team, no scheduler, and no metrics store.

`REPORTING.md` was the first draft of a broader persona. The review (`.dev/decision-logs/ops/2026-09-27-reporting-persona-review.md`, verdict **keep, re-scoped**) kept the cohort discipline and cut the page plan, the chart contract, the brainstorm gate, and the eval rows. `corrections.md` is the errata for that brief.

## What the 2026-09-27 session did

Run r001 had already been written the same day. This session did not open the databases and did not decide a cutoff, a pin, or a rate.

The operator asked what the registry translated to in actions. Owner docs were checked against the 2026-09-27 status notes. Nothing had picked the findings up. No queued run was due: r001 is this week's run, PB-012 was still deferred, no uptime-clean week existed yet, and the pool window starts after 2026-09-28. The operator chose to file the four asks whose owners could record them now.

| Finding | What was written | Status after |
|---------|------------------|--------------|
| F-001 | Tap-yield gate in `harvest-pool-next.md` Deferred and in PB-012 (`product-backlog.yaml`, `updated` 2026-09-27). Cutover stays deferred until Q-001: 5+ settled, uptime-clean tap days under `N_cap` 4712. r001 figures cited: tap INDEXED 2/4,976 (0.04%) vs incremental 14/1,909 (0.73%) on 2026-09-17, 09-18, 09-26. | `routed`. Selection investigation and Q-001 have not run. |
| F-003 | Days-to-drain called the stopped-mill figure in `harvest-pool-next.md` Operator pages and in `.dev/ui/harvest-dashboard.md`. The page already said "if the mill adds nothing" (`services/ui/app/templates/partials/harvest_stats.html`). Template was left as it was. Walk forecast stays "waiting" until 3 complete Search windows exist (r001: 677/677 `harvest_runs` on 2026-09-27 were `incomplete_results`). | `acted` |
| F-005 | Dated intel in `config/source-notes/lesswrong.md` (73 passes, 73 parked, 0 INDEXED) and `config/source-notes/huggingface.md` (13,200/30,052 discoveries, 7/189 INDEXED). Window: discovered 2026-09-11..09-21 UTC. Same pin. | `acted` |
| F-007 | Per-result usage constraint on PB-002 and on the Anthropic row in `.dev/persist-vendor-payloads.md`. `batches.source_ids` mixes sources inside one pre-filter batch, so a batch total cannot be split by source without an allocation rule. | `routed`. PB-002 still `idea`. Columns are not built. |

Left with their owners, untouched this session:

- F-002 — `config/harvest/economics.yaml` `github_paid_path_rate` still 0.022. Recalibrate only in a commit that owns that file.
- F-004 — parked is 75% of passes in the settled window; lifetime promoted is 0 of 968. PB-013 and the soft-launch overlay log do not cite it. Size the promote-vs-leave pass when PB-013 is picked up.
- F-006 — tap releases of 2026-09-17/18 nominated for eval to freeze and label. PB-008 has not taken it.
- F-008 — already `acted` before this session (`corrections.md`, banner on `REPORTING.md`).

## What it is doing now

Waiting. README rule 3: at most one run a week, and a run happens when a decision is about to be made or a queued blocker clears. r001 is the run for this week.

## Mid-term

Same job, next windows. Named in `findings.yaml` → `queued`. Not a build-out.

| ID | When it becomes a run | Blocked on |
|----|----------------------|------------|
| Q-001 | Before PB-012 leaves deferred. Tap vs incremental under `N_cap` 4712, first 5+ settled uptime-clean tap days after 2026-09-27. | Nothing in the registry. The trigger is the cutover moving, and those days do not exist yet. |
| Q-002 | Next weekly cohort, arXiv also on `published_at`. The 09-11..09-21 window under-counted arXiv (stuck export). | An uptime-clean week existing. |
| Q-003 | Pool adds vs releases for 7 UTC days after 2026-09-28, at `N_cap` 4712. F-003 was the 1413/2150 regime plus a burst day. | The window elapsing. |
| Q-004 | Billed `$` per proceeded and per INDEXED, by source and path. Two series forever: modeled and billed. | PB-002, per-result usage (F-007). |
| Q-005 | Live yield times gold precision, estimated true-relevant INDEXED per `$`. | PB-008 freezing a slice (F-006) and PB-002. |

Three questions sit in `findings.yaml` → `open_questions`. Runs feed them. This function does not close them.

- OQ-1 — spend harvest `$` on the GitHub mill, or let arXiv fill `DISCOVERED`? Decided in `harvest-pool-next.md` / PB-012.
- OQ-2 — parked rows: waste, a second look, or a taste buffer? Decided in PB-013.
- OQ-3 — what is a good week? Needed only before a page headline. Decided by the operator if a page is earned (README rule 8).

## Long-term, as the charter has it

More runs of this same kind. A page only after three runs have asked the same question; this function would write the definition, and `.dev/ui/` would build the page. No warehouse of saved results, no run scheduler, no Cursor rule until an agent ignores the folder once.

Column holes stay asks. There is no `indexed_at`. Promote count is exact from `pre_filter_tier`; promote latency is not. Billed `$` per source waits on per-result usage. The proxies and their lies are in `glossary.md`.

## Production insights org — operator question, 2026-09-27

After the filing, the operator said the picture they had was a production insights manager: a lead whose tools are a data analyst, a data scientist, an ML engineer, and a data engineer, covering data infrastructure, reporting, insight gathering, experiments and A/B tests, recommendations, and the data-driven decision.

That org is a different system from this folder. It is not the plan here. Logged so a later session does not treat it as unfinished work inside this hat.

Where those jobs live in Bishop today:

| Piece of that org | Where it lives |
|-------------------|----------------|
| Data infrastructure, pipelines, schema | Scraper, state-worker, harvest sidecar. This hat reads `mode=ro`. |
| Reporting surfaces | Operator UI (`.dev/ui/`): `/dashboard`, `/scrape`, `/harvest`, `/today`. This hat does not author pages. |
| Insight gathering | This hat. Population, window, success, grain. A rate with a denominator. |
| Recommendations | The `ask` on a finding. The owner document decides. |
| Data-driven decisions | `harvest-pool-next.md`, PB-012, `economics.yaml`, source notes, PB-013, eval. |
| Experiments / A/B | No experiment platform. E1–E6 are names of cohort questions on live history. |
| ML, precision, labels | Eval (PB-008). This hat nominates a slice (`source_id`s and a reason). |
| Data engineering | Alembic and state-worker domain models. This hat writes the proxy and routes the column ask. |
| Analyst, scientist, ML engineer, data engineer as subagents | Not built. The queries are scripts under `queries/`. |

The review cut the broader persona because that draft was already reaching for pages and for eval, and that work belongs to other hats. Building the production org would be a new design, started on purpose, not a completion of `README.md`.
