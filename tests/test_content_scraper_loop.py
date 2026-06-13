"""Unit tests for content_scrape_cycle loop (M4 T2)."""

from __future__ import annotations

import asyncio
import shutil
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from bishop_shared.enums import DomainEnum, SourceEnum

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CONTENT_SCRAPER_ROOT = _REPO_ROOT / "services" / "content-scraper"
_SCRAPER_SRC = _REPO_ROOT / "services" / "scraper" / "app"


def _vendor_scraper_app(target_root: Path) -> None:
    scraper_dst = target_root / "scraper_app"
    if scraper_dst.exists():
        shutil.rmtree(scraper_dst)
    shutil.copytree(_SCRAPER_SRC, scraper_dst)
    for py_file in scraper_dst.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        text = text.replace("from app.", "from scraper_app.").replace(
            "import app.",
            "import scraper_app.",
        )
        py_file.write_text(text, encoding="utf-8")


def _load_content_scraper_loop_stack(
    tmp_path: Path,
) -> tuple[ModuleType, ModuleType, ModuleType, ModuleType]:
    saved_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "app"
        or name.startswith("app.")
        or name == "scraper_app"
        or name.startswith("scraper_app.")
    }
    for name in saved_modules:
        del sys.modules[name]

    vendor_root = tmp_path / "vendor"
    vendor_root.mkdir()
    _vendor_scraper_app(vendor_root)

    repo_str = str(_REPO_ROOT)
    worker_str = str(_CONTENT_SCRAPER_ROOT)
    vendor_str = str(vendor_root)
    path_state: list[str] = []
    for path_str in (worker_str, vendor_str, repo_str):
        if path_str not in sys.path:
            sys.path.insert(0, path_str)
            path_state.append(path_str)

    try:
        import app.loop as loop_mod  # noqa: WPS433
        import app.models as models  # noqa: WPS433
        import app.state_worker_client as client_mod  # noqa: WPS433
        import scraper_app.adapters.arxiv as arxiv_mod  # noqa: WPS433
    finally:
        for name in list(sys.modules):
            if (
                name == "app"
                or name.startswith("app.")
                or name == "scraper_app"
                or name.startswith("scraper_app.")
            ):
                del sys.modules[name]
        sys.modules.update(saved_modules)
        for path_str in path_state:
            sys.path.remove(path_str)

    return loop_mod, models, client_mod, arxiv_mod


def _sample_poll_entry(models: ModuleType, source_id: str = "arxiv:2301.00001") -> object:
    return models.ManifestPollEntry(
        source_id=source_id,
        source=SourceEnum.ARXIV,
        url="http://arxiv.org/abs/2301.00001",
        title="Example Paper",
        abstract="An abstract.",
        domain=DomainEnum.PROFESSIONAL,
        processing_state="SCRAPE_QUEUED",
    )


def _mock_state_client(
    client_mod: ModuleType,
    models: ModuleType,
    *,
    entries: list[object] | None = None,
    content_error: bool = False,
) -> MagicMock:
    poll_response = models.ManifestPollResponse(
        entries=entries or [],
        claimed_count=len(entries or []),
        transitioned_to="SCRAPE_QUEUED" if entries else None,
    )
    client = MagicMock(spec=client_mod.StateWorkerClient)
    client.poll_relevance_passed = AsyncMock(return_value=poll_response)
    if content_error:
        request = httpx.Request("POST", "http://test/entries/content")
        response = httpx.Response(409, request=request)
        client.post_content = AsyncMock(
            side_effect=httpx.HTTPStatusError("error", request=request, response=response),
        )
    else:
        client.post_content = AsyncMock(
            return_value=models.ContentPostResponse(
                entry_id="entry-1",
                processing_state="SCRAPED",
            ),
        )
    client.post_failed = AsyncMock()
    client.aclose = AsyncMock()
    return client


def test_scraper_app_fetch_content_importable_via_vendor_layout(tmp_path: Path) -> None:
    """Kill-criterion smoke: vendored scraper_app exposes T1 fetch_content."""
    vendor_root = tmp_path / "vendor"
    vendor_root.mkdir()
    _vendor_scraper_app(vendor_root)
    sys.path.insert(0, str(vendor_root))
    try:
        from scraper_app.adapters.arxiv import ArxivAdapter  # noqa: WPS433

        assert callable(getattr(ArxivAdapter, "fetch_content", None))
    finally:
        sys.path.remove(str(vendor_root))
        for name in list(sys.modules):
            if name == "scraper_app" or name.startswith("scraper_app."):
                del sys.modules[name]


