"""query-api FastAPI application (M7 T5 HTTP surface)."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.config import LOG_LEVEL
from app.embedding import QueryEmbeddingEncoder
from app.lifespan import cold_start_init
from app.routers import batches, entries, escalations, recent, search
from app.stores.bm25_reader import Bm25QueryIndex
from app.stores.duckdb_reader import DuckDbReader
from app.stores.lancedb_reader import LanceDbSearcher
from bishop_shared.constants import STATE_WORKER_INTERNAL_PORT
from bishop_shared.query_config import DEFAULT_SEARCH_DOMAIN

logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    status: str


@dataclass
class AppStores:
    bm25: Bm25QueryIndex
    dense: LanceDbSearcher
    metadata: DuckDbReader
    _encoder: QueryEmbeddingEncoder | None = None

    @property
    def encoder(self) -> QueryEmbeddingEncoder:
        if self._encoder is None:
            self._encoder = QueryEmbeddingEncoder()
        return self._encoder


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    logger.info("query-api startup: probing stores (G7 cold-start)")
    cold_start_init(logger)

    bm25 = Bm25QueryIndex(DEFAULT_SEARCH_DOMAIN)
    bm25.load()
    bm25.start_background_reload(logger)

    stores = AppStores(
        bm25=bm25,
        dense=LanceDbSearcher(),
        metadata=DuckDbReader(),
    )
    app.state.stores = stores

    yield

    await bm25.stop_background_reload()
    stores.metadata.close()


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"error": "invalid_query", "detail": str(exc.errors())},
    )


app.include_router(search.router)
app.include_router(recent.router)
app.include_router(entries.router)
app.include_router(batches.router)
app.include_router(escalations.router)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


def run() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=STATE_WORKER_INTERNAL_PORT)


if __name__ == "__main__":
    run()
