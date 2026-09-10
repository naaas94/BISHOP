"""LessWrong manifest adapter — GraphQL API (M8 T4, spec §3.1 / §23 flag 3).

Context-map ambiguity flag 3 resolution: probe the LessWrong GraphQL API
before implementing; implement the adapter only if the probe succeeds,
otherwise omit it from the registry with a documented waiver.

**Probe result (live-probed 2026-09-10): SUCCEEDED.** See
``.dev/decision-logs/m8-hardening-scale/T4-openreview-lesswrong.md`` for the
full transcript. Key finding: ``POST https://www.lesswrong.com/graphql``
returns HTTP 500 with an empty body for every query shape tried (including
a bare ``{ __typename }`` introspection query, with and without an
``apollo-require-preflight`` header) — this looks like a CSRF/preflight
rejection on the host, not an API outage. ``GET`` requests with ``query`` /
``variables`` in the querystring return HTTP 200 with well-formed GraphQL
JSON for both the ``posts`` list query and a single-post ``contents.html``
query. This adapter therefore issues **GET only**, never POST.

Because the probe succeeded, this adapter is implemented in full. Whether it
is registered in ``ADAPTER_REGISTRY`` is T8's call (T8 is the sole
``ADAPTER_REGISTRY`` merger per §2); this module and its decision log record
the probe evidence T8 needs to make that call.
"""

from __future__ import annotations

import html as html_module
import json
import logging
import os
import re
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from bishop_shared.enums import DomainEnum, SourceEnum

from app.adapters.base import SourceAdapter
from app.models import ManifestIngestEntry
from app.rate_limit import SOURCE_RATE_LIMITS, TokenBucketRateLimiter

logger = logging.getLogger(__name__)

LESSWRONG_GRAPHQL_URL = "https://www.lesswrong.com/graphql"
LESSWRONG_PROBE_EVENT = "lesswrong_adapter_probe"

_POSTS_QUERY = (
    "query($after: String, $limit: Int) { "
    'posts(input: {terms: {view: "new", limit: $limit, after: $after}}) { '
    "results { _id title postedAt pageUrl } } }"
)

_POST_CONTENT_QUERY = (
    "query($postId: String) { "
    "post(input: {selector: {_id: $postId}}) { "
    "result { _id title contents { html } } } }"
)

_DEFAULT_SINCE_DAYS = 7


def _max_results_from_env() -> int:
    raw = os.environ.get("BISHOP_LESSWRONG_MAX_RESULTS")
    if raw is None:
        return 50
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


def build_graphql_get_params(query: str, variables: dict[str, Any]) -> dict[str, str]:
    """Build GraphQL-over-GET query params.

    ``POST`` to this host returns HTTP 500 with an empty body (probed
    2026-09-10); ``GET`` with ``query``/``variables`` in the querystring is
    the only shape that returns a real GraphQL response.
    """
    return {"query": query, "variables": json.dumps(variables)}


async def probe_lesswrong_api(*, http_client: httpx.AsyncClient) -> bool:
    """Live probe: GET a minimal introspection query; True iff a schema comes back."""
    params = build_graphql_get_params("{ __schema { queryType { name } } }", {})
    try:
        response = await http_client.get(LESSWRONG_GRAPHQL_URL, params=params)
    except httpx.HTTPError:
        return False
    if response.status_code != 200:
        return False
    try:
        payload = response.json()
    except ValueError:
        return False
    schema = payload.get("data", {}).get("__schema") if isinstance(payload.get("data"), dict) else None
    if not isinstance(schema, dict):
        return False
    return bool(schema.get("queryType"))


def _parse_posted_at(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def parse_posts_response(
    payload: dict[str, Any],
    *,
    adapter: "LessWrongAdapter",
) -> list[ManifestIngestEntry]:
    """Map the ``posts`` GraphQL response to manifest DTOs."""
    entries: list[ManifestIngestEntry] = []
    seen: set[str] = set()

    data = payload.get("data")
    results = (
        data.get("posts", {}).get("results", [])
        if isinstance(data, dict) and isinstance(data.get("posts"), dict)
        else []
    )

    for post in results:
        post_id = post.get("_id")
        title = post.get("title")
        if not post_id or not title:
            continue

        source_id = adapter.make_source_id(post_id)
        if source_id in seen:
            continue
        seen.add(source_id)

        entries.append(
            ManifestIngestEntry(
                source_id=source_id,
                source=adapter.source,
                url=post.get("pageUrl") or f"https://www.lesswrong.com/posts/{post_id}",
                title=title,
                abstract=None,
                published_at=_parse_posted_at(post.get("postedAt")),
                domain=adapter.domain,
            ),
        )

    return entries


def strip_html_to_text(markup: str) -> str:
    """Strip HTML markup to plain text using stdlib only (no new dependency)."""
    without_tags = re.sub(r"<[^>]+>", " ", markup)
    unescaped = html_module.unescape(without_tags)
    return re.sub(r"\s+", " ", unescaped).strip()


class LessWrongAdapter(SourceAdapter):
    """Fetches lightweight manifest rows from the LessWrong GraphQL API (GET-only)."""

    source = SourceEnum.LESSWRONG
    domain = DomainEnum.PROFESSIONAL
    rate_limit = SOURCE_RATE_LIMITS[SourceEnum.LESSWRONG.value]

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
        params = build_graphql_get_params(
            _POSTS_QUERY,
            {"after": effective_since.isoformat(), "limit": _max_results_from_env()},
        )

        client = self._http_client or httpx.AsyncClient()
        try:
            await self._rate_limiter.acquire()
            response = await client.get(LESSWRONG_GRAPHQL_URL, params=params)
            response.raise_for_status()
            payload = response.json()
            return parse_posts_response(payload, adapter=self)
        finally:
            if self._owns_client:
                await client.aclose()

    async def fetch_content(self, entry: ManifestIngestEntry) -> str:
        raw_id = entry.source_id.split(":", 1)[1] if ":" in entry.source_id else entry.source_id
        params = build_graphql_get_params(_POST_CONTENT_QUERY, {"postId": raw_id})

        client = self._http_client or httpx.AsyncClient()
        try:
            await self._rate_limiter.acquire()
            response = await client.get(LESSWRONG_GRAPHQL_URL, params=params)
            response.raise_for_status()
            payload = response.json()
        finally:
            if self._owns_client:
                await client.aclose()

        data = payload.get("data")
        post = data.get("post") if isinstance(data, dict) else None
        result = post.get("result") if isinstance(post, dict) else None
        contents = result.get("contents") if isinstance(result, dict) else None
        html_body = contents.get("html") if isinstance(contents, dict) else None

        if isinstance(html_body, str):
            text = strip_html_to_text(html_body)
            if text:
                return text
        return entry.title
