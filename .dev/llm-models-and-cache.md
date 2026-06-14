# LLM providers, models, and cache policies

Quick reference for which models and caching apply at each pipeline stage. Canonical constants live in `bishop_shared/anthropic_config.py` and `bishop_shared/indexing_config.py`.

**Last reviewed:** 2026-06-13 (as-built in repo)

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

| Stage | Default | Env var |
|-------|---------|---------|
| Pre-filter | 50 | `BISHOP_PREFILTER_BATCH_SIZE` |
| Enrichment stage 1 | 10 | `BISHOP_ENRICHMENT_STAGE1_BATCH_SIZE` |
| Enrichment stage 2 | 10 | `BISHOP_ENRICHMENT_STAGE2_BATCH_SIZE` |

All LLM calls use the Anthropic Batch API (~50% discount vs standard pricing per spec §12.1).

---

## Cache / cost policies

### Anthropic Batch API

Every LLM inference goes through the Batch API (async, non-urgent pipeline). `batch-poller` handles `pre_filter`, `enrichment_stage1`, and `enrichment_stage2` batch types.

### Prompt caching (`cache_control`)

| Stage | Caching in code? | Details |
|-------|------------------|---------|
| **Pre-filter** | **No** | Profile is a plain `system` string in `pre-filter-worker` — no `cache_control`. Spec §12.1 documents future caching when the NL profile grows past Anthropic's minimum token threshold ("Phase 1.5"); not wired yet. |
| **Enrichment Call 1** | **No** | Static taxonomy system prompt (`build_call1_system_prompt`); no profile injected. |
| **Enrichment Call 2** | **Yes** | Profile block: `cache_control: {"type": "ephemeral"}` via `build_call2_system_prompt` in `bishop_shared/enrichment_prompts.py`. Instructions block is not cached. Profile is likely still below Anthropic's caching threshold (~300–500 tokens today) — `cache_control` is emitted per spec but may no-op until the profile grows. See `.dev/decision-logs/m5-enrichment/T4-call2-cache-control.md`. |

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
