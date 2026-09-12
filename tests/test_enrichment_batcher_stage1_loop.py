"""Unit tests for enrichment-batcher stage1_cycle loop (M5 T3; rubric hash-or-abort
and cache key B wiring: prompt-caching T6)."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import bishop_shared.rubric_assets as rubric_assets_mod
from bishop_shared.enums import DomainEnum, SourceEnum
from bishop_shared.batch_custom_id import source_id_to_batch_custom_id

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ENRICHMENT_ROOT = _REPO_ROOT / "services" / "enrichment-batcher"
_PROFILE_PATH = _REPO_ROOT / "config/profiles/professional_v1.0.0.yaml"
_RUBRIC_PATH = _REPO_ROOT / "config/prompts/call1_rubric_v1.md"
_BAD_HASH = "0" * 64


def _load_enrichment_batcher_stack() -> tuple[ModuleType, ModuleType, ModuleType, ModuleType]:
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
        import app.stage1_loop as loop_mod  # noqa: WPS433
        import app.state_worker_client as client_mod  # noqa: WPS433
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.modules.update(saved_app_modules)
        for path_str in path_state:
            sys.path.remove(path_str)

    return anthropic_mod, loop_mod, models, client_mod


def _sample_poll_entry(
    models: ModuleType,
    source_id: str,
    *,
    title: str = "Paper",
    content: str = "Abstract\n\nBody text for truncation.",
) -> object:
    return models.EntryPollEntry(
        source_id=source_id,
        source=SourceEnum.ARXIV,
        url=f"http://arxiv.org/abs/{source_id}",
        title=title,
        content_raw=content,
        domain=DomainEnum.PROFESSIONAL,
        profile_version="1.0.0",
        processing_state="ENRICHMENT_STAGE1_QUEUED",
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
        transitioned_to="ENRICHMENT_STAGE1_QUEUED" if entries else None,
    )
    client = MagicMock(spec=client_mod.StateWorkerClient)
    client.poll_scraped_entries = AsyncMock(return_value=poll_response)
    if register_error:
        request = httpx.Request("POST", "http://test/batches")
        response = httpx.Response(500, request=request)
        client.register_batch = AsyncMock(
            side_effect=httpx.HTTPStatusError("error", request=request, response=response)
        )
    else:
        client.register_batch = AsyncMock(
            return_value=models.BatchRegisterResponse(batch_id="batch-1", status="submitted")
        )
    client.aclose = AsyncMock()
    return client


def _mock_anthropic_client(anthropic_mod: ModuleType, models: ModuleType) -> MagicMock:
    mock_sdk = MagicMock()
    mock_sdk.messages.batches.create.return_value = SimpleNamespace(id="msgbatch_enrich_1")
    client = anthropic_mod.AnthropicBatchClient(client=mock_sdk)
    return client


@pytest.fixture(autouse=True)
def _reset_g3_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    _, loop_mod, _, _ = _load_enrichment_batcher_stack()
    loop_mod.reset_g3_gate_for_tests()
    monkeypatch.setenv("BISHOP_G3_VERIFIED", "1")
    yield
    loop_mod.reset_g3_gate_for_tests()


@pytest.fixture(autouse=True)
def _patch_rubric_container_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """build_call1_system_prompt (called inside build_requests, no override
    param — row 5) resolves the call1 rubric via the container path
    (/app/config/prompts). Point the container dir at the real repo asset so
    tests that reach a live batch build run outside the Docker image."""
    monkeypatch.setattr(
        rubric_assets_mod, "PROMPTS_CONTAINER_DIR", _REPO_ROOT / "config" / "prompts"
    )


def _write_tampered_rubric(tmp_path: Path) -> Path:
    path = tmp_path / "call1_rubric_v1.md"
    path.write_text(
        f'---\nrubric_id: call1_rubric\nversion: "1.0.0"\ncanonical_hash: "{_BAD_HASH}"\n'
        "---\nTampered body — does not match the stamped hash.\n",
        encoding="utf-8",
    )
    return path


def test_stage1_cycle_empty_poll_skips_submit() -> None:
    _, loop_mod, models, client_mod = _load_enrichment_batcher_stack()
    state_client = _mock_state_client(client_mod, models, entries=[])
    anthropic_client = MagicMock()

    async def _run() -> None:
        await loop_mod.stage1_cycle(state_client, anthropic_client)

    asyncio.run(_run())
    state_client.register_batch.assert_not_called()
    anthropic_client.submit_stage1_batch.assert_not_called()


def test_stage1_cycle_happy_path_registers_enrichment_stage1_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    anthropic_mod, loop_mod, models, client_mod = _load_enrichment_batcher_stack()
    monkeypatch.setattr(loop_mod, "ENRICHMENT_STAGE1_MIN_BATCH_SIZE", 1)
    source_ids = [f"arxiv:2406.{idx:05d}" for idx in range(1, 4)]
    entries = [_sample_poll_entry(models, sid, title=f"Paper {sid}") for sid in source_ids]
    state_client = _mock_state_client(client_mod, models, entries=entries)
    anthropic_client = _mock_anthropic_client(anthropic_mod, models)

    async def _run() -> None:
        await loop_mod.stage1_cycle(
            state_client,
            anthropic_client,
            profile_path=_PROFILE_PATH,
            rubric_path=_RUBRIC_PATH,
        )

    asyncio.run(_run())
    state_client.register_batch.assert_called_once()
    register_body = state_client.register_batch.call_args.args[0]
    assert register_body.batch_type == "enrichment_stage1"
    assert register_body.source_ids == source_ids
    assert register_body.external_batch_id == "msgbatch_enrich_1"
    assert register_body.entry_count == 3
    assert register_body.profile_render_hash == loop_mod.load_profile(_PROFILE_PATH).canonical_hash

    batch_entries = [
        models.Stage1BatchEntry(
            source_id=entry.source_id,
            source=entry.source,
            title=entry.title,
            truncated_content=loop_mod.truncate_content_for_call1(
                entry.source.value,
                entry.title,
                entry.content_raw,
            ),
        )
        for entry in entries
    ]
    requests = anthropic_client.build_requests(entries=batch_entries)
    for req, source_id in zip(requests, source_ids, strict=True):
        assert req["custom_id"] == source_id_to_batch_custom_id(source_id)
        assert req["params"]["model"] == "claude-haiku-4-5-20251001"


def test_stage1_cycle_state_worker_register_error_after_anthropic_submit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Falsifier: orphaned Anthropic batch when POST /batches fails (M3 CR-1 pattern)."""
    anthropic_mod, loop_mod, models, client_mod = _load_enrichment_batcher_stack()
    monkeypatch.setattr(loop_mod, "ENRICHMENT_STAGE1_MIN_BATCH_SIZE", 1)
    entries = [_sample_poll_entry(models, "arxiv:2406.00001")]
    state_client = _mock_state_client(client_mod, models, entries=entries, register_error=True)
    anthropic_client = _mock_anthropic_client(anthropic_mod, models)

    async def _run() -> None:
        await loop_mod.stage1_cycle(
            state_client,
            anthropic_client,
            profile_path=_PROFILE_PATH,
            rubric_path=_RUBRIC_PATH,
        )

    asyncio.run(_run())
    anthropic_client._client.messages.batches.create.assert_called_once()
    state_client.register_batch.assert_called_once()


