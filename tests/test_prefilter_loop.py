"""Unit tests for prefilter_cycle loop (M3 T4)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from bishop_shared.batch_custom_id import source_id_to_batch_custom_id
from bishop_shared.enums import DomainEnum, SourceEnum
from bishop_shared.prompt_cache import CACHE_TTL, cached_system_blocks
from bishop_shared.rubric_assets import load_rubric

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PREFILTER_ROOT = _REPO_ROOT / "services" / "pre-filter-worker"
_PROFILE_PATH = _REPO_ROOT / "config/profiles/professional_v1.0.0.yaml"
_RUBRIC_PATH = _REPO_ROOT / "config/prompts/prefilter_rubric_v1.md"


def _load_prefilter_loop_stack() -> tuple[ModuleType, ModuleType, ModuleType, ModuleType]:
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
        import app.anthropic_batch_client as anthropic_mod  # noqa: WPS433
        import app.loop as loop_mod  # noqa: WPS433
        import app.models as models  # noqa: WPS433
        import app.state_worker_client as client_mod  # noqa: WPS433
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.modules.update(saved_app_modules)
        for path_str in path_state:
            sys.path.remove(path_str)

    return anthropic_mod, loop_mod, models, client_mod


def _sample_poll_entry(models: ModuleType, source_id: str, *, title: str = "Paper") -> object:
    return models.ManifestPollEntry(
        source_id=source_id,
        source=SourceEnum.ARXIV,
        url=f"http://arxiv.org/abs/{source_id}",
        title=title,
        abstract="An abstract.",
        domain=DomainEnum.PROFESSIONAL,
        processing_state="RELEVANCE_QUEUED",
    )


def _mock_state_client(
    client_mod: ModuleType,
    models: ModuleType,
    *,
    entries: list[object] | None = None,
    register_error: bool = False,
) -> MagicMock:
    poll_response = models.ManifestPollResponse(
        entries=entries or [],
        claimed_count=len(entries or []),
        transitioned_to="RELEVANCE_QUEUED" if entries else None,
    )
    client = MagicMock(spec=client_mod.StateWorkerClient)
    client.poll_discovered_manifest = AsyncMock(return_value=poll_response)
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
    mock_sdk.messages.batches.create.return_value = SimpleNamespace(id="msgbatch_test_1")
    client = anthropic_mod.AnthropicBatchClient(client=mock_sdk)
    return client


@pytest.fixture(autouse=True)
def _reset_g3_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    _, loop_mod, _, _ = _load_prefilter_loop_stack()
    loop_mod.reset_g3_gate_for_tests()
    monkeypatch.setenv("BISHOP_G3_VERIFIED", "1")
    yield
    loop_mod.reset_g3_gate_for_tests()


def test_prefilter_cycle_empty_poll_skips_submit() -> None:
    _, loop_mod, models, client_mod = _load_prefilter_loop_stack()
    state_client = _mock_state_client(client_mod, models, entries=[])
    anthropic_client = MagicMock()

    async def _run() -> None:
        await loop_mod.prefilter_cycle(state_client, anthropic_client)

    asyncio.run(_run())
    state_client.register_batch.assert_not_called()
    anthropic_client.submit_pre_filter_batch.assert_not_called()


def test_prefilter_cycle_hash_mismatch_aborts_without_anthropic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    anthropic_mod, loop_mod, models, client_mod = _load_prefilter_loop_stack()
    monkeypatch.setattr(loop_mod, "PREFILTER_MIN_BATCH_SIZE", 1)
    entries = [_sample_poll_entry(models, "arxiv:2406.00001")]
    state_client = _mock_state_client(client_mod, models, entries=entries)
    anthropic_client = _mock_anthropic_client(anthropic_mod, models)

    monkeypatch.setattr(
        loop_mod,
        "compute_profile_hash",
        lambda _path: "deadbeef" * 8,
    )

    async def _run() -> None:
        await loop_mod.prefilter_cycle(
            state_client,
            anthropic_client,
            profile_path=_PROFILE_PATH,
            rubric_path=_RUBRIC_PATH,
        )

    asyncio.run(_run())
    state_client.register_batch.assert_not_called()
    anthropic_client._client.messages.batches.create.assert_not_called()


def test_prefilter_cycle_rubric_hash_mismatch_aborts_with_critical_alert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """§2 row 12: tampered rubric aborts before Anthropic and emits CRITICAL."""
    anthropic_mod, loop_mod, models, client_mod = _load_prefilter_loop_stack()
    monkeypatch.setattr(loop_mod, "PREFILTER_MIN_BATCH_SIZE", 1)
    entries = [_sample_poll_entry(models, "arxiv:2406.00001")]
    state_client = _mock_state_client(client_mod, models, entries=entries)
    anthropic_client = _mock_anthropic_client(anthropic_mod, models)

    monkeypatch.setattr(
        loop_mod,
        "compute_rubric_hash",
        lambda _path: "deadbeef" * 8,
    )

    with patch.object(loop_mod.logger, "critical") as mock_critical:
        async def _run() -> None:
            await loop_mod.prefilter_cycle(
                state_client,
                anthropic_client,
                profile_path=_PROFILE_PATH,
                rubric_path=_RUBRIC_PATH,
            )

        asyncio.run(_run())

    state_client.register_batch.assert_not_called()
    anthropic_client._client.messages.batches.create.assert_not_called()
    mock_critical.assert_called_once()
    assert mock_critical.call_args.kwargs["extra"]["alert_type"] == "rubric_hash_mismatch"


def test_prefilter_cycle_happy_path_registers_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    anthropic_mod, loop_mod, models, client_mod = _load_prefilter_loop_stack()
    monkeypatch.setattr(loop_mod, "PREFILTER_MIN_BATCH_SIZE", 1)
    source_ids = [f"arxiv:2406.{idx:05d}" for idx in range(1, 4)]
    entries = [_sample_poll_entry(models, sid, title=f"Paper {sid}") for sid in source_ids]
    state_client = _mock_state_client(client_mod, models, entries=entries)
    anthropic_client = _mock_anthropic_client(anthropic_mod, models)

    async def _run() -> None:
        await loop_mod.prefilter_cycle(
            state_client,
            anthropic_client,
            profile_path=_PROFILE_PATH,
            rubric_path=_RUBRIC_PATH,
        )

    asyncio.run(_run())
    state_client.register_batch.assert_called_once()
    register_body = state_client.register_batch.call_args.args[0]
    assert register_body.batch_type == "pre_filter"
    assert register_body.source_ids == source_ids
    assert register_body.external_batch_id == "msgbatch_test_1"
    assert register_body.entry_count == 3
    assert register_body.profile_render_hash == loop_mod.load_profile(_PROFILE_PATH).canonical_hash

    profile_prompt = loop_mod.render_profile_prompt(loop_mod.load_profile(_PROFILE_PATH))
    rubric_body = load_rubric(_RUBRIC_PATH).body
    expected_blocks = cached_system_blocks(profile_prompt, rubric_body)
    requests = anthropic_client.build_requests(
        system_blocks=expected_blocks,
        entries=[
            models.PreFilterBatchEntry(
                source_id=entry.source_id,
                title=entry.title,
                abstract=entry.abstract,
            )
            for entry in entries
        ],
    )
    for req, source_id in zip(requests, source_ids, strict=True):
        assert req["custom_id"] == source_id_to_batch_custom_id(source_id)
    wire_system = anthropic_client._client.messages.batches.create.call_args.kwargs["requests"][0][
        "params"
    ]["system"]
    assert wire_system == expected_blocks
    cache_indices = [idx for idx, block in enumerate(wire_system) if "cache_control" in block]
    assert cache_indices == [len(wire_system) - 1]
    assert wire_system[-1]["cache_control"] == {"type": "ephemeral", "ttl": CACHE_TTL}


def test_prefilter_cycle_twenty_entry_batch_assembly(monkeypatch: pytest.MonkeyPatch) -> None:
    """Contract: 20-entry sample via fixture loop test."""
    anthropic_mod, loop_mod, models, client_mod = _load_prefilter_loop_stack()
    monkeypatch.setattr(loop_mod, "PREFILTER_MIN_BATCH_SIZE", 1)
    source_ids = [f"arxiv:2406.{idx:05d}" for idx in range(1, 21)]
    entries = [_sample_poll_entry(models, sid) for sid in source_ids]
    state_client = _mock_state_client(client_mod, models, entries=entries)
    anthropic_client = _mock_anthropic_client(anthropic_mod, models)

    async def _run() -> None:
        await loop_mod.prefilter_cycle(
            state_client,
            anthropic_client,
            profile_path=_PROFILE_PATH,
            rubric_path=_RUBRIC_PATH,
        )

    asyncio.run(_run())
    register_body = state_client.register_batch.call_args.args[0]
    assert register_body.entry_count == 20
    assert len(register_body.source_ids) == 20


def test_prefilter_cycle_state_worker_register_error_skips_after_anthropic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    anthropic_mod, loop_mod, models, client_mod = _load_prefilter_loop_stack()
    monkeypatch.setattr(loop_mod, "PREFILTER_MIN_BATCH_SIZE", 1)
    entries = [_sample_poll_entry(models, "arxiv:2406.00001")]
    state_client = _mock_state_client(client_mod, models, entries=entries, register_error=True)
    anthropic_client = _mock_anthropic_client(anthropic_mod, models)

    async def _run() -> None:
        await loop_mod.prefilter_cycle(
            state_client,
            anthropic_client,
            profile_path=_PROFILE_PATH,
            rubric_path=_RUBRIC_PATH,
        )

    asyncio.run(_run())
    anthropic_client._client.messages.batches.create.assert_called_once()
    state_client.register_batch.assert_called_once()


def test_prefilter_cycle_anthropic_400_skips_batch_registration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Falsifier: model_string_fatal must not register a batch with state-worker."""
    anthropic_mod, loop_mod, models, client_mod = _load_prefilter_loop_stack()
    monkeypatch.setattr(loop_mod, "PREFILTER_MIN_BATCH_SIZE", 1)
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
        await loop_mod.prefilter_cycle(
            state_client,
            anthropic_client,
            profile_path=_PROFILE_PATH,
            rubric_path=_RUBRIC_PATH,
        )

    asyncio.run(_run())
    mock_sdk.messages.batches.create.assert_called_once()
    state_client.register_batch.assert_not_called()


