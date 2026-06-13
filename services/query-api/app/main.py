"""query-api FastAPI application (M7 T1 scaffold)."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from app.config import LOG_LEVEL
from app.lifespan import cold_start_init
from bishop_shared.constants import STATE_WORKER_INTERNAL_PORT

logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    status: str


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logging.basicConfig(level=getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    logger.info("query-api startup: probing stores (G7 cold-start)")
    cold_start_init(logger)
    yield


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


def run() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=STATE_WORKER_INTERNAL_PORT)


if __name__ == "__main__":
    run()
