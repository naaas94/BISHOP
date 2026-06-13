"""Async HTTP client for state-worker manifest poll and entry write routes."""

from __future__ import annotations

import httpx

from app.config import CONTENT_SCRAPE_BATCH_SIZE, STATE_WORKER_BASE_URL
from app.models import (
    ContentPostRequest,
    ContentPostResponse,
    FailedPostRequest,
    ManifestPollResponse,
)


class StateWorkerClient:
    """httpx async client for GET /manifest/poll and POST /entries/*."""

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

    async def poll_relevance_passed(
        self,
        *,
        limit: int | None = None,
    ) -> ManifestPollResponse:
        batch_limit = limit if limit is not None else CONTENT_SCRAPE_BATCH_SIZE
        response = await self._client.get(
            "/manifest/poll",
            params={"state": "RELEVANCE_PASSED", "limit": batch_limit},
        )
        response.raise_for_status()
        return ManifestPollResponse.model_validate(response.json())

    async def post_content(self, body: ContentPostRequest) -> ContentPostResponse:
        response = await self._client.post(
            "/entries/content",
            json=body.model_dump(mode="json"),
        )
        response.raise_for_status()
        return ContentPostResponse.model_validate(response.json())

    async def post_failed(self, body: FailedPostRequest) -> None:
        response = await self._client.post(
            "/entries/failed",
            json=body.model_dump(mode="json"),
        )
        response.raise_for_status()
        if response.status_code != 204:
            msg = f"expected 204 from POST /entries/failed, got {response.status_code}"
            raise httpx.HTTPStatusError(msg, request=response.request, response=response)
