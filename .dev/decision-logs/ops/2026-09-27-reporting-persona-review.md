# Reporting persona review — defend or dissolve

**Date:** 2026-09-27
**Scope:** Verdict on `REPORTING.md` (persona brief). Review + read-only SQL. No UI, no `stats_reader`, no schema. `REPORTING.md` not edited.
**Verdict:** (ii) keep, re-scoped. See §4.
**Evidence scripts (read-only, `mode=ro`):** `.dev/scratch/reporting-e1/e1_tuesday_cohort.py`, `e1_followups.py`, `e4_settled_yield.py`.
**DB reached:** yes. Live `bishop.db` is `C:/Users/Ale/bishop_data/sqlite_live/bishop.db` (not `sqlite/`, which is the 2026-09-11 file). Harvest sidecar `C:/Users/Ale/bishop_data/harvest/ledger.sqlite` (1.7 GB). Compose up. One sidecar read hit `attempt to write a readonly database` (WAL, scraper mid-write); retry succeeded.

Line refs are `REPORTING.md:<line>` unless noted.

## 0. Context check

**Four operator surfaces.**

- `/dashboard` (`GET /stats/overview`) is the lifetime pipeline glance: cards, a 13-stage funnel of stocks, and ingest per day against the 30-day peak.
- `/scrape` (`GET /stats/scrape`) shows incremental cursors: `scraper_state.last_successful_run_at` lag, the overlay window, and today's inserts.
- `/harvest` (`GET /stats/harvest`) is the GitHub mill plus the `$N` tap: unreleased × `$0.000764` modeled liability, the walk forecast, and the faucet against `N_cap`.
- `/today` (`GET /stats/today`) is the UTC-midnight glance of today's discovery cohort *today*.
- `/landed` is a list of indexed rows (`GET /recent`), not a rate.

**Language.**

- **Stock** is what sits in a state now.
- **Flow** is what entered a state in a window.
- **Cohort** is rows sharing a `discovered_at` window, followed forward.
- **Pass** is `relevance_decision = 1`.
- **Proceeded** is a pass that was not parked.
- **Parked** is a pass that was held (`RELEVANCE_PARKED`). It is a branch, not a success.

**Two dollars.** Blend `$` is a model: `economics.yaml` unit × count, with a *guessed* paid-path rate baked in. Anthropic `$` is a bill: `message.usage` × price, which is not persisted (PB-002). On one card, the difference between them reads as savings or overrun. It is really model error. The 2026-09-27 burst already shows this: modeled `$10.80` vs billed about `$5.11` (`.dev/ui/harvest-dashboard.md:20`).

## 1. Persona, first person

I'm the reporting hat. I don't own a page, and I'm not here to make the dashboard look instrumented.

I'm good at one thing. I take a question like "how's GitHub doing" and refuse to answer it until it has four parts: a population, a window, a success event, and a grain. Then I write the denominator in the same clause as the number. "3% pass" means nothing to me until I know of what, since when, which source, and where parked went (`REPORTING.md:29`, `:33`).

I'm bad at this repo's kind of UI work. Given a landing page, I'll fill it with KPI strips and exception sentences. That happened on 2026-09-27 and the operator removed it (`:17`, `:31`). I'll also blend the modeled mill dollar with the Anthropic bill if nobody stops me.

I report to the operator. Here that is the same person who writes the adapters and reads the corpus (`:27`). There is no exec above him.

Three surfaces I never touch:

1. `/dashboard` (no cards, no one-liners)
2. `/today`, which is the UTC-day ops glance, not my cohort page (`:209`)
3. `/harvest`'s modeled-`$` hero, which I read and never copy (`:113`)

I also stay out of `style.css`, eval gold, and PB-013's attention pass.

My first deliverable is a written definition plus a read-only SQL slice, not HTML (`:134`).

## 2. Adversarial pass

### 2a. Operator lens — is this real work or agent busywork?

**A1. The hat table has seven hats and one human.** `:27` admits that the audience, the engineer, and the consumer are one person. `:41–49` then lists seven hats, and `:184` schedules "brainstorming sessions (operator + this hat)". On a single-operator host, a session with a persona is the operator paying for an agent to interview him. *Needed:* the hat has to hand the operator a finding he could not get from the pages, not a session request. *For this not to matter:* each unit of hat output ends in a named owner doc (backlog item, source note, decision log) that changes a decision. §3 tests this, and it holds three times.

