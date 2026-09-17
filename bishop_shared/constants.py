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

# M1 — frozen SQLite filename and absolute container path (plan flag 2 resolution).
SQLITE_DB_FILENAME = "bishop.db"
_SQLITE_MOUNT = next(m for m in BISHOP_VOLUME_MOUNTS if m.host_suffix == "sqlite").container_path
SQLITE_DB_PATH = f"{_SQLITE_MOUNT}/{SQLITE_DB_FILENAME}"

# Integrity-gated snapshots live beside the live file; the live name never rotates.
# See .dev/decision-logs/ops/sqlite-snapshot-and-integrity-gate.md.
SQLITE_SNAPSHOT_DIRNAME = "snapshots"
SQLITE_SNAPSHOT_DIR = f"{_SQLITE_MOUNT}/{SQLITE_SNAPSHOT_DIRNAME}"
SQLITE_SNAPSHOT_PREFIX = "bishop-"
SQLITE_SNAPSHOT_SUFFIX = ".db"
SQLITE_SNAPSHOT_TIMESTAMP_FORMAT = "%Y%m%d-%H%M%S"
SQLITE_SNAPSHOT_GLOB = f"{SQLITE_SNAPSHOT_PREFIX}*{SQLITE_SNAPSHOT_SUFFIX}"
SQLITE_SNAPSHOT_TTL_HOURS = 24
SQLITE_SNAPSHOT_INTERVAL_MINUTES = 30

# Busy timeout for every writer connection; a Windows bind mount blocks longer
# than the SQLite default of 0ms, which surfaces as spurious "database is locked".
SQLITE_BUSY_TIMEOUT_MS = 5000

# Harvest pool sidecar — not one of the six spec §8.5 mounts. Compose adds
# this volume on scraper (rw) and query-api (ro). Do not fold into
# BISHOP_VOLUME_MOUNTS (tests pin that list at 6).
HARVEST_DIRNAME = "harvest"
HARVEST_DIR = "/app/data/harvest"
HARVEST_DB_FILENAME = "ledger.sqlite"
HARVEST_DB_PATH = f"{HARVEST_DIR}/{HARVEST_DB_FILENAME}"
HARVEST_ECONOMICS_FILENAME = "economics.yaml"
