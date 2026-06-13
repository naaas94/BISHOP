"""Resolve poll ``source`` values to vendored adapter instances."""

from __future__ import annotations

import logging

from bishop_shared.enums import SourceEnum
from scraper_app.adapters.base import SourceAdapter
from scraper_app.adapters.registry import ADAPTER_REGISTRY

logger = logging.getLogger(__name__)


def resolve_adapter(source: SourceEnum) -> SourceAdapter | None:
    """Return an adapter instance for ``source``, or None when unregistered."""
    for adapter_cls in ADAPTER_REGISTRY:
        adapter = adapter_cls()
        if adapter.source == source:
            return adapter
    logger.error(
        "no adapter registered for source",
        extra={"event": "adapter_not_found", "source": source.value},
    )
    return None
