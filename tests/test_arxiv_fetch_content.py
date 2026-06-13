"""Unit tests for ArxivAdapter.fetch_content (M4 T1)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

import httpx
import pytest

from bishop_shared.enums import DomainEnum, SourceEnum

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRAPER_ROOT = _REPO_ROOT / "services" / "scraper"


def _load_arxiv_stack() -> tuple[ModuleType, ModuleType]:
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
        import app.models as models  # noqa: WPS433
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.modules.update(saved_app_modules)
        for path_str in path_state:
            sys.path.remove(path_str)

    return arxiv, models


def _sample_entry(
    models: ModuleType,
    *,
    title: str = "Example Paper",
    abstract: str | None = "An abstract.",
) -> object:
    return models.ManifestIngestEntry(
        source_id="arxiv:2301.00001",
        source=SourceEnum.ARXIV,
        url="http://arxiv.org/abs/2301.00001",
        title=title,
        abstract=abstract,
        domain=DomainEnum.PROFESSIONAL,
    )


def test_parse_raw_id_from_source_id() -> None:
    arxiv, _ = _load_arxiv_stack()
    assert arxiv.parse_raw_id_from_source_id("arxiv:2301.00001") == "2301.00001"


def test_compose_fallback_content_with_abstract() -> None:
    arxiv, models = _load_arxiv_stack()
    entry = _sample_entry(models, title="Title", abstract="Body abstract")
    assert arxiv.compose_fallback_content(entry) == "Title\n\nBody abstract"


def test_compose_fallback_content_without_abstract() -> None:
    arxiv, models = _load_arxiv_stack()
    entry = _sample_entry(models, title="Title Only", abstract=None)
    assert arxiv.compose_fallback_content(entry) == "Title Only\n\n"


def test_strip_html_to_text_ignores_script_and_style() -> None:
    arxiv, _ = _load_arxiv_stack()
    html = (
        "<html><head><style>.x{color:red}</style></head>"
        "<body><script>ignore()</script><p>Visible text</p></body></html>"
    )
    assert arxiv.strip_html_to_text(html) == "Visible text"


@pytest.mark.asyncio
async def test_fetch_arxiv_html_text_returns_stripped_text() -> None:
    arxiv, _ = _load_arxiv_stack()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("https://arxiv.org/html/2301.00001")
        return httpx.Response(200, text="<html><body><p>Full paper text</p></body></html>")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        text = await arxiv.fetch_arxiv_html_text("2301.00001", http_client=client)

    assert text == "Full paper text"


@pytest.mark.asyncio
async def test_fetch_arxiv_html_text_non_2xx_returns_none() -> None:
    arxiv, _ = _load_arxiv_stack()

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        text = await arxiv.fetch_arxiv_html_text("2301.00001", http_client=client)

    assert text is None


@pytest.mark.asyncio
async def test_fetch_arxiv_html_text_empty_body_returns_none() -> None:
    arxiv, _ = _load_arxiv_stack()

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html><body><script>only()</script></body></html>")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        text = await arxiv.fetch_arxiv_html_text("2301.00001", http_client=client)

    assert text is None


@pytest.mark.asyncio
async def test_fetch_content_uses_html_on_success() -> None:
    arxiv, models = _load_arxiv_stack()
    entry = _sample_entry(models)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html><body><p>HTML body</p></body></html>")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = arxiv.ArxivAdapter(http_client=client)
        content = await adapter.fetch_content(entry)

    assert content == "HTML body"


@pytest.mark.asyncio
async def test_fetch_content_falls_back_on_404() -> None:
    arxiv, models = _load_arxiv_stack()
    entry = _sample_entry(models, title="Fallback Title", abstract="Fallback abstract")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = arxiv.ArxivAdapter(http_client=client)
        content = await adapter.fetch_content(entry)

    assert content == "Fallback Title\n\nFallback abstract"
