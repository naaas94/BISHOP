Section:      data-contract-registry
Version:      1.0.0
Last updated: 2026-06-10

```
Contract:       HealthResponse
Module:         services/state-worker/app/models.py
Serialization:  Pydantic model
Version:        unversioned — tracked by git blame
Purpose:        Canonical JSON body for state-worker liveness probe
Fields:
  - status: Literal["ok"] — must be exactly "ok" at M0
Validators:     status restricted to single literal "ok"
Consumers:      services/state-worker/app/main.py, compose healthcheck, scripts/verify-g1.sh, tests/test_state_worker_health.py
Last changed:   2026-06-10
```

```
Contract:       VolumeMount
Module:         bishop_shared/constants.py
Serialization:  dataclass (frozen)
Version:        unversioned — tracked by git blame
Purpose:        Typed pair linking host subdirectory under BISHOP_DATA_ROOT to container mount path
Fields:
  - host_suffix: str — directory name under BISHOP_DATA_ROOT (e.g. "sqlite")
  - container_path: str — in-container mount target (e.g. "/app/data/sqlite")
Validators:     none (frozen dataclass)
Consumers:      BISHOP_VOLUME_MOUNTS, tests/test_constants.py, tests/test_compose.py
Last changed:   2026-06-10
```

```
Contract:       BISHOP_SERVICES
Module:         bishop_shared/constants.py
Serialization:  tuple[str, ...]
Version:        unversioned — tracked by git blame
Purpose:        Authoritative list of nine Docker Compose service keys matching bishop_spec_0_6.md §9
Fields:
  - (ordered tuple of nine service name strings)
Validators:     frozen at M0; tests assert exact spec ordering and count
Consumers:      docker-compose.yml, all compose/stub tests
Last changed:   2026-06-10
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
Validators:     tests/test_compose.py::test_volume_matrix enforces per-service subset
Consumers:      all services with volume mounts, init-volumes scripts, verify-g1.sh
Last changed:   2026-06-10
```

```
Contract:       STATE_WORKER_URL
Module:         docker-compose.yml (environment on eight dependents)
Serialization:  plain string env var
Version:        unversioned — tracked by git blame
Purpose:        Reserved internal base URL for state-worker HTTP client use post-M0
Fields:
  - value: http://state-worker:8000
Validators:     compose test asserts presence on all non-state-worker services; unused in M0 stub code
Consumers:      future pipeline workers (M1+)
Last changed:   2026-06-10
```

**Deferred contracts (not present in code at M0):** `ProcessingState`, manifest/entry/batch Pydantic models, SQLite schema, LanceDB/DuckDB/BM25 payloads — see charter §M1 and bishop_spec_0_6.md §6–§7.
