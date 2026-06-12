"""Unit tests for SourceAdapter ABC and ADAPTER_REGISTRY (M2 T2)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

import pytest

from bishop_shared.enums import DomainEnum, SourceEnum

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRAPER_ROOT = _REPO_ROOT / "services" / "scraper"


def _load_adapters_stack() -> tuple[ModuleType, ModuleType, ModuleType]:
    """Load scraper adapters without shadowing state-worker ``app`` in sys.modules."""
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
        import app.adapters.base as base  # noqa: WPS433
        import app.adapters.registry as registry  # noqa: WPS433
        import app.models as models  # noqa: WPS433
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.modules.update(saved_app_modules)
        for path_str in path_state:
            sys.path.remove(path_str)

    return base, registry, models


@pytest.mark.asyncio
async def test_source_adapter_contract() -> None:
    base, registry, models = _load_adapters_stack()
    adapter = registry.ArxivAdapter()

    assert issubclass(registry.ArxivAdapter, base.SourceAdapter)
    assert adapter.source == SourceEnum.ARXIV
    assert adapter.domain == DomainEnum.PROFESSIONAL
    assert adapter.rate_limit.calls == 3
    assert adapter.rate_limit.period_seconds == 1
    assert adapter.make_source_id("2301.00001") == "arxiv:2301.00001"

    entry = models.ManifestIngestEntry(
        source_id="arxiv:2301.00001",
        source=SourceEnum.ARXIV,
        url="http://arxiv.org/abs/2301.00001",
        title="Example",
        domain=DomainEnum.PROFESSIONAL,
    )

    with pytest.raises(NotImplementedError, match="M4"):
        await adapter.fetch_content(entry)


def test_registry_contains_only_arxiv() -> None:
    _, registry, _ = _load_adapters_stack()
    assert len(registry.ADAPTER_REGISTRY) == 1
    assert registry.ADAPTER_REGISTRY[0] is registry.ArxivAdapter
    assert registry.ADAPTER_REGISTRY[0].__name__ == "ArxivAdapter"
