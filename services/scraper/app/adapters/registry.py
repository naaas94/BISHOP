"""Adapter registry — M2 contains ArxivAdapter only (charter override of §10.2)."""

from __future__ import annotations

from datetime import datetime

from bishop_shared.enums import DomainEnum, SourceEnum

from app.adapters.base import SourceAdapter
from app.models import ManifestIngestEntry
from app.rate_limit import SOURCE_RATE_LIMITS

try:
    from app.adapters.arxiv import ArxivAdapter
except ImportError:
    class ArxivAdapter(SourceAdapter):
        """Bootstrap stub until T4 lands ``adapters/arxiv.py``."""

        source = SourceEnum.ARXIV
        domain = DomainEnum.PROFESSIONAL
        rate_limit = SOURCE_RATE_LIMITS[SourceEnum.ARXIV.value]

        async def fetch_manifest(
            self,
            since: datetime | None = None,
        ) -> list[ManifestIngestEntry]:
            raise NotImplementedError("T4")


ADAPTER_REGISTRY: list[type[SourceAdapter]] = [ArxivAdapter]
