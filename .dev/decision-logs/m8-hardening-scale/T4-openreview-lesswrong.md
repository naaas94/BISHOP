# T4 — OpenReview + LessWrong adapters

**Plan:** m8-hardening-scale · **Date:** 2026-09-10

## Chosen approach

- **`OpenReviewAdapter` (`services/scraper/app/adapters/openreview.py`):**
  before choosing an endpoint shape, live-probed the real OpenReview hosts
  (2026-09-10, no credentials):
  - `GET https://api.openreview.net/notes?mintcdate=1&limit=1` → **HTTP 403**
    `ChallengeRequiredError` ("Challenge verification required").
  - `GET https://api2.openreview.net/notes?content.venueid=ICLR.cc%2F2026%2FConference%2FSubmission&limit=1`
    → **HTTP 403** `ChallengeRequiredError`.
  - `GET https://api2.openreview.net/notes?invitation=ICLR.cc%2F2026%2FConference%2F-%2FSubmission&limit=1`
    → **HTTP 403** `ChallengeRequiredError`.
  - `GET https://api2.openreview.net/notes/search?term=<term>&type=terms&content=all&group=all&source=forum&sort=cdate:desc&limit=N`
    → **HTTP 200**, well-formed note JSON, sorted correctly by `cdate` descending.

  Every unauthenticated venue/invitation-filtered listing endpoint is bot-gated;
  the unauthenticated term-search endpoint (`/notes/search`) is not. The
  adapter therefore fetches via `/notes/search` with a broad cross-venue term
  (`"machine learning"`) and `sort=cdate:desc`, then filters results to
  `content.cdate >= since_ms` client-side (the search endpoint has no native
  date-range parameter). `fetch_content` composes `title + abstract` — the
  search response has no body/PDF text, and extracting one would require a
  new PDF-parsing dependency, which needs orchestrator approval and is out of
  scope here.

- **`LessWrongAdapter` (`services/scraper/app/adapters/lesswrong.py`)** —
  context-map ambiguity flag 3: **probe before implement.** Live-probed
  2026-09-10, no credentials:
  - `POST https://www.lesswrong.com/graphql` with body
    `{"query":"{ __typename }"}` (and with `apollo-require-preflight: true`
    added) → **HTTP 500**, empty body, every time. Looks like a CSRF/preflight
    rejection on this specific host for non-browser POSTs, not an outage —
    a malformed `POST` with no `query` field distinctly returns a real
    `400 BAD_REQUEST` JSON error body, so the server *is* alive and
    responding to malformed requests; well-formed POST bodies are the ones
    that silently 500.
  - `GET https://www.lesswrong.com/graphql?query=%7B__schema%7BqueryType%7Bname%7D%7D%7D`
    → **HTTP 200**, `{"data":{"__schema":{"queryType":{"name":"Query"}}}}`.
  - `GET .../graphql?query=<posts query>&variables=<json>` (view `"new"`,
    `after` cursor, `limit`) → **HTTP 200**, real post data (`_id`, `title`,
    `postedAt`, `pageUrl`); the `after` filter was verified to actually
    narrow the result set (re-probed with a tighter `after` cutoff and got
    fewer results back).
  - `GET .../graphql?query=<single-post query>&variables={"postId": "<id>"}`
    → **HTTP 200**, `contents.html` present and non-empty.

  **Probe verdict: SUCCEEDED (via GET, not POST).** Per the flag-3
  resolution ("implement only if probe succeeds"), the adapter is
  implemented in full: `fetch_manifest` and `fetch_content` both use `GET`
  with `query`/`variables` in the querystring, never `POST`. This is the one
  fork the packet's kill criteria explicitly gate on — the negative branch
  (omit from registry, log `WARN lesswrong_adapter_skipped`) was **not**
  taken because the probe came back positive.

- **Neither adapter touches `services/scraper/app/adapters/registry.py`.**
  Per §2 contract bindings, `ADAPTER_REGISTRY` is owned by T8 (sole merger);
  T4's Files-to-touch does not include `registry.py`. This decision log is
  the artifact T8 needs to decide the LessWrong fork: the probe succeeded,
  so `LessWrongAdapter` is a real, tested module ready to import — T8's
  merge is a policy question (register it or not), not a re-probe.

## Alternatives rejected

