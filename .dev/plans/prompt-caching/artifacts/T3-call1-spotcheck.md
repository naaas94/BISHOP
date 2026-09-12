# T3 spot-check — Call 1 extraction, before/after `call1_rubric_v1.md`

**Purpose.** Contract row 8 (token floor) and this packet's kill criteria have no
automated Call 1 eval gate for extraction *quality* — only token count is
gate-checked mechanically. This artifact is the manual mitigation named in the
packet's Risks & mitigations row: a live, side-by-side comparison of real Call 1
output with and without the `call1_rubric_v1.md` annex injected into the system
prompt, specifically watching for `challenge_hooks` degradation (spec §13.1: the
most load-bearing field for Layer 2 retrieval, with no automated Call 1 eval gate
to catch regression).

**Method.** 6 real entries were pulled read-only from the live `bishop.db`
(`entries` joined to `manifest`, filtered to `content_raw` present and >800
chars — all happened to be `arxiv` in the current DB snapshot; no `github` /
`huggingface` / article-source entries currently carry `content_raw` in this
DB, so this spot-check cannot exercise the annex's per-source notes for those
sources live — see Coverage gap below). Each entry's content was passed through
the existing, unmodified `truncate_content_for_call1()` and then sent live to
`claude-haiku-4-5-20251001` twice:

- **before** — `system=build_call1_system_prompt()` (current production prompt, no annex).
- **after** — `system=build_call1_system_prompt() + "\n\n" + <call1_rubric_v1.md body>` (this
  packet's annex appended, simulating what T6 will wire; T6 itself is out of
  scope for T3 and is not touched here).

No other input changed. This is a manual probe (`.dev/scratch/prompt-caching/T3_spotcheck_probe.py`,
not committed — throwaway per repo scratch convention) run once against the live API;
it is not a repeatable pytest gate and is not claimed as one.

## Results

### 1. `arxiv:2606.07924` — "Decoupling Semantics and Logic..." (video RAG)

