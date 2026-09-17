Section:      integration-seams
Version:      1.3.1
Last updated: 2026-09-16

```
Seam:          Docker Compose internal network (bishop-internal)
Direction:     bidirectional
Protocol:      Docker bridge DNS (service hostname resolution)
Auth:          none (internal network only)
Data sent:     HTTP between containers (health, poll/claim, batch lifecycle, content, enrichment, indexed, parked, proxies)
Data received: HTTP responses from state-worker, query-api
Error modes:   service_healthy timeout; DNS failure if service key renamed
Retry policy:  compose healthcheck retries (state-worker start_period 30s)
Owner module:  docker-compose.yml
```

```
Seam:          Host filesystem — BISHOP_DATA_ROOT volume mounts
Direction:     bidirectional
Protocol:      Docker bind mounts
Auth:          OS filesystem permissions
Data sent:     state-worker writes SQLite and logs; vector-writer writes lancedb/duckdb/bm25; pre-filter reads profiles
Data received: Services read mounted paths under /app/data and /app/config
Error modes:   missing host directory; wrong path on Windows; permission denied; empty profiles dir without seed
Retry policy:  none
Owner module:  docker-compose.yml, scripts/init-volumes.sh, scripts/init-volumes.ps1, scripts/seed-profiles.*
```

```
Seam:          This-host sqlite_live overlay
Direction:     bidirectional
Protocol:      Compose override bind remount
Auth:          OS filesystem
Data sent:     live bishop.db under ${BISHOP_DATA_ROOT}/sqlite_live
Data received: snapshots remain under ${BISHOP_DATA_ROOT}/sqlite/snapshots/
Error modes:   scripts that assume sqlite/bishop.db miss the live file unless they resolve sqlite_live
Retry policy:  none — remove docker-compose.override.yml when leaked WAL handles are gone
Owner module:  docker-compose.override.yml, scripts/sqlite_snapshot.py
```

```
Seam:          state-worker HTTP — liveness /health
Direction:     inbound
Protocol:      HTTP GET /health (JSON)
Auth:          none
Data sent:     none
Data received: {"status":"ok"}
Error modes:   non-200; connection refused before process listen
Retry policy:  none (not the compose healthcheck)
Owner module:  services/state-worker/app/main.py
```

```
Seam:          state-worker HTTP — /health/db integrity gate
Direction:     inbound
Protocol:      HTTP GET /health/db (JSON)
Auth:          none (compose healthcheck)
Data sent:     none
Data received: {"status":"ok","detail":"<alembic_version>"} or 503
Error modes:   corrupt DB; empty alembic_version; pool not ready
Retry policy:  compose healthcheck retries (start_period 30s)
Owner module:  services/state-worker/app/main.py, services/state-worker/app/db.py
```

```
Seam:          state-worker HTTP — scraper integration
Direction:     inbound to state-worker
Protocol:      HTTP JSON — GET/POST /scraper-state/{source}, POST /manifest/batch
Auth:          none (internal network)
Data sent:     ManifestIngestEntry batches; scraper checkpoint timestamps
Data received: inserted/skipped counts; ScraperStateSnapshot; 204 on state update
Error modes:   non-2xx; connection refused; batch POST failure aborts adapter pass
Retry policy:  none at HTTP client level; manifest idempotency on server
Owner module:  services/scraper/app/state_worker_client.py → services/state-worker/app/routers/
```

```
Seam:          state-worker HTTP — pre-filter-worker integration
Direction:     inbound to state-worker
Protocol:      HTTP JSON — GET /manifest/poll, POST /batches
Auth:          none
Data sent:     poll claim for DISCOVERED; BatchRegisterRequest at Anthropic submit
Data received: PollResponse; BatchRegisterResponse (201) or 409 batch_conflict
Error modes:   empty poll; profile/rubric hash mismatch; G3 gate failure; min-batch hold
Retry policy:  scheduler interval; idle-flush MAX_HOLD_MINUTES
Owner module:  services/pre-filter-worker/app/state_worker_client.py
```

```
Seam:          state-worker HTTP — batch-poller integration
Direction:     inbound to state-worker
Protocol:      HTTP JSON — GET /batches, PATCH /batches/{id}, POST /batches/{id}/timeout, POST /manifest/pre-filter-results, POST /entries/enrichment-stage1-results, POST /entries/enrichment-stage2-results
Auth:          none
Data sent:     batch status; pre-filter and enrichment result entries; timeout requests
Data received: BatchRecord list/detail; PreFilterResultsResponse counts (incl. parked); 204 on enrichment POSTs
Error modes:   404; 409 invalid_batch_state; untracked batch_type ignored
Retry policy:  poll loop interval; startup_scan reconciles in-flight batches
Owner module:  services/batch-poller/app/clients/state_worker.py
```

