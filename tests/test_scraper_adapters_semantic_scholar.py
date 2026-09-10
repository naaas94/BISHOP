"""Unit tests for SemanticScholarAdapter (M8 T3)."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from bishop_shared.enums import DomainEnum, SourceEnum
from bishop_shared.scraper_config import BACKFILL_CONFIG

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRAPER_ROOT = _REPO_ROOT / "services" / "scraper"

_SINCE = datetime(2026, 6, 1, 0, 0, 0, tzinfo=UTC)
_UNTIL = datetime(2026, 7, 1, 12, 0, 0, tzinfo=UTC)

_SEARCH_FIXTURE = {
    "data": [
        {
            "paperId": "abc123def456",
            "title": "Example ML Paper",
            "abstract": "An example abstract.",
            "url": "https://www.semanticscholar.org/paper/abc123def456",
            "publicationDate": "2026-06-15",
        },
        {
            "paperId": "xyz789",
            "title": "Second Paper",
            "publicationDate": "2026-06-20T08:00:00Z",
        },
    ],
}

_PAPER_DETAIL_FIXTURE = {
    "title": "Example ML Paper",
    "abstract": "An example abstract.",
    "tldr": {"text": "A short summary."},
}


def _load_semantic_scholar_stack() -> ModuleType:
    """Load scraper semantic_scholar adapter without shadowing state-worker ``app``."""
    saved_app_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "app" or name.startswith("app.")
    }
    for name in saved_app_modules:
        del sys.modules[name]

    repo_str = str(_REPO_ROOT)
    scraper_str = str(_SCRAPER_ROOT)
    path_state: list[str] = []
    for path_str in (scraper_str, repo_str):
        if path_str not in sys.path:
            sys.path.insert(0, path_str)
            path_state.append(path_str)

    try:
        import app.adapters.semantic_scholar as semantic_scholar  # noqa: WPS433
        import app.models as models  # noqa: WPS433
        semantic_scholar.ManifestIngestEntry = models.ManifestIngestEntry  # type: ignore[attr-defined]
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.modules.update(saved_app_modules)
        for path_str in path_state:
            sys.path.remove(path_str)

    return semantic_scholar


def test_make_source_id() -> None:
    ss = _load_semantic_scholar_stack()
    adapter = ss.SemanticScholarAdapter()
    assert adapter.make_source_id("abc123") == "semantic_scholar:abc123"


def test_resolve_effective_since_uses_backfill_window() -> None:
    ss = _load_semantic_scholar_stack()
    now = datetime(2026, 7, 1, 12, 0, 0, tzinfo=UTC)
    resolved = ss.resolve_effective_since(None, now=now)
    expected = now - __import__("datetime").timedelta(
        days=BACKFILL_CONFIG["semantic_scholar"].window_days,
    )
    assert resolved == expected


def test_parse_search_response_maps_manifest_fields() -> None:
    ss = _load_semantic_scholar_stack()
    adapter = ss.SemanticScholarAdapter()
    entries = ss.parse_search_response(_SEARCH_FIXTURE, adapter=adapter)

    assert len(entries) == 2
    first = entries[0]
    assert first.source_id == "semantic_scholar:abc123def456"
    assert first.source == SourceEnum.SEMANTIC_SCHOLAR
    assert first.domain == DomainEnum.PROFESSIONAL
    assert first.title == "Example ML Paper"
    assert first.abstract == "An example abstract."
    assert first.published_at == datetime(2026, 6, 15, 0, 0, 0, tzinfo=UTC)

    second = entries[1]
    assert second.source_id == "semantic_scholar:xyz789"
    assert second.abstract is None


@pytest.mark.asyncio
async def test_fetch_manifest_sends_api_key_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ss = _load_semantic_scholar_stack()
    captured: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["api_key"] = request.headers.get("x-api-key")
        return httpx.Response(200, json=_SEARCH_FIXTURE)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = ss.SemanticScholarAdapter(http_client=client)
        monkeypatch.setattr(ss, "SEMANTIC_SCHOLAR_API_KEY", "test-ss-key")
        monkeypatch.setattr(
            ss,
            "datetime",
            type(
                "FrozenDateTime",
                (datetime,),
                {"now": classmethod(lambda cls, tz=None: _UNTIL)},
            ),
        )
        entries = await adapter.fetch_manifest(since=_SINCE)

    assert len(entries) == 2
    assert captured["api_key"] == "test-ss-key"


@pytest.mark.asyncio
async def test_fetch_manifest_builds_search_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ss = _load_semantic_scholar_stack()
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"data": []})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = ss.SemanticScholarAdapter(http_client=client)
        monkeypatch.setattr(ss, "SEMANTIC_SCHOLAR_API_KEY", None)
        monkeypatch.setattr(
            ss,
            "datetime",
            type(
                "FrozenDateTime",
                (datetime,),
                {"now": classmethod(lambda cls, tz=None: _UNTIL)},
            ),
        )
        await adapter.fetch_manifest(since=_SINCE)

    parsed = urlparse(captured["url"])
    assert parsed.netloc == "api.semanticscholar.org"
    assert parsed.path == "/graph/v1/paper/search"
    params = parse_qs(parsed.query)
    assert "publicationDateOrYear" in params
    assert params["publicationDateOrYear"][0].startswith("2026-06-01:")


@pytest.mark.asyncio
async def test_fetch_content_returns_paper_fields() -> None:
    ss = _load_semantic_scholar_stack()

    def handler(request: httpx.Request) -> httpx.Response:
        assert "/paper/abc123def456" in str(request.url)
        return httpx.Response(200, json=_PAPER_DETAIL_FIXTURE)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = ss.SemanticScholarAdapter(http_client=client)
        entry = ss.ManifestIngestEntry(
            source_id="semantic_scholar:abc123def456",
            source=SourceEnum.SEMANTIC_SCHOLAR,
            url="https://www.semanticscholar.org/paper/abc123def456",
            title="Example ML Paper",
            domain=DomainEnum.PROFESSIONAL,
        )
        content = await adapter.fetch_content(entry)

    assert "Example ML Paper" in content
    assert "An example abstract." in content
    assert "A short summary." in content


@pytest.mark.asyncio
async def test_fetch_content_falls_back_when_paper_missing() -> None:
    ss = _load_semantic_scholar_stack()

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = ss.SemanticScholarAdapter(http_client=client)
        entry = ss.ManifestIngestEntry(
            source_id="semantic_scholar:missing",
            source=SourceEnum.SEMANTIC_SCHOLAR,
            url="https://example.com",
            title="Missing Paper",
            abstract="Fallback abstract.",
            domain=DomainEnum.PROFESSIONAL,
        )
        content = await adapter.fetch_content(entry)

    assert content == "Missing Paper\n\nFallback abstract."


def test_parse_search_response_empty_payload_returns_empty_list() -> None:
    ss = _load_semantic_scholar_stack()
    adapter = ss.SemanticScholarAdapter()
    assert ss.parse_search_response({}, adapter=adapter) == []
