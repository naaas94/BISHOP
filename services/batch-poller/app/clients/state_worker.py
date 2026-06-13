"""Async HTTP client for state-worker batch and manifest endpoints."""

from __future__ import annotations

from datetime import datetime

import httpx

from app.config import STATE_WORKER_BASE_URL
from app.models import (
    BatchPatchRequest,
    BatchRecordWire,
    BatchTimeoutResponse,
    BatchesListResponse,
    PreFilterResultsRequest,
    PreFilterResultsResponse,
)


class StateWorkerClient:
    """httpx async client for batch lifecycle and pre-filter result routes."""

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

    async def get_in_flight_batches(self) -> list[BatchRecordWire]:
        response = await self._client.get(
            "/batches",
            params={"status": "submitted,processing"},
        )
        response.raise_for_status()
        return BatchesListResponse.model_validate(response.json()).batches

    async def post_pre_filter_results(
        self,
        request: PreFilterResultsRequest,
    ) -> PreFilterResultsResponse:
        response = await self._client.post(
            "/manifest/pre-filter-results",
            json=request.model_dump(mode="json"),
        )
        response.raise_for_status()
        return PreFilterResultsResponse.model_validate(response.json())

    async def patch_batch(self, batch_id: str, request: BatchPatchRequest) -> None:
        response = await self._client.patch(
            f"/batches/{batch_id}",
            json=request.model_dump(mode="json", exclude_none=True),
        )
        response.raise_for_status()

    async def post_batch_timeout(self, batch_id: str) -> BatchTimeoutResponse:
        response = await self._client.post(f"/batches/{batch_id}/timeout")
        response.raise_for_status()
        return BatchTimeoutResponse.model_validate(response.json())


def iso_timestamp(value: datetime) -> str:
    text = value.isoformat()
    if value.tzinfo is not None:
        return text.replace("+00:00", "Z")
    return text
