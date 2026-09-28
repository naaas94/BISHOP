# Phase 1 raw notes — independent Jev calibration / accuracy measurements and reviews

Slice: independent measurements and reviews only. No verdicts.

---

## Source 1 — TrueStandard

**Locator:** https://truestandard.ai/blog/jev-accuracy-tested  
**Title:** "Jev's Accuracy, Measured on 108 Claims"  
**Author:** Arun Agrahri (byline)  
**Date:** September 18, 2026  
**Retrieved:** 2026-09-27 (WebFetch)

### Called Jev API?

**Yes.** Post describes a full run: "One run per model, 18 claims in each of six domains, 18 September 2026." Cost line: "Our entire 108-claim run cost $0.00033 on Jev." Model version named as **Jev 1.13**.

### N and tasks

- **N:** 108 claims total; "108 claims across six source passages"; "56 supported, 52 not."
- **Structure:** 6 domains × 18 claims per domain; "Each model got the whole task in one call per domain."
- **Task shape:** Grounding / citation-style check — "here is a source passage, here is a claim, does the passage support the claim as stated?"
- **Domains (six source passages):** quarterly financial report, clinical trial summary, product changelog, travel policy, supply contract, engineering post-incident review.
- **Difficulty tiers (4):** Literal, Paraphrase, Inference-adjacent, Adversarial near-miss (Tier 4 emphasized as "the tier that matters").
- **Labels:** "We wrote and labelled every claim by hand before any model saw them."

### Compared against

- **Gemini 3.1 Flash Lite**
- **Claude Haiku 4.5**
- Chat models prompted for probability: "We asked for a probability rather than a verdict. We told the chat models to use the full range between zero and one."
- Also discusses TypeSafe's published workflow evals (reference = average of Astra and Fable, not ground truth) as context for what TypeSafe does *not* publish (no ECE in vendor materials per author).

### ECE / accuracy / Brier — verbatim quotes and table values

Headline table (108 claims):

> | Model | Accuracy | Brier score | Calibration error | Cost |
> | Jev 1.13 | 96.3% | 0.0331 | 0.0660 | $0.00033 |
> | Gemini 3.1 Flash Lite | 94.4% | 0.0369 | 0.0611 | $0.00267 |
> | Claude Haiku 4.5 | 93.5% | 0.0547 | 0.0669 | $0.00905 |

Prose on ECE:

> "Expected calibration error came out at 0.066 for Jev, 0.061 for Gemini 3.1 Flash Lite and 0.067 for Claude Haiku 4.5. At 108 items those are one number."

Definition given in post:

> "Written ECE, for expected calibration error, in the tables above and in most papers. Sort every answer into buckets by the confidence the model claimed, then check each bucket against what actually happened."

Tier 4 accuracy (table):

> | 4 · Adversarial near-miss | 91.7% | 83.3% | 80.6% |

> "On tier 4 the chat models lose eight and eleven points, and Jev loses four."

Overall accuracy lead:

> "Jev finished 1.9 points ahead of Gemini 3.1 Flash Lite and 2.8 ahead of Claude Haiku 4.5 on raw accuracy."

Calibration claim assessment (author):

> "It does not survive. A cheap frontier-lab model, asked properly for a probability, calibrates about as well as the model built to produce calibrated probabilities."

### Author-stated limits / caveats

- Small sample / single run: "At 108 items those are one number"; "A probability from one model is one draw, and a threshold set from one run is a guess."
- Task scope: passage support only — "None of the three can settle whether a claim is true in the world. This test asked only whether a passage supports a claim."
- Method sensitivity: study evolved 22 → 72 → 108 claims; wrong early result from chat prompt not asking full probability range — "The cause was our own prompt."
- "Three sample sizes, three conclusions, one afternoon."
- Not measuring vendor-published calibration curves — filling gap author claims TypeSafe left open.

---

## Source 2 — UCLA / eScholarship (Meng preprint)

**Locator:** https://escholarship.org/content/qt4t4449jv/qt4t4449jv.pdf  
**Title:** "How far can a commercial decision model's probabilities be trusted? A calibration audit of Jev against open and general-purpose classifiers"  
**Author:** Lingsen Meng, Department of Earth, Planetary, and Space Sciences, UCLA  
**Publication date:** 2026-09-24 (Preprint draft)  
**Retrieved:** 2026-09-27 (full text from cached extract on disk)

### Called Jev API?

