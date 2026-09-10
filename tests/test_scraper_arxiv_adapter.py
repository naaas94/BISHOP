"""Unit tests for ArxivAdapter Atom export API (M2 T4)."""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from bishop_shared.enums import DomainEnum, SourceEnum
from bishop_shared.source_config import SourceCategoryConfig

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRAPER_ROOT = _REPO_ROOT / "services" / "scraper"

_SINCE = datetime(2026, 6, 5, 0, 0, 0, tzinfo=UTC)
_UNTIL = datetime(2026, 6, 12, 15, 30, 0, tzinfo=UTC)

_ATOM_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2406.00001v1</id>
    <title>Example Paper Title</title>
    <summary>  An example abstract.  </summary>
    <published>2026-06-10T12:00:00Z</published>
    <link rel="alternate" href="http://arxiv.org/abs/2406.00001"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2406.00002v2</id>
    <title>Second Paper</title>
    <published>2026-06-11T08:00:00Z</published>
    <link rel="alternate" href="http://arxiv.org/abs/2406.00002"/>
  </entry>
</feed>
"""

_CATEGORY_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2406.00010v1</id>
    <title>On-Profile Systems Paper</title>
    <arxiv:primary_category term="cs.CL"/>
    <category term="cs.CL"/>
    <category term="cs.CV"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2406.00011v1</id>
    <title>Off-Profile Vision Paper</title>
    <arxiv:primary_category term="cs.CV"/>
    <category term="cs.CV"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2406.00012v1</id>
    <title>Paper Without Category Metadata</title>
  </entry>
</feed>
"""

