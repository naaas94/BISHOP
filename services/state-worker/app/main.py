"""state-worker FastAPI application."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response

from app.db import close_pool, enforce_integrity, get_db, init_pool, run_migrations
from app.models import DbHealthResponse, HealthResponse
from app.routers import batches, entries, escalations, manifest, parked, poll, scraper_state
from app.sweeps import start_sweep_task
from bishop_shared.constants import STATE_WORKER_INTERNAL_PORT

logger = logging.getLogger(__name__)

_sweep_shutdown: asyncio.Event | None = None
_sweep_task: asyncio.Task[None] | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _sweep_shutdown, _sweep_task
    logger.info("state-worker startup: checking sqlite integrity before migrations")
    enforce_integrity()
    logger.info("state-worker startup: running migrations")
    run_migrations()
    logger.info("state-worker startup: initializing database pool")
    await init_pool()
    _sweep_task, _sweep_shutdown = start_sweep_task()
    logger.info("state-worker startup: sweep background task started")
    yield
    if _sweep_shutdown is not None:
        _sweep_shutdown.set()
    if _sweep_task is not None:
        await _sweep_task
    await close_pool()


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)

app.include_router(manifest.router)
app.include_router(poll.router)
app.include_router(entries.router)
app.include_router(batches.router)
app.include_router(scraper_state.router)
app.include_router(escalations.router)
app.include_router(parked.router)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/health/db", response_model=DbHealthResponse)
async def health_db(response: Response) -> DbHealthResponse:
    try:
        async with get_db() as conn:
            cursor = await conn.execute(
                "SELECT version_num FROM alembic_version LIMIT 1"
            )
            row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("alembic_version is empty")
        return DbHealthResponse(status="ok", detail=str(row[0]))
    except Exception as exc:
        logger.error(
            "health/db failed: %s",
            exc,
            extra={"event": "health_db_failed"},
        )
        response.status_code = 503
        return DbHealthResponse(status="error", detail=str(exc) or type(exc).__name__)


def run() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=STATE_WORKER_INTERNAL_PORT)


if __name__ == "__main__":
    run()
