---
rubric_id: call2_rubric
version: "1.0.0"
canonical_hash: "d1e7b871e1793b277a08dbe929390a45960bf665c7a44e60e1442229325d58a5"
---
# Call 2 relevance-scoring rubric

This annex governs **enrichment Call 2's relevance scoring** — the continuous
`relevance_score` float (0.0–1.0) and the accompanying `relevance_reason` and
`value_rationale` strings. It does not govern, and must never be read as
restoring, the pre-filter's binary pass/reject gate. That decision has
already been made by the time an item reaches Call 2: the item survived
gate 1 and is now being scored for how strongly it serves the profile, not
whether it is admitted at all. If you find yourself reasoning toward an
admit/reject verdict instead of a magnitude, you are answering the wrong
question for this stage.

## Why a float, not a decision

Gate 1 asks "should this enter the corpus at all?" Call 2 asks "how much
should this item's relevance weigh in downstream ranking, digesting, and
surfacing?" Two items can both have passed gate 1 and still deserve very
different scores: a landmark paper introducing a retrieval technique this
profile is built around should score far higher than a passable-but-generic
engineering blog post that mentions retrieval only in passing. Collapsing
that distinction back into a binary would throw away the signal Call 2
exists to produce. Score every item as if the two questions — "does this
belong in the corpus" and "how relevant is it" — were being asked by two
different people who never talk to each other, because in this pipeline
they are.

## Score bands

Five bands. Treat the boundaries as centers of gravity, not hard cutoffs —
an item can sit at 0.62 or 0.86 and that is fine. What matters is which
band's *character* the item matches, not which decimal it lands on.

### 0.90–1.00 — Core exemplar

The item is squarely inside a high-weight anchor (weight ≥ 0.9) and would be
useful to reread later as a reference on that anchor. It is specific,
technical, and actionable — not a survey of the field but a concrete
technique, system, or result a practitioner could apply or cite. Multiple
anchors overlapping (e.g. a paper that is both retrieval and evaluation)
pushes toward the top of this band even at slightly lower novelty.

### 0.70–0.89 — Strong secondary

The item clearly serves at least one anchor but is narrower in scope, lower
weight, or more incremental than a core exemplar — a solid engineering
write-up on a known technique, a useful but non-foundational benchmark
result, a serving optimization with real numbers but limited generality.
Still worth surfacing prominently; just not the item you'd point to as the
canonical reference on its anchor.

### 0.50–0.69 — Marginal

The item touches an anchor but only partially, or serves a low-weight
anchor (weight ≤ 0.8) without unusual depth, or mixes genuinely relevant
content with a large share of material the profile's principles would
deprioritize (e.g. a mostly-theoretical paper with one practical section).
This band is where judgment calls concentrate — see "Marginal-band
worked examples" below before defaulting to it out of uncertainty.

### 0.30–0.49 — Weak / tangential

The item is adjacent to the domain — it name-drops an anchor concept, is
written by a lab or author who works in this space, or shares surface
vocabulary — but does not give the profile's owner anything actionable on
any anchor. It survived gate 1 (often on a peripheral-tier or borderline
call) but Call 2's more careful read finds little substance underneath.

### 0.00–0.29 — Should not have passed gate 1

Reserve this band for items where Call 2's fuller read (full summary and
extracted concepts, not just the gate-1 title/snippet) reveals the item is
actually excluded-class material — pure business news, introductory
tutorial content, or hardware-only content with no ML application — that
the pre-filter's coarser judgment missed. Do not use this band to express
"I would have rejected this at gate 1 too" for material that is genuinely
on-topic but simply unexciting; that is 0.30–0.49 territory. This band is
specifically the exclusions list, discovered late.

## Anchor-weighted scoring guidance

The profile's anchors carry different weights (see the profile block above
this annex), and that weight should visibly move the score, not just be a
mental footnote:

- An item squarely on a **weight 1.0** anchor (RAG/retrieval, agentic
  systems) should rarely score below 0.6 even when it is a weaker example
  of that anchor, because the anchor itself is core to the profile.
- An item squarely on a **weight 0.7** anchor (eval/observability) with the
  same intrinsic quality as the case above should typically land 0.1–0.15
  lower — the content is just as well-executed, but it serves a less
  central concern.
