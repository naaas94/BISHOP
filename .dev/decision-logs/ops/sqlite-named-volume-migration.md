# SQLite Docker named-volume migration — proposal + tooling (Phase 1)

**Status:** proposal + tooling landed, **cutover NOT executed** · 2026-09-11
**Read first:** `.dev/decision-logs/ops/sqlite-snapshot-and-integrity-gate.md` (incident history, root
cause, and why this item was deferred out of that packet), `.dev/sqlite.md`, `.dev/still_open.md` OPEN-007.
**Scope:** `sqlite` mount only, per OPEN-007's outstanding operator decision. `lancedb`, `duckdb`,
`bm25`, `logs`, `profiles` stay bind mounts — not addressed here.

This document is Phase 1: design + tooling + tests. It does not change `docker-compose.yml`, does
not run the cutover, and does not touch `C:/Users/Ale/bishop_data/**`. The live stack (project
`bishop`, 9 containers) was up the entire time this work was done and was never brought down,
recreated, or modified by anything in this document or its accompanying code.

---

## 1. What residual risk this closes, and what it does not

The 2026-09-11 incident packet (`sqlite-snapshot-and-integrity-gate.md` §2) found the actual proximate
cause of that specific corruption: a code defect (`run_retry_sweep` skipping `_prepare_conn`, an
exception leaving a write transaction open, `get_db()` returning that connection to the pool anyway).
That is fixed. It is tempting to conclude the bind mount was never a problem — the packet itself is
careful not to conclude that:

> "The bind mount is still a plausible contributor to the *physical* page tearing, and the
> named-volume migration remains a follow-up. But the write-lock deadlock, the 500 storm, and the
> silence were all in our code."

The September corruption signature was **torn btree + overflow pages** (`overflow list length is 12
but should be 14`, `2nd reference to page 2976`) — a different failure class from June's file
replacement. Torn pages are the textbook symptom of a write landing on the wrong side of an `mmap`/
byte-range-lock boundary, which is exactly the class of bug Docker Desktop for Windows bind mounts are
documented to have with SQLite WAL:

- WAL relies on the writer's `fsync`/`fdatasync` semantics and on other processes observing
  byte-range locks on the `-shm` file to coordinate readers and the single writer. Windows bind
  mounts proxy file I/O from the Linux VM through a translation layer (grpcFUSE-style on older Docker
  Desktop, VirtioFS-backed 9p-like semantics more recently) that does not implement POSIX
  byte-range advisory locking and `mmap` coherency identically to a native Linux filesystem.
- SQLite's own recommendations (`https://www.sqlite.org/wal.html` "Concurrency", and the FAQ on
  network filesystems) explicitly warn WAL mode away from filesystems with non-native locking
  semantics, and Docker's own documentation recommends named volumes over bind mounts for
  database workloads on Windows/macOS for the same reason: named volumes on Docker Desktop are
  backed by the WSL2 Linux VM's own ext4-backed disk, with no host-filesystem translation layer in
  the write path at all.
- state-worker is a single async process with an aiosqlite connection pool; it does not fork or run
  multiple OS processes against the file. That rules out the "extra processes" contributor the
  original packet floated, but it does not touch the filesystem-translation-layer risk, which is a
  property of the *mount*, independent of how many processes use it.

**What a named volume closes that the code fix does not:** any tearing caused by the Windows
filesystem-translation layer misrepresenting an `fsync` as complete, or serving a torn read/write
race on `-shm`/`-wal`, when the OS-level page cache and the container's view of the file disagree.
The code fix eliminates the *known* mechanism that produced 500s and pool poisoning; it does nothing
about physical page tearing from the mount layer, because that class of corruption doesn't route
through any of the code the fix touched — it happens beneath SQLite's own I/O layer.

**What it does not close:** anything caused by application logic (the exact bug that was actually
found and fixed), by disk failure, by an operator running two writers, or by a corrupt snapshot being
restored. Those are unaffected by where the volume physically lives.

**Verdict:** worth doing as defense in depth against a failure class that has now bitten this project
twice with two different physical signatures, even though only one of the two incidents was
conclusively root-caused to the mount itself (arguably neither was — June was a host overwrite, not a
mount defect either). The named volume is cheap insurance for a fix that changes only where four
mount lines point.

---

