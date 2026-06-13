"""Async HTTP client for state-worker entry poll and batch registration."""

from __future__ import annotations

import httpx

from app.config import ENRICHMENT_STAGE1_BATCH_SIZE, STATE_WORKER_BASE_URL
from app.models import BatchRegisterRequest, BatchRegisterResponse, EntryPollResponse

SCRAPED_POLL_STATE = "SCRAPED"


class StateWorkerClient:
    """httpx async client for GET /entries/poll and POST /batches."""

    def __init__(
        self,
        base_url: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = (base_url or STATE_WORKER_BASE_URL).rstrip("/")
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(base_url=self._base_url)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def poll_scraped_entries(
        self,
        *,
        limit: int | None = None,
    ) -> EntryPollResponse:
        batch_limit = limit if limit is not None else ENRICHMENT_STAGE1_BATCH_SIZE
        response = await self._client.get(
            "/entries/poll",
            params={"state": SCRAPED_POLL_STATE, "limit": batch_limit},
        )
        response.raise_for_status()
        return EntryPollResponse.model_validate(response.json())

    async def register_batch(self, body: BatchRegisterRequest) -> BatchRegisterResponse:
        response = await self._client.post(
            "/batches",
            json=body.model_dump(mode="json"),
        )
        response.raise_for_status()
        return BatchRegisterResponse.model_validate(response.json())
