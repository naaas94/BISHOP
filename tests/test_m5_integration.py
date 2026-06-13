"""M5 integration tests — mocked e2e across state-worker, enrichment-batcher, batch-poller (T6)."""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

import aiosqlite
import httpx
import pytest
from fastapi.testclient import TestClient

from bishop_shared.enums import DomainEnum, SourceEnum
from bishop_shared.batch_custom_id import source_id_to_batch_custom_id

_REPO_ROOT = Path(__file__).resolve().parent.parent
_STATE_WORKER_ROOT = _REPO_ROOT / "services" / "state-worker"
_BATCH_POLLER_ROOT = _REPO_ROOT / "services" / "batch-poller"
_ENRICHMENT_ROOT = _REPO_ROOT / "services" / "enrichment-batcher"
_PROFILE_PATH = _REPO_ROOT / "config/profiles/professional_v1.0.0.yaml"

for path in (_STATE_WORKER_ROOT, _REPO_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from app.enums import BatchStatusEnum, ProcessingState  # noqa: E402
from app.main import app  # noqa: E402

_NOW = datetime(2026, 6, 13, 15, 0, 0, tzinfo=UTC)
_ENTRY_COUNT = 5
_PREFILTER_BATCH_ID = "m5-prefilter-batch"
_CONTENT_RAW = "Full paper text for enrichment Call 1 truncation and summary."


def _patch_db_path(monkeypatch: pytest.MonkeyPatch, db_path: Path) -> None:
    monkeypatch.setattr("app.db.SQLITE_DB_PATH", str(db_path))


def _source_ids(count: int = _ENTRY_COUNT) -> list[str]:
    return [f"arxiv:2506.{idx:05d}" for idx in range(1, count + 1)]


def _manifest_batch_payload(source_ids: list[str]) -> dict:
    return {
        "entries": [
            {
                "source_id": source_id,
                "source": SourceEnum.ARXIV.value,
                "url": f"https://arxiv.org/abs/{source_id.removeprefix('arxiv:')}",
                "title": f"M5 Integration Paper {source_id}",
                "abstract": "An abstract for enrichment.",
                "published_at": _NOW.isoformat().replace("+00:00", "Z"),
                "domain": DomainEnum.PROFESSIONAL.value,
            }
            for source_id in source_ids
        ]
    }


def _pre_filter_payload(source_ids: list[str]) -> dict:
    return {
        "batch_id": _PREFILTER_BATCH_ID,
        "profile_version": "1.0.0",
        "entries": [
            {
                "source_id": source_id,
                "decision": 1,
                "pre_filter_rationale": "Relevant for M5 integration.",
            }
            for source_id in source_ids
        ],
    }


def _seed_scraped_entries(client: TestClient, source_ids: list[str]) -> None:
    ingest = client.post("/manifest/batch", json=_manifest_batch_payload(source_ids))
    assert ingest.status_code == 200
    discovered = client.get(
        "/manifest/poll",
        params={"state": ProcessingState.DISCOVERED.value, "limit": 50},
    )
    assert discovered.status_code == 200
    assert discovered.json()["claimed_count"] == len(source_ids)
    pre_filter = client.post("/manifest/pre-filter-results", json=_pre_filter_payload(source_ids))
    assert pre_filter.status_code == 200
    passed = client.get(
        "/manifest/poll",
        params={"state": ProcessingState.RELEVANCE_PASSED.value, "limit": 50},
    )
    assert passed.status_code == 200
    assert passed.json()["claimed_count"] == len(source_ids)
    for source_id in source_ids:
        content = client.post(
            "/entries/content",
            json={"source_id": source_id, "content_raw": _CONTENT_RAW},
        )
        assert content.status_code == 200
        assert content.json()["processing_state"] == ProcessingState.SCRAPED.value


def _load_enrichment_batcher_stack() -> tuple[ModuleType, ModuleType, ModuleType, ModuleType]:
    saved = {name: mod for name, mod in sys.modules.items() if name == "app" or name.startswith("app.")}
    for name in saved:
        del sys.modules[name]

    path_state: list[str] = []
    for path_str in (str(_ENRICHMENT_ROOT), str(_REPO_ROOT)):
        if path_str not in sys.path:
            sys.path.insert(0, path_str)
            path_state.append(path_str)

    try:
        import app.anthropic_batch_client as anthropic_mod  # noqa: WPS433
        import app.stage1_loop as stage1_mod  # noqa: WPS433
        import app.stage2_loop as stage2_mod  # noqa: WPS433
        import app.state_worker_client as enrich_sw_mod  # noqa: WPS433
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.modules.update(saved)
        for path_str in path_state:
            sys.path.remove(path_str)

    return anthropic_mod, stage1_mod, stage2_mod, enrich_sw_mod


def _load_batch_poller_stack() -> tuple[ModuleType, ModuleType, ModuleType, ModuleType]:
    saved = {name: mod for name, mod in sys.modules.items() if name == "app" or name.startswith("app.")}
    for name in saved:
        del sys.modules[name]

    path_state: list[str] = []
    for path_str in (str(_BATCH_POLLER_ROOT), str(_REPO_ROOT)):
        if path_str not in sys.path:
            sys.path.insert(0, path_str)
            path_state.append(path_str)

    try:
        import app.clients.state_worker as poller_sw_mod  # noqa: WPS433
        import app.loop as poller_loop_mod  # noqa: WPS433
        import app.models as poller_models_mod  # noqa: WPS433
        import app.startup as startup_mod  # noqa: WPS433
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.modules.update(saved)
        for path_str in path_state:
            sys.path.remove(path_str)

    return poller_sw_mod, poller_loop_mod, poller_models_mod, startup_mod


def _call1_payload(*, oov: bool = False) -> str:
    tags = ["RAG", "not-in-taxonomy"] if oov else ["RAG", "hybrid-retrieval"]
    return json.dumps(
        {
            "summary": "A dense technical summary of hybrid retrieval methods.",
            "concepts": ["retrieval", "graphs", "latency", "embeddings", "indexing"],
            "tags": tags,
            "entry_type": "paper",
            "challenge_hooks": [
                "How to reduce latency in dense retrieval",
                "When to use hybrid sparse-dense pipelines",
            ],
        }
    )


def _call2_payload() -> str:
    return json.dumps(
        {
            "relevance_score": 0.87,
            "relevance_reason": "Directly addresses hybrid retrieval.",
            "value_rationale": "Useful for production RAG tuning.",
        }
    )


class FakeAnthropicClient:
    def __init__(self, results: list) -> None:
        self.results = results

    async def retrieve_batch_status(self, external_batch_id: str) -> tuple[str, str | None]:
        return "ended", "succeeded"

    async def fetch_batch_results(self, external_batch_id: str) -> list:
        return self.results


def _mock_submit_anthropic(anthropic_mod: ModuleType, external_ids: list[str]) -> MagicMock:
    mock_sdk = MagicMock()
    mock_sdk.messages.batches.create.side_effect = [
        SimpleNamespace(id=external_id) for external_id in external_ids
    ]
    return anthropic_mod.AnthropicBatchClient(client=mock_sdk)


@pytest.fixture
def integration_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "bishop.db"
    _patch_db_path(monkeypatch, db_path)
    monkeypatch.setattr("app.sweeps.SWEEP_INTERVAL_SEC", 3600.0)
    monkeypatch.setenv("BISHOP_G3_VERIFIED", "1")
    anthropic_mod, stage1_mod, _, _ = _load_enrichment_batcher_stack()
    stage1_mod.reset_g3_gate_for_tests()
    with TestClient(app) as client:
        yield client, db_path, anthropic_mod, stage1_mod


async def _entry_enrichment_row(db_path: Path, source_id: str) -> dict[str, object] | None:
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            """
            SELECT processing_state, summary, concepts, tags, entry_type,
                   challenge_hooks, enrichment_stage1_batch_id,
                   relevance_score, relevance_reason, value_rationale,
                   enrichment_stage2_batch_id
            FROM entries WHERE source_id = ?
            """,
            (source_id,),
        )
        row = await cursor.fetchone()
    if row is None:
        return None
    keys = [
        "processing_state",
        "summary",
        "concepts",
        "tags",
        "entry_type",
        "challenge_hooks",
        "enrichment_stage1_batch_id",
        "relevance_score",
        "relevance_reason",
        "value_rationale",
        "enrichment_stage2_batch_id",
    ]
    return dict(zip(keys, row, strict=True))


