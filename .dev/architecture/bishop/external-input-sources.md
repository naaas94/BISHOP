Section:      external-input-sources
Version:      1.4.1
Last updated: 2026-09-16

```
Source:               Developer environment file (.env)
Format:               KEY=VALUE lines
Parser:               Docker Compose env interpolation; verify-g1.sh export loop
Trust level:          trusted — developer-controlled local configuration
Surfaces extracted:   BISHOP_DATA_ROOT; optional ANTHROPIC_API_KEY, GITHUB_TOKEN, HUGGINGFACE_TOKEN, SEMANTIC_SCHOLAR_API_KEY, BISHOP_BACKFILL_*
Surfaces NOT extracted: comments, blank lines
Volume:               read once at compose/G1 startup
Sensitivity:          wrong BISHOP_DATA_ROOT causes silent wrong-volume bind; missing API key blocks Anthropic submit
Owner module:         .env.example, docker-compose.yml, scripts/verify-g1.sh
```

```
Source:               Scraper environment variables
Format:               KEY=VALUE via os.environ
Parser:               services/scraper/app/config.py
Trust level:          trusted — operator-controlled container config
Surfaces extracted:   STATE_WORKER_URL, BISHOP_BACKFILL_ENABLED, BISHOP_BACKFILL_CHUNK_DAYS, BISHOP_BACKFILL_INTER_CHUNK_DELAY_SEC, BISHOP_BACKFILL_WINDOW_OVERRIDE_DAYS, GITHUB_TOKEN, HUGGINGFACE_TOKEN, SEMANTIC_SCHOLAR_API_KEY, schedule/max_results knobs
Surfaces NOT extracted: unknown keys
Volume:               read at process start
Sensitivity:          override_days=1 (compose default) caps all sources; missing tokens degrade to anonymous quotas
Owner module:         services/scraper/app/config.py, docker-compose.yml
```

```
Source:               Pre-filter-worker environment variables
Format:               KEY=VALUE via os.environ
Parser:               services/pre-filter-worker/app/config.py
Trust level:          trusted
Surfaces extracted:   STATE_WORKER_URL, ANTHROPIC_API_KEY, BISHOP_PREFILTER_BATCH_SIZE, BISHOP_PREFILTER_MIN_BATCH_SIZE, BISHOP_PREFILTER_MAX_HOLD_MINUTES, BISHOP_PREFILTER_POLL_INTERVAL_SEC, BISHOP_G3_VERIFIED, LOG_LEVEL
Surfaces NOT extracted: unknown keys
Volume:               read at process start
Sensitivity:          missing API key blocks submit; hold knobs change cache amortization vs latency
Owner module:         services/pre-filter-worker/app/config.py
```

```
Source:               Enrichment-batcher environment variables
Format:               KEY=VALUE via os.environ
Parser:               services/enrichment-batcher/app/config.py
Trust level:          trusted
Surfaces extracted:   STATE_WORKER_URL, ANTHROPIC_API_KEY, BISHOP_ENRICHMENT_STAGE{1,2}_{BATCH_SIZE,MIN_BATCH_SIZE,MAX_HOLD_MINUTES}, BISHOP_ENRICHMENT_POLL_INTERVAL_SEC, BISHOP_G3_VERIFIED, LOG_LEVEL
Surfaces NOT extracted: unknown keys
Volume:               read at process start
Sensitivity:          same as pre-filter hold knobs, independently per stage
Owner module:         services/enrichment-batcher/app/config.py
```

```
Source:               Batch-poller environment variables
Format:               KEY=VALUE via os.environ
Parser:               services/batch-poller/app/config.py
Trust level:          trusted
Surfaces extracted:   STATE_WORKER_URL, ANTHROPIC_API_KEY, BISHOP_BATCH_POLL_INTERVAL_SEC, BISHOP_BATCH_TIMEOUT_HOURS, LOG_LEVEL
Surfaces NOT extracted: unknown keys
Volume:               read at process start
Sensitivity:          missing API key blocks poll; timeout hours affect manifest reset
Owner module:         services/batch-poller/app/config.py
```

