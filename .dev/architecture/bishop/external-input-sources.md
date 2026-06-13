Section:      external-input-sources
Version:      1.2.0
Last updated: 2026-06-13

```
Source:               Developer environment file (.env)
Format:               KEY=VALUE lines
Parser:               Docker Compose env interpolation; verify-g1.sh manual export loop
Trust level:          trusted — developer-controlled local configuration
Surfaces extracted:   BISHOP_DATA_ROOT, optional QUERY_API_HOST_PORT, UI_HOST_PORT
Surfaces NOT extracted: comments, blank lines, BOM-prefixed lines (stripped by verify-g1)
Volume:               read once at compose/G1 startup
Sensitivity:          wrong BISHOP_DATA_ROOT causes silent wrong-volume bind or writability failure
Owner module:         .env.example, docker-compose.yml, scripts/verify-g1.sh
```

```
Source:               Scraper environment variables
Format:               KEY=VALUE via os.environ
Parser:               services/scraper/app/config.py, arxiv.py
Trust level:          trusted — operator-controlled container config
Surfaces extracted:   STATE_WORKER_URL, BISHOP_ARXIV_BACKFILL_WINDOW_DAYS, BISHOP_SCRAPER_SCHEDULE_INTERVAL_SEC, BISHOP_ARXIV_MAX_RESULTS
Surfaces NOT extracted: unknown keys
Volume:               read at process start / per ArXiv request for max_results
Sensitivity:          wrong STATE_WORKER_URL breaks scraper→state-worker seam; extreme max_results affects ArXiv load
Owner module:         services/scraper/app/config.py, adapters/arxiv.py
```

```
Source:               Pre-filter-worker environment variables
Format:               KEY=VALUE via os.environ
Parser:               services/pre-filter-worker/app/config.py, loop.py
Trust level:          trusted — operator-controlled container config
Surfaces extracted:   STATE_WORKER_URL, ANTHROPIC_API_KEY, BISHOP_PREFILTER_BATCH_SIZE, BISHOP_PREFILTER_POLL_INTERVAL_SEC, BISHOP_G3_VERIFIED, LOG_LEVEL
Surfaces NOT extracted: unknown keys
Volume:               read at process start; G3 probe once per process unless BISHOP_G3_VERIFIED=1
Sensitivity:          missing ANTHROPIC_API_KEY blocks submit; wrong batch size affects throughput
Owner module:         services/pre-filter-worker/app/config.py, loop.py
```

```
Source:               Batch-poller environment variables
Format:               KEY=VALUE via os.environ
Parser:               services/batch-poller/app/config.py
Trust level:          trusted — operator-controlled container config
Surfaces extracted:   STATE_WORKER_URL, ANTHROPIC_API_KEY, BISHOP_BATCH_POLL_INTERVAL_SEC, BISHOP_BATCH_TIMEOUT_HOURS, LOG_LEVEL
Surfaces NOT extracted: unknown keys
Volume:               read at process start
Sensitivity:          missing API key blocks poll; timeout hours affect manifest reset behavior
Owner module:         services/batch-poller/app/config.py
```

```
Source:               ArXiv Atom export API (export.arxiv.org)
Format:               Atom XML (application/atom+xml) over HTTP
Parser:               stdlib xml.etree.ElementTree in adapters/arxiv.py::parse_atom_feed
Trust level:          partially trusted — public academic feed; content is untrusted document metadata
Surfaces extracted:   entry id, title, summary (abstract), published, link href
Surfaces NOT extracted: author lists, categories, comments, PDF bytes, full paper content
Volume:               up to BISHOP_ARXIV_MAX_RESULTS (default 100) per cycle per adapter
Sensitivity:          malformed or adversarial XML could cause skipped entries or parse errors; no code execution path
Owner module:         services/scraper/app/adapters/arxiv.py
```

```
Source:               NL profile YAML files (host profiles volume)
Format:               YAML (UTF-8) at /app/config/profiles/professional_v1.0.0.yaml
Parser:               PyYAML safe_load + ProfileDocument Pydantic validation in bishop_shared/profile_renderer.py
Trust level:          trusted — operator-seeded local files; content defines pre-filter judgment criteria
Surfaces extracted:   version, domain, context, principles, anchors, exclusions, output instruction; canonical_hash verified at runtime
Surfaces NOT extracted: created_at, label, changelog (included in hash via raw dict but ignored by ProfileDocument)
Volume:               one profile file at M3 (professional domain only)
Sensitivity:          tampered profile changes relevance decisions; hash mismatch blocks batch submit and emits CRITICAL alert
Owner module:         bishop_shared/profile_renderer.py, scripts/seed-profiles.sh, scripts/seed-profiles.ps1
```

```
Source:               Anthropic API responses (batch results)
Format:               HTTPS JSON from batches.results
Parser:               batch-poller parse_pre_filter_response
Trust level:          partially trusted — vendor API; model output is untrusted structured text
Surfaces extracted:   decision (0|1), pre_filter_rationale from result message content
Surfaces NOT extracted: raw message metadata beyond custom_id join key
Volume:               up to BISHOP_PREFILTER_BATCH_SIZE entries per batch
Sensitivity:          malformed JSON or unexpected format logged and skipped; wrong decisions affect manifest state
Owner module:         services/batch-poller/app/loop.py
```

```
Source:               HTTP clients hitting query-api and ui host ports (G1 verification, manual curl)
Format:               HTTP/1.1 GET /
Parser:               stdlib BaseHTTPRequestHandler in stub_main.py
Trust level:          untrusted at production; M0 accepts any GET / with no auth
Surfaces extracted:   path == "/"
Surfaces NOT extracted: request body, headers, query strings, non-GET methods (404/405)
Volume:               negligible at M0
Sensitivity:          M0 stubs return static "ok"; no data persistence
Owner module:         services/query-api/stub_main.py, services/ui/stub_main.py
```

```
Source:               state-worker REST requests from pipeline workers (internal network)
Format:               HTTP/1.1 JSON (manifest batch, scraper-state, poll/claim, batch lifecycle, pre-filter results)
Parser:               FastAPI routes + Pydantic request models
Trust level:          trusted internal — not host-exposed; no auth at M3
Surfaces extracted:   validated DTO fields only
Surfaces NOT extracted: arbitrary SQL
Volume:               scraper: one batch per adapter per cycle; pre-filter: poll batches on interval; batch-poller: poll on interval
Sensitivity:          poisoned manifest rows enter SQLite as DISCOVERED; idempotency prevents duplicate source_id
Owner module:         services/state-worker/app/routers/
```

```
Source:               state-worker GET /health (compose healthcheck, verify-g1 exec curl)
Format:               HTTP/1.1 GET /health → application/json
Parser:               FastAPI route + Pydantic response_model
Trust level:          trusted internal probe only
Surfaces extracted:   none (response only)
Surfaces NOT extracted: request body, query params
Volume:               periodic health probes only
Sensitivity:          false healthy signal blocks entire stack startup
Owner module:         services/state-worker/app/main.py
```

**Not applicable yet:** PDF/HTML full-content ingestion (M4), user query strings on query-api (future).
