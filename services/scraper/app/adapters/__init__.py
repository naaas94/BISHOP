"""Source adapters for the scraper discovery stage."""

from app.adapters.base import SourceAdapter
from app.adapters.registry import ADAPTER_REGISTRY, ArxivAdapter

__all__ = ["ADAPTER_REGISTRY", "ArxivAdapter", "SourceAdapter"]