## 2. Chosen snapshot/restore architecture: (a), short-lived helper container

Of the three options posed for host-visibility of a named-volume-resident `bishop.db`:

**(a) chosen — snapshot/restore inside a throwaway `docker run --rm` container.**
The container mounts the named volume, and the *same* `scripts/sqlite_snapshot.py` /
`scripts/sqlite_restore.py` re-invoke themselves inside it against the volume's internal path,
writing the finished snapshot to a still-host-visible bind-mounted directory. Rationale:

- **Zero duplicated logic.** `take_snapshot`, `integrity_ok`, `prune_snapshots`,
  `newest_passing_snapshot`, and the restore install/preserve/verify sequence are unchanged. The
  volume case is purely a `docker run` wrapper that calls the identical script with translated
  paths (`/data/bishop.db`, `/out`, `/snap/<file>`). There is no second implementation to keep in
  sync or drift from the host-path one.
- **No new attack surface on state-worker.** The container never talks to state-worker; it opens
  the file directly from the volume with the same `mode=ro`-URI-gated backup-API approach the host
  script already uses. state-worker's process, pool, and HTTP surface are completely untouched by
  this change.
- **Reuses the existing scheduled task shape.** `BishopSqliteSnapshot` just needs its command line
  changed to add `--volume bishop-sqlite`; the timing, TTL, and prune behavior are identical.
- **Minimal exposure.** The helper container is `python:3.12-slim` (already a cached base layer —
  every Bishop service image is built `FROM python:3.12-slim`, so no extra image pull is typically
  needed) with only `scripts/` and `bishop_shared/` bind-mounted read-only, plus the volume and the
  snapshot directory. It never sees `.env`, never sees the rest of the repo, and both scripts are
  100% stdlib (`sqlite3`, `argparse`, `pathlib`, …) — no `pip install` step, no dependency drift
  between the host's Python and the container's.

**(b) rejected — state-worker exposes an internal snapshot endpoint.**
Explicitly against the standing decision in the incident packet: *"Snapshot never opens a second RW
connection... a read-only connection cannot run `VACUUM INTO`."* Adding a snapshot endpoint to
state-worker means either (i) a second connection into the same pool competing for the single WAL
write lock — reintroducing exactly the contention class `BEGIN IMMEDIATE` + `busy_timeout` were
added to eliminate — or (ii) scheduling logic inside the app process, which the packet also
explicitly did not want ("prefer not making the app itself do scheduling"). It also couples snapshot
cadence to state-worker's deploy lifecycle and makes the snapshot path go through the same process
that a bug in state-worker could poison — the opposite of what an out-of-band backup is for.

**(c) other options considered and rejected:**
- *Mount the volume read-only into a long-lived sidecar container* that does nothing but serve
  snapshots. Rejected: a standing extra service is more moving parts than a `docker run --rm` that
  exists only for the ~1 second the snapshot takes, for no operational benefit — it would need its
  own healthcheck, image, and lifecycle in `docker-compose.yml`, none of which the scheduled-task
  model needs.
- *Copy the whole volume with `docker cp` / `docker run ... tar`* instead of an integrity-gated
  SQLite backup-API copy. Rejected: this is exactly the `shutil.copy`-of-a-live-WAL-database anti-
  pattern the existing snapshot tool was built to avoid — a raw file copy of `bishop.db` without
  its `-wal` in a single atomic operation can capture a torn mid-write state. The backup API
  approach guarantees a transactionally-consistent copy regardless of what's mid-flight in the WAL.
- *`VACUUM INTO` from inside the helper container.* Same reasoning as (b): the existing tooling
  already rejected `VACUUM INTO` because it requires a writable connection; that reasoning holds
  regardless of whether the writable connection is inside state-worker or a helper container. The
  backup API from a `mode=ro` connection remains correct and is what both scripts already do.

### The one gotcha this design surfaces: do NOT mount the volume `:ro` for snapshots

