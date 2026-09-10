"""Unit tests for LessWrongAdapter (M8 T4, context-map flag 3).

Flag 3 resolution: implement the adapter only if a live GraphQL probe
succeeds. The probe *did* succeed (live-probed 2026-09-10 — see decision
log), so this suite tests the full adapter against mocked HTTP by default.
A separate, explicitly-opt-in live probe test is gated behind
``BISHOP_LESSWRONG_PROBE_LIVE=1`` and is skipped otherwise, matching the
"Optional live probes" test convention (§2 Tests) and the "no live network
in default CI" adapter-test convention.
"""

from __future__ import annotations

import os
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


def _load_lesswrong_stack() -> ModuleType:
    """Load scraper lesswrong adapter without shadowing state-worker ``app``."""
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
        import app.adapters.lesswrong as lesswrong  # noqa: WPS433
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.modules.update(saved_app_modules)
        for path_str in path_state:
            sys.path.remove(path_str)

    return lesswrong


def test_make_source_id() -> None:
    lesswrong = _load_lesswrong_stack()
    adapter = lesswrong.LessWrongAdapter()
    assert adapter.make_source_id("abc123") == "lesswrong:abc123"


def test_resolve_effective_since_default_window() -> None:
    lesswrong = _load_lesswrong_stack()
    now = datetime(2026, 6, 12, 12, 0, 0, tzinfo=UTC)
    resolved = lesswrong.resolve_effective_since(None, now=now)
    assert resolved == datetime(2026, 6, 5, 12, 0, 0, tzinfo=UTC)


def test_build_graphql_get_params_encodes_variables_as_json() -> None:
    lesswrong = _load_lesswrong_stack()
    params = lesswrong.build_graphql_get_params("query { __typename }", {"limit": 5})
    assert params["query"] == "query { __typename }"
    assert params["variables"] == '{"limit": 5}'


def test_parse_posts_response_maps_manifest_fields() -> None:
    lesswrong = _load_lesswrong_stack()
    adapter = lesswrong.LessWrongAdapter()
    payload = {
        "data": {
            "posts": {
                "results": [
                    {
                        "_id": "post1",
                        "title": "A LessWrong Post",
                        "postedAt": "2026-06-10T12:00:00.000Z",
                        "pageUrl": "https://www.lesswrong.com/posts/post1/a-lesswrong-post",
                    },
                    {"_id": "post2", "title": "No date", "postedAt": None, "pageUrl": None},
                ],
            },
        },
    }

    entries = lesswrong.parse_posts_response(payload, adapter=adapter)

    assert len(entries) == 2
    first = entries[0]
    assert first.source_id == "lesswrong:post1"
    assert first.source == SourceEnum.LESSWRONG
    assert first.domain == DomainEnum.PROFESSIONAL
    assert first.url == "https://www.lesswrong.com/posts/post1/a-lesswrong-post"
    assert first.published_at == datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)

    second = entries[1]
    assert second.url == "https://www.lesswrong.com/posts/post2"
    assert second.published_at is None


def test_parse_posts_response_dedupes_by_source_id() -> None:
    lesswrong = _load_lesswrong_stack()
    adapter = lesswrong.LessWrongAdapter()
    post = {"_id": "dup1", "title": "Dup", "postedAt": None, "pageUrl": None}
    payload = {"data": {"posts": {"results": [post, dict(post)]}}}

    entries = lesswrong.parse_posts_response(payload, adapter=adapter)

    assert len(entries) == 1


def test_parse_posts_response_skips_posts_missing_id_or_title() -> None:
    lesswrong = _load_lesswrong_stack()
    adapter = lesswrong.LessWrongAdapter()
    payload = {
        "data": {
            "posts": {
                "results": [
                    {"_id": "no-title", "title": None},
                    {"title": "no id"},
                ],
            },
        },
    }

    entries = lesswrong.parse_posts_response(payload, adapter=adapter)

    assert entries == []


def test_strip_html_to_text_removes_tags_and_collapses_whitespace() -> None:
    lesswrong = _load_lesswrong_stack()
    html = '<p><span style="white-space:pre-wrap">Hello</span> <a href="x">world</a>.</p>'
    assert lesswrong.strip_html_to_text(html) == "Hello world ."


@pytest.mark.asyncio
async def test_fetch_manifest_uses_get_and_hits_declared_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Falsifier for the GET-only contract (§2.1 adversarial micro-pass).

    Failure mode: fetch_manifest silently switches to (or is refactored
    into) a POST call, which the probed host answers with an opaque HTTP 500
    empty body — a production regression the mocked transport alone would
    not otherwise catch unless the test asserts the HTTP method explicitly.
    """
    lesswrong = _load_lesswrong_stack()
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"data": {"posts": {"results": []}}})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = lesswrong.LessWrongAdapter(http_client=client)
        entries = await adapter.fetch_manifest(since=_SINCE)

    assert entries == []
    assert captured["method"] == "GET"

    parsed = urlparse(str(captured["url"]))
    assert parsed.scheme == "https"
    assert parsed.netloc == "www.lesswrong.com"
    assert parsed.path == "/graphql"
    params = parse_qs(parsed.query)
    assert "query" in params
    assert "posts" in params["query"][0]


@pytest.mark.asyncio
async def test_fetch_content_strips_html_from_graphql_response() -> None:
    lesswrong = _load_lesswrong_stack()

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": {
                    "post": {
                        "result": {
                            "_id": "post1",
                            "title": "A LessWrong Post",
                            "contents": {"html": "<p>Body <b>text</b>.</p>"},
                        },
                    },
                },
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = lesswrong.LessWrongAdapter(http_client=client)
        entry = lesswrong.ManifestIngestEntry(
            source_id="lesswrong:post1",
            source=SourceEnum.LESSWRONG,
            url="https://www.lesswrong.com/posts/post1",
            title="A LessWrong Post",
            domain=DomainEnum.PROFESSIONAL,
        )
        content = await adapter.fetch_content(entry)

    assert content == "Body text ."


@pytest.mark.asyncio
async def test_fetch_content_falls_back_to_title_when_html_missing() -> None:
    lesswrong = _load_lesswrong_stack()

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"post": {"result": {"contents": None}}}})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = lesswrong.LessWrongAdapter(http_client=client)
        entry = lesswrong.ManifestIngestEntry(
            source_id="lesswrong:post1",
            source=SourceEnum.LESSWRONG,
            url="https://www.lesswrong.com/posts/post1",
            title="Fallback Title",
            domain=DomainEnum.PROFESSIONAL,
        )
        content = await adapter.fetch_content(entry)

    assert content == "Fallback Title"


@pytest.mark.skipif(
    os.environ.get("BISHOP_LESSWRONG_PROBE_LIVE") != "1",
    reason="Live network probe — opt-in via BISHOP_LESSWRONG_PROBE_LIVE=1",
)
@pytest.mark.asyncio
async def test_probe_lesswrong_api_live() -> None:
    lesswrong = _load_lesswrong_stack()
    async with httpx.AsyncClient() as client:
        probe_ok = await lesswrong.probe_lesswrong_api(http_client=client)
    assert probe_ok is True
