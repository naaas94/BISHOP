"""ArXiv manifest adapter — Atom export API (plan flag 2 / §10.1)."""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from xml.etree import ElementTree as ET

import httpx

from bishop_shared.enums import DomainEnum, SourceEnum

from app.adapters.base import SourceAdapter
from app.config import ARXIV_BACKFILL_WINDOW_DAYS, ARXIV_CATEGORIES
from app.models import ManifestIngestEntry
from app.rate_limit import SOURCE_RATE_LIMITS, TokenBucketRateLimiter

ARXIV_EXPORT_API_URL = "http://export.arxiv.org/api/query"
ARXIV_HTML_BASE_URL = "https://arxiv.org/html"

ATOM_NS = "http://www.w3.org/2005/Atom"
_ATOM = f"{{{ATOM_NS}}}"

_ARXIV_ID_VERSION_RE = re.compile(r"^(.+?)v\d+$")


def _max_results_from_env() -> int:
    raw = os.environ.get("BISHOP_ARXIV_MAX_RESULTS")
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
    return now - timedelta(days=ARXIV_BACKFILL_WINDOW_DAYS)


def _format_submitted_date(dt: datetime) -> str:
    """Format datetime for ArXiv ``submittedDate`` range (UTC, YYYYMMDDHHMMSS)."""
    utc = dt.astimezone(UTC)
    return utc.strftime("%Y%m%d%H%M%S")


def build_search_query(
    categories: tuple[str, ...],
    since: datetime,
    until: datetime,
) -> str:
    """Build Atom API ``search_query`` with category union and submittedDate range."""
    cat_clause = " OR ".join(f"cat:{category}" for category in categories)
    if len(categories) > 1:
        cat_clause = f"({cat_clause})"
    start = _format_submitted_date(since.replace(hour=0, minute=0, second=0, microsecond=0))
    end = _format_submitted_date(
        until.replace(hour=23, minute=59, second=59, microsecond=0),
    )
    return f"{cat_clause} AND submittedDate:[{start} TO {end}]"


def _extract_raw_id(entry_id: str) -> str:
    """Strip ArXiv version suffix from Atom entry id URL."""
    path = entry_id.rstrip("/").rsplit("/", 1)[-1]
    match = _ARXIV_ID_VERSION_RE.match(path)
    if match:
        return match.group(1)
    return path


def _entry_link_url(entry: ET.Element) -> str | None:
    for link in entry.findall(f"{_ATOM}link"):
        rel = link.get("rel")
        href = link.get("href")
        if href and rel in (None, "alternate"):
            return href
    return None


def _parse_published(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def parse_atom_feed(xml: bytes | str, *, adapter: SourceAdapter) -> list[ManifestIngestEntry]:
    """Map Atom export XML to manifest ingest DTOs."""
    root = ET.fromstring(xml)
    seen: set[str] = set()
    entries: list[ManifestIngestEntry] = []

    for entry in root.findall(f"{_ATOM}entry"):
        entry_id_el = entry.find(f"{_ATOM}id")
        title_el = entry.find(f"{_ATOM}title")
        if entry_id_el is None or entry_id_el.text is None:
            continue
        if title_el is None or title_el.text is None:
            continue

        raw_id = _extract_raw_id(entry_id_el.text.strip())
        source_id = adapter.make_source_id(raw_id)
        if source_id in seen:
            continue
        seen.add(source_id)

        summary_el = entry.find(f"{_ATOM}summary")
        published_el = entry.find(f"{_ATOM}published")
        url = _entry_link_url(entry) or f"http://arxiv.org/abs/{raw_id}"

        entries.append(
            ManifestIngestEntry(
                source_id=source_id,
                source=adapter.source,
                url=url,
                title=" ".join(title_el.text.split()),
                abstract=(
                    " ".join(summary_el.text.split())
                    if summary_el is not None and summary_el.text
                    else None
                ),
                published_at=_parse_published(
                    published_el.text.strip()
                    if published_el is not None and published_el.text
                    else None,
                ),
                domain=adapter.domain,
            ),
        )

    return entries


def parse_raw_id_from_source_id(source_id: str) -> str:
    """Extract ArXiv raw id from canonical ``source_name:raw_id`` form."""
    if ":" in source_id:
        return source_id.split(":", 1)[1]
    return source_id


class _HTMLTextExtractor(HTMLParser):
    """Collect visible text from HTML, skipping script/style blocks."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self._skip_depth += 1
        elif self._skip_depth == 0 and tag in ("p", "div", "br", "li", "h1", "h2", "h3", "tr"):
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._parts.append(data)

    def get_text(self) -> str:
        raw = "".join(self._parts)
        return re.sub(r"\s+", " ", raw).strip()


def strip_html_to_text(html: str) -> str:
    """Strip HTML markup to plain text using stdlib only."""
    parser = _HTMLTextExtractor()
    parser.feed(html)
    return parser.get_text()


def compose_fallback_content(entry: ManifestIngestEntry) -> str:
    """Compose title + abstract when HTML full-text is unavailable."""
    abstract = entry.abstract or ""
    return f"{entry.title}\n\n{abstract}"


async def fetch_arxiv_html_text(
    raw_id: str,
    *,
    http_client: httpx.AsyncClient,
) -> str | None:
    """GET ArXiv HTML endpoint and return stripped text, or None if unusable."""
    url = f"{ARXIV_HTML_BASE_URL}/{raw_id}"
    response = await http_client.get(url)
    if response.status_code < 200 or response.status_code >= 300:
        return None
    text = strip_html_to_text(response.text)
    if not text:
        return None
    return text


class ArxivAdapter(SourceAdapter):
    """Fetches lightweight manifest rows from the ArXiv Atom export API."""

    source = SourceEnum.ARXIV
    domain = DomainEnum.PROFESSIONAL
    rate_limit = SOURCE_RATE_LIMITS[SourceEnum.ARXIV.value]

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
        search_query = build_search_query(ARXIV_CATEGORIES, effective_since, now)
        params = {
            "search_query": search_query,
            "max_results": _max_results_from_env(),
        }

        client = self._http_client or httpx.AsyncClient()
        try:
            await self._rate_limiter.acquire()
            response = await client.get(ARXIV_EXPORT_API_URL, params=params)
            response.raise_for_status()
            return parse_atom_feed(response.content, adapter=self)
        finally:
            if self._owns_client:
                await client.aclose()

    async def fetch_content(self, entry: ManifestIngestEntry) -> str:
        raw_id = parse_raw_id_from_source_id(entry.source_id)
        client = self._http_client or httpx.AsyncClient()
        try:
            await self._rate_limiter.acquire()
            html_text = await fetch_arxiv_html_text(raw_id, http_client=client)
            if html_text is not None:
                return html_text
            return compose_fallback_content(entry)
        finally:
            if self._owns_client:
                await client.aclose()
