Section:      external-input-sources
Version:      1.0.0
Last updated: 2026-06-10

```
Source:               Developer environment file (.env)
Format:               KEY=VALUE lines
Parser:               Docker Compose env interpolation; verify-g1.sh manual export loop
Trust level:          trusted — developer-controlled local configuration
Surfaces extracted:   BISHOP_DATA_ROOT, optional QUERY_API_HOST_PORT, UI_HOST_PORT
Surfaces NOT extracted: comments, blank lines, BOM-prefixed lines (stripped by verify-g1)
Volume:               read once at compose/G1 startup
Sensitivity:          wrong BISHOP_DATA_ROOT causes silent wrong-volume bind or writability failure
Owner module:         .env.example (template), docker-compose.yml, scripts/verify-g1.sh
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
Source:               state-worker GET /health (compose healthcheck, verify-g1 exec curl)
Format:               HTTP/1.1 GET /health → application/json
Parser:               FastAPI route + Pydantic response_model
Trust level:          trusted internal probe only (not host-exposed at M0)
Surfaces extracted:   none (response only)
Surfaces NOT extracted: request body, query params
Volume:               periodic health probes only
Sensitivity:          false healthy signal blocks entire stack startup
Owner module:         services/state-worker/app/main.py
```

**Not applicable at M0:** Web pages, RSS feeds, API manifests, PDF/HTML document ingestion, NL profile YAML — deferred to post-M0 pipeline milestones per charter §M0 non-goals.
