"""Source adapter abstract base class (§10.1)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from bishop_shared.enums import DomainEnum, SourceEnum

from app.models import ManifestIngestEntry
from app.rate_limit import RateLimit


class SourceAdapter(ABC):
    """Pipeline-facing interface for per-source manifest discovery."""

    source: SourceEnum
    domain: DomainEnum
    rate_limit: RateLimit

    @abstractmethod
    async def fetch_manifest(
        self,
        since: datetime | None = None,
    ) -> list[ManifestIngestEntry]:
        """Lightweight scrape: IDs, titles, abstracts only."""

    async def fetch_content(self, entry: ManifestIngestEntry) -> str:
        """Full content fetch — deferred to M4."""
        raise NotImplementedError("M4")

    def make_source_id(self, raw_id: str) -> str:
        """Canonical source ID format: ``source_name:raw_id``."""
        return f"{self.source.value}:{raw_id}"
