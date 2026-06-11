"""ProcessingState and §20 controlled vocabularies for state-worker."""

from enum import Enum


class ProcessingState(str, Enum):
    """Spec §6.1 — complete processing state machine."""

    DISCOVERED = "DISCOVERED"
    RELEVANCE_QUEUED = "RELEVANCE_QUEUED"
    RELEVANCE_PASSED = "RELEVANCE_PASSED"
    RELEVANCE_REJECTED = "RELEVANCE_REJECTED"
    SCRAPE_QUEUED = "SCRAPE_QUEUED"
    SCRAPED = "SCRAPED"
    ENRICHMENT_STAGE1_QUEUED = "ENRICHMENT_STAGE1_QUEUED"
    ENRICHMENT_STAGE1_SUBMITTED = "ENRICHMENT_STAGE1_SUBMITTED"
    ENRICHMENT_STAGE1_COMPLETE = "ENRICHMENT_STAGE1_COMPLETE"
    ENRICHMENT_STAGE2_QUEUED = "ENRICHMENT_STAGE2_QUEUED"
    ENRICHMENT_STAGE2_CLAIMED = "ENRICHMENT_STAGE2_CLAIMED"
    ENRICHMENT_STAGE2_SUBMITTED = "ENRICHMENT_STAGE2_SUBMITTED"
    ENRICHMENT_STAGE2_COMPLETE = "ENRICHMENT_STAGE2_COMPLETE"
    VECTOR_WRITE_QUEUED = "VECTOR_WRITE_QUEUED"
    INDEXED = "INDEXED"
    SCRAPE_FAILED = "SCRAPE_FAILED"
    ENRICHMENT_STAGE1_FAILED = "ENRICHMENT_STAGE1_FAILED"
    ENRICHMENT_STAGE2_FAILED = "ENRICHMENT_STAGE2_FAILED"
    VECTOR_WRITE_FAILED = "VECTOR_WRITE_FAILED"
    ESCALATION_FLAGGED = "ESCALATION_FLAGGED"
    PERMANENTLY_FAILED = "PERMANENTLY_FAILED"


class SourceEnum(str, Enum):
    """Spec §20.1."""

    ARXIV = "arxiv"
    SEMANTIC_SCHOLAR = "semantic_scholar"
    HUGGINGFACE = "huggingface"
    PAPERSWITHCODE = "paperswithcode"
    GITHUB = "github"
    OPENREVIEW = "openreview"
    LESSWRONG = "lesswrong"


class DomainEnum(str, Enum):
    """Spec §20.3."""

    PROFESSIONAL = "professional"
    PERSONAL = "personal"


class BatchTypeEnum(str, Enum):
    """Spec §20.4."""

    PRE_FILTER = "pre_filter"
    ENRICHMENT_STAGE1 = "enrichment_stage1"
    ENRICHMENT_STAGE2 = "enrichment_stage2"


class BatchStatusEnum(str, Enum):
    """Spec §20.5."""

    PENDING = "pending"
    SUBMITTED = "submitted"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"
    BATCH_TIMED_OUT = "batch_timed_out"


class EntryTypeEnum(str, Enum):
    """Spec §20.2."""

    PAPER = "paper"
    MODEL = "model"
    DATASET = "dataset"
    REPO = "repo"
    ARTICLE = "article"
    SPEC = "spec"
    IDEA = "idea"
    BENCHMARK = "benchmark"
    OTHER = "other"


class ReadingStatusEnum(str, Enum):
    """Spec §20.6."""

    UNREAD = "unread"
    READING = "reading"
    READ = "read"
    ARCHIVED = "archived"


class OovReviewStatusEnum(str, Enum):
    """Spec §20.7."""

    PENDING = "pending"
    ADDED_TO_TAXONOMY = "added_to_taxonomy"
    REJECTED = "rejected"