- An item that spans two anchors, even at moderate depth on each, generally
  outscores a single-anchor item of similar per-anchor depth. Breadth
  across the profile's stated interests is itself a signal of relevance,
  not a diluting one.
- An item that is well-executed but sits entirely outside all five anchors
  — competent work, just not this profile's business — belongs in the
  0.30–0.49 band regardless of how well it is written. Execution quality is
  not a substitute for anchor fit.

## Worked examples

Each example gives a title, the band it lands in, the score, a one-sentence
`relevance_reason`, and a `value_rationale` in the style Call 2 should
produce. These are illustrative, not a lookup table — do not attempt to
match incoming items against these titles.

**1. "Late Chunking: Contextual Chunk Embeddings Using Long-Context Embedding
Models" — 0.95, core exemplar.**
`relevance_reason`: "Directly introduces a retrieval-quality technique
(late chunking) squarely inside the RAG/retrieval anchor at weight 1.0."
`value_rationale`: "Gives a concrete, reproducible technique for improving
chunk-boundary embedding quality that is directly applicable to this
profile owner's current retrieval stack, not just a conceptual survey."

**2. "LangGraph Multi-Agent Handoff Patterns in Production" — 0.92, core
exemplar.**
`relevance_reason`: "Squarely inside the agentic-systems anchor and
explicitly frames the content around production deployment, matching the
profile's practitioner-over-academic framing."
`value_rationale`: "Documents a specific handoff pattern with failure modes
observed in production, which is exactly the kind of engineering-tradeoff
content the profile's principles prioritize over theoretical novelty."

**3. "Benchmarking INT4 Quantization Throughput on H100s for 70B-Class
Models" — 0.78, strong secondary.**
`relevance_reason`: "Serves the llm-inference anchor (weight 0.8) with
concrete throughput numbers, but is narrower in scope than a core exemplar
— a single hardware/quantization combination rather than a general
serving-architecture result."
`value_rationale`: "Provides a specific throughput data point useful for
capacity-planning decisions, though its narrow hardware scope limits how
directly it generalizes to other deployment targets."

**4. "A Survey of Schema-Bound Extraction Methods for Document AI" — 0.74,
strong secondary.**
`relevance_reason`: "On-anchor for document intelligence (weight 0.9) but a
survey rather than a specific technique or system, which caps it below the
core-exemplar band even at a central anchor."
`value_rationale`: "Useful as a map of the extraction-method landscape for
orienting future reading, though it does not itself hand the profile owner
a technique to apply directly."

**5. "Tracing LLM Agent Failures with OpenTelemetry: A Case Study" — 0.68,
marginal.**
`relevance_reason`: "Touches the eval/observability anchor (weight 0.7) and
the agentic-systems anchor, but the case study is thin on transferable
detail beyond 'we added tracing.'"
`value_rationale`: "Confirms that OpenTelemetry-based tracing is a viable
pattern for agent observability, but the write-up does not provide enough
implementation detail to be independently actionable."

**6. "Why Every Startup Needs an AI Strategy in 2026" — 0.22, excluded-class
missed at gate 1.**
`relevance_reason`: "Business-strategy framing with no technical substance
once read past the headline — matches the exclusions list ('market
analysis or business news without technical substance') that gate 1's
coarser pass missed."
`value_rationale`: "No specific, applicable content for a practitioner
building production AI systems; the piece is positioning commentary, not
engineering guidance."

**7. "Introduction to Neural Networks for Beginners" — 0.28, excluded-class
missed at gate 1.**
`relevance_reason`: "Introductory-level tutorial content explicitly
excluded by the profile ('tutorial content at introductory level — assume
expert baseline'); Call 2's fuller read confirms no expert-level content is
present beyond the intro framing."
`value_rationale`: "Nothing here is new information for the profile
owner's stated expert baseline; the piece has no standalone value at this
reading level."

**8. "A Fully Homomorphic Encryption Scheme for Federated Averaging" — 0.35,
weak/tangential.**
`relevance_reason`: "Shares surface vocabulary with ML systems (federated
averaging) but the actual content is a cryptography result with no
retrieval, agentic, inference, document, or eval application — it is
adjacent to, not inside, any anchor."
`value_rationale`: "Interesting cryptographic technique, but it does not
connect to any of the profile's stated engineering concerns (latency,
reliability, cost, retrieval, agent orchestration) closely enough to be
directly useful."

