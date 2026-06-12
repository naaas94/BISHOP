"""Unit tests for StateWorkerClient (M2 T1) — httpx mock transport."""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import httpx
import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRAPER_ROOT = _REPO_ROOT / "services" / "scraper"

_UPDATED_AT = datetime(2026, 6, 11, 12, 0, 0, tzinfo=UTC)
_TS = datetime(2026, 6, 8, 10, 0, 0, tzinfo=UTC)


def _load_scraper_client_stack() -> tuple[ModuleType, ModuleType]:
    """Load scraper client stack without shadowing state-worker `app` in sys.modules."""
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
        import app.models as models  # noqa: WPS433 — isolated import under scraper path
        import app.state_worker_client as client_mod  # noqa: WPS433
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.modules.update(saved_app_modules)
        for path_str in path_state:
            sys.path.remove(path_str)

    return models, client_mod


def _sample_entry(models: ModuleType) -> object:
    return models.ManifestIngestEntry(
        source_id="arxiv:2406.00001",
        source=models.SourceEnum.ARXIV,
        url="http://arxiv.org/abs/2406.00001",
        title="Example Paper",
        domain=models.DomainEnum.PROFESSIONAL,
    )


def test_get_scraper_state_parses_null_last_run() -> None:
    models, client_mod = _load_scraper_client_stack()

    async def _run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/scraper-state/arxiv"
            return httpx.Response(
                200,
                json={
                    "source": "arxiv",
                    "last_successful_run_at": None,
                    "updated_at": _UPDATED_AT.isoformat().replace("+00:00", "Z"),
                },
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            client = client_mod.StateWorkerClient(client=http)
            snapshot = await client.get_scraper_state(models.SourceEnum.ARXIV)
        assert snapshot.source == models.SourceEnum.ARXIV
        assert snapshot.last_successful_run_at is None
        assert snapshot.updated_at == _UPDATED_AT

    asyncio.run(_run())


def test_post_manifest_batch_parses_response() -> None:
    models, client_mod = _load_scraper_client_stack()

    async def _run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/manifest/batch"
            body = json.loads(request.content.decode())
            assert body["entries"][0]["domain"] == "professional"
            return httpx.Response(200, json={"inserted": 2, "skipped": 1})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            client = client_mod.StateWorkerClient(client=http)
            result = await client.post_manifest_batch([_sample_entry(models)])
        assert result.inserted == 2
        assert result.skipped == 1

    asyncio.run(_run())


def test_post_scraper_state_sends_timestamp_and_expects_204() -> None:
    models, client_mod = _load_scraper_client_stack()

    async def _run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/scraper-state/arxiv"
            body = json.loads(request.content.decode())
            assert body["timestamp"] == "2026-06-08T10:00:00Z"
            return httpx.Response(204)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            client = client_mod.StateWorkerClient(client=http)
            await client.post_scraper_state(models.SourceEnum.ARXIV, _TS)

    asyncio.run(_run())


def test_post_manifest_batch_raises_on_non_2xx() -> None:
    """Falsifier: silent acceptance of state-worker HTTP errors on batch POST."""

    models, client_mod = _load_scraper_client_stack()

    async def _run() -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"detail": "internal error"})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            client = client_mod.StateWorkerClient(client=http)
            with pytest.raises(httpx.HTTPStatusError):
                await client.post_manifest_batch([_sample_entry(models)])

    asyncio.run(_run())