async def _oov_tag_count(db_path: Path, source_id: str) -> int:
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            "SELECT COUNT(*) FROM oov_tags_log WHERE source_id = ?",
            (source_id,),
        )
        row = await cursor.fetchone()
    return int(row[0]) if row else 0


async def _batch_types(db_path: Path) -> dict[str, str]:
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            "SELECT batch_id, batch_type, status FROM batches WHERE batch_type LIKE 'enrichment_%'"
        )
        rows = await cursor.fetchall()
    return {row[0]: row[1] for row in rows}


def _in_flight_enrichment_batch(client: TestClient, batch_type: str) -> dict:
    listing = client.get("/batches", params={"status": "submitted,processing"})
    assert listing.status_code == 200
    batches = listing.json()["batches"]
    matches = [batch for batch in batches if batch["batch_type"] == batch_type]
    assert len(matches) == 1
    return matches[0]


def test_m5_e2e_five_entries_reach_vector_write_queued_with_enrichment_fields(
    integration_client: tuple[TestClient, Path, ModuleType, ModuleType],
) -> None:
    """Contract: 5 SCRAPED entries → mocked Anthropic → VECTOR_WRITE_QUEUED with all enrichment fields."""
    client, db_path, anthropic_mod, stage1_mod = integration_client
    _, _, stage2_mod, enrich_sw_mod = _load_enrichment_batcher_stack()
    poller_sw_mod, poller_loop_mod, poller_models_mod, _ = _load_batch_poller_stack()

    source_ids = _source_ids()
    _seed_scraped_entries(client, source_ids)

    anthropic_batcher = _mock_submit_anthropic(
        anthropic_mod,
        ["msgbatch_m5_stage1", "msgbatch_m5_stage2"],
    )

    async def _run_pipeline() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            enrich_client = enrich_sw_mod.StateWorkerClient(client=http)
            poller_client = poller_sw_mod.StateWorkerClient(client=http)

            await stage1_mod.stage1_cycle(
                enrich_client,
                anthropic_batcher,
                profile_path=_PROFILE_PATH,
            )
            stage1_batch = _in_flight_enrichment_batch(client, "enrichment_stage1")
            stage1_results = [
                poller_models_mod.AnthropicBatchResultItem(
                    custom_id=source_id_to_batch_custom_id(source_id),
                    text=_call1_payload(oov=(index == 0)),
                )
                for index, source_id in enumerate(source_ids)
            ]
            tracked = {stage1_batch["batch_id"]: poller_models_mod.BatchRecordWire.model_validate(stage1_batch)}
            await poller_loop_mod.poll_once(
                poller_client,
                FakeAnthropicClient(stage1_results),
                tracked,
                now=_NOW,
            )
            assert tracked == {}

            await stage2_mod.stage2_cycle(
                enrich_client,
                anthropic_batcher,
                profile_path=_PROFILE_PATH,
            )
            stage2_batch = _in_flight_enrichment_batch(client, "enrichment_stage2")
            stage2_results = [
                poller_models_mod.AnthropicBatchResultItem(
                    custom_id=source_id_to_batch_custom_id(source_id),
                    text=_call2_payload(),
                )
                for source_id in source_ids
            ]
            tracked = {stage2_batch["batch_id"]: poller_models_mod.BatchRecordWire.model_validate(stage2_batch)}
            await poller_loop_mod.poll_once(
                poller_client,
                FakeAnthropicClient(stage2_results),
                tracked,
                now=_NOW,
            )
            assert tracked == {}

    asyncio.run(_run_pipeline())

    for source_id in source_ids:
        row = asyncio.run(_entry_enrichment_row(db_path, source_id))
        assert row is not None
        assert row["processing_state"] == ProcessingState.VECTOR_WRITE_QUEUED.value
        for field in (
            "summary",
            "concepts",
            "tags",
            "entry_type",
            "challenge_hooks",
            "enrichment_stage1_batch_id",
            "relevance_score",
            "relevance_reason",
            "value_rationale",
            "enrichment_stage2_batch_id",
        ):
            assert row[field] is not None, f"{source_id}.{field} is null"

    oov_count = asyncio.run(_oov_tag_count(db_path, source_ids[0]))
    assert oov_count >= 1

    batch_types = asyncio.run(_batch_types(db_path))
    assert "enrichment_stage1" in batch_types.values()
    assert "enrichment_stage2" in batch_types.values()


