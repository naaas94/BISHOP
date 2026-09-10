"""Semantic Scholar manifest adapter — Graph API paper search (§10.1)."""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta

import httpx

from bishop_shared.enums import DomainEnum, SourceEnum
from bishop_shared.scraper_config import BACKFILL_CONFIG

from app.adapters.base import SourceAdapter
from app.config import SEMANTIC_SCHOLAR_API_KEY
from app.models import ManifestIngestEntry
from app.rate_limit import SOURCE_RATE_LIMITS, TokenBucketRateLimiter

logger = logging.getLogger(__name__)

SEMANTIC_SCHOLAR_API_BASE = "https://api.semanticscholar.org/graph/v1"
SEMANTIC_SCHOLAR_SEARCH_URL = f"{SEMANTIC_SCHOLAR_API_BASE}/paper/search"
SEMANTIC_SCHOLAR_PAPER_URL = f"{SEMANTIC_SCHOLAR_API_BASE}/paper"

MANIFEST_FIELDS = "paperId,title,abstract,url,publicationDate"
CONTENT_FIELDS = "title,abstract,tldr"

_DEFAULT_SEARCH_QUERY = "machine learning artificial intelligence"


def _max_results_from_env() -> int:
    raw = os.environ.get("BISHOP_SEMANTIC_SCHOLAR_MAX_RESULTS")
    if raw is None:
        return 100
    return int(raw)


def resolve_effective_since(
    since: datetime | None,
    *,
    now: datetime,
) -> datetime:
    """Resolve incremental ``since`` or first-run backfill window start."""
    if since is not None:
        return since
    window_days = BACKFILL_CONFIG[SourceEnum.SEMANTIC_SCHOLAR.value].window_days
    return now - timedelta(days=window_days)


def _format_date(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%d")


def build_search_params(since: datetime, until: datetime) -> dict[str, str | int]:
    """Build Semantic Scholar paper search query parameters."""
    return {
        "query": _DEFAULT_SEARCH_QUERY,
        "publicationDateOrYear": f"{_format_date(since)}:{_format_date(until)}",
        "fields": MANIFEST_FIELDS,
        "limit": _max_results_from_env(),
    }


def _parse_publication_date(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    if len(normalized) == 10:
        normalized = f"{normalized}T00:00:00+00:00"
    return datetime.fromisoformat(normalized)


def parse_search_response(
    payload: dict[str, object],
    *,
    adapter: SourceAdapter,
) -> list[ManifestIngestEntry]:
    """Map Semantic Scholar search JSON to manifest ingest DTOs."""
    raw_data = payload.get("data")
    if not isinstance(raw_data, list):
        return []

    seen: set[str] = set()
    entries: list[ManifestIngestEntry] = []

    for item in raw_data:
        if not isinstance(item, dict):
            continue
        paper_id = item.get("paperId")
        title = item.get("title")
        if not isinstance(paper_id, str) or not paper_id:
            continue
        if not isinstance(title, str) or not title.strip():
            continue

        source_id = adapter.make_source_id(paper_id)
        if source_id in seen:
            continue
        seen.add(source_id)

        abstract = item.get("abstract")
        url = item.get("url")
        publication_date = item.get("publicationDate")

        entries.append(
            ManifestIngestEntry(
                source_id=source_id,
                source=adapter.source,
                url=url if isinstance(url, str) and url else f"https://www.semanticscholar.org/paper/{paper_id}",
                title=title.strip(),
                abstract=abstract.strip() if isinstance(abstract, str) and abstract.strip() else None,
                published_at=_parse_publication_date(
                    publication_date if isinstance(publication_date, str) else None,
                ),
                domain=adapter.domain,
            ),
        )

    return entries


def parse_raw_id_from_source_id(source_id: str) -> str:
    """Extract Semantic Scholar paper id from canonical ``source_name:raw_id`` form."""
    if ":" in source_id:
        return source_id.split(":", 1)[1]
    return source_id


def compose_fallback_content(entry: ManifestIngestEntry) -> str:
    """Compose title + abstract when full paper text is unavailable."""
    abstract = entry.abstract or ""
    return f"{entry.title}\n\n{abstract}"


def compose_paper_content(payload: dict[str, object], entry: ManifestIngestEntry) -> str:
    """Build paper-shaped content from Semantic Scholar paper detail fields."""
    title = payload.get("title")
    abstract = payload.get("abstract")
    tldr = payload.get("tldr")

    parts: list[str] = []
    if isinstance(title, str) and title.strip():
        parts.append(title.strip())
    elif entry.title:
        parts.append(entry.title)

    if isinstance(abstract, str) and abstract.strip():
        parts.append(abstract.strip())
    elif entry.abstract:
        parts.append(entry.abstract)

    if isinstance(tldr, dict):
        tldr_text = tldr.get("text")
        if isinstance(tldr_text, str) and tldr_text.strip():
            parts.append(tldr_text.strip())

    if parts:
        return "\n\n".join(parts)
    return compose_fallback_content(entry)


class SemanticScholarAdapter(SourceAdapter):
    """Fetches lightweight manifest rows from the Semantic Scholar Graph API."""

    source = SourceEnum.SEMANTIC_SCHOLAR
    domain = DomainEnum.PROFESSIONAL
    rate_limit = SOURCE_RATE_LIMITS[SourceEnum.SEMANTIC_SCHOLAR.value]

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._http_client = http_client
        self._owns_client = http_client is None
        self._rate_limiter = TokenBucketRateLimiter(self.rate_limit)

    def _auth_headers(self) -> dict[str, str]:
        if SEMANTIC_SCHOLAR_API_KEY:
            return {"x-api-key": SEMANTIC_SCHOLAR_API_KEY}
        return {}

    async def fetch_manifest(
        self,
        since: datetime | None = None,
    ) -> list[ManifestIngestEntry]:
        now = datetime.now(UTC)
        effective_since = resolve_effective_since(since, now=now)
        params = build_search_params(effective_since, now)

        client = self._http_client or httpx.AsyncClient()
        try:
            await self._rate_limiter.acquire()
            response = await client.get(
                SEMANTIC_SCHOLAR_SEARCH_URL,
                params=params,
                headers=self._auth_headers(),
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                return []
            entries = parse_search_response(payload, adapter=self)
            logger.info(
                "semantic scholar manifest fetched",
                extra={
                    "event": "adapter_manifest_fetched",
                    "source": self.source.value,
                    "fetched": len(entries),
                },
            )
            return entries
        finally:
            if self._owns_client:
                await client.aclose()

    async def fetch_content(self, entry: ManifestIngestEntry) -> str:
        raw_id = parse_raw_id_from_source_id(entry.source_id)
        url = f"{SEMANTIC_SCHOLAR_PAPER_URL}/{raw_id}"
        params = {"fields": CONTENT_FIELDS}

        client = self._http_client or httpx.AsyncClient()
        try:
            await self._rate_limiter.acquire()
            response = await client.get(
                url,
                params=params,
                headers=self._auth_headers(),
            )
            if response.status_code < 200 or response.status_code >= 300:
                return compose_fallback_content(entry)
            payload = response.json()
            if not isinstance(payload, dict):
                return compose_fallback_content(entry)
            return compose_paper_content(payload, entry)
        finally:
            if self._owns_client:
                await client.aclose()
