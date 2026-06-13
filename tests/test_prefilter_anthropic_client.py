"""Unit tests for AnthropicBatchClient (M3 T4)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from anthropic import BadRequestError

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PREFILTER_ROOT = _REPO_ROOT / "services" / "pre-filter-worker"


def _load_anthropic_client_stack() -> tuple[ModuleType, ModuleType]:
    saved_app_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "app" or name.startswith("app.")
    }
    for name in saved_app_modules:
        del sys.modules[name]

    repo_str = str(_REPO_ROOT)
    prefilter_str = str(_PREFILTER_ROOT)
    path_state: list[str] = []
    for path_str in (prefilter_str, repo_str):
        if path_str not in sys.path:
            sys.path.insert(0, path_str)
            path_state.append(path_str)

    try:
        import app.anthropic_batch_client as anthropic_mod  # noqa: WPS433
        import app.models as models  # noqa: WPS433
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.modules.update(saved_app_modules)
        for path_str in path_state:
            sys.path.remove(path_str)

    return anthropic_mod, models


def test_build_requests_custom_id_equals_source_id() -> None:
    anthropic_mod, models = _load_anthropic_client_stack()
    mock_sdk = MagicMock()
    client = anthropic_mod.AnthropicBatchClient(client=mock_sdk)

    entries = [
        models.PreFilterBatchEntry(
            source_id="arxiv:2406.00001",
            title="Paper A",
            abstract="Abstract A",
        ),
        models.PreFilterBatchEntry(
            source_id="arxiv:2406.00002",
            title="Paper B",
            abstract=None,
        ),
    ]
    requests = client.build_requests(system_prompt="system text", entries=entries)

    assert len(requests) == 2
    assert requests[0]["custom_id"] == "arxiv:2406.00001"
    assert requests[1]["custom_id"] == "arxiv:2406.00002"
    assert requests[0]["params"]["model"] == "claude-haiku-4-5-20251001"
    assert requests[0]["params"]["system"] == "system text"
    assert requests[0]["params"]["messages"][0]["content"] == "Paper A\nAbstract A"
    assert requests[1]["params"]["messages"][0]["content"] == "Paper B\n"


def test_submit_pre_filter_batch_returns_external_id() -> None:
    anthropic_mod, models = _load_anthropic_client_stack()
    mock_sdk = MagicMock()
    mock_sdk.messages.batches.create.return_value = SimpleNamespace(id="msgbatch_abc123")
    client = anthropic_mod.AnthropicBatchClient(client=mock_sdk)

    entries = [
        models.PreFilterBatchEntry(
            source_id="arxiv:2406.00001",
            title="Paper A",
            abstract="Abstract A",
        )
    ]
    result = client.submit_pre_filter_batch(system_prompt="system", entries=entries)

    assert result.external_batch_id == "msgbatch_abc123"
    mock_sdk.messages.batches.create.assert_called_once()
    call_kwargs = mock_sdk.messages.batches.create.call_args.kwargs
    assert call_kwargs["requests"][0]["custom_id"] == "arxiv:2406.00001"


def test_submit_pre_filter_batch_or_fatal_logs_model_string_fatal_on_400() -> None:
    anthropic_mod, models = _load_anthropic_client_stack()
    mock_sdk = MagicMock()
    mock_sdk.messages.batches.create.side_effect = BadRequestError(
        message="invalid model",
        response=MagicMock(status_code=400),
        body={"error": {"message": "invalid model"}},
    )
    client = anthropic_mod.AnthropicBatchClient(client=mock_sdk)

    entries = [
        models.PreFilterBatchEntry(
            source_id="arxiv:2406.00001",
            title="Paper A",
            abstract="Abstract A",
        )
    ]
    with patch.object(anthropic_mod.logger, "error") as mock_log:
        result = anthropic_mod.submit_pre_filter_batch_or_fatal(
            client,
            system_prompt="system",
            entries=entries,
        )

    assert result is None
    mock_log.assert_called_once()
    assert mock_log.call_args.kwargs["extra"]["event"] == "model_string_fatal"
