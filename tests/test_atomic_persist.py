"""Unit tests for bishop_shared.atomic_persist (M6 T1 contract surface)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from bishop_shared.atomic_persist import atomic_persist


def test_atomic_persist_writes_and_replaces(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "index.pkl"
    payload = b"serialized-index-bytes"

    def serialize(out: object) -> None:
        out.write(payload)  # type: ignore[union-attr]

    atomic_persist(target, serialize)

    assert target.read_bytes() == payload
    assert not any(tmp_path.rglob("*.tmp"))


def test_atomic_persist_preserves_prior_on_serialize_failure(tmp_path: Path) -> None:
    """Falsifier: failed serialize must not corrupt an existing target file."""
    target = tmp_path / "index.pkl"
    original = b"valid-prior-state"
    target.write_bytes(original)

    def failing_serialize(_out: object) -> None:
        raise RuntimeError("serialize failed")

    with pytest.raises(RuntimeError, match="serialize failed"):
        atomic_persist(target, failing_serialize)

    assert target.read_bytes() == original


def test_atomic_persist_uses_fsync_and_replace(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Falsifier: implementation must fsync temp file and os.replace, not in-place overwrite."""
    target = tmp_path / "index.pkl"
    fsync_calls: list[int] = []
    replace_calls: list[tuple[Path, Path]] = []

    real_fsync = os.fsync
    real_replace = os.replace

    def track_fsync(fd: int) -> None:
        fsync_calls.append(fd)
        real_fsync(fd)

    def track_replace(src: os.PathLike[str] | str, dst: os.PathLike[str] | str) -> None:
        replace_calls.append((Path(src), Path(dst)))
        real_replace(src, dst)

    monkeypatch.setattr(os, "fsync", track_fsync)
    monkeypatch.setattr(os, "replace", track_replace)

    atomic_persist(target, lambda out: out.write(b"x"))  # type: ignore[union-attr]

    assert fsync_calls
    assert replace_calls == [(replace_calls[0][0], target)]
