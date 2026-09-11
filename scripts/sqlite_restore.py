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
    SQLITE_SNAPSHOT_TIMESTAMP_FORMAT,
)
from sqlite_snapshot import (  # noqa: E402
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


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", help="Host path to bishop.db (otherwise BISHOP_DATA_ROOT)")
    parser.add_argument(
        "--snapshot-dir",
        help="Snapshot directory for --latest (default: <db-dir>/snapshots)",
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