**Yes.** "Jev was called through its public API with the model version pinned." Appendix: "Jev was called with the model version pinned to **1.13.0**." Total: "**All 5,616 Jev calls** in this study cost US$0.086 in total." Caching: "All API calls are cached on their request body."

### N and tasks

- **Calibration analysis set:** "3,244 evaluations of 2,372 distinct texts from two public classification tasks."
- **Tasks:**
  - **SST-2** (GLUE dev): 872 movie-review sentences — asked in **two question forms** (yes/no `noul` and `choice`).
  - **AG News:** sample of **1,500** items (seed-fixed from 7,600 test set), title + description joined; **four-way choice**.
- **Extra Jev calls:** second label-description set adds 2,372 further calls → 5,616 Jev calls total.
- **Open models** also run on full AG News 7,600 where noted for population estimate.

### Compared against

(Table 1 systems)

- **Jev 1.13.0** (TypeSafe commercial decision API)
- **DeBERTa-v3-large-zeroshot-v2.0-c** ("open NLI classifier, trained without supervised examples from these benchmarks")
- **DeBERTa-v3-large-zeroshot-v2.0** ("task-exposed" — up to 500 examples/class from 28 datasets including AG News and Rotten Tomatoes)
- **gpt-5.4-nano, gpt-4.1-nano** — "probabilities from top_logprobs" of single output token

