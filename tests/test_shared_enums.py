"""Unit tests for bishop_shared enums (M2 T1 — cross-service §20 literals)."""

from bishop_shared.enums import DomainEnum, SourceEnum

STATE_WORKER_SOURCE_LITERALS = {
    "arxiv",
    "semantic_scholar",
    "huggingface",
    "paperswithcode",
    "github",
    "openreview",
    "lesswrong",
}

STATE_WORKER_DOMAIN_LITERALS = {"professional", "personal"}


def test_shared_enums_match_state_worker() -> None:
    assert {member.value for member in SourceEnum} == STATE_WORKER_SOURCE_LITERALS
    assert {member.value for member in DomainEnum} == STATE_WORKER_DOMAIN_LITERALS
