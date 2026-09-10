"""Unit tests for §18.4 backfill chunking (M8 T8-bis)."""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, patch

import pytest

from bishop_shared.enums import DomainEnum, SourceEnum

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRAPER_ROOT = _REPO_ROOT / "services" / "scraper"

_NOW = datetime(2026, 9, 10, 12, 0, 0, tzinfo=UTC)


def _load_scraper_loop_stack(env: dict[str, str] | None = None) -> tuple[ModuleType, ModuleType]:
    """Load ``app.loop`` and ``app.models`` fresh, honoring ``env`` overrides,
    without shadowing state-worker ``app`` in ``sys.modules`` (mirrors
    ``tests/test_scraper_loop.py``'s isolation pattern)."""
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

    saved_env: dict[str, str | None] = {}
    if env:
        for key, value in env.items():
            saved_env[key] = __import__("os").environ.get(key)
            __import__("os").environ[key] = value

    try:
        import app.loop as loop_mod  # noqa: WPS433
        import app.models as models  # noqa: WPS433
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.modules.update(saved_app_modules)
        for path_str in path_state:
            sys.path.remove(path_str)
        for key, original in saved_env.items():
            if original is None:
                __import__("os").environ.pop(key, None)
            else:
                __import__("os").environ[key] = original

    return loop_mod, models


def _sample_entry(models: ModuleType, source_id: str) -> object:
    return models.ManifestIngestEntry(
        source_id=source_id,
        source=SourceEnum.ARXIV,
        url=f"http://arxiv.org/abs/{source_id}",
        title="Example Paper",
        domain=DomainEnum.PROFESSIONAL,
    )


class _StubAdapter:
    source = SourceEnum.ARXIV
    domain = DomainEnum.PROFESSIONAL

    def __init__(self, entries_by_call: list[list[object]]) -> None:
        self._entries_by_call = entries_by_call
        self.fetch_manifest = AsyncMock(side_effect=[list(e) for e in entries_by_call])


def _adapter_factory(adapter: object) -> type:
    def _factory() -> object:
        return adapter

    return _factory  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# compute_backfill_chunk_starts
# ---------------------------------------------------------------------------


def test_compute_chunk_starts_covers_full_window() -> None:
    loop_mod, _ = _load_scraper_loop_stack()
    starts = loop_mod.compute_backfill_chunk_starts(window_days=60, chunk_days=7, now=_NOW)

    assert starts[0] == _NOW - timedelta(days=60)
    assert starts == sorted(starts)
    assert starts[-1] > _NOW - timedelta(days=7)
    assert len(starts) == 9


def test_compute_chunk_starts_falsifier_wrong_step_changes_count() -> None:
    """Falsifier: mutating chunk_days must change the returned chunk count."""
    loop_mod, _ = _load_scraper_loop_stack()
    starts_7 = loop_mod.compute_backfill_chunk_starts(window_days=60, chunk_days=7, now=_NOW)
    starts_30 = loop_mod.compute_backfill_chunk_starts(window_days=60, chunk_days=30, now=_NOW)
    assert len(starts_7) != len(starts_30)
    assert len(starts_30) == 2


def test_compute_chunk_starts_zero_window_returns_single_now() -> None:
    loop_mod, _ = _load_scraper_loop_stack()
    starts = loop_mod.compute_backfill_chunk_starts(window_days=0, chunk_days=7, now=_NOW)
    assert starts == [_NOW]


def test_compute_chunk_starts_zero_chunk_days_returns_single_window_start() -> None:
    loop_mod, _ = _load_scraper_loop_stack()
    starts = loop_mod.compute_backfill_chunk_starts(window_days=30, chunk_days=0, now=_NOW)
    assert starts == [_NOW - timedelta(days=30)]


