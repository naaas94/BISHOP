"""Tests for G3 model-string verification gate (M3 T1)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from anthropic import BadRequestError

from bishop_shared.anthropic_config import verify_model_string

SCRIPT_PATH = Path("scripts/verify-g3.sh")
PS1_PATH = Path("scripts/verify-g3.ps1")
G3_TEST_MODULES = (
    "tests/test_anthropic_config.py",
    "tests/test_verify_g3.py",
)


@pytest.fixture(scope="module")
def script_text() -> str:
    assert SCRIPT_PATH.is_file(), "scripts/verify-g3.sh must exist"
    return SCRIPT_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def ps1_text() -> str:
    assert PS1_PATH.is_file(), "scripts/verify-g3.ps1 must exist"
    return PS1_PATH.read_text(encoding="utf-8")


def test_runs_g3_pytest_modules(script_text: str) -> None:
    for module in G3_TEST_MODULES:
        assert module in script_text


def test_skips_live_probe_without_api_key(script_text: str, ps1_text: str) -> None:
    assert "SKIP" in script_text
    assert "ANTHROPIC_API_KEY not set" in script_text
    assert "exit 0" in script_text
    assert "SKIP" in ps1_text
    assert "ANTHROPIC_API_KEY not set" in ps1_text


def test_exits_nonzero_on_failure(script_text: str) -> None:
    assert "set -euo pipefail" in script_text


def test_verify_model_string_success() -> None:
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock()

    with patch("anthropic.Anthropic", return_value=mock_client):
        assert verify_model_string(api_key="sk-test") is True

    mock_client.messages.create.assert_called_once()
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-haiku-4-5-20251001"
    assert call_kwargs["max_tokens"] == 1


def test_verify_model_string_http_400_returns_false() -> None:
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = BadRequestError(
        message="invalid model",
        response=MagicMock(status_code=400),
        body=None,
    )

    with patch("anthropic.Anthropic", return_value=mock_client):
        assert verify_model_string(api_key="sk-test") is False


def test_verify_model_string_requires_api_key() -> None:
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        verify_model_string(api_key=None)
