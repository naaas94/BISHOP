"""state-worker FastAPI application."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import close_pool, init_pool, run_migrations
from app.models import HealthResponse
from app.routers import batches, entries, escalations, manifest, poll, scraper_state
from app.sweeps import start_sweep_task
from bishop_shared.constants import STATE_WORKER_INTERNAL_PORT

logger = logging.getLogger(__name__)

_sweep_shutdown: asyncio.Event | None = None
_sweep_task: asyncio.Task[None] | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _sweep_shutdown, _sweep_task
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


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


def run() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=STATE_WORKER_INTERNAL_PORT)


if __name__ == "__main__":
    run()