_EMPTY_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
</feed>
"""


def _load_arxiv_stack() -> ModuleType:
    """Load scraper arxiv adapter without shadowing state-worker ``app`` in sys.modules."""
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
        import app.adapters.arxiv as arxiv  # noqa: WPS433
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.modules.update(saved_app_modules)
        for path_str in path_state:
            sys.path.remove(path_str)

    return arxiv


def test_make_source_id() -> None:
    arxiv = _load_arxiv_stack()
    adapter = arxiv.ArxivAdapter()
    assert adapter.make_source_id("2406.00001") == "arxiv:2406.00001"


def test_resolve_effective_since_uses_backfill_window() -> None:
    arxiv = _load_arxiv_stack()
    now = datetime(2026, 6, 12, 12, 0, 0, tzinfo=UTC)
    resolved = arxiv.resolve_effective_since(None, now=now)
    assert resolved == datetime(2026, 6, 5, 12, 0, 0, tzinfo=UTC)


def test_resolve_effective_since_preserves_incremental_since() -> None:
    arxiv = _load_arxiv_stack()
    since = datetime(2026, 6, 1, 0, 0, 0, tzinfo=UTC)
    now = datetime(2026, 6, 12, 0, 0, 0, tzinfo=UTC)
    assert arxiv.resolve_effective_since(since, now=now) == since


def test_build_search_query_includes_categories_and_date_range() -> None:
    arxiv = _load_arxiv_stack()
    query = arxiv.build_search_query(
        ("cs.AI", "cs.CL", "cs.LG"),
        _SINCE,
        _UNTIL,
    )
    assert "cat:cs.AI" in query
    assert "cat:cs.CL" in query
    assert "cat:cs.LG" in query
    assert "submittedDate:[20260605000000 TO 20260612235959]" in query


def test_parse_atom_feed_maps_manifest_fields() -> None:
    arxiv = _load_arxiv_stack()
    adapter = arxiv.ArxivAdapter()
    entries = arxiv.parse_atom_feed(_ATOM_FIXTURE, adapter=adapter)

    assert len(entries) == 2
    first = entries[0]
    assert first.source_id == "arxiv:2406.00001"
    assert first.source == SourceEnum.ARXIV
    assert first.domain == DomainEnum.PROFESSIONAL
    assert first.url == "http://arxiv.org/abs/2406.00001"
    assert first.title == "Example Paper Title"
    assert first.abstract == "An example abstract."
    assert first.published_at == datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)

    second = entries[1]
    assert second.source_id == "arxiv:2406.00002"
    assert second.abstract is None


@pytest.mark.asyncio
async def test_fetch_manifest_parses_fixture_atom_xml(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    arxiv = _load_arxiv_stack()
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, content=_ATOM_FIXTURE.encode())

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = arxiv.ArxivAdapter(http_client=client)
        monkeypatch.setattr(
            arxiv,
            "datetime",
            type(
                "FrozenDateTime",
                (datetime,),
                {"now": classmethod(lambda cls, tz=None: _UNTIL)},
            ),
        )
        entries = await adapter.fetch_manifest(since=_SINCE)

    assert len(entries) == 2
    assert all(entry.source_id.startswith("arxiv:") for entry in entries)
    assert all(entry.domain == DomainEnum.PROFESSIONAL for entry in entries)

    parsed = urlparse(captured["url"])
    assert parsed.scheme == "https"
    assert parsed.netloc == "export.arxiv.org"
    assert parsed.path == "/api/query"
    params = parse_qs(parsed.query)
    assert "search_query" in params
    assert "cat:cs.AI" in params["search_query"][0]
    assert params["max_results"] == ["100"]


@pytest.mark.asyncio
async def test_fetch_manifest_empty_feed_returns_empty_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    arxiv = _load_arxiv_stack()

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_EMPTY_FEED.encode())

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = arxiv.ArxivAdapter(http_client=client)
        monkeypatch.setattr(
            arxiv,
            "datetime",
            type(
                "FrozenDateTime",
                (datetime,),
                {"now": classmethod(lambda cls, tz=None: _UNTIL)},
            ),
        )
        entries = await adapter.fetch_manifest(since=_SINCE)

    assert entries == []


def test_extract_primary_category_reads_arxiv_schema_term() -> None:
    arxiv = _load_arxiv_stack()
    adapter = arxiv.ArxivAdapter()
    pairs = arxiv.parse_atom_feed_with_categories(_CATEGORY_FIXTURE, adapter=adapter)

    assert [category for _entry, category in pairs] == ["cs.CL", "cs.CV", None]


def test_category_gate_measures_without_enforcing() -> None:
    arxiv = _load_arxiv_stack()
    adapter = arxiv.ArxivAdapter()
    pairs = arxiv.parse_atom_feed_with_categories(_CATEGORY_FIXTURE, adapter=adapter)
    config = SourceCategoryConfig(
        version="test",
        exclude_categories=["cs.CV"],
        enforce=False,
    )

    entries, skipped = arxiv.apply_category_gate(pairs, config)

    assert skipped == 1
    assert len(entries) == 3


def test_category_gate_drops_excluded_primary_when_enforced() -> None:
    arxiv = _load_arxiv_stack()
    adapter = arxiv.ArxivAdapter()
    pairs = arxiv.parse_atom_feed_with_categories(_CATEGORY_FIXTURE, adapter=adapter)
    config = SourceCategoryConfig(
        version="test",
        exclude_categories=["cs.CV"],
        enforce=True,
    )

    entries, skipped = arxiv.apply_category_gate(pairs, config)

    assert skipped == 1
    assert [entry.source_id for entry in entries] == ["arxiv:2406.00010", "arxiv:2406.00012"]


def test_category_gate_matches_primary_not_cross_listings() -> None:
    """The on-profile cs.CL paper is cross-listed cs.CV and must survive."""
    arxiv = _load_arxiv_stack()
    adapter = arxiv.ArxivAdapter()
    pairs = arxiv.parse_atom_feed_with_categories(_CATEGORY_FIXTURE, adapter=adapter)
    config = SourceCategoryConfig(
        version="test",
        include_categories=["cs.*"],
        exclude_categories=["cs.CV"],
        enforce=True,
    )

    entries, _skipped = arxiv.apply_category_gate(pairs, config)

    assert "arxiv:2406.00010" in [entry.source_id for entry in entries]


def test_category_gate_missing_config_keeps_every_entry() -> None:
    arxiv = _load_arxiv_stack()
    adapter = arxiv.ArxivAdapter()
    pairs = arxiv.parse_atom_feed_with_categories(_CATEGORY_FIXTURE, adapter=adapter)

    entries, skipped = arxiv.apply_category_gate(pairs, None)

    assert skipped == 0
    assert len(entries) == 3


@pytest.mark.asyncio
async def test_fetch_manifest_logs_category_gate_event(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    arxiv = _load_arxiv_stack()

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_CATEGORY_FIXTURE.encode())

    transport = httpx.MockTransport(handler)
    with caplog.at_level(logging.INFO):
        async with httpx.AsyncClient(transport=transport) as client:
            adapter = arxiv.ArxivAdapter(http_client=client)
            monkeypatch.setattr(
                arxiv,
                "datetime",
                type(
                    "FrozenDateTime",
                    (datetime,),
                    {"now": classmethod(lambda cls, tz=None: _UNTIL)},
                ),
            )
            entries = await adapter.fetch_manifest(since=_SINCE)

    gate_records = [
        record
        for record in caplog.records
        if getattr(record, "event", None) == arxiv.CATEGORY_GATE_EVENT
    ]
    assert len(gate_records) == 1
    record = gate_records[0]
    assert record.enforce is False
    assert record.skipped_by_category == 1
    assert record.kept == 3
    assert len(entries) == 3
