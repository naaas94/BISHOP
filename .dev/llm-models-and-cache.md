# LLM providers, models, and cache policies

Quick reference for which models and caching apply at each pipeline stage. Canonical constants live in `bishop_shared/anthropic_config.py` and `bishop_shared/indexing_config.py`.

**Last reviewed:** 2026-09-12 (as-built in repo, post prompt-caching plan T10-bis closure)

---

## Provider summary

| Provider | Used? | Where |
|----------|-------|-------|
| **Anthropic** | Yes | All LLM pipeline stages (pre-filter + enrichment) |
| **OpenAI** | No | Rejected in spec (§24); no SDK, env var, or code path |
| **Gemini / Google** | No | Rejected in spec (§24); no SDK, env var, or code path |
| **Local `sentence-transformers`** | Yes | Indexing (`vector-writer`) and query (`query-api`) — not an LLM API |

Only `ANTHROPIC_API_KEY` is wired in Docker Compose (`.env.example`, `pre-filter-worker`, `enrichment-batcher`, `batch-poller`).

---

## Anthropic model (all LLM stages)

Pinned dated snapshot — do not use undated aliases (`claude-haiku-4-5` returns HTTP 400 on Batch API).

| Constant | Value |
|----------|-------|
| `ANTHROPIC_MODEL_PREFILTER` | `claude-haiku-4-5-20251001` |
| `ANTHROPIC_MODEL_ENRICHMENT` | `claude-haiku-4-5-20251001` |

**G3 gate:** `verify_model_string()` in `bishop_shared/anthropic_config.py` probes the Messages API once before the first live batch submit. Dev bypass: `BISHOP_G3_VERIFIED=1`.

---

## Models by stage / service

| Stage / state flow | Service | Model | API | Max tokens |
|--------------------|---------|-------|-----|------------|
| **Pre-filter** (`DISCOVERED` → batch → relevance) | `pre-filter-worker` | `claude-haiku-4-5-20251001` | Anthropic **Batch** API | 256 |
| **Enrichment Call 1** (`SCRAPED` → factual extraction) | `enrichment-batcher` (stage1) | same | Anthropic Batch API | 1024 |
| **Enrichment Call 2** (`ENRICHMENT_STAGE2_*` → evaluative) | `enrichment-batcher` (stage2) | same | Anthropic Batch API | 512 |
| **Batch completion polling** | `batch-poller` | — (poll only) | Anthropic Batch API | — |
| **Vector indexing** (`VECTOR_WRITE_QUEUED` → `INDEXED`) | `vector-writer` | `sentence-transformers/all-MiniLM-L6-v2` (384-dim, local) | In-process | — |
| **Query retrieval** | `query-api` | same embedding + BM25 | In-process | — |

**Not implemented (spec only):**

- Cross-encoder reranker `ms-marco-MiniLM-L-6-v2` — deferred until RRF fusion feels noisy (§13.3).
- Embedding upgrade `nomic-embed-text` (768-dim via Ollama) — if quality gate G5 fails before backfill.

---

## Batch sizes and env overrides

Amortization controls added by the prompt-caching plan (T9-bis): each gate also
holds a partial batch open until `MIN_BATCH_SIZE` is reached, up to
`MAX_HOLD_MINUTES`, so small trickles of entries don't submit batches too
small to amortize a cache write. The hold clock is per-gate, in-process, and
resets on service restart (accepted, documented in
`.dev/decision-logs/prompt-caching/T9-bis-batch-amortization.md`).

| Stage | Batch size default | Batch size env var | Min batch size | Max hold (minutes) |
|-------|---------------------|---------------------|-----------------|---------------------|
| Pre-filter | 50 | `BISHOP_PREFILTER_BATCH_SIZE` | 25 (`BISHOP_PREFILTER_MIN_BATCH_SIZE`) | 120 (`BISHOP_PREFILTER_MAX_HOLD_MINUTES`) |
| Enrichment stage 1 | 50 (was 10) | `BISHOP_ENRICHMENT_STAGE1_BATCH_SIZE` | 10 (`BISHOP_ENRICHMENT_STAGE1_MIN_BATCH_SIZE`) | 120 (`BISHOP_ENRICHMENT_STAGE1_MAX_HOLD_MINUTES`) |
| Enrichment stage 2 | 50 (was 10) | `BISHOP_ENRICHMENT_STAGE2_BATCH_SIZE` | 10 (`BISHOP_ENRICHMENT_STAGE2_MIN_BATCH_SIZE`) | 120 (`BISHOP_ENRICHMENT_STAGE2_MAX_HOLD_MINUTES`) |

