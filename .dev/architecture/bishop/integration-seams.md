Section:      integration-seams
Version:      1.1.0
Last updated: 2026-06-12

```
Seam:          Docker Compose internal network (bishop-internal)
Direction:     bidirectional
Protocol:      Docker bridge DNS (service hostname resolution)
Auth:          none (internal network only)
Data sent:     HTTP requests between containers (health, manifest batch, scraper-state, future poll/claim)
Data received: HTTP responses from state-worker and stubs
Error modes:   service_healthy timeout; DNS failure if service key renamed
Retry policy:  compose healthcheck retries (state-worker start_period 30s)
Owner module:  docker-compose.yml
```

```
Seam:          Host filesystem — BISHOP_DATA_ROOT volume mounts
Direction:     bidirectional
Protocol:      Docker bind mounts
Auth:          OS filesystem permissions
Data sent:     state-worker writes SQLite and logs; future milestones write lancedb, duckdb, bm25, profiles
Data received: Services read mounted paths under /app/data and /app/config
Error modes:   missing host directory; wrong path on Windows; permission denied
Retry policy:  none
Owner module:  docker-compose.yml, scripts/init-volumes.sh, scripts/init-volumes.ps1
```

```
Seam:          state-worker HTTP — internal health probe
Direction:     inbound
Protocol:      HTTP GET /health (JSON)
Auth:          none
Data sent:     none
Data received: {"status":"ok"}
Error modes:   non-200; connection refused before migrations complete
Retry policy:  compose healthcheck retries; verify-g1 exec curl
Owner module:  services/state-worker/app/main.py
```

```
Seam:          state-worker HTTP — scraper integration (M2)
Direction:     inbound to state-worker
Protocol:      HTTP JSON — GET/POST /scraper-state/{source}, POST /manifest/batch
Auth:          none (internal network)
Data sent:     ManifestIngestEntry batches; scraper checkpoint timestamps
Data received: inserted/skipped counts; ScraperStateSnapshot; 204 on state update
Error modes:   non-2xx from state-worker; connection refused; batch POST failure aborts adapter pass
Retry policy:  none at HTTP client level (loop logs httpx.HTTPStatusError); manifest idempotency on server
Owner module:  services/scraper/app/state_worker_client.py → services/state-worker/app/routers/
```

```
Seam:          state-worker — SQLite file
Direction:     bidirectional
Protocol:      SQLite file at SQLITE_DB_PATH (/app/data/sqlite/bishop.db)
Auth:          filesystem (container-local)
Data sent:     INSERT/UPDATE for all §7 tables
Data received: SELECT for poll-and-claim, batch queries, escalations
Error modes:   migration failure; WAL lock contention; corrupt DB
Retry policy:  none; sweeps recover lock-state and retry-scheduled rows
Owner module:  services/state-worker/app/db.py, transitions.py
```

```
Seam:          ArXiv Atom export API
Direction:     outbound from scraper
Protocol:      HTTP GET http://export.arxiv.org/api/query (Atom XML)
Auth:          none (public API)
Data sent:     search_query, submittedDate range, max_results, sortBy
Data received: Atom feed XML (entries with id, title, summary, published, link)
Error modes:   429 rate limit; 403/401 escalatable; 400 permanent; network timeout; malformed XML
Retry policy:  failure_envelope with exponential backoff per §15.2; in-adapter token-bucket before request
Owner module:  services/scraper/app/adapters/arxiv.py, failure_envelope.py
```

```
Seam:          query-api — host port exposure
Direction:     inbound
Protocol:      HTTP GET / (plain text "ok" at M0)
Auth:          none (M0)
Data sent:     none
Data received: 200 ok on host port QUERY_API_HOST_PORT (default 8080)
Error modes:   port bind conflict; container not running
Retry policy:  verify-g1 curl -sf (fail fast)
Owner module:  services/query-api/stub_main.py, docker-compose.yml
```

```
Seam:          ui — host port exposure
Direction:     inbound
Protocol:      HTTP GET / (plain text "ok" at M0)
Auth:          none (M0)
Data sent:     none
Data received: 200 ok on host port UI_HOST_PORT (default 8081)
Error modes:   port bind conflict; UI_CONTAINER_PORT drift from compose :80 mapping
Retry policy:  verify-g1 curl -sf (fail fast)
Owner module:  services/ui/stub_main.py, docker-compose.yml
```

**Future seams (not wired):** OpenAI/batch enrichment APIs, pre-filter-worker poll/claim, content-scraper, LanceDB/DuckDB/BM25 read/write — per charter §M3+.
