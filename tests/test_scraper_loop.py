"""Unit tests for scraper loop and scheduler (M2 T5)."""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from bishop_shared.enums import DomainEnum, SourceEnum

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRAPER_ROOT = _REPO_ROOT / "services" / "scraper"

_UPDATED_AT = datetime(2026, 6, 12, 12, 0, 0, tzinfo=UTC)
_LAST_RUN = datetime(2026, 6, 10, 8, 0, 0, tzinfo=UTC)


def _adapter_factory(adapter: object) -> type:
    """Registry entry callable that always returns ``adapter``."""

    def _factory() -> object:
        return adapter

    return _factory  # type: ignore[return-value]


def _load_scraper_loop_stack() -> tuple[ModuleType, ModuleType, ModuleType, ModuleType, ModuleType]:
    """Load scraper loop stack without shadowing state-worker ``app`` in sys.modules."""
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
        import app.adapters.base as adapter_base  # noqa: WPS433
        import app.exceptions as exceptions  # noqa: WPS433
        import app.loop as loop_mod  # noqa: WPS433
        import app.main as main_mod  # noqa: WPS433
        import app.models as models  # noqa: WPS433
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.modules.update(saved_app_modules)
        for path_str in path_state:
            sys.path.remove(path_str)

    return adapter_base, exceptions, loop_mod, main_mod, models


def _sample_entry(models: ModuleType) -> object:
    return models.ManifestIngestEntry(
        source_id="arxiv:2406.00001",
        source=SourceEnum.ARXIV,
        url="http://arxiv.org/abs/2406.00001",
        title="Example Paper",
        domain=DomainEnum.PROFESSIONAL,
    )


class _StubAdapter:
    source = SourceEnum.ARXIV
    domain = DomainEnum.PROFESSIONAL

    def __init__(self, entries: list[object] | None = None) -> None:
        self._entries = entries or []
        self.fetch_manifest = AsyncMock(return_value=self._entries)


@pytest.mark.asyncio
async def test_scrape_cycle_posts_batch_and_updates_state() -> None:
    _, _, loop_mod, _, models = _load_scraper_loop_stack()
    entry = _sample_entry(models)
    adapter = _StubAdapter([entry])
    client = AsyncMock()
    client.get_scraper_state.return_value = models.ScraperStateSnapshot(
        source=SourceEnum.ARXIV,
        last_successful_run_at=_LAST_RUN,
        updated_at=_UPDATED_AT,
    )
    client.post_manifest_batch.return_value = models.ManifestBatchResult(
        inserted=1,
        skipped=0,
    )

    with patch.object(loop_mod, "ADAPTER_REGISTRY", [_adapter_factory(adapter)]):
        await loop_mod.scrape_cycle(client)

    client.get_scraper_state.assert_awaited_once_with(SourceEnum.ARXIV)
    adapter.fetch_manifest.assert_awaited_once_with(since=_LAST_RUN)
    client.post_manifest_batch.assert_awaited_once_with([entry])
    client.post_scraper_state.assert_awaited_once()
    client.aclose.assert_not_awaited()


@pytest.mark.asyncio
async def test_scrape_cycle_skips_state_update_on_batch_failure() -> None:
    _, _, loop_mod, _, models = _load_scraper_loop_stack()
    adapter = _StubAdapter([_sample_entry(models)])
    client = AsyncMock()
    client.get_scraper_state.return_value = models.ScraperStateSnapshot(
        source=SourceEnum.ARXIV,
        last_successful_run_at=None,
        updated_at=_UPDATED_AT,
    )
    request = httpx.Request("POST", "http://state-worker:8000/manifest/batch")
    response = httpx.Response(500, request=request)
    client.post_manifest_batch.side_effect = httpx.HTTPStatusError(
        "error",
        request=request,
        response=response,
    )

    with patch.object(loop_mod, "ADAPTER_REGISTRY", [_adapter_factory(adapter)]):
        await loop_mod.scrape_cycle(client)

    client.post_scraper_state.assert_not_awaited()


@pytest.mark.asyncio
async def test_scrape_cycle_rerun_reports_skipped_idempotent_rows() -> None:
    """Falsifier: duplicate source_id must surface skipped >= 1 on re-run."""
    _, _, loop_mod, _, models = _load_scraper_loop_stack()
    entry = _sample_entry(models)
    adapter = _StubAdapter([entry])
    client = AsyncMock()
    client.get_scraper_state.return_value = models.ScraperStateSnapshot(
        source=SourceEnum.ARXIV,
        last_successful_run_at=_LAST_RUN,
        updated_at=_UPDATED_AT,
    )
    batch_results = [
        models.ManifestBatchResult(inserted=1, skipped=0),
        models.ManifestBatchResult(inserted=0, skipped=1),
    ]
    client.post_manifest_batch.side_effect = batch_results

    with patch.object(loop_mod, "ADAPTER_REGISTRY", [_adapter_factory(adapter)]):
        await loop_mod.scrape_cycle(client)
        await loop_mod.scrape_cycle(client)

    assert client.post_manifest_batch.await_count == 2
    assert batch_results[1].skipped >= 1


