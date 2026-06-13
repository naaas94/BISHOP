"""Unit tests for batch-poller enrichment dispatch (M5 T5)."""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType

import httpx

from bishop_shared.batch_custom_id import source_id_to_batch_custom_id

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BATCH_POLLER_ROOT = _REPO_ROOT / "services" / "batch-poller"

_NOW = datetime(2026, 6, 13, 14, 0, 0, tzinfo=UTC)
_SUBMITTED_AT = _NOW - timedelta(hours=1)
_TIMEOUT_SUBMITTED_AT = _NOW - timedelta(hours=49)
_STAGE1_BATCH_ID = "enrich-stage1-poll-1"
_STAGE2_BATCH_ID = "enrich-stage2-poll-1"
_EXTERNAL_ID = "msgbatch_enrich_1"
_SOURCE_PASS = "arxiv:2406.00001"
_SOURCE_FAIL = "arxiv:2406.00002"


def _load_enrichment_stack() -> tuple[ModuleType, ModuleType, ModuleType]:
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


def _call1_payload(**overrides: object) -> str:
    base = {
        "summary": "A dense technical summary of hybrid retrieval methods.",
        "concepts": ["retrieval", "graphs", "latency", "embeddings", "indexing"],
        "tags": ["RAG", "hybrid-retrieval"],
        "entry_type": "paper",
        "challenge_hooks": [
            "How to reduce latency in dense retrieval",
            "When to use hybrid sparse-dense pipelines",
        ],
    }
    base.update(overrides)
    return json.dumps(base)


def _call2_payload(**overrides: object) -> str:
    base = {
        "relevance_score": 0.87,
        "relevance_reason": "Directly addresses hybrid retrieval.",
        "value_rationale": "Useful for production RAG tuning.",
    }
    base.update(overrides)
    return json.dumps(base)


