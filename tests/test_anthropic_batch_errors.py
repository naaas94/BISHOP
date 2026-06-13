"""Unit tests for bishop_shared.anthropic_batch_errors."""

from __future__ import annotations

from unittest.mock import MagicMock

from anthropic import BadRequestError

from bishop_shared.anthropic_batch_errors import anthropic_batch_400_event


def _bad_request(message: str) -> BadRequestError:
    return BadRequestError(
        message=message,
        response=MagicMock(status_code=400),
        body={"error": {"message": message}},
    )


def test_anthropic_batch_400_event_custom_id() -> None:
    exc = _bad_request("requests.0.custom_id: String should match pattern")
    assert anthropic_batch_400_event(exc) == "batch_custom_id_rejected"


def test_anthropic_batch_400_event_model() -> None:
    exc = _bad_request("model: invalid model string")
    assert anthropic_batch_400_event(exc) == "model_string_fatal"


def test_anthropic_batch_400_event_generic() -> None:
    exc = _bad_request("malformed request body")
    assert anthropic_batch_400_event(exc) == "batch_submit_rejected"
