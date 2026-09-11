"""Explicit operator restore of bishop.db from an integrity-checked snapshot.

Refuses to run while docker compose is up (exit 2) unless --force. If compose
state is UNKNOWN (CLI missing, error, or timeout), logs a warning naming that
uncertainty and proceeds — the operator asked for a restore. Never auto-restores
on startup and never swaps the live file while the stack is known to be up.
A snapshot that fails PRAGMA integrity_check is refused (exit 3). After install,
the new live file is re-checked and a failure exits 4.

Usage:
  python scripts/sqlite_restore.py [--db PATH] --file SNAPSHOT.db
  python scripts/sqlite_restore.py [--db PATH] --latest [--snapshot-dir DIR]
  python scripts/sqlite_restore.py --file SNAPSHOT.db --dry-run

Named-volume mode (see .dev/decision-logs/ops/sqlite-named-volume-migration.md):
  python scripts/sqlite_restore.py --volume bishop-sqlite --latest
  python scripts/sqlite_restore.py --volume bishop-sqlite --file SNAPSHOT.db

The docker-compose-is-up guard and snapshot selection (--file/--latest) still
run on the host exactly as in bind-mount mode, against the host-visible
snapshot directory. Only the install step (preserve + atomic copy + stale
-wal/-shm cleanup + re-verify) runs inside a throwaway container that mounts
the named volume read-write and the chosen snapshot file read-only.
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from bishop_shared.constants import (  # noqa: E402
    SQLITE_DB_FILENAME,
    SQLITE_SNAPSHOT_TIMESTAMP_FORMAT,
)
from sqlite_snapshot import (  # noqa: E402
    DEFAULT_VOLUME_HELPER_IMAGE,
    default_snapshot_dir,
    integrity_ok,
    newest_passing_snapshot,
    resolve_db_path,
    snapshot_dir_for,
)

logger = logging.getLogger(__name__)

_COMPOSE_TIMEOUT_SEC = 10


def compose_is_up() -> bool | None:
    """True if `docker compose ps -q` prints containers; False if empty; None if unknown."""
    try:
        completed = subprocess.run(
            ["docker", "compose", "ps", "-q"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=_COMPOSE_TIMEOUT_SEC,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    if completed.returncode != 0:
        return None
    return bool(completed.stdout.strip())


def run_restore_in_volume_container(
    *,
    volume: str,
    snapshot_path: Path,
    force: bool,
    dry_run: bool,
    docker_image: str = DEFAULT_VOLUME_HELPER_IMAGE,
) -> int:
    """Re-invoke this script's install step inside a throwaway container.

    Mounts (nothing else from the repo/host is exposed):
      - the named volume at /data, read-write (the install itself is a write;
        also a WAL reader inside the same container needs -shm write access)
      - snapshot_path's parent directory at /snap, read-only
      - repo scripts/ and bishop_shared/ at /repo/scripts and
        /repo/bishop_shared, read-only

    The outer process has already done the compose-is-up gate against the
    real host, using --force is only to skip re-doing that (unreliable)
    check inside a container that has no docker CLI of its own.
    """
    scripts_dir = ROOT / "scripts"
    shared_dir = ROOT / "bishop_shared"
    inner_args = [
        "--db",
        f"/data/{SQLITE_DB_FILENAME}",
        "--file",
        f"/snap/{snapshot_path.name}",
        "--force",
    ]
    if dry_run:
        inner_args.append("--dry-run")
    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{volume}:/data",
        "-v",
        f"{snapshot_path.resolve().parent.as_posix()}:/snap:ro",
        "-v",
        f"{scripts_dir.as_posix()}:/repo/scripts:ro",
        "-v",
        f"{shared_dir.as_posix()}:/repo/bishop_shared:ro",
        "-w",
        "/repo",
        docker_image,
        "python",
        "scripts/sqlite_restore.py",
        *inner_args,
    ]
    logger.info(
        "event=volume_restore_container_start volume=%s snapshot=%s",
        volume,
        snapshot_path.name,
    )
    completed = subprocess.run(cmd)
    return completed.returncode


def _wal_path(db_path: Path) -> Path:
    return Path(str(db_path) + "-wal")


def _shm_path(db_path: Path) -> Path:
    return Path(str(db_path) + "-shm")


def _preserve_name(db_path: Path, now: datetime) -> Path:
    stamp = now.strftime(SQLITE_SNAPSHOT_TIMESTAMP_FORMAT)
    return db_path.with_name(f"{db_path.name}.pre-restore-{stamp}")


def preserve_live(db_path: Path, *, now: datetime | None = None) -> Path | None:
    """Copy the live db (and -wal/-shm) beside it as bishop.db.pre-restore-<ts>."""
    if not db_path.is_file():
        return None
    stamp_now = now if now is not None else datetime.now()
    preserved = _preserve_name(db_path, stamp_now)
    shutil.copy2(db_path, preserved)
    for sidecar in (_wal_path(db_path), _shm_path(db_path)):
        if sidecar.exists():
            shutil.copy2(sidecar, Path(str(preserved) + sidecar.name[len(db_path.name) :]))
    logger.info("event=restore_preserved path=%s", preserved)
    return preserved


def _atomic_copy_file(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=dest.parent,
        prefix=f".{dest.name}.",
        suffix=".tmp",
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as out:
            with src.open("rb") as inp:
                shutil.copyfileobj(inp, out)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp_path, dest)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def _delete_stale_wal(db_path: Path) -> None:
    # Mixing a stale WAL onto a different main file is corruption: the restored
    # snapshot is a complete main database; leftover -wal/-shm belong to the
    # previous live file and must not be replayed onto it.
    for sidecar in (_wal_path(db_path), _shm_path(db_path)):
        if sidecar.exists():
            sidecar.unlink()
            logger.info("event=restore_sidecar_removed path=%s", sidecar)


def run_restore(
    db_path: Path,
    snapshot_path: Path,
    *,
    force: bool = False,
    dry_run: bool = False,
    now: datetime | None = None,
) -> None:
    """Install snapshot_path over db_path, or raise SystemExit with a documented code."""
    stamp_now = now if now is not None else datetime.now()
    compose = compose_is_up()
    if compose is True and not force:
        print(
            "REFUSE: docker compose appears to be up. Bring the stack down first, "
            "or pass --force if you are certain no writer is open."
        )
        raise SystemExit(2)
    if compose is None:
        logger.warning(
            "event=restore_compose_unknown "
            "docker compose ps did not yield a definitive answer "
            "(CLI missing, error, or timeout). Proceeding because the operator "
            "requested a restore; the stack may still be up."
        )

    if not snapshot_path.is_file():
        print(f"REFUSE: snapshot file does not exist: {snapshot_path}")
        raise SystemExit(1)

    ok, lines = integrity_ok(snapshot_path)
    if not ok:
        print(
            "REFUSE: snapshot failed PRAGMA integrity_check; "
            "will not replace the live file."
        )
        for line in lines:
            print(line)
        raise SystemExit(3)

    preserved = _preserve_name(db_path, stamp_now)
    wal = _wal_path(db_path)
    shm = _shm_path(db_path)

    if dry_run:
        if db_path.is_file():
            print(f"DRY-RUN: would preserve {db_path} as {preserved}")
            if wal.exists():
                print(f"DRY-RUN: would preserve {wal} as {Path(str(preserved) + '-wal')}")
            if shm.exists():
                print(f"DRY-RUN: would preserve {shm} as {Path(str(preserved) + '-shm')}")
        print(f"DRY-RUN: would install {snapshot_path} -> {db_path}")
        print(f"DRY-RUN: would delete {wal} and {shm} if present")
        print("DRY-RUN: would re-run PRAGMA integrity_check on the installed file")
        return

    preserve_live(db_path, now=stamp_now)
    _atomic_copy_file(snapshot_path, db_path)
    _delete_stale_wal(db_path)

    installed_ok, installed_lines = integrity_ok(db_path)
    if not installed_ok:
        print("FAIL: restored bishop.db failed PRAGMA integrity_check.")
        for line in installed_lines:
            print(line)
        raise SystemExit(4)

    logger.info(
        "event=restore_installed path=%s bytes=%s source=%s",
        db_path,
        db_path.stat().st_size,
        snapshot_path,
    )
    print("Next step: docker compose up --build  (or: docker compose up -d)")
    print(
        "Reminder: in-flight Anthropic batches in the restored batches table "
        "will be re-fetched (not re-submitted) by batch-poller's startup scan."
    )


def run_restore_volume(
    volume: str,
    snapshot_path: Path,
    *,
    force: bool = False,
    dry_run: bool = False,
    docker_image: str = DEFAULT_VOLUME_HELPER_IMAGE,
) -> None:
    """Same gate + snapshot-integrity checks as run_restore, host-side, then
    delegate the actual install to a container mounting the named volume.
    Raises SystemExit with the same documented exit codes as run_restore.
    """
    compose = compose_is_up()
    if compose is True and not force:
        print(
            "REFUSE: docker compose appears to be up. Bring the stack down first, "
            "or pass --force if you are certain no writer is open."
        )
        raise SystemExit(2)
    if compose is None:
        logger.warning(
            "event=restore_compose_unknown "
            "docker compose ps did not yield a definitive answer "
            "(CLI missing, error, or timeout). Proceeding because the operator "
            "requested a restore; the stack may still be up."
        )

    if not snapshot_path.is_file():
        print(f"REFUSE: snapshot file does not exist: {snapshot_path}")
        raise SystemExit(1)

    ok, lines = integrity_ok(snapshot_path)
    if not ok:
        print(
            "REFUSE: snapshot failed PRAGMA integrity_check; "
            "will not replace the live file."
        )
        for line in lines:
            print(line)
        raise SystemExit(3)

    # The container has no docker CLI of its own, so its internal
    # compose_is_up() check would always be "unknown" anyway; force=True
    # here documents that the real gate already happened, above, on the host.
    code = run_restore_in_volume_container(
        volume=volume,
        snapshot_path=snapshot_path,
        force=True,
        dry_run=dry_run,
        docker_image=docker_image,
    )
    raise SystemExit(code)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", help="Host path to bishop.db (otherwise BISHOP_DATA_ROOT)")
    parser.add_argument(
        "--snapshot-dir",
        help="Snapshot directory for --latest (default: <db-dir>/snapshots)",
    )
    parser.add_argument(
        "--volume",
        help=(
            "Named Docker volume holding bishop.db instead of a host bind "
            "mount. The compose-is-up gate and snapshot selection still run "
            "on the host; only the install step runs inside a container "
            "against the volume. --db is ignored in this mode."
        ),
    )
    parser.add_argument(
        "--docker-image",
        default=DEFAULT_VOLUME_HELPER_IMAGE,
        help=f"Helper image for --volume mode (default {DEFAULT_VOLUME_HELPER_IMAGE})",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--file", type=Path, help="Explicit snapshot file to restore")
    source.add_argument(
        "--latest",
        action="store_true",
        help="Use newest_passing_snapshot in the snapshot directory",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Restore even if docker compose appears to be up",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would happen; change nothing on disk",
    )
    args = parser.parse_args()

    if args.volume:
        snapshot_dir = Path(args.snapshot_dir) if args.snapshot_dir else default_snapshot_dir()
        if args.latest:
            chosen = newest_passing_snapshot(snapshot_dir)
            if chosen is None:
                print(f"REFUSE: no passing snapshot in {snapshot_dir}")
                raise SystemExit(1)
            snapshot_path = chosen
        else:
            snapshot_path = Path(args.file)
        run_restore_volume(
            args.volume,
            snapshot_path,
            force=args.force,
            dry_run=args.dry_run,
            docker_image=args.docker_image,
        )
        return

    db_path = resolve_db_path(args.db)
    snapshot_dir = Path(args.snapshot_dir) if args.snapshot_dir else snapshot_dir_for(db_path)

    if args.latest:
        chosen = newest_passing_snapshot(snapshot_dir)
        if chosen is None:
            print(f"REFUSE: no passing snapshot in {snapshot_dir}")
            raise SystemExit(1)
        snapshot_path = chosen
    else:
        snapshot_path = Path(args.file)

    run_restore(
        db_path,
        snapshot_path,
        force=args.force,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
