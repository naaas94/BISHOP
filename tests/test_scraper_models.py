"""Unit tests for scraper wire DTOs (M2 T1)."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRAPER_ROOT = _REPO_ROOT / "services" / "scraper"


def _load_models_module() -> ModuleType:
    """Load scraper models without shadowing state-worker `app` in sys.modules."""
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
        import app.models as models  # noqa: WPS433 — isolated import under scraper path
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.modules.update(saved_app_modules)
        for path_str in path_state:
            sys.path.remove(path_str)

    return models


def test_manifest_ingest_entry_round_trip() -> None:
    models = _load_models_module()
    published = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    entry = models.ManifestIngestEntry(
        source_id="arxiv:2406.00001",
        source=models.SourceEnum.ARXIV,
        url="http://arxiv.org/abs/2406.00001",
        title="Example Paper",
        abstract="An abstract.",
        published_at=published,
        domain=models.DomainEnum.PROFESSIONAL,
    )
    payload = entry.model_dump(mode="json")
    assert payload == {
        "source_id": "arxiv:2406.00001",
        "source": "arxiv",
        "url": "http://arxiv.org/abs/2406.00001",
        "title": "Example Paper",
        "abstract": "An abstract.",
        "published_at": published.isoformat().replace("+00:00", "Z"),
        "domain": "professional",
    }
    restored = models.ManifestIngestEntry.model_validate(payload)
    assert restored == entry
