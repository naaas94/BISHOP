"""Frozen service names, volume mounts, and port constants for Bishop M0."""

from dataclasses import dataclass


@dataclass(frozen=True)
class VolumeMount:
    """Host path suffix (under BISHOP_DATA_ROOT) and container mount target."""

    host_suffix: str
    container_path: str


# Spec §9 — nine services, exact compose keys and directory names.
BISHOP_SERVICES: tuple[str, ...] = (
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

# Spec §8.5 — six host-mounted volume pairs.
BISHOP_VOLUME_MOUNTS: list[VolumeMount] = [
    VolumeMount("sqlite", "/app/data/sqlite"),
    VolumeMount("lancedb", "/app/data/lancedb"),
    VolumeMount("duckdb", "/app/data/duckdb"),
    VolumeMount("bm25", "/app/data/bm25"),
    VolumeMount("profiles", "/app/config/profiles"),
    VolumeMount("logs", "/app/logs"),
]

# Default host data root; override via BISHOP_DATA_ROOT in .env (see .env.example).
BISHOP_DATA_ROOT_DEFAULT = "~/bishop_data"

STATE_WORKER_INTERNAL_PORT = 8000
QUERY_API_HOST_PORT = 8080
UI_HOST_PORT = 8081
