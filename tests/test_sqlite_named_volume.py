"""Tests for the --volume mode added to scripts/sqlite_snapshot.py and
scripts/sqlite_restore.py (see .dev/decision-logs/ops/sqlite-named-volume-migration.md).

These exercise REAL, throwaway Docker named volumes and short-lived
containers — never the real `bishop-sqlite` volume name, never the live
`bishop.db`. Every volume created here is prefixed `bishop-test-namedvol-`
plus a random suffix and is removed in a fixture teardown (try/finally),
even on failure. If Docker is unavailable in the sandbox, the whole module
is skipped rather than failing.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SNAPSHOT_SCRIPT = _REPO_ROOT / "scripts" / "sqlite_snapshot.py"
_RESTORE_SCRIPT = _REPO_ROOT / "scripts" / "sqlite_restore.py"
_OVERRIDE_COMPOSE = _REPO_ROOT / "docker-compose.override.named-volume.yml"
_BASE_COMPOSE = _REPO_ROOT / "docker-compose.yml"

_DOCKER_TIMEOUT_SEC = 30


def _load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


snap = _load_script("sqlite_snapshot", _SNAPSHOT_SCRIPT)
restore = _load_script("sqlite_restore", _RESTORE_SCRIPT)


def _docker_available() -> bool:
    try:
        completed = subprocess.run(
            ["docker", "version"],
            capture_output=True,
            timeout=_DOCKER_TIMEOUT_SEC,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False
    return completed.returncode == 0


pytestmark = pytest.mark.skipif(
    not _docker_available(),
    reason="Docker is not available in this sandbox; named-volume tests need a real docker daemon",
)


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    kwargs.setdefault("timeout", 120)
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


@pytest.fixture
def test_volume():
    """A throwaway, test-prefixed Docker named volume, removed unconditionally."""
    name = f"bishop-test-namedvol-{uuid.uuid4().hex[:12]}"
    assert not name.startswith("bishop-sqlite"), "must never collide with the real volume name"
    try:
        yield name
    finally:
        # docker run -v auto-creates the volume; it may or may not exist yet
        # depending on where the test failed. -f suppresses errors either way,
        # but we still don't swallow unexpected failures silently.
        result = _run(["docker", "volume", "rm", "-f", name])
        if result.returncode != 0 and "No such volume" not in (result.stderr or ""):
            pytest.fail(f"failed to clean up test volume {name}: {result.stderr}")


def _seed_wal_db_in_volume(volume: str, rows: list[str]) -> None:
    """Write a WAL-mode sqlite db with the given rows into an empty volume,
    via a throwaway container. Mirrors how state-worker writes WAL data.
    """
    code = (
        "import sqlite3\n"
        "conn = sqlite3.connect('/data/bishop.db')\n"
        "conn.execute('PRAGMA journal_mode=WAL')\n"
        "conn.execute('CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)')\n"
        f"conn.executemany('INSERT INTO items (name) VALUES (?)', {[(r,) for r in rows]!r})\n"
        "conn.commit()\n"
        "conn.close()\n"
    )
    result = _run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{volume}:/data",
            snap.DEFAULT_VOLUME_HELPER_IMAGE,
            "python",
            "-c",
            code,
        ]
    )
    assert result.returncode == 0, f"seed failed: {result.stdout}\n{result.stderr}"


def _query_names_in_volume(volume: str) -> list[str]:
    result = _run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{volume}:/data",
            snap.DEFAULT_VOLUME_HELPER_IMAGE,
            "python",
            "-c",
            "import sqlite3; c = sqlite3.connect('/data/bishop.db'); "
            "print('\\n'.join(r[0] for r in c.execute('SELECT name FROM items ORDER BY id')))",
        ]
    )
    assert result.returncode == 0, f"query failed: {result.stdout}\n{result.stderr}"
    return [line for line in result.stdout.splitlines() if line]


def test_volume_snapshot_captures_wal_resident_rows(tmp_path: Path, test_volume: str) -> None:
    _seed_wal_db_in_volume(test_volume, ["alpha", "beta"])
    snapshot_dir = tmp_path / "snapshots"

    written = snap.run_in_volume_container(
        volume=test_volume,
        snapshot_dir=snapshot_dir,
        inner_args=["--db", "/data/bishop.db", "--snapshot-dir", "/out"],
    )

    assert written == 0
    snapshots = list(snapshot_dir.glob("bishop-*.db"))
    assert len(snapshots) == 1
    ok, _lines = snap.integrity_ok(snapshots[0])
    assert ok
    import sqlite3

    conn = sqlite3.connect(f"file:{snapshots[0].as_posix()}?mode=ro", uri=True)
    try:
        rows = [r[0] for r in conn.execute("SELECT name FROM items ORDER BY id")]
    finally:
        conn.close()
    assert rows == ["alpha", "beta"]


def test_volume_snapshot_cli_end_to_end(tmp_path: Path, test_volume: str) -> None:
    _seed_wal_db_in_volume(test_volume, ["one"])
    snapshot_dir = tmp_path / "snapshots"

    result = _run(
        [
            sys.executable,
            str(_SNAPSHOT_SCRIPT),
            "--volume",
            test_volume,
            "--snapshot-dir",
            str(snapshot_dir),
        ]
    )

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    snapshots = list(snapshot_dir.glob("bishop-*.db"))
    assert len(snapshots) == 1


def test_volume_snapshot_missing_db_reports_failure(tmp_path: Path, test_volume: str) -> None:
    # test_volume fixture yields a name docker will auto-create empty on first
    # use, so there is no bishop.db inside it yet.
    snapshot_dir = tmp_path / "snapshots"

    result = _run(
        [
            sys.executable,
            str(_SNAPSHOT_SCRIPT),
            "--volume",
            test_volume,
            "--snapshot-dir",
            str(snapshot_dir),
        ]
    )

    assert result.returncode != 0
    assert list(snapshot_dir.glob("bishop-*.db")) == []


def test_volume_restore_installs_snapshot_into_fresh_volume(
    tmp_path: Path, test_volume: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()
    snapshot_path = snapshot_dir / "bishop-20260101-000000.db"
    import sqlite3

    conn = sqlite3.connect(snapshot_path)
    conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO items (name) VALUES ('restored-row')")
    conn.commit()
    conn.close()
    monkeypatch.setattr(restore, "compose_is_up", lambda: False)

    with pytest.raises(SystemExit) as exc:
        restore.run_restore_volume(test_volume, snapshot_path, force=False, dry_run=False)
    assert exc.value.code == 0

    assert _query_names_in_volume(test_volume) == ["restored-row"]


def test_volume_restore_cli_latest_end_to_end(tmp_path: Path, test_volume: str) -> None:
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()
    import sqlite3

    older = snapshot_dir / "bishop-20200101-000000.db"
    newer = snapshot_dir / "bishop-20260911-000000.db"
    for path, name in ((older, "older"), (newer, "newer")):
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO items (name) VALUES (?)", (name,))
        conn.commit()
        conn.close()

    result = _run(
        [
            sys.executable,
            str(_RESTORE_SCRIPT),
            "--volume",
            test_volume,
            "--snapshot-dir",
            str(snapshot_dir),
            "--latest",
            "--force",
        ]
    )

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    assert _query_names_in_volume(test_volume) == ["newer"]


def test_volume_restore_refuses_when_compose_up(
    tmp_path: Path, test_volume: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()
    import sqlite3

    snapshot_path = snapshot_dir / "bishop-20260101-000000.db"
    conn = sqlite3.connect(snapshot_path)
    conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO items (name) VALUES ('should-not-land')")
    conn.commit()
    conn.close()
    monkeypatch.setattr(restore, "compose_is_up", lambda: True)

    with pytest.raises(SystemExit) as exc:
        restore.run_restore_volume(test_volume, snapshot_path, force=False, dry_run=False)

    assert exc.value.code == 2
    # The refusal must happen before any container touches the volume: querying
    # a volume docker has never initialized raises rather than returning rows.
    result = _run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{test_volume}:/data",
            snap.DEFAULT_VOLUME_HELPER_IMAGE,
            "python",
            "-c",
            "import os; print(os.path.exists('/data/bishop.db'))",
        ]
    )
    assert result.stdout.strip() == "False"


def test_volume_restore_refuses_corrupt_snapshot(
    tmp_path: Path, test_volume: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()
    snapshot_path = snapshot_dir / "bad.db"
    snapshot_path.write_bytes(b"not a database")
    monkeypatch.setattr(restore, "compose_is_up", lambda: False)

    with pytest.raises(SystemExit) as exc:
        restore.run_restore_volume(test_volume, snapshot_path, force=False, dry_run=False)

    assert exc.value.code == 3


def test_named_volume_override_compose_file_is_valid_yaml() -> None:
    assert _OVERRIDE_COMPOSE.is_file()
    with _OVERRIDE_COMPOSE.open(encoding="utf-8") as fh:
        parsed = yaml.safe_load(fh)
    assert "bishop-sqlite" in parsed["volumes"]
    assert set(parsed["services"]) == {"state-worker", "query-api"}


def test_named_volume_override_scopes_only_sqlite_mounts() -> None:
    """Render base vs base+override with `docker compose config` and assert
    the only differences are the sqlite volume entries for state-worker /
    query-api, plus the new top-level `volumes:` key. This is a render-only
    operation (`config`, not `up`) and never starts or touches any container,
    so it is safe to run even while the real `bishop` project is up.
    """
    base = _run(["docker", "compose", "-f", str(_BASE_COMPOSE), "config"], cwd=_REPO_ROOT)
    assert base.returncode == 0, base.stderr
    merged = _run(
        [
            "docker",
            "compose",
            "-f",
            str(_BASE_COMPOSE),
            "-f",
            str(_OVERRIDE_COMPOSE),
            "config",
        ],
        cwd=_REPO_ROOT,
    )
    assert merged.returncode == 0, merged.stderr

    base_cfg = yaml.safe_load(base.stdout)
    merged_cfg = yaml.safe_load(merged.stdout)

    assert set(base_cfg["services"]) == set(merged_cfg["services"])
    for service in base_cfg["services"]:
        base_svc = dict(base_cfg["services"][service])
        merged_svc = dict(merged_cfg["services"][service])
        base_volumes = base_svc.pop("volumes", [])
        merged_volumes = merged_svc.pop("volumes", [])
        # Everything except volumes must be byte-identical: network, ports,
        # environment, depends_on, healthcheck, image, build, etc.
        assert base_svc == merged_svc, f"{service}: non-volume config diverged"
        if service not in ("state-worker", "query-api"):
            assert base_volumes == merged_volumes, f"{service}: volumes should be untouched"
            continue
        # For the two sqlite-mounting services, every mount target except
        # /app/data/sqlite must be identical, and /app/data/sqlite must have
        # flipped from a bind mount to a named volume named bishop-sqlite.
        base_by_target = {v["target"]: v for v in base_volumes}
        merged_by_target = {v["target"]: v for v in merged_volumes}
        assert set(base_by_target) == set(merged_by_target)
        for target, base_mount in base_by_target.items():
            merged_mount = merged_by_target[target]
            if target == "/app/data/sqlite":
                assert base_mount["type"] == "bind"
                assert merged_mount["type"] == "volume"
                assert merged_mount["source"] == "bishop-sqlite"
            else:
                assert base_mount == merged_mount

    assert "bishop-sqlite" in merged_cfg["volumes"]
    assert "volumes" not in base_cfg or "bishop-sqlite" not in base_cfg.get("volumes", {})


def test_default_compose_discovery_ignores_named_volume_override() -> None:
    """A plain `docker compose config` (what the live `docker compose up -d`
    uses) must NOT pick up docker-compose.override.named-volume.yml, because
    Compose only auto-loads a file literally named docker-compose.override.yml.
    Render-only; does not touch the live stack.
    """
    default = _run(["docker", "compose", "config"], cwd=_REPO_ROOT)
    assert default.returncode == 0, default.stderr
    explicit_base = _run(["docker", "compose", "-f", str(_BASE_COMPOSE), "config"], cwd=_REPO_ROOT)
    assert explicit_base.returncode == 0, explicit_base.stderr

    default_cfg = yaml.safe_load(default.stdout)
    base_cfg = yaml.safe_load(explicit_base.stdout)
    assert "bishop-sqlite" not in default_cfg.get("volumes", {})
    assert default_cfg == base_cfg
