Section:      known-coupling-surfaces
Version:      1.0.0
Last updated: 2026-06-10

```
Surface:      BISHOP_SERVICES tuple ↔ docker-compose.yml service keys ↔ services/<name>/ directory names
Shared by:    bishop_shared.constants (authoritative list) ↔ docker-compose.yml (service blocks) ↔ services/* (filesystem layout) ↔ tests/test_service_stubs.py (directory name check)
Failure mode: Renaming a service in one location breaks compose DNS, build context paths, or stub tests
Confirmed:    yes — source: bishop_shared/constants.py, docker-compose.yml, tests/test_constants.py, tests/test_compose.py
```

```
Surface:      BISHOP_VOLUME_MOUNTS host_suffix ↔ container_path pairs
Shared by:    bishop_shared.constants ↔ docker-compose.yml volume lines ↔ scripts/init-volumes.{sh,ps1} ↔ tests/test_compose.py SERVICE_VOLUME_SUFFIXES matrix
Failure mode: New volume suffix in constants without init script or compose matrix update leaves G1 writability or mount checks failing
Confirmed:    yes — source: T1 decision log, test_compose.py
```

```
Surface:      Per-service volume mount subset (T1 matrix)
Shared by:    .dev/decision-logs/m0-workshop/T1-repo-layout.md ↔ tests/test_compose.py::SERVICE_VOLUME_SUFFIXES ↔ docker-compose.yml per-service volumes blocks
Failure mode: Matrix encoded only in tests/decision log, not in bishop_shared — drift if compose edited without test update
Confirmed:    yes — source: T1 decision log, tests/test_compose.py
```

```
Surface:      STATE_WORKER_INTERNAL_PORT (8000)
Shared by:    bishop_shared.constants ↔ state-worker uvicorn bind ↔ compose healthcheck URL ↔ query-api stub HTTPServer port ↔ docker-compose STATE_WORKER_URL path segment
Failure mode: Health gate passes internally but dependent URL or stub bind points at wrong port
Confirmed:    yes — source: constants.py, docker-compose.yml, tests
```

```
Surface:      Host port mapping query-api ${QUERY_API_HOST_PORT}:8000 and ui ${UI_HOST_PORT}:80
Shared by:    bishop_shared.constants (8080, 8081 defaults) ↔ docker-compose.yml ports blocks ↔ verify-g1.sh host curl ↔ ui stub UI_CONTAINER_PORT == 80
Failure mode: Host unreachable or wrong port if constants, compose, or ui listen port diverge
Confirmed:    yes — source: T1/T4 decision logs, tests/test_compose.py, tests/test_service_stubs.py
```

```
Surface:      Docker image tags bishop/<service>:m0
Shared by:    docker-compose.yml image lines ↔ tests/test_compose.py::test_image_tags_use_m0_convention
Failure mode: Tag convention change breaks compose test; CI pull expectations may drift
Confirmed:    yes — source: docker-compose.yml, tests/test_compose.py
```

```
Surface:      Docker network name bishop-internal
Shared by:    docker-compose.yml networks section ↔ tests/test_compose.py::test_bishop_internal_network
Failure mode: Service discovery failure if network name or attach config changes inconsistently
Confirmed:    yes — source: docker-compose.yml, T4 decision log
```

```
Surface:      BISHOP_DATA_ROOT env interpolation
Shared by:    .env.example ↔ docker-compose.yml volume host paths ↔ init-volumes scripts ↔ verify-g1.sh ROOT expansion
Failure mode: Volumes bind to wrong host path; G1 writability probes wrong directory (especially on Windows)
Confirmed:    yes — source: .env.example, T1 decision log; Windows tilde behavior partially confirmed on audit host only
```

```
Surface:      STATE_WORKER_URL=http://state-worker:8000
Shared by:    docker-compose.yml environment on eight dependents ↔ tests/test_compose.py (presence assertion only)
Failure mode: Future HTTP clients assume URL present; removing env breaks M1+ workers without compile-time signal
Confirmed:    yes — source: docker-compose.yml, T4 decision log; unused in M0 stub code
```