**A2. The brief is written mostly as prohibitions.** Positive job: `:64–70` (7 bullets). Prohibitions: `:76–83` (8), `:204–210` (7), and `:3` ("Not earned"). It was born from an incident (`:17`). A brief written mainly as fences is a way to stop the last mistake, not a job. *Missing:* a forcing function. Nothing in the doc says who consumes a finding, or by when.

**A3. "Research queue, not a build sequence" (`:158`), plus a blocker (`:186`), plus "no page" (`:134`), plus a status of "Not earned" (`:3`).** Together these make a role that can never be late. That is the failure mode the prompt names. It is only half true, though. The E-runs (`:171–176`) need none of those gates and ran in under an hour here. The escape hatch is the brainstorm gate, not the experiments.

**A4. "Do not collapse this hat into PB-008, PB-010, PB-013, or M9" (`:210`) is a category error.** Those are backlog items, not hats. The real merge candidates are the *hats* at `:43` (pipeline operator) and `:45` (eval/calibration), and the doc never argues against merging into them. It only says "sibling" (`:45`).

**Operator-lens bottom line:** as a *persona with surfaces*, it is decorative. As a *discipline that runs cohort SQL and routes the verdict to an owner*, it produced the most decision-relevant numbers of the day (§3). Keep the discipline and cut the persona apparatus.

### 2b. Rigor lens

**R1. Time-to-INDEXED (`:96`, `:165`) is hand-waved, but a fix exists without a schema change.**
- `ingested_at` is set when the `entries` row is created at scrape (`.dev/sqlite.md:45`). So `ingested_at − discovered_at` measures **time-to-scrape**, not time-to-INDEXED.
- For the 2026-09-15 cohort that proxy says 0.26 h (median, GitHub). The better proxy says 2.46 h.
- "batch `completed_at`" (`:96`) does not say *which* batch. A pre-filter batch, a Call 1 batch, and a Call 2 batch each give a different answer.
- *Well-defined replacement:* `batches.completed_at` joined through `entries.enrichment_stage2_batch_id`. This is a lower bound on INDEXED time, because the vector write comes after. It also answers as-of questions without `indexed_at`: "INDEXED by Friday" ≈ `processing_state='INDEXED' AND stage2.completed_at <= Friday`.
- Known lies: a re-run of Call 2 overwrites the batch id, and pre-`m3` rows may lack it (0 missing in the 09-15 cohort).
- *For this not to matter:* cohorts settle within hours. They do (§3: max 17.4 h). The "of Tuesday's arXiv… by Friday" framing (`:67`) is almost degenerate. Unless there is an outage, the answer is known the same day.

**R2. The cohort clock confounds Bishop's uptime with the world (`:65`, `:142`).** `discovered_at` is ingestion wall-clock.
- Tuesday 2026-09-22 has **zero** rows. The host was down 22–25 Sep (caba trip).
- arXiv has 308 rows over 11–21 Sep, then **16,719** on 27 Sep (export-stuck catch-up, `.dev/decision-logs/ops/2026-09-27-arxiv-export-stuck.md`).
- `:29` says the hat refuses census when the question is "this week's arXiv". But "this week's arXiv" is a *publication-week* population (`published_at`, which exists), and the doc's only named clock is discovery.
- *Missing:* two clocks. Discovery measures pipeline latency. Publication measures "what came out this week".
- *For this not to matter:* scrape has no outages or catch-ups. That is false this month.

**R3. E3 (`:173`) looks as if it needs a promote timestamp. It needs one only for timing, not for counts.**
- `promote_parked` flips `RELEVANCE_PARKED → RELEVANCE_PASSED` and only *logs* the event (`services/state-worker/app/transitions.py:1510–1540`). No promote time is persisted.
- But `manifest.pre_filter_tier` (`peripheral` = parked at decision, `core` = proceeded) survives the flip. So *promoted* = `tier='peripheral' AND processing_state != 'RELEVANCE_PARKED'` is countable today. **Lifetime value: 0 promoted of 968 peripheral.**
- Promote *latency* would need an event column, which is a schema change and is out of scope.
- *Also wrong:* `:143` defines proceeded by current state, so a promoted row would silently migrate from parked to proceeded. Define both by tier (decision-time), not by state.
- *For this not to matter:* promotes stay at ~0. So far they have.

