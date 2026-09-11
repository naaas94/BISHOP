"""Integrity-gated host-side snapshot of bishop.db, then TTL prune.

Takes one snapshot of a live SQLite file using the online backup API from a
read-only source connection (never a second writer, never shutil.copy of a WAL
database). The live file is snapshotted only when PRAGMA integrity_check passes
at snapshot time; a failing attempt is deleted, not kept. Timestamps in
snapshot filenames are naive local time from datetime.now(), and prune uses
the same clock (filename parse, with mtime fallback).

Usage:
  python scripts/sqlite_snapshot.py [--db PATH] [--snapshot-dir DIR]
      [--ttl-hours 24] [--interval-minutes 30] [--loop] [--prune-only]

Named-volume mode (see .dev/decision-logs/ops/sqlite-named-volume-migration.md):
  python scripts/sqlite_snapshot.py --volume bishop-sqlite [--snapshot-dir DIR]

When bishop.db lives in a Docker named volume instead of a host bind mount,
the host process cannot open it directly. --volume shells out to a short-lived
`docker run --rm` container that bind-mounts this repo's scripts/ and
bishop_shared/ (read-only, never the whole repo or .env) plus the named
volume, and re-invokes this SAME script inside that container in ordinary
--db mode against the volume's internal path. The snapshot is written
straight to --snapshot-dir, which stays a host bind-mounted/plain directory
on the outside — the container never sees anything else. This reuses
take_snapshot / integrity_ok / prune_snapshots unchanged; there is no forked
duplicate of the snapshot logic for the volume case.
"""

from __future__ import annotations

import argparse
import logging
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bishop_shared.constants import (  # noqa: E402
    SQLITE_DB_FILENAME,
    SQLITE_SNAPSHOT_DIRNAME,
    SQLITE_SNAPSHOT_GLOB,
    SQLITE_SNAPSHOT_INTERVAL_MINUTES,
    SQLITE_SNAPSHOT_PREFIX,
    SQLITE_SNAPSHOT_SUFFIX,
    SQLITE_SNAPSHOT_TIMESTAMP_FORMAT,
    SQLITE_SNAPSHOT_TTL_HOURS,
)

logger = logging.getLogger(__name__)

_ENV_KEY = "BISHOP_DATA_ROOT"


def _parse_bishop_data_root_from_env_file(env_path: Path) -> str | None:
    """Return only BISHOP_DATA_ROOT from a .env file. Never log other keys."""
    if not env_path.is_file():
        return None
    try:
        text = env_path.read_text(encoding="utf-8")
    except OSError:
        return None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if not line.startswith(f"{_ENV_KEY}="):
            continue
        value = line.split("=", 1)[1].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        return value or None
    return None


def resolve_db_path(arg: str | Path | None) -> Path:
    """Host path to bishop.db: --db, else BISHOP_DATA_ROOT/sqlite/<filename>."""
    if arg is not None and str(arg).strip():
        return Path(arg).expanduser()
    root = os.environ.get(_ENV_KEY)
    if not root:
        root = _parse_bishop_data_root_from_env_file(ROOT / ".env")
    if not root:
        raise SystemExit(
            "cannot resolve host SQLite path: pass --db or set "
            "BISHOP_DATA_ROOT (environment or repo-root .env)"
        )
    return Path(root).expanduser() / "sqlite" / SQLITE_DB_FILENAME


def default_data_root() -> Path | None:
    """BISHOP_DATA_ROOT from env or repo-root .env, or None if unset."""
    root = os.environ.get(_ENV_KEY)
    if not root:
        root = _parse_bishop_data_root_from_env_file(ROOT / ".env")
    return Path(root).expanduser() if root else None


