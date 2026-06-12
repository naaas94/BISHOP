Section:      data-contract-registry
Version:      1.1.0
Last updated: 2026-06-12

## M0 contracts (retained)

```
Contract:       HealthResponse
Module:         services/state-worker/app/models/__init__.py
Serialization:  Pydantic model
Version:        unversioned — tracked by git blame
Purpose:        Canonical JSON body for state-worker liveness probe
Fields:
  - status: Literal["ok"] — must be exactly "ok"
Validators:     status restricted to single literal "ok"
Consumers:      services/state-worker/app/main.py, compose healthcheck, scripts/verify-g1.sh
Last changed:   2026-06-10
```

```
Contract:       VolumeMount
Module:         bishop_shared/constants.py
Serialization:  dataclass (frozen)
Version:        unversioned — tracked by git blame
Purpose:        Typed pair linking host subdirectory under BISHOP_DATA_ROOT to container mount path
Fields:
  - host_suffix: str
  - container_path: str
Validators:     none (frozen dataclass)
Consumers:      BISHOP_VOLUME_MOUNTS, tests/test_constants.py, tests/test_compose.py
Last changed:   2026-06-10
```

```
Contract:       SQLITE_DB_PATH
Module:         bishop_shared/constants.py
Serialization:  constant string
Version:        unversioned — tracked by git blame
Purpose:        Authoritative absolute container path for SQLite database file
Fields:
  - value: "/app/data/sqlite/bishop.db" (derived from volume mount + SQLITE_DB_FILENAME)
Validators:     tests/test_constants.py::test_sqlite_db_filename
Consumers:      services/state-worker/app/db.py, future direct SQLite readers (batch-poller, query-api)
Last changed:   2026-06-11
```

```
Contract:       Compose volume interpolation
Module:         docker-compose.yml
Serialization:  Docker Compose YAML env interpolation
Version:        unversioned — tracked by git blame
Purpose:        Bind host persistent dirs to container paths per per-service matrix
Fields:
  - host path: ${BISHOP_DATA_ROOT}/<host_suffix>
  - container path: from BISHOP_VOLUME_MOUNTS.container_path
Validators:     tests/test_compose.py::test_volume_matrix
Consumers:      all services with volume mounts, init-volumes scripts
Last changed:   2026-06-10
```

```
Contract:       STATE_WORKER_URL
Module:         docker-compose.yml (environment on dependents)
Serialization:  plain string env var
Version:        unversioned — tracked by git blame
Purpose:        Internal base URL for state-worker HTTP clients
Fields:
  - value: http://state-worker:8000
Validators:     compose test asserts presence on all non-state-worker services
Consumers:      services/scraper/app/config.py (as STATE_WORKER_BASE_URL)
Last changed:   2026-06-12
```

## M1 — SQLite schema and domain models (§7)

```
Contract:       manifest (table)
Module:         services/state-worker/alembic/versions/
Serialization:  SQLite table via Alembic migration
Version:        unversioned — tracked by git blame
Purpose:        Manifest discovery records and pre-filter state
Fields:
  - source_id: TEXT PK — canonical "{source}:{raw_id}"
  - source, url, title, abstract, published_at, discovered_at, domain
  - profile_version, pre_filter_batch_id, relevance_decision, pre_filter_rationale
  - processing_state, retry_count, next_retry_at
Validators:     relevance_decision ∈ {0, 1, NULL}; processing_state ∈ ProcessingState
Consumers:      transitions.py, manifest router, poll router
Last changed:   2026-06-11
```

```
Contract:       entries (table)
Module:         services/state-worker/alembic/versions/
Serialization:  SQLite table via Alembic migration
Version:        unversioned — tracked by git blame
Purpose:        Full content records post-scrape through enrichment and indexing
Fields:
  - id: TEXT PK; source_id FK; content_raw; enrichment fields; processing_state; retry fields
  - JSON list columns: concepts, tags, challenge_hooks, references, cited_by, top_entries
Validators:     ProcessingState transitions enforced in transitions.py
Consumers:      transitions.py, entries router, poll router
Last changed:   2026-06-11
```

```
Contract:       batches, error_log, oov_tags_log, scraper_state (tables)
Module:         services/state-worker/alembic/versions/
Serialization:  SQLite table via Alembic migration
Version:        unversioned — tracked by git blame
Purpose:        Batch tracking (§7.3), failure/alert log (§7.4), OOV tags (§7.5), scraper checkpoint (§7.6)
Fields:         per bishop_spec_0_6.md §7 and domain models
Validators:     enum columns match §20 vocabularies
Consumers:      respective routers, transitions.py, alerts.py
Last changed:   2026-06-11
```

