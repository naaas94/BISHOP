# BISHOP — Anthropic Prompt Caching Strategy

**Version:** 0.3.0  
**Date:** 2026-06-14  
**Status:** Reference (not yet implemented beyond Call 2 `cache_control` wiring)

Companion to `bishop_spec_0_6.md` §12.3 (bootstrapping cycle) and M5 Call 2 decision log. Captures research and architecture notes from the 2026-06-14 caching review.

---

## 1. Why the Console Shows "Not Using Prompt Caching"

The Anthropic developer console Caching tab shows an empty state when **zero cache activity** (`cache_creation_input_tokens` + `cache_read_input_tokens`) occurred in the selected period. For BISHOP today, that is expected for **two independent reasons**:

### 1a. Most traffic has no `cache_control` (primary)

Anthropic prompt caching is **opt-in**. Repeating the same system prompt across requests is not enough — cacheable content must be marked with a `cache_control` block.

| Path | `cache_control`? | Notes |
|------|------------------|-------|
| Pre-filter batches | **No** | Plain string `system` prompt |
| Enrichment Call 1 | **No** | Plain string `system` prompt (taxonomy + schema) |
| Enrichment Call 2 | **Yes** | Ephemeral on NL profile block |
| G3 model probe | **No** | One-off `messages.create` ping |

Pre-filter is likely the bulk of Anthropic usage (every `DISCOVERED` entry). Those requests never declare caching, so the dashboard correctly reports no caching for that traffic.

**Code references:**

- Pre-filter: `services/pre-filter-worker/app/anthropic_batch_client.py` — `"system": system_prompt` (string)
- Call 1: `services/enrichment-batcher/app/anthropic_batch_client.py` — `"system": system_prompt` (string)
- Call 2: `bishop_shared/enrichment_prompts.py` — `build_call2_system_prompt()` returns content blocks with `cache_control: {"type": "ephemeral"}` on the profile block

### 1b. Cached prefix is below the model minimum (secondary)

Even Call 2, which already emits `cache_control`, cannot cache yet because the marked block is too short.

**Measured (2026-06-14):** rendered NL profile `professional_v1.0.0` ≈ **383 tokens** (`cl100k_base`), ~1,860 chars.

**Anthropic minimum cacheable prefix ([prompt caching docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)):**

| Model | Min cacheable prefix |
|-------|----------------------|
| Sonnet 4.5 / 4.6 | 1,024 tokens |
| **Claude Haiku 4.5** (BISHOP pinned model) | **4,096 tokens** |
| Opus 4.6 / 4.5 | 4,096 tokens |

Shorter prefixes are processed **without error** but **without caching**. Verify via batch result `usage`: if both `cache_creation_input_tokens` and `cache_read_input_tokens` are 0, nothing was cached.

> **Spec drift:** `bishop_spec_0_6.md` §12.3 and related prose assume ~1,024 tokens and a ~300–500 token profile. That threshold applies to Sonnet-class models, **not** Haiku 4.5. BISHOP uses `claude-haiku-4-5-20251001` everywhere — the operative floor is **4,096 tokens**.

M5 decision log (`T4-call2-cache-control.md`) noted caching may no-op until the profile grows; the actual gap is larger than assumed at spec time.

---

## 2. Batch API + Prompt Caching

### 2a. They stack

Per [Batch processing docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing):

- Message Batches **supports** `cache_control` in batch request `params`
- **Batch 50% discount** and **caching discounts stack**
- BISHOP's `messages.batches.create` path is valid for caching

### 2b. Cache hits are best-effort in batch

Batch requests are processed **asynchronously, concurrently, and out of order**. Cache hits are **best-effort** — reported hit rates typically **30–98%** depending on traffic shape.

To maximize hits within a batch:

1. Include **identical** `cache_control` blocks in **every** request in the batch
2. Structure requests so the **shared prefix is byte-identical** across all requests
3. Place dynamic per-entry content **after** the cache breakpoint (user message tail)

