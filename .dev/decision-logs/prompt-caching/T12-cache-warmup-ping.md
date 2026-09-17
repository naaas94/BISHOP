# T12 — Cache warmup ping (FU-CACHE-WARMUP-01) + scraper-cadence config

**Date:** 2026-09-15
**Trigger:** User review of the prompt-caching dashboard — 98% cache-read ratio
but only ~14x 24h write amortization at current steady-state traffic, vs. 57.7x
during the Sep 13 post-go-live window. Root cause (see
`.dev/plans/prompt-caching/artifacts/scratch/` canvas analysis, not repeated
here): the 6h global scraper tick outlives the 1h cache TTL, so every
discovery wave cold-starts all three cache keys, and each cold start's first
~50-row batch races Anthropic's concurrent out-of-order scheduler for the
cache write (observed: 41 writes / 50 rows on the live G1 first batch vs. 1
write / 300 rows on a later lucky wave).

## Decision 1 — warmup implementation: synchronous priming call, not a
## batch-based warmup

`caching_strategy.md` §3c describes a batch-based warmup: submit a single
request containing only the shared prefix, wait for completion, then submit
the full batch. Adversarial review before implementation surfaced two
disqualifying problems with that literal shape:

1. **No completion signal.** Anthropic's Batch API has no partial or
   streaming per-request result — results are retrievable only via
   `results_url` once the whole batch has ended. "Wait for completion" on a
   batch means polling `processing_status` with no SLA (Anthropic's stated
   guarantee is "within 24 hours"), not the few-second wait the strategy
   implied.
2. **Double-submission of a real row.** Peeling one real pending entry into
   its own 1-row batch, then including it again in the main batch, submits
   that manifest row through two separate `BatchRecord`s. `manifest.pre_filter_batch_id`
   is a single FK — whichever batch's result lands second silently
   overwrites the provenance link — and `entry_count`/`passed_count`
   double-count the row across two batches. This is the same class of hazard
   already named in the plan's own risk register as R8 (duplicate Anthropic
   batches from sweep/retry pay the write premium again and corrupt
   accounting), just self-inflicted here instead of from a retry bug.

**Chosen instead:** a synchronous, non-batch `client.messages.create()` call
with the batch's own `system_blocks`, `max_tokens=1`, fired right before the
real batch submit. This writes to the same cache entry — Anthropic scopes
prompt caching by organization + model + byte-identical prefix, not by which
API surface wrote it — in one blocking round-trip (no batch-turnaround wait),
and never touches `batches`/`BatchRecord`/state-worker bookkeeping, so no real
manifest row is ever submitted twice.

**Named, unverified assumption:** the claim in the previous paragraph — that
the cache is shared across the sync Messages API and the Batches API — is
asserted from general knowledge of Anthropic's cache design, not proven
against this repo's live traffic. Before trusting this in production, run a
G1-style live check: confirm the batch immediately following a warmup ping
shows `cache_read_tokens > 0` in batch-poller logs (the existing T8
`cache_read_zero` warning already flags the failure mode if the assumption is
wrong — the warmup will look like a no-op, not a silent corruption).

**Placement:** the warmup call fires only after the hold-below-minimum check
and any hash/G3 abort have already passed — i.e., only immediately before a
real batch submit is about to happen. It does not fire for a cohort that gets
held below `*_MIN_BATCH_SIZE` (no wasted write for a batch that might not
submit for up to `*_MAX_HOLD_MINUTES`) or one that aborts on a hash/G3
mismatch (matches the existing C9 discipline: abort paths must not have
side effects that outlive the abort).

**Rejected alternative — do not implement now:** deferring again was
considered, since the original plan explicitly named this item's owner as
"operator, outside this plan." Given the concrete cost evidence (14x vs.
57.7x-250x+ amortization swing) and that the double-submission/no-SLA
objections to the literal §3c shape are now resolved by a different
implementation, not by more analysis, deferring further had no remaining
open question to wait on.

## Decision 2 — scraper cadence: lower the existing global interval, do not
## wire the per-source map

`bishop_shared/scraper_config.py::SOURCE_SCHEDULE_INTERVAL_SEC` already
defines a per-source cadence (HF/ArXiv 6h, GitHub 12h, others 24h) but it is
dead config — `services/scraper/app/main.py` runs every adapter on one global
`SCRAPER_SCHEDULE_INTERVAL_SEC` tick (default 21600s / 6h). The first
instinct — "wire the unused per-source map so cadence matches intent" — was
considered and rejected: doing so would desynchronize sources onto
independent 6h/12h/24h clocks, which spreads discovery events *further*
apart, not closer together, and could produce more distinct cache-cold
waves per day, not fewer. That is the wrong direction for this goal.

**Chosen:** lower the single global `BISHOP_SCRAPER_SCHEDULE_INTERVAL_SEC` to
2700s (45min) via `.env.example`, so every source's adapter wakes together
inside one 1h TTL window and pre-filter has something to batch more than
once per TTL. Cost: every adapter — including the 24h-intended-cadence
sources — now polls ~7-29x more often for mostly-incremental (small,
`since=`-bounded) fetches. Rate limiters (`services/scraper/app/rate_limit.py`)
are per-second token buckets, not daily quotas, so this does not risk hard
rate-limit exhaustion; the cost is redundant idle HTTP round trips against
courtesy APIs, not additional spend.

**Compose gap found and fixed:** `docker-compose.yml`'s `scraper` service
`environment:` block never listed `BISHOP_SCRAPER_SCHEDULE_INTERVAL_SEC` —
compose only interpolates explicitly-listed vars, so setting this in `.env`
alone would have been a silent no-op. Added the passthrough with the
code's own default (`:-21600`) as the compose-level fallback, so the actual
override lives only in `.env.example`/`.env`.

## Explicitly out of scope for this subtask

- Persisting cache-usage tokens onto the `batches` table (PB-002 / D8) — no
  Alembic revision, no `BatchRecord` schema change. Warmup pings are
  observable only via `send_cache_warmup_ping`'s own `cache_warmup_sent`/
  `cache_warmup_failed` log events, not via SQLite.
- The repo-wide `logging.basicConfig` gap (structured `extra={}` fields never
  print to compose stdout) — real, but identical across all nine services,
  not specific to caching; left as a separate, un-filed observation rather
  than scope-creeped into this change.
- A dummy heartbeat batch to keep the cache warm independent of scraper
  cadence — T11 already forbade this; not revisited here.
