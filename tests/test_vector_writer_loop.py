"""Unit tests for vector-writer index_cycle loop (M6 T5)."""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from bishop_shared.enums import DomainEnum, SourceEnum

_REPO_ROOT = Path(__file__).resolve().parent.parent
_VECTOR_WRITER_ROOT = _REPO_ROOT / "services" / "vector-writer"


def _load_loop_stack() -> tuple[ModuleType, ModuleType, ModuleType, ModuleType]:
    saved_app_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "app" or name.startswith("app.")
    }
    for name in saved_app_modules:
        del sys.modules[name]

    repo_str = str(_REPO_ROOT)
    worker_str = str(_VECTOR_WRITER_ROOT)
    path_state: list[str] = []
    for path_str in (worker_str, repo_str):
        if path_str not in sys.path:
            sys.path.insert(0, path_str)
            path_state.append(path_str)

    try:
        import app.index_entry as index_mod  # noqa: WPS433
        import app.loop as loop_mod  # noqa: WPS433
        import app.models as models_mod  # noqa: WPS433
        import app.state_worker_client as client_mod  # noqa: WPS433
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.modules.update(saved_app_modules)
        for path_str in path_state:
            sys.path.remove(path_str)

    return loop_mod, models_mod, client_mod, index_mod


def _sample_poll_entry(models: ModuleType) -> object:
    return models.EntryPollRow(
        source_id="arxiv:2401.00001",
        source=SourceEnum.ARXIV,
        url="https://arxiv.org/abs/2401.00001",
        title="Hybrid Retrieval",
        published_at=datetime(2024, 1, 15, tzinfo=UTC),
        ingested_at=datetime(2024, 1, 16, 12, 0, tzinfo=UTC),
        domain=DomainEnum.PROFESSIONAL,
        profile_version="1.0.0",
        pre_filter_batch_id="batch-1",
        pre_filter_rationale="Relevant",
        summary="Dense and sparse search combined.",
        concepts=["vector search"],
        tags=["retrieval"],
        challenge_hooks=["sparse document graphs"],
        relevance_score=0.92,
        processing_state="VECTOR_WRITE_QUEUED",
    )


def _mock_state_client(
    client_mod: ModuleType,
    models: ModuleType,
    *,
    entries: list[object] | None = None,
    poll_error: bool = False,
) -> MagicMock:
    poll_response = models.EntryPollResponse(
        entries=entries or [],
        claimed_count=len(entries or []),
        transitioned_to=None,
    )
    client = MagicMock(spec=client_mod.StateWorkerClient)
    if poll_error:
        request = httpx.Request("GET", "http://test/entries/poll")
        response = httpx.Response(503, request=request)
        client.poll_vector_write_queued = AsyncMock(
            side_effect=httpx.HTTPStatusError("error", request=request, response=response),
        )
    else:
        client.poll_vector_write_queued = AsyncMock(return_value=poll_response)
    client.aclose = AsyncMock()
    return client


def test_poll_client_uses_vector_write_queued_state() -> None:
    _, _, client_mod, _ = _load_loop_stack()

    async def _run() -> None:
        seen_state: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen_state.append(request.url.params["state"])
            assert request.url.params["limit"] == "10"
            return httpx.Response(
                200,
                json={"entries": [], "claimed_count": 0, "transitioned_to": None},
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            client = client_mod.StateWorkerClient(client=http)
            await client.poll_vector_write_queued()
        assert seen_state == ["VECTOR_WRITE_QUEUED"]

    asyncio.run(_run())


def test_index_cycle_empty_poll_skips_index_entry() -> None:
    loop_mod, models, client_mod, index_mod = _load_loop_stack()
    state_client = _mock_state_client(client_mod, models, entries=[])
    stores = MagicMock(spec=index_mod.IndexStores)
    index_entry_mock = AsyncMock()
    original_index_entry = index_mod.index_entry
    index_mod.index_entry = index_entry_mock  # type: ignore[method-assign]

    try:
        async def _run() -> None:
            await loop_mod.index_cycle(state_client=state_client, stores=stores)

        asyncio.run(_run())
        index_entry_mock.assert_not_awaited()
    finally:
        index_mod.index_entry = original_index_entry  # type: ignore[method-assign]


def test_index_cycle_poll_error_skips_index_entry() -> None:
    loop_mod, models, client_mod, index_mod = _load_loop_stack()
    state_client = _mock_state_client(client_mod, models, poll_error=True)
    stores = MagicMock(spec=index_mod.IndexStores)
    index_entry_mock = AsyncMock()
    original_index_entry = index_mod.index_entry
    index_mod.index_entry = index_entry_mock  # type: ignore[method-assign]

    try:
        async def _run() -> None:
            await loop_mod.index_cycle(state_client=state_client, stores=stores)

        asyncio.run(_run())
        index_entry_mock.assert_not_awaited()
    finally:
        index_mod.index_entry = original_index_entry  # type: ignore[method-assign]


def test_index_cycle_indexes_each_polled_entry() -> None:
    loop_mod, models, client_mod, index_mod = _load_loop_stack()
    entries = [_sample_poll_entry(models), _sample_poll_entry(models)]
    entries[1] = models.EntryPollRow.model_validate(
        {**entries[1].model_dump(), "source_id": "arxiv:2401.00002"}
    )
    state_client = _mock_state_client(client_mod, models, entries=entries)
    stores = MagicMock(spec=index_mod.IndexStores)
    indexed: list[str] = []

    async def _fake_index(entry: object, _stores: object, _client: object) -> bool:
        indexed.append(entry.source_id)  # type: ignore[attr-defined]
        return True

    original_index_entry = loop_mod.index_entry
    loop_mod.index_entry = _fake_index  # type: ignore[method-assign]

    try:
        async def _run() -> None:
            await loop_mod.index_cycle(state_client=state_client, stores=stores)

        asyncio.run(_run())
        assert indexed == ["arxiv:2401.00001", "arxiv:2401.00002"]
    finally:
        loop_mod.index_entry = original_index_entry  # type: ignore[method-assign]


def test_post_indexed_posts_wire_payload() -> None:
    _, models, client_mod, _ = _load_loop_stack()

    async def _run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/entries/indexed"
            body = json.loads(request.content.decode())
            assert body == {"source_id": "arxiv:2401.00001"}
            return httpx.Response(204)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            client = client_mod.StateWorkerClient(client=http)
            await client.post_indexed(models.IndexedPostRequest(source_id="arxiv:2401.00001"))

    asyncio.run(_run())