```
Contract:       ManifestEntry
Module:         services/state-worker/app/models/domain.py
Serialization:  Pydantic model
Version:        unversioned — tracked by git blame
Purpose:        In-process representation of manifest table row
Fields:         mirrors manifest table columns
Validators:     relevance_decision binary; to_db_row/from_db_row serialization
Consumers:      transitions.py, routers
Last changed:   2026-06-11
```

```
Contract:       Entry
Module:         services/state-worker/app/models/domain.py
Serialization:  Pydantic model
Version:        unversioned — tracked by git blame
Purpose:        In-process representation of entries table row
Fields:         mirrors entries table including JSON list fields
Validators:     encode_json_list_fields / decode_json_list_fields for SQLite round-trip
Consumers:      transitions.py, poll router (content_raw omission at VECTOR_WRITE_QUEUED)
Last changed:   2026-06-11
```

```
Contract:       ProcessingState
Module:         services/state-worker/app/enums.py
Serialization:  str Enum (22 members)
Version:        unversioned — tracked by git blame
Purpose:        Authoritative §6.1 processing state machine vocabulary
Fields:         DISCOVERED through PERMANENTLY_FAILED (see enum definition)
Validators:     transition guards in transitions.py
Consumers:      all state-worker routers and transitions
Last changed:   2026-06-11
```

```
Contract:       ManifestBatchRequest / ManifestBatchResponse
Module:         services/state-worker/app/models/http.py
Serialization:  Pydantic model
Version:        unversioned — tracked by git blame
Purpose:        HTTP wire format for POST /manifest/batch
Fields:
  - request.entries: list of manifest ingest fields
  - response.inserted: int; response.skipped: int
Validators:     Pydantic field types; idempotent skip on duplicate source_id
Consumers:      manifest router, scraper StateWorkerClient
Last changed:   2026-06-11
```

```
Contract:       PollResponse
Module:         services/state-worker/app/models/http.py
Serialization:  Pydantic model
Version:        unversioned — tracked by git blame
Purpose:        HTTP wire format for poll-and-claim endpoints
Fields:
  - entries: list[dict] — claimed rows; content_raw omitted at VECTOR_WRITE_QUEUED
Validators:     state query param must be valid poll-eligible ProcessingState
Consumers:      manifest poll router, entries poll router, G2 contract test
Last changed:   2026-06-11
```

```
Contract:       ScraperStateResponse / ScraperStateUpdateRequest
Module:         services/state-worker/app/models/http.py
Serialization:  Pydantic model
Version:        unversioned — tracked by git blame
Purpose:        HTTP wire format for scraper checkpoint read/write
Fields:
  - response: source, last_successful_run_at, updated_at
  - update request: timestamp (ISO 8601)
Validators:     POST returns 204 on success
Consumers:      scraper_state router, scraper StateWorkerClient
Last changed:   2026-06-11
```

## M2 — scraper wire DTOs

```
Contract:       ManifestIngestEntry
Module:         services/scraper/app/models.py
Serialization:  Pydantic model
Version:        unversioned — tracked by git blame
Purpose:        Scraper-side manifest row for POST /manifest/batch (subset of ManifestEntry)
Fields:
  - source_id, source, url, title, abstract, published_at, domain
Validators:     source_id format "{source}:{raw_id}" via make_source_id
Consumers:      adapters, StateWorkerClient, loop.py
Last changed:   2026-06-12
```

```
Contract:       ManifestBatchResult
Module:         services/scraper/app/models.py
Serialization:  Pydantic model
Version:        unversioned — tracked by git blame
Purpose:        Client-side parse of manifest batch response
Fields:
  - inserted: int; skipped: int
Validators:     none
Consumers:      StateWorkerClient, loop.py
Last changed:   2026-06-12
```

```
Contract:       RateLimit
Module:         services/scraper/app/rate_limit.py
Serialization:  dataclass
Version:        unversioned — tracked by git blame
Purpose:        Per-source rate limit and retry config (§15.1, §15.2)
Fields:
  - requests_per_second, burst, max_retries, backoff_strategy
Validators:     SOURCE_RATE_LIMITS keyed by source string
Consumers:      adapters, failure_envelope
Last changed:   2026-06-12
```

```
Contract:       ArXiv Atom feed response
Module:         (external) export.arxiv.org
Serialization:  Atom XML (application/atom+xml)
Version:        unversioned — external API
Purpose:        Manifest discovery input for ArxivAdapter
Fields:
  - atom:entry elements with id, title, summary, published, link
Validators:     entries without id/title silently skipped (T4 decision log)
Consumers:      services/scraper/app/adapters/arxiv.py::parse_atom_feed
Last changed:   2026-06-12
```

**Deferred contracts (not present in code):** LanceDB/DuckDB/BM25 payloads, enrichment batch API wire formats, NL profile YAML schema, `fetch_content` response body — per charter §M3+.
