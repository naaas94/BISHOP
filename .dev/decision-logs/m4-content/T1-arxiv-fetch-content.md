# T1 — ArXiv fetch_content (HTML + fallback)

**Plan:** m4-content · **Date:** 2026-06-13

## Chosen approach

- **Full-text source:** `GET https://arxiv.org/html/{raw_id}` where `raw_id` is parsed from `entry.source_id` via `parse_raw_id_from_source_id` (`arxiv:2301.00001` → `2301.00001`).
- **HTML extraction:** stdlib `html.parser.HTMLParser` subclass skips `script`/`style`, collapses whitespace — no new dependencies.
- **Fallback:** On non-2xx HTTP or empty stripped body, `compose_fallback_content` returns `{title}\n\n{abstract or ""}` from the poll/ingest entry fields; no extra preamble.
- **Rate limiting:** `TokenBucketRateLimiter.acquire()` wraps the HTML GET inside `fetch_content`, matching manifest fetch behavior; `failure_envelope` wraps at content-scraper loop (T2).
- **HTTP client:** Reuses injectable `httpx.AsyncClient` on `ArxivAdapter` for unit tests; creates and owns a client when none injected.

## Alternatives rejected

- **PDF / LaTeX source parsing:** Rejected — spec §0 Flag 1 binds HTML endpoint + title/abstract fallback only; PDF parsers would add deps and scope beyond M4.
- **ArXiv abstract-only API round-trip:** Rejected — poll entry already carries title/abstract; redundant HTTP when HTML is unavailable.
- **`beautifulsoup4` / `lxml` for HTML stripping:** Rejected — kill criterion binds existing `httpx` only; stdlib parser sufficient for M4 smoke.

## Assumptions made

- ArXiv HTML endpoint availability correlates with papers that have HTML renditions; older papers without HTML correctly fall back to title+abstract.
- Stripped HTML text quality is acceptable for M4 `content_raw` population; M5 owns truncation and enrichment quality gates.
- `source_id` always uses `make_source_id` canonical form (`arxiv:{raw_id}`) when invoked from the pipeline.

## Items deferred

- **Large HTML payload truncation:** No truncation in M4 — M5 owns content size limits per plan risks.
- **Live ArXiv HTML integration (`pytest -m integration`):** Deferred per plan test policy; default CI uses mocked httpx only.
- **Malformed `source_id` without colon separator:** Not tested — pipeline-only input assumed canonical; adversarial gap recorded in CHANGELOG.