def test_m5_double_poll_stage2_queued_empty_while_claimed_held(
    integration_client: tuple[TestClient, Path, ModuleType, ModuleType],
) -> None:
    """Falsifier: concurrent ENRICHMENT_STAGE2_QUEUED poll must not double-claim."""
    client, db_path, _, _ = integration_client
    source_ids = [_source_ids(1)[0]]
    _seed_scraped_entries(client, source_ids)

    scraped_poll = client.get(
        "/entries/poll",
        params={"state": ProcessingState.SCRAPED.value, "limit": 10},
    )
    assert scraped_poll.status_code == 200
    assert scraped_poll.json()["claimed_count"] == 1

    register = client.post(
        "/batches",
        json={
            "batch_id": "m5-double-poll-s1",
            "batch_type": "enrichment_stage1",
            "domain": DomainEnum.PROFESSIONAL.value,
            "profile_version": "1.0.0",
            "profile_render_hash": "c" * 64,
            "source_ids": source_ids,
            "external_batch_id": "msgbatch_m5_dp_s1",
            "entry_count": 1,
        },
    )
    assert register.status_code == 201

    stage1_results = client.post(
        "/entries/enrichment-stage1-results",
        json={
            "batch_id": "m5-double-poll-s1",
            "entries": [
                {
                    "source_id": source_ids[0],
                    "success": True,
                    "summary": "Summary for stage2 poll test.",
                    "concepts": ["retrieval"],
                    "tags": ["RAG"],
                    "entry_type": "paper",
                    "challenge_hooks": ["hook one"],
                }
            ],
        },
    )
    assert stage1_results.status_code == 204

    first = client.get(
        "/entries/poll",
        params={"state": ProcessingState.ENRICHMENT_STAGE2_QUEUED.value, "limit": 10},
    )
    assert first.status_code == 200
    assert first.json()["claimed_count"] == 1
    assert first.json()["transitioned_to"] == ProcessingState.ENRICHMENT_STAGE2_CLAIMED.value

    second = client.get(
        "/entries/poll",
        params={"state": ProcessingState.ENRICHMENT_STAGE2_QUEUED.value, "limit": 10},
    )
    assert second.status_code == 200
    assert second.json()["claimed_count"] == 0

    async def _claimed_state() -> str:
        async with aiosqlite.connect(db_path) as conn:
            cursor = await conn.execute(
                "SELECT processing_state FROM entries WHERE source_id = ?",
                (source_ids[0],),
            )
            row = await cursor.fetchone()
        return row[0]

    assert asyncio.run(_claimed_state()) == ProcessingState.ENRICHMENT_STAGE2_CLAIMED.value


