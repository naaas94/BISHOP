Section:      external-input-sources
Version:      1.1.0
Last updated: 2026-06-12

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
Source:               state-worker REST requests from scraper (internal network)
Format:               HTTP/1.1 JSON (manifest batch, scraper-state)
Parser:               FastAPI routes + Pydantic request models
Trust level:          trusted internal — not host-exposed; no auth at M2
Surfaces extracted:   manifest ingest fields, ISO timestamps for scraper checkpoint
Surfaces NOT extracted: arbitrary SQL; only validated DTO fields persisted
Volume:               one batch per adapter per scrape cycle (default 6h interval)
Sensitivity:          poisoned manifest rows enter SQLite as DISCOVERED; idempotency prevents duplicate source_id
Owner module:         services/state-worker/app/routers/manifest.py, scraper_state.py
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

**Not applicable yet:** PDF/HTML full-content ingestion (M4), NL profile YAML (M3+), user query strings on query-api (future).
