---
rubric_id: call1_rubric
version: "1.0.0"
canonical_hash: "f3cf74ac069d066c378f1a0937ce3c6da230455ce29660dc8e630803859819cc"
---
# Call 1 Extraction Rubric — Annex

This annex extends the Call 1 system prompt (schema, entry-type enum, and
tag taxonomy are injected by `build_call1_system_prompt()` and are **not**
restated here). It gives per-`entry_type` extraction guidance, per-source
content-shape notes, and worked examples so a Haiku-class model extracting
from truncated, source-heterogeneous text produces consistent `summary`,
`concepts`, `tags`, `entry_type`, and `challenge_hooks` fields. Nothing
below introduces a second schema; every worked example below returns the
exact same JSON shape the system prompt already defines.

Call 1 never sees a profile. This annex is the only stable context the
model has beyond the raw title and truncated body, so treat every rule
here as load-bearing, not decorative.

## 1. Why extraction drifts without this annex

Two failure patterns recur across sources when a model only has the bare
schema and no worked guidance:

1. **Summary genericism.** Without a length and density target that is
   anchored to examples, models default to a one-sentence marketing blurb
   ("This paper presents a new method for improving X") instead of a
   dense technical summary that names the actual mechanism, dataset, or
   result. A summary that could be copy-pasted onto ten different papers
   in the same subfield is a failed extraction even if it is 200-300
   characters and grammatically correct.
