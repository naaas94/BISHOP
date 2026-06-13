"""Unit tests for batch-poller startup scan (M3 T5)."""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import httpx
import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BATCH_POLLER_ROOT = _REPO_ROOT / "services" / "batch-poller"

_SUBMITTED_AT = datetime(2026, 6, 13, 10, 0, 0, tzinfo=UTC)


def _load_batch_poller_modules() -> tuple[ModuleType, ModuleType]:
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
        import app.startup as startup_mod  # noqa: WPS433
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.modules.update(saved)
        for path_str in path_state:
            sys.path.remove(path_str)

    return state_worker_mod, startup_mod


def _batch_payload(
    *,
    batch_id: str,
    batch_type: str = "pre_filter",
    status: str = "submitted",
) -> dict:
    return {
        "batch_id": batch_id,
        "batch_type": batch_type,
        "domain": "professional",
        "profile_version": "1.0.0",
        "profile_render_hash": "a" * 64,
        "status": status,
        "created_at": _SUBMITTED_AT.isoformat().replace("+00:00", "Z"),
        "submitted_at": _SUBMITTED_AT.isoformat().replace("+00:00", "Z"),
        "completed_at": None,
        "entry_count": 1,
        "passed_count": 0,
        "failed_count": 0,
        "source_ids": ["arxiv:2406.00001"],
        "external_batch_id": "msgbatch_ext_1",
    }


def test_startup_scan_filters_pre_filter_only() -> None:
    state_worker_mod, startup_mod = _load_batch_poller_modules()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/batches"
        assert request.url.params.get("status") == "submitted,processing"
        return httpx.Response(
            200,
            json={
                "batches": [
                    _batch_payload(batch_id="pf-1", batch_type="pre_filter"),
                    _batch_payload(batch_id="enr-1", batch_type="enrichment_stage1"),
                ],
            },
        )

    async def _run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            client = state_worker_mod.StateWorkerClient(client=http)
            tracked = await startup_mod.startup_scan(client)

        assert len(tracked) == 1
        assert tracked[0].batch_id == "pf-1"
        assert tracked[0].batch_type == "pre_filter"

    asyncio.run(_run())


def test_startup_scan_restart_recovery_registers_in_flight_batch() -> None:
    """Falsifier: restart without startup scan orphans submitted batches."""
    state_worker_mod, startup_mod = _load_batch_poller_modules()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "batches": [
                    _batch_payload(batch_id="pf-restart-1", status="processing"),
                ],
            },
        )

    async def _run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            client = state_worker_mod.StateWorkerClient(client=http)
            tracked = await startup_mod.startup_scan(client)

        assert [batch.batch_id for batch in tracked] == ["pf-restart-1"]
        assert tracked[0].status == "processing"
        assert tracked[0].external_batch_id == "msgbatch_ext_1"

    asyncio.run(_run())