def default_snapshot_dir() -> Path:
    """Snapshot directory when there is no host bishop.db path to derive it
    from (named-volume mode). Snapshots stay under BISHOP_DATA_ROOT/sqlite/
    even after the live file moves to a named volume: this directory is
    written by host-side Python, never mounted into a container, so moving
    the live db out of a bind mount does not affect it. See
    .dev/decision-logs/ops/sqlite-named-volume-migration.md.
    """
    root = default_data_root()
    if root is None:
        raise SystemExit(
            "cannot resolve snapshot dir: pass --snapshot-dir or set "
            "BISHOP_DATA_ROOT (environment or repo-root .env)"
        )
    return root / "sqlite" / SQLITE_SNAPSHOT_DIRNAME


DEFAULT_VOLUME_HELPER_IMAGE = "python:3.12-slim"


def run_in_volume_container(
    *,
    volume: str,
    snapshot_dir: Path,
    inner_args: list[str],
    docker_image: str = DEFAULT_VOLUME_HELPER_IMAGE,
) -> int:
    """Re-invoke this script inside a throwaway container against a named
    volume, and return its exit code.

    Mounts (all explicit, nothing else from the repo or host is exposed):
      - the named volume at /data (read-write: SQLite WAL readers need
        write access to the -shm wal-index even when the SQL-level
        connection uses mode=ro; see the proposal doc's "why not :ro" note)
      - snapshot_dir at /out (this is where the snapshot is actually written)
      - repo scripts/ and bishop_shared/ at /repo/scripts and
        /repo/bishop_shared, read-only (never the whole repo, never .env)

    inner_args are passed to the containerized `python scripts/sqlite_snapshot.py`
    verbatim except --db/--snapshot-dir, which the caller must already have
    translated to the container-internal paths /data/<file> and /out.
    """
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    scripts_dir = ROOT / "scripts"
    shared_dir = ROOT / "bishop_shared"
    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{volume}:/data",
        "-v",
        f"{snapshot_dir.as_posix()}:/out",
        "-v",
        f"{scripts_dir.as_posix()}:/repo/scripts:ro",
        "-v",
        f"{shared_dir.as_posix()}:/repo/bishop_shared:ro",
        "-w",
        "/repo",
        docker_image,
        "python",
        "scripts/sqlite_snapshot.py",
        *inner_args,
    ]
    logger.info("event=volume_snapshot_container_start volume=%s", volume)
    completed = subprocess.run(cmd)
    return completed.returncode


def snapshot_dir_for(db_path: Path) -> Path:
    return db_path.parent / SQLITE_SNAPSHOT_DIRNAME


def snapshot_name(now: datetime) -> str:
    return f"{SQLITE_SNAPSHOT_PREFIX}{now.strftime(SQLITE_SNAPSHOT_TIMESTAMP_FORMAT)}{SQLITE_SNAPSHOT_SUFFIX}"


def integrity_ok(path: Path) -> tuple[bool, list[str]]:
    """Run PRAGMA integrity_check on path via a read-only connection."""
    try:
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        try:
            rows = conn.execute("PRAGMA integrity_check").fetchall()
        finally:
            conn.close()
    except sqlite3.DatabaseError as exc:
        return False, [str(exc)]
    lines = [str(row[0]) if row else "" for row in rows][:20]
    return lines == ["ok"], lines


def _fsync_file(path: Path) -> None:
    # Windows FlushFileBuffers rejects a read-only fd (Errno 9); open r+b.
    with path.open("r+b") as fh:
        fh.flush()
        os.fsync(fh.fileno())


def _remove_temp_snapshot(tmp_path: Path) -> None:
    tmp_path.unlink(missing_ok=True)
    Path(str(tmp_path) + "-wal").unlink(missing_ok=True)
    Path(str(tmp_path) + "-shm").unlink(missing_ok=True)


