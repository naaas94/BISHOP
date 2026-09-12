"""Papers With Code manifest adapter — REST API v1 (§3.1, §10.1)."""

from __future__ import annotations

import logging
import os
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx

from bishop_shared.enums import DomainEnum, SourceEnum
from bishop_shared.scraper_config import BACKFILL_CONFIG

from app.adapters.arxiv import compose_fallback_content
from app.adapters.base import SourceAdapter
from app.models import ManifestIngestEntry
from app.rate_limit import SOURCE_RATE_LIMITS, TokenBucketRateLimiter

logger = logging.getLogger(__name__)

PWC_API_BASE_URL = "https://paperswithcode.com/api/v1"
PWC_PAPERS_LIST_URL = f"{PWC_API_BASE_URL}/papers/"


def _paperswithcode_api_unavailable(response: httpx.Response) -> bool:
    """True when the v1 API is gone (site 302s to huggingface.co/papers)."""
    if response.is_redirect:
        return True
    content_type = response.headers.get("content-type", "")
    return response.status_code < 400 and "json" not in content_type.lower()


def resolve_effective_since(
    since: datetime | None,
    *,
    now: datetime,
) -> datetime:
    """Resolve incremental ``since`` or first-run backfill window start."""
    if since is not None:
        return since
    window_days = BACKFILL_CONFIG[SourceEnum.PAPERSWITHCODE.value].window_days
    return now - timedelta(days=window_days)


def _items_per_page_from_env() -> int:
    raw = os.environ.get("BISHOP_PAPERSWITHCODE_ITEMS_PER_PAGE")
    if raw is None:
        return 50
    return int(raw)


def _parse_published(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed_date = date.fromisoformat(value)
    except ValueError:
        return None
    return datetime(parsed_date.year, parsed_date.month, parsed_date.day, tzinfo=UTC)


def parse_papers_page(
    payload: dict[str, Any],
    *,
    adapter: SourceAdapter,
    since: datetime,
) -> list[ManifestIngestEntry]:
    """Map one Papers With Code list page to manifest rows."""
    since_date = since.astimezone(UTC).date()
    results = payload.get("results")
    if not isinstance(results, list):
        return []

    seen: set[str] = set()
    entries: list[ManifestIngestEntry] = []

    for item in results:
        if not isinstance(item, dict):
            continue
        paper_id = item.get("id")
        title = item.get("title")
        if not isinstance(paper_id, str) or not paper_id.strip():
            continue
        if not isinstance(title, str) or not title.strip():
            continue

        published_at = _parse_published(
            item.get("published") if isinstance(item.get("published"), str) else None,
        )
        if published_at is not None and published_at.date() < since_date:
            continue

        source_id = adapter.make_source_id(paper_id.strip())
        if source_id in seen:
            continue
        seen.add(source_id)

        abstract_raw = item.get("abstract")
        abstract = (
            " ".join(str(abstract_raw).split())
            if isinstance(abstract_raw, str) and abstract_raw.strip()
            else None
        )
        url_abs = item.get("url_abs")
        url = (
            str(url_abs).strip()
            if isinstance(url_abs, str) and url_abs.strip()
            else f"https://paperswithcode.com/paper/{paper_id.strip()}"
        )

        entries.append(
            ManifestIngestEntry(
                source_id=source_id,
                source=adapter.source,
                url=url,
                title=title.strip(),
                abstract=abstract,
                published_at=published_at,
                domain=adapter.domain,
            ),
        )

    return entries


def parse_raw_id_from_source_id(source_id: str) -> str:
    """Extract Papers With Code paper slug from canonical ``source_id``."""
    if ":" in source_id:
        return source_id.split(":", 1)[1]
    return source_id


class PapersWithCodeAdapter(SourceAdapter):
    """Fetches lightweight manifest rows from the Papers With Code REST API."""

    source = SourceEnum.PAPERSWITHCODE
    domain = DomainEnum.PROFESSIONAL
    rate_limit = SOURCE_RATE_LIMITS[SourceEnum.PAPERSWITHCODE.value]

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
        params = {
            "page": "1",
            "items_per_page": str(_items_per_page_from_env()),
        }

        client = self._http_client or httpx.AsyncClient()
        try:
            await self._rate_limiter.acquire()
            response = await client.get(PWC_PAPERS_LIST_URL, params=params)
            if _paperswithcode_api_unavailable(response):
                logger.warning(
                    "paperswithcode API discontinued; skipping manifest fetch",
                    extra={
                        "event": "adapter_source_unavailable",
                        "source": self.source.value,
                        "http_status": response.status_code,
                    },
                )
                return []
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                return []
            entries = parse_papers_page(payload, adapter=self, since=effective_since)
            logger.info(
                "paperswithcode manifest fetched",
                extra={
                    "event": "adapter_fetch_manifest",
                    "source": self.source.value,
                    "fetched": len(entries),
                },
            )
            return entries
        finally:
            if self._owns_client:
                await client.aclose()

    async def fetch_content(self, entry: ManifestIngestEntry) -> str:
        paper_id = parse_raw_id_from_source_id(entry.source_id)
        detail_url = f"{PWC_API_BASE_URL}/papers/{paper_id}/"
        client = self._http_client or httpx.AsyncClient()
        try:
            await self._rate_limiter.acquire()
            response = await client.get(detail_url)
            if 200 <= response.status_code < 300:
                payload = response.json()
                if isinstance(payload, dict):
                    abstract_raw = payload.get("abstract")
                    title_raw = payload.get("title")
                    abstract = (
                        " ".join(str(abstract_raw).split())
                        if isinstance(abstract_raw, str) and abstract_raw.strip()
                        else entry.abstract or ""
                    )
                    title = (
                        str(title_raw).strip()
                        if isinstance(title_raw, str) and title_raw.strip()
                        else entry.title
                    )
                    if abstract:
                        logger.info(
                            "paperswithcode content fetched",
                            extra={
                                "event": "adapter_fetch_content",
                                "source": self.source.value,
                                "source_id": entry.source_id,
                            },
                        )
                        return f"{title}\n\n{abstract}"
            return compose_fallback_content(entry)
        finally:
            if self._owns_client:
                await client.aclose()
