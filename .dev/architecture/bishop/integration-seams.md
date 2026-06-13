Section:      integration-seams
Version:      1.2.0
Last updated: 2026-06-13

```
Seam:          Docker Compose internal network (bishop-internal)
Direction:     bidirectional
Protocol:      Docker bridge DNS (service hostname resolution)
Auth:          none (internal network only)
Data sent:     HTTP requests between containers (health, manifest batch, scraper-state, poll/claim, batch lifecycle)
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
Data sent:     state-worker writes SQLite and logs; pre-filter reads profiles; future milestones write lancedb, duckdb, bm25
Data received: Services read mounted paths under /app/data and /app/config
Error modes:   missing host directory; wrong path on Windows; permission denied; empty profiles dir without seed
Retry policy:  none
Owner module:  docker-compose.yml, scripts/init-volumes.sh, scripts/init-volumes.ps1, scripts/seed-profiles.*
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
Seam:          state-worker HTTP — pre-filter-worker integration (M3)
Direction:     inbound to state-worker
Protocol:      HTTP JSON — GET /manifest/poll, POST /batches
Auth:          none (internal network)
Data sent:     poll claim for DISCOVERED manifests; BatchRegisterRequest at Anthropic submit
Data received: PollResponse claimed rows; BatchRegisterResponse (201) or 409 batch_conflict
Error modes:   empty poll (no-op cycle); profile hash mismatch blocks submit; G3 gate failure blocks first submit
Retry policy:  scheduler retries on interval (BISHOP_PREFILTER_POLL_INTERVAL_SEC); no HTTP retry on register conflict
Owner module:  services/pre-filter-worker/app/state_worker_client.py → services/state-worker/app/routers/
```

```
Seam:          state-worker HTTP — batch-poller integration (M3)
Direction:     inbound to state-worker
Protocol:      HTTP JSON — GET /batches, PATCH /batches/{id}, POST /batches/{id}/timeout, POST /manifest/pre-filter-results
Auth:          none (internal network)
Data sent:     batch status updates; pre-filter result entries; timeout requests
Data received: BatchRecord list/detail; PreFilterResultsResponse counts; BatchTimeoutResponse entries_reset
Error modes:   404 not_found; 409 invalid_batch_state; non-pre_filter batch_type rejected by poller
Retry policy:  poll loop interval (BISHOP_BATCH_POLL_INTERVAL_SEC); startup_scan reconciles in-flight batches
Owner module:  services/batch-poller/app/clients/state_worker.py → services/state-worker/app/routers/
```

```
Seam:          state-worker — SQLite file
Direction:     bidirectional
Protocol:      SQLite file at SQLITE_DB_PATH (/app/data/sqlite/bishop.db)
Auth:          filesystem (container-local)
Data sent:     INSERT/UPDATE for all §7 tables incl. batches.source_ids (m3_001)
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
Seam:          Anthropic Messages Batches API
Direction:     outbound from pre-filter-worker (submit) and batch-poller (poll/results)
Protocol:      HTTPS JSON — messages.batches.create, batches.retrieve, batches.results
Auth:          ANTHROPIC_API_KEY bearer token
Data sent:     pre-filter batch requests (custom_id=source_id, system prompt from profile, max_tokens=256)
Data received: external_batch_id; batch status; per-item result JSON with decision/rationale
Error modes:   HTTP 400 invalid model (fatal); rate limits; batch expired; partial failures
Retry policy:  G3 verify_model_string before first submit; scheduler re-polls; batch timeout via state-worker after BISHOP_BATCH_TIMEOUT_HOURS
Owner module:  services/pre-filter-worker/app/anthropic_batch_client.py, services/batch-poller/app/clients/anthropic.py, bishop_shared/anthropic_config.py
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

**Future seams (not wired):** enrichment batch APIs (OpenAI/Anthropic enrichment stage), content-scraper fetch_content, LanceDB/DuckDB/BM25 read/write — per charter §M4+.
