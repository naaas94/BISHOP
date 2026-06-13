"""Unit tests for AnthropicBatchPollerClient SDK path (M3/M5 hotfix)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BATCH_POLLER_ROOT = _REPO_ROOT / "services" / "batch-poller"

_EXTERNAL_ID = "msgbatch_poll_1"


def _load_anthropic_client_stack() -> ModuleType:
    saved_app_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "app" or name.startswith("app.")
    }
    for name in saved_app_modules:
        del sys.modules[name]

    repo_str = str(_REPO_ROOT)
    poller_str = str(_BATCH_POLLER_ROOT)
    path_state: list[str] = []
    for path_str in (poller_str, repo_str):
        if path_str not in sys.path:
            sys.path.insert(0, path_str)
            path_state.append(path_str)

    try:
        import app.clients.anthropic as anthropic_mod  # noqa: WPS433
    finally:
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]
        sys.modules.update(saved_app_modules)
        for path_str in path_state:
            sys.path.remove(path_str)

    return anthropic_mod


def test_retrieve_batch_status_uses_messages_batches_retrieve() -> None:
    anthropic_mod = _load_anthropic_client_stack()
    mock_sdk = MagicMock()
    mock_sdk.messages.batches.retrieve.return_value = SimpleNamespace(
        processing_status="in_progress",
    )
    client = anthropic_mod.AnthropicBatchPollerClient(client=mock_sdk)

    status, terminal = asyncio.run(client.retrieve_batch_status(_EXTERNAL_ID))

    assert status == "in_progress"
    assert terminal is None
    mock_sdk.messages.batches.retrieve.assert_called_once_with(_EXTERNAL_ID)


def test_fetch_batch_results_uses_messages_batches_results() -> None:
    anthropic_mod = _load_anthropic_client_stack()
    mock_sdk = MagicMock()
    mock_sdk.messages.batches.results.return_value = [
        SimpleNamespace(
            custom_id="cid1",
            result=SimpleNamespace(
                type="succeeded",
                message=SimpleNamespace(
                    content=[SimpleNamespace(text='{"decision": 1, "rationale": "ok"}')],
                ),
            ),
        ),
    ]
    client = anthropic_mod.AnthropicBatchPollerClient(client=mock_sdk)

    items = asyncio.run(client.fetch_batch_results(_EXTERNAL_ID))

    assert len(items) == 1
    assert items[0].custom_id == "cid1"
    assert items[0].errored is False
    mock_sdk.messages.batches.results.assert_called_once_with(_EXTERNAL_ID)
