"""Unit tests for enrichment-batcher stage2_cycle loop (M5 T4; cache key C
breakpoint move and rubric hash-or-abort: prompt-caching T7-bis)."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from bishop_shared.enums import DomainEnum, SourceEnum
from bishop_shared.batch_custom_id import source_id_to_batch_custom_id
from bishop_shared.prompt_cache import CACHE_TTL

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ENRICHMENT_ROOT = _REPO_ROOT / "services" / "enrichment-batcher"
_PROFILE_PATH = _REPO_ROOT / "config/profiles/professional_v1.0.0.yaml"
_RUBRIC_PATH = _REPO_ROOT / "config/prompts/call2_rubric_v1.md"
_BAD_HASH = "0" * 64


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


def _write_tampered_rubric(tmp_path: Path) -> Path:
    path = tmp_path / "call2_rubric_v1.md"
    path.write_text(
        f'---\nrubric_id: call2_rubric\nversion: "1.0.0"\ncanonical_hash: "{_BAD_HASH}"\n'
        "---\nTampered body — does not match the stamped hash.\n",
        encoding="utf-8",
    )
    return path


def test_stage2_cycle_empty_poll_skips_submit() -> None:
    _, loop_mod, models, client_mod, _ = _load_enrichment_batcher_stack()
    state_client = _mock_state_client(client_mod, models, entries=[])
    anthropic_client = MagicMock()

    async def _run() -> None:
        await loop_mod.stage2_cycle(state_client, anthropic_client)

    asyncio.run(_run())
    state_client.register_batch.assert_not_called()
    anthropic_client.submit_stage2_batch.assert_not_called()


def test_stage2_cycle_happy_path_registers_enrichment_stage2_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    anthropic_mod, loop_mod, models, client_mod, _ = _load_enrichment_batcher_stack()
    monkeypatch.setattr(loop_mod, "ENRICHMENT_STAGE2_MIN_BATCH_SIZE", 1)
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
            rubric_path=_RUBRIC_PATH,
        )

    asyncio.run(_run())
    state_client.register_batch.assert_called_once()
    register_body = state_client.register_batch.call_args.args[0]
    assert register_body.batch_type == "enrichment_stage2"
    assert register_body.source_ids == source_ids
    assert register_body.external_batch_id == "msgbatch_enrich_2"
    assert register_body.entry_count == 3
    assert register_body.profile_render_hash == loop_mod.load_profile(_PROFILE_PATH).canonical_hash

    # Inspect the requests the production path actually built and submitted —
    # not a re-render constructed independently in the test — so a mutation to
    # ``_verify_profile_hash``'s ``include_output`` argument (C4) or to the
    # breakpoint placement (row 10) is caught on the real call path, not on a
    # test-side shadow computation that could drift from it unnoticed.
    create_call = anthropic_client._client.messages.batches.create
    create_call.assert_called_once()
    requests = create_call.call_args.kwargs["requests"]
    for req, source_id in zip(requests, source_ids, strict=True):
        assert req["custom_id"] == source_id_to_batch_custom_id(source_id)
        assert req["params"]["model"] == "claude-haiku-4-5-20251001"
        user_content = req["params"]["messages"][0]["content"]
        assert user_content.startswith(f"Title: Paper {source_id}\nSummary:")
        assert "Full body" not in user_content
        system_blocks = req["params"]["system"]
        # Row 10 falsifier: exactly one cache_control, on the LAST block — a
        # count-only assertion would pass even with the pre-move shape
        # (breakpoint on block 0, no ttl).
        cache_control_indices = [
            i for i, b in enumerate(system_blocks) if "cache_control" in b
        ]
        assert cache_control_indices == [len(system_blocks) - 1]
        assert system_blocks[-1]["cache_control"] == {"type": "ephemeral", "ttl": CACHE_TTL}
        # C4: the gate-1 output contract must not ride along in the cached prefix.
        for block in system_blocks:
            assert '"decision"' not in block["text"]


def test_stage2_cycle_hash_mismatch_aborts_without_anthropic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    anthropic_mod, loop_mod, models, client_mod, _ = _load_enrichment_batcher_stack()
    monkeypatch.setattr(loop_mod, "ENRICHMENT_STAGE2_MIN_BATCH_SIZE", 1)
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


def test_stage2_cycle_state_worker_register_error_after_anthropic_submit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Falsifier: orphaned Anthropic batch when POST /batches fails (M3 CR-1 pattern)."""
    anthropic_mod, loop_mod, models, client_mod, _ = _load_enrichment_batcher_stack()
    monkeypatch.setattr(loop_mod, "ENRICHMENT_STAGE2_MIN_BATCH_SIZE", 1)
    entries = [_sample_stage2_poll_entry(models, "arxiv:2406.00001")]
    state_client = _mock_state_client(client_mod, models, entries=entries, register_error=True)
    anthropic_client = _mock_anthropic_client(anthropic_mod, models)

    async def _run() -> None:
        await loop_mod.stage2_cycle(
            state_client,
            anthropic_client,
            profile_path=_PROFILE_PATH,
            rubric_path=_RUBRIC_PATH,
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
            assert request.url.params["limit"] == "50"
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


def test_stage2_cycle_missing_summary_aborts_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Falsifier: entry without Call 1 summary must not submit Call 2."""
    anthropic_mod, loop_mod, models, client_mod, _ = _load_enrichment_batcher_stack()
    monkeypatch.setattr(loop_mod, "ENRICHMENT_STAGE2_MIN_BATCH_SIZE", 1)
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
            rubric_path=_RUBRIC_PATH,
        )

    asyncio.run(_run())
    state_client.register_batch.assert_not_called()
    anthropic_client._client.messages.batches.create.assert_not_called()


def _mock_state_client_sequence(
    client_mod: ModuleType,
    models: ModuleType,
    *,
    poll_entries_sequence: list[list[object]],
) -> MagicMock:
    """State client whose poll returns a different entry list on each successive call."""
    responses = [
        models.EntryPollResponse(
            entries=entries,
            claimed_count=len(entries),
            transitioned_to="ENRICHMENT_STAGE2_CLAIMED" if entries else None,
        )
        for entries in poll_entries_sequence
    ]
    client = MagicMock(spec=client_mod.StateWorkerClient)
    client.poll_stage2_queued_entries = AsyncMock(side_effect=responses)
    client.register_batch = AsyncMock(
        return_value=models.BatchRegisterResponse(batch_id="batch-2", status="submitted")
    )
    client.aclose = AsyncMock()
    return client


def test_stage2_cycle_holds_batch_below_minimum_volume_then_submits_on_volume() -> None:
    """Falsifier for row 18/19: entries below MIN_BATCH_SIZE are held, not submitted,
    and later cycles accumulate onto the same held set until the minimum is met."""
    anthropic_mod, loop_mod, models, client_mod, _ = _load_enrichment_batcher_stack()
    loop_mod.ENRICHMENT_STAGE2_MIN_BATCH_SIZE = 5
    loop_mod.ENRICHMENT_STAGE2_MAX_HOLD_MINUTES = 120

    first_batch = [_sample_stage2_poll_entry(models, "arxiv:2406.00001")]
    second_batch = [
        _sample_stage2_poll_entry(models, f"arxiv:2406.{idx:05d}") for idx in range(2, 6)
    ]
    state_client = _mock_state_client_sequence(
        client_mod, models, poll_entries_sequence=[first_batch, second_batch]
    )
    anthropic_client = _mock_anthropic_client(anthropic_mod, models)

    async def _run() -> None:
        await loop_mod.stage2_cycle(
            state_client,
            anthropic_client,
            profile_path=_PROFILE_PATH,
            rubric_path=_RUBRIC_PATH,
        )

    # Cycle 1: 1 entry held (below min of 5); no submit.
    asyncio.run(_run())
    state_client.register_batch.assert_not_called()
    anthropic_client._client.messages.batches.create.assert_not_called()
    assert len(loop_mod._pending_entries) == 1

    # Cycle 2: 4 more entries arrive -> total 5 == min -> submits accumulated 5.
    asyncio.run(_run())
    state_client.register_batch.assert_called_once()
    register_body = state_client.register_batch.call_args.args[0]
    assert register_body.entry_count == 5
    assert len(loop_mod._pending_entries) == 0


def test_stage2_cycle_submits_below_minimum_after_max_hold_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Falsifier for row 19 (no starvation): a single entry below MIN_BATCH_SIZE is
    submitted once MAX_HOLD_MINUTES has elapsed since it started being held."""
    anthropic_mod, loop_mod, models, client_mod, _ = _load_enrichment_batcher_stack()
    loop_mod.ENRICHMENT_STAGE2_MIN_BATCH_SIZE = 10
    loop_mod.ENRICHMENT_STAGE2_MAX_HOLD_MINUTES = 10

    entries = [_sample_stage2_poll_entry(models, "arxiv:2406.00001")]
    state_client = _mock_state_client_sequence(
        client_mod, models, poll_entries_sequence=[entries, []]
    )
    anthropic_client = _mock_anthropic_client(anthropic_mod, models)

    fake_now = {"t": 1_000.0}
    monkeypatch.setattr(loop_mod, "_now", lambda: fake_now["t"])

    async def _run() -> None:
        await loop_mod.stage2_cycle(
            state_client,
            anthropic_client,
            profile_path=_PROFILE_PATH,
            rubric_path=_RUBRIC_PATH,
        )

    # Cycle 1: entry held, deadline not reached.
    asyncio.run(_run())
    state_client.register_batch.assert_not_called()

    # Advance time past the 10-minute deadline; second poll is empty (no new arrivals).
    fake_now["t"] = 1_000.0 + (10 * 60) + 1
    asyncio.run(_run())
    state_client.register_batch.assert_called_once()
    register_body = state_client.register_batch.call_args.args[0]
    assert register_body.entry_count == 1


def test_stage2_cycle_hash_abort_does_not_extend_hold_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Negative falsifier for C9: a hash-mismatch abort while held must not push the
    hold deadline forward. If it did, the second (post-deadline) cycle below would
    incorrectly hold again instead of submitting once the hash is fixed."""
    anthropic_mod, loop_mod, models, client_mod, _ = _load_enrichment_batcher_stack()
    loop_mod.ENRICHMENT_STAGE2_MIN_BATCH_SIZE = 25
    loop_mod.ENRICHMENT_STAGE2_MAX_HOLD_MINUTES = 10

    entries = [_sample_stage2_poll_entry(models, "arxiv:2406.00001")]
    state_client = _mock_state_client_sequence(
        client_mod, models, poll_entries_sequence=[entries, [], []]
    )
    anthropic_client = _mock_anthropic_client(anthropic_mod, models)

    fake_now = {"t": 1_000.0}
    monkeypatch.setattr(loop_mod, "_now", lambda: fake_now["t"])

    async def _run() -> None:
        await loop_mod.stage2_cycle(
            state_client,
            anthropic_client,
            profile_path=_PROFILE_PATH,
            rubric_path=_RUBRIC_PATH,
        )

    # Cycle 1: entry held, deadline not reached (t = 1000).
    asyncio.run(_run())
    assert loop_mod._hold_started_at == 1_000.0

    # Advance past the deadline and force a hash mismatch: the attempt aborts before
    # submit, but hold_started_at must remain at its original value (not reset to now).
    fake_now["t"] = 1_000.0 + (10 * 60) + 1
    monkeypatch.setattr(loop_mod, "compute_profile_hash", lambda _path: "deadbeef" * 8)
    asyncio.run(_run())
    state_client.register_batch.assert_not_called()
    anthropic_client._client.messages.batches.create.assert_not_called()
    assert loop_mod._hold_started_at == 1_000.0

    # Fix the hash and retry at the same "now" (barely past deadline). If the abort
    # above had reset hold_started_at to that later "now", the deadline would no
    # longer be considered elapsed and this cycle would incorrectly hold again.
    monkeypatch.setattr(
        loop_mod,
        "compute_profile_hash",
        lambda path: loop_mod.load_profile(path).canonical_hash,
    )
    asyncio.run(_run())
    state_client.register_batch.assert_called_once()
    register_body = state_client.register_batch.call_args.args[0]
    assert register_body.entry_count == 1


# --- prompt-caching T7-bis: cache key C rubric hash-or-abort ----------------


def test_stage2_cycle_rubric_hash_mismatch_aborts_without_anthropic_call(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Falsifier for row 12: a tampered call2 rubric aborts before Anthropic is ever
    called. Row 12 asymmetry: stage 2 logs an ERROR only — no CRITICAL alert, unlike
    pre-filter's ``emit_profile_hash_mismatch_alert`` path."""
    anthropic_mod, loop_mod, models, client_mod, _ = _load_enrichment_batcher_stack()
    monkeypatch.setattr(loop_mod, "ENRICHMENT_STAGE2_MIN_BATCH_SIZE", 1)
    entries = [_sample_stage2_poll_entry(models, "arxiv:2406.00001")]
    state_client = _mock_state_client(client_mod, models, entries=entries)
    anthropic_client = _mock_anthropic_client(anthropic_mod, models)
    tampered_rubric = _write_tampered_rubric(tmp_path)

    async def _run() -> None:
        with caplog.at_level(logging.INFO):
            await loop_mod.stage2_cycle(
                state_client,
                anthropic_client,
                profile_path=_PROFILE_PATH,
                rubric_path=tampered_rubric,
            )

    asyncio.run(_run())
    anthropic_client._client.messages.batches.create.assert_not_called()
    state_client.register_batch.assert_not_called()
    assert any(
        r.levelno == logging.ERROR and getattr(r, "event", None) == "rubric_hash_mismatch"
        for r in caplog.records
    )
    assert not any(r.levelno >= logging.CRITICAL for r in caplog.records)


def test_stage2_cycle_rubric_hash_match_proceeds_to_submit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Positive counterpart: a rubric whose body matches its stamped hash does not
    abort — the cycle reaches Anthropic submit and registration."""
    anthropic_mod, loop_mod, models, client_mod, _ = _load_enrichment_batcher_stack()
    monkeypatch.setattr(loop_mod, "ENRICHMENT_STAGE2_MIN_BATCH_SIZE", 1)
    entries = [_sample_stage2_poll_entry(models, "arxiv:2406.00001")]
    state_client = _mock_state_client(client_mod, models, entries=entries)
    anthropic_client = _mock_anthropic_client(anthropic_mod, models)

    async def _run() -> None:
        await loop_mod.stage2_cycle(
            state_client,
            anthropic_client,
            profile_path=_PROFILE_PATH,
            rubric_path=_RUBRIC_PATH,
        )

    asyncio.run(_run())
    anthropic_client._client.messages.batches.create.assert_called_once()
    state_client.register_batch.assert_called_once()


def test_stage2_cycle_rubric_abort_does_not_extend_hold_deadline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Negative falsifier for C9 (stage 2's own copy of the obligation already proven
    for the profile-hash gate above): a rubric hash abort while held must not push the
    hold deadline forward, else a persistently tampered rubric would starve stage 2
    indefinitely instead of eventually submitting past the deadline."""
    anthropic_mod, loop_mod, models, client_mod, _ = _load_enrichment_batcher_stack()
    loop_mod.ENRICHMENT_STAGE2_MIN_BATCH_SIZE = 25
    loop_mod.ENRICHMENT_STAGE2_MAX_HOLD_MINUTES = 10

    entries = [_sample_stage2_poll_entry(models, "arxiv:2406.00001")]
    state_client = _mock_state_client_sequence(
        client_mod, models, poll_entries_sequence=[entries, [], []]
    )
    anthropic_client = _mock_anthropic_client(anthropic_mod, models)
    tampered_rubric = _write_tampered_rubric(tmp_path)

    fake_now = {"t": 1_000.0}
    monkeypatch.setattr(loop_mod, "_now", lambda: fake_now["t"])

    async def _run(rubric_path: Path) -> None:
        await loop_mod.stage2_cycle(
            state_client,
            anthropic_client,
            profile_path=_PROFILE_PATH,
            rubric_path=rubric_path,
        )

    # Cycle 1: entry held, deadline not reached (t = 1000).
    asyncio.run(_run(tampered_rubric))
    assert loop_mod._hold_started_at == 1_000.0

    # Advance past the deadline with the rubric still tampered: the attempt aborts
    # before submit, but hold_started_at must remain at its original value.
    fake_now["t"] = 1_000.0 + (10 * 60) + 1
    asyncio.run(_run(tampered_rubric))
    state_client.register_batch.assert_not_called()
    anthropic_client._client.messages.batches.create.assert_not_called()
    assert loop_mod._hold_started_at == 1_000.0

    # Restore a valid rubric and retry at the same "now". If the abort above had
    # reset hold_started_at to that later "now", the deadline would no longer be
    # considered elapsed and this cycle would incorrectly hold again.
    asyncio.run(_run(_RUBRIC_PATH))
    state_client.register_batch.assert_called_once()
    register_body = state_client.register_batch.call_args.args[0]
    assert register_body.entry_count == 1
