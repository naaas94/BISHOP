"""Unit tests for enrichment-batcher stage2_cycle loop (M5 T4)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from bishop_shared.enums import DomainEnum, SourceEnum

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ENRICHMENT_ROOT = _REPO_ROOT / "services" / "enrichment-batcher"
_PROFILE_PATH = _REPO_ROOT / "config/profiles/professional_v1.0.0.yaml"


def _load_enrichment_batcher_stack() -> tuple[ModuleType, ModuleType, ModuleType, ModuleType, ModuleType]:
    saved_app_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "app" or name.startswith("app.")
    }
    for name in saved_app_modules:
        del sys.modules[name]

    repo_str = str(_REPO_ROOT)
    enrichment_str = str(_ENRICHMENT_ROOT)
    path_state: list[str] = []
    for path_str in (enrichment_str, repo_str):
        if path_str not in sys.path:
            sys.path.insert(0, path_str)
            path_state.append(path_str)

    try:
        import app.anthropic_batch_client as anthropic_mod  # noqa: WPS433
        import app.models as models  # noqa: WPS433
        import app.stage1_loop as stage1_mod  # noqa: WPS433
        import app.stage2_loop as loop_mod  # noqa: WPS433
        import app.state_worker_client as client_mod  # noqa: WPS433
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.modules.update(saved_app_modules)
        for path_str in path_state:
            sys.path.remove(path_str)

    return anthropic_mod, loop_mod, models, client_mod, stage1_mod


def _sample_stage2_poll_entry(
    models: ModuleType,
    source_id: str,
    *,
    title: str = "Paper",
    summary: str = "Dense technical summary from Call 1.",
    content_raw: str | None = "Full body that must not appear in Call 2 user message.",
) -> object:
    return models.EntryPollEntry(
        source_id=source_id,
        source=SourceEnum.ARXIV,
        url=f"http://arxiv.org/abs/{source_id}",
        title=title,
        content_raw=content_raw,
        summary=summary,
        domain=DomainEnum.PROFESSIONAL,
        profile_version="1.0.0",
        processing_state="ENRICHMENT_STAGE2_CLAIMED",
    )


def _mock_state_client(
    client_mod: ModuleType,
    models: ModuleType,
    *,
    entries: list[object] | None = None,
    register_error: bool = False,
) -> MagicMock:
    poll_response = models.EntryPollResponse(
        entries=entries or [],
        claimed_count=len(entries or []),
        transitioned_to="ENRICHMENT_STAGE2_CLAIMED" if entries else None,
    )
    client = MagicMock(spec=client_mod.StateWorkerClient)
    client.poll_stage2_queued_entries = AsyncMock(return_value=poll_response)
    if register_error:
        request = httpx.Request("POST", "http://test/batches")
        response = httpx.Response(500, request=request)
        client.register_batch = AsyncMock(
            side_effect=httpx.HTTPStatusError("error", request=request, response=response)
        )
    else:
        client.register_batch = AsyncMock(
            return_value=models.BatchRegisterResponse(batch_id="batch-2", status="submitted")
        )
    client.aclose = AsyncMock()
    return client


def _mock_anthropic_client(anthropic_mod: ModuleType, models: ModuleType) -> MagicMock:
    mock_sdk = MagicMock()
    mock_sdk.messages.batches.create.return_value = SimpleNamespace(id="msgbatch_enrich_2")
    client = anthropic_mod.AnthropicBatchClient(client=mock_sdk)
    return client


@pytest.fixture(autouse=True)
def _reset_g3_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    *_, stage1_mod = _load_enrichment_batcher_stack()
    stage1_mod.reset_g3_gate_for_tests()
    monkeypatch.setenv("BISHOP_G3_VERIFIED", "1")
    yield
    stage1_mod.reset_g3_gate_for_tests()


def test_stage2_cycle_empty_poll_skips_submit() -> None:
    _, loop_mod, models, client_mod, _ = _load_enrichment_batcher_stack()
    state_client = _mock_state_client(client_mod, models, entries=[])
    anthropic_client = MagicMock()

    async def _run() -> None:
        await loop_mod.stage2_cycle(state_client, anthropic_client)

    asyncio.run(_run())
    state_client.register_batch.assert_not_called()
    anthropic_client.submit_stage2_batch.assert_not_called()


def test_stage2_cycle_happy_path_registers_enrichment_stage2_batch() -> None:
    anthropic_mod, loop_mod, models, client_mod, _ = _load_enrichment_batcher_stack()
    source_ids = [f"arxiv:2406.{idx:05d}" for idx in range(1, 4)]
    entries = [
        _sample_stage2_poll_entry(models, sid, title=f"Paper {sid}") for sid in source_ids
    ]
    state_client = _mock_state_client(client_mod, models, entries=entries)
    anthropic_client = _mock_anthropic_client(anthropic_mod, models)

    async def _run() -> None:
        await loop_mod.stage2_cycle(
            state_client,
            anthropic_client,
            profile_path=_PROFILE_PATH,
        )

    asyncio.run(_run())
    state_client.register_batch.assert_called_once()
    register_body = state_client.register_batch.call_args.args[0]
    assert register_body.batch_type == "enrichment_stage2"
    assert register_body.source_ids == source_ids
    assert register_body.external_batch_id == "msgbatch_enrich_2"
    assert register_body.entry_count == 3
    assert register_body.profile_render_hash == loop_mod.load_profile(_PROFILE_PATH).canonical_hash

    profile_prompt = loop_mod.render_profile_prompt(loop_mod.load_profile(_PROFILE_PATH))
    batch_entries = [
        models.Stage2BatchEntry(
            source_id=entry.source_id,
            title=entry.title,
            summary=entry.summary,
        )
        for entry in entries
    ]
    requests = anthropic_client.build_stage2_requests(
        profile_prompt=profile_prompt,
        entries=batch_entries,
    )
    for req, source_id in zip(requests, source_ids, strict=True):
        assert req["custom_id"] == source_id
        assert req["params"]["model"] == "claude-haiku-4-5-20251001"
        user_content = req["params"]["messages"][0]["content"]
        assert user_content.startswith(f"Title: Paper {source_id}\nSummary:")
        assert "Full body" not in user_content
        system_blocks = req["params"]["system"]
        assert system_blocks[0]["cache_control"] == {"type": "ephemeral"}


def test_stage2_cycle_hash_mismatch_aborts_without_anthropic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    anthropic_mod, loop_mod, models, client_mod, _ = _load_enrichment_batcher_stack()
    entries = [_sample_stage2_poll_entry(models, "arxiv:2406.00001")]
    state_client = _mock_state_client(client_mod, models, entries=entries)
    anthropic_client = _mock_anthropic_client(anthropic_mod, models)

    monkeypatch.setattr(
        loop_mod,
        "compute_profile_hash",
        lambda _path: "deadbeef" * 8,
    )

    async def _run() -> None:
        await loop_mod.stage2_cycle(
            state_client,
            anthropic_client,
            profile_path=_PROFILE_PATH,
        )

    asyncio.run(_run())
    state_client.register_batch.assert_not_called()
    anthropic_client._client.messages.batches.create.assert_not_called()


def test_stage2_cycle_state_worker_register_error_after_anthropic_submit() -> None:
    """Falsifier: orphaned Anthropic batch when POST /batches fails (M3 CR-1 pattern)."""
    anthropic_mod, loop_mod, models, client_mod, _ = _load_enrichment_batcher_stack()
    entries = [_sample_stage2_poll_entry(models, "arxiv:2406.00001")]
    state_client = _mock_state_client(client_mod, models, entries=entries, register_error=True)
    anthropic_client = _mock_anthropic_client(anthropic_mod, models)

    async def _run() -> None:
        await loop_mod.stage2_cycle(
            state_client,
            anthropic_client,
            profile_path=_PROFILE_PATH,
        )

    asyncio.run(_run())
    anthropic_client._client.messages.batches.create.assert_called_once()
    state_client.register_batch.assert_called_once()


def test_poll_stage2_queued_entries_uses_stage2_state() -> None:
    _, _, models, client_mod, _ = _load_enrichment_batcher_stack()

    async def _run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/entries/poll"
            assert request.url.params["state"] == "ENRICHMENT_STAGE2_QUEUED"
            assert request.url.params["limit"] == "10"
            return httpx.Response(
                200,
                json={
                    "entries": [],
                    "claimed_count": 0,
                    "transitioned_to": None,
                },
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            client = client_mod.StateWorkerClient(client=http)
            result = await client.poll_stage2_queued_entries()
        assert result.claimed_count == 0

    asyncio.run(_run())


def test_stage2_cycle_poll_http_error_skips_submit() -> None:
    """Falsifier: non-2xx poll must skip Anthropic submit and batch registration."""
    _, loop_mod, _, client_mod, _ = _load_enrichment_batcher_stack()
    client = MagicMock(spec=client_mod.StateWorkerClient)
    request = httpx.Request("GET", "http://test/entries/poll")
    response = httpx.Response(503, request=request)
    client.poll_stage2_queued_entries = AsyncMock(
        side_effect=httpx.HTTPStatusError("error", request=request, response=response)
    )
    client.aclose = AsyncMock()
    anthropic_client = MagicMock()

    async def _run() -> None:
        await loop_mod.stage2_cycle(client, anthropic_client)

    asyncio.run(_run())
    client.register_batch.assert_not_called()
    anthropic_client.submit_stage2_batch.assert_not_called()


def test_stage2_cycle_missing_summary_aborts_batch() -> None:
    """Falsifier: entry without Call 1 summary must not submit Call 2."""
    anthropic_mod, loop_mod, models, client_mod, _ = _load_enrichment_batcher_stack()
    entries = [
        _sample_stage2_poll_entry(models, "arxiv:2406.00001", summary="ok"),
        _sample_stage2_poll_entry(models, "arxiv:2406.00002", summary=None),
    ]
    state_client = _mock_state_client(client_mod, models, entries=entries)
    anthropic_client = _mock_anthropic_client(anthropic_mod, models)

    async def _run() -> None:
        await loop_mod.stage2_cycle(
            state_client,
            anthropic_client,
            profile_path=_PROFILE_PATH,
        )

    asyncio.run(_run())
    state_client.register_batch.assert_not_called()
    anthropic_client._client.messages.batches.create.assert_not_called()
