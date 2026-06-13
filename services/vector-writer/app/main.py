"""Vector-writer entrypoint — asyncio scheduler invoking ``index_cycle``."""

from __future__ import annotations

import asyncio
import logging

from app.config import LOG_LEVEL, VECTOR_WRITE_POLL_INTERVAL_SEC
from app.embedding import EmbeddingEncoder
from app.index_entry import IndexStores
from app.loop import index_cycle
from app.state_worker_client import StateWorkerClient
from app.stores.duckdb_mirror import DuckDbMirror
from app.stores.lancedb_store import LanceDbStore
from bishop_shared.indexing_config import LANCEDB_DIR

logger = logging.getLogger(__name__)


def _build_stores() -> IndexStores:
    return IndexStores(
        encoder=EmbeddingEncoder(),
        lancedb=LanceDbStore(LANCEDB_DIR),
        duckdb=DuckDbMirror(),
    )


async def run_scheduler() -> None:
    """Periodically run ``index_cycle`` until cancelled."""
    stores = _build_stores()
    client = StateWorkerClient()
    try:
        while True:
            await index_cycle(state_client=client, stores=stores)
            await asyncio.sleep(VECTOR_WRITE_POLL_INTERVAL_SEC)
    finally:
        await client.aclose()
        stores.duckdb.close()


def main() -> None:
    logging.basicConfig(level=getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    logger.info("vector-writer starting scheduler")
    asyncio.run(run_scheduler())


if __name__ == "__main__":
    main()