### 2c. `max_tokens: 0` pre-warming is not allowed in batches

Anthropic rejects `max_tokens: 0` inside batch requests. A cache entry written during batch processing would likely expire before a follow-up synchronous request runs. Pre-warming must use a real batch request or a synchronous Messages API call outside the batch.

---

## 3. Cache TTL: 5 Minutes vs 1 Hour

### 3a. Pricing (Claude Haiku 4.5)

| Category | Multiplier vs base input | Haiku 4.5 $/MTok |
|----------|--------------------------|------------------|
| Base input | 1× | $1.00 |
| 5m cache **write** | 1.25× | $1.25 |
| 1h cache **write** | 2× | $2.00 |
| Cache **read** (hit) | 0.10× | $0.10 |
| Output tokens | — | $5.00 (unchanged) |

Batch API applies **50%** to all of the above when using Message Batches.

Savings range advertised by Anthropic (50–90% on input) depends on read/write ratio. Reads at 10% of base are where the 90% figure comes from; writes at 1.25× or 2× are the upfront cost.

### 3b. TTL behavior

| TTL | Default | Timer reset | Best for |
|-----|---------|-------------|----------|
| 5 min | `{"type": "ephemeral"}` | Resets on each cache **hit** | Steady interactive traffic (<5 min between requests) |
| 1 hour | `{"type": "ephemeral", "ttl": "1h"}` | Resets on each cache **hit** | Bursty / async / batch workloads |

**For BISHOP:** batches can take **longer than 5 minutes** to process. Anthropic explicitly recommends **1-hour TTL** for batch workloads with shared context.

### 3c. Recommended batch warm-up pattern (Anthropic)

For large batches with a shared prefix:

1. Submit a **single** batch request containing only the shared prefix + `cache_control` with `ttl: "1h"` → writes cache
2. Wait for completion
3. Submit the full batch → subsequent requests read from cache

Within a **single** batch of ≤50 entries with identical system blocks, intra-batch reuse often works (first request writes, later ones read) but is not guaranteed due to concurrent processing.

### 3d. Concurrent requests caveat

A cache entry only becomes available **after the first response begins**. Parallel requests sent before that may all miss and each pay write cost. Within a batch this is partially mitigated by Anthropic's scheduler but remains best-effort.

---

## 4. Cost Leverage: Input vs Output

**Caching only affects input tokens.** Output is always full price.

BISHOP's LLM outputs are intentionally small:

- Pre-filter: `{"decision": 0|1, "rationale": "..."}` (~60 token cap on rationale)
- Call 1: structured JSON (summary, concepts, tags, entry_type, challenge_hooks)
- Call 2: structured JSON (relevance_score, relevance_reason, value_rationale)

The economic and quality leverage is in **rich static input prefixes** (rubrics, taxonomy, few-shot examples, NL profile) — not in lengthening outputs. Investing in better **reasoning via prompts** is the right axis; output token cost stays secondary.

---

## 5. Per-Path Caching Design

Each pipeline stage has a **different job** and should have a **different cached prefix**. Do not merge pre-filter, Call 1, and Call 2 into one mega-prompt.

### 5a. Pre-filter (highest volume — priority)

**Stable prefix (cache):**

- Rendered NL profile (`bishop_shared/profile_renderer.py`)
- Evaluation principles, anchors, exclusions
- Output format contract
- **Few-shot pass/reject examples** (quality + token padding toward 4k)
- Source-type guidance (e.g. ArXiv vs repo vs article heuristics)

**Dynamic tail (no cache):**

- Per-entry title + abstract

**Current gap:** no `cache_control` in `pre-filter-worker` batch client. Must add when implementing caching.

### 5b. Enrichment Call 1 (extraction)

**Stable prefix (cache):**

- Taxonomy list (`bishop_shared/tag_taxonomy.py`)
- JSON schema and extraction instructions (`build_call1_system_prompt()`)
- Domain guidance, challenge_hooks framing rules
- Few-shot extraction examples