```
Seam:          state-worker HTTP — content-scraper integration
Direction:     inbound to state-worker
Protocol:      HTTP JSON — GET /manifest/poll?state=RELEVANCE_PASSED; POST /entries/content; POST /entries/failed
Auth:          none
Data sent:     claimed manifests; {source_id, content_raw}; scrape failure envelopes
Data received: PollResponse; ContentPostResponse; 204 on failed
Error modes:   adapter_not_found; fetch failures → SCRAPE_FAILED; 409 provenance_incomplete
Retry policy:  scheduler interval BISHOP_CONTENT_SCRAPE_POLL_INTERVAL_SEC; failure_envelope on outbound fetches
Owner module:  services/content-scraper/app/loop.py
```

```
Seam:          state-worker HTTP — enrichment-batcher integration
Direction:     inbound to state-worker
Protocol:      HTTP JSON — GET /entries/poll (SCRAPED, ENRICHMENT_STAGE2_QUEUED); POST /batches
Auth:          none internal
Data sent:     BatchRegisterRequest (enrichment_stage1|enrichment_stage2)
Data received: PollResponse; BatchRegisterResponse or 409
Error modes:   hash mismatch; G3 fatal; min-batch hold
Retry policy:  poll interval; MAX_HOLD_MINUTES 30 per stage
Owner module:  services/enrichment-batcher/app/stage1_loop.py, stage2_loop.py
```

```
Seam:          state-worker HTTP — vector-writer integration
Direction:     inbound to state-worker
Protocol:      HTTP JSON — GET /entries/poll?state=VECTOR_WRITE_QUEUED; POST /entries/indexed; POST /entries/failed
Auth:          none
Data sent:     indexed signal; retriable write failures
Data received: PollResponse (content_raw omitted)
Error modes:   LanceDB/BM25/DuckDB write failure → VECTOR_WRITE_FAILED
Retry policy:  vector-writer poll loop; filelock on BM25 persist
Owner module:  services/vector-writer/app/loop.py
```

```
Seam:          state-worker HTTP — parked inbox (soft-launch overlay)
Direction:     inbound; proxied by query-api and ui
Protocol:      HTTP JSON — GET /parked; POST /parked/promote
Auth:          none
Data sent:     source_id to promote RELEVANCE_PARKED → RELEVANCE_PASSED
Data received: parked manifest list
Error modes:   404; 409 if not RELEVANCE_PARKED
Retry policy:  none
Owner module:  services/state-worker/app/routers/parked.py
```

```
Seam:          state-worker — SQLite file
Direction:     bidirectional (writer); inbound read-only from query-api and host scripts
Protocol:      SQLite file at SQLITE_DB_PATH; WAL + busy_timeout
Auth:          filesystem
Data sent:     INSERT/UPDATE for §7 tables incl. batches.source_ids, pre_filter_tier (m8_001)
Data received: SELECT for poll-and-claim, batch queries, escalations, parked, query-api entry reads
Error modes:   integrity_check fail at startup; WAL lock contention; corrupt DB
Retry policy:  none on boot (refuse); sweeps recover lock-state and retry-scheduled rows
Owner module:  services/state-worker/app/db.py, transitions.py
```

```
Seam:          ArXiv Atom export API
Direction:     outbound from scraper
Protocol:      HTTP GET http://export.arxiv.org/api/query (Atom XML)
Auth:          none
Data sent:     search_query, submittedDate range, max_results, sortBy
Data received: Atom feed XML
Error modes:   429; 403/401; 400; network timeout; malformed XML
Retry policy:  failure_envelope + token-bucket
Owner module:  services/scraper/app/adapters/arxiv.py
```

```
Seam:          Scraper outbound — six additional manifest APIs
Direction:     outbound from scraper
Protocol:      HTTPS JSON/GraphQL — GitHub Search, HuggingFace Hub REST, Semantic Scholar Graph, Papers With Code REST, OpenReview notes, LessWrong GraphQL-over-GET
Auth:          optional GITHUB_TOKEN, HUGGINGFACE_TOKEN, SEMANTIC_SCHOLAR_API_KEY
Data sent:     date-bounded search queries, pagination
Data received: manifest metadata
Error modes:   rate limits; unauthenticated low quotas; LessWrong POST broken (GET only)
Retry policy:  failure_envelope + token-bucket; chunked backfill when BISHOP_BACKFILL_ENABLED=1
Owner module:  services/scraper/app/adapters/{github,huggingface,semantic_scholar,paperswithcode,openreview,lesswrong}.py
```

