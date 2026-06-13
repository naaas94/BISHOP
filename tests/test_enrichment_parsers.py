"""Unit tests for bishop_shared.enrichment_parsers (M5 T1)."""

from __future__ import annotations

import json

from bishop_shared.enrichment_parsers import parse_call1_response, parse_call2_response

_SOURCE = "arxiv:2401.00001"


def _call1_payload(**overrides: object) -> str:
    base = {
        "summary": "A dense technical summary of hybrid retrieval methods for sparse graphs.",
        "concepts": ["retrieval", "graphs", "latency", "embeddings", "indexing"],
        "tags": ["RAG", "hybrid-retrieval", "not-in-taxonomy"],
        "entry_type": "paper",
        "challenge_hooks": [
            "How to reduce latency in dense retrieval",
            "When to use hybrid sparse-dense pipelines",
        ],
    }
    base.update(overrides)
    return json.dumps(base)


def test_parse_call1_success_strips_oov_tags() -> None:
    parsed = parse_call1_response(_SOURCE, _call1_payload())
    assert parsed.success is True
    assert parsed.parse_failed is False
    assert parsed.tags == ["RAG", "hybrid-retrieval"]
    assert parsed.oov_tags_stripped == ["not-in-taxonomy"]
    assert parsed.entry_type == "paper"


def test_parse_call1_malformed_json_fails() -> None:
    parsed = parse_call1_response(_SOURCE, "not json")
    assert parsed.success is False
    assert parsed.parse_failed is True
    assert parsed.error_message == "malformed JSON response"


def test_parse_call1_missing_summary_fails() -> None:
    parsed = parse_call1_response(_SOURCE, _call1_payload(summary=""))
    assert parsed.success is False
    assert parsed.parse_failed is True


def test_parse_call2_success() -> None:
    payload = json.dumps(
        {
            "relevance_score": 0.87,
            "relevance_reason": "Directly addresses hybrid retrieval.",
            "value_rationale": "Useful for production RAG tuning.",
        }
    )
    parsed = parse_call2_response(_SOURCE, payload)
    assert parsed.success is True
    assert parsed.relevance_score == 0.87
    assert parsed.parse_failed is False


def test_parse_call2_score_out_of_range_fails() -> None:
    payload = json.dumps(
        {
            "relevance_score": 1.5,
            "relevance_reason": "Too high.",
            "value_rationale": "Invalid score.",
        }
    )
    parsed = parse_call2_response(_SOURCE, payload)
    assert parsed.success is False
    assert parsed.parse_failed is True