**Dynamic tail (no cache):**

- Per-entry title + truncated content

**Current gap:** no `cache_control` on Call 1 system prompt.

### 5c. Enrichment Call 2 (relevance scoring)

**Stable prefix (cache) — target layout:**

- NL profile + eval schema + relevance few-shots — all **before** the `cache_control` breakpoint on the **last** system block (see §5e)
- **Today:** `cache_control` sits on profile block only; eval schema is a second system block **after** the breakpoint → full input price every row even though the schema is byte-identical across the batch

**Dynamic tail (no cache):**

- Per-entry title + summary (never `content_raw`)

**Current gaps:** profile block ~383 tokens; breakpoint placement suboptimal; needs ~3,700+ more tokens inside the cached prefix plus `cache_control` moved to last system block (§5e).

### 5d. Prompt structure pattern

```
system:
  [static block 1: profile / taxonomy / rubric]
  [static block 2: schema + few-shots]
  [cache_control: ephemeral, ttl: 1h]  ← on LAST system block only
messages:
  [user: per-entry dynamic content — never cache_control here]
```

Cached prefix = everything from request start through the block marked with `cache_control` (inclusive). Target **≥ 4,096 tokens** in that prefix for Haiku 4.5.

Up to **4 cache breakpoints** per request. Longer TTL blocks must appear **before** shorter TTL blocks if mixing.

### 5e. Cache breakpoint semantics

`cache_control` marks the **end of the cached prefix**, not the whole request.

| Rule | Detail |
|------|--------|
| Byte-identical requirement | Applies only from request start **through** the `cache_control` block |
| After the breakpoint | Billed as full input on every request — even if byte-identical across rows |
| User message | Must stay **after** the breakpoint; varies per entry |
| Never | Put `cache_control` on user content — cache key would include per-entry data → no hits |

**Call 2 today** (`bishop_shared/enrichment_prompts.py`):

```
[CACHED PREFIX — profile only, cache_control here]
[FULL PRICE EVERY ROW — eval schema; identical but after breakpoint]
[FULL PRICE EVERY ROW — user: title + summary]
```

**Recommended fix:** single system array — profile, then schema, then few-shots, with `cache_control` + `ttl: "1h"` on the **last** system block. All static system content then shares cache read pricing once the prefix exceeds 4,096 tokens.

### 5f. Input budget vs context window