2. **`challenge_hooks` collapse into restated titles.** Left unguided, a
   model tends to rephrase the title as a "hook" ("Improving X for Y") a "hook" instead of writing the
   underlying problem framing a practitioner would type into a search
   box ("how to reduce KV-cache memory for long-context serving without
   quality loss"). `challenge_hooks` is the single most load-bearing
   field for Layer 2 retrieval (spec §13.1) — a title restated as a hook
   is nearly useless for a query that never mentions the title.

Every rule below exists to close one of these two gaps, or the adjacent
gap of `concepts` drifting toward keyword-stuffing instead of naming the
handful of ideas a domain reader would actually cite.

## 2. Per-`entry_type` extraction guidance

The nine `entry_type` values are not evenly weighted in the corpus, and
they do not all extract the same way. Guidance per type:

### `paper`

The most common type. `summary` should name the method, the problem it
solves, and — if stated — the headline quantitative result (a benchmark
number, an ablation delta, a scaling exponent). Do not summarize the
introduction's motivating narrative; summarize the contribution.
`concepts` should list the named techniques and named prior work the
paper builds on or compares against, not generic ML vocabulary ("neural
network", "deep learning") unless that vocabulary is itself the paper's
subject. `challenge_hooks` should be phrased as the open problem the
paper is trying to close, in language a practitioner facing that problem
would use, not language borrowed from the paper's own title.

### `model`

Applies to model-card content (typically `huggingface`). `summary`
should state the model family, parameter count if given, training data
or fine-tuning objective, and the stated intended use. `concepts` should
include the base architecture family and the training technique (LoRA,
RLHF, DPO, distillation, quantization scheme) rather than restating the
model name. `challenge_hooks` should frame the deployment or selection
problem this model addresses ("small model for structured extraction
under a latency budget") rather than restating the model card's own
marketing language.

### `dataset`

`summary` should state what the dataset contains, its size, and its
intended evaluation or training use. `concepts` should include the task
family the dataset targets (retrieval, QA, code generation, safety
red-teaming) and any notable construction methodology (synthetic
generation, human annotation, scraped-and-filtered). `challenge_hooks`
should frame the gap this dataset fills ("benchmark for long-context
retrieval faithfulness") rather than restating the dataset's name.

### `repo`

Applies to `github` content. `summary` should state what the repository
implements or automates, and at what level (library, framework,
end-to-end application, research reproduction). `concepts` should
include the primary framework or runtime it targets (a serving engine, an
orchestration framework, a vector store integration) and the problem
class it automates. `challenge_hooks` should frame the practitioner
problem the repo solves, not the repo's own README tagline. README badge
rows, build-status shields, and license boilerplate carry no extraction
signal — do not let them displace real content in `summary` or
`concepts` when a README is short and badge-heavy.

### `article`

Applies to blog-style and forum-style writing (`lesswrong`,
`paperswithcode` write-ups, and similar). `summary` should state the
article's actual claim or finding, not its narrative framing device.
Opinion and analysis pieces still need a concrete, checkable claim in the
summary — "argues that X causes Y under condition Z" rather than "reflects
on X". `concepts` should list the named ideas, papers, or prior debates
the article engages with. `challenge_hooks` should frame the open
question the piece raises for a practitioner, distinct from the piece's
own rhetorical question if it has one.

### `spec`

Technical specifications, RFCs, and design documents. `summary` should
state what the spec standardizes or constrains and at what layer (wire
protocol, API contract, data schema). `concepts` should include the named
standards, protocols, or prior specs it extends or supersedes.
`challenge_hooks` should frame the interoperability or design problem the
spec resolves.

### `idea`

Short-form proposals, position pieces, or early-stage concept write-ups
that are not yet backed by an implementation or dataset. `summary` should
state the proposed idea and its intended effect, flagged as a proposal
rather than a result — do not let the summary imply a result exists when
the source is explicitly speculative. `concepts` should list the prior
work the idea positions itself against. `challenge_hooks` should frame
the gap the idea claims to address, worded as a question a practitioner
would ask before the idea existed.

### `benchmark`

Leaderboards, evaluation suites, and benchmark-result write-ups distinct
from `dataset` entries in that the emphasis is the *comparison*, not the
underlying data. `summary` should name what is being compared, on what
axis, and the headline result or ranking if stated. `concepts` should
list the systems or methods being compared and the metric family used.
`challenge_hooks` should frame the evaluation gap the benchmark closes
("apples-to-apples latency comparison across serving engines under a
shared load profile").

### `other`

Reserved for content that does not cleanly fit the eight types above —
do not force a type. `summary`, `concepts`, and `challenge_hooks` follow
the same density and framing rules as every other type; only the type
label differs. If the content shape most resembles one of the eight
named types but is ambiguous, prefer the named type over `other` — this
label should be rare in a well-behaved extraction, not a default.

## 3. Per-source content-shape notes

Call 1's truncation strategy (a fixed transform, out of scope for this
annex and this plan) already reshapes the raw content differently per
source before it reaches the model. Extraction should account for the
shape it is actually given, not the shape the raw source would have had
before truncation.

### `arxiv`, `semantic_scholar`, `openreview` (paper sources)

Content typically arrives as an abstract followed by a truncated body
(introduction and, space permitting, early sections). Treat the abstract
as the highest-density source for `summary` and the body as the source
for `concepts` and `challenge_hooks` detail the abstract alone often
omits — named baselines, named datasets, and specific numeric results
frequently only appear in the body. `openreview` content may include
reviewer framing or a decision summary ahead of the paper body; do not
extract the review's meta-commentary about the paper as if it were the
paper's own content — extract the paper's contribution, not the review of
it.

### `github` (repo source)

Content typically arrives as a short header slice followed by a
structural digest (directory-like lines and list items) rather than full
prose, because long READMEs are truncated to a header plus structure
rather than a head-and-tail window. This means `summary` and `concepts`
often must be inferred from a combination of the header prose, the
repository's stated purpose line (usually near the top), and the
structural digest showing named modules, named integrations, or named
commands — a `pyproject.toml` or `requirements.txt` line naming a
framework is itself extraction signal for `concepts`. Do not treat
directory-listing noise (`__pycache__`, `.github/`, `node_modules/`) as a
concept.

### `huggingface` (model or dataset source)

Model-card content typically arrives as YAML front matter (base model,
license, task tags, sometimes benchmark numbers) followed by truncated
card prose. The YAML front matter is itself a rich extraction source —
`license`, `base_model`, `pipeline_tag`, and any `datasets:` or
`metrics:` keys frequently answer parts of `summary` and `concepts`
directly and more reliably than the prose that follows, which is often
marketing copy. Dataset-card content on `huggingface` follows the
`dataset` entry-type guidance above rather than the `model` guidance,
even though it shares the same source.

### `paperswithcode`, `lesswrong` (article sources)

Content typically arrives as a beginning-and-end window (an opening
slice plus a closing slice, with a truncation marker between them) rather
than a full linear read, because long articles are truncated from both
ends rather than just the head. This means the piece's stated conclusion
or takeaway is frequently present in the tail slice even when the body
argument in between is not — check the tail before assuming a claim is
unsupported by the given text. `paperswithcode` write-ups specifically
often reference a leaderboard position or a specific paper implementation
and should usually extract as `benchmark` or `repo` rather than generic
`article` when the content is dominantly a comparison or an
implementation writeup rather than discursive analysis.

## 4. Worked examples

Each example shows a truncated content excerpt as Call 1 would actually
receive it (post per-source truncation, pre-extraction) and the expected
extraction. These are illustrations of the rubric above, not a competing
schema — the JSON keys and value types are exactly the schema the system
prompt already defines.

### Example A — `paper`, source `arxiv`

Input excerpt (abstract + truncated body):

> Abstract: We present a method for reducing KV-cache memory in
> transformer decoding by sharing key/value projections across adjacent
> layers, evaluated on three open-weight model families. Our approach cuts
> peak KV-cache memory by 38% at matched perplexity on long-context
> benchmarks, with no architecture retraining required.
>
> 1. Introduction. Long-context serving is memory-bound rather than
> compute-bound on most inference hardware... [truncated]

Expected extraction:

```json
{
  "summary": "Cross-layer key/value projection sharing cuts peak KV-cache memory 38% at matched perplexity across three open-weight model families, with no architecture retraining required.",
  "concepts": ["KV-cache", "long-context serving", "key/value projection sharing", "inference memory footprint", "open-weight model evaluation"],
  "tags": ["inference", "serving", "optimization"],
  "entry_type": "paper",
  "challenge_hooks": [
    "how to reduce KV-cache memory for long-context inference without retraining the model",
    "memory-bound vs compute-bound tradeoffs in transformer decoding at long context lengths"
  ]
}
```

Note why this passes the rubric: the summary names the mechanism (layer
sharing) and the headline number (38%) instead of restating "a new method
for reducing memory"; `challenge_hooks` are phrased as a practitioner's
search query, not as a rephrased title.

### Example B — `repo`, source `github`

Input excerpt (header + structural digest):

> A lightweight router for splitting inference traffic across multiple
> vLLM backends by request SLA class.
>
> - src/
>   - router.py
>   - sla_classifier.py
>   - backends/
> - configs/
>   - sla_tiers.yaml
> - requirements.txt (fastapi, vllm, pydantic)

Expected extraction:

```json
{
  "summary": "A request router that classifies inbound inference traffic by SLA tier and dispatches to separate vLLM backend pools, implemented as a FastAPI service with a YAML tier configuration.",
  "concepts": ["vLLM", "request routing", "SLA-based dispatch", "FastAPI", "multi-backend serving"],
  "tags": ["serving", "orchestration", "production"],
  "entry_type": "repo",
  "challenge_hooks": [
    "how to route inference requests to different backend pools based on latency SLA",
    "operating multiple vLLM instances behind one entry point without a generic load balancer"
  ]
}
```

Note why this passes the rubric: `concepts` pulls the named framework
(`vLLM`, `FastAPI`) from the structural digest rather than treating the
directory listing as noise; `summary` states the mechanism (SLA-tier
classification, backend dispatch) rather than restating the one-line
repo tagline verbatim.

### Example C — `model`, source `huggingface`

Input excerpt (YAML front matter + truncated card prose):

> ---
> base_model: meta-llama/Llama-3.1-8B
> license: apache-2.0
> pipeline_tag: text-generation
> datasets: [synthetic-function-calling-v2]
> metrics: [tool_call_accuracy: 0.91]
> ---
>
> This is a LoRA fine-tune of Llama-3.1-8B specialized for structured
> function-calling and JSON-mode output... [truncated]

Expected extraction:

```json
{
  "summary": "A LoRA fine-tune of Llama-3.1-8B specialized for structured function-calling and JSON-mode output, trained on a synthetic function-calling dataset, reporting 0.91 tool-call accuracy.",
  "concepts": ["LoRA fine-tuning", "function calling", "structured output", "Llama-3.1-8B", "synthetic training data"],
  "tags": ["fine-tuning", "structured-output", "tool-use"],
  "entry_type": "model",
  "challenge_hooks": [
    "small model for reliable structured function-calling under a fine-tuning budget",
    "evaluating tool-call accuracy for LoRA-tuned open-weight models"
  ]
}
```

Note why this passes the rubric: the front matter's `datasets` and
`metrics` keys directly supplied the training-data claim and the 0.91
accuracy figure without needing the (truncated) prose; `concepts` names
the base model and the training technique rather than generic terms like
"language model".

### Example D — `article`, source `lesswrong`

Input excerpt (beginning-and-end window):

> Opening slice: Most discussions of alignment tax assume the tax is paid
> once, at deployment. I want to argue this framing hides a compounding
> cost that shows up during iteration, not deployment...
>
> [... truncated ...]
>
> Closing slice: ...so the practical upshot is that teams underestimate
> alignment tax by roughly the number of iteration cycles they expect to
> run, not just the deployment-time overhead. This suggests iteration
> count, not model size, is the dominant driver of total alignment cost
> for a given project.

Expected extraction:

```json
{
  "summary": "Argues that alignment tax compounds across iteration cycles rather than being paid once at deployment, and that iteration count — not model size — is the dominant driver of total alignment cost for a project.",
  "concepts": ["alignment tax", "iteration cost", "deployment-time overhead", "cost modeling for alignment work"],
  "tags": ["alignment", "safety"],
  "entry_type": "article",
  "challenge_hooks": [
    "how alignment tax scales with iteration count rather than one-time deployment cost",
    "estimating total alignment cost for a project before committing to an iteration budget"
  ]
}
```

Note why this passes the rubric: the extraction used the closing slice's
explicit conclusion rather than assuming the truncated middle made the
claim unrecoverable, and `summary` states the checkable claim (iteration
count is the dominant driver) rather than "reflects on alignment tax".

## 5. Boundary cases between entry types

Several entry-type pairs are genuinely ambiguous from truncated content
alone. Resolve them by asking what the source is *primarily doing*, not
by pattern-matching a keyword:

- **`dataset` vs `benchmark`.** A dataset release that ships with a
  leaderboard or a fixed evaluation protocol is still a `dataset` if the
  primary deliverable is the data itself; it is a `benchmark` if the
  primary deliverable is the comparison of systems against that data
  (a leaderboard page, a "state of the art" table, a benchmark paper that
  reports many models' scores rather than releasing a corpus). When both
  are plausible, prefer `dataset` for a first-party release announcement
  and `benchmark` for a third-party evaluation or leaderboard write-up.
- **`model` vs `repo`.** A `huggingface` model card is almost always
  `model`. A `github` repository that *wraps* a model (a serving harness,
  a fine-tuning script, an inference server) is `repo`, even if the
  README spends most of its space describing the underlying model's
  capabilities — the deliverable being distributed is the code, not the
  weights. If a `github` repo's primary artifact is a checkpoint release
  with the code as secondary tooling, prefer `model`.
- **`spec` vs `paper`.** A specification document that is also published
  as an academic paper (a protocol paper, a schema-standardization paper)
  is `spec` when the content is normative ("implementations MUST...",
  versioned field definitions) and `paper` when the content is
  descriptive or evaluative (motivating the design, presenting results
  about it) rather than normative. When an excerpt mixes both, the
  presence of versioned, binding requirement language is the stronger
  signal for `spec`.
- **`idea` vs `paper`.** A short position paper with no experiments and
  no dataset is `idea` even if it is formatted and hosted like a paper.
  The presence of a reported quantitative result — even a small one — is
  the deciding signal for `paper` over `idea`; the absence of any result
  and explicit hedging language ("we propose", "we speculate", "future
  work should investigate") favors `idea`.
- **`article` vs `benchmark` on `paperswithcode`.** Per §3 above, prefer
  `benchmark` when the write-up's dominant content is a comparison table
  or leaderboard position, and `article` when the dominant content is
  discursive analysis or commentary about a result rather than the result
  table itself.

None of these boundary calls change `summary`, `concepts`, or
`challenge_hooks` guidance — they only change which per-type extraction
guidance in §2 to apply. Getting the boundary call wrong is a smaller
extraction failure than picking the right type but writing a generic
summary; when genuinely torn between two adjacent types, prioritize
getting the other four fields right over deliberating further on the
type label.

## 6. Common failure modes to avoid

- Do not output a `summary` that is true of nearly any entry of the same
  `entry_type` — if the summary would still read naturally after swapping
  in a different paper's name, it has not extracted anything specific.
- Do not let `concepts` degrade into single-word genericisms ("AI",
  "machine learning", "model") when the source names specific techniques,
  architectures, or prior work.
- Do not phrase `challenge_hooks` as a restatement of the title with
  different word order. A hook should survive being read with the title
  removed from context.
- Do not invent numeric results, benchmark names, or dataset names that
  are not present in the given excerpt. A truncated excerpt that omits a
  result is a reason to omit that claim, not a reason to guess it.
- Do not let YAML front matter, README badges, or navigational boilerplate
  (table of contents, "Edit this page" links) leak into `summary` or
  `concepts` as if they were content.