It would be tempting to mount the named volume read-only into the snapshot helper container, since
the snapshot only reads. **Do not.** Per SQLite's own documentation on WAL mode, a reader still needs
write access to the `-shm` wal-index file (to update its own read-mark and, if no `-shm` exists yet,
to create one) even though its *SQL-level* connection is opened `mode=ro`. If the directory containing
`bishop.db` is not writable at the OS level, WAL reads can fail or silently fall back to a stale view.
This mirrors the host setup today: the bind mount itself is not `:ro` at the OS level (only the
`sqlite3` URI parameter enforces logical read-only-ness); `scripts/sqlite_snapshot.py` and the
helper-container wrapper both mount the volume/directory read-write and rely on the SQL-level
`mode=ro` URI, exactly like decision 11 in the incident packet ("Source is `mode=ro`; the copy uses
the SQLite online backup API"). Verified empirically in this session (§5below) against a real WAL
database in a real named volume.

---

## 3. Proposed `docker-compose.yml` diff (NOT applied to the base file)

This repo's base `docker-compose.yml` is unchanged by this work. The diff below is what a human would
apply to it during the cutover in §4, or apply today via the opt-in overlay
`docker-compose.override.named-volume.yml` (see §3.1) without touching the base file at all.

```diff
--- a/docker-compose.yml
+++ b/docker-compose.yml
@@ services.state-worker.volumes
     volumes:
-      - ${BISHOP_DATA_ROOT}/sqlite:/app/data/sqlite
+      - bishop-sqlite:/app/data/sqlite
       - ${BISHOP_DATA_ROOT}/logs:/app/logs
@@ services.query-api.volumes
     volumes:
       - ${BISHOP_DATA_ROOT}/lancedb:/app/data/lancedb
       - ${BISHOP_DATA_ROOT}/duckdb:/app/data/duckdb
       - ${BISHOP_DATA_ROOT}/bm25:/app/data/bm25
-      - ${BISHOP_DATA_ROOT}/sqlite:/app/data/sqlite
+      - bishop-sqlite:/app/data/sqlite
       - ${BISHOP_DATA_ROOT}/logs:/app/logs
@@ top level
 networks:
   bishop-internal:
     name: bishop-internal
+
+volumes:
+  bishop-sqlite: {}
```

`SQLITE_DB_PATH` (`/app/data/sqlite/bishop.db`, `bishop_shared/constants.py`) is untouched — the
container-side path never changes, only what backs it on the host.

### 3.1 — Opt-in overlay file (implemented, does not touch the live stack)

`docker-compose.override.named-volume.yml` (repo root, new file) declares the named volume and
redeclares the full `volumes:` list for `state-worker` and `query-api` with the sqlite line swapped.
It is applied explicitly:

```powershell
docker compose -f docker-compose.yml -f docker-compose.override.named-volume.yml config   # render only
docker compose -f docker-compose.yml -f docker-compose.override.named-volume.yml up -d    # would recreate containers — NOT run in this session
```

**Verified in this session** (render-only, no containers started or touched):

1. `docker compose -f docker-compose.yml -f docker-compose.override.named-volume.yml config`
   diffed against `docker compose -f docker-compose.yml config` (plain base) shows **only**:
   the `state-worker` and `query-api` `/app/data/sqlite` mount flipping from `type: bind` to
   `type: volume, source: bishop-sqlite`, and a new top-level `volumes: {bishop-sqlite: {name:
   bishop-sqlite}}` key. Every other mount, every port, network, environment variable,
   `depends_on`, `healthcheck`, and image for every service is byte-identical. This is asserted by
   `tests/test_sqlite_named_volume.py::test_named_volume_override_scopes_only_sqlite_mounts`.
2. **Compose file precedence claim verified, not assumed.** A plain `docker compose config` (no
   `-f`, i.e. exactly what the live `docker compose up -d` on this host uses) was rendered and
   diffed against `docker compose -f docker-compose.yml config`: **byte-identical**. Compose's
   default file discovery only auto-loads a file literally named `docker-compose.override.yml`
   (or `compose.override.yaml`); a file named `docker-compose.override.named-volume.yml` sitting on
   disk is invisible to a plain `docker compose ...` invocation with no `-f`. Asserted by
   `test_default_compose_discovery_ignores_named_volume_override`. **This means the live `bishop`
   project, which the operator brings up with plain `docker compose up -d`, cannot be affected by
   the mere presence of this file on disk.**
3. **`:ro` named-volume mount for a second service is valid Compose syntax** in the sense that
   nothing about a named volume prevents a second service from mounting it — Compose has no
   volume-level access-control concept; whether a mount is read-only is purely a per-service mount
   flag (long-form `read_only: true` under the volume entry, or `:ro` in short form). This repo's
   *base* `docker-compose.yml` does **not** actually mount sqlite `:ro` for query-api today — the
   existing compose line for query-api is `${BISHOP_DATA_ROOT}/sqlite:/app/data/sqlite` with no
   `:ro`; read-only-ness is enforced only at the application layer via the `file:...?mode=ro` SQLite
   URI in `sqlite_reader.py`, matching decision 11 in the incident packet (only the *source*
   connection for snapshots is read-only by URI; nothing in this repo relies on an OS-level `:ro`
   mount today). The overlay therefore mirrors this exactly and does **not** add `:ro` at the
   compose level, to avoid changing existing behavior as part of this migration. **What I did not
   test:** whether adding a compose-level `:ro` flag on top of the named volume for query-api would
   work cleanly for WAL reads (the `-shm` write-access gotcha in §2 applies here too — a `:ro`
   compose mount would likely break query-api's WAL reads the same way it would break the snapshot
   helper). I recommend the operator **not** add `:ro` at the compose level for this reason, and
   this proposal does not.

### 3.2 — Snapshot directory: stays exactly where it is, decided

`sqlite/snapshots/` **stays a plain host directory under `${BISHOP_DATA_ROOT}/sqlite/`,
unaffected by this migration.** Justification: `scripts/sqlite_snapshot.py` and
`scripts/sqlite_restore.py` are host-side Python processes, not containers — they never relied on
`${BISHOP_DATA_ROOT}/sqlite` being *mounted into a container* to read or write snapshot files, only
on it being a normal path on the Windows filesystem. Moving the *live* `bishop.db` out of that
directory and into a named volume does not change that; `${BISHOP_DATA_ROOT}/sqlite/` continues to
exist on disk, now holding only `snapshots/` (no more live `bishop.db`/`-wal`/`-shm` beside it). The
scheduled task `BishopSqliteSnapshot` needs one command-line change (see §4) and nothing else moves.

---

## 4. Cutover runbook (operator-executed; NOT run in this session)

**Pre-conditions:** stack currently up via `docker compose up -d` (project `bishop`), live data at
`C:/Users/Ale/bishop_data/sqlite/`. Read this whole section before starting; steps are ordered and
some are irreversible without the rollback in §5.

1. **Take a fresh snapshot and confirm it passes integrity**, before touching anything:
   ```powershell
   python scripts/sqlite_snapshot.py
   python scripts/sqlite_restore.py --latest --dry-run   # confirms a passing snapshot exists; changes nothing
   ```

2. **Stop the stack.** (Operator action — not run by this proposal.)
   ```powershell
   docker compose down
   ```

3. **Create the named volume** (idempotent; `docker run` auto-creates it, but explicit is clearer):
   ```powershell
   docker volume create bishop-sqlite
   ```

4. **One-time data copy**, old bind-mount directory → new named volume, via a throwaway container
   that mounts both:
   ```powershell
   docker run --rm `
     -v "C:/Users/Ale/bishop_data/sqlite:/old:ro" `
     -v "bishop-sqlite:/new" `
     python:3.12-slim `
     python -c "import shutil, pathlib; src = pathlib.Path('/old'); dst = pathlib.Path('/new'); [shutil.copy2(p, dst / p.name) for p in src.iterdir() if p.is_file() and not p.name == 'snapshots']"
   ```
   This copies `bishop.db`, `bishop.db-wal`, `bishop.db-shm` (if present) into the volume, and
   explicitly excludes the `snapshots/` subdirectory (it stays a plain host directory per §3.2, not
   copied into the volume). Confirm the copy:
   ```powershell
   docker run --rm -v bishop-sqlite:/new alpine ls -la /new
   ```

5. **Verify integrity inside the volume**, before pointing the stack at it:
   ```powershell
   python scripts/sqlite_snapshot.py --volume bishop-sqlite --snapshot-dir C:/Users/Ale/bishop_data/sqlite/snapshots
   ```
   A successful run here (`event=snapshot_written`) proves `PRAGMA integrity_check` passes against
   the copied file inside the volume — the identical gate the live host copy would have been
   subjected to. If this refuses (`event=snapshot_source_corrupt`), **stop** — do not bring the
   stack up against the volume; go to §5 rollback and re-copy or investigate.

6. **Apply the compose change.** Either:
   - (a) merge the diff in §3 into `docker-compose.yml` directly, and run plain
     `docker compose up -d`; or
   - (b) keep the base file untouched and always launch with the overlay:
     `docker compose -f docker-compose.yml -f docker-compose.override.named-volume.yml up -d`.

   (a) is recommended for the permanent cutover — running two `-f` flags forever is an easy thing to
   forget on some future `docker compose up -d` and would silently revert to the bind mount with an
   **empty** named volume the next time someone starts the stack the plain way. If (b) is kept
   long-term, alias or document the two-file command everywhere `docker compose up -d` appears in
   ops docs.

7. **Bring the stack up and verify `/health/db`:**
   ```powershell
   docker compose up -d
   curl http://localhost:8080/health/db   # via query-api port, or docker compose exec state-worker curl localhost:8000/health/db
   ```
   `/health/db` does real I/O (`SELECT version_num FROM alembic_version`) and returns 503 on any
   integrity/connectivity failure — this is the same gate that already exists, unmodified by this
   work.

8. **Smoke-test both consumers:** confirm state-worker writes advance (`manifest`/`entries` counts
   climb over a few minutes) and query-api reads succeed (`GET /search`, or any read-path route).

9. **Update the scheduled task** to snapshot from the volume instead of the old path:
   ```powershell
   # scripts/register-snapshot-task.ps1 currently runs:
   #   python scripts/sqlite_snapshot.py
   # change the task's action to:
   #   python scripts/sqlite_snapshot.py --volume bishop-sqlite --snapshot-dir C:/Users/Ale/bishop_data/sqlite/snapshots
   ```
   (This proposal does not modify `register-snapshot-task.ps1`'s registered task in Windows Task
   Scheduler — that is a live host-state change the operator should apply by hand, per the
   constraint against silently mutating running host state.)

10. **Decommission the old bind-mount directory — quarantine, do not delete:**
    ```powershell
    Rename-Item "C:/Users/Ale/bishop_data/sqlite" "C:/Users/Ale/bishop_data/_quarantine_2026-09-11_bind-mount-sqlite"
    ```
    Wait — do this only **after** step 9's directory (snapshots) has been relocated or re-pointed;
    since §3.2 keeps `snapshots/` living under `${BISHOP_DATA_ROOT}/sqlite/`, do not rename the
    whole `sqlite/` directory away. Instead, once satisfied the volume is durable (recommend: after
    the first automated 30-minute snapshot cycle completes cleanly from the volume), delete only the
    old bind-mounted `bishop.db`, `bishop.db-wal`, `bishop.db-shm` from that directory, or move them
    into a `_quarantine_<date>/` subfolder beside `snapshots/` — keep the `snapshots/` subdirectory
    exactly where it is, since it is still live and unrelated to this rename.

---

## 5. Rollback plan

At any point before decommissioning the old directory (§4 step 10), rollback is a straight reversal:

1. `docker compose down`
2. Revert the compose change (drop the diff in §3, or simply stop passing the overlay `-f` if using
   the two-file form).
3. `docker compose up -d` — this brings the stack back up pointed at the original bind mount, which
   was never modified or deleted (only copied *from*, read-only, in step 4).
4. If the named volume had already accumulated new writes before rollback was decided (i.e. the
   volume was live for a while), those writes are **not** in the bind-mount copy. Decide before
   rolling back whether to also restore the volume's latest snapshot back onto the bind-mount path:
   ```powershell
   python scripts/sqlite_snapshot.py --volume bishop-sqlite --snapshot-dir C:/Users/Ale/bishop_data/sqlite/snapshots
   python scripts/sqlite_restore.py --latest   # installs onto the bind-mount path; refuses if compose is up
   ```
5. The named volume itself can be left in place (harmless, not referenced once the compose change is
   reverted) or removed with `docker volume rm bishop-sqlite` once its contents are confirmed no
   longer needed.

---

## 6. What was and was not done in this session

**Done (this session):**
- This proposal document.
- `scripts/sqlite_snapshot.py` — added `--volume NAME` mode (`run_in_volume_container`,
  `default_snapshot_dir`, `default_data_root`), reusing all existing snapshot logic unchanged.
- `scripts/sqlite_restore.py` — added `--volume NAME` mode (`run_restore_volume`,
  `run_restore_in_volume_container`), same host-side compose-up + integrity gates as bind-mount mode.
- `docker-compose.override.named-volume.yml` — new, opt-in, not referenced by any plain
  `docker compose` invocation.
- `tests/test_sqlite_named_volume.py` — 10 tests against **real** throwaway Docker volumes
  (`bishop-test-namedvol-<random>`, never `bishop-sqlite`), each removed in a fixture `finally`, plus
  compose-scope and precedence tests. All 10 passed in this session (§7).
- Manually verified, then encoded into tests: WAL-resident (uncheckpointed) rows survive a
  volume-mode snapshot; a corrupt snapshot is refused (exit 3) in volume mode; a compose-up host is
  refused (exit 2) in volume mode *before* any container touches the target volume; a
  `docker compose config` render diff proves the overlay only touches sqlite mounts for
  state-worker/query-api; default `docker compose config` (no `-f`) ignores the overlay file.
- `.dev/sqlite.md` and `.dev/still_open.md` OPEN-007 updated to reflect: proposal + tooling exist,
  cutover is a pending operator action.

**Explicitly NOT done (operator action required, per §4):**
- `docker-compose.yml` was **not** modified.
- The named volume `bishop-sqlite` was **not** created against the live data (only disposable
  `bishop-test-namedvol-*` volumes were created and destroyed during testing).
- No data was copied out of `C:/Users/Ale/bishop_data/**`; that directory was not opened, read, or
  written by any command in this session.
- `docker compose down` / `docker compose up` were never run against the live `bishop` project.
  Only `docker compose ... config` (render-only) was run against it, twice, to verify the overlay's
  scope and default-discovery behavior — this does not start, stop, or recreate any container.
- The Windows Scheduled Task `BishopSqliteSnapshot` was not modified.

---

## 7. What was tested, and what remains for the operator to verify

**Tested in this session (real Docker, throwaway resources, all torn down):**
- Volume-mode snapshot of a live WAL-mode database (uncheckpointed rows) inside a real named volume,
  via both the direct function call and the CLI end-to-end (`tests/test_sqlite_named_volume.py`).
- Volume-mode restore into a fresh named volume, both via direct call and CLI `--latest`.
- Volume-mode restore's compose-up refusal, confirmed the target volume is untouched (no
  `bishop.db` created at all) when refused.