```
Source:               ArXiv Atom export API (export.arxiv.org)
Format:               Atom XML over HTTP
Parser:               stdlib xml.etree.ElementTree in adapters/arxiv.py::parse_atom_feed
Trust level:          partially trusted — public academic feed; metadata is untrusted document text
Surfaces extracted:   entry id, title, summary, published, link href; primary category for category gate
Surfaces NOT extracted: author lists, comments, PDF bytes
Volume:               up to adapter max_results per cycle
Sensitivity:          malformed XML skipped; no code execution path. Untrusted title/summary go to Gate 1 user turn with no delimiters. Atom link href is stored as url and rendered as UI href without a scheme allowlist (OPEN-023 I-1/I-6). CPython xml.etree does not resolve XXE.
Owner module:         services/scraper/app/adapters/arxiv.py
```

```
Source:               Other source APIs (GitHub, HuggingFace, Semantic Scholar, Papers With Code, OpenReview, LessWrong)
Format:               JSON or GraphQL-over-GET
Parser:               per-adapter JSON / GraphQL
Trust level:          partially trusted — public APIs; content is untrusted document metadata
Surfaces extracted:   id, title, abstract/summary, url, published_at
Surfaces NOT extracted: binaries, tokens in response bodies beyond stored metadata
Volume:               per-source rate limits in SOURCE_RATE_LIMITS
Sensitivity:          poisoned titles/abstracts enter SQLite as DISCOVERED and Gate 1 user turn. Adapter url fields (GitHub html_url, LessWrong pageUrl, …) are stored and UI-linked without a scheme allowlist; adapters do not GET those urls for content (OPEN-023).
Owner module:         services/scraper/app/adapters/*
```

```
Source:               Full content fetch payloads (HTML/JSON/text)
Format:               HTTP response bodies from source sites/APIs
Parser:               Per-adapter fetch_content (stdlib HTMLParser on ArXiv; JSON elsewhere; compose_fallback_content)
Trust level:          untrusted document text downstream
Surfaces extracted:   plain text content_raw on entries row
Surfaces NOT extracted: PDF bytes (OpenReview is title+abstract); executable content
Volume:               one fetch per RELEVANCE_PASSED claim (content-scraper batch default 10)
Sensitivity:          adversarial HTML/JSON can bloat SQLite (no wire max_length) or confuse Call 1; token truncate at 4000 is enrichment-only. LessWrong regex strip keeps script inner text. Call-1 summary is re-injected into Call 2 (OPEN-023 I-2/I-3/I-5).
Owner module:         services/scraper/app/adapters/*, bishop_shared/content_truncation.py
```

```
Source:               ArXiv category-gate YAML
Format:               YAML at /app/config/sources/arxiv.yaml (image-baked or repo fallback)
Parser:               bishop_shared/source_config.py SourceCategoryConfig
Trust level:          trusted operator config
Surfaces extracted:   include_categories, exclude_categories, enforce
Surfaces NOT extracted: cross-list categories (primary category only)
Volume:               one file for arXiv; other sources have no YAML yet
Sensitivity:          over-broad exclude destroys human-pass items before the LLM gate
Owner module:         config/sources/arxiv.yaml, bishop_shared/source_config.py, adapters/arxiv.py
```

```
Source:               NL profile YAML files (host profiles volume)
Format:               YAML UTF-8 at /app/config/profiles/
Parser:               PyYAML + ProfileDocument in bishop_shared/profile_renderer.py
Trust level:          trusted — operator-seeded; defines pre-filter and Call 2 judgment
Surfaces extracted:   version, domain, context, principles, anchors, exclusions, peripheral_*, calibration_examples, output; canonical_hash verified
Surfaces NOT extracted: created_at, label, changelog (ignored by ProfileDocument extra=ignore)
Volume:               live pins: prefilter professional_v1.2.0_soft_launch.yaml (overlay); enrichment professional_v1.0.0.yaml. On disk unused: v1.1.0, v1.1.1, intended v1.2.0
Sensitivity:          tampered profile changes relevance/parking; hash mismatch blocks submit
Owner module:         bishop_shared/profile_renderer.py, scripts/seed-profiles.*
```

