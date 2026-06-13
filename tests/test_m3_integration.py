"""M3 integration tests — mocked e2e across state-worker and batch-poller (T6)."""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import aiosqlite
import httpx
import pytest
from fastapi.testclient import TestClient

_REPO_ROOT = Path(__file__).resolve().parent.parent
_STATE_WORKER_ROOT = _REPO_ROOT / "services" / "state-worker"
_BATCH_POLLER_ROOT = _REPO_ROOT / "services" / "batch-poller"

for path in (_STATE_WORKER_ROOT, _REPO_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from app.enums import BatchStatusEnum, DomainEnum, ProcessingState, SourceEnum  # noqa: E402
from app.main import app  # noqa: E402

_NOW = datetime(2026, 6, 13, 12, 0, 0, tzinfo=UTC)
_BATCH_ID = "m3-e2e-batch-1"
_EXTERNAL_ID = "msgbatch_m3_e2e_1"
_PROFILE_HASH = "ab" * 32
_ENTRY_COUNT = 20


def _patch_db_path(monkeypatch: pytest.MonkeyPatch, db_path: Path) -> None:
    monkeypatch.setattr("app.db.SQLITE_DB_PATH", str(db_path))


def _source_ids(count: int = _ENTRY_COUNT) -> list[str]:
    return [f"arxiv:2406.{idx:05d}" for idx in range(1, count + 1)]


def _manifest_batch_payload(source_ids: list[str]) -> dict:
    return {
        "entries": [
            {
                "source_id": source_id,
                "source": SourceEnum.ARXIV.value,
                "url": f"https://arxiv.org/abs/{source_id}",
                "title": f"Paper {source_id}",
                "abstract": "An abstract for pre-filter.",
                "published_at": _NOW.isoformat().replace("+00:00", "Z"),
                "domain": DomainEnum.PROFESSIONAL.value,
            }
            for source_id in source_ids
        ]
    }


def _register_batch_payload(source_ids: list[str], batch_id: str = _BATCH_ID) -> dict:
    return {
        "batch_id": batch_id,
        "batch_type": "pre_filter",
        "domain": DomainEnum.PROFESSIONAL.value,
        "profile_version": "1.0.0",
        "profile_render_hash": _PROFILE_HASH,
        "source_ids": source_ids,
        "external_batch_id": _EXTERNAL_ID,
        "entry_count": len(source_ids),
    }


def _load_batch_poller_loop_stack() -> tuple[ModuleType, ModuleType, ModuleType]:
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


def _load_batch_poller_startup_stack() -> tuple[ModuleType, ModuleType]:
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

    async def retrieve_batch_status(self, external_batch_id: str) -> tuple[str, str | None]:
        if self.processing_status != "ended":
            return self.processing_status, None
        return "ended", self.terminal

    async def fetch_batch_results(self, external_batch_id: str) -> list:
        return self.results


@pytest.fixture
def integration_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "bishop.db"
    _patch_db_path(monkeypatch, db_path)
    monkeypatch.setattr("app.sweeps.SWEEP_INTERVAL_SEC", 3600.0)
    with TestClient(app) as client:
        yield client, db_path


def _seed_relevance_queued_batch(
    client: TestClient,
    source_ids: list[str],
    *,
    batch_id: str = _BATCH_ID,
    external_batch_id: str = _EXTERNAL_ID,
) -> None:
    ingest = client.post("/manifest/batch", json=_manifest_batch_payload(source_ids))
    assert ingest.status_code == 200
    poll = client.get(
        "/manifest/poll",
        params={"state": ProcessingState.DISCOVERED.value, "limit": 50},
    )
    assert poll.status_code == 200
    assert poll.json()["claimed_count"] == len(source_ids)
    register = client.post(
        "/batches",
        json=_register_batch_payload(source_ids, batch_id=batch_id)
        | {"external_batch_id": external_batch_id},
    )
    assert register.status_code == 201


async def _manifest_states(db_path: Path, source_ids: list[str]) -> dict[str, str]:
    placeholders = ", ".join("?" for _ in source_ids)
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            f"SELECT source_id, processing_state FROM manifest WHERE source_id IN ({placeholders})",
            source_ids,
        )
        rows = await cursor.fetchall()
    return {row[0]: row[1] for row in rows}


def test_m3_e2e_twenty_entry_batch_pass_and_reject(
    integration_client: tuple[TestClient, Path],
) -> None:
    """Contract: 20-entry batch yields RELEVANCE_PASSED and RELEVANCE_REJECTED in one cycle."""
    client, db_path = integration_client
    source_ids = _source_ids()
    _seed_relevance_queued_batch(client, source_ids)

    state_worker_mod, loop_mod, models_mod = _load_batch_poller_loop_stack()
    fake_results = [
        models_mod.AnthropicBatchResultItem(
            custom_id=source_id,
            text=(
                '{"decision": 1, "rationale": "Relevant RAG content."}'
                if index < 10
                else '{"decision": 0, "rationale": "Off topic."}'
            ),
        )
        for index, source_id in enumerate(source_ids)
    ]
    anthropic = FakeAnthropicClient(results=fake_results)

    async def _run_poll() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            sw_client = state_worker_mod.StateWorkerClient(client=http)
            batches = await sw_client.get_in_flight_batches()
            assert len(batches) == 1
            tracked = {batches[0].batch_id: batches[0]}
            await loop_mod.poll_once(sw_client, anthropic, tracked, now=_NOW)
            assert tracked == {}

    asyncio.run(_run_poll())

    states = asyncio.run(_manifest_states(db_path, source_ids))
    passed = [
        source_id
        for source_id, state in states.items()
        if state == ProcessingState.RELEVANCE_PASSED.value
    ]
    rejected = [
        source_id
        for source_id, state in states.items()
        if state == ProcessingState.RELEVANCE_REJECTED.value
    ]
    assert len(passed) == 10
    assert len(rejected) == 10

    detail = client.get(f"/batches/{_BATCH_ID}")
    assert detail.status_code == 200
    batch = detail.json()["batch"]
    assert batch["status"] == BatchStatusEnum.COMPLETE.value
    assert batch["passed_count"] == 10
    assert batch["failed_count"] == 10


def test_m3_startup_scan_registers_pre_seeded_in_flight_batch(
    integration_client: tuple[TestClient, Path],
) -> None:
    """Falsifier: restart without startup scan orphans in-flight pre_filter batches."""
    client, _db_path = integration_client
    batch_id = "m3-restart-batch-1"
    external_id = "msgbatch_m3_restart_1"
    source_ids = ["arxiv:2406.10001"]
    _seed_relevance_queued_batch(
        client,
        source_ids,
        batch_id=batch_id,
        external_batch_id=external_id,
    )

    patch = client.patch(
        f"/batches/{batch_id}",
        json={"status": BatchStatusEnum.PROCESSING.value},
    )
    assert patch.status_code == 200

    state_worker_mod, startup_mod = _load_batch_poller_startup_stack()

    async def _run_scan() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            sw_client = state_worker_mod.StateWorkerClient(client=http)
            tracked = await startup_mod.startup_scan(sw_client)

        assert len(tracked) == 1
        assert tracked[0].batch_id == batch_id
        assert tracked[0].status == BatchStatusEnum.PROCESSING.value
        assert tracked[0].external_batch_id == external_id
        assert tracked[0].source_ids == source_ids

    asyncio.run(_run_scan())
