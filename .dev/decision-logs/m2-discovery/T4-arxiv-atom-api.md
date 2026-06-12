# T4 — ArXiv Atom export adapter

**Plan:** m2-discovery · **Date:** 2026-06-12

## Chosen approach

- **Wire protocol:** `fetch_manifest` calls the Atom export API at `ARXIV_EXPORT_API_URL` (`http://export.arxiv.org/api/query`) per plan flag 2 resolution — RSS deferred to M8.
- **Query shape:** Single `search_query` with OR-union of `ARXIV_CATEGORIES` and `submittedDate:[YYYYMMDD000000 TO YYYYMMDD235959]` from resolved `since` through `now` (UTC).
- **`since` resolution:** `resolve_effective_since` — non-null `since` is incremental; `None` → `now - ARXIV_BACKFILL_WINDOW_DAYS` (default 7).
- **Rate limiting:** `TokenBucketRateLimiter.acquire()` wraps the HTTP GET inside the adapter (plan §5.4 C4); `failure_envelope` (T3) wraps the adapter call at loop time (T5).
- **Parsing:** stdlib `xml.etree.ElementTree`; dedupe by `source_id`; strip ArXiv version suffix from Atom `id`; `domain=professional` via class-level `DomainEnum.PROFESSIONAL`.
- **`max_results`:** env `BISHOP_ARXIV_MAX_RESULTS`, default 100, read in `arxiv.py`.

## Alternatives rejected

- **ArXiv RSS feed:** Rejected for M2 — plan §0 binds Atom export API; RSS only if export blocked (M8).
- **Per-category sequential HTTP requests:** Rejected — one OR-union query reduces API calls and stays within M2 smoke `max_results` cap; category union semantics preserved in `search_query`.
- **`lxml` / feedparser dependency:** Rejected — no new packages; Atom XML is stable and small for M2 fixtures.

## Assumptions made

- ArXiv continues to serve Atom entries with `id`, `title`, optional `summary`, `published`, and `link[@rel=alternate]` fields used here.
- `submittedDate` range filtering on the export API matches incremental/backfill intent for M2 smoke (full §18 chunking deferred to M8).
- Injectable `httpx.AsyncClient` in `ArxivAdapter.__init__` is sufficient for unit tests without live API calls.

## Items deferred

- **Malformed Atom entry (missing `id`/`title`):** Skipped silently during parse; no test — entries without required fields are not emitted. Follow-up only if live feed produces systematic gaps.
- **Live ArXiv integration smoke (`pytest -m integration`):** Deferred to T5 optional manual/compose checkpoint per plan test policy.
- **Production 60-day backfill default:** Remains env override only; M2 default stays 7 (T1 decision log).
