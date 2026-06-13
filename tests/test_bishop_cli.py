"""Unit tests for bishop Typer CLI (M7 T6)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from bishop_cli.main import app

_RUNNER = CliRunner()
_REPO_ROOT = Path(__file__).resolve().parent.parent

_SEARCH_PAYLOAD = {
    "query": "RAG",
    "problem_shaped": False,
    "channels_active": ["bm25_main", "dense"],
    "hits": [],
    "total": 0,
}

_RECENT_PAYLOAD = {"entries": [], "total": 0}

_BATCH_PAYLOAD = {"batch": {"batch_id": "b1"}, "entries": []}

_ESCALATIONS_PAYLOAD = {"escalations": []}


def _read_pyproject_scripts() -> dict[str, str]:
    text = (_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    in_scripts = False
    scripts: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "[project.scripts]":
            in_scripts = True
            continue
        if in_scripts:
            if stripped.startswith("[") and stripped.endswith("]"):
                break
            if "=" in stripped:
                name, target = stripped.split("=", 1)
                scripts[name.strip()] = target.strip().strip('"')
    return scripts


def test_console_script_name_is_bishop() -> None:
    scripts = _read_pyproject_scripts()
    assert "bishop" in scripts
    assert scripts["bishop"] == "bishop_cli.main:app"


@respx.mock
def test_search_calls_search_route_with_query_params() -> None:
    route = respx.get("http://localhost:8080/search").mock(
        return_value=httpx.Response(200, json=_SEARCH_PAYLOAD),
    )
    result = _RUNNER.invoke(
        app,
        [
            "search",
            "RAG systems",
            "--domain",
            "professional",
            "--type",
            "paper",
            "--tags",
            "RAG,retrieval",
            "--min-relevance",
            "0.5",
            "--days",
            "14",
            "--source",
            "arxiv",
            "--reading-status",
            "unread",
        ],
    )
    assert result.exit_code == 0, result.output
    assert route.called
    request = route.calls.last.request
    assert request.url.path == "/search"
    assert request.url.params["q"] == "RAG systems"
    assert request.url.params["domain"] == "professional"
    assert request.url.params["type"] == "paper"
    assert request.url.params["tags"] == "RAG,retrieval"
    assert request.url.params["min_relevance"] == "0.5"
    assert request.url.params["days"] == "14"
    assert request.url.params["source"] == "arxiv"
    assert request.url.params["reading_status"] == "unread"


@respx.mock
def test_search_emits_utf8_query_string(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QUERY_API_BASE_URL", raising=False)
    query = "café naïve résumé"
    respx.get("http://localhost:8080/search").mock(
        return_value=httpx.Response(
            200,
            json={**_SEARCH_PAYLOAD, "query": query},
        ),
    )
    result = _RUNNER.invoke(app, ["search", query])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["query"] == query


@respx.mock
def test_recent_calls_recent_route() -> None:
    route = respx.get("http://localhost:8080/recent").mock(
        return_value=httpx.Response(200, json=_RECENT_PAYLOAD),
    )
    result = _RUNNER.invoke(
        app,
        ["recent", "--source", "arxiv", "--days", "3", "--domain", "professional"],
    )
    assert result.exit_code == 0, result.output
    assert route.called
    request = route.calls.last.request
    assert request.url.path == "/recent"
    assert request.url.params["source"] == "arxiv"
    assert request.url.params["days"] == "3"
    assert request.url.params["domain"] == "professional"


@respx.mock
def test_batch_calls_batch_detail_route() -> None:
    route = respx.get("http://localhost:8080/batches/batch-42").mock(
        return_value=httpx.Response(200, json=_BATCH_PAYLOAD),
    )
    result = _RUNNER.invoke(app, ["batch", "batch-42"])
    assert result.exit_code == 0, result.output
    assert route.called
    assert route.calls.last.request.url.path == "/batches/batch-42"


@respx.mock
def test_escalations_calls_escalations_route() -> None:
    route = respx.get("http://localhost:8080/escalations").mock(
        return_value=httpx.Response(200, json=_ESCALATIONS_PAYLOAD),
    )
    result = _RUNNER.invoke(app, ["escalations"])
    assert result.exit_code == 0, result.output
    assert route.called
    assert route.calls.last.request.url.path == "/escalations"


@respx.mock
def test_upstream_error_exits_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    """Falsifier: CLI must not report success on query-api 404."""
    monkeypatch.delenv("QUERY_API_BASE_URL", raising=False)
    respx.get("http://localhost:8080/search").mock(
        return_value=httpx.Response(
            404,
            json={"error": "not_found", "detail": "missing"},
        ),
    )
    result = _RUNNER.invoke(app, ["search", "missing"])
    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["error"] == "not_found"