@pytest.mark.asyncio
async def test_scrape_cycle_survives_429_via_failure_envelope() -> None:
    """Falsifier: unhandled 429 must not crash the scrape cycle."""
    _, _, loop_mod, _, models = _load_scraper_loop_stack()
    entry = _sample_entry(models)
    attempts = 0

    async def flaky_fetch_manifest(*, since: datetime | None = None) -> list[object]:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            request = httpx.Request("GET", "http://export.arxiv.org/api/query")
            response = httpx.Response(429, request=request)
            raise httpx.HTTPStatusError("rate limited", request=request, response=response)
        return [entry]

    adapter = _StubAdapter()
    adapter.fetch_manifest = flaky_fetch_manifest
    client = AsyncMock()
    client.get_scraper_state.return_value = models.ScraperStateSnapshot(
        source=SourceEnum.ARXIV,
        last_successful_run_at=None,
        updated_at=_UPDATED_AT,
    )
    client.post_manifest_batch.return_value = models.ManifestBatchResult(
        inserted=1,
        skipped=0,
    )

    with patch.object(loop_mod, "ADAPTER_REGISTRY", [_adapter_factory(adapter)]):
        await loop_mod.scrape_cycle(client)

    assert attempts == 3
    client.post_manifest_batch.assert_awaited_once()
    client.post_scraper_state.assert_awaited_once()


@pytest.mark.asyncio
async def test_scrape_cycle_logs_permanent_failure_and_continues() -> None:
    _, exceptions_mod, loop_mod, _, models = _load_scraper_loop_stack()
    adapter = _StubAdapter()
    request = httpx.Request("GET", "http://export.arxiv.org/api/query")
    response = httpx.Response(400, request=request)
    adapter.fetch_manifest.side_effect = exceptions_mod.PermanentFailureError(
        SourceEnum.ARXIV,
        400,
        httpx.HTTPStatusError("bad request", request=request, response=response),
    )
    client = AsyncMock()
    client.get_scraper_state.return_value = models.ScraperStateSnapshot(
        source=SourceEnum.ARXIV,
        last_successful_run_at=None,
        updated_at=_UPDATED_AT,
    )

    with patch.object(loop_mod, "ADAPTER_REGISTRY", [_adapter_factory(adapter)]):
        with patch.object(loop_mod, "log_permanent_failure") as log_failure:
            await loop_mod.scrape_cycle(client)

    log_failure.assert_called_once()
    client.post_manifest_batch.assert_not_awaited()


@pytest.mark.asyncio
async def test_scrape_cycle_escalatable_failure_skips_batch() -> None:
    """Falsifier: escalatable HTTP errors must not post manifest or update state."""
    _, exceptions_mod, loop_mod, _, models = _load_scraper_loop_stack()
    adapter = _StubAdapter()
    request = httpx.Request("GET", "http://export.arxiv.org/api/query")
    response = httpx.Response(403, request=request)
    adapter.fetch_manifest.side_effect = exceptions_mod.EscalatableError(
        SourceEnum.ARXIV,
        403,
        httpx.HTTPStatusError("forbidden", request=request, response=response),
    )
    client = AsyncMock()
    client.get_scraper_state.return_value = models.ScraperStateSnapshot(
        source=SourceEnum.ARXIV,
        last_successful_run_at=None,
        updated_at=_UPDATED_AT,
    )

    with patch.object(loop_mod, "ADAPTER_REGISTRY", [_adapter_factory(adapter)]):
        await loop_mod.scrape_cycle(client)

    client.post_manifest_batch.assert_not_awaited()
    client.post_scraper_state.assert_not_awaited()


@pytest.mark.asyncio
async def test_scheduler_invokes_cycle() -> None:
    _, _, loop_mod, main_mod, _ = _load_scraper_loop_stack()
    invoked = asyncio.Event()

    async def fake_cycle(client=None) -> None:
        invoked.set()
        raise asyncio.CancelledError

    with patch.object(main_mod, "StateWorkerClient", return_value=AsyncMock()):
        with patch.object(main_mod, "scrape_cycle", side_effect=fake_cycle):
            with pytest.raises(asyncio.CancelledError):
                await main_mod.run_scheduler()

    assert invoked.is_set()
