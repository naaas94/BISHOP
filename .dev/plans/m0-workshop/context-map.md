# Context Map — M0 Implementation Workshop

**Plan name:** `m0-workshop`  
**Generated:** 2026-06-09  
**Skill version:** pre-plan 0.2 (greenfield waiver — no existing code to traverse)  
**Commit SHA:** `f2352147e44fb03647a102ceda9f48e75475daca`  
**Readiness verdict:** **READY**

---

## §Scope boundary

Greenfield repository. Tracked files at generation time: `bishop_spec_0_6.md`, `.dev/bishop_program_charter.md`, `.dev/bishop_program_rationale.md`. No application code, Docker artifacts, or architecture folder. Prior milestone handoff: none (first milestone).

**Root paths (planned, do not exist yet):**
- `docker-compose.yml` — M0 deliverable; compose skeleton anchor
- `services/` — per-service Dockerfiles and entry points (9 services)
- `scripts/` — volume init and G1 verification

**Explicit exclusions:** All §23/§24 deferred items; Alembic/SQLite schema; §9.1 REST beyond `GET /health`; source adapters; NL profiles; architecture folder (post-M0 per charter §7).

**Visited-set size:** 3 (existing tracked files only).

---

## §File map

| path | role | in_task_scope | rationale |
|------|------|---------------|-----------|
| `bishop_spec_0_6.md` | Normative architecture spec | adjacent | Binding source for service names, volumes, health contract |
| `.dev/bishop_program_charter.md` | Program milestone index | adjacent | M0 intent, gates G0/G1, non-goals |
| `docker-compose.yml` | Compose skeleton | direct | M0 primary deliverable |
| `services/state-worker/` | state-worker container + `/health` | direct | G1 exit gate |
| `services/scraper/` | scraper stub | direct | One of nine services |
| `services/pre-filter-worker/` | pre-filter stub | direct | One of nine services |
| `services/content-scraper/` | content-scraper stub | direct | One of nine services |
| `services/enrichment-batcher/` | enrichment-batcher stub | direct | One of nine services |
| `services/batch-poller/` | batch-poller stub | direct | One of nine services |
| `services/vector-writer/` | vector-writer stub | direct | One of nine services |
| `services/query-api/` | query-api stub + host port | direct | Host-reachable per §9 |
| `services/ui/` | ui stub + host port | direct | Host-reachable per §9 |
| `scripts/init-volumes.sh` | Host volume directory bootstrap | direct | G1 writable dirs |
| `scripts/init-volumes.ps1` | Windows host volume bootstrap | direct | Developer on win32 |
| `scripts/verify-g1.sh` | G1 smoke verification | direct | Exit gate automation |
| `.env.example` | Frozen host port + path vars | direct | Compose contract surface |
| `bishop_shared/constants.py` | Frozen service/volume/port constants | direct | Typed parse + test anchor |

---

## §Interface inventory

No existing public interfaces. Planned interfaces introduced in M0 (all `unknown` stability until landed):

| symbol | kind | signature | consumed_by | stability | test_file |
|--------|------|-----------|-------------|-----------|-----------|
| `BISHOP_VOLUME_MOUNTS` | constant | 6 host→container path pairs per §8.5 | compose, init scripts | unknown | `tests/test_constants.py` |
| `STATE_WORKER_INTERNAL_PORT` | constant | `8000` | compose healthcheck, stubs | unknown | `tests/test_constants.py` |
| `QUERY_API_HOST_PORT` | constant | `8080` | compose, verify-g1 | unknown | `tests/test_constants.py` |
| `UI_HOST_PORT` | constant | `8081` | compose, verify-g1 | unknown | `tests/test_constants.py` |
| `GET /health` | function route | `200 {"status":"ok"}` on state-worker | compose `depends_on` | unknown | verify-g1 script |

---

## §Coupling surfaces

| ID | surface | coupling | subtasks affected |
|----|---------|----------|-------------------|
| C1 | `docker-compose.yml` service keys | Must match spec §9 names exactly (`scraper`, `state-worker`, …) | T1, T4 |
| C2 | `depends_on: state-worker: condition: service_healthy` | All 8 dependents block on state-worker healthcheck | T3, T4 |
| C3 | Host volume paths `~/bishop_data/*` | Windows vs Linux path expansion in compose | T1, T4, T5 |
| C4 | Per-service volume subset | Over-mounting vs under-mounting affects M1+ | T2, T4 |

---

## §Ambiguity flags

| ID | flag | resolution owner |
|----|------|------------------|
| A1 | Charter M0 exit gate (L101) cites `curl localhost:<state-worker-port>/health`; spec §9 (L599) and §17.3 (L1288) state only `query-api` and `ui` are host port-mapped | Orch plan §2: G1 verifies `/health` via compose healthcheck + in-container curl; no state-worker host port |
| A2 | Spec §22 mentions "repository structure" but does not prescribe directory layout | Orch T1 decision log: `services/<name>/` monorepo layout |
| A3 | Host port numbers not in spec | Orch T1 freezes 8080 (query-api), 8081 (ui), internal 8000 (state-worker) |
| A4 | Which services mount which of the six volume paths at M0 | Orch T1 decision log: minimal per-service subset + init script creates all six host dirs |
| A5 | `~/bishop_data` on Windows host (user env win32) | T1 provides `.env.example` with `${BISHOP_DATA_ROOT}` default; compose uses env interpolation |

---

## §Prior reasoning

None (first milestone).
