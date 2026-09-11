"""Unit tests for HuggingFaceAdapter Hub REST API (M8 T2)."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from bishop_shared.enums import DomainEnum, SourceEnum
from bishop_shared.scraper_config import BACKFILL_CONFIG

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRAPER_ROOT = _REPO_ROOT / "services" / "scraper"

_SINCE = datetime(2026, 6, 1, 0, 0, 0, tzinfo=UTC)
_NOW = datetime(2026, 6, 12, 12, 0, 0, tzinfo=UTC)

_HF_MODELS_FIXTURE = [
    {
        "id": "org/new-model",
        "createdAt": "2026-06-10T12:00:00.000Z",
        "cardData": {"title": "Fresh Model", "description": "  A new model.  "},
    },
    {
        "id": "org/old-model",
        "createdAt": "2026-05-01T12:00:00.000Z",
        "tags": ["pytorch"],
    },
]

_HF_DATASETS_FIXTURE = [
    {
        "id": "org/new-dataset",
        "createdAt": "2026-06-11T08:00:00.000Z",
    },
]

_HF_SPACES_FIXTURE: list[dict[str, str]] = []


def _load_hf_stack() -> ModuleType:
    """Load scraper huggingface adapter without shadowing state-worker ``app``."""
    saved_app_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "app" or name.startswith("app.")
    }
    for name in saved_app_modules:
        del sys.modules[name]

    repo_str = str(_REPO_ROOT)
    scraper_str = str(_SCRAPER_ROOT)
    path_state: list[str] = []
    for path_str in (scraper_str, repo_str):
        if path_str not in sys.path:
            sys.path.insert(0, path_str)
            path_state.append(path_str)

    try:
        import app.adapters.huggingface as huggingface  # noqa: WPS433
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.modules.update(saved_app_modules)
        for path_str in path_state:
            sys.path.remove(path_str)

    return huggingface


def test_resolve_effective_since_uses_backfill_config() -> None:
    hf = _load_hf_stack()
    resolved = hf.resolve_effective_since(None, now=_NOW)
    window_days = BACKFILL_CONFIG[SourceEnum.HUGGINGFACE.value].window_days
    assert resolved == _NOW - __import__("datetime").timedelta(days=window_days)


def test_parse_entity_list_filters_by_since_and_maps_fields() -> None:
    hf = _load_hf_stack()
    adapter = hf.HuggingFaceAdapter()
    entries = hf.parse_entity_list(
        _HF_MODELS_FIXTURE,
        kind="model",
        adapter=adapter,
        since=_SINCE,
    )

    assert len(entries) == 1
    entry = entries[0]
    assert entry.source_id == "huggingface:model:org/new-model"
    assert entry.source == SourceEnum.HUGGINGFACE
    assert entry.domain == DomainEnum.PROFESSIONAL
    assert entry.url == "https://huggingface.co/org/new-model"
    assert entry.title == "[model] Fresh Model"
    assert entry.abstract == "A new model."
    assert entry.published_at == datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_fetch_manifest_hits_all_entity_endpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hf = _load_hf_stack()
    captured_paths: list[str] = []
    captured_model_params: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_paths.append(request.url.path)
        if request.url.path.endswith("/models"):
            captured_model_params.update(dict(request.url.params))
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json=_HF_MODELS_FIXTURE)
        if request.url.path.endswith("/datasets"):
            return httpx.Response(200, json=_HF_DATASETS_FIXTURE)
        if request.url.path.endswith("/spaces"):
            return httpx.Response(200, json=_HF_SPACES_FIXTURE)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = hf.HuggingFaceAdapter(http_client=client)
        monkeypatch.setattr(
            hf,
            "datetime",
            type(
                "FrozenDateTime",
                (datetime,),
                {"now": classmethod(lambda cls, tz=None: _NOW)},
            ),
        )
        entries = await adapter.fetch_manifest(since=_SINCE)

    assert captured_paths == ["/api/models", "/api/datasets", "/api/spaces"]
    assert {entry.source_id for entry in entries} == {
        "huggingface:model:org/new-model",
        "huggingface:dataset:org/new-dataset",
    }

    assert captured_model_params["sort"] == "createdAt"
    assert captured_model_params["direction"] == "-1"
    assert captured_model_params["limit"] == "100"


@pytest.mark.asyncio
async def test_fetch_manifest_sends_huggingface_token_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hf = _load_hf_stack()
    monkeypatch.setattr(hf, "HUGGINGFACE_TOKEN", "hf_test_token")
    captured_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_headers["authorization"] = request.headers.get("Authorization", "")
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = hf.HuggingFaceAdapter(http_client=client)
        monkeypatch.setattr(
            hf,
            "datetime",
            type(
                "FrozenDateTime",
                (datetime,),
                {"now": classmethod(lambda cls, tz=None: _NOW)},
            ),
        )
        await adapter.fetch_manifest(since=_SINCE)

    assert captured_headers["authorization"] == "Bearer hf_test_token"


def _manifest_entry(**kwargs: object):
    saved_app_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "app" or name.startswith("app.")
    }
    for name in saved_app_modules:
        del sys.modules[name]
    repo_str = str(_REPO_ROOT)
    scraper_str = str(_SCRAPER_ROOT)
    for path_str in (scraper_str, repo_str):
        if path_str not in sys.path:
            sys.path.insert(0, path_str)
    try:
        from app.models import ManifestIngestEntry  # noqa: WPS433

        return ManifestIngestEntry(**kwargs)
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.modules.update(saved_app_modules)


@pytest.mark.asyncio
async def test_fetch_content_reads_readme_or_falls_back() -> None:
    hf = _load_hf_stack()
    entry = _manifest_entry(
        source_id="huggingface:model:org/new-model",
        source=SourceEnum.HUGGINGFACE,
        url="https://huggingface.co/org/new-model",
        title="[model] Fresh Model",
        abstract="Fallback abstract",
        domain=DomainEnum.PROFESSIONAL,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/README.md"):
            return httpx.Response(200, text="# Model Card\n\nBody text.")
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = hf.HuggingFaceAdapter(http_client=client)
        content = await adapter.fetch_content(entry)

    assert content == "# Model Card\n\nBody text."


@pytest.mark.asyncio
async def test_fetch_content_falls_back_when_readme_missing() -> None:
    hf = _load_hf_stack()
    entry = _manifest_entry(
        source_id="huggingface:dataset:org/new-dataset",
        source=SourceEnum.HUGGINGFACE,
        url="https://huggingface.co/datasets/org/new-dataset",
        title="[dataset] Example",
        abstract="Dataset summary",
        domain=DomainEnum.PROFESSIONAL,
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = hf.HuggingFaceAdapter(http_client=client)
        content = await adapter.fetch_content(entry)

    assert content == "[dataset] Example\n\nDataset summary"


def test_parse_entity_list_since_filter_falsifier() -> None:
    """Mutation-checked: dropping the since guard would keep org/old-model."""
    hf = _load_hf_stack()
    adapter = hf.HuggingFaceAdapter()
    entries = hf.parse_entity_list(
        _HF_MODELS_FIXTURE,
        kind="model",
        adapter=adapter,
        since=_SINCE,
    )
    source_ids = {entry.source_id for entry in entries}
    assert "huggingface:model:org/old-model" not in source_ids