```
Source:               Rubric markdown annexes
Format:               Markdown with YAML front matter at config/prompts/*_rubric_v1.md
Parser:               bishop_shared/rubric_assets.py (body-only canonical_hash)
Trust level:          trusted operator-authored; image-baked
Surfaces extracted:   rubric_id, version, canonical_hash, body into system blocks
Surfaces NOT extracted: front matter beyond required fields
Volume:               three rubrics (prefilter, call1, call2)
Sensitivity:          hash mismatch blocks batch submit
Owner module:         bishop_shared/rubric_assets.py, config/prompts/
```

```
Source:               Anthropic API responses (batch results)
Format:               HTTPS JSON from batches.results
Parser:               batch-poller parse_pre_filter_response / parse_call1_response / parse_call2_response
Trust level:          partially trusted — vendor API; model output is untrusted structured text
Surfaces extracted:   decision 0|1, tier, rationale; Call 1 summary/concepts/tags/entry_type/challenge_hooks; Call 2 scores; cache token counters
Surfaces NOT extracted: cache_usage is logged only, not stored in SQLite
Volume:               up to configured batch sizes
Sensitivity:          malformed JSON skipped or treated as reject/parse_failed; wrong decisions change pipeline state
Owner module:         services/batch-poller/app/loop.py, bishop_shared/enrichment_parsers.py
```

```
Source:               User search query strings (query-api / ui)
Format:               HTTP query param q (min length 1)
Parser:               FastAPI Query; BM25 tokenize + dense embed + DuckDB metadata filter
Trust level:          untrusted
Surfaces extracted:   q, domain, source, tags, min_relevance, days, type, reading_status
Surfaces NOT extracted: raw SQL
Volume:               unbounded on QUERY_API_HOST_PORT
Sensitivity:          query text logged truncated; no auth
Owner module:         services/query-api/app/routers/search.py, services/ui/app/main.py
```

```
Source:               UI HTML forms (HTMX POST)
Format:               form fields via FastAPI Form
Parser:               ui/app/main.py → query-api JSON proxy
Trust level:          untrusted local operator input
Surfaces extracted:   source_id (promote, retry, permanent-fail); reading_status enum
Surfaces NOT extracted: arbitrary state-worker paths (fixed proxy routes only)
Volume:               manual operator actions
Sensitivity:          can promote parked entries, retry escalations, mark permanent fail. UI_HOST_PORT is unauthenticated — a LAN client can do the same (OPEN-023 I-7).
Owner module:         services/ui/app/main.py
```

```
Source:               state-worker REST requests from pipeline workers (internal network)
Format:               HTTP/1.1 JSON
Parser:               FastAPI + Pydantic
Trust level:          trusted internal — not host-exposed; no auth
Surfaces extracted:   validated DTO fields only
Surfaces NOT extracted: arbitrary SQL
Volume:               scraper/content/enrichment/vector poll cycles
Sensitivity:          poisoned manifest rows enter SQLite as DISCOVERED; idempotency on source_id
Owner module:         services/state-worker/app/routers/
```

```
Source:               state-worker GET /health and GET /health/db
Format:               HTTP GET
Parser:               FastAPI
Trust level:          trusted internal probe
Surfaces extracted:   none (response only)
Surfaces NOT extracted: request body
Volume:               periodic health probes
Sensitivity:          false healthy /health/db blocks or unblocks the entire stack
Owner module:         services/state-worker/app/main.py
```

```
Source:               SQLite snapshot/restore operator CLI
Format:               host paths; optional --volume bishop-sqlite
Parser:               scripts/sqlite_snapshot.py, sqlite_restore.py
Trust level:          trusted operator
Surfaces extracted:   live bishop.db path; snapshot dir; TTL/interval flags
Surfaces NOT extracted: table contents except via backup API
Volume:               scheduled or manual
Sensitivity:          restore replaces live DB; integrity gate prevents promoting corrupt snapshots
Owner module:         scripts/sqlite_snapshot.py, scripts/sqlite_restore.py
```
