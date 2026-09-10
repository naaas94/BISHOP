"""Unit tests for OpenReviewAdapter (M8 T4)."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from bishop_shared.enums import DomainEnum, SourceEnum

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRAPER_ROOT = _REPO_ROOT / "services" / "scraper"

_SINCE = datetime(2026, 6, 5, 0, 0, 0, tzinfo=UTC)
_UNTIL = datetime(2026, 6, 12, 15, 30, 0, tzinfo=UTC)
_SINCE_MS = int(_SINCE.timestamp() * 1000)


def _load_openreview_stack() -> ModuleType:
    """Load scraper openreview adapter without shadowing state-worker ``app``."""
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
        import app.adapters.openreview as openreview  # noqa: WPS433
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.modules.update(saved_app_modules)
        for path_str in path_state:
            sys.path.remove(path_str)

    return openreview


def _note(note_id: str, *, cdate_ms: int, title: str, abstract: str | None, forum: str | None = None) -> dict:
    content: dict = {"title": {"value": title}}
    if abstract is not None:
        content["abstract"] = {"value": abstract}
    return {
        "id": note_id,
        "forum": forum or note_id,
        "cdate": cdate_ms,
        "content": content,
    }


def test_make_source_id() -> None:
    openreview = _load_openreview_stack()
    adapter = openreview.OpenReviewAdapter()
    assert adapter.make_source_id("abc123") == "openreview:abc123"


def test_resolve_effective_since_default_window() -> None:
    openreview = _load_openreview_stack()
    now = datetime(2026, 6, 12, 12, 0, 0, tzinfo=UTC)
    resolved = openreview.resolve_effective_since(None, now=now)
    assert resolved == datetime(2026, 6, 5, 12, 0, 0, tzinfo=UTC)


def test_resolve_effective_since_preserves_incremental_since() -> None:
    openreview = _load_openreview_stack()
    since = datetime(2026, 6, 1, 0, 0, 0, tzinfo=UTC)
    now = datetime(2026, 6, 12, 0, 0, 0, tzinfo=UTC)
    assert openreview.resolve_effective_since(since, now=now) == since


def test_parse_search_response_maps_manifest_fields_and_filters_by_since() -> None:
    openreview = _load_openreview_stack()
    adapter = openreview.OpenReviewAdapter()
    payload = {
        "notes": [
            _note("aaa111", cdate_ms=_SINCE_MS + 3600_000, title="New Paper", abstract="An abstract."),
            _note("bbb222", cdate_ms=_SINCE_MS - 3600_000, title="Old Paper", abstract="stale"),
        ],
    }

    entries = openreview.parse_search_response(payload, adapter=adapter, since_ms=_SINCE_MS)

    assert len(entries) == 1
    entry = entries[0]
    assert entry.source_id == "openreview:aaa111"
    assert entry.source == SourceEnum.OPENREVIEW
    assert entry.domain == DomainEnum.PROFESSIONAL
    assert entry.title == "New Paper"
    assert entry.abstract == "An abstract."
    assert entry.url == "https://openreview.net/forum?id=aaa111"


def test_parse_search_response_dedupes_by_source_id() -> None:
    openreview = _load_openreview_stack()
    adapter = openreview.OpenReviewAdapter()
    note = _note("ccc333", cdate_ms=_SINCE_MS + 1000, title="Dup", abstract=None)
    payload = {"notes": [note, dict(note)]}

    entries = openreview.parse_search_response(payload, adapter=adapter, since_ms=_SINCE_MS)

    assert len(entries) == 1


def test_parse_search_response_skips_notes_missing_title_or_id() -> None:
    openreview = _load_openreview_stack()
    adapter = openreview.OpenReviewAdapter()
    payload = {
        "notes": [
            {"id": "no-title", "cdate": _SINCE_MS + 1000, "content": {}},
            {"cdate": _SINCE_MS + 1000, "content": {"title": {"value": "no id"}}},
        ],
    }

    entries = openreview.parse_search_response(payload, adapter=adapter, since_ms=_SINCE_MS)

    assert entries == []


@pytest.mark.asyncio
async def test_fetch_manifest_hits_declared_search_url_and_parses_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    openreview = _load_openreview_stack()
    captured: dict[str, str] = {}
    note = _note("ddd444", cdate_ms=_SINCE_MS + 1000, title="Fixture Paper", abstract="fixture abstract")

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"notes": [note]})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = openreview.OpenReviewAdapter(http_client=client)
        monkeypatch.setattr(
            openreview,
            "datetime",
            type(
                "FrozenDateTime",
                (datetime,),
                {"now": classmethod(lambda cls, tz=None: _UNTIL)},
            ),
        )
        entries = await adapter.fetch_manifest(since=_SINCE)

    assert len(entries) == 1
    assert entries[0].source_id == "openreview:ddd444"

    parsed = urlparse(captured["url"])
    assert parsed.scheme == "https"
    assert parsed.netloc == "api2.openreview.net"
    assert parsed.path == "/notes/search"
    params = parse_qs(parsed.query)
    assert params["term"] == ["machine learning"]
    assert params["sort"] == ["cdate:desc"]


@pytest.mark.asyncio
async def test_fetch_manifest_empty_notes_returns_empty_list() -> None:
    openreview = _load_openreview_stack()

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"notes": []})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = openreview.OpenReviewAdapter(http_client=client)
        entries = await adapter.fetch_manifest(since=_SINCE)

    assert entries == []


@pytest.mark.asyncio
async def test_fetch_content_composes_title_and_abstract() -> None:
    openreview = _load_openreview_stack()
    adapter = openreview.OpenReviewAdapter()

    entry = openreview.ManifestIngestEntry(
        source_id="openreview:eee555",
        source=SourceEnum.OPENREVIEW,
        url="https://openreview.net/forum?id=eee555",
        title="A Paper Title",
        abstract="A paper abstract.",
        domain=DomainEnum.PROFESSIONAL,
    )

    content = await adapter.fetch_content(entry)

    assert content == "A Paper Title\n\nA paper abstract."


def test_since_filter_is_load_bearing() -> None:
    """Falsifier for the since-date filter (§2.1 adversarial micro-pass).

    Failure mode: an off-by-one or unit mismatch (ms vs s) in the ``cdate``
    comparison silently lets stale notes leak into the manifest on every
    incremental cycle. This test pins the boundary: a note exactly at
    ``since_ms`` is kept, one 1ms older is dropped.
    """
    openreview = _load_openreview_stack()
    adapter = openreview.OpenReviewAdapter()
    boundary_note = _note("fff666", cdate_ms=_SINCE_MS, title="At boundary", abstract=None)
    stale_note = _note("ggg777", cdate_ms=_SINCE_MS - 1, title="Just stale", abstract=None)
    payload = {"notes": [boundary_note, stale_note]}

    entries = openreview.parse_search_response(payload, adapter=adapter, since_ms=_SINCE_MS)

    assert [entry.source_id for entry in entries] == ["openreview:fff666"]