**R4. E5 (`:175`) is answerable with current ledger columns. No schema change is needed.**
- Unreleased at the end of day D = `count(first_seen_at <= D) − count(released_at <= D)`.
- Reconstructed from `2026-09-13` forward, this gives **305,983**, which equals the live `released_at IS NULL` count exactly.
- Mill upserts per day are in `harvest_runs.items_upserted`.
- The only thing the ledger cannot give is *re-seen* rows per day, because `last_seen_at` is overwritten. E5 does not need them.
- *For this not to matter:* nothing. It already doesn't.

**R5. "One gate-1 pin" (`:58`) versus a per-source breakdown.**
- There is no conflict in *reading*. A per-source breakdown of one gate's output is reporting, not routing.
- The seam is what the numbers *invite*. §3 shows:
  - Lesswrong: 73 passes, 73 parked, 0 INDEXED.
  - Hugging Face: 44% of discovered, 3.7% of INDEXED.
  - The GitHub tap passes at a seventh of incremental's rate.
- Each of those tempts a per-source threshold, which is option 3 (not earned, per the source-notes rule). `:189` says live yield is not gold, but the doc gives the hat no route for the evidence.
- *Missing:* the rule that per-source findings go to `config/source-notes/<source>.md` as dated intel and to eval as a labeling request. They never go to a pin proposal.
- *For this not to matter:* the hat never recommends thresholds. Write that down.

**R6. "Reporting cannot start until [good week] is picked" (`:186`) is an escape hatch.** It contradicts `:171–176`: none of E1–E6 needs a "good week" score. Each has its own `{population, window, success, grain}`. The gate is real for exactly one thing, a *headline* on a page. `:134` already says there is no page. *Fix:* scope `:186` to "before any page", and drop it from "before reporting".

**R7. PB-008 seam (eval), stated concretely.**
- `:103` puts "soft-launch pin vs frozen gold" under **Cohorts**, while `:81` and `:180` say eval is not merged. That row is PB-008's replay. It is not a cohort question and should be cut from this hat.
- `:109` (steal bar vs topic match) says "needs labels". Also eval.
- The real seam is the *sample*. Eval needs a labeled slice, and this hat is the only one that knows which live slice is anomalous. For example: the tap's 2026-09-17/18 releases, 2,826 rows with 4 passes and 0 proceeded.
- *Handoff contract:* reporting names the slice (source_ids + reason). Eval freezes and labels it. Reporting never computes precision.

**R8. PB-013 seam (attention), stated concretely.**
- `:188` "Parked as a product" and PB-013's "parked overlay rows are a separate cheap promote-vs-leave pass" (`product-backlog.yaml:61–62`) are **the same population**: `pre_filter_tier='peripheral'`, 968 rows.
- The seam is that reporting's E3 is PB-013's *input*. 75% of passes park and 0 ever promote, so `/parked` is a write-only bin today. The hat does not design the pass. It hands PB-013 the size and the promote rate.
- `:120` ("must-look is PB-013") is about INDEXED. It misses that the bigger overlap is on *parked*.

**R9. False premise in Cost (`:115`): "Call-1 spend on parked that never promote".** Parked rows have **no** `entries` row and **no** Call 1 batch (968 peripheral → 0 entries, 0 `enrichment_stage1_batch_id`). Their only cost is gate-1. The waste line should read "gate-1 spend on rows that park and never promote."

**R10. Tautological metric (`:113`): "`$` per tap-released GitHub row".** In the modeled series this is always `$0.000764` by construction, because it is the input parameter. The informative modeled number is `$` per tap-released row that reached INDEXED.

**R11. Falsified prediction (`:174`): "GitHub tap the opposite [high yield]".** Observed on tap days: tap pass rate 0.26% vs incremental 1.83% (§3, E2). The "~0.7% on the 2024 slice" at `:115` and `:174` comes from a different slice. The 2026 recency tap is lower.

**R12. The conversion row (`:93`) is not a partition.** It lists "DISCOVERED / gate-1 no / parked / proceeded / scraped / INDEXED / failed", but proceeded ⊃ scraped ⊃ INDEXED. *Use:* undecided / rejected / parked / proceeded-in-flight / INDEXED / failed-or-escalated. These are exclusive and sum to discovered.

## 3. E1 — the actual answer (and what fell out)

All numbers were read 2026-09-27 ~16:40 UTC, `mode=ro`. They are frozen here. Do not re-probe to "confirm", because live rows move (peripheral went 957 → 968 during this session). Definitions:

- tier-based: proceeded = `pre_filter_tier='core'`, parked = `'peripheral'`
- INDEXED = currently INDEXED ("already through", the lie from `:165`)
- Clock = `discovered_at` UTC

### E1 — Tuesday cohort

**The most recent Tuesday, 2026-09-22, is empty (0 rows) because of the host outage from 22 to 25 Sep.** That is the first answer. Picking a "frozen week" (`:163`) means checking uptime first.

**Tuesday 2026-09-15** (12 days old, fully settled: 0 undecided, 0 in flight):

| source | discovered | rejected | pass | parked | proceeded | INDEXED |
|---|---:|---:|---:|---:|---:|---:|
| github | 2,156 | 2,017 | 139 | 107 | 32 | 32 |
| huggingface | 1,721 | 1,710 | 11 | 11 | 0 | 0 |
| semantic_scholar | 125 | 117 | 8 | 7 | 1 | 1 |
| arxiv | 108 | 59 | 49 | 30 | 19 | 19 |
| lesswrong | 22 | 7 | 15 | 15 | 0 | 0 |
| openreview | 3 | 3 | 0 | 0 | 0 | 0 |
| **all** | **4,135** | **3,913** | **222** | **170** | **52** | **52** |

- Of 4,135 rows discovered 2026-09-15 UTC, **5.4%** passed gate-1, **1.3%** are INDEXED, and **77% of passes parked**.
- Proceeded → INDEXED is 52/52. Once a row proceeds, the pipe does not lose it.
- Mix: Hugging Face is 42% of the day's discoveries and 0% of its INDEXED. arXiv is 2.6% of discoveries and 37% of INDEXED.
- Time, discovered → Call 2 batch `completed_at` (the R1 proxy):
  - GitHub: median 2.5 h, max 17.4 h
  - arXiv: median 0.95 h
  - The `ingested_at` proxy would have said 0.26 h (GitHub median). That is time-to-scrape, and it is wrong for this question.
- Versus `/today`: that day's glance is gone. `/today` could only ever show this cohort mid-flight. Following it forward shows the pipe fully settled it within a day, with parking as the dominant exit after rejection.

### Settled window 2026-09-11 → 2026-09-21 (11 UTC days, before the outage)

| source | discovered | pass | parked | proceeded | INDEXED | promoted |
|---|---:|---:|---:|---:|---:|---:|
| github | 15,907 | 504 | 350 | 154 | 145 | 0 |
| huggingface | 13,200 | 87 | 80 | 7 | 7 | 0 |
| semantic_scholar | 321 | 18 | 17 | 1 | 1 | 0 |
| lesswrong | 313 | 73 | 73 | 0 | 0 | 0 |
| arxiv | 308 | 117 | 81 | 36 | 36 | 0 |
| **all** | **30,052** | **799** | **601** | **198** | **189** | **0** |

- Parked is **75%** of passes. Lifetime promoted is **0 of 968**.
- Lesswrong has never produced an INDEXED row in this window. All 73 of its passes parked.
- Hugging Face is 44% of discoveries and 3.7% of INDEXED.
- arXiv is under-counted by the stuck export (R2).

### E2 — the GitHub tap vs incremental (the finding that matters)

Tap = `source_id` in ledger `released_at` that UTC day.

| day | tap released | tap pass | tap INDEXED | incremental | incr pass | incr INDEXED |
|---|---:|---:|---:|---:|---:|---:|
| 2026-09-17 | 1,413 | 3 | 0 | 650 | 12 | 5 |
| 2026-09-18 | 1,413 | 1 | 0 | 651 | 10 | 4 |
| 2026-09-26 | 2,150 | 9 | 2 | 608 | 13 | 5 |
| **sum** | **4,976** | **13 (0.26%)** | **2 (0.04%)** | **1,909** | **35 (1.83%)** | **14 (0.73%)** |

