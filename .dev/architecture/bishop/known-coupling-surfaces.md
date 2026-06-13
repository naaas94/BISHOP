Section:      known-coupling-surfaces
Version:      1.2.0
Last updated: 2026-06-13

```
Surface:      BISHOP_SERVICES tuple ↔ docker-compose.yml service keys ↔ services/<name>/ directory names
Shared by:    bishop_shared.constants ↔ docker-compose.yml ↔ services/* ↔ tests/test_service_stubs.py
Failure mode: Renaming a service in one location breaks compose DNS, build context paths, or stub tests
Confirmed:    yes — source: bishop_shared/constants.py, docker-compose.yml, tests
```

```
Surface:      BISHOP_VOLUME_MOUNTS host_suffix ↔ container_path pairs
Shared by:    bishop_shared.constants ↔ docker-compose.yml ↔ scripts/init-volumes.{sh,ps1} ↔ tests/test_compose.py
Failure mode: New volume suffix without init script or compose matrix update leaves G1 writability failing
Confirmed:    yes — source: T1 decision log, test_compose.py
```

```
Surface:      Per-service volume mount subset (T1 matrix)
Shared by:    .dev/decision-logs/m0-workshop/T1-repo-layout.md ↔ tests/test_compose.py::SERVICE_VOLUME_SUFFIXES ↔ docker-compose.yml
Failure mode: Matrix encoded only in tests/decision log, not in bishop_shared — drift if compose edited without test update
Confirmed:    yes — source: T1 decision log, tests/test_compose.py
```

```
Surface:      STATE_WORKER_INTERNAL_PORT (8000)
Shared by:    bishop_shared.constants ↔ state-worker uvicorn bind ↔ compose healthcheck ↔ query-api stub ↔ STATE_WORKER_URL path segment
Failure mode: Health gate passes internally but dependent URL or stub bind points at wrong port
Confirmed:    yes — source: constants.py, docker-compose.yml, tests
```

```
Surface:      Host port mapping query-api ${QUERY_API_HOST_PORT}:8000 and ui ${UI_HOST_PORT}:80
Shared by:    bishop_shared.constants ↔ docker-compose.yml ↔ verify-g1.sh ↔ ui stub UI_CONTAINER_PORT == 80
Failure mode: Host unreachable or wrong port if constants, compose, or ui listen port diverge
Confirmed:    yes — source: T1/T4 decision logs, tests
```

```
Surface:      Docker image tags bishop/<service>:<milestone>
Shared by:    docker-compose.yml image lines ↔ tests/test_compose.py::test_image_tags_use_milestone_convention
Failure mode: state-worker m1, scraper m2, pre-filter-worker m3, batch-poller m3, others m0 — tag change breaks compose test
Confirmed:    yes — source: docker-compose.yml, tests/test_compose.py (M3 T6)
```

```
Surface:      Docker network name bishop-internal
Shared by:    docker-compose.yml networks section ↔ tests/test_compose.py::test_bishop_internal_network
Failure mode: Service discovery failure if network name changes inconsistently
Confirmed:    yes — source: docker-compose.yml, T4 decision log
```

```
Surface:      BISHOP_DATA_ROOT env interpolation
Shared by:    .env.example ↔ docker-compose.yml ↔ init-volumes scripts ↔ verify-g1.sh
Failure mode: Volumes bind to wrong host path; G1 writability probes wrong directory (especially on Windows)
Confirmed:    yes — source: .env.example, T1 decision log
```

```
Surface:      STATE_WORKER_URL=http://state-worker:8000
Shared by:    docker-compose.yml environment on eight dependents ↔ scraper app/config.py STATE_WORKER_BASE_URL ↔ tests/test_compose.py
Failure mode: Scraper cannot reach state-worker if env removed or URL path wrong
Confirmed:    yes — source: docker-compose.yml, services/scraper/app/config.py (M2 T1)
```

```
Surface:      SQLITE_DB_PATH = /app/data/sqlite/bishop.db
Shared by:    bishop_shared/constants.py ↔ state-worker app/db.py ↔ compose sqlite volume mount ↔ tests/test_constants.py
Failure mode: state-worker opens wrong file; future direct readers (batch-poller, query-api) diverge
Confirmed:    yes — source: T1-schema-foundation decision log, M1 audit F-013 area
```

```
Surface:      §20 SourceEnum / DomainEnum literals — dual definition
Shared by:    bishop_shared/enums.py ↔ services/state-worker/app/enums.py ↔ tests/test_shared_enums.py hardcoded literal sets
Failure mode: Wire incompatibility between scraper POST bodies and state-worker validation if literals drift
Confirmed:    yes — source: tests/test_shared_enums.py (M2 T1 drift guard)
```