def test_content_scrape_cycle_empty_poll_skips_fetch(tmp_path: Path) -> None:
    loop_mod, models, client_mod, _ = _load_content_scraper_loop_stack(tmp_path)
    state_client = _mock_state_client(client_mod, models, entries=[])

    async def _run() -> None:
        with patch.object(loop_mod, "failure_envelope", new_callable=AsyncMock) as mock_fe:
            await loop_mod.content_scrape_cycle(state_client)
            mock_fe.assert_not_called()

    asyncio.run(_run())
    state_client.post_content.assert_not_called()


def test_content_scrape_cycle_happy_path_posts_content(tmp_path: Path) -> None:
    loop_mod, models, client_mod, arxiv_mod = _load_content_scraper_loop_stack(tmp_path)
    entry = _sample_poll_entry(models)
    state_client = _mock_state_client(client_mod, models, entries=[entry])

    async def _run() -> None:
        with patch.object(loop_mod, "resolve_adapter") as mock_resolve:
            adapter = arxiv_mod.ArxivAdapter()
            mock_resolve.return_value = adapter
            with patch.object(
                loop_mod,
                "failure_envelope",
                new_callable=AsyncMock,
                return_value="scraped body text",
            ) as mock_fe:
                await loop_mod.content_scrape_cycle(state_client)
                mock_fe.assert_awaited_once()
                assert mock_fe.await_args.args[0] == adapter.fetch_content

    asyncio.run(_run())
    state_client.post_content.assert_awaited_once()
    posted = state_client.post_content.await_args.args[0]
    assert posted.source_id == "arxiv:2301.00001"
    assert posted.content_raw == "scraped body text"
    state_client.post_failed.assert_not_called()


def test_content_scrape_cycle_adapter_failure_posts_failed(tmp_path: Path) -> None:
    loop_mod, models, client_mod, arxiv_mod = _load_content_scraper_loop_stack(tmp_path)
    entry = _sample_poll_entry(models)
    state_client = _mock_state_client(client_mod, models, entries=[entry])

    async def _run() -> None:
        with patch.object(loop_mod, "resolve_adapter") as mock_resolve:
            mock_resolve.return_value = arxiv_mod.ArxivAdapter()
            with patch.object(
                loop_mod,
                "failure_envelope",
                new_callable=AsyncMock,
                side_effect=RuntimeError("fetch blew up"),
            ):
                await loop_mod.content_scrape_cycle(state_client)

    asyncio.run(_run())
    state_client.post_failed.assert_awaited_once()
    failed_body = state_client.post_failed.await_args.args[0]
    assert failed_body.state_at_failure == "SCRAPE_QUEUED"
    assert failed_body.error_class == "RuntimeError"
    state_client.post_content.assert_not_called()


def test_content_scrape_cycle_unknown_source_skips_entry(tmp_path: Path) -> None:
    loop_mod, models, client_mod, _ = _load_content_scraper_loop_stack(tmp_path)
    entry = models.ManifestPollEntry(
        source_id="unknown:1",
        source=SourceEnum.ARXIV,
        url="http://example.com",
        title="Unknown",
        domain=DomainEnum.PROFESSIONAL,
    )
    state_client = _mock_state_client(client_mod, models, entries=[entry])

    async def _run() -> None:
        with patch.object(loop_mod, "resolve_adapter", return_value=None):
            with patch.object(loop_mod, "failure_envelope", new_callable=AsyncMock) as mock_fe:
                await loop_mod.content_scrape_cycle(state_client)
                mock_fe.assert_not_called()

    asyncio.run(_run())
    state_client.post_content.assert_not_called()
    state_client.post_failed.assert_not_called()


def test_content_scrape_cycle_content_post_error_logged_not_swallowed(tmp_path: Path) -> None:
    """Falsifier: non-2xx content POST must not be treated as success."""
    loop_mod, models, client_mod, arxiv_mod = _load_content_scraper_loop_stack(tmp_path)
    entry = _sample_poll_entry(models)
    state_client = _mock_state_client(client_mod, models, entries=[entry], content_error=True)

    async def _run() -> None:
        with patch.object(loop_mod, "resolve_adapter") as mock_resolve:
            mock_resolve.return_value = arxiv_mod.ArxivAdapter()
            with patch.object(
                loop_mod,
                "failure_envelope",
                new_callable=AsyncMock,
                return_value="body",
            ):
                await loop_mod.content_scrape_cycle(state_client)

    asyncio.run(_run())
    state_client.post_content.assert_awaited_once()
    state_client.post_failed.assert_not_called()