- For every 1,000 GitHub rows, the tap yields about 0.4 INDEXED and incremental yields about 7.3. That is roughly **18×**.
- Modeled cost (blend `$`, labeled): 4,976 × `$0.000764` = `$3.80` modeled for 2 tap INDEXED, or **`$1.90` modeled per tap INDEXED**.
- The blend's own `github_paid_path_rate` is **0.022** (`config/harvest/economics.yaml:12`). Observed tap proceeded rate is 2/4,976 = **0.04%**. The model assumes about 50× more Call 1/2 than happens, so the modeled unit overstates the tap. This compares a parameter with an observed rate. It is not a comparison of dollars, and the bill stays out of it.
- *Likely cause (unverified):* a population difference between harvest `stars:>10` pushed-window selection and the incremental query. This is not a gate change, and the pin is not implicated (R5).
- *Why it's load-bearing:* PB-012 (`product-backlog.yaml:44–45`) plans to "stop POSTing GitHub fetch_manifest into DISCOVERED; DISCOVERED is the `$N` tap only". On this evidence, cutover replaces the higher-yield GitHub path with the lower one. That is a question for PB-012's owner. Reporting does not decide it.

### E5 — drain honesty

Unreleased pool at the end of each UTC day, reconstructed from ledger timestamps (R4):

| day | mill adds (new `first_seen_at`) | released | unreleased EOD |
|---|---:|---:|---:|
| 09-17 | 3,546 | 1,413 | 2,133 |
| 09-18 | 7,244 | 1,413 | 7,964 |
| 09-19 | 7,463 | 1,413 | 14,014 |
| 09-20 | 7,157 | 1,413 | 19,758 |
| 09-21 | 3,430 | 1,413 | 21,775 |
| 09-26 | 4,300 | 2,150 | 23,925 |
| 09-27 (partial) | 296,244 | 14,186 | 305,983 |

- Adds exceeded releases on **every** observed day. `/harvest` days-to-drain today would be `ceil(305,983 / 4,712)` = **65 days**. That number assumes zero further adds, which has never happened.
- `harvest_runs` on 09-27: **677 of 677 windows `incomplete_results`** (Search cap). The walk forecast is censored on every window and will stay "waiting" at this granularity.
- This goes in a scratch note, per `:175`. It is not a card.

### Not run

- E4 is covered by the settled-window table.
- E6 is blocked on PB-002. `batches` has no usage columns (confirmed column list).

## 4. Defend or dissolve

### 4.1 Justification

The case for a distinct hat is not "someone should own analytics". The case is that **no other hat's clock produces these numbers**:

- The pipeline operator reads *stocks now* (`/dashboard`, `/today`). The tap-vs-incremental gap is invisible on every page. `/scrape` shows GitHub `discovered_today` with `released_today` beside it (`.dev/ui/scrape.md:7`), but no pass or INDEXED rate per path.
- Eval/calibration reads *gold*. It measures whether the gate is right on a frozen slice. It cannot see that the tap feeds the gate a population that gate-1 correctly rejects at 99.7%.
- Harvest economics reads *the model*. Its paid-path parameter (0.022) is off from observation by ~50×, and nothing in its loop compares them.

The value is the **follow-forward join**: manifest × tier × entries × batches × ledger over a fixed window. Nothing else in the org runs it. If that join is merged into the operator hat, the 2026-09-27 dashboard incident (`:17`) comes back, because the operator hat's instinct is to put numbers on a now-page. If it is merged into eval, live yield gets treated as a quality signal (`:189`).

What does *not* survive as justification: the surfaces table (`:128–132`), the chart contract (`:147–152`), the brainstorm sessions (`:184–190`), and the "Later" page plan (`:194–198`). None of those is needed for this week's value.

### 4.2 Immediate value (this week, zero schema, zero pages)

Already produced, in §3:

1. **E2:** the GitHub tap yields ~0.04% INDEXED vs incremental ~0.73%. Input to PB-012 before cutover.
2. **E3:** 75% of passes park and 0 of 968 ever promoted. Input to PB-013's parked pass and to the soft-launch overlay decision log.
3. **E5:** the pool grew on every observed day, and days-to-drain assumes no adds. Input to `harvest-dashboard.md` and `harvest-pool-next.md`.
4. **E1 definitions:** a tier-based proceeded/parked/promoted partition (R3, R12) and the Call 2 `completed_at` INDEXED clock (R1), so no later agent invents `indexed_at` or `promoted_at`.

Queries: `.dev/scratch/reporting-e1/*.py`.

### 4.3 Long-term value (what compounds)

- **After PB-002:** `$`-billed per INDEXED by source and by path (tap vs incremental). This is the only way to learn whether the tap's ~`$1.90` modeled per INDEXED is real, and it re-prices `github_paid_path_rate` from observation instead of a guess.
  - *Ask to PB-002, from this hat only:* persist usage **per result** (per `source_id`/`custom_id`), not only as `batches` aggregates. Batch-level columns would force an allocation rule across `batches.source_ids`, which mixes sources inside one pre-filter batch. That rule would be a fiction on a card.
