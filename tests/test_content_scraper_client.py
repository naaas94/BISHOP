"""Unit tests for content-scraper StateWorkerClient (M4 T2)."""

from __future__ import annotations

import asyncio
import json
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import httpx
import pytest

from bishop_shared.enums import DomainEnum, SourceEnum

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CONTENT_SCRAPER_ROOT = _REPO_ROOT / "services" / "content-scraper"


def _load_client_stack() -> tuple[ModuleType, ModuleType]:
    saved_app_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "app" or name.startswith("app.")
    }
    for name in saved_app_modules:
        del sys.modules[name]

    repo_str = str(_REPO_ROOT)
    worker_str = str(_CONTENT_SCRAPER_ROOT)
    path_state: list[str] = []
    for path_str in (worker_str, repo_str):
        if path_str not in sys.path:
            sys.path.insert(0, path_str)
            path_state.append(path_str)

    try:
        import app.models as models  # noqa: WPS433
        import app.state_worker_client as client_mod  # noqa: WPS433
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.modules.update(saved_app_modules)
        for path_str in path_state:
            sys.path.remove(path_str)

    return models, client_mod


def test_manifest_poll_entry_round_trip() -> None:
    models, _ = _load_client_stack()
    entry = models.ManifestPollEntry(
        source_id="arxiv:2301.00001",
        source=SourceEnum.ARXIV,
        url="http://arxiv.org/abs/2301.00001",
        title="Example",
        abstract="Abstract text",
        domain=DomainEnum.PROFESSIONAL,
        processing_state="SCRAPE_QUEUED",
    )
    payload = entry.model_dump(mode="json")
    restored = models.ManifestPollEntry.model_validate(payload)
    assert restored.source_id == entry.source_id
    assert restored.processing_state == "SCRAPE_QUEUED"


def test_poll_relevance_passed_calls_wire_route() -> None:
    _, client_mod = _load_client_stack()

    async def _run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/manifest/poll"
            assert request.url.params["state"] == "RELEVANCE_PASSED"
            assert request.url.params["limit"] == "10"
            return httpx.Response(
                200,
                json={
                    "entries": [
                        {
                            "source_id": "arxiv:2301.00001",
                            "source": "arxiv",
                            "url": "http://arxiv.org/abs/2301.00001",
                            "title": "Example Paper",
                            "abstract": "An abstract.",
                            "domain": "professional",
                            "processing_state": "SCRAPE_QUEUED",
                        }
                    ],
                    "claimed_count": 1,
                    "transitioned_to": "SCRAPE_QUEUED",
                },
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            client = client_mod.StateWorkerClient(client=http)
            result = await client.poll_relevance_passed()
        assert result.claimed_count == 1
        assert result.transitioned_to == "SCRAPE_QUEUED"
        assert len(result.entries) == 1

    asyncio.run(_run())


def test_post_content_posts_wire_payload() -> None:
    models, client_mod = _load_client_stack()

    async def _run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/entries/content"
            body = json.loads(request.content.decode())
            assert body == {"source_id": "arxiv:2301.00001", "content_raw": "full text body"}
            return httpx.Response(
                200,
                json={"entry_id": "entry-uuid-1", "processing_state": "SCRAPED"},
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            client = client_mod.StateWorkerClient(client=http)
            body = models.ContentPostRequest(
                source_id="arxiv:2301.00001",
                content_raw="full text body",
            )
            result = await client.post_content(body)
        assert result.entry_id == "entry-uuid-1"
        assert result.processing_state == "SCRAPED"

    asyncio.run(_run())


def test_post_failed_posts_wire_payload() -> None:
    models, client_mod = _load_client_stack()

    async def _run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/entries/failed"
            body = json.loads(request.content.decode())
            assert body["source_id"] == "arxiv:2301.00001"
            assert body["state_at_failure"] == "SCRAPE_QUEUED"
            assert body["error_class"] == "RetryExhaustedError"
            assert body["is_retriable"] is True
            return httpx.Response(204)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            client = client_mod.StateWorkerClient(client=http)
            body = models.FailedPostRequest(
                source_id="arxiv:2301.00001",
                state_at_failure="SCRAPE_QUEUED",
                error_class="RetryExhaustedError",
                http_status=503,
                message="retry exhausted",
                is_retriable=True,
            )
            await client.post_failed(body)

    asyncio.run(_run())


def test_poll_raises_on_non_2xx() -> None:
    _, client_mod = _load_client_stack()

    async def _run() -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, json={"detail": "unavailable"})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            client = client_mod.StateWorkerClient(client=http)
            with pytest.raises(httpx.HTTPStatusError):
                await client.poll_relevance_passed()

    asyncio.run(_run())
