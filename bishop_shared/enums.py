"""Cross-service §20 controlled vocabularies shared by scraper and downstream clients."""

from enum import Enum


class SourceEnum(str, Enum):
    """Spec §20.1 — must match services/state-worker/app/enums.py literals."""

    ARXIV = "arxiv"
    SEMANTIC_SCHOLAR = "semantic_scholar"
    HUGGINGFACE = "huggingface"
    PAPERSWITHCODE = "paperswithcode"
    GITHUB = "github"
    OPENREVIEW = "openreview"
    LESSWRONG = "lesswrong"


class DomainEnum(str, Enum):
    """Spec §20.3 — must match services/state-worker/app/enums.py literals."""

    PROFESSIONAL = "professional"
    PERSONAL = "personal"
