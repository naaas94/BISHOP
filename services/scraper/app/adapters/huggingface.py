"""HuggingFace Hub manifest adapter — Hub REST API (§3.1, §10.1)."""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import httpx

from bishop_shared.enums import DomainEnum, SourceEnum
from bishop_shared.scraper_config import BACKFILL_CONFIG

from app.adapters.arxiv import compose_fallback_content
from app.adapters.base import SourceAdapter
from app.config import HUGGINGFACE_TOKEN
from app.models import ManifestIngestEntry
from app.rate_limit import SOURCE_RATE_LIMITS, TokenBucketRateLimiter

logger = logging.getLogger(__name__)

HF_API_BASE_URL = "https://huggingface.co/api"
HF_SITE_BASE_URL = "https://huggingface.co"

EntityKind = Literal["model", "dataset", "space"]

_ENTITY_LIST_PATHS: dict[EntityKind, str] = {
    "model": "/models",
    "dataset": "/datasets",
    "space": "/spaces",
}


def resolve_effective_since(
    since: datetime | None,
    *,
    now: datetime,
) -> datetime:
    """Resolve incremental ``since`` or first-run backfill window start."""
    if since is not None:
        return since
    window_days = BACKFILL_CONFIG[SourceEnum.HUGGINGFACE.value].window_days
    return now - timedelta(days=window_days)


def _auth_headers() -> dict[str, str]:
    if HUGGINGFACE_TOKEN:
        return {"Authorization": f"Bearer {HUGGINGFACE_TOKEN}"}
    return {}


def _max_results_from_env() -> int:
    raw = os.environ.get("BISHOP_HUGGINGFACE_MAX_RESULTS")
    if raw is None:
        return 100
    return int(raw)


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _entity_repo_id(item: dict[str, Any]) -> str | None:
    for key in ("id", "modelId", "name"):
        raw = item.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return None


def _entity_title(item: dict[str, Any], repo_id: str, kind: EntityKind) -> str:
    card = item.get("cardData")
    if isinstance(card, dict):
        card_title = card.get("title")
        if isinstance(card_title, str) and card_title.strip():
            return f"[{kind}] {card_title.strip()}"
    return f"[{kind}] {repo_id}"


def _entity_abstract(item: dict[str, Any]) -> str | None:
    card = item.get("cardData")
    if isinstance(card, dict):
        description = card.get("description")
        if isinstance(description, str) and description.strip():
            return " ".join(description.split())
    for key in ("description", "tag"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return " ".join(value.split())
    tags = item.get("tags")
    if isinstance(tags, list) and tags:
        return ", ".join(str(tag) for tag in tags)
    return None


def _entity_published_at(item: dict[str, Any]) -> datetime | None:
    return _parse_timestamp(item.get("createdAt")) or _parse_timestamp(item.get("lastModified"))


def parse_entity_list(
    payload: list[dict[str, Any]],
    *,
    kind: EntityKind,
    adapter: SourceAdapter,
    since: datetime,
) -> list[ManifestIngestEntry]:
    """Map Hub list JSON to manifest rows, keeping only items at or after ``since``."""
    since_utc = since.astimezone(UTC)
    seen: set[str] = set()
    entries: list[ManifestIngestEntry] = []

    for item in payload:
        repo_id = _entity_repo_id(item)
        if repo_id is None:
            continue

        published_at = _entity_published_at(item)
        if published_at is not None and published_at.astimezone(UTC) < since_utc:
            continue

        raw_id = f"{kind}:{repo_id}"
        source_id = adapter.make_source_id(raw_id)
        if source_id in seen:
            continue
        seen.add(source_id)

        entries.append(
            ManifestIngestEntry(
                source_id=source_id,
                source=adapter.source,
                url=f"{HF_SITE_BASE_URL}/{repo_id}",
                title=_entity_title(item, repo_id, kind),
                abstract=_entity_abstract(item),
                published_at=published_at,
                domain=adapter.domain,
            ),
        )

    return entries


def parse_raw_id_from_source_id(source_id: str) -> tuple[EntityKind, str]:
    """Extract entity kind and repo path from canonical ``source_id``."""
    raw = source_id.split(":", 1)[1] if ":" in source_id else source_id
    prefix, separator, repo_path = raw.partition(":")
    if separator and prefix in _ENTITY_LIST_PATHS:
        return prefix, repo_path  # type: ignore[return-value]
    return "model", raw


class HuggingFaceAdapter(SourceAdapter):
    """Fetches lightweight manifest rows from the HuggingFace Hub REST API."""

    source = SourceEnum.HUGGINGFACE
    domain = DomainEnum.PROFESSIONAL
    rate_limit = SOURCE_RATE_LIMITS[SourceEnum.HUGGINGFACE.value]

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._http_client = http_client
        self._owns_client = http_client is None
        self._rate_limiter = TokenBucketRateLimiter(self.rate_limit)

    async def fetch_manifest(
        self,
        since: datetime | None = None,
    ) -> list[ManifestIngestEntry]:
        now = datetime.now(UTC)
        effective_since = resolve_effective_since(since, now=now)
        limit = _max_results_from_env()
        params = {
            "sort": "createdAt",
            "direction": "-1",
            "limit": str(limit),
        }
        headers = _auth_headers()

        client = self._http_client or httpx.AsyncClient()
        entries: list[ManifestIngestEntry] = []
        try:
            for kind, path in _ENTITY_LIST_PATHS.items():
                await self._rate_limiter.acquire()
                response = await client.get(
                    f"{HF_API_BASE_URL}{path}",
                    params=params,
                    headers=headers,
                )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, list):
                    continue
                batch = parse_entity_list(
                    payload,
                    kind=kind,
                    adapter=self,
                    since=effective_since,
                )
                entries.extend(batch)
                logger.info(
                    "huggingface manifest slice fetched",
                    extra={
                        "event": "adapter_fetch_manifest",
                        "source": self.source.value,
                        "entity_kind": kind,
                        "fetched": len(batch),
                    },
                )
            return entries
        finally:
            if self._owns_client:
                await client.aclose()

    async def fetch_content(self, entry: ManifestIngestEntry) -> str:
        kind, repo_path = parse_raw_id_from_source_id(entry.source_id)
        readme_url = f"{HF_SITE_BASE_URL}/{repo_path}/raw/main/README.md"
        client = self._http_client or httpx.AsyncClient()
        try:
            await self._rate_limiter.acquire()
            response = await client.get(readme_url, headers=_auth_headers())
            if 200 <= response.status_code < 300 and response.text.strip():
                logger.info(
                    "huggingface content fetched",
                    extra={
                        "event": "adapter_fetch_content",
                        "source": self.source.value,
                        "source_id": entry.source_id,
                        "entity_kind": kind,
                    },
                )
                return response.text
            return compose_fallback_content(entry)
        finally:
            if self._owns_client:
                await client.aclose()