def test_stage1_cycle_anthropic_400_skips_batch_registration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Falsifier: model_string_fatal must not register a batch with state-worker."""
    anthropic_mod, loop_mod, models, client_mod = _load_enrichment_batcher_stack()
    monkeypatch.setattr(loop_mod, "ENRICHMENT_STAGE1_MIN_BATCH_SIZE", 1)
    entries = [_sample_poll_entry(models, "arxiv:2406.00001")]
    state_client = _mock_state_client(client_mod, models, entries=entries)

    mock_sdk = MagicMock()
    from anthropic import BadRequestError

    mock_sdk.messages.batches.create.side_effect = BadRequestError(
        message="invalid model",
        response=MagicMock(status_code=400),
        body={"error": {"message": "invalid model"}},
    )
    anthropic_client = anthropic_mod.AnthropicBatchClient(client=mock_sdk)

    async def _run() -> None:
        await loop_mod.stage1_cycle(
            state_client,
            anthropic_client,
            profile_path=_PROFILE_PATH,
            rubric_path=_RUBRIC_PATH,
        )

    asyncio.run(_run())
    mock_sdk.messages.batches.create.assert_called_once()
    state_client.register_batch.assert_not_called()


def test_poll_scraped_entries_uses_scraped_state() -> None:
    _, _, models, client_mod = _load_enrichment_batcher_stack()

    async def _run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/entries/poll"
            assert request.url.params["state"] == "SCRAPED"
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
            result = await client.poll_scraped_entries()
        assert result.claimed_count == 0

    asyncio.run(_run())


def test_stage1_cycle_poll_http_error_skips_submit() -> None:
    """Falsifier: non-2xx poll must skip Anthropic submit and batch registration."""
    _, loop_mod, _, client_mod = _load_enrichment_batcher_stack()
    client = MagicMock(spec=client_mod.StateWorkerClient)
    request = httpx.Request("GET", "http://test/entries/poll")
    response = httpx.Response(503, request=request)
    client.poll_scraped_entries = AsyncMock(
        side_effect=httpx.HTTPStatusError("error", request=request, response=response)
    )
    client.aclose = AsyncMock()
    anthropic_client = MagicMock()

    async def _run() -> None:
        await loop_mod.stage1_cycle(client, anthropic_client)

    asyncio.run(_run())
    client.register_batch.assert_not_called()
    anthropic_client.submit_stage1_batch.assert_not_called()


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
            transitioned_to="ENRICHMENT_STAGE1_QUEUED" if entries else None,
        )
        for entries in poll_entries_sequence
    ]
    client = MagicMock(spec=client_mod.StateWorkerClient)
    client.poll_scraped_entries = AsyncMock(side_effect=responses)
    client.register_batch = AsyncMock(
        return_value=models.BatchRegisterResponse(batch_id="batch-1", status="submitted")
    )
    client.aclose = AsyncMock()
    return client


def test_stage1_cycle_holds_batch_below_minimum_volume_then_submits_on_volume() -> None:
    """Falsifier for row 18/19: entries below MIN_BATCH_SIZE are held, not submitted,
    and later cycles accumulate onto the same held set until the minimum is met."""
    anthropic_mod, loop_mod, models, client_mod = _load_enrichment_batcher_stack()
    loop_mod.ENRICHMENT_STAGE1_MIN_BATCH_SIZE = 5
    loop_mod.ENRICHMENT_STAGE1_MAX_HOLD_MINUTES = 120

    first_batch = [_sample_poll_entry(models, "arxiv:2406.00001")]
    second_batch = [
        _sample_poll_entry(models, f"arxiv:2406.{idx:05d}") for idx in range(2, 6)
    ]
    state_client = _mock_state_client_sequence(
        client_mod, models, poll_entries_sequence=[first_batch, second_batch]
    )
    anthropic_client = _mock_anthropic_client(anthropic_mod, models)

    async def _run() -> None:
        await loop_mod.stage1_cycle(
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


def test_stage1_cycle_submits_below_minimum_after_max_hold_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Falsifier for row 19 (no starvation): a single entry below MIN_BATCH_SIZE is
    submitted once MAX_HOLD_MINUTES has elapsed since it started being held."""
    anthropic_mod, loop_mod, models, client_mod = _load_enrichment_batcher_stack()
    loop_mod.ENRICHMENT_STAGE1_MIN_BATCH_SIZE = 10
    loop_mod.ENRICHMENT_STAGE1_MAX_HOLD_MINUTES = 10

    entries = [_sample_poll_entry(models, "arxiv:2406.00001")]
    state_client = _mock_state_client_sequence(
        client_mod, models, poll_entries_sequence=[entries, []]
    )
    anthropic_client = _mock_anthropic_client(anthropic_mod, models)

    fake_now = {"t": 1_000.0}
    monkeypatch.setattr(loop_mod, "_now", lambda: fake_now["t"])

    async def _run() -> None:
        await loop_mod.stage1_cycle(
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


def test_stage1_cycle_g3_abort_does_not_extend_hold_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Negative falsifier for C9: an abort while held (here, the G3 gate) must not
    push the hold deadline forward. (T6 adds stage 1's own rubric-hash abort with an
    identical C9 obligation, covered separately by
    ``test_stage1_cycle_rubric_abort_does_not_extend_hold_deadline`` below.)"""
    anthropic_mod, loop_mod, models, client_mod = _load_enrichment_batcher_stack()
    loop_mod.ENRICHMENT_STAGE1_MIN_BATCH_SIZE = 25
    loop_mod.ENRICHMENT_STAGE1_MAX_HOLD_MINUTES = 10

    entries = [_sample_poll_entry(models, "arxiv:2406.00001")]
    state_client = _mock_state_client_sequence(
        client_mod, models, poll_entries_sequence=[entries, [], []]
    )
    anthropic_client = _mock_anthropic_client(anthropic_mod, models)

    fake_now = {"t": 1_000.0}
    monkeypatch.setattr(loop_mod, "_now", lambda: fake_now["t"])

    async def _run() -> None:
        await loop_mod.stage1_cycle(
            state_client,
            anthropic_client,
            profile_path=_PROFILE_PATH,
            rubric_path=_RUBRIC_PATH,
        )

    # Cycle 1: entry held, deadline not reached (t = 1000).
    asyncio.run(_run())
    assert loop_mod._hold_started_at == 1_000.0

    # Advance past the deadline and force the G3 gate closed: the attempt aborts
    # before submit, but hold_started_at must remain at its original value.
    fake_now["t"] = 1_000.0 + (10 * 60) + 1
    loop_mod.reset_g3_gate_for_tests()
    monkeypatch.setattr(loop_mod, "G3_DEV_BYPASS", False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    asyncio.run(_run())
    state_client.register_batch.assert_not_called()
    anthropic_client._client.messages.batches.create.assert_not_called()
    assert loop_mod._hold_started_at == 1_000.0

    # Restore G3 bypass and retry at the same "now". If the abort above had reset
    # hold_started_at, the deadline would no longer be elapsed and this would hold.
    monkeypatch.setattr(loop_mod, "G3_DEV_BYPASS", True)
    asyncio.run(_run())
    state_client.register_batch.assert_called_once()
    register_body = state_client.register_batch.call_args.args[0]
    assert register_body.entry_count == 1


def test_ensure_g3_verified_blocks_without_bypass_or_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _, loop_mod, _, _ = _load_enrichment_batcher_stack()
    loop_mod.reset_g3_gate_for_tests()
    monkeypatch.setattr(loop_mod, "G3_DEV_BYPASS", False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    assert loop_mod.ensure_g3_verified() is False
    assert loop_mod.ensure_g3_verified() is False


# --- prompt-caching T6: stage 1 rubric hash-or-abort (§2 rows 12/13) --------


def test_stage1_cycle_rubric_hash_mismatch_aborts_without_anthropic_call(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Falsifier for row 12: a tampered call1 rubric aborts before Anthropic is ever
    called. Row 12 asymmetry: stage 1 logs an ERROR only — no CRITICAL alert, unlike
    pre-filter's ``emit_profile_hash_mismatch_alert`` path."""
    anthropic_mod, loop_mod, models, client_mod = _load_enrichment_batcher_stack()
    monkeypatch.setattr(loop_mod, "ENRICHMENT_STAGE1_MIN_BATCH_SIZE", 1)
    entries = [_sample_poll_entry(models, "arxiv:2406.00001")]
    state_client = _mock_state_client(client_mod, models, entries=entries)
    anthropic_client = _mock_anthropic_client(anthropic_mod, models)
    tampered_rubric = _write_tampered_rubric(tmp_path)

    async def _run() -> None:
        with caplog.at_level(logging.INFO):
            await loop_mod.stage1_cycle(
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


def test_stage1_cycle_rubric_hash_match_proceeds_to_submit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Positive counterpart: a rubric whose body matches its stamped hash does not
    abort — the cycle reaches Anthropic submit and registration."""
    anthropic_mod, loop_mod, models, client_mod = _load_enrichment_batcher_stack()
    monkeypatch.setattr(loop_mod, "ENRICHMENT_STAGE1_MIN_BATCH_SIZE", 1)
    entries = [_sample_poll_entry(models, "arxiv:2406.00001")]
    state_client = _mock_state_client(client_mod, models, entries=entries)
    anthropic_client = _mock_anthropic_client(anthropic_mod, models)

    async def _run() -> None:
        await loop_mod.stage1_cycle(
            state_client,
            anthropic_client,
            profile_path=_PROFILE_PATH,
            rubric_path=_RUBRIC_PATH,
        )

    asyncio.run(_run())
    anthropic_client._client.messages.batches.create.assert_called_once()
    state_client.register_batch.assert_called_once()


def test_stage1_cycle_rubric_abort_does_not_extend_hold_deadline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Negative falsifier for C9 (stage 1's own copy of the obligation already
    proven for the G3 gate above): a rubric hash abort while held must not push the
    hold deadline forward, else a persistently tampered rubric would starve stage 1
    indefinitely instead of eventually submitting past the deadline."""
    anthropic_mod, loop_mod, models, client_mod = _load_enrichment_batcher_stack()
    loop_mod.ENRICHMENT_STAGE1_MIN_BATCH_SIZE = 25
    loop_mod.ENRICHMENT_STAGE1_MAX_HOLD_MINUTES = 10

    entries = [_sample_poll_entry(models, "arxiv:2406.00001")]
    state_client = _mock_state_client_sequence(
        client_mod, models, poll_entries_sequence=[entries, [], []]
    )
    anthropic_client = _mock_anthropic_client(anthropic_mod, models)
    tampered_rubric = _write_tampered_rubric(tmp_path)

    fake_now = {"t": 1_000.0}
    monkeypatch.setattr(loop_mod, "_now", lambda: fake_now["t"])

    async def _run(rubric_path: Path) -> None:
        await loop_mod.stage1_cycle(
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
    # reset hold_started_at, the deadline would no longer be elapsed and this
    # would hold instead of submitting.
    asyncio.run(_run(_RUBRIC_PATH))
    state_client.register_batch.assert_called_once()
    register_body = state_client.register_batch.call_args.args[0]
    assert register_body.entry_count == 1


def test_profile_render_hash_no_recompute_regression() -> None:
    """Regression for row 13 / C3: stage 1's ``_profile_render_hash`` must keep
    trusting the profile's stamped ``canonical_hash`` with no recompute — adding
    the rubric hash-or-abort in this subtask must not also add a profile hash
    recompute (that stays a separate, still-open contract change per the M5 T4
    log)."""
    _, loop_mod, _, _ = _load_enrichment_batcher_stack()
    result = loop_mod._profile_render_hash(DomainEnum.PROFESSIONAL, profile_path=_PROFILE_PATH)
    assert result == loop_mod.load_profile(_PROFILE_PATH).canonical_hash


def test_profile_render_hash_does_not_import_compute_profile_hash() -> None:
    """Kill-criterion guard: HALT trigger if this subtask's rubric abort quietly
    also wired a profile-hash recompute into stage1_loop (row 13 forbids this)."""
    _, loop_mod, _, _ = _load_enrichment_batcher_stack()
    assert not hasattr(loop_mod, "compute_profile_hash")


def test_stage1_rubric_abort_does_not_propagate_exception_to_gather(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Risk mitigation: stage 1 and stage 2 run in the same service via
    asyncio.gather (app.main.run_scheduler). Stage 1's rubric-hash abort must
    return normally (a plain early ``return``, not a raise) so a sibling
    coroutine gathered alongside it still completes — gather propagates the
    first exception from any task and cancels the rest, so a raise here would
    take stage 2's concurrent cycle down with it."""
    anthropic_mod, loop_mod, models, client_mod = _load_enrichment_batcher_stack()
    monkeypatch.setattr(loop_mod, "ENRICHMENT_STAGE1_MIN_BATCH_SIZE", 1)
    entries = [_sample_poll_entry(models, "arxiv:2406.00001")]
    state_client = _mock_state_client(client_mod, models, entries=entries)
    anthropic_client = _mock_anthropic_client(anthropic_mod, models)
    tampered_rubric = _write_tampered_rubric(tmp_path)

    stage2_stand_in_completed = {"done": False}

    async def _stage2_stand_in() -> None:
        await asyncio.sleep(0)
        stage2_stand_in_completed["done"] = True

    async def _run() -> None:
        await asyncio.gather(
            loop_mod.stage1_cycle(
                state_client,
                anthropic_client,
                profile_path=_PROFILE_PATH,
                rubric_path=tampered_rubric,
            ),
            _stage2_stand_in(),
        )

    asyncio.run(_run())  # must not raise
    anthropic_client._client.messages.batches.create.assert_not_called()
    state_client.register_batch.assert_not_called()
    assert stage2_stand_in_completed["done"] is True


# --- prompt-caching T6: cache key B block shape at the client level --------


def test_build_requests_system_blocks_batch_identity_and_single_breakpoint() -> None:
    """Row 5: ``system`` is a content-block list. Row 10: exactly one
    ``cache_control``, on the last block. Row 11: every request in the batch
    carries byte-identical system blocks."""
    anthropic_mod, _, models, _ = _load_enrichment_batcher_stack()
    anthropic_client = _mock_anthropic_client(anthropic_mod, models)
    batch_entries = [
        models.Stage1BatchEntry(
            source_id=f"arxiv:2406.{idx:05d}",
            source=SourceEnum.ARXIV,
            title=f"Paper {idx}",
            truncated_content="body text",
        )
        for idx in range(3)
    ]

    requests = anthropic_client.build_requests(entries=batch_entries)

    first_system = requests[0]["params"]["system"]
    assert isinstance(first_system, list)
    cache_control_indices = [i for i, b in enumerate(first_system) if "cache_control" in b]
    assert cache_control_indices == [len(first_system) - 1]

    for req in requests[1:]:
        assert req["params"]["system"] == first_system