**9. "Reranking with Cross-Encoders: A Production Postmortem" — 0.88, strong
secondary bordering core.**
`relevance_reason`: "On the RAG/retrieval anchor at weight 1.0, framed as a
postmortem with concrete failure analysis, which the principles explicitly
value ('failure modes') — held just under core-exemplar because it covers
one component's failure rather than a full technique or system."
`value_rationale`: "Documents a specific reranking failure mode and its
fix in enough detail to be directly checked against the profile owner's
own reranking setup."

**10. "GPU Market Share Q2 2026: NVIDIA vs. Competitors" — 0.18,
excluded-class missed at gate 1.**
`relevance_reason`: "Hardware-market analysis with no ML-application
content once read fully — matches both the 'hardware-only content without
ML application' and 'market analysis... without technical substance'
exclusions."
`value_rationale`: "No engineering content for the profile owner to act
on; this is competitive/market commentary, not a technical resource."

**11. "Peripheral Note: Vector Database Pricing Comparison, Sept 2026" — 0.42,
weak/tangential, peripheral-tier pass-through.**
`relevance_reason`: "Arrived from gate 1's peripheral-tier pass rather than
a core-anchor match; pricing comparisons touch the retrieval anchor
tangentially through vector-store selection but carry no technique or
architectural content of their own."
`value_rationale`: "Useful only as a cost-reference data point if the
profile owner is actively re-pricing a vector store; standalone it offers
no engineering insight."

**12. "Combining Hybrid Retrieval with Agent-Driven Query Rewriting: A
Production Architecture" — 0.97, core exemplar, multi-anchor overlap.**
`relevance_reason`: "Squarely spans two weight-1.0 anchors at once —
retrieval and agentic systems — with a described production architecture
rather than a conceptual pitch, which is the strongest possible anchor
match this profile can register."
`value_rationale`: "Documents a concrete architecture where an agent
rewrites queries before a hybrid-retrieval pass, including the specific
failure mode this combination avoids, giving the profile owner a pattern
they could adapt directly rather than merely a citation."

**13. "Formal Verification Techniques for Neural Network Robustness
Certificates" — 0.31, weak/tangential, low-weight anchor at high execution
quality.**
`relevance_reason`: "Technically rigorous and clearly well-executed, but
it sits outside all five anchors — none of retrieval, agentic systems,
inference serving, document intelligence, or eval/observability cover
formal robustness certification — so execution quality alone cannot lift
it past the weak band."
`value_rationale`: "A strong result in its own subfield, but it does not
connect to any production concern (latency, reliability, cost, retrieval,
orchestration) the profile tracks, so it offers little the owner can act
on this cycle."

**14. "Prompt Caching for Long-Context Agents: An Implementation Guide" —
0.30, borderline between weak and excluded — resolved toward weak, not
excluded.**
`relevance_reason`: "Touches the llm-inference anchor (caching is a
serving-cost lever) and the agentic-systems anchor by name, but the guide
is generic vendor-documentation restatement with no measured numbers or
novel pattern — thin enough to tempt an excluded-class call, but it is not
actually exclusions-list material (not business news, not an
introductory tutorial, not hardware-only), so it stays in 0.30–0.49 rather
than dropping to 0.00–0.29."
`value_rationale`: "Restates publicly documented caching mechanics without
adding a measured tradeoff or edge case, so it functions as a reference
pointer rather than a source of new engineering signal."

**15. "Structured Extraction from Scanned Contracts Using Layout-Aware
Transformers" — 0.86, strong secondary bordering core.**
`relevance_reason`: "On the document-intelligence anchor (weight 0.9) with
a specific model family (layout-aware transformers) and a concrete
extraction task, close to core-exemplar territory but held slightly below
it because the write-up focuses on one document type rather than a
generalizable pipeline pattern."
`value_rationale`: "Names a specific architectural family for
layout-aware extraction and the document type it was validated against,
giving the profile owner a concrete starting point for a comparable
extraction task rather than a general survey."

