Section:      integration-seams
Version:      1.0.0
Last updated: 2026-06-10

```
Seam:          Docker Compose internal network (bishop-internal)
Direction:     bidirectional
Protocol:      Docker bridge DNS (service hostname resolution)
Auth:          none (M0 — internal network only)
Data sent:     HTTP requests between containers (M0: healthcheck only; STATE_WORKER_URL reserved)
Data received: HTTP responses from state-worker /health; stub 200 from query-api/ui internally
Error modes:   service_healthy timeout if state-worker fails; DNS failure if service key renamed
Retry policy:  compose healthcheck retries (interval 10s, retries 5, start_period 10s on state-worker)
Owner module:  docker-compose.yml
```

```
Seam:          Host filesystem — BISHOP_DATA_ROOT volume mounts
Direction:     bidirectional
Protocol:      Docker bind mounts
Auth:          OS filesystem permissions
Data sent:     Pipeline writes to sqlite, lancedb, duckdb, bm25, profiles, logs (future milestones)
Data received: Services read mounted paths at container paths under /app/data and /app/config
Error modes:   missing host directory; wrong path on Windows; permission denied; probe write failure in G1
Retry policy:  none at M0
Owner module:  docker-compose.yml, scripts/init-volumes.sh, scripts/init-volumes.ps1
```

```
Seam:          state-worker HTTP — internal health probe
Direction:     inbound
Protocol:      HTTP GET /health (JSON)
Auth:          none (M0)
Data sent:     none
Data received: {"status":"ok"}
Error modes:   non-200; body missing "ok"; connection refused before uvicorn ready
Retry policy:  compose healthcheck retries; verify-g1 waits for stack then exec curl once
Owner module:  services/state-worker/app/main.py
```

```
Seam:          query-api — host port exposure
Direction:     inbound
Protocol:      HTTP GET / (plain text "ok" at M0)
Auth:          none (M0)
Data sent:     none
Data received: 200 ok on host port QUERY_API_HOST_PORT (default 8080)
Error modes:   port bind conflict; container not running; wrong host port mapping
Retry policy:  verify-g1 curl -sf (fail fast)
Owner module:  services/query-api/stub_main.py, docker-compose.yml
```

```
Seam:          ui — host port exposure
Direction:     inbound
Protocol:      HTTP GET / (plain text "ok" at M0)
Auth:          none (M0)
Data sent:     none
Data received: 200 ok on host port UI_HOST_PORT (default 8081) mapped to container port 80
Error modes:   port bind conflict; UI_CONTAINER_PORT drift from compose :80 mapping
Retry policy:  verify-g1 curl -sf (fail fast)
Owner module:  services/ui/stub_main.py, docker-compose.yml
```

**Future seams (not wired at M0):** external source APIs (scrapers), OpenAI/batch enrichment APIs, SQLite file access from batch-poller, LanceDB/DuckDB/BM25 read/write from vector-writer and query-api — per bishop_spec_0_6.md §4–§9.