- Volume-mode restore's corrupt-snapshot refusal (exit 3).
- The compose overlay's config-render scope (only sqlite mounts change) and its invisibility to
  default `docker compose` discovery.
- `pytest tests/test_sqlite_named_volume.py` (10/10 pass), plus a regression pass of
  `tests/test_sqlite_snapshot.py` + `tests/test_sqlite_restore.py` + `tests/test_compose.py`
  (43/43 pass, unchanged from before this work).

**Not tested — recommend the operator verify during the runbook, not assume:**
- Whether `state-worker`'s aiosqlite pool behaves identically against a named-volume-backed file
  under sustained concurrent load, the way the incident packet's 4-minute live-load run validated
  the bind-mount + code-fix combination. This proposal's tests exercise the snapshot/restore
  *tooling*, not the write-heavy pooled-connection path under load against a volume.
  Recommend repeating the incident packet's §8 live-verification loop after cutover.
  This is also OPEN-018's still-missing "genuinely concurrent adversarial test... against a Windows
  bind mount" — worth re-running against the named volume too once cut over, for comparison.
- Whether a compose-level `:ro` mount flag on query-api's named-volume entry works for WAL reads
  (§3.1 point 3) — not attempted; this proposal deliberately does not add `:ro` at the compose level
  to avoid the untested risk.
- Actual performance/latency difference between the Windows bind mount and the named volume under
  this workload — not measured; the case for this migration is corruption-avoidance, not speed,
  though the named volume is expected to be at least as fast since it avoids the translation layer.
- Whatever cross-platform / Docker-Desktop-version quirks might exist in named-volume backing store
  location — irrelevant to this design specifically because scripts never assume a host path for the
  volume; they only ever go through `docker run -v <name>:/data`, which is stable across Docker
  Desktop versions by contract (unlike the internal WSL2 disk path, which is not).
