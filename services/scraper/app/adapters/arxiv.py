"""ArXiv manifest adapter — Atom export API (plan flag 2 / §10.1)."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import ssl
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from xml.etree import ElementTree as ET

import httpx

from bishop_shared.enums import DomainEnum, SourceEnum
from bishop_shared.source_config import SourceCategoryConfig, load_source_config

from app.adapters.base import SourceAdapter
from app.config import ARXIV_BACKFILL_WINDOW_DAYS, ARXIV_CATEGORIES
from app.exceptions import PermanentFailureError
from app.models import ManifestIngestEntry
from app.rate_limit import SOURCE_RATE_LIMITS, TokenBucketRateLimiter

logger = logging.getLogger(__name__)

ARXIV_EXPORT_API_URL = "https://export.arxiv.org/api/query"
ARXIV_HTML_BASE_URL = "https://arxiv.org/html"

ATOM_NS = "http://www.w3.org/2005/Atom"
_ATOM = f"{{{ATOM_NS}}}"

ARXIV_SCHEMA_NS = "http://arxiv.org/schemas/atom"
_ARXIV = f"{{{ARXIV_SCHEMA_NS}}}"

CATEGORY_GATE_EVENT = "arxiv_category_gate"

# export.arxiv.org sits behind Fastly. OpenSSL 3.5's default handshake (the
# scraper image) is answered with an empty 406 and never reaches arXiv.
# Capping this client at TLS 1.2 is what Fastly forwards. Other adapters stay
# on the default handshake.
ARXIV_INTER_PAGE_DELAY_SEC = 3.0
# export API will not return past this many hits for one query. A window that
# is still full here must not look finished — the scrape loop would stamp the
# cursor to now and drop the tail.
ARXIV_EXPORT_RESULT_CAP = 30_000

OPENSEARCH_NS = "http://a9.com/-/spec/opensearch/1.1/"
_OPENSEARCH = f"{{{OPENSEARCH_NS}}}"

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


def extract_primary_category(entry: ET.Element) -> str | None:
    """Read the ArXiv-schema ``primary_category`` term, or None when absent."""
    primary = entry.find(f"{_ARXIV}primary_category")
    if primary is None:
        return None
    term = primary.get("term")
    return term or None


def parse_atom_feed_with_categories(
    xml: bytes | str,
    *,
    adapter: SourceAdapter,
) -> list[tuple[ManifestIngestEntry, str | None]]:
    """Map Atom export XML to ``(manifest DTO, primary category)`` pairs.

    The primary category is carried alongside rather than on
    ``ManifestIngestEntry`` because it is gate-local: it never reaches the
    state-worker wire and has no persisted column.
    """
    root = ET.fromstring(xml)
    seen: set[str] = set()
    entries: list[tuple[ManifestIngestEntry, str | None]] = []

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
            (
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
                extract_primary_category(entry),
            ),
        )

    return entries


def parse_atom_feed(xml: bytes | str, *, adapter: SourceAdapter) -> list[ManifestIngestEntry]:
    """Map Atom export XML to manifest ingest DTOs."""
    return [entry for entry, _category in parse_atom_feed_with_categories(xml, adapter=adapter)]


def export_feed_bounds(xml: bytes | str) -> tuple[int, int | None]:
    """Raw Atom entry count and ``opensearch:totalResults``, if the feed has it.

    Pagination stops on the raw entry count. The category gate runs later, so a
    page that the gate would shrink must not look like the last page.
    """
    root = ET.fromstring(xml)
    entry_count = len(root.findall(f"{_ATOM}entry"))
    total_el = root.find(f"{_OPENSEARCH}totalResults")
    if total_el is None or not total_el.text or not total_el.text.strip().isdigit():
        return entry_count, None
    return entry_count, int(total_el.text.strip())


def arxiv_export_ssl_context() -> ssl.SSLContext:
    """SSL context Fastly will forward to the export API."""
    ctx = httpx.create_ssl_context()
    ctx.maximum_version = ssl.TLSVersion.TLSv1_2
    return ctx


def apply_category_gate(
    pairs: list[tuple[ManifestIngestEntry, str | None]],
    config: SourceCategoryConfig | None,
) -> tuple[list[ManifestIngestEntry], int]:
    """Return kept entries and the count the gate would skip.

    When ``config`` is absent or ``enforce`` is false, every entry is kept and
    only the count is reported — the knob is measurable before it is
    load-bearing.
    """
    entries = [entry for entry, _category in pairs]
    if config is None:
        return entries, 0

    skipped = sum(1 for _entry, category in pairs if not config.allows(category))
    if not config.enforce:
        return entries, skipped

    kept = [entry for entry, category in pairs if config.allows(category)]
    return kept, skipped


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
    # Scrape loop walks one UTC calendar day at a time and stamps the end of
    # that day. A single fetch through "now" would skip every day it did not
    # finish and leave the cursor on today.
    walks_calendar_days = True

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._http_client = http_client
        self._owns_client = http_client is None
        self._rate_limiter = TokenBucketRateLimiter(self.rate_limit)

    async def fetch_manifest(
        self,
        since: datetime | None = None,
        *,
        until: datetime | None = None,
    ) -> list[ManifestIngestEntry]:
        now = datetime.now(UTC)
        effective_since = resolve_effective_since(since, now=now)
        effective_until = until if until is not None else now
        search_query = build_search_query(
            ARXIV_CATEGORIES,
            effective_since,
            effective_until,
        )
        page_size = _max_results_from_env()

        client = self._http_client or httpx.AsyncClient(
            verify=arxiv_export_ssl_context(),
            timeout=httpx.Timeout(60.0),
        )
        try:
            pairs = await self._page_export(client, search_query, page_size)
            return self._gate_by_category(pairs)
        finally:
            if self._owns_client:
                await client.aclose()

    async def _page_export(
        self,
        client: httpx.AsyncClient,
        search_query: str,
        page_size: int,
    ) -> list[tuple[ManifestIngestEntry, str | None]]:
        """Read every page of one submittedDate window before returning.

        A later-page failure raises, so the scrape loop does not stamp
        ``last_successful_run_at``. Pages are submittedDate-ascending so the
        offset does not shuffle. arXiv asks for about 3s between export calls.
        """
        start = 0
        seen: set[str] = set()
        collected: list[tuple[ManifestIngestEntry, str | None]] = []
        while True:
            if start > 0 and ARXIV_INTER_PAGE_DELAY_SEC > 0:
                await asyncio.sleep(ARXIV_INTER_PAGE_DELAY_SEC)
            await self._rate_limiter.acquire()
            response = await client.get(
                ARXIV_EXPORT_API_URL,
                params={
                    "search_query": search_query,
                    "start": start,
                    "max_results": page_size,
                    "sortBy": "submittedDate",
                    "sortOrder": "ascending",
                },
            )
            response.raise_for_status()
            entry_count, total = export_feed_bounds(response.content)
            for pair in parse_atom_feed_with_categories(response.content, adapter=self):
                source_id = pair[0].source_id
                if source_id in seen:
                    continue
                seen.add(source_id)
                collected.append(pair)
            next_start = start + page_size
            if entry_count < page_size:
                return collected
            if total is not None and next_start >= total:
                return collected
            if next_start >= ARXIV_EXPORT_RESULT_CAP:
                raise PermanentFailureError(
                    self.source,
                    None,
                    RuntimeError(
                        "arxiv export window exceeds "
                        f"{ARXIV_EXPORT_RESULT_CAP} results "
                        f"(fetched through start={start}, total={total})"
                    ),
                )
            start = next_start

    def _gate_by_category(
        self,
        pairs: list[tuple[ManifestIngestEntry, str | None]],
    ) -> list[ManifestIngestEntry]:
        """Apply the primary-category gate and log the per-cycle skip count."""
        config = load_source_config(self.source.value)
        entries, skipped = apply_category_gate(pairs, config)
        logger.info(
            "arxiv category gate evaluated",
            extra={
                "event": CATEGORY_GATE_EVENT,
                "source": self.source.value,
                "config_version": config.version if config is not None else None,
                "enforce": config.enforce if config is not None else False,
                "fetched": len(pairs),
                "skipped_by_category": skipped,
                "kept": len(entries),
            },
        )
        return entries

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
