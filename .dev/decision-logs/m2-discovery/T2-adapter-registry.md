# T2 — adapter registry, ABC, rate limits

**Plan:** m2-discovery · **Date:** 2026-06-12

## Chosen approach

- **`SourceAdapter` ABC:** `services/scraper/app/adapters/base.py` mirrors §10.1 with `ManifestIngestEntry` (T1 DTO) instead of spec prose `ManifestEntry`. `fetch_manifest` remains abstract; `fetch_content` default raises `NotImplementedError("M4")` per M2 charter.
- **`make_source_id`:** `f"{source.value}:{raw_id}"` on the ABC base class.
- **`ADAPTER_REGISTRY`:** Single `ArxivAdapter` entry only — charter override of spec §10.2 seven-adapter list.
- **Registry import bootstrap:** `registry.py` tries `from app.adapters.arxiv import ArxivAdapter` and falls back to an inline bootstrap stub (`fetch_manifest` → `NotImplementedError("T4")`) when `arxiv.py` is absent. T4 creates `arxiv.py` without editing `registry.py`.
- **`RateLimit` / `SOURCE_RATE_LIMITS`:** Frozen dataclass per §15.1; M2 dict contains **arxiv only** (`calls=3`, `period_seconds=1`, `backoff="exponential"`, `max_retries=4`, `jitter=True`).
- **`TokenBucketRateLimiter`:** In-process async token bucket enforcing `calls/period_seconds` (§15.3); separate from failure-envelope retry (T3).

## Alternatives rejected

- **Copy spec §10.2 seven-adapter registry:** Rejected — M2 charter non-goals defer all non-ArXiv adapters to M8; kill criterion halts if registry has more than one adapter.
- **Populate `SOURCE_RATE_LIMITS` with all §15.1 sources at M2:** Rejected — plan §2 allows other sources as optional M8 stubs; M2 requires arxiv entry only with spec-exact values.
- **Make `fetch_content` abstract on the ABC:** Rejected — M2 charter binds default `NotImplementedError("M4")` on the base class.

## Assumptions made

- T4 `ArxivAdapter` in `adapters/arxiv.py` will use the same class name and class-level `source` / `domain` / `rate_limit` attributes so `ADAPTER_REGISTRY` resolves via import without registry edits.
- `TokenBucketRateLimiter` is instantiated per adapter at HTTP call sites (T4), not wired in T2.
- Bootstrap stub in `registry.py` `except ImportError` branch is dead code after T4 lands; retained so T2 and T4 stay file-disjoint.

## Items deferred

- **Non-ArXiv `SOURCE_RATE_LIMITS` entries:** M8 adapter amendment per plan §5.2 assumption.
- **`fetch_manifest` implementation:** T4 `adapters/arxiv.py`.
- **Failure envelope integration with `max_retries` / backoff:** T3.
- **Concurrent `acquire()` fairness under high parallelism:** M2 single-adapter loop; no test for lock starvation (adversarial gap deferred below).

**Adversarial test gap (deferred):** No test asserts token-bucket behavior when `calls > 1` within `period_seconds` (burst then throttle). Current `test_token_bucket_throttles` covers `calls=1` only; multi-token refill correctness deferred to T4 limiter integration test.
