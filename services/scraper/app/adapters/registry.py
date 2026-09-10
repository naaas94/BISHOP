"""Adapter registry - M8 T8-bis merges all seven registered sources (contract sole merger).

LessWrongAdapter is included: the T4-openreview-lesswrong.md decision log
records a successful live GraphQL-over-GET probe (2026-09-10), which is the
condition the plan's context-map flag 3 gates registration on.
"""

from __future__ import annotations

from app.adapters.arxiv import ArxivAdapter
from app.adapters.base import SourceAdapter
from app.adapters.github import GitHubAdapter
from app.adapters.huggingface import HuggingFaceAdapter
from app.adapters.lesswrong import LessWrongAdapter
from app.adapters.openreview import OpenReviewAdapter
from app.adapters.paperswithcode import PapersWithCodeAdapter
from app.adapters.semantic_scholar import SemanticScholarAdapter

ADAPTER_REGISTRY: list[type[SourceAdapter]] = [
    ArxivAdapter,
    GitHubAdapter,
    HuggingFaceAdapter,
    LessWrongAdapter,
    OpenReviewAdapter,
    PapersWithCodeAdapter,
    SemanticScholarAdapter,
]
