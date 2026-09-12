"""Unit tests for PapersWithCodeAdapter REST API v1 (M8 T2)."""

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
_NOW = datetime(2026, 6, 12, 12, 0, 0, tzinfo=UTC)

_PWC_LIST_FIXTURE = {
    "count": 2,
    "next": None,
    "previous": None,
    "results": [
        {
            "id": "fresh-paper-slug",
            "title": "Fresh Paper",
            "abstract": "  New results.  ",
            "url_abs": "https://arxiv.org/abs/2606.00001",
            "published": "2026-06-10",
        },
        {
            "id": "stale-paper-slug",
            "title": "Stale Paper",
            "abstract": "Old work.",
            "url_abs": "https://arxiv.org/abs/2501.00001",
            "published": "2025-01-01",
        },
    ],
}


def _load_pwc_stack() -> ModuleType:
    """Load scraper paperswithcode adapter without shadowing state-worker ``app``."""
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
        import app.adapters.paperswithcode as paperswithcode  # noqa: WPS433
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.modules.update(saved_app_modules)
        for path_str in path_state:
            sys.path.remove(path_str)

    return paperswithcode


def test_resolve_effective_since_uses_backfill_config() -> None:
    pwc = _load_pwc_stack()
    resolved = pwc.resolve_effective_since(None, now=_NOW)
    window_days = BACKFILL_CONFIG[SourceEnum.PAPERSWITHCODE.value].window_days
    assert resolved == _NOW - __import__("datetime").timedelta(days=window_days)


def test_parse_papers_page_filters_by_since_and_maps_fields() -> None:
    pwc = _load_pwc_stack()
    adapter = pwc.PapersWithCodeAdapter()
    entries = pwc.parse_papers_page(_PWC_LIST_FIXTURE, adapter=adapter, since=_SINCE)

    assert len(entries) == 1
    entry = entries[0]
    assert entry.source_id == "paperswithcode:fresh-paper-slug"
    assert entry.source == SourceEnum.PAPERSWITHCODE
    assert entry.domain == DomainEnum.PROFESSIONAL
    assert entry.url == "https://arxiv.org/abs/2606.00001"
    assert entry.title == "Fresh Paper"
    assert entry.abstract == "New results."
    assert entry.published_at == datetime(2026, 6, 10, 0, 0, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_fetch_manifest_calls_papers_list_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pwc = _load_pwc_stack()
    captured_url = ""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_url
        captured_url = str(request.url)
        return httpx.Response(200, json=_PWC_LIST_FIXTURE)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = pwc.PapersWithCodeAdapter(http_client=client)
        monkeypatch.setattr(
            pwc,
            "datetime",
            type(
                "FrozenDateTime",
                (datetime,),
                {"now": classmethod(lambda cls, tz=None: _NOW)},
            ),
        )
        entries = await adapter.fetch_manifest(since=_SINCE)

    parsed = urlparse(captured_url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "paperswithcode.com"
    assert parsed.path == "/api/v1/papers/"
    params = parse_qs(parsed.query)
    assert params["page"] == ["1"]
    assert params["items_per_page"] == ["50"]
    assert len(entries) == 1
    assert entries[0].source_id == "paperswithcode:fresh-paper-slug"


@pytest.mark.asyncio
async def test_fetch_manifest_skips_when_api_redirects() -> None:
    pwc = _load_pwc_stack()

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            302,
            headers={"Location": "https://huggingface.co/papers/trending"},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = pwc.PapersWithCodeAdapter(http_client=client)
        entries = await adapter.fetch_manifest(since=_SINCE)

    assert entries == []


def _manifest_entry(**kwargs: object):
    saved_app_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "app" or name.startswith("app.")
    }
    for name in saved_app_modules:
        del sys.modules[name]
    repo_str = str(_REPO_ROOT)
    scraper_str = str(_SCRAPER_ROOT)
    for path_str in (scraper_str, repo_str):
        if path_str not in sys.path:
            sys.path.insert(0, path_str)
    try:
        from app.models import ManifestIngestEntry  # noqa: WPS433

        return ManifestIngestEntry(**kwargs)
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.modules.update(saved_app_modules)


@pytest.mark.asyncio
async def test_fetch_content_uses_detail_endpoint_or_fallback() -> None:
    pwc = _load_pwc_stack()
    entry = _manifest_entry(
        source_id="paperswithcode:fresh-paper-slug",
        source=SourceEnum.PAPERSWITHCODE,
        url="https://arxiv.org/abs/2606.00001",
        title="Fresh Paper",
        abstract="Fallback abstract",
        domain=DomainEnum.PROFESSIONAL,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/papers/fresh-paper-slug/"):
            return httpx.Response(
                200,
                json={
                    "id": "fresh-paper-slug",
                    "title": "Fresh Paper",
                    "abstract": "Detailed abstract.",
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = pwc.PapersWithCodeAdapter(http_client=client)
        content = await adapter.fetch_content(entry)

    assert content == "Fresh Paper\n\nDetailed abstract."


@pytest.mark.asyncio
async def test_fetch_content_falls_back_when_detail_missing() -> None:
    pwc = _load_pwc_stack()
    entry = _manifest_entry(
        source_id="paperswithcode:fresh-paper-slug",
        source=SourceEnum.PAPERSWITHCODE,
        url="https://arxiv.org/abs/2606.00001",
        title="Fresh Paper",
        abstract="Fallback abstract",
        domain=DomainEnum.PROFESSIONAL,
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = pwc.PapersWithCodeAdapter(http_client=client)
        content = await adapter.fetch_content(entry)

    assert content == "Fresh Paper\n\nFallback abstract"


def test_parse_papers_page_since_filter_falsifier() -> None:
    """Mutation-checked: dropping the since guard would keep stale-paper-slug."""
    pwc = _load_pwc_stack()
    adapter = pwc.PapersWithCodeAdapter()
    entries = pwc.parse_papers_page(_PWC_LIST_FIXTURE, adapter=adapter, since=_SINCE)
    source_ids = {entry.source_id for entry in entries}
    assert "paperswithcode:stale-paper-slug" not in source_ids
