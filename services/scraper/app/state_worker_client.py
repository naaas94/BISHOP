"""Async HTTP client for state-worker manifest and scraper-state endpoints."""

from __future__ import annotations

from datetime import datetime

import httpx

from app.config import STATE_WORKER_BASE_URL
from app.models import ManifestBatchResult, ManifestIngestEntry, ScraperStateSnapshot
from bishop_shared.enums import SourceEnum


class StateWorkerClient:
    """httpx async client for POST /manifest/batch and scraper-state routes."""

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

    async def get_scraper_state(self, source: SourceEnum) -> ScraperStateSnapshot:
        response = await self._client.get(f"/scraper-state/{source.value}")
        response.raise_for_status()
        return ScraperStateSnapshot.model_validate(response.json())

    async def post_scraper_state(self, source: SourceEnum, timestamp: datetime) -> None:
        response = await self._client.post(
            f"/scraper-state/{source.value}",
            json={"timestamp": _iso_timestamp(timestamp)},
        )
        response.raise_for_status()
        if response.status_code != 204:
            msg = f"expected 204 from POST /scraper-state/{source.value}, got {response.status_code}"
            raise httpx.HTTPStatusError(msg, request=response.request, response=response)

    async def post_manifest_batch(
        self,
        entries: list[ManifestIngestEntry],
    ) -> ManifestBatchResult:
        payload = {
            "entries": [entry.model_dump(mode="json") for entry in entries],
        }
        response = await self._client.post("/manifest/batch", json=payload)
        response.raise_for_status()
        return ManifestBatchResult.model_validate(response.json())


def _iso_timestamp(value: datetime) -> str:
    text = value.isoformat()
    if value.tzinfo is not None:
        return text.replace("+00:00", "Z")
    return text