def take_snapshot(
    db_path: Path,
    snapshot_dir: Path,
    *,
    now: datetime | None = None,
) -> Path | None:
    """Copy db_path into snapshot_dir via sqlite backup; None if skipped or failed."""
    if not db_path.is_file() or db_path.stat().st_size == 0:
        logger.warning("event=snapshot_skipped reason=missing_or_empty path=%s", db_path)
        return None

    source_ok, source_lines = integrity_ok(db_path)
    if not source_ok:
        logger.error(
            "event=snapshot_source_corrupt path=%s detail=%s",
            db_path,
            source_lines,
        )
        return None

    snapshot_dir.mkdir(parents=True, exist_ok=True)
    stamp = now if now is not None else datetime.now()
    final_path = snapshot_dir / snapshot_name(stamp)

    fd, tmp_name = tempfile.mkstemp(
        dir=snapshot_dir,
        prefix=".bishop-snapshot.",
        suffix=".tmp",
    )
    tmp_path = Path(tmp_name)
    src_conn: sqlite3.Connection | None = None
    dst_conn: sqlite3.Connection | None = None
    try:
        os.close(fd)
        fd = -1
        src_conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
        dst_conn = sqlite3.connect(str(tmp_path))
        src_conn.backup(dst_conn)
        # Backup of a WAL source can leave dest in WAL mode. Collapse into a
        # single standalone file so publish does not orphan .tmp-wal/.tmp-shm.
        dst_conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        dst_conn.execute("PRAGMA journal_mode=DELETE")
        dst_conn.close()
        dst_conn = None
        src_conn.close()
        src_conn = None
        _fsync_file(tmp_path)
        dest_ok, dest_lines = integrity_ok(tmp_path)
        if not dest_ok:
            _remove_temp_snapshot(tmp_path)
            logger.error(
                "event=snapshot_integrity_failed path=%s detail=%s",
                tmp_path,
                dest_lines,
            )
            return None
        # Directory fsync is not portable on Windows (os.open on a directory
        # then fsync fails or is a no-op), so we skip it and rely on file
        # fsync + os.replace for the publish.
        os.replace(tmp_path, final_path)
        Path(str(tmp_path) + "-wal").unlink(missing_ok=True)
        Path(str(tmp_path) + "-shm").unlink(missing_ok=True)
        size = final_path.stat().st_size
        logger.info("event=snapshot_written path=%s bytes=%s", final_path, size)
        return final_path
    except Exception:
        _remove_temp_snapshot(tmp_path)
        raise
    finally:
        if dst_conn is not None:
            dst_conn.close()
        if src_conn is not None:
            src_conn.close()
        if fd >= 0:
            os.close(fd)


def _timestamp_from_snapshot_name(path: Path) -> datetime | None:
    name = path.name
    if not (
        name.startswith(SQLITE_SNAPSHOT_PREFIX)
        and name.endswith(SQLITE_SNAPSHOT_SUFFIX)
    ):
        return None
    stamp = name[len(SQLITE_SNAPSHOT_PREFIX) : -len(SQLITE_SNAPSHOT_SUFFIX)]
    try:
        return datetime.strptime(stamp, SQLITE_SNAPSHOT_TIMESTAMP_FORMAT)
    except ValueError:
        return None


def _snapshot_age_timestamp(path: Path) -> datetime:
    """Naive local time: filename stamp if parseable, else file mtime.

    Snapshot names are written with datetime.now() (naive local). Prune
    compares against the same clock. Unparseable names fall back to
    datetime.fromtimestamp(mtime), also naive local.
    """
    parsed = _timestamp_from_snapshot_name(path)
    if parsed is not None:
        return parsed
    return datetime.fromtimestamp(path.stat().st_mtime)


def prune_snapshots(
    snapshot_dir: Path,
    ttl_hours: float,
    *,
    now: datetime | None = None,
) -> list[Path]:
    """Delete glob-matching snapshots older than ttl_hours. Returns deleted paths."""
    if not snapshot_dir.is_dir():
        return []
    clock = now if now is not None else datetime.now()
    cutoff = timedelta(hours=ttl_hours)
    snapshot_root = snapshot_dir.resolve()
    deleted: list[Path] = []
    for path in snapshot_dir.glob(SQLITE_SNAPSHOT_GLOB):
        if not path.is_file():
            continue
        try:
            if path.resolve().parent != snapshot_root:
                continue
        except OSError:
            continue
        if clock - _snapshot_age_timestamp(path) > cutoff:
            path.unlink()
            deleted.append(path)
            logger.info("event=snapshot_pruned path=%s", path)
    return deleted


