"""Unit tests for pre-filter StateWorkerClient (M3 T4)."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import ModuleType

import httpx
import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PREFILTER_ROOT = _REPO_ROOT / "services" / "pre-filter-worker"


def _load_prefilter_client_stack() -> tuple[ModuleType, ModuleType]:
    saved_app_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "app" or name.startswith("app.")
    }
    for name in saved_app_modules:
        del sys.modules[name]

    repo_str = str(_REPO_ROOT)
    prefilter_str = str(_PREFILTER_ROOT)
    path_state: list[str] = []
    for path_str in (prefilter_str, repo_str):
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


def test_poll_discovered_manifest_calls_wire_route() -> None:
    models, client_mod = _load_prefilter_client_stack()

    async def _run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/manifest/poll"
            assert request.url.params["state"] == "DISCOVERED"
            assert request.url.params["limit"] == "50"
            return httpx.Response(
                200,
                json={
                    "entries": [
                        {
                            "source_id": "arxiv:2406.00001",
                            "source": "arxiv",
                            "url": "http://arxiv.org/abs/2406.00001",
                            "title": "Example Paper",
                            "abstract": "An abstract.",
                            "domain": "professional",
                            "processing_state": "RELEVANCE_QUEUED",
                        }
                    ],
                    "claimed_count": 1,
                    "transitioned_to": "RELEVANCE_QUEUED",
                },
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            client = client_mod.StateWorkerClient(client=http)
            result = await client.poll_discovered_manifest()
        assert result.claimed_count == 1
        assert len(result.entries) == 1
        assert result.entries[0].source_id == "arxiv:2406.00001"
        assert result.entries[0].domain == models.DomainEnum.PROFESSIONAL

    asyncio.run(_run())


def test_register_batch_posts_wire_payload() -> None:
    models, client_mod = _load_prefilter_client_stack()

    async def _run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/batches"
            body = json.loads(request.content.decode())
            assert body["batch_type"] == "pre_filter"
            assert body["profile_render_hash"] == "abc123"
            assert body["source_ids"] == ["arxiv:2406.00001"]
            assert body["external_batch_id"] == "msgbatch_ext_1"
            return httpx.Response(201, json={"batch_id": body["batch_id"], "status": "submitted"})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            client = client_mod.StateWorkerClient(client=http)
            body = models.BatchRegisterRequest(
                batch_id="batch-uuid-1",
                domain=models.DomainEnum.PROFESSIONAL,
                profile_version="1.0.0",
                profile_render_hash="abc123",
                source_ids=["arxiv:2406.00001"],
                external_batch_id="msgbatch_ext_1",
                entry_count=1,
            )
            result = await client.register_batch(body)
        assert result.batch_id == "batch-uuid-1"
        assert result.status == "submitted"

    asyncio.run(_run())


def test_poll_raises_on_non_2xx() -> None:
    _, client_mod = _load_prefilter_client_stack()

    async def _run() -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, json={"detail": "unavailable"})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            client = client_mod.StateWorkerClient(client=http)
            with pytest.raises(httpx.HTTPStatusError):
                await client.poll_discovered_manifest()

    asyncio.run(_run())
