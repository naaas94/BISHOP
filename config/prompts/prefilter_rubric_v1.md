---
rubric_id: prefilter_rubric
version: "1.0.0"
canonical_hash: "976d9185b0bbef3eb994ed68913b9c1908dd4190d175148e5cec9190e14d4fb0"
---
# Source-shape law for pre-filter

You are shown a `title` and, for most sources, an `abstract`. Both are lightweight manifest
fields captured before full content is fetched — the manifest stage exists precisely so that
scrape and enrichment are not spent on items you would reject anyway. What those two fields
*contain* is not uniform. It depends on which of the seven registered adapters produced the
row, and each adapter's manifest shape carries a different amount and a different kind of
evidence. Judging every row as if it were a dense academic abstract will systematically
misjudge the rows that are not one. This annex is source-shape law: it tells you how much
weight the fields in front of you can bear, source by source, before you apply the profile's
own exclusion / peripheral / anchor decision order. It does not replace that decision order,
and it does not add, remove, or reweight any exclusion, anchor, or peripheral class. It only
calibrates how confidently you should read what little or much evidence a given shape gives
you.

There are five shapes behind the seven adapters. Three of the seven — the ones that draw from
academic literature — hand you the same kind of field as one another, so they share one law
below instead of three separate ones.

## Shape 1 — paper (arxiv, openreview, semantic_scholar)

These three adapters hand you a real abstract: several sentences written by the authors to
summarize contribution, method, and scope. This is the highest-evidence shape. Read it the way
the profile's own decision order and object-of-study test assume you will: identify what the
paper is trying to make better, check it against the exclusions (base-model science, modality
adapters, vertical/narrow-corpus work) in the stated order, then check the anchors, then apply
the "would I open this as a working reference this week" test before marking core. Because the
abstract is usually dense enough to resolve the object-of-study test cleanly, treat an
unresolved case as genuine ambiguity, not as missing evidence — route it to peripheral per the
profile's own uncertainty instruction, rather than guessing core or reject from a thin reading.
A long abstract that never names a system, pipeline, or application anyone could build from is
still base-model science even if it uses agent- or retrieval-adjacent vocabulary in passing;
do not let a single keyword override the sustained subject of the abstract.

One shape-specific trap: these three adapters draw from overlapping literature — the same
paper can appear as an arxiv preprint, an OpenReview submission, and a Semantic Scholar record,
each as its own manifest row with its own `source_id`. Judge each row on the fields in front of
you. Do not assume familiarity with a paper because a similarly titled row scrolled past
earlier in the batch; a shared title is not evidence either way about a specific row's
abstract, and batches do not guarantee ordering that would let such inference be reliable
regardless.

## Shape 2 — repo (github)

The GitHub adapter's `title` is the repository name and its `abstract` is the repository's
one-line description field — the tagline the maintainer chose for a search results page, not
a technical summary written to justify a contribution. This is materially thinner evidence
than a paper abstract, and it is evidence of a different kind: a tagline optimizes for
discoverability, not disclosure of method or object of study. Do not read the absence of
methodological language in a tagline as evidence that the repository lacks one — the field was
never going to contain it. Do not read the *presence* of exciting vocabulary in a tagline
("state-of-the-art", "blazing fast", a benchmark name) as strong evidence of quality either;
taglines are marketing copy by construction and are the least reliable field in this entire
pipeline for anchor matching.

The bar for a repo is whether you would study or steal from this codebase, not whether the
tagline is about agents or RAG. A tagline that names a concrete stealable artifact — a
retrieval index builder with a described retrieval mode, a browser extension that attaches to
a real agent runtime, an observability pane with a named protocol, an operator playbook
whose repo is the working artifact — is real evidence for `applied_systems` or `dev_skills`.
The code is the working reference the profile asks for; that row may be core. Badges on a
README that also names such an artifact do not by themselves make it junk.

Treat the following as the profile's existing star-count-dump / no-reusable-technique
exclusion and **reject** them (decision 0). Do not park them: park still spends gate-1 tokens
and fills the inbox, and on-topic boilerplate must not spend scrape or enrich.

- Kitchen-sink wrapper: capability laundry lists ("AI employees", RAG-in-a-box,
  fleet-of-agents) that advertise every adjacent buzzword without a named stealable core.
- Product landing: "deploy in minutes", YAML-as-product, hero copy with no application code
  or technique to copy.
- Badge-wall: stars, CI, shields, self-assessed compliance badges, and install buttons with
  no named technique or artifact behind them.
- Awesome-list / link dump / curated papers or prompts (already excluded).
- Vendor SDK / thin client around someone else's API (install a hook, pass an agent id).
- Clone of a CLI you already run: auto-yes wrappers, thin skins, rebrands of a tool already
  on the machine.

If the tagline is ambiguous about whether it is one of those junk classes, **reject**, not
park. Uncertainty about kitchen-sink vs landing vs badge-wall is not genuine ambiguity about
a working reference. Genuine remaining park cases are taglines that do name a stealable
artifact but are too thin to tell whether you would open it this week — those stay peripheral,
not core and not reject. Do not auto-reject a working-reference repo just because the tagline
is short or the README also has badges.

## Shape 3 — model card (huggingface)

The HuggingFace adapter's `title` is prefixed with a bracketed entity kind — `[model]`,
`[dataset]`, or `[space]` — followed by either a card-declared title or the raw repo ID. Read
the kind bracket before anything else: a `[space]` is frequently a running demo of a pipeline
or agent, which is a different evidentiary question from a `[model]`, which is frequently a
fine-tuned or quantized checkpoint with no pipeline around it at all, or a `[dataset]`, which
is frequently a benchmark or corpus release.

