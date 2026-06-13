"""Async HTTP client for state-worker entry poll and index signaling."""

from __future__ import annotations

import httpx

from app.config import STATE_WORKER_BASE_URL, VECTOR_WRITE_BATCH_SIZE, VECTOR_WRITE_POLL_STATE
from app.models import EntryPollResponse, FailedPostRequest, IndexedPostRequest


class StateWorkerClient:
    """httpx async client for GET /entries/poll and POST /entries/indexed|failed."""

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

    async def poll_vector_write_queued(
        self,
        *,
        limit: int | None = None,
    ) -> EntryPollResponse:
        batch_limit = limit if limit is not None else VECTOR_WRITE_BATCH_SIZE
        response = await self._client.get(
            "/entries/poll",
            params={"state": VECTOR_WRITE_POLL_STATE, "limit": batch_limit},
        )
        response.raise_for_status()
        return EntryPollResponse.model_validate(response.json())

    async def post_indexed(self, body: IndexedPostRequest) -> None:
        response = await self._client.post(
            "/entries/indexed",
            json=body.model_dump(mode="json"),
        )
        response.raise_for_status()
        if response.status_code != 204:
            msg = f"expected 204 from POST /entries/indexed, got {response.status_code}"
            raise httpx.HTTPStatusError(msg, request=response.request, response=response)

    async def post_failed(self, body: FailedPostRequest) -> None:
        response = await self._client.post(
            "/entries/failed",
            json=body.model_dump(mode="json"),
        )
        response.raise_for_status()
        if response.status_code != 204:
            msg = f"expected 204 from POST /entries/failed, got {response.status_code}"
            raise httpx.HTTPStatusError(msg, request=response.request, response=response)