- **After a labeled slice exists:** live yield × gold precision gives an *estimated true-relevant INDEXED per $* by source. Eval alone has precision without volume, and reporting alone has volume without truth. This is the only place in the org where the two multiply, and it is the evidence `:189` says a pin bump needs.
- **Anomaly-slice nomination to eval (R7).** Each cohort run can name the one live slice most worth labeling. For this week, that is the 2026-09-17/18 tap releases.

### 4.4 Self-verdict: **(ii) keep, re-scoped**

**Kept:**

- the `{population, window, success, grain}` law (`:89`)
- the language block (`:140–145`), amended by R3, R12, and R2's second clock
- E1–E6 as scratch SQL, each ending in a verdict routed to an owner doc (§5)

**Cut:**

1. **Surfaces and page plan** (`:124–134`, `:192–198`). Reopen only when the *same* question has been asked in three separate runs. A page answers a recurring question, and none recurs yet.
2. **Brainstorm sessions as a gate** (`:182–190`). Keep session 3 (parked) and session 2 (source strategy) as *questions*. The E-runs have already answered their inputs. Drop "reporting cannot start until" (R6).
3. **`:103` and `:109`** (gold vs pin, steal bar). These are eval's (R7).
4. **Chart design contract** (`:69`, `:147–152`). There is no chart without a page. It moves to `.dev/ui/design.md` when a page is earned.
5. **False and tautological lines** `:113` (`$`/tap row), `:115` (Call-1 on parked), and `:174` (tap high-yield prediction). See R9, R10, and R11.

**Added (the forcing function the brief lacks):** every run ends in a routed verdict with a named owner doc, or it is not done. At most one run per week, no standing sessions, and the operator's cost is reading one decision log.

**Ranking by EV vs operator time** (one operator, no exec audience):

1. **(ii) Re-scope.** It had the highest EV this sitting: three decision-changing findings (E2 → PB-012, E3 → PB-013, E5 → harvest). It costs the operator about one read per run.
2. **(iii) Merge into the pipeline operator hat.** It keeps most of the SQL value at the lowest ceremony. It loses the fence that stopped the 2026-09-27 dashboard densification (`:17`), and cohort numbers drift onto now-pages. Merging into eval instead would be worse, because it would conflate live yield with gold (`:189`).
3. **(i) Keep as-is.** It keeps the value but also keeps the escape hatch (`:186`), the page ambitions, and three wrong premises. Operator time goes to sessions (`:184`) instead of findings.
4. **(iv) Kill.** It is cheapest in words and most expensive in outcome. The tap-yield gap would have gone into PB-012 unseen. REPORTING.md *as written* is close to the failure mode the prompt names (A2, A3), but the discipline inside it is not.

## 5. Routing (where each finding goes)

This log does not edit these. The owner of each doc decides.

| finding | owner doc | ask |
|---|---|---|
| E2 tap vs incremental yield | `harvest-pool-next.md`, PB-012 | Gate cutover on a tap-yield check; investigate the selection-population difference |
| `github_paid_path_rate` 0.022 vs observed ~0.0004 on tap | `config/harvest/economics.yaml` | Recalibrate by commit (the file's own rule), or split the paid-path rate per path. Not at runtime |
| E5 pool grows every day; forecast 677/677 censored | `.dev/ui/harvest-dashboard.md` | Days-to-drain label should say "if the mill stopped now" |
| E3 0 promotes / 75% parked | PB-013, `.dev/decision-logs/ops/soft-launch-precision-overlay.md` | Parked is a write-only bin today; size the parked pass at ~968 |
| Lesswrong 73/73 parked, HF 0.05% INDEXED | `config/source-notes/lesswrong.md`, `huggingface.md` | Append dated intel. No pin change (R5) |
| Tap 2026-09-17/18 slice | eval (PB-008) | Candidate labeled slice. Reporting does not compute precision |
| Per-result usage | PB-002 | Persist per `source_id`, not only `batches` aggregates |
| R1/R3/R12 definitions, R2 two clocks, R6/R9/R10/R11 corrections | `REPORTING.md` owner | Re-scope per §4.4. This log is the verdict, not the edit |