| Field | Before | After |
|---|---|---|
| summary | Names BGE-M3, A.I.R. agent, "logic-gated exponential attenuation scoring" | Same named mechanisms; adds "iterative cognitive reranking" and clarifies retrieval targets "global summaries" |
| concepts | 8 items, appropriately specific (no genericisms) | 8 items, comparably specific; swaps "cognitive reranking agent" language for "Adaptive Iterative Reasoning (A.I.R.) framework" — slightly more precise |
| tags | 8 tags, all valid taxonomy | 6 tags — tighter, but `video-retrieval` is **not** in `TAG_TAXONOMY_ORDERED` and will be silently stripped by `validate_tags()` at the real pipeline stage (pre-existing model behavior under an unconstrained-vocabulary prompt in either variant; **not** introduced by the annex — the annex does not restate or alter the taxonomy per §2 row 6/C8) |
| entry_type | `paper` | `paper` — unchanged |
| challenge_hooks | 4 hooks, phrased as questions, reasonably specific | 4 hooks, phrased as statements (matches this annex's Example A style more closely), comparably specific — **no degradation** |

### 2. `arxiv:2606.07951` — "From 'May' to 'Is'..." (certainty distortion)

| Field | Before | After |
|---|---|---|
| summary | Names the 75% distortion rate and 1.5–2× bias | Same numbers retained; adds "compounds over repeated paraphrasing iterations" |
| concepts | 8 items | 7 items; drops "domain-specific bias" as a concept but summary still covers it in prose — net neutral |
| tags | 5 tags (adds `benchmark`) | 4 tags (adds `NLP`) — both valid, comparably specific |
| entry_type | `paper` | `paper` — unchanged |
| challenge_hooks | 3 hooks, all specific and non-title-restating | 3 hooks, comparably specific, one now explicitly names "epistemic faithfulness separately from factuality" — **no degradation**, arguably sharper |

### 3. `arxiv:2606.08153` — "LogNEO" (log anomaly detection)

| Field | Before | After |
|---|---|---|
| summary | Reports F1≥0.913, 45ms/15k events/s | Reports **F1 0.927–0.984** (a range, not a single floor) at the same latency/throughput — after-run pulled a more precise number from the same source text |
| concepts | 7 items | 7 items; adds "Drain log parser" (a named tool from the source, matches this annex's `paper` guidance to name specific prior work) and "microservice deployment architecture" |
| tags | 7 tags | 6 tags; adds `serving` (accurate — the paper is about real-time serving) |
| entry_type | `paper` | `paper` — unchanged |
| challenge_hooks | 3 hooks | 4 hooks — adds one naming the prior baseline ("LogGPT") by name, following this annex's `paper` guidance ("named prior work... it compares against") — **no degradation, closer rubric adherence** |

### 4. `arxiv:2606.08200` — "Online Agent-as-a-Judge"

| Field | Before | After |
|---|---|---|
| summary | Describes the mechanism generically | After names the eval scale ("32 designer-authored criteria in a family simulation") and states a comparative result ("improves... over passive offline baselines") — more specific, matching this annex's §1 anti-genericism guidance |
| concepts | 8 items | 7 items, comparably specific |
| tags | 5 tags | 4 tags, comparably specific |
| entry_type | `paper` | `paper` — unchanged |
| challenge_hooks | 4 hooks | 3 hooks — fewer, but each is at least as specific; one before-hook ("Scaling situated evaluation... without manual playtesting") reappears reworded in after — **no degradation** |

### 5. `arxiv:2606.08529` — "Scaffold Effects on GAIA"

| Field | Before | After |
|---|---|---|
| summary | Reports "up to 28 percentage points" gap | Same number retained; adds a specific qualifier absent before ("scaffold effects vary by model family rather than capability tier... within Anthropic family but not cross-provider") — strictly more specific |
| concepts | 8 items | 8 items, comparably specific |
| tags | 7 tags | 6 tags, comparably specific |
| entry_type | `paper` | `paper` — unchanged |
| challenge_hooks | 3 hooks (questions) | 3 hooks (statements) — comparably specific; after-hook 3 narrows to "multi-agent or planning-focused scaffolds... across model families and difficulty levels", roughly equal specificity to before — **no degradation** |

### 6. `arxiv:2606.08571` — "Structured Ignorance Certificates"

| Field | Before | After |
|---|---|---|
| summary | Names GRPO, 7,347 samples, 99.46% JSON validity | Same facts retained; adds the base model (**Qwen3-14B**) and a second metric ("0.967 Certificate Specificity Score") the before-run omitted — strictly more specific |
| concepts | 8 items | 7 items, comparably specific |
| tags | 7 tags | 7 tags, comparably specific |
| entry_type | `paper` | `paper` — unchanged |
| challenge_hooks | 4 hooks | 3 hooks — fewer but each retained is comparably specific; no title-restatement in either variant — **no degradation** |

## Verdict against this packet's kill criterion

**Kill criterion:** "HALT if the spot-check shows `challenge_hooks` degrading in
specificity."

Across all 6 entries, `challenge_hooks` in the **after** run is never less
specific than the corresponding **before** hook, and in three cases (2, 3, 5)
the after-run names a specific prior method, dataset, or comparison the
before-run did not. `entry_type` was unchanged (`paper`) in all 6 cases —
expected, since all 6 sampled entries are `arxiv` papers with no ambiguous
boundary case (see Coverage gap). No `summary` regressed toward genericism;
three summaries (3, 5, 6) became strictly more specific. **Criterion satisfied:
no degradation observed. Not HALTing.**

## Coverage gap (named, not closed here)

All 6 entries available in the live DB with non-trivial `content_raw` are
`source=arxiv`. This spot-check therefore validates the annex's `paper`
entry-type guidance and the `arxiv`/`semantic_scholar`/`openreview` per-source
note, but does **not** live-validate the annex's `repo` (`github`), `model`
(`huggingface`), or `article` (`lesswrong`/`paperswithcode`) guidance, nor any
`dataset`/`spec`/`idea`/`benchmark`/`other` entry_type — those sources/types
are not yet populated with `content_raw` in this DB snapshot. This is a data
availability gap, not a scope reduction of this packet: T3's annex content
(§2, §3 of the annex) is authored for all seven sources and nine types per the
packet's task statement, and §2.1's mutation-checked pytest falsifier
(`tests/test_rubric_assets.py::test_call1_rubric_v1_asset_exists_and_verifies`)
covers the asset's structural integrity regardless of source mix. The
live-behavior claim in this artifact is scoped to `paper`/`arxiv` only; a
future backfill cycle that populates `github`/`huggingface`/article content
would be the natural point to re-run this same probe against those sources —
no orchestrator subtask in this plan currently owns that re-run, so it is not
named as a landing gate here beyond this note.
