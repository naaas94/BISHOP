# T1 — Docker alembic root resolution (amendment)

**Plan:** m1-state-kernel · **Date:** 2026-06-13 · **Status:** active

## Problem

`state-worker` failed on `docker compose up` during FastAPI lifespan startup:

```
IndexError: 3
  File "/app/app/db.py", line 24, in _repo_root
    for candidate in (here.parents[3], here.parents[1], Path("/app")):
```

The Dockerfile copies `services/state-worker/app` to `/app/app/`, so `db.py` resolves to `/app/app/db.py` with only three ancestors (`/app/app`, `/app`, `/`). T1 assumed `parents[3]` would always exist (true for local checkout depth `…/services/state-worker/app/db.py`, false in the container). Python evaluates tuple elements eagerly, so the loop never reached `parents[1]` or `/app` where `alembic.ini` lives.

Pytest migration tests passed because they import `app.db` from the repo tree, not from the Docker layout.

## Chosen approach

- Build candidate list as `[Path("/app")] + list(here.parents)` and return the first directory containing `alembic.ini`.
- Log resolved root at INFO: `alembic config root: <path>` when migrations run.
- Regression test `test_repo_root_resolves_shallow_app_layout` monkeypatches `__file__` to a two-level `/app/app/db.py` layout.

## Alternatives rejected

- **Hard-code `/app` only in Docker:** Rejected — breaks local `pytest` and dev runs where alembic lives at repo root.
- **Try/except around `parents[3]` only:** Rejected — fixed indices remain fragile if packaging layout changes again; parent walk is layout-agnostic.
- **Move `alembic.ini` under `services/state-worker/`:** Rejected — out of scope; Alembic at repo root is established M1 contract and Dockerfile already COPYs to `/app`.

## Assumptions made

- Docker `WORKDIR /app` and `COPY alembic.ini alembic.ini` remain the container anchor (unchanged from T1 Dockerfile).
- At most one `alembic.ini` appears on the walk from `/app` and `here.parents`; first match is correct.

## Items deferred

- **Live `docker compose up` in CI:** Same deferral as M3–M7 verify scripts; fix validated by unit falsifier plus manual compose smoke.
- **Supersede T1-schema-foundation.md assumption (line 39):** Left as historical record; this log amends that assumption.