```
Surface:      source_id canonical format "{source}:{raw_id}"
Shared by:    SourceAdapter.make_source_id ↔ ArxivAdapter raw ID extraction ↔ state-worker manifest PK ↔ idempotency tests
Failure mode: Duplicate or orphan rows if format changes in adapter but not ingest path
Confirmed:    yes — source: adapters/base.py, M2 audit idempotency tests
```

```
Surface:      ManifestIngestEntry.domain wire value
Shared by:    ArxivAdapter (hardcoded professional) ↔ POST /manifest/batch ↔ manifest table domain column
Failure mode: Downstream pre-filter routing breaks if domain assignment changes per source without contract update
Confirmed:    yes — source: M2 audit C1 (domain wire)
```

```
Surface:      G2 pytest module list in verify-g2.sh, verify-m2.sh, and verify-m3.sh
Shared by:    scripts/verify-g2.sh ↔ scripts/verify-m2.sh ↔ scripts/verify-m3.sh ↔ tests/test_verify_g2.py, test_verify_m2.py, test_verify_m3.py
Failure mode: New contract tests not in gate script give false confidence (M1 audit F-014: alerts test outside G2 script)
Confirmed:    yes — source: dev_log.md F-014, scripts/verify-g2.sh, scripts/verify-m3.sh
```

```
Surface:      ANTHROPIC_MODEL_PREFILTER model string
Shared by:    bishop_shared/anthropic_config.py ↔ pre-filter-worker submit payload ↔ batch-poller ↔ verify-g3.sh ↔ G3 probe
Failure mode: HTTP 400 model_string_fatal if Anthropic deprecates dated snapshot without coordinated bump
Confirmed:    yes — source: M3 T1 G3 gate, anthropic_config.py
```

```
Surface:      Profile canonical_hash ↔ runtime compute_profile_hash
Shared by:    config/profiles/professional_v1.0.0.yaml ↔ bishop_shared/profile_renderer.py ↔ pre-filter-worker loop
Failure mode: Batch submit blocked; CRITICAL profile_hash_mismatch alert if YAML edited without hash recompute
Confirmed:    yes — source: M3 T2 decision log, test_profile_renderer.py
```

```
Surface:      Profile version "1.0.0" and filename professional_v1.0.0.yaml
Shared by:    YAML version field ↔ _PROFILE_FILENAME map ↔ BatchRegisterRequest.profile_version ↔ PreFilterResultsRequest
Failure mode: Results rejected or wrong profile attribution if version string diverges across registration and results POST
Confirmed:    yes — source: profile_renderer.py, state-worker batch registration
```

```
Surface:      Anthropic batch custom_id = manifest source_id
Shared by:    pre-filter-worker anthropic_batch_client ↔ batch-poller result join ↔ batches.source_ids column
Failure mode: Results cannot be matched to manifests if custom_id format changes
Confirmed:    yes — source: M3 T4/T5 decision logs, test_m3_integration.py
```

```
Surface:      batch_type "pre_filter" filter
Shared by:    BatchTypeEnum.PRE_FILTER ↔ batch-poller PRE_FILTER_BATCH_TYPE ↔ enrichment batches (future)
Failure mode: Enrichment batches incorrectly processed by M3 poller if type string drifts
Confirmed:    yes — source: batch-poller/app/models.py, batch-poller loop
```

```
Surface:      G3 verification gate chain (verify-m3 → verify-g3)
Shared by:    scripts/verify-m3.sh ↔ scripts/verify-g3.sh ↔ pre-filter-worker ensure_g3_verified ↔ BISHOP_G3_VERIFIED bypass
Failure mode: CI passes with bypass env set; live deploy fails without API key or on model deprecation
Confirmed:    yes — source: M3 T1/T6, verify-m3.sh
```

```
Surface:      Host profiles volume mount path
Shared by:    docker-compose.yml ${BISHOP_DATA_ROOT}/profiles ↔ PROFILES_CONTAINER_DIR ↔ seed-profiles scripts
Failure mode: pre-filter-worker cannot load profile if mount path or seed script diverges from renderer constant
Confirmed:    yes — source: docker-compose.yml, profile_renderer.py, seed-profiles.sh
```

```
Surface:      state-worker start_period 30s (M1)
Shared by:    docker-compose.yml healthcheck ↔ tests/test_compose.py
Failure mode: Dependents start before migrations complete if start_period shortened without test update
Confirmed:    yes — source: M1 T5/T6, test_compose.py
```