Haiku 4.5 **200,000-token** context window ([models overview](https://platform.claude.com/docs/en/about-claude/models/overview)). The 4,096-token cache minimum is a **floor** for caching eligibility, not a ceiling on prompt size.

**Per-request input budget (estimated, `cl100k_base`):**

| Path | Cached prefix | Dynamic tail (typical / max) | `max_tokens` | ~Input + reserved output | vs 200k |
|------|--------------|------------------------------|--------------|--------------------------|--------:|
| Pre-filter | ~4,096 | ~50–500 / **no cap today** | 256 | ~5–6.5k | <4% |
| Call 1 | ~4,096 | title + content, **capped 4,000** (§13.1) | 1,024 | ~9.2k | <5% |
| Call 2 | ~4,096+ | title + summary (~50–100) | 512 | ~4.8k | <3% |

BISHOP is nowhere near context limits. The relevant constraints are cache eligibility and rubric quality, not model capacity.

**Prompt layout:** static system instructions first, dynamic user content last — appropriate for classification and extraction (model attends to rubric, then the item under judgment).

**Optional hardening:** pre-filter sends `title + abstract` with **no truncation** (`PreFilterBatchEntry.user_message()`). Manifest abstracts are usually short; a future adapter could supply a long blurb. Spec §13.1 truncation applies to enrichment Call 1 only. Consider a pre-filter user-tail cap (~500–1,000 tokens) independent of the cached block.

---

## 6. Quality and Caching Alignment

Growing prompts for **pre-filter precision** (e.g. ArXiv false-positive patterns noted in `relevance_log.md`) and hitting the **4,096-token cache floor** are aligned goals but not identical:

| Goal | Mechanism |
|------|-----------|
| Better relevance decisions | Richer anchors, exclusions, few-shot examples, source-specific rules |
| Cache eligibility | Same static content ≥ 4,096 tokens, byte-identical across batch, `cache_control` present |
| Auditability | `canonical_hash` on profile YAML; `profile_render_hash` on `BatchRecord` |

Any change to cached prefix content invalidates the cache entry and requires a new write. Profile updates must bump `canonical_hash` and expect one batch cycle of write-priced tokens.

**Do not pad with noise** solely to hit 4k — use substantive rubric content (examples, edge cases, source heuristics) that also improves filter quality.

---

## 7. Spec / Charter Notes

| Artifact | What it says | Gap |
|----------|--------------|-----|
| `bishop_spec_0_6.md` §12.3 Phase 1.5 | Caching applies "automatically" when profile crosses threshold; "no code change required" | Half true: Call 2 has `cache_control`; pre-filter and Call 1 still need it. Threshold for Haiku 4.5 is **4,096**, not 1,024. |
| Charter M5 §344 | Call 2 uses `cache_control` blocks | Landed in `enrichment_prompts.py` |
| Charter M3 | Pre-filter eligible for caching once profile grows | Not wired in code; threshold understated |

---

## 8. Break-Even Intuition

For a 50-entry batch with a 4k-token shared prefix (Haiku 4.5, 1h TTL, batch discount):

- **Without caching:** 50 × 4k = 200k input tokens at batch input rate
- **Ideal caching:** 1 × 4k write (@ 2×) + 49 × 4k read (@ 0.10×) + 50 × small dynamic tails
- Write premium pays off when the same prefix gets **multiple reads** before TTL expiry

A full batch with identical system blocks is the ideal shape. Separate batches hours apart need `ttl: "1h"` or accept re-writes on expiry.

### 8a. Scale reference

Makes the 4,096-token cache floor tangible. Measured 2026-06-14 with `cl100k_base` (approximation; confirm via batch result `usage` in production).

| Reference | Tokens | vs 4,096 min |
|-----------|-------:|-------------:|
| NL profile (rendered `professional_v1.0.0`) | 383 | 9% |
| Call 1 system prompt (`build_call1_system_prompt()`) | 267 | 7% |
| **Haiku 4.5 cache minimum** | **4,096** | 100% |
| `auditor-review` `SKILL.md` (longest local skill) | 7,786 | 190% |
| `.dev/caching_strategy.md` (this doc, v0.3) | ~6,900 | 168% |
| Gap: profile → minimum | ~3,713 | need ~91% more content |

**4,096 tokens ≈ first ~327 of 615 lines** of `auditor-review` (~53%) — from frontmatter through Phase 4 adversarial testing, before re-audit discipline and finding-classification tables.

**Authoring scale:** three separate ~4k rubrics (pre-filter, Call 1, Call 2) ≈ **~1.5× auditor-review** total static content across pipeline paths — large but consistent with existing skill/doc authoring volume. Call 1 cannot reach 4k by growing the NL profile alone (spec §5.4: Call 1 has no profile context); it needs a dedicated `call1_rubric` asset (§16).

---

## 9. Document map

| Section | Topic |
|---------|--------|
| §1–8 | Baseline strategy (console diagnosis, batch+TTL, per-path design, break-even) |
| §5e–5f | Cache breakpoint semantics; input budget vs 200k context window |
| §8a | Scale reference (auditor-review ruler, token counts) |
| §10–18 | Adversarial pass — multi-source, daily schedule, backfill scale |

---

## 10. Adversarial Review (Red Team)

Second-pass review against multi-source steady-state, daily schedules, and §18 backfill scale. Items below are **gaps or risks in v0.1.0** that must inform implementation.

### 10a. Severity summary

| ID | Finding | Severity | v0.1.0 covered? |
|----|---------|----------|-----------------|
| R1 | Haiku 4.5 requires **4,096** tokens — Call 1 system is only ~267 tokens; growing profile alone is insufficient for Call 1 | High | Partial |
| R2 | Mixed-source batches share one cached prefix — ArXiv-centric few-shots may hurt GitHub/LW/OpenReview precision | High | Mentioned, not resolved |
| R3 | Enrichment batch size **10** vs pre-filter **50** — fewer intra-batch cache reads on Call 1/2 | Medium | No |
| R4 | Backfill inter-chunk delay (default **300s**) + overnight quiet can exceed **1h TTL** → silent re-writes | Medium | No |
| R5 | No cache metrics in `batch-poller` / `BatchRecord` — flying blind during G6 calibration and G7 backfill | High | No |
| R6 | Three workers submit **different** cached prefixes concurrently — correct, but triple write cost on cold start | Medium | No |
| R7 | Profile version bump mid-backfill invalidates cache **and** aborts batches via `canonical_hash` | Medium | Partial |
| R8 | Duplicate Anthropic batches from sweep/retry pay write premium again | Medium | No |
| R9 | Pre-warm-before-batch pattern not implementable in current worker loops | Medium | Listed as optional only |
| R10 | Call 2 eval instructions sit **outside** cached block — wasted input + missed token budget toward 4k | Low | No |
| R11 | Per-source batch splitting as alternative strategy not evaluated | Low | No |
| R12 | Steady-state daily volume may be too low for caching ROI without backfill | Low | No |

---

## 11. Multi-Source Architecture

### 11a. How batches are assembled today

- **Pre-filter:** one poll claims up to 50 `DISCOVERED` entries; batch can mix `arxiv`, `github`, `semantic_scholar`, etc. All share **one** rendered NL profile as `system` (same `domain`, currently `professional` only).
- **User tail:** `title + abstract` per entry (`PreFilterBatchEntry.user_message()`). Sources without abstracts send title-only — variable tail length, **does not** affect prefix cache.
- **Enrichment Call 1:** polls `SCRAPED` entries (post-filter); per-source truncation in **user** message only (`bishop_shared/content_truncation.py` — paper vs repo vs article strategies). System prompt is source-agnostic.
- **Enrichment Call 2:** title + summary only; source-agnostic.

**Caching implication:** prefix cache is **per pipeline stage**, not per source. One cache key per stage per profile version.

### 11b. Unified rubric vs per-source cache keys

| Approach | Cache behavior | Quality risk |
|----------|----------------|--------------|
| **A. Unified multi-source rubric** (recommended) | Single 4k+ prefix for all sources in a batch; maximum hit rate | Must balance ArXiv paper heuristics with repo README / forum post / HF model-card patterns in one static block |
| **B. Split batches by `source`** | Separate cache entry per source; source-specific few-shots | Smaller batches, more Anthropic batch jobs, more cache writes, worse batch discount amortization |
| **C. Dynamic source in system prompt** | `system` includes `entry.source` | **Breaks prefix identity** across requests — cache miss on every row. **Do not do this.** |

**Red-team verdict:** the doc’s “source-type guidance” must be a **multi-source** appendix inside the cached block (ArXiv + GitHub + OpenReview + HF + LessWrong + Semantic Scholar), not ArXiv-only examples drawn from `relevance_log.md`. Source-specific signal belongs in the **user tail** (e.g. prefix `Source: github\n` in user message) if needed — that tail is uncached and cheap relative to a 4k prefix.

### 11c. Pre-filter is the multi-source cost gate

Per spec §18.3: 60-day ArXiv backfill alone ≈ **30,000** manifest rows; most rejected at pre-filter. All seven sources backfilling produce **tens of thousands** of pre-filter API calls; enrichment volume is gated by pass rate.

**Caching priority order at scale:**

1. Pre-filter (highest call count, every manifest row)
2. Call 1 (every `RELEVANCE_PASSED` row — ~5–15% of manifest at calibration)
3. Call 2 (same pass rate as Call 1)

---

## 12. Daily Schedule and TTL Dynamics

### 12a. Steady-state cadence (post-M8)

| Worker | Default poll | Default batch size |
|--------|--------------|-------------------|
| `pre-filter-worker` | 60s | 50 |
| `enrichment-batcher` | 120s | 10 (stage 1 and 2) |
| `batch-poller` | 120s | — |
| Scrapers | per-source schedule (Appendix B) | — |

During active hours, scrapers on staggered intervals feed manifest rows; pre-filter submits a batch roughly every minute when backlog exists. **Within a busy window**, `ttl: "1h"` cache should stay warm via hits across consecutive batches.

### 12b. When the cache goes cold

| Gap pattern | Risk | Mitigation |
|-------------|------|------------|
| Overnight / weekend quiet (>1h no batches) | First morning batch pays **1h write** (2×) on full prefix | Acceptable at steady-state volume; monitor `cache_creation_input_tokens` |
| Backfill `BISHOP_BACKFILL_INTER_CHUNK_DELAY_SEC` (default 300s) | Safe for 1h TTL **if** pre-filter keeps processing between chunks | If manifest drains and workers idle between chunks, cache may expire before next chunk’s manifest lands |
| Anthropic batch processing >1h | Requests in one batch may miss if cache expires mid-flight | Use `ttl: "1h"`; consider warm-up pattern for very large batches |
| Profile `canonical_hash` change | Instant invalidation of all prefix caches | Freeze profile during G7 backfill; bump version only between calibration cycles |

**Red-team verdict:** default **5m TTL is wrong for BISHOP** on all batch paths. Use **`ttl: "1h"`** everywhere. Revisit only if steady-state traffic is continuous sub-5-minute intervals *and* cost telemetry shows 1h write premium exceeds savings (unlikely at backfill scale).

### 12c. Rate limits during backfill

Anthropic docs: **cache hits do not deduct from input-tokens-per-minute rate limits.** At backfill scale, caching is not only a cost optimization — it reduces throttling risk on the pre-filter flood.

---

## 13. Backfill Scale Economics

### 13a. Order-of-magnitude (calibration assumptions)

Illustrative ArXiv-only floor from spec §18.3:

| Stage | Volume (60d ArXiv cs.AI+CL+LG) | Notes |
|-------|----------------------------------|-------|
| Manifest | ~30,000 | cheap SQLite |
| Pre-filter API calls | ~30,000 | **every row** |
| Enrichment (10% pass) | ~3,000 × 2 calls | Call 1 + Call 2 |

All-sources backfill multiplies manifest volume. Pre-filter dominates LLM cost regardless of pass rate.

### 13b. Caching impact at scale (Haiku 4.5, batch + 1h cache)

Assume 4,096-token cached prefix, 50-row pre-filter batch, batch 50% discount:

| Scenario | Prefix input cost shape (relative) |
|----------|-----------------------------------|
| No caching | 50 × 4096 = 204,800 prefix tokens **per batch** at full batch input rate |
| Ideal caching | 1 × write (2×) + 49 × read (0.10×) per batch |
| Cold start / TTL expiry | Extra write (2×) per prefix per hour of idle |

Across 600 pre-filter batches (30k rows): ideal caching reduces prefix input charges by **~90%** on the cached block; dynamic tails (title+abstract, ~50–300 tokens each) remain full price.

**Without reaching 4,096 tokens, none of this applies** — backfill runs at full input price for the entire rubric on every call.

### 13c. Backfill-specific operational rules

1. **Do not enable G7 backfill until** caching is wired **and** prefix ≥ 4,096 tokens **or** accept full input cost for the calibration run (explicit budget decision).
2. **Freeze NL profile** (`canonical_hash`) for the duration of a backfill tranche; iterate profile only between tranches.
3. **Tune batch sizes for cache amortization** during backfill:
   - Pre-filter: consider raising toward 100–200 while watching 48h batch timeout (spec allows up to 10,000 requests/batch).
   - Enrichment: default **10** means only 9 cache reads per batch on Call 1/2 — consider `BISHOP_ENRICHMENT_STAGE*_BATCH_SIZE=50` during backfill via env.
4. **Chunk manifest ingestion** (§18.4) limits SQLite blast radius but creates **pipeline waves**: scraper chunk → manifest swell → pre-filter batches → enrichment lag. Cache stays warm if pre-filter keeps pace; if enrichment falls behind, Call 1/2 caches still benefit from continuous enrichment batches once SCRAPED backlog builds.
5. **Same pipeline, no special mode** (§18.1) — caching config must work for steady-state and backfill without a “backfill mode” fork. Use **env-tunable batch sizes** only.

---

## 14. Three-Stage Cache Topology

BISHOP runs three independent Anthropic batch submitters:

```
pre-filter-worker  →  cache key A  (NL profile + pre-filter rubric)
enrichment stage1  →  cache key B  (taxonomy + Call 1 schema + examples)
enrichment stage2  →  cache key C  (NL profile + Call 2 eval rubric)
```

- Keys A and C share the NL profile text but **differ** in trailing instructions and breakpoint structure — Anthropic treats them as **different prefixes**. Expect **separate writes** for A and C even when profile text is identical.
- On cold start or after TTL expiry, **three write premiums** hit before steady hit rates emerge.
- `enrichment-batcher` runs stage 1 and stage 2 in parallel (`asyncio.gather`) — both may submit batches in the same tick, racing on cache creation for their respective keys.

**Breakpoint placement (§5e):** move Call 2 `cache_control` to the **last** system block so profile + eval schema + few-shots share one cached prefix. Current placement (breakpoint on profile only) leaves schema outside the cache region.

---

## 15. Observability and Failure Modes

### 15a. Missing today

`batch-poller` does not parse or persist Anthropic result `usage` fields:

- `cache_creation_input_tokens`
- `cache_read_input_tokens`
- `input_tokens` / `output_tokens`

**Required for caching rollout:**

- Log per-batch cache hit ratio at `batch-poller` completion (aggregate across result rows).
- Optional: extend `BatchRecord` with `cache_read_tokens` / `cache_write_tokens` sums for G6/G7 dashboards.
- Alert if `cache_read_input_tokens == 0` across N consecutive completed batches after caching enabled (misconfiguration detector).

### 15b. Duplicate batch cost leak

Spec §6.2 sweep caveat: lock-state recovery can produce **duplicate Anthropic batches** for the same `source_id`. Each duplicate pays output tokens and may pay **cache write** if it races as the first request on a cold prefix. Caching does not deduplicate logical work — idempotency is at state-worker, not Anthropic billing.

**Mitigation:** monitor `BatchRecord` count per `source_id`; caching strategy does not replace sweep tuning.

### 15c. Profile hash abort vs cache invalidation

`canonical_hash` mismatch aborts batch submit before Anthropic sees the request. Profile edit during active backfill:

- Aborts in-flight worker cycles (good — no silent drift)
- Invalidates Anthropic-side cache entries for old prefix (stale entries expire via TTL)

**Playbook:** profile iteration → bump semver + `canonical_hash` → expect one cold-cache cycle → resume backfill.

---

## 16. Prefix Content Strategy (Revised)

v0.1.0 implied growing the NL profile YAML toward 4k tokens. Red-team revision:

| Cached block | Target content | ~Token budget |
|--------------|----------------|---------------|
| **Pre-filter (key A)** | NL profile + multi-source pass/reject few-shots (≥1 example per major source) + cross-source exclusion rules | ≥ 4,096 |
| **Call 1 (key B)** | Taxonomy + schema + **per-`entry_type` extraction examples** + per-source content-shape notes (paper vs README vs thread) | ≥ 4,096 (currently ~267 — needs dedicated `call1_rubric` asset, not just profile growth) |
| **Call 2 (key C)** | NL profile + eval schema + relevance scoring few-shots (pass/marginal/reject with scores) | ≥ 4,096 |

**Do not** bloat `context:` in the YAML with filler. Prefer structured annexes:

- `config/prompts/prefilter_rubric_v1.md` (or YAML section) — versioned, hash-verified separately or folded into `canonical_hash` computation with explicit decision log.
- `config/prompts/call1_rubric_v1.md` — independent of NL profile; Call 1 explicitly does not use profile today (spec §5.4).

Any rubric change must participate in the same hash-or-abort discipline as the profile.

---

## 17. Rejected Alternatives (Documented)

| Alternative | Why rejected |
|-------------|--------------|
| Switch to Sonnet 4.5 for lower cache minimum (1,024) | Breaks G3 pinned model gate; higher base input and output pricing |
| Per-source Anthropic batches only | Operational complexity; smaller batches; more cache writes |
| Put `source` enum in cached system prompt | Destroys prefix sharing within a batch |
| Rely on Phase 1.5 “no code change” | Pre-filter and Call 1 still need `cache_control`; Call 2 needs `ttl: "1h"` and 4k content |
| Pad to 4k with lorem ipsum / whitespace | Cache-eligible but quality-neutral; violates §6 intent |

---

## 18. Implementation Checklist (revised)

### Wiring

- [ ] Add `cache_control` + `ttl: "1h"` to pre-filter `build_requests()` on profile + **multi-source** rubric block
- [ ] Add `cache_control` + `ttl: "1h"` to Call 1 on **dedicated** rubric block (not profile — separate asset)
- [ ] Call 2: `ttl: "1h"`; place `cache_control` on **last** system block (§5e); include profile + eval schema + few-shots in cached prefix
- [ ] Author `prefilter_rubric` and `call1_rubric` content to reach **≥ 4,096 tokens** each (measured with `cl100k_base`)
- [ ] Extend hash verification to cover rubric assets (or composite hash in profile commit)

### Scale / ops

- [ ] Persist cache usage aggregates in `batch-poller` logs (minimum); consider `BatchRecord` columns
- [ ] Document env overrides for backfill: larger `BISHOP_PREFILTER_BATCH_SIZE`, `BISHOP_ENRICHMENT_STAGE*_BATCH_SIZE`
- [ ] Profile freeze policy during G7 backfill tranches
- [ ] Alert: consecutive batches with zero `cache_read_input_tokens` after enablement
- [ ] Optional: pre-filter user-tail truncation for `title + abstract` (~500–1k tokens; §5f)

### Spec

- [ ] Update `bishop_spec_0_6.md` §12.3: Haiku 4.5 **4,096** minimum; pre-filter needs explicit `cache_control`; Call 1 rubric is separate from profile
- [ ] Note pre-filter has no manifest-level abstract cap (§13.1 truncation is enrichment-only)
- [ ] Cross-reference this doc from charter M8 T7 (profile iteration) and T8 (backfill enable)

**Out of scope:** G3 probe caching, model switch for cache floor, personal domain (second cache key family when §19.2 lands).

---

## 19. References

- [Anthropic — Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Anthropic — Batch processing (caching section)](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- BISHOP code: `bishop_shared/enrichment_prompts.py`, `services/pre-filter-worker/app/anthropic_batch_client.py`, `services/enrichment-batcher/app/anthropic_batch_client.py`
- Decision log: `.dev/decision-logs/m5-enrichment/T4-call2-cache-control.md`

---

*Caching strategy v0.3.0 — 2026-06-14 (v0.3 adds §5e–5f breakpoint semantics + input budget, §8a scale reference; v0.2 §10–18 adversarial / backfill pass)*
