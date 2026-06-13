"""Query-api startup lifecycle — G7 cold-start store probes (M7 T1)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from bishop_shared.indexing_config import (
    DUCKDB_PATH,
    LANCEDB_DIR,
    LANCEDB_TABLE_NAME,
    bm25_domain_root,
)
from bishop_shared.query_config import DEFAULT_SEARCH_DOMAIN

logger = logging.getLogger(__name__)


@dataclass
class ColdStartState:
    """Store readiness flags set during startup probes."""

    bm25_ready: bool = False
    lancedb_ready: bool = False
    duckdb_ready: bool = False


def _warn_cold_start_empty(
    log: logging.Logger,
    *,
    channel: str,
    detail: str,
    domain: str | None = None,
) -> None:
    extra: dict[str, str] = {
        "event": "store_cold_start_empty",
        "channel": channel,
    }
    if domain is not None:
        extra["domain"] = domain
    log.warning(detail, extra=extra)


def cold_start_init(log: logging.Logger | None = None) -> ColdStartState:
    """Probe BM25, LanceDB, and DuckDB stores; WARN on missing paths, never raise."""
    active_logger = log or logger
    state = ColdStartState()

    bm25_root = bm25_domain_root(DEFAULT_SEARCH_DOMAIN)
    if bm25_root.is_dir():
        state.bm25_ready = True
    else:
        _warn_cold_start_empty(
            active_logger,
            channel="bm25_main",
            domain=DEFAULT_SEARCH_DOMAIN,
            detail="BM25 index directory missing; serving empty BM25 channel",
        )

    lance_table = Path(LANCEDB_DIR) / f"{LANCEDB_TABLE_NAME}.lance"
    if lance_table.is_dir():
        state.lancedb_ready = True
    else:
        _warn_cold_start_empty(
            active_logger,
            channel="dense",
            detail="LanceDB entries table missing; skipping dense channel",
        )

    if Path(DUCKDB_PATH).is_file():
        state.duckdb_ready = True
    else:
        _warn_cold_start_empty(
            active_logger,
            channel="metadata",
            detail="DuckDB mirror file missing; serving empty metadata filter",
        )

    return state