The `abstract` field for this shape degrades in three steps, and you cannot tell from the field
alone which step produced what you are reading: it may be a genuine card description, or it
may be a bare comma-joined list of tags with no prose at all. A tag list ("text-generation,
pytorch, transformers, en") carries almost no anchor-matching signal — it is a taxonomy
placement, not a claim about contribution or applicability — and should not be read as either
supporting or contradicting any anchor. This is exactly the near-zero-evidence case the
profile's own "star-count dumps, model-card listings ... with no reusable technique" exclusion
was written for: a model or dataset card whose only visible content is a tag list or a bare
repo ID, with no described integration, pipeline, or technique, is that exclusion's central
case, not a park-for-later case. Reserve core or even peripheral for cards whose title or
description names an actual applied use — a `[space]` demoing a retrieval or agent pipeline, a
`[model]` whose card describes a specific production integration pattern rather than only
benchmark numbers. A `[model]` or `[dataset]` card is essentially never core under this
profile: it is, at most, a working reference to a technique described *around* a checkpoint,
never the checkpoint itself, and checkpoint-only science is squarely base-model territory the
profile already excludes regardless of card thinness.

## Shape 4 — article (lesswrong)

The LessWrong adapter never populates `abstract` — every row of this shape is `title` only,
by construction of the manifest stage, not by an accident of a particular post. Do not read
the empty field as evidence of a thin or low-effort post; the platform does not expose an
excerpt at this stage and every post from this source looks identical in that respect. This is
the lowest-evidence shape in the batch, and the only sound response to genuinely low evidence
is the profile's own instruction for genuine uncertainty: when a title plausibly touches an
anchor but you cannot resolve object-of-study, tier, or exclusion from the title alone, park it
peripheral rather than guessing either core or reject. Do not let the absence of body text push
you toward reject by default — that would silently convert every LessWrong row into a rejection
gate regardless of topic, which is not what the profile's exclusion list says and not a
distinction this shape's evidence can support.

Title alone is still real evidence for some calls. A title that names a specific exclusion
directly — a clinical or biomedical claim, a specific non-English benchmark, an explicit
training-recipe or decoding-algorithm claim — is enough to exclude without needing the body,
the same way it would be from a paper title. A title that clearly names one of the profile's
peripheral classes (alignment or agency philosophy, LLM psychometrics, interpretability,
sociotechnical or market analysis of deployment) is enough to park peripheral on that basis
alone; those classes are defined by subject, and subject is frequently legible from a title
even without a body. What a bare title cannot support is a *core* mark: core requires the
"working reference I would open this week" judgment, and that judgment needs the applied
detail a title-only row structurally cannot supply. Do not mark an article-shape row core;
route the anchor-plausible cases to peripheral instead, exactly as the profile already asks you
to do for anything you cannot confirm is a working reference.

## Shape 5 — hub dump (paperswithcode)

The Papers With Code adapter hands you a paper title and abstract much like shape 1 — but the
row exists in this index because an implementation was linked to the paper, not because the
implementation itself was evaluated for quality or the paper for a system built on top of it.
Do not treat the mere existence of a linked implementation as evidence toward `applied_systems`
or `dev_skills`; those anchors ask whether *you* would open the artifact as a working reference,
and a link existing in an index says nothing about whether the artifact is a maintained,
runnable, or well-designed one. Judge the abstract exactly as you would a paper-shape abstract
— same object-of-study test, same exclusion order, same anchor matching — and let the
implementation link raise your confidence in nothing. If the abstract itself describes an
applied system, pipeline, or reusable technique, that stands on its own paper-shape merits.
This shape is, in effect, a paper-shape row with an extra fact attached that is not decision-
relevant at the pre-filter stage; do not let the fact of "code exists" substitute for evidence
that the code, or the method it implements, is worth this week's attention.

## Confidence calibration by shape

As a quick reference, evidence density runs from highest to lowest across the five shapes:
paper and hub dump hand you a multi-sentence abstract written to disclose contribution; repo
hands you a one-line tagline written to attract attention rather than disclose method; model
card hands you either a short card description or, degenerately, a bare tag list that
discloses nothing about contribution; article hands you a title and nothing else. The decision
this density difference should change is never *which* exclusion, anchor, or peripheral class
applies — those are fixed by the profile regardless of source. What it changes is how willing
you should be to convert an anchor-plausible reading into a *core* mark specifically. High-
density shapes can earn core on the strength of their own field content, because the field
actually states what you would be opening as a working reference. Low-density shapes — a bare
tagline, a tag list, a title alone — essentially never carry enough disclosed detail to satisfy
the "working reference I would open this week" test on their own, so an anchor-plausible but
under-specified low-density row should default to peripheral, not core, precisely because core
is the profile's scarce, high-confidence tier and a thin field cannot supply that confidence.
This is a restatement of the per-shape guidance above, offered as a single cross-cutting
checkpoint: before marking any row core, ask whether the specific field you read actually
disclosed a working reference, or whether you inferred one from a source's reputation, a
keyword, or a linked artifact whose quality you have no way to check from this field alone.

## Cross-shape discipline

Two closing rules bind across all five shapes above. First, evidentiary weight is not a
separate axis from the exclusion / peripheral / anchor order the profile's output instruction
already specifies — this annex tells you how hard you can lean on a field, not a fourth
decision step to run after the other three. When a shape's evidence is thin, the correct
response is nearly always the profile's own uncertainty instruction — park peripheral — not an
invented default of reject or core for that source as a class. Second, do not let a source's
typical thinness become a prior about that source's typical relevance. A repo tagline being
weak evidence for anchor-matching does not mean GitHub rows are typically off-topic, and a
dense arxiv abstract being strong evidence does not mean arxiv rows are typically on-topic.
Judge the row in front of you on the fields it actually gives you, weighted the way this annex
describes, and nothing else.
