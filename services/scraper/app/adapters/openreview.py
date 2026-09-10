"""OpenReview manifest adapter — unauthenticated REST search API (M8 T4, spec §3.1).

Live-probed 2026-09-10 against the real OpenReview hosts before choosing this
shape (see ``.dev/decision-logs/m8-hardening-scale/T4-openreview-lesswrong.md``
for full evidence):

* ``api.openreview.net/notes`` (API v1) and ``api2.openreview.net/notes``
  (API v2, filtered by ``content.venueid=`` or ``invitation=``) both return
  HTTP 403 ``ChallengeRequiredError`` for unauthenticated callers.
* ``api2.openreview.net/notes/search`` (term search) returns HTTP 200 with
  well-formed note JSON for unauthenticated callers, and supports
  ``sort=cdate:desc``.

This adapter therefore fetches via the search endpoint with a broad
cross-venue term and filters to entries newer than ``since`` client-side,
rather than the (blocked) venue/invitation-filtered listing endpoints.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from bishop_shared.enums import DomainEnum, SourceEnum

from app.adapters.base import SourceAdapter
from app.models import ManifestIngestEntry
from app.rate_limit import SOURCE_RATE_LIMITS, TokenBucketRateLimiter

logger = logging.getLogger(__name__)

OPENREVIEW_SEARCH_API_URL = "https://api2.openreview.net/notes/search"
OPENREVIEW_FORUM_BASE_URL = "https://openreview.net/forum"

# Unauthenticated ``/notes/search`` requires a non-empty ``term``; venue-id
# scoping is not reachable without auth (see module docstring), so a broad
# cross-venue term stands in for venue scoping until authenticated access is
# available. Tracked as an accuracy tradeoff, not a T4 blocker — see decision
# log "Items deferred".
_SEARCH_TERM = "machine learning"

_DEFAULT_SINCE_DAYS = 7


def _max_results_from_env() -> int:
    raw = os.environ.get("BISHOP_OPENREVIEW_MAX_RESULTS")
    if raw is None:
        return 100
    return int(raw)


def resolve_effective_since(
    since: datetime | None,
    *,
    now: datetime,
) -> datetime:
    """Resolve incremental ``since`` or the adapter-local default window."""
    if since is not None:
        return since
    return now - timedelta(days=_DEFAULT_SINCE_DAYS)


def _note_field(note: dict[str, Any], field: str) -> str | None:
    content = note.get("content")
    if not isinstance(content, dict):
        return None
    entry = content.get(field)
    if isinstance(entry, dict):
        value = entry.get("value")
        return value if isinstance(value, str) else None
    return None


def _note_cdate_ms(note: dict[str, Any]) -> int | None:
    value = note.get("cdate")
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    return None


def parse_search_response(
    payload: dict[str, Any],
    *,
    adapter: "OpenReviewAdapter",
    since_ms: int,
) -> list[ManifestIngestEntry]:
    """Map ``/notes/search`` JSON payload to manifest DTOs newer than ``since_ms``."""
    entries: list[ManifestIngestEntry] = []
    seen: set[str] = set()

    for note in payload.get("notes") or []:
        note_id = note.get("id")
        title = _note_field(note, "title")
        if not note_id or not title:
            continue

        cdate_ms = _note_cdate_ms(note)
        if cdate_ms is None or cdate_ms < since_ms:
            continue

        source_id = adapter.make_source_id(note_id)
        if source_id in seen:
            continue
        seen.add(source_id)

        forum = note.get("forum") or note_id
        entries.append(
            ManifestIngestEntry(
                source_id=source_id,
                source=adapter.source,
                url=f"{OPENREVIEW_FORUM_BASE_URL}?id={forum}",
                title=title,
                abstract=_note_field(note, "abstract"),
                published_at=datetime.fromtimestamp(cdate_ms / 1000, tz=UTC),
                domain=adapter.domain,
            ),
        )

    return entries


class OpenReviewAdapter(SourceAdapter):
    """Fetches lightweight manifest rows from OpenReview's search API."""

    source = SourceEnum.OPENREVIEW
    domain = DomainEnum.PROFESSIONAL
    rate_limit = SOURCE_RATE_LIMITS[SourceEnum.OPENREVIEW.value]

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
        since_ms = int(effective_since.timestamp() * 1000)
        params = {
            "term": _SEARCH_TERM,
            "type": "terms",
            "content": "all",
            "group": "all",
            "source": "forum",
            "sort": "cdate:desc",
            "limit": _max_results_from_env(),
        }

        client = self._http_client or httpx.AsyncClient()
        try:
            await self._rate_limiter.acquire()
            response = await client.get(OPENREVIEW_SEARCH_API_URL, params=params)
            response.raise_for_status()
            payload = response.json()
            return parse_search_response(payload, adapter=self, since_ms=since_ms)
        finally:
            if self._owns_client:
                await client.aclose()

    async def fetch_content(self, entry: ManifestIngestEntry) -> str:
        """Compose title + abstract.

        Full PDF text extraction is out of scope for M8 T4 (would require a
        new PDF-parsing dependency, which needs orchestrator approval); the
        search API does not surface body text.
        """
        abstract = entry.abstract or ""
        return f"{entry.title}\n\n{abstract}"
