"""GitHub manifest adapter — Search API repositories + README content (§10.1)."""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta

import httpx

from bishop_shared.enums import DomainEnum, SourceEnum
from bishop_shared.scraper_config import BACKFILL_CONFIG

from app.adapters.base import SourceAdapter
from app.config import GITHUB_TOKEN
from app.models import ManifestIngestEntry
from app.rate_limit import SOURCE_RATE_LIMITS, TokenBucketRateLimiter

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
GITHUB_SEARCH_REPOS_URL = f"{GITHUB_API_BASE}/search/repositories"

# Backfill window (30 days) at 100 repos/page and default 10 pages stays within
# authenticated Search API budget (10 calls << 5000/hr Appendix B row).
_DEFAULT_MAX_PAGES = 10


def _max_pages_from_env() -> int:
    raw = os.environ.get("BISHOP_GITHUB_MAX_PAGES")
    if raw is None:
        return _DEFAULT_MAX_PAGES
    return int(raw)


def resolve_effective_since(
    since: datetime | None,
    *,
    now: datetime,
) -> datetime:
    """Resolve incremental ``since`` or first-run backfill window start."""
    if since is not None:
        return since
    window_days = BACKFILL_CONFIG[SourceEnum.GITHUB.value].window_days
    return now - timedelta(days=window_days)


def _format_github_date(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%d")


def build_search_query(since: datetime) -> str:
    """Build GitHub repository search query for repos updated since ``since``."""
    return f"pushed:>{_format_github_date(since)} stars:>10"


def _parse_github_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def parse_search_response(
    payload: dict[str, object],
    *,
    adapter: SourceAdapter,
) -> list[ManifestIngestEntry]:
    """Map GitHub search JSON to manifest ingest DTOs."""
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        return []

    seen: set[str] = set()
    entries: list[ManifestIngestEntry] = []

    for item in raw_items:
        if not isinstance(item, dict):
            continue
        full_name = item.get("full_name")
        if not isinstance(full_name, str) or "/" not in full_name:
            continue

        source_id = adapter.make_source_id(full_name)
        if source_id in seen:
            continue
        seen.add(source_id)

        name = item.get("name")
        description = item.get("description")
        html_url = item.get("html_url")
        pushed_at = item.get("pushed_at")

        title = name.strip() if isinstance(name, str) and name.strip() else full_name
        abstract = description.strip() if isinstance(description, str) and description.strip() else None
        url = html_url if isinstance(html_url, str) and html_url else f"https://github.com/{full_name}"

        entries.append(
            ManifestIngestEntry(
                source_id=source_id,
                source=adapter.source,
                url=url,
                title=title,
                abstract=abstract,
                published_at=_parse_github_datetime(
                    pushed_at if isinstance(pushed_at, str) else None,
                ),
                domain=adapter.domain,
            ),
        )

    return entries


def parse_raw_id_from_source_id(source_id: str) -> str:
    """Extract ``owner/repo`` from canonical ``source_name:raw_id`` form."""
    if ":" in source_id:
        return source_id.split(":", 1)[1]
    return source_id


def compose_fallback_content(entry: ManifestIngestEntry) -> str:
    """Compose title + description when README fetch is unavailable."""
    abstract = entry.abstract or ""
    return f"{entry.title}\n\n{abstract}"


class GitHubAdapter(SourceAdapter):
    """Fetches lightweight manifest rows from the GitHub Search API."""

    source = SourceEnum.GITHUB
    domain = DomainEnum.PROFESSIONAL
    rate_limit = SOURCE_RATE_LIMITS[SourceEnum.GITHUB.value]

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._http_client = http_client
        self._owns_client = http_client is None
        self._rate_limiter = TokenBucketRateLimiter(self.rate_limit)

    def _auth_headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
        return headers

    async def fetch_manifest(
        self,
        since: datetime | None = None,
    ) -> list[ManifestIngestEntry]:
        now = datetime.now(UTC)
        effective_since = resolve_effective_since(since, now=now)
        search_query = build_search_query(effective_since)
        max_pages = _max_pages_from_env()

        client = self._http_client or httpx.AsyncClient()
        entries: list[ManifestIngestEntry] = []
        seen: set[str] = set()

        try:
            for page in range(1, max_pages + 1):
                params = {
                    "q": search_query,
                    "sort": "updated",
                    "order": "desc",
                    "per_page": 100,
                    "page": page,
                }
                await self._rate_limiter.acquire()
                response = await client.get(
                    GITHUB_SEARCH_REPOS_URL,
                    params=params,
                    headers=self._auth_headers(),
                )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    break

                page_entries = parse_search_response(payload, adapter=self)
                if not page_entries:
                    break

                for entry in page_entries:
                    if entry.source_id in seen:
                        continue
                    seen.add(entry.source_id)
                    entries.append(entry)

                raw_items = payload.get("items")
                if not isinstance(raw_items, list) or len(raw_items) < 100:
                    break

            logger.info(
                "github manifest fetched",
                extra={
                    "event": "adapter_manifest_fetched",
                    "source": self.source.value,
                    "fetched": len(entries),
                    "max_pages": max_pages,
                },
            )
            return entries
        finally:
            if self._owns_client:
                await client.aclose()

    async def fetch_content(self, entry: ManifestIngestEntry) -> str:
        raw_id = parse_raw_id_from_source_id(entry.source_id)
        url = f"{GITHUB_API_BASE}/repos/{raw_id}/readme"
        headers = self._auth_headers()
        headers["Accept"] = "application/vnd.github.raw"

        client = self._http_client or httpx.AsyncClient()
        try:
            await self._rate_limiter.acquire()
            response = await client.get(url, headers=headers)
            if response.status_code < 200 or response.status_code >= 300:
                return compose_fallback_content(entry)
            text = response.text.strip()
            if not text:
                return compose_fallback_content(entry)
            return text
        finally:
            if self._owns_client:
                await client.aclose()