# ---------------------------------------------------------------------------
# _scrape_adapter backfill branch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scrape_adapter_cold_start_with_backfill_enabled_chunks_and_sleeps() -> None:
    """Falsifier: with BISHOP_BACKFILL_ENABLED=1 and no prior state, fetch_manifest
    must be called once per chunk boundary (not once with since=None), and the
    inter-chunk sleep must run len(chunks)-1 times."""
    loop_mod, models = _load_scraper_loop_stack(
        env={"BISHOP_BACKFILL_ENABLED": "1", "BISHOP_BACKFILL_CHUNK_DAYS": "30"},
    )
    entry = _sample_entry(models, "arxiv:2607.00001")
    adapter = _StubAdapter([[entry], [], []])
    client = AsyncMock()
    client.get_scraper_state.return_value = models.ScraperStateSnapshot(
        source=SourceEnum.ARXIV,
        last_successful_run_at=None,
        updated_at=_NOW,
    )
    client.post_manifest_batch.return_value = models.ManifestBatchResult(inserted=1, skipped=0)

    with patch.object(loop_mod, "ADAPTER_REGISTRY", [_adapter_factory(adapter)]):
        with patch.object(loop_mod.asyncio, "sleep", AsyncMock()) as sleep_mock:
            await loop_mod.scrape_cycle(client)

    # ArxivAdapter's BACKFILL_CONFIG window is 60 days; chunk_days=30 -> 2 chunks.
    assert adapter.fetch_manifest.await_count == 2
    since_values = [call.kwargs["since"] for call in adapter.fetch_manifest.await_args_list]
    assert since_values == sorted(since_values)
    assert all(since != None for since in since_values)  # noqa: E711
    assert sleep_mock.await_count == 1
    client.post_scraper_state.assert_awaited_once()


@pytest.mark.asyncio
async def test_scrape_adapter_cold_start_backfill_disabled_stays_single_incremental_call() -> None:
    """Falsifier: default BISHOP_BACKFILL_ENABLED=0 must NOT chunk even when
    last_successful_run_at is None — a single fetch_manifest(since=None) call."""
    loop_mod, models = _load_scraper_loop_stack(env={"BISHOP_BACKFILL_ENABLED": "0"})
    entry = _sample_entry(models, "arxiv:2607.00002")
    adapter = _StubAdapter([[entry]])
    client = AsyncMock()
    client.get_scraper_state.return_value = models.ScraperStateSnapshot(
        source=SourceEnum.ARXIV,
        last_successful_run_at=None,
        updated_at=_NOW,
    )
    client.post_manifest_batch.return_value = models.ManifestBatchResult(inserted=1, skipped=0)

    with patch.object(loop_mod, "ADAPTER_REGISTRY", [_adapter_factory(adapter)]):
        await loop_mod.scrape_cycle(client)

    adapter.fetch_manifest.assert_awaited_once_with(since=None)
    client.post_manifest_batch.assert_awaited_once_with([entry])


@pytest.mark.asyncio
async def test_scrape_adapter_backfill_enabled_but_warm_start_stays_incremental() -> None:
    """Falsifier: BISHOP_BACKFILL_ENABLED=1 with an existing scraper_state
    (warm start) must not trigger chunking — cold-start-only per §0 flag 4."""
    loop_mod, models = _load_scraper_loop_stack(env={"BISHOP_BACKFILL_ENABLED": "1"})
    entry = _sample_entry(models, "arxiv:2607.00003")
    adapter = _StubAdapter([[entry]])
    last_run = _NOW - timedelta(days=1)
    client = AsyncMock()
    client.get_scraper_state.return_value = models.ScraperStateSnapshot(
        source=SourceEnum.ARXIV,
        last_successful_run_at=last_run,
        updated_at=_NOW,
    )
    client.post_manifest_batch.return_value = models.ManifestBatchResult(inserted=1, skipped=0)

    with patch.object(loop_mod, "ADAPTER_REGISTRY", [_adapter_factory(adapter)]):
        await loop_mod.scrape_cycle(client)

    adapter.fetch_manifest.assert_awaited_once_with(since=last_run)
    client.post_manifest_batch.assert_awaited_once_with([entry])