def _batch_wire(
    *,
    batch_id: str,
    batch_type: str,
    submitted_at: datetime = _SUBMITTED_AT,
    status: str = "submitted",
) -> dict:
    return {
        "batch_id": batch_id,
        "batch_type": batch_type,
        "domain": "professional",
        "profile_version": "1.0.0",
        "profile_render_hash": "c" * 64,
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


def test_enrichment_batch_type_constants() -> None:
    _, _, models_mod = _load_enrichment_stack()
    assert models_mod.ENRICHMENT_STAGE1_BATCH_TYPE == "enrichment_stage1"
    assert models_mod.ENRICHMENT_STAGE2_BATCH_TYPE == "enrichment_stage2"
    assert models_mod.TRACKED_BATCH_TYPES == frozenset(
        {"pre_filter", "enrichment_stage1", "enrichment_stage2"},
    )


def test_poll_once_enrichment_stage1_posts_results_and_patches_complete() -> None:
    state_worker_mod, loop_mod, models_mod = _load_enrichment_stack()
    patch_calls: list[dict] = []
    results_posted = False
    posted_body: dict | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal results_posted, posted_body
        if request.url.path == "/batches":
            return httpx.Response(
                200,
                json={
                    "batches": [
                        _batch_wire(batch_id=_STAGE1_BATCH_ID, batch_type="enrichment_stage1"),
                    ],
                },
            )
        if request.url.path == "/entries/enrichment-stage1-results":
            results_posted = True
            posted_body = json.loads(request.read().decode("utf-8"))
            return httpx.Response(204)
        if request.url.path == f"/batches/{_STAGE1_BATCH_ID}" and request.method == "PATCH":
            patch_calls.append(json.loads(request.content))
            return httpx.Response(200, json={"batch": _batch_wire(
                batch_id=_STAGE1_BATCH_ID,
                batch_type="enrichment_stage1",
                status="complete",
            )})
        return httpx.Response(404)

    fake_results = [
        models_mod.AnthropicBatchResultItem(
            custom_id=source_id_to_batch_custom_id(_SOURCE_PASS),
            text=_call1_payload(),
        ),
        models_mod.AnthropicBatchResultItem(
            custom_id=source_id_to_batch_custom_id(_SOURCE_FAIL),
            text="not json",
        ),
    ]
    anthropic = FakeAnthropicClient(results=fake_results)

    async def _run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            client = state_worker_mod.StateWorkerClient(client=http)
            batch = models_mod.BatchRecordWire.model_validate(
                _batch_wire(batch_id=_STAGE1_BATCH_ID, batch_type="enrichment_stage1"),
            )
            tracked = {batch.batch_id: batch}
            await loop_mod.poll_once(client, anthropic, tracked, now=_NOW)

        assert results_posted is True
        assert posted_body is not None
        assert posted_body["batch_id"] == _STAGE1_BATCH_ID
        assert len(posted_body["entries"]) == 2
        assert posted_body["entries"][0]["success"] is True
        assert posted_body["entries"][1]["success"] is False
        assert patch_calls
        final_patch = patch_calls[-1]
        assert final_patch["status"] == "complete"
        assert final_patch["passed_count"] == 1
        assert final_patch["failed_count"] == 1
        assert tracked == {}

    asyncio.run(_run())


def test_poll_once_enrichment_stage2_posts_results_and_patches_complete() -> None:
    state_worker_mod, loop_mod, models_mod = _load_enrichment_stack()
    patch_calls: list[dict] = []
    results_posted = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal results_posted
        if request.url.path == "/batches":
            return httpx.Response(
                200,
                json={
                    "batches": [
                        _batch_wire(batch_id=_STAGE2_BATCH_ID, batch_type="enrichment_stage2"),
                    ],
                },
            )
        if request.url.path == "/entries/enrichment-stage2-results":
            results_posted = True
            body = json.loads(request.read().decode("utf-8"))
            assert body["batch_id"] == _STAGE2_BATCH_ID
            assert body["entries"][0]["success"] is True
            return httpx.Response(204)
        if request.url.path == f"/batches/{_STAGE2_BATCH_ID}" and request.method == "PATCH":
            patch_calls.append(json.loads(request.content))
            return httpx.Response(200, json={"batch": _batch_wire(
                batch_id=_STAGE2_BATCH_ID,
                batch_type="enrichment_stage2",
                status="complete",
            )})
        return httpx.Response(404)

    fake_results = [
        models_mod.AnthropicBatchResultItem(
            custom_id=source_id_to_batch_custom_id(_SOURCE_PASS),
            text=_call2_payload(),
        ),
    ]
    anthropic = FakeAnthropicClient(results=fake_results)

    async def _run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            client = state_worker_mod.StateWorkerClient(client=http)
            batch = models_mod.BatchRecordWire.model_validate(
                _batch_wire(
                    batch_id=_STAGE2_BATCH_ID,
                    batch_type="enrichment_stage2",
                ),
            )
            tracked = {batch.batch_id: batch}
            await loop_mod.poll_once(client, anthropic, tracked, now=_NOW)

        assert results_posted is True
        assert patch_calls[-1]["status"] == "complete"
        assert tracked == {}

    asyncio.run(_run())


def test_poll_once_enrichment_stage1_results_non_2xx_skips_patch_complete() -> None:
    state_worker_mod, loop_mod, models_mod = _load_enrichment_stack()
    patch_calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/batches":
            return httpx.Response(
                200,
                json={
                    "batches": [
                        _batch_wire(batch_id=_STAGE1_BATCH_ID, batch_type="enrichment_stage1"),
                    ],
                },
            )
        if request.url.path == "/entries/enrichment-stage1-results":
            return httpx.Response(409, json={"error": "invalid_transition"})
        if request.url.path == f"/batches/{_STAGE1_BATCH_ID}" and request.method == "PATCH":
            patch_calls.append(json.loads(request.content))
            return httpx.Response(200, json={"batch": _batch_wire(
                batch_id=_STAGE1_BATCH_ID,
                batch_type="enrichment_stage1",
                status="processing",
            )})
        return httpx.Response(404)

    fake_results = [
        models_mod.AnthropicBatchResultItem(
            custom_id=source_id_to_batch_custom_id(_SOURCE_PASS),
            text=_call1_payload(),
        ),
    ]
    anthropic = FakeAnthropicClient(results=fake_results)

    async def _run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            client = state_worker_mod.StateWorkerClient(client=http)
            batch = models_mod.BatchRecordWire.model_validate(
                _batch_wire(batch_id=_STAGE1_BATCH_ID, batch_type="enrichment_stage1"),
            )
            tracked = {batch.batch_id: batch}
            await loop_mod.poll_once(client, anthropic, tracked, now=_NOW)

        complete_patches = [call for call in patch_calls if call.get("status") == "complete"]
        assert complete_patches == []
        assert _STAGE1_BATCH_ID in tracked

    asyncio.run(_run())


def test_poll_once_enrichment_stage1_timeout_calls_post_timeout_endpoint() -> None:
    state_worker_mod, loop_mod, models_mod = _load_enrichment_stack()
    timeout_called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal timeout_called
        if request.url.path == "/batches":
            return httpx.Response(
                200,
                json={
                    "batches": [
                        _batch_wire(
                            batch_id=_STAGE1_BATCH_ID,
                            batch_type="enrichment_stage1",
                            submitted_at=_TIMEOUT_SUBMITTED_AT,
                        ),
                    ],
                },
            )
        if request.url.path == f"/batches/{_STAGE1_BATCH_ID}/timeout" and request.method == "POST":
            timeout_called = True
            return httpx.Response(
                200,
                json={
                    "batch_id": _STAGE1_BATCH_ID,
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
                _batch_wire(
                    batch_id=_STAGE1_BATCH_ID,
                    batch_type="enrichment_stage1",
                    submitted_at=_TIMEOUT_SUBMITTED_AT,
                ),
            )
            tracked = {batch.batch_id: batch}
            await loop_mod.poll_once(client, anthropic, tracked, now=_NOW)

        assert timeout_called is True
        assert tracked == {}
        assert anthropic.status_calls == []

    asyncio.run(_run())


def test_poll_once_stage1_includes_oov_tags_stripped_in_wire() -> None:
    """Falsifier: OOV tags stripped by parser but not forwarded to state-worker."""
    state_worker_mod, loop_mod, models_mod = _load_enrichment_stack()
    posted_body: dict | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal posted_body
        if request.url.path == "/batches":
            return httpx.Response(
                200,
                json={
                    "batches": [
                        _batch_wire(batch_id=_STAGE1_BATCH_ID, batch_type="enrichment_stage1"),
                    ],
                },
            )
        if request.url.path == "/entries/enrichment-stage1-results":
            posted_body = json.loads(request.read().decode("utf-8"))
            return httpx.Response(204)
        if request.url.path == f"/batches/{_STAGE1_BATCH_ID}" and request.method == "PATCH":
            return httpx.Response(200, json={"batch": {}})
        return httpx.Response(404)

    fake_results = [
        models_mod.AnthropicBatchResultItem(
            custom_id=source_id_to_batch_custom_id(_SOURCE_PASS),
            text=_call1_payload(tags=["RAG", "not-in-taxonomy"]),
        ),
    ]
    anthropic = FakeAnthropicClient(results=fake_results)

    async def _run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            client = state_worker_mod.StateWorkerClient(client=http)
            batch = models_mod.BatchRecordWire.model_validate(
                _batch_wire(
                    batch_id=_STAGE1_BATCH_ID,
                    batch_type="enrichment_stage1",
                ),
            )
            batch = batch.model_copy(update={"source_ids": [_SOURCE_PASS]})
            tracked = {batch.batch_id: batch}
            await loop_mod.poll_once(client, anthropic, tracked, now=_NOW)

        assert posted_body is not None
        entry = posted_body["entries"][0]
        assert entry["tags"] == ["RAG"]
        assert entry["oov_tags_stripped"] == ["not-in-taxonomy"]

    asyncio.run(_run())