def test_m5_startup_scan_registers_enrichment_stage1_in_flight(
    integration_client: tuple[TestClient, Path, ModuleType, ModuleType],
) -> None:
    """Falsifier: poller restart without startup scan orphans enrichment_stage1 batches."""
    client, _, anthropic_mod, stage1_mod = integration_client
    _, _, enrich_sw_mod, _ = _load_enrichment_batcher_stack()
    poller_sw_mod, _, _, startup_mod = _load_batch_poller_stack()

    source_ids = [_source_ids(1)[0]]
    _seed_scraped_entries(client, source_ids)
    anthropic_batcher = _mock_submit_anthropic(anthropic_mod, ["msgbatch_m5_restart_s1"])

    async def _register_batch() -> str:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            enrich_client = enrich_sw_mod.StateWorkerClient(client=http)
            await stage1_mod.stage1_cycle(
                enrich_client,
                anthropic_batcher,
                profile_path=_PROFILE_PATH,
            )
        batch = _in_flight_enrichment_batch(client, "enrichment_stage1")
        return batch["batch_id"]

    batch_id = asyncio.run(_register_batch())
    patch = client.patch(
        f"/batches/{batch_id}",
        json={"status": BatchStatusEnum.PROCESSING.value},
    )
    assert patch.status_code == 200

    async def _run_scan() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            sw_client = poller_sw_mod.StateWorkerClient(client=http)
            tracked = await startup_mod.startup_scan(sw_client)

        assert len(tracked) == 1
        assert tracked[0].batch_id == batch_id
        assert tracked[0].batch_type == "enrichment_stage1"
        assert tracked[0].status == BatchStatusEnum.PROCESSING.value
        assert tracked[0].external_batch_id == "msgbatch_m5_restart_s1"
        assert tracked[0].source_ids == source_ids

    asyncio.run(_run_scan())
