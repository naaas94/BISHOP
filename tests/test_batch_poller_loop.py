"""Unit tests for batch-poller poll loop (M3 T5)."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType

import httpx
import pytest

from bishop_shared.batch_custom_id import source_id_to_batch_custom_id

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BATCH_POLLER_ROOT = _REPO_ROOT / "services" / "batch-poller"

_NOW = datetime(2026, 6, 13, 14, 0, 0, tzinfo=UTC)
_SUBMITTED_AT = _NOW - timedelta(hours=1)
_TIMEOUT_SUBMITTED_AT = _NOW - timedelta(hours=49)
_BATCH_ID = "batch-poll-1"
_EXTERNAL_ID = "msgbatch_poll_1"
_SOURCE_PASS = "arxiv:2406.00001"
_SOURCE_FAIL = "arxiv:2406.00002"


def _load_loop_stack() -> tuple[ModuleType, ModuleType, ModuleType]:
    saved = {name: mod for name, mod in sys.modules.items() if name == "app" or name.startswith("app.")}
    for name in saved:
        del sys.modules[name]

    path_state: list[str] = []
    for path_str in (str(_BATCH_POLLER_ROOT), str(_REPO_ROOT)):
        if path_str not in sys.path:
            sys.path.insert(0, path_str)
            path_state.append(path_str)

    try:
        import app.clients.state_worker as state_worker_mod  # noqa: WPS433
        import app.loop as loop_mod  # noqa: WPS433
        import app.models as models_mod  # noqa: WPS433
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.modules.update(saved)
        for path_str in path_state:
            sys.path.remove(path_str)

    return state_worker_mod, loop_mod, models_mod


def _batch_wire(
    *,
    batch_id: str = _BATCH_ID,
    submitted_at: datetime = _SUBMITTED_AT,
    status: str = "submitted",
    batch_type: str = "pre_filter",
) -> dict:
    return {
        "batch_id": batch_id,
        "batch_type": batch_type,
        "domain": "professional",
        "profile_version": "1.0.0",
        "profile_render_hash": "b" * 64,
        "status": status,
        "created_at": submitted_at.isoformat().replace("+00:00", "Z"),
        "submitted_at": submitted_at.isoformat().replace("+00:00", "Z"),
        "completed_at": None,
        "entry_count": 2,
        "passed_count": 0,
        "failed_count": 0,
        "source_ids": [_SOURCE_PASS, _SOURCE_FAIL],
        "external_batch_id": _EXTERNAL_ID,
    }


class FakeAnthropicClient:
    def __init__(
        self,
        *,
        processing_status: str = "ended",
        terminal: str | None = "succeeded",
        results: list | None = None,
    ) -> None:
        self.processing_status = processing_status
        self.terminal = terminal
        self.results = results or []
        self.status_calls: list[str] = []
        self.result_calls: list[str] = []

    async def retrieve_batch_status(self, external_batch_id: str) -> tuple[str, str | None]:
        self.status_calls.append(external_batch_id)
        if self.processing_status != "ended":
            return self.processing_status, None
        return "ended", self.terminal

    async def fetch_batch_results(self, external_batch_id: str) -> list:
        self.result_calls.append(external_batch_id)
        return self.results


def test_parse_pre_filter_response_valid_json() -> None:
    _, loop_mod, _ = _load_loop_stack()
    parsed = loop_mod.parse_pre_filter_response(
        _SOURCE_PASS,
        '{"decision": 1, "rationale": "Relevant RAG paper."}',
    )
    assert parsed.decision == 1
    assert parsed.parse_failed is False


def test_parse_pre_filter_response_malformed_json_counts_as_reject() -> None:
    _, loop_mod, _ = _load_loop_stack()
    parsed = loop_mod.parse_pre_filter_response(_SOURCE_FAIL, "not json at all")
    assert parsed.decision == 0
    assert parsed.parse_failed is True
    assert "malformed" in parsed.pre_filter_rationale.lower()


def test_parse_pre_filter_response_tier_absent_pass_defaults_to_core() -> None:
    """Backward compat: profile v1.0.0 omits tier, so a pass normalizes to core."""
    _, loop_mod, _ = _load_loop_stack()
    parsed = loop_mod.parse_pre_filter_response(
        _SOURCE_PASS,
        '{"decision": 1, "rationale": "Relevant RAG paper."}',
    )
    assert parsed.decision == 1
    assert parsed.parse_failed is False
    assert parsed.pre_filter_tier == "core"


def test_parse_pre_filter_response_tier_absent_reject_stays_reject() -> None:
    """Backward compat: a tier-less reject stays a reject with no tier."""
    _, loop_mod, _ = _load_loop_stack()
    parsed = loop_mod.parse_pre_filter_response(
        _SOURCE_FAIL,
        '{"decision": 0, "rationale": "Off topic."}',
    )
    assert parsed.decision == 0
    assert parsed.parse_failed is False
    assert parsed.pre_filter_tier is None


def test_parse_pre_filter_response_peripheral_tier_preserved() -> None:
    _, loop_mod, _ = _load_loop_stack()
    parsed = loop_mod.parse_pre_filter_response(
        _SOURCE_PASS,
        '{"decision": 1, "tier": "peripheral", "rationale": "Worth a skim."}',
    )
    assert parsed.decision == 1
    assert parsed.pre_filter_tier == "peripheral"


def test_parse_pre_filter_response_invalid_tier_on_pass_normalizes_to_core() -> None:
    _, loop_mod, _ = _load_loop_stack()
    for raw_tier in ('"marginal"', "null", "7"):
        parsed = loop_mod.parse_pre_filter_response(
            _SOURCE_PASS,
            f'{{"decision": 1, "tier": {raw_tier}, "rationale": "Relevant."}}',
        )
        assert parsed.decision == 1
        assert parsed.parse_failed is False
        assert parsed.pre_filter_tier == "core"


def test_parse_pre_filter_response_reject_with_tier_forces_null_tier() -> None:
    _, loop_mod, _ = _load_loop_stack()
    parsed = loop_mod.parse_pre_filter_response(
        _SOURCE_FAIL,
        '{"decision": 0, "tier": "core", "rationale": "Off topic."}',
    )
    assert parsed.decision == 0
    assert parsed.pre_filter_tier is None


def test_poll_once_posts_pre_filter_tier_on_wire() -> None:
    """Contract: tier reaches the state-worker payload, null for the rejected entry."""
    state_worker_mod, loop_mod, models_mod = _load_loop_stack()
    posted_entries: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/batches":
            return httpx.Response(200, json={"batches": [_batch_wire()]})
        if request.url.path == "/manifest/pre-filter-results":
            posted_entries.extend(json.loads(request.content)["entries"])
            return httpx.Response(200, json={"updated": 2, "passed": 1, "rejected": 1})
        if request.url.path == f"/batches/{_BATCH_ID}" and request.method == "PATCH":
            return httpx.Response(200, json={"batch": _batch_wire(status="complete")})
        return httpx.Response(404)

    fake_results = [
        models_mod.AnthropicBatchResultItem(
            custom_id=source_id_to_batch_custom_id(_SOURCE_PASS),
            text='{"decision": 1, "tier": "peripheral", "rationale": "Worth a skim."}',
        ),
        models_mod.AnthropicBatchResultItem(
            custom_id=source_id_to_batch_custom_id(_SOURCE_FAIL),
            text='{"decision": 0, "tier": "core", "rationale": "Off topic."}',
        ),
    ]
    anthropic = FakeAnthropicClient(results=fake_results)

    async def _run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            client = state_worker_mod.StateWorkerClient(client=http)
            batch = models_mod.BatchRecordWire.model_validate(_batch_wire())
            await loop_mod.poll_once(client, anthropic, {batch.batch_id: batch}, now=_NOW)

        by_source = {entry["source_id"]: entry for entry in posted_entries}
        assert by_source[_SOURCE_PASS]["pre_filter_tier"] == "peripheral"
        assert by_source[_SOURCE_FAIL]["pre_filter_tier"] is None

    asyncio.run(_run())


def test_poll_once_posts_results_and_patches_complete() -> None:
    state_worker_mod, loop_mod, models_mod = _load_loop_stack()
    patch_calls: list[dict] = []
    results_posted = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal results_posted
        if request.url.path == "/batches":
            return httpx.Response(200, json={"batches": [_batch_wire()]})
        if request.url.path == "/manifest/pre-filter-results":
            results_posted = True
            body = request.read().decode("utf-8")
            assert _BATCH_ID in body
            return httpx.Response(200, json={"updated": 2, "passed": 1, "rejected": 1})
        if request.url.path == f"/batches/{_BATCH_ID}" and request.method == "PATCH":
            patch_calls.append(json.loads(request.content))
            return httpx.Response(200, json={"batch": _batch_wire(status="complete")})
        return httpx.Response(404)

    fake_results = [
        models_mod.AnthropicBatchResultItem(
            custom_id=source_id_to_batch_custom_id(_SOURCE_PASS),
            text='{"decision": 1, "rationale": "Strong RAG content."}',
        ),
        models_mod.AnthropicBatchResultItem(
            custom_id=source_id_to_batch_custom_id(_SOURCE_FAIL),
            text='{"decision": 0, "rationale": "Off topic."}',
        ),
    ]
    anthropic = FakeAnthropicClient(results=fake_results)

    async def _run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            client = state_worker_mod.StateWorkerClient(client=http)
            batch = models_mod.BatchRecordWire.model_validate(_batch_wire())
            tracked = {batch.batch_id: batch}
            await loop_mod.poll_once(client, anthropic, tracked, now=_NOW)

        assert results_posted is True
        assert patch_calls
        final_patch = patch_calls[-1]
        assert final_patch["status"] == "complete"
        assert final_patch["passed_count"] == 1
        assert final_patch["failed_count"] == 1
        assert tracked == {}

    asyncio.run(_run())


def test_poll_once_timeout_calls_post_timeout_endpoint() -> None:
    state_worker_mod, loop_mod, models_mod = _load_loop_stack()
    timeout_called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal timeout_called
        if request.url.path == "/batches":
            return httpx.Response(
                200,
                json={"batches": [_batch_wire(submitted_at=_TIMEOUT_SUBMITTED_AT)]},
            )
        if request.url.path == f"/batches/{_BATCH_ID}/timeout" and request.method == "POST":
            timeout_called = True
            return httpx.Response(
                200,
                json={
                    "batch_id": _BATCH_ID,
                    "status": "batch_timed_out",
                    "entries_reset": 2,
                },
            )
        return httpx.Response(404)

    anthropic = FakeAnthropicClient(processing_status="in_progress")

    async def _run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            client = state_worker_mod.StateWorkerClient(client=http)
            batch = models_mod.BatchRecordWire.model_validate(
                _batch_wire(submitted_at=_TIMEOUT_SUBMITTED_AT),
            )
            tracked = {batch.batch_id: batch}
            await loop_mod.poll_once(client, anthropic, tracked, now=_NOW)

        assert timeout_called is True
        assert tracked == {}
        assert anthropic.status_calls == []

    asyncio.run(_run())


def test_poll_once_pre_filter_results_non_2xx_skips_patch_complete() -> None:
    state_worker_mod, loop_mod, models_mod = _load_loop_stack()
    patch_calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/batches":
            return httpx.Response(200, json={"batches": [_batch_wire()]})
        if request.url.path == "/manifest/pre-filter-results":
            return httpx.Response(409, json={"error": "batch_conflict"})
        if request.url.path == f"/batches/{_BATCH_ID}" and request.method == "PATCH":
            patch_calls.append(json.loads(request.content))
            return httpx.Response(200, json={"batch": _batch_wire(status="processing")})
        return httpx.Response(404)

    fake_results = [
        models_mod.AnthropicBatchResultItem(
            custom_id=source_id_to_batch_custom_id(_SOURCE_PASS),
            text='{"decision": 1, "rationale": "ok"}',
        ),
    ]
    anthropic = FakeAnthropicClient(results=fake_results)

    async def _run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            client = state_worker_mod.StateWorkerClient(client=http)
            batch = models_mod.BatchRecordWire.model_validate(_batch_wire())
            tracked = {batch.batch_id: batch}
            await loop_mod.poll_once(client, anthropic, tracked, now=_NOW)

        complete_patches = [call for call in patch_calls if call.get("status") == "complete"]
        assert complete_patches == []
        assert _BATCH_ID in tracked

    asyncio.run(_run())


def test_poll_once_pre_filter_invalid_transition_marks_batch_failed() -> None:
    state_worker_mod, loop_mod, models_mod = _load_loop_stack()
    patch_calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/batches":
            return httpx.Response(200, json={"batches": [_batch_wire()]})
        if request.url.path == "/manifest/pre-filter-results":
            return httpx.Response(
                409,
                json={
                    "error": "invalid_transition",
                    "source_id": _SOURCE_PASS,
                    "from_state": "DISCOVERED",
                    "to_state": "pre_filter_result",
                },
            )
        if request.url.path == f"/batches/{_BATCH_ID}" and request.method == "PATCH":
            patch_calls.append(json.loads(request.content))
            return httpx.Response(200, json={"batch": _batch_wire(status="failed")})
        return httpx.Response(404)

    fake_results = [
        models_mod.AnthropicBatchResultItem(
            custom_id=source_id_to_batch_custom_id(_SOURCE_PASS),
            text='{"decision": 1, "rationale": "ok"}',
        ),
    ]
    anthropic = FakeAnthropicClient(results=fake_results)

    async def _run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            client = state_worker_mod.StateWorkerClient(client=http)
            batch = models_mod.BatchRecordWire.model_validate(_batch_wire())
            tracked = {batch.batch_id: batch}
            await loop_mod.poll_once(client, anthropic, tracked, now=_NOW)

        assert patch_calls == [{"status": "failed"}]
        assert tracked == {}

    asyncio.run(_run())


def test_poll_once_pre_filter_results_timeout_keeps_batch_tracked() -> None:
    state_worker_mod, loop_mod, models_mod = _load_loop_stack()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/batches":
            return httpx.Response(200, json={"batches": [_batch_wire()]})
        if request.url.path == "/manifest/pre-filter-results":
            raise httpx.ReadTimeout("timed out")
        return httpx.Response(404)

    fake_results = [
        models_mod.AnthropicBatchResultItem(
            custom_id=source_id_to_batch_custom_id(_SOURCE_PASS),
            text='{"decision": 1, "rationale": "ok"}',
        ),
    ]
    anthropic = FakeAnthropicClient(results=fake_results)

    async def _run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            client = state_worker_mod.StateWorkerClient(client=http)
            batch = models_mod.BatchRecordWire.model_validate(_batch_wire())
            tracked = {batch.batch_id: batch}
            await loop_mod.poll_once(client, anthropic, tracked, now=_NOW)

        assert _BATCH_ID in tracked

    asyncio.run(_run())


def test_poll_once_anthropic_failed_patches_batch_failed() -> None:
    state_worker_mod, loop_mod, models_mod = _load_loop_stack()
    patch_calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/batches":
            return httpx.Response(200, json={"batches": [_batch_wire()]})
        if request.url.path == f"/batches/{_BATCH_ID}" and request.method == "PATCH":
            patch_calls.append(json.loads(request.content))
            return httpx.Response(200, json={"batch": _batch_wire(status="failed")})
        return httpx.Response(404)

    anthropic = FakeAnthropicClient(terminal="failed")

    async def _run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            client = state_worker_mod.StateWorkerClient(client=http)
            batch = models_mod.BatchRecordWire.model_validate(_batch_wire())
            tracked = {batch.batch_id: batch}
            await loop_mod.poll_once(client, anthropic, tracked, now=_NOW)

        assert patch_calls == [{"status": "failed"}]
        assert tracked == {}

    asyncio.run(_run())


def test_cache_usage_log_keys_do_not_collide_with_log_record_reserved() -> None:
    _, loop_mod, _ = _load_loop_stack()
    reserved = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__)
    assert loop_mod.CACHE_USAGE_LOG_KEYS.isdisjoint(reserved)


def test_aggregate_batch_cache_usage_sums_across_results() -> None:
    """Falsifier: aggregation must sum all results, not just the first."""
    _, loop_mod, models_mod = _load_loop_stack()
    results = [
        models_mod.AnthropicBatchResultItem(
            custom_id="a",
            input_tokens=100,
            output_tokens=10,
            cache_creation_input_tokens=4000,
            cache_read_input_tokens=0,
        ),
        models_mod.AnthropicBatchResultItem(
            custom_id="b",
            input_tokens=200,
            output_tokens=20,
            cache_creation_input_tokens=0,
            cache_read_input_tokens=3800,
        ),
    ]
    usage = loop_mod.aggregate_batch_cache_usage(results)
    assert usage["input_tokens"] == 300
    assert usage["output_tokens"] == 30
    assert usage["cache_write_tokens"] == 4000
    assert usage["cache_read_tokens"] == 3800
    assert usage["cache_hit_ratio"] == pytest.approx(3800 / 7800)


def test_poll_once_pre_filter_completion_logs_cache_usage_keys(
    caplog: pytest.LogCaptureFixture,
) -> None:
    state_worker_mod, loop_mod, models_mod = _load_loop_stack()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/batches":
            return httpx.Response(200, json={"batches": [_batch_wire()]})
        if request.url.path == "/manifest/pre-filter-results":
            return httpx.Response(200, json={"updated": 2, "passed": 1, "rejected": 1})
        if request.url.path == f"/batches/{_BATCH_ID}" and request.method == "PATCH":
            return httpx.Response(200, json={"batch": _batch_wire(status="complete")})
        return httpx.Response(404)

    fake_results = [
        models_mod.AnthropicBatchResultItem(
            custom_id=source_id_to_batch_custom_id(_SOURCE_PASS),
            text='{"decision": 1, "rationale": "Strong RAG content."}',
            input_tokens=100,
            output_tokens=10,
            cache_creation_input_tokens=0,
            cache_read_input_tokens=5000,
        ),
        models_mod.AnthropicBatchResultItem(
            custom_id=source_id_to_batch_custom_id(_SOURCE_FAIL),
            text='{"decision": 0, "rationale": "Off topic."}',
            input_tokens=100,
            output_tokens=10,
            cache_creation_input_tokens=0,
            cache_read_input_tokens=5000,
        ),
    ]
    anthropic = FakeAnthropicClient(results=fake_results)

    async def _run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            client = state_worker_mod.StateWorkerClient(client=http)
            batch = models_mod.BatchRecordWire.model_validate(_batch_wire())
            tracked = {batch.batch_id: batch}
            with caplog.at_level(logging.INFO, logger="app.loop"):
                await loop_mod.poll_once(client, anthropic, tracked, now=_NOW)

    asyncio.run(_run())

    complete_records = [
        record
        for record in caplog.records
        if record.getMessage() == "batch complete"
    ]
    assert len(complete_records) == 1
    emitted_keys = frozenset(complete_records[0].__dict__)
    for key in loop_mod.CACHE_USAGE_LOG_KEYS:
        assert key in emitted_keys


def test_poll_once_pre_filter_zero_cache_usage_emits_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    state_worker_mod, loop_mod, models_mod = _load_loop_stack()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/batches":
            return httpx.Response(200, json={"batches": [_batch_wire()]})
        if request.url.path == "/manifest/pre-filter-results":
            return httpx.Response(200, json={"updated": 1, "passed": 1, "rejected": 0})
        if request.url.path == f"/batches/{_BATCH_ID}" and request.method == "PATCH":
            return httpx.Response(200, json={"batch": _batch_wire(status="complete")})
        return httpx.Response(404)

    fake_results = [
        models_mod.AnthropicBatchResultItem(
            custom_id=source_id_to_batch_custom_id(_SOURCE_PASS),
            text='{"decision": 1, "rationale": "ok"}',
            input_tokens=100,
            output_tokens=10,
        ),
    ]
    anthropic = FakeAnthropicClient(results=fake_results)

    async def _run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            client = state_worker_mod.StateWorkerClient(client=http)
            batch = models_mod.BatchRecordWire.model_validate(
                {**_batch_wire(), "source_ids": [_SOURCE_PASS]},
            )
            tracked = {batch.batch_id: batch}
            with caplog.at_level(logging.WARNING, logger="app.loop"):
                await loop_mod.poll_once(client, anthropic, tracked, now=_NOW)

    asyncio.run(_run())

    zero_warnings = [
        record
        for record in caplog.records
        if record.getMessage() == "no cache usage reported"
    ]
    assert len(zero_warnings) == 1
    assert zero_warnings[0].event == "cache_read_zero"


def test_poll_once_pre_filter_nonzero_cache_usage_skips_zero_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    state_worker_mod, loop_mod, models_mod = _load_loop_stack()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/batches":
            return httpx.Response(200, json={"batches": [_batch_wire()]})
        if request.url.path == "/manifest/pre-filter-results":
            return httpx.Response(200, json={"updated": 1, "passed": 1, "rejected": 0})
        if request.url.path == f"/batches/{_BATCH_ID}" and request.method == "PATCH":
            return httpx.Response(200, json={"batch": _batch_wire(status="complete")})
        return httpx.Response(404)

    fake_results = [
        models_mod.AnthropicBatchResultItem(
            custom_id=source_id_to_batch_custom_id(_SOURCE_PASS),
            text='{"decision": 1, "rationale": "ok"}',
            cache_read_input_tokens=5000,
        ),
    ]
    anthropic = FakeAnthropicClient(results=fake_results)

    async def _run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            client = state_worker_mod.StateWorkerClient(client=http)
            batch = models_mod.BatchRecordWire.model_validate(
                {**_batch_wire(), "source_ids": [_SOURCE_PASS]},
            )
            tracked = {batch.batch_id: batch}
            with caplog.at_level(logging.WARNING, logger="app.loop"):
                await loop_mod.poll_once(client, anthropic, tracked, now=_NOW)

    asyncio.run(_run())

    zero_warnings = [
        record
        for record in caplog.records
        if record.getMessage() == "no cache usage reported"
    ]
    assert zero_warnings == []


def test_poll_loop_invokes_startup_scan_before_first_cycle() -> None:
    state_worker_mod, loop_mod, _ = _load_loop_stack()
    get_calls = 0
    cycles = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal get_calls
        if request.url.path == "/batches":
            get_calls += 1
            return httpx.Response(200, json={"batches": []})
        return httpx.Response(404)

    async def fake_sleep(_seconds: float) -> None:
        nonlocal cycles
        cycles += 1
        if cycles >= 1:
            raise asyncio.CancelledError

    async def _run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            client = state_worker_mod.StateWorkerClient(client=http)
            anthropic = FakeAnthropicClient()
            with pytest.raises(asyncio.CancelledError):
                await loop_mod.poll_loop(
                    client,
                    anthropic,
                    poll_interval_sec=0.01,
                    sleep_fn=fake_sleep,
                )

        assert get_calls >= 2

    asyncio.run(_run())
