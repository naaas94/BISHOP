"""JSON parsers for enrichment batch results (Call 1 and Call 2)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from bishop_shared.tag_taxonomy import validate_tags

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)

_VALID_ENTRY_TYPES = frozenset(
    {"paper", "model", "dataset", "repo", "article", "spec", "idea", "benchmark", "other"}
)


@dataclass(frozen=True)
class ParsedCall1Response:
    source_id: str
    success: bool
    summary: str | None = None
    concepts: list[str] | None = None
    tags: list[str] | None = None
    oov_tags_stripped: list[str] | None = None
    entry_type: str | None = None
    challenge_hooks: list[str] | None = None
    error_message: str | None = None
    parse_failed: bool = False


@dataclass(frozen=True)
class ParsedCall2Response:
    source_id: str
    success: bool
    relevance_score: float | None = None
    relevance_reason: str | None = None
    value_rationale: str | None = None
    error_message: str | None = None
    parse_failed: bool = False


def _parse_json_object(text: str) -> dict[str, object] | None:
    candidate = text.strip()
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        match = _JSON_OBJECT_RE.search(candidate)
        if match is None:
            return None
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    if not isinstance(payload, dict):
        return None
    return payload


def _as_string_list(value: object) -> list[str] | None:
    if not isinstance(value, list):
        return None
    if not all(isinstance(item, str) for item in value):
        return None
    return [item.strip() for item in value if item.strip()]


def parse_call1_response(source_id: str, text: str | None) -> ParsedCall1Response:
    """Parse Call 1 JSON; strip OOV tags without failing the entry."""
    if not text:
        return ParsedCall1Response(
            source_id=source_id,
            success=False,
            error_message="empty model response",
            parse_failed=True,
        )
    payload = _parse_json_object(text)
    if payload is None:
        return ParsedCall1Response(
            source_id=source_id,
            success=False,
            error_message="malformed JSON response",
            parse_failed=True,
        )

    summary = payload.get("summary")
    concepts_raw = payload.get("concepts")
    tags_raw = payload.get("tags")
    entry_type = payload.get("entry_type")
    challenge_hooks_raw = payload.get("challenge_hooks")

    if not isinstance(summary, str) or not summary.strip():
        return ParsedCall1Response(
            source_id=source_id,
            success=False,
            error_message="malformed JSON response",
            parse_failed=True,
        )
    concepts = _as_string_list(concepts_raw)
    if concepts is None or not concepts:
        return ParsedCall1Response(
            source_id=source_id,
            success=False,
            error_message="malformed JSON response",
            parse_failed=True,
        )
    if not isinstance(tags_raw, list):
        return ParsedCall1Response(
            source_id=source_id,
            success=False,
            error_message="malformed JSON response",
            parse_failed=True,
        )
    raw_tags = [tag for tag in tags_raw if isinstance(tag, str)]
    validated_tags, stripped_tags = validate_tags(raw_tags)

    if not isinstance(entry_type, str) or entry_type not in _VALID_ENTRY_TYPES:
        return ParsedCall1Response(
            source_id=source_id,
            success=False,
            error_message="malformed JSON response",
            parse_failed=True,
        )
    challenge_hooks = _as_string_list(challenge_hooks_raw)
    if challenge_hooks is None or not challenge_hooks:
        return ParsedCall1Response(
            source_id=source_id,
            success=False,
            error_message="malformed JSON response",
            parse_failed=True,
        )

    return ParsedCall1Response(
        source_id=source_id,
        success=True,
        summary=summary.strip(),
        concepts=concepts,
        tags=validated_tags,
        oov_tags_stripped=stripped_tags if stripped_tags else None,
        entry_type=entry_type,
        challenge_hooks=challenge_hooks,
        parse_failed=False,
    )


def parse_call2_response(source_id: str, text: str | None) -> ParsedCall2Response:
    """Parse Call 2 JSON relevance fields."""
    if not text:
        return ParsedCall2Response(
            source_id=source_id,
            success=False,
            error_message="empty model response",
            parse_failed=True,
        )
    payload = _parse_json_object(text)
    if payload is None:
        return ParsedCall2Response(
            source_id=source_id,
            success=False,
            error_message="malformed JSON response",
            parse_failed=True,
        )

    score = payload.get("relevance_score")
    relevance_reason = payload.get("relevance_reason")
    value_rationale = payload.get("value_rationale")

    if not isinstance(score, (int, float)) or score < 0.0 or score > 1.0:
        return ParsedCall2Response(
            source_id=source_id,
            success=False,
            error_message="malformed JSON response",
            parse_failed=True,
        )
    if not isinstance(relevance_reason, str) or not relevance_reason.strip():
        return ParsedCall2Response(
            source_id=source_id,
            success=False,
            error_message="malformed JSON response",
            parse_failed=True,
        )
    if not isinstance(value_rationale, str) or not value_rationale.strip():
        return ParsedCall2Response(
            source_id=source_id,
            success=False,
            error_message="malformed JSON response",
            parse_failed=True,
        )

    return ParsedCall2Response(
        source_id=source_id,
        success=True,
        relevance_score=float(score),
        relevance_reason=relevance_reason.strip(),
        value_rationale=value_rationale.strip(),
        parse_failed=False,
    )