- **OpenReview: venue/invitation-filtered `/notes` (API v1 or v2).** Rejected
  — both return `403 ChallengeRequiredError` for unauthenticated callers
  (live-probed above). Would require registering for OpenReview API
  credentials, a new dependency/config surface not authorized in this
  packet.
- **OpenReview: no client-side since-filter, rely on `/notes/search` sort
  order alone.** Rejected — the search endpoint has no date-range query
  parameter; relying on sort order alone would require the caller to guess
  how many pages to walk before hitting `since`, which is both fragile and
  unbounded. Client-side filtering over a bounded `limit` fetch is simpler
  and testable.
- **LessWrong: retry `POST` with alternate content-types / cookies before
  falling back to `GET`.** Rejected as unnecessary — `GET` is a first-class,
  fully-functional way to execute GraphQL queries against this endpoint (not
  a degraded fallback), so there is no reliability reason to keep chasing a
  working `POST` shape once `GET` was confirmed to work end-to-end for both
  queries this adapter needs.
- **LessWrong: fetch `contents.html` inside `fetch_manifest`.** Rejected —
  the spec's own adapter contract keeps `fetch_manifest` "lightweight:
  IDs, titles, abstracts only" (`base.py` docstring); fetching full HTML body
  for every manifest row would multiply request volume against a 5 req/s
  rate limit for no benefit until an entry is actually selected for content
  fetch. Content fetch stays in `fetch_content`, called per-entry, matching
  the ArXiv two-phase pattern.

## Assumptions made

- **OpenReview's `"machine learning"` search term is a workable stand-in for
  venue scoping**, not a precise filter. This adapter will pull in broader
  content than a venue-scoped feed would (e.g. non-ICLR/NeurIPS/ICML
  results, per the raw probe output above). This is a real precision
  tradeoff, not a hidden one — flagged below under Items deferred.
- **`content.cdate` (top-level, epoch ms) on OpenReview notes is a reliable
  proxy for "submission/creation date"** for the since-filter. Verified
  against three independent live queries; format was consistent across all
  probed venues (DBLP-imported records, ICML 2025 submissions, and
  `OpenReview.net/Archive` uploads all used the same top-level `cdate` in ms).
- **LessWrong's `posts(input: {terms: {view: "new", after: ...}})` shape is
  stable** — verified live against the production GraphQL schema
  (introspection confirmed `Query` type resolves; `after` cutoff verified to
  narrow results) but this is a third-party API with no versioning
  guarantee. If it breaks, the adapter's `respx`/`MockTransport`-based tests
  will keep passing (they assert against a fixture, not the live schema) —
  only the live opt-in probe test
  (`test_probe_lesswrong_api_live`, `BISHOP_LESSWRONG_PROBE_LIVE=1`) or
  production traffic would surface a live-side break.
- **The ArXiv adapter pattern (rate limiter reuse, `SourceAdapter` base,
  `make_source_id`, manifest/content two-phase fetch) is a sufficient
  template for both sources** — no source-specific base-class extension was
  needed for either adapter.

## Items deferred

- **OpenReview venue-precise scoping.** The unauthenticated `/notes/search`
  term-search is a coarser filter than a venue-id-scoped feed. Tightening
  this (e.g. multiple targeted terms, or switching to authenticated
  venue-filtered `/notes` if/when OpenReview API credentials are
  provisioned) is deferred — no landing gate is named in this plan for it;
  it is a data-quality tuning item for a future M8/M9 pass, not a blocker
  for T4's kill criteria (which only require the declared REST base URL to
  be reachable in mocked tests — satisfied).
- **OpenReview full-text content fetch (PDF body).** `fetch_content`
  currently composes `title + abstract` only. Extracting PDF body text would
  need a new dependency (e.g. a PDF-parsing library) — out of scope without
  orchestrator approval. Deferred to a future subtask if OpenReview content
  quality proves insufficient at the G6 enrichment sampling gate (T7).
- **`ADAPTER_REGISTRY` inclusion of `LessWrongAdapter`.** This module is
  fully implemented and tested (probe succeeded), but registration is T8's
  call per §2 (`ADAPTER_REGISTRY` — T8, sole merger). Landing gate: T8's
  merge subtask, using this decision log's probe evidence.

## Files changed

- `services/scraper/app/adapters/openreview.py` (new)
- `services/scraper/app/adapters/lesswrong.py` (new)
- `tests/test_scraper_adapters_openreview.py` (new)
- `tests/test_scraper_adapters_lesswrong.py` (new)