```
Seam:          Outbound content fetch (per source)
Direction:     outbound from content-scraper (vendored adapters)
Protocol:      HTTPS GET / GraphQL GET
Auth:          same optional tokens as scraper (compose currently injects them on scraper; content-scraper image must receive them if authenticated fetch is required)
Data sent:     source-specific query params
Data received: HTML/JSON/text → content_raw (unbounded; no adapter response size cap)
Error modes:   429/403/401/400; malformed JSON/XML; empty HTML; network timeout; huge body fills SQLite before Call 1 truncate (OPEN-023 I-5)
Retry policy:  failure_envelope + token-bucket
Owner module:  services/scraper/app/adapters/* vendored as scraper_app
```

```
Seam:          Anthropic Messages Batches API
Direction:     outbound from pre-filter-worker and enrichment-batcher (submit) and batch-poller (poll/results)
Protocol:      HTTPS JSON — messages.batches.create, batches.retrieve, batches.results
Auth:          ANTHROPIC_API_KEY bearer
Data sent:     batch requests with cached system blocks (keys A/B/C); custom_id encoded source_id; max_tokens 256/1024/512. User role is untrusted title/abstract (Gate 1), title+content_raw (Call 1), or title+Call-1 summary (Call 2) — not in the cached prefix.
Data received: external_batch_id; per-item JSON; cache_creation_input_tokens / cache_read_input_tokens
Error modes:   HTTP 400 invalid model (fatal); rate limits; batch expired; prefix below cache floor → zero cache writes; prompt injection can steer pass/park/score (integrity, not an HTTP error) — OPEN-023
Retry policy:  G3 verify before first submit; scheduler re-polls; batch timeout via state-worker
Owner module:  services/pre-filter-worker/app/anthropic_batch_client.py, services/enrichment-batcher/app/anthropic_batch_client.py, services/batch-poller/app/clients/anthropic.py, bishop_shared/prompt_cache.py
```

```
Seam:          LanceDB / DuckDB / BM25 filesystem stores
Direction:     bidirectional (writer: vector-writer; readers: query-api)
Protocol:      file I/O — lancedb table entries; duckdb bishop.duckdb; bm25/{domain}/{main|challenge_hooks}/index.pkl
Auth:          OS mount permissions
Data sent:     embeddings, tokenized corpora, metadata mirror rows
Data received: search-time reads (DuckDB read_only, BM25 COW reload, LanceDB cosine)
Error modes:   missing table/dir (G7 cold-start WARN); DuckDB lock skip; corrupt pickle; BM25 lock timeout
Retry policy:  idempotent skip if source_id exists; BM25_RELOAD_INTERVAL_SEC background reload
Owner module:  services/vector-writer/app/stores/*, services/query-api/app/stores/*, bishop_shared/indexing_config.py
```

```
Seam:          query-api — host port exposure
Direction:     inbound from host/ui
Protocol:      HTTP FastAPI — GET /search, /recent, /entries/{id}, /batches*, /escalations, /parked; write proxies POST/PATCH to state-worker; SQLite mode=ro for GET /entries/{id}
Auth:          none (local-first)
Data sent:     query strings, filter params, promote/retry/permanent-fail/reading-status bodies
Data received: JSON search hits, entry detail, proxied state-worker responses
Error modes:   validation 400; upstream 502; sqlite_read_failed 500; DuckDB lock → empty metadata filter; LAN client on QUERY_API_HOST_PORT has the same surface (OPEN-023 I-7)
Retry policy:  none at HTTP layer
Owner module:  services/query-api/app/main.py, routers/*, sqlite_reader.py
```

```
Seam:          ui — host port exposure
Direction:     inbound browser; outbound to query-api only
Protocol:      HTTP FastAPI + Jinja/HTMX — /batches, /explorer, /parked, /escalations, /search, /entries/{id}
Auth:          none
Data sent:     form posts (promote, retry, permanent-fail, reading-status)
Data received: HTML rendered from query-api JSON (Jinja autoescape on; entry.url as href with no scheme allowlist)
Error modes:   query-api unreachable → error slot in template; click XSS if stored url is javascript:/data: (OPEN-023 I-6)
Retry policy:  none
Owner module:  services/ui/app/main.py; compose QUERY_API_URL=http://query-api:8000
```

```
Seam:          Host filesystem — SQLite snapshot/restore
Direction:     host-side scripts; backup from live bishop.db
Protocol:      SQLite online backup API; PRAGMA integrity_check; optional docker run --volume bishop-sqlite
Auth:          OS filesystem
Data sent:     snapshot files under sqlite/snapshots/bishop-YYYYMMDD-HHMMSS.db
Data received: restore swaps live DB after integrity check
Error modes:   integrity_check fail → snapshot deleted; Windows bind-mount lock contention
Retry policy:  TTL prune (24h); interval 30 min in loop mode
Owner module:  scripts/sqlite_snapshot.py, scripts/sqlite_restore.py
```