All LLM calls use the Anthropic Batch API (~50% discount vs standard pricing per spec §12.1).

---

## Cache / cost policies

### Anthropic Batch API

Every LLM inference goes through the Batch API (async, non-urgent pipeline). `batch-poller` handles `pre_filter`, `enrichment_stage1`, and `enrichment_stage2` batch types.

### Prompt caching (`cache_control`)

All three gates now emit a single `cache_control: {"type": "ephemeral", "ttl": "1h"}`
breakpoint on the **last** block of `params["system"]`, via the sole emitter
`bishop_shared/prompt_cache.py::cached_system_blocks` (prompt-caching plan,
landed 2026-09-12). Each gate's cached prefix is sized with a stamped,
hash-verified rubric annex (`config/prompts/*.md`) so the **total** prefix —
not the annex alone — clears Claude Haiku 4.5's 4,096-token minimum with a
10% margin (4,506), per `tests/test_prompt_cache_token_floor.py`. The three
cache keys (A/B/C) stay independent by construction — no shared prefix.

| Stage | Cache key | System blocks (breakpoint on last) | Measured tokens (`cl100k_base`) |
|-------|-----------|--------------------------------------|----------------------------------|
| **Pre-filter** | A | `[profile_render(professional_v1.2.0_soft_launch), prefilter_rubric]` | 5,057 (floor 4,506, margin 551) |
| **Enrichment Call 1** | B | `[call1_system, call1_rubric]` | 4,886 (floor 4,506, margin 380) |
| **Enrichment Call 2** | C | `[profile_render(professional_v1.0.0, include_output=False), call2_rubric, call2_instructions]` | 4,809 (floor 4,506, margin 303) |

Each rubric asset is image-baked (`Dockerfile` `COPY config/prompts`), never
bind-mounted, and hash-verified before every submit (hash-or-abort mirrors the
existing profile-hash abort; pre-filter additionally raises the CRITICAL
alert path, stage1/stage2 log-only, per the pre-existing M5 T4 asymmetry).
`batch-poller` logs `cache_read_tokens`, `cache_write_tokens`, `input_tokens`,
`output_tokens`, `cache_hit_ratio` on every batch completion (`cache_read_zero`
warning when both cache counters are zero) — see
`.dev/decision-logs/prompt-caching/`. **This `cl100k_base` measurement is a
proxy, not proof Anthropic cached anything** — the live falsifier is gate G1's
`cache_creation_input_tokens > 0` on a real batch (operator-run, not yet
executed as of this doc's last review).

`bishop_spec_0_6.md` §12.1/§12.3 still describe pre-filter caching as
"applies automatically" / "no code change required" with a ~1,024-token
framing — that language is now known-stale and was left uncorrected by
explicit operator decision (D6); do not treat the spec as current on caching.

### Embeddings

No API caching. `EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"` (`bishop_shared/indexing_config.py`) loaded in-process by `vector-writer` and `query-api`.

---

## Prompt context per stage

| Stage | System prompt | User prompt |
|-------|---------------|-------------|
| Pre-filter | Rendered NL profile (YAML → text) | `title` + `abstract` |
| Enrichment Call 1 | Static extraction schema + tag taxonomy | `title` + truncated `content_raw` (≤4k tokens) |
| Enrichment Call 2 | Profile (cached block) + evaluative instructions | `title` + `summary` from Call 1 only |

---

## Why not multi-provider?

From `bishop_spec_0_6.md` §24 (rejected items):

| Rejected | Chosen | Rationale |
|----------|--------|-----------|
| **Gemini Flash** (pre-filter) | Anthropic Batch API (Haiku) | Gemini context-caching minimum (1,024 tokens) exceeded initial profile size; single provider removes second API key and polling flow. |
| **GPT-4o-mini** (enrichment) | Anthropic Batch API (Haiku) | Cost negligible at projected volume; Haiku better structured-output fidelity; Batch API adds 50% discount and async fit. |

---

## Source files

| Concern | File |
|---------|------|
| Anthropic model constants + G3 gate | `bishop_shared/anthropic_config.py` |
| Embedding model + embed text builder | `bishop_shared/indexing_config.py` |
| Call 1/2 prompt builders + Call 2 cache | `bishop_shared/enrichment_prompts.py` |
| Pre-filter batch submit | `services/pre-filter-worker/app/anthropic_batch_client.py` |
| Enrichment batch submit | `services/enrichment-batcher/app/anthropic_batch_client.py` |
| Batch polling | `services/batch-poller/app/loop.py` |
| Spec (normative) | `bishop_spec_0_6.md` §12–13, §24 |