## Scoring consistency across a batch

Call 2 processes many items per batch. Two failure modes erode the score's
usefulness even when each individual score looks locally defensible:

- **Compression toward the middle.** If every item in a batch lands between
  0.55 and 0.75 regardless of how different they actually are, the score
  has stopped carrying information. Force yourself to ask, for each item,
  "is this closer to example 1 or example 6 above?" rather than anchoring
  on the previous item's score.
- **Tier leakage from gate 1.** An item that arrived from gate 1's
  peripheral-tier pass (see the profile's "Peripheral tier" instructions,
  where applicable) is not entitled to a floor score just because it was
  allowed through. Score peripheral-tier arrivals exactly as you would any
  other item — by anchor fit and specificity — and expect many of them to
  land in the 0.30–0.49 band, since peripheral tier exists precisely for
  material that is adjacent but not central.

## `value_rationale` guidance

A good `value_rationale` names the *specific, checkable* thing the item
gives its reader — a technique, a number, a failure mode, a comparison —
not a restatement of the topic. Contrast:

- Weak (topic restatement): "This article discusses retrieval systems and
  is relevant to the profile's interest in RAG."
- Strong (specific value): "Gives a measured latency/recall tradeoff curve
  for three reranking models on a 10M-document corpus, letting the profile
  owner pick a model without running the benchmark themselves."

A `value_rationale` that would read identically for two different items in
the same score band is under-specified — go back to the summary and name
what is actually distinct about *this* item's contribution.

## Distinguishing `relevance_reason` from `value_rationale`

The two strings answer different questions and should not paraphrase each
other:

- `relevance_reason` answers "why does this land where it does relative to
  the profile's anchors" — it names the anchor(s), the weight
  consideration, and the factor that pushed the score up or down (breadth,
  specificity, execution, exclusions-list overlap).
- `value_rationale` answers "what, concretely, would the profile's owner
  get out of reading this" — it should be specific enough that someone who
  has not read the item could decide whether to prioritize it, based on
  the rationale alone.

A `relevance_reason` that only restates the score band's name ("this is a
strong secondary item") without naming the anchor and the specific factor
is under-specified; so is a `value_rationale` that only restates the
title's topic without naming a technique, number, comparison, or failure
mode. Both fields should survive being read on their own, out of context,
by a downstream consumer who never sees the score.

## Common miscalibration traps

- **Hype inflation.** A well-known lab or a widely shared item is not
  automatically a core exemplar. Score the content, not its popularity.
- **Enthusiasm substitution.** Do not let a well-written or entertaining
  piece outscore a duller piece with more transferable substance —
  `value_rationale` should survive being read by someone who does not
  share the writer's enthusiasm.
- **Anchor-adjacent drift.** Vocabulary overlap (the word "agent," the word
  "embedding") is not anchor fit. Confirm the item's actual technical
  content, not its keyword surface, before assigning anything above 0.5.
- **Binary bleed-through.** Do not let a "this clearly belongs in the
  corpus" instinct pull the score toward 1.0 by default. Gate 1 already
  settled corpus membership; this score answers a narrower, harder
  question about degree of relevance, and the honest answer is often in
  the 0.5–0.8 range even for items that obviously belong.
- **Author-prestige substitution.** A well-known research lab or a
  frequently cited author does not raise the score on its own. Judge the
  specific item's content — its anchor fit, specificity, and actionable
  detail — exactly as you would from an unknown source, and let the
  worked examples above, not the byline, set the calibration point.
- **Length-as-depth substitution.** A long piece is not automatically more
  specific than a short one. A tight two-paragraph write-up with one
  measured number can outscore a ten-page piece that never gets past
  motivation and background. Score the density of transferable content,
  not the word count.

## Summary for the model applying this rubric

Read the full item (summary, extracted concepts, and any challenge hooks
from Call 1), pick the score band whose worked examples most resemble it,
adjust up or down within that band using the anchor-weight guidance, and
write `relevance_reason` and `value_rationale` as two independent,
self-contained statements per the distinction above. Do not emit a
pass/reject decision field of any kind — this stage's output is the score
and its two supporting strings only.


Respond with {"decision": 0 or 1}.
