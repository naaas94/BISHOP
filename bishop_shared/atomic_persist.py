"""Atomic file persistence (spec §8.4 S4): temp write → fsync → os.replace."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable
from pathlib import Path


def atomic_persist(path: Path | str, serialize_fn: Callable[[object], None]) -> None:
    """Serialize to a temp file in the target directory, fsync, then atomically replace."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as tmp_file:
            serialize_fn(tmp_file)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
        os.replace(tmp_path, target)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