def _mock_state_client_sequence(
    client_mod: ModuleType,
    models: ModuleType,
    *,
    poll_entries_sequence: list[list[object]],
) -> MagicMock:
    """State client whose poll returns a different entry list on each successive call."""
    responses = [
        models.ManifestPollResponse(
            entries=entries,
            claimed_count=len(entries),
            transitioned_to="RELEVANCE_QUEUED" if entries else None,
        )
        for entries in poll_entries_sequence
    ]
    client = MagicMock(spec=client_mod.StateWorkerClient)
    client.poll_discovered_manifest = AsyncMock(side_effect=responses)
    client.register_batch = AsyncMock(
        return_value=models.BatchRegisterResponse(batch_id="batch-1", status="submitted")
    )
    client.aclose = AsyncMock()
    return client


def test_prefilter_cycle_holds_batch_below_minimum_volume_then_submits_on_volume(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Falsifier for row 18/19: entries below MIN_BATCH_SIZE are held, not submitted,
    and later cycles accumulate onto the same held set until the minimum is met."""
    anthropic_mod, loop_mod, models, client_mod = _load_prefilter_loop_stack()
    monkeypatch.setattr(loop_mod, "PREFILTER_MIN_BATCH_SIZE", 5)
    monkeypatch.setattr(loop_mod, "PREFILTER_MAX_HOLD_MINUTES", 120)

    first_batch = [_sample_poll_entry(models, "arxiv:2406.00001")]
    second_batch = [
        _sample_poll_entry(models, f"arxiv:2406.{idx:05d}") for idx in range(2, 6)
    ]
    state_client = _mock_state_client_sequence(
        client_mod, models, poll_entries_sequence=[first_batch, second_batch]
    )
    anthropic_client = _mock_anthropic_client(anthropic_mod, models)

    async def _run() -> None:
        await loop_mod.prefilter_cycle(
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


def test_prefilter_cycle_submits_below_minimum_after_max_hold_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Falsifier for row 19 (no starvation): a single entry below MIN_BATCH_SIZE is
    submitted once MAX_HOLD_MINUTES has elapsed since it started being held."""
    anthropic_mod, loop_mod, models, client_mod = _load_prefilter_loop_stack()
    monkeypatch.setattr(loop_mod, "PREFILTER_MIN_BATCH_SIZE", 25)
    monkeypatch.setattr(loop_mod, "PREFILTER_MAX_HOLD_MINUTES", 10)

    entries = [_sample_poll_entry(models, "arxiv:2406.00001")]
    state_client = _mock_state_client_sequence(
        client_mod, models, poll_entries_sequence=[entries, []]
    )
    anthropic_client = _mock_anthropic_client(anthropic_mod, models)

    fake_now = {"t": 1_000.0}
    monkeypatch.setattr(loop_mod, "_now", lambda: fake_now["t"])

    async def _run() -> None:
        await loop_mod.prefilter_cycle(
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


def test_prefilter_cycle_hash_abort_does_not_extend_hold_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Negative falsifier for C9: a hash-mismatch abort while held must not push the
    hold deadline forward. If it did, the second (post-deadline) cycle below would
    incorrectly hold again instead of submitting once the hash is fixed."""
    anthropic_mod, loop_mod, models, client_mod = _load_prefilter_loop_stack()
    monkeypatch.setattr(loop_mod, "PREFILTER_MIN_BATCH_SIZE", 25)
    monkeypatch.setattr(loop_mod, "PREFILTER_MAX_HOLD_MINUTES", 10)

    entries = [_sample_poll_entry(models, "arxiv:2406.00001")]
    state_client = _mock_state_client_sequence(
        client_mod, models, poll_entries_sequence=[entries, [], []]
    )
    anthropic_client = _mock_anthropic_client(anthropic_mod, models)

    fake_now = {"t": 1_000.0}
    monkeypatch.setattr(loop_mod, "_now", lambda: fake_now["t"])

    async def _run() -> None:
        await loop_mod.prefilter_cycle(
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


def test_ensure_g3_verified_blocks_without_bypass_or_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _, loop_mod, _, _ = _load_prefilter_loop_stack()
    loop_mod.reset_g3_gate_for_tests()
    monkeypatch.setattr(loop_mod, "G3_DEV_BYPASS", False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    assert loop_mod.ensure_g3_verified() is False
    assert loop_mod.ensure_g3_verified() is False