Two label wordings per system (author's vs open model card descriptions).

### ECE / accuracy — verbatim quotes and table values

Abstract (middle scale, quantization):

> "the middle of the four-class scale is overconfident (stated 0.750, observed 0.612), and 71.6% of four-class answers sit at exactly 1.00"

Question-form ECE shift:

> "the calibration error changes by 0.071 between two ways of posing the same question"

Table 2 (95% item-bootstrap intervals):

> "SST-2, yes/no form 0.948 [0.933, 0.962] **0.091 [0.078, 0.104]**"
> "SST-2, choice form 0.961 [0.947, 0.974] **0.020 [0.014, 0.035]**"
> "AG News, four-way 0.867 [0.850, 0.884] **0.089 [0.076, 0.108]**"

Section 4.1 on same 872 sentences, two forms:

> "The observed difference in ECE is **0.071**, with a bootstrap mean of 0.067 and an interval of **[0.047, 0.086]**"

AG News pooled middle bins:

> "mean stated confidence of **0.750** against an observed accuracy of **0.612**, interval [0.552, 0.670]"

Table 4 held-out ECE after temperature scaling (200 random halves) — "as returned" column:

> "SST-2 yes/no **0.091** … choice **0.024** … AG News **0.092**"
> After scaling: "yes/no **0.023** … choice **0.034** … News **0.028**"

Accuracy vs open models (Table 6 sample, author wording):

> "Jev, our label wording **0.961** [SST-2] **0.867** [AG News]"

Full-test-set exploratory gap (AG News, author's descriptions, answers as delivered):

> "Jev is more accurate than -c by **+5.72 points**, 95% interval [+4.70, +6.75], and less accurate than the task-exposed checkpoint by **−2.30 points** [−3.33, −1.28]"

Conformal (not ECE but calibration-adjacent):

> "single-label sets error inside … **5.93%**" (randomised rule at 95% target on AG News)

Certification:

> "a 5% tier certifies for Jev in **0 splits**" on AG News (their procedure)

### Author-stated limits (Section 6 and elsewhere)

- "The study covers **two English text-classification tasks** and **one version** of each system; we did not test domain data, other languages, long contexts, latency or cost."
- Label wordings: each system tried under **exactly two** label wordings; OpenAI under one fixed prompt.
- "The OpenAI probabilities come from a single output token under a short completion budget, which is a **proxy** for the model's belief and not the object Jev returns."
- "**The analysis is exploratory.** The evaluation items were used while the analysis was developed… the +5.72 is therefore a transparently specified exploratory estimate rather than a preregistered confirmation."
- Intervals "None of these intervals includes variation from **querying the systems again**."
- Cannot examine Jev pretraining data or internal confidence computation: "the vendor's post-processing is **not observable**."

---

## Source 3 — Kingy AI review

**Locator:** https://kingy.ai/blog/typesafe-jev-review-the-ai-model-that-doesnt-generate-text/  
**Author:** Curtis Pyke (JSON-LD `author`; Kingy AI)  
**Date published:** 2026-09-15T23:12:34+00:00 (modified 2026-09-15T23:36:46+00:00)  
**Research scope stated:** "checked September 15, 2026"  
**Retrieved:** 2026-09-27 (WebFetch; fallback text on disk matches)

### Called Jev API?

**No.** Verbatim:

> "We did not run a live Jev API call because access was still early access / waitlist."

Table row:

> "**Measured directly** | No instrumented measurements. No live Jev API key or paid API usage was available at publication."

> "**Not tested** | Ground-truth accuracy, **calibration metrics**, p95/p99 latency…"

### N and tasks (vendor dashboard cited, not independently run)

TypeSafe workflow dashboard as reported by reviewer:

> "**711 cases across four tasks**"

| Workflow | N (from table) |
| --- | --- |
| Security incidents | 240 |
| Agent trace observability | 117 |
| Invoice processing | 150 |
| Customer service | 204 |
| Aggregate | 711 |

Tasks are TypeSafe-defined workflows (triage/classification-style), not author-run benchmarks.

### Compared against

From dashboard (TypeSafe): comparators named include **Sol**, **Opus** on various rows; reference policy described as model-derived:

> "compared with a reference policy based on the average judgments of **GPT-6 Astra and Claude Fable 5.1**"

> "the reported accuracy is better understood as **agreement with a model-derived reference** than as independently verified correctness."

External: **Every's** Mike Taylor test cited (37 documents, 777 judgments) — not Kingy's API run.

### ECE / accuracy numbers

**No ECE reported by Kingy** (none measured). On calibration:

> "**Confidence is not independently demonstrated to be calibrated.**"

FAQ:

> "**Is Jev's confidence calibrated?** … **TypeSafe has not yet published standard calibration metrics** across independent ground-truth tasks."

Vendor aggregate accuracy (rounded dashboard, not ECE):

> "Aggregate | 711 | **67.8%** / $0.0004 / 0.4s | Sol **74.1%** …"

Invoice processing gap called out: Jev **61.8%** vs Sol **79.1%**.

### Author-stated limits

- Document-and-eval review, not lab test.
- No calibration curves, no independent ground-truth dataset with raw predictions from Kingy.
- Benchmark harness bias acknowledged (vendor-built tasks).
- "Zero hallucinations" framed as type-safety, not semantic correctness.

---

## Source 4 — Prefactor blog

**Locator:** https://prefactor.tech/blog/jev-calibrated-confidence-is-not-correctness  
**Title:** "Is Jev's confidence score trustworthy? RLCD calibration explained"  
**Author:** Matt Doughty  
**Date:** 25 September 2026  
**Retrieved:** 2026-09-27 (WebFetch)

### Called Jev API?

**No empirical Jev run in post.** Conceptual / production-practices article promoting outcome logging on customer traffic. No sample size, no API calls, no reported Jev scores from author.

### N and tasks

- **N:** not applicable — no measurement study.
- **Task:** discusses generic routing / auto-approve on confidence thresholds, not a specific benchmark.

### Compared against

- Does not compare Jev to other models on a fixed dataset.
- Compares **calibration vs accuracy** conceptually; cites enterprise anecdotes (Klarna, JPMorgan COIN, Salesforce Agentforce) as pattern examples, not Jev benchmarks.

### ECE / accuracy numbers

**None reported for Jev.** No ECE, Brier, or accuracy figures from author measurement.

TL;DR:

> "Jev's confidence score is calibrated on TypeSafe's training data, not your traffic. Until you compare it to real outcomes per run, you cannot act on it."

On vendor transparency:

> "**TypeSafe has not published** Jev's reward function, its architecture, or its calibration methodology."

Recommended practice (bins, not results):

> "Binning decisions by reported confidence and computing the actual error rate in each bin."

Sample size guidance (generic):

> "Fewer than **200 labeled examples per bin** makes the estimates noisy enough to mislead."

### Author-stated limits

- Does not claim to have validated or falsified Jev calibration empirically.
- "This is a **production evaluation problem**, not a vendor question."
- Assumes RLCD premise "is sound" in abstract but argues transfer to user traffic requires own measurement.
- Prefactor product pitch for span logging — not an independent audit.

---

## Cross-source index (factual only, not a verdict)

| Source | API called? | Own ECE? | Own N |
| --- | --- | --- | --- |
| TrueStandard | Yes | Yes (0.066 / 0.061 / 0.067) | 108 |
| Meng UCLA | Yes | Yes (0.091 / 0.020 / 0.089 + post-T scaling) | 3,244 evals / 5,616 Jev calls |
| Kingy | No | No | 0 ( cites vendor 711 ) |
| Prefactor | No | No | 0 |