def newest_passing_snapshot(snapshot_dir: Path) -> Path | None:
    """Newest snapshot by filename whose integrity_check passes, or None."""
    if not snapshot_dir.is_dir():
        return None
    candidates = sorted(
        snapshot_dir.glob(SQLITE_SNAPSHOT_GLOB),
        key=lambda p: p.name,
        reverse=True,
    )
    for path in candidates:
        if not path.is_file():
            continue
        ok, _lines = integrity_ok(path)
        if ok:
            return path
    return None


def _run_cycle(
    db_path: Path,
    snapshot_dir: Path,
    ttl_hours: float,
    *,
    prune_only: bool,
) -> bool:
    wrote_ok = True
    if not prune_only:
        wrote_ok = take_snapshot(db_path, snapshot_dir) is not None
    prune_snapshots(snapshot_dir, ttl_hours)
    return wrote_ok


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", help="Host path to bishop.db (otherwise BISHOP_DATA_ROOT)")
    parser.add_argument("--snapshot-dir", help="Directory for snapshots (default: <db-dir>/snapshots)")
    parser.add_argument(
        "--volume",
        help=(
            "Named Docker volume holding bishop.db instead of a host bind "
            "mount. Runs this script inside a throwaway container against "
            "the volume; --db is ignored in this mode."
        ),
    )
    parser.add_argument(
        "--docker-image",
        default=DEFAULT_VOLUME_HELPER_IMAGE,
        help=f"Helper image for --volume mode (default {DEFAULT_VOLUME_HELPER_IMAGE})",
    )
    parser.add_argument(
        "--ttl-hours",
        type=float,
        default=SQLITE_SNAPSHOT_TTL_HOURS,
        help=f"Prune snapshots older than this (default {SQLITE_SNAPSHOT_TTL_HOURS})",
    )
    parser.add_argument(
        "--interval-minutes",
        type=float,
        default=SQLITE_SNAPSHOT_INTERVAL_MINUTES,
        help=f"Sleep between --loop cycles (default {SQLITE_SNAPSHOT_INTERVAL_MINUTES})",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Repeat forever (a failed cycle logs and continues)",
    )
    parser.add_argument(
        "--prune-only",
        action="store_true",
        help="Only prune expired snapshots; do not take a new one",
    )
    args = parser.parse_args()

    if args.volume:
        snapshot_dir = Path(args.snapshot_dir) if args.snapshot_dir else default_snapshot_dir()
        inner_args = [
            "--db",
            f"/data/{SQLITE_DB_FILENAME}",
            "--snapshot-dir",
            "/out",
            "--ttl-hours",
            str(args.ttl_hours),
        ]
        if args.prune_only:
            inner_args.append("--prune-only")
        if args.loop:
            inner_args += ["--loop", "--interval-minutes", str(args.interval_minutes)]
        code = run_in_volume_container(
            volume=args.volume,
            snapshot_dir=snapshot_dir,
            inner_args=inner_args,
            docker_image=args.docker_image,
        )
        raise SystemExit(code)

    db_path = resolve_db_path(args.db)
    snapshot_dir = Path(args.snapshot_dir) if args.snapshot_dir else snapshot_dir_for(db_path)

    if args.loop:
        while True:
            try:
                if not _run_cycle(
                    db_path,
                    snapshot_dir,
                    args.ttl_hours,
                    prune_only=args.prune_only,
                ):
                    logger.error("event=snapshot_cycle_failed")
            except Exception:
                logger.exception("event=snapshot_cycle_failed")
            time.sleep(args.interval_minutes * 60)
    try:
        ok = _run_cycle(
            db_path,
            snapshot_dir,
            args.ttl_hours,
            prune_only=args.prune_only,
        )
    except Exception:
        logger.exception("event=snapshot_failed")
        raise SystemExit(1) from None
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
