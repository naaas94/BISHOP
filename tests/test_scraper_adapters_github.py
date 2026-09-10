"""Unit tests for GitHubAdapter (M8 T3)."""

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


def _search_fixture(items: list[dict[str, object]]) -> dict[str, object]:
    return {"total_count": len(items), "items": items}


def _repo_item(full_name: str, *, description: str | None = "A repo.") -> dict[str, object]:
    owner, name = full_name.split("/", 1)
    return {
        "full_name": full_name,
        "name": name,
        "description": description,
        "html_url": f"https://github.com/{full_name}",
        "pushed_at": "2026-06-15T10:00:00Z",
        "owner": {"login": owner},
    }


def _load_github_stack() -> ModuleType:
    """Load scraper github adapter without shadowing state-worker ``app``."""
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
        import app.adapters.github as github  # noqa: WPS433
        import app.models as models  # noqa: WPS433
        github.ManifestIngestEntry = models.ManifestIngestEntry  # type: ignore[attr-defined]
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.modules.update(saved_app_modules)
        for path_str in path_state:
            sys.path.remove(path_str)

    return github


def test_make_source_id() -> None:
    gh = _load_github_stack()
    adapter = gh.GitHubAdapter()
    assert adapter.make_source_id("owner/repo") == "github:owner/repo"


def test_resolve_effective_since_uses_backfill_window() -> None:
    gh = _load_github_stack()
    now = datetime(2026, 7, 1, 12, 0, 0, tzinfo=UTC)
    resolved = gh.resolve_effective_since(None, now=now)
    expected = now - __import__("datetime").timedelta(
        days=BACKFILL_CONFIG["github"].window_days,
    )
    assert resolved == expected


def test_build_search_query_includes_since_date() -> None:
    gh = _load_github_stack()
    query = gh.build_search_query(_SINCE)
    assert query.startswith("pushed:>2026-06-01")
    assert "stars:>10" in query


def test_parse_search_response_maps_manifest_fields() -> None:
    gh = _load_github_stack()
    adapter = gh.GitHubAdapter()
    payload = _search_fixture([_repo_item("acme/ml-tools"), _repo_item("acme/other", description=None)])
    entries = gh.parse_search_response(payload, adapter=adapter)

    assert len(entries) == 2
    first = entries[0]
    assert first.source_id == "github:acme/ml-tools"
    assert first.source == SourceEnum.GITHUB
    assert first.domain == DomainEnum.PROFESSIONAL
    assert first.title == "ml-tools"
    assert first.abstract == "A repo."
    assert first.published_at == datetime(2026, 6, 15, 10, 0, 0, tzinfo=UTC)

    second = entries[1]
    assert second.abstract is None


@pytest.mark.asyncio
async def test_fetch_manifest_sends_bearer_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gh = _load_github_stack()
    captured: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("Authorization")
        return httpx.Response(
            200,
            json=_search_fixture([_repo_item("acme/ml-tools")]),
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = gh.GitHubAdapter(http_client=client)
        monkeypatch.setattr(gh, "GITHUB_TOKEN", "ghp_test_token")
        monkeypatch.setattr(gh, "_max_pages_from_env", lambda: 1)
        monkeypatch.setattr(
            gh,
            "datetime",
            type(
                "FrozenDateTime",
                (datetime,),
                {"now": classmethod(lambda cls, tz=None: _UNTIL)},
            ),
        )
        entries = await adapter.fetch_manifest(since=_SINCE)

    assert len(entries) == 1
    assert captured["authorization"] == "Bearer ghp_test_token"


@pytest.mark.asyncio
async def test_fetch_manifest_stops_at_max_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gh = _load_github_stack()
    pages_seen: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        params = parse_qs(urlparse(str(request.url)).query)
        page = int(params["page"][0])
        pages_seen.append(page)
        items = [_repo_item(f"acme/repo-{page}-{idx}") for idx in range(100)]
        return httpx.Response(200, json=_search_fixture(items))

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = gh.GitHubAdapter(http_client=client)
        monkeypatch.setattr(gh, "GITHUB_TOKEN", "ghp_test_token")
        monkeypatch.setattr(gh, "_max_pages_from_env", lambda: 2)
        monkeypatch.setattr(
            gh,
            "datetime",
            type(
                "FrozenDateTime",
                (datetime,),
                {"now": classmethod(lambda cls, tz=None: _UNTIL)},
            ),
        )
        entries = await adapter.fetch_manifest(since=_SINCE)

    assert pages_seen == [1, 2]
    assert len(entries) == 200


@pytest.mark.asyncio
async def test_fetch_content_returns_readme_text() -> None:
    gh = _load_github_stack()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/repos/acme/ml-tools/readme"
        return httpx.Response(200, text="# ML Tools\n\nREADME body.")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = gh.GitHubAdapter(http_client=client)
        entry = gh.ManifestIngestEntry(
            source_id="github:acme/ml-tools",
            source=SourceEnum.GITHUB,
            url="https://github.com/acme/ml-tools",
            title="ml-tools",
            domain=DomainEnum.PROFESSIONAL,
        )
        content = await adapter.fetch_content(entry)

    assert content == "# ML Tools\n\nREADME body."


@pytest.mark.asyncio
async def test_fetch_content_falls_back_when_readme_missing() -> None:
    gh = _load_github_stack()

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = gh.GitHubAdapter(http_client=client)
        entry = gh.ManifestIngestEntry(
            source_id="github:acme/empty",
            source=SourceEnum.GITHUB,
            url="https://github.com/acme/empty",
            title="empty",
            abstract="No readme.",
            domain=DomainEnum.PROFESSIONAL,
        )
        content = await adapter.fetch_content(entry)

    assert content == "empty\n\nNo readme."
