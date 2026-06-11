"""Unit tests for bishop_shared.constants (M0 contract surface)."""

from pathlib import Path

import pytest

from bishop_shared.constants import (
    BISHOP_DATA_ROOT_DEFAULT,
    BISHOP_SERVICES,
    BISHOP_VOLUME_MOUNTS,
    QUERY_API_HOST_PORT,
    SQLITE_DB_FILENAME,
    SQLITE_DB_PATH,
    STATE_WORKER_INTERNAL_PORT,
    UI_HOST_PORT,
    VolumeMount,
)

SPEC_SERVICES = (
    "scraper",
    "state-worker",
    "pre-filter-worker",
    "content-scraper",
    "enrichment-batcher",
    "batch-poller",
    "vector-writer",
    "query-api",
    "ui",
)

SPEC_VOLUME_MOUNTS = [
    ("sqlite", "/app/data/sqlite"),
    ("lancedb", "/app/data/lancedb"),
    ("duckdb", "/app/data/duckdb"),
    ("bm25", "/app/data/bm25"),
    ("profiles", "/app/config/profiles"),
    ("logs", "/app/logs"),
]


def test_service_names_match_spec() -> None:
    assert BISHOP_SERVICES == SPEC_SERVICES
    assert len(BISHOP_SERVICES) == 9


def test_volume_mounts_match_spec() -> None:
    assert len(BISHOP_VOLUME_MOUNTS) == 6
    actual = [(m.host_suffix, m.container_path) for m in BISHOP_VOLUME_MOUNTS]
    assert actual == SPEC_VOLUME_MOUNTS
    assert all(isinstance(m, VolumeMount) for m in BISHOP_VOLUME_MOUNTS)


def test_data_root_env_default() -> None:
    assert BISHOP_DATA_ROOT_DEFAULT == "~/bishop_data"
    env_example = Path(".env.example").read_text(encoding="utf-8")
    assert "BISHOP_DATA_ROOT=~/bishop_data" in env_example
    assert "Windows" in env_example


def test_internal_ports() -> None:
    assert STATE_WORKER_INTERNAL_PORT == 8000


def test_host_ports() -> None:
    assert QUERY_API_HOST_PORT == 8080
    assert UI_HOST_PORT == 8081


def test_service_names_are_unique() -> None:
    """Falsifier: duplicate compose key would break DNS for dependents."""
    assert len(set(BISHOP_SERVICES)) == len(BISHOP_SERVICES)


def test_sqlite_db_filename() -> None:
    assert SQLITE_DB_FILENAME == "bishop.db"
    assert SQLITE_DB_PATH == "/app/data/sqlite/bishop.db"
