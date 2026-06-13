"""Typer CLI for Bishop query-api read path (M7 T6)."""

from __future__ import annotations

import json
import sys
from typing import Any

import httpx
import typer

from bishop_cli.config import QUERY_API_BASE_URL

app = typer.Typer(
    name="bishop",
    help="Query Bishop knowledge-base entries via query-api.",
    no_args_is_help=True,
)


def _ensure_utf8_stdout() -> None:
    stdout = sys.stdout
    if hasattr(stdout, "reconfigure"):
        try:
            stdout.reconfigure(encoding="utf-8")
        except (AttributeError, OSError, ValueError):
            pass


def _base_url() -> str:
    return QUERY_API_BASE_URL.rstrip("/")


def _api_get(path: str, *, params: dict[str, Any] | None = None) -> httpx.Response:
    url = f"{_base_url()}{path}"
    with httpx.Client(timeout=30.0) as client:
        return client.get(url, params=params)


def _emit_response(response: httpx.Response) -> None:
    _ensure_utf8_stdout()
    try:
        payload = response.json()
    except json.JSONDecodeError:
        typer.echo(response.text)
        raise typer.Exit(code=1) from None

    typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
    if response.status_code >= 400:
        raise typer.Exit(code=1)


@app.command("search")
def search(
    query: str = typer.Argument(..., help="Search query string."),
    entry_type: str | None = typer.Option(None, "--type", help="Filter by entry type."),
    days: int | None = typer.Option(None, "--days", min=1, help="Limit to last N days."),
    tags: str | None = typer.Option(None, "--tags", help="Comma-separated tags."),
    min_relevance: float | None = typer.Option(
        None,
        "--min-relevance",
        min=0.0,
        max=1.0,
        help="Minimum relevance score.",
    ),
    domain: str | None = typer.Option(None, "--domain", help="Search domain."),
    source: str | None = typer.Option(None, "--source", help="Source filter."),
    reading_status: str | None = typer.Option(
        None,
        "--reading-status",
        help="Reading status filter.",
    ),
) -> None:
    """Search indexed entries via GET /search."""
    params: dict[str, Any] = {"q": query}
    if entry_type is not None:
        params["type"] = entry_type
    if days is not None:
        params["days"] = days
    if tags is not None:
        params["tags"] = tags
    if min_relevance is not None:
        params["min_relevance"] = min_relevance
    if domain is not None:
        params["domain"] = domain
    if source is not None:
        params["source"] = source
    if reading_status is not None:
        params["reading_status"] = reading_status

    response = _api_get("/search", params=params)
    _emit_response(response)


@app.command("recent")
def recent(
    source: str | None = typer.Option(None, "--source", help="Source filter."),
    days: int | None = typer.Option(None, "--days", min=1, help="Lookback window in days."),
    domain: str | None = typer.Option(None, "--domain", help="Domain filter."),
) -> None:
    """List recent entries via GET /recent."""
    params: dict[str, Any] = {}
    if source is not None:
        params["source"] = source
    if days is not None:
        params["days"] = days
    if domain is not None:
        params["domain"] = domain

    response = _api_get("/recent", params=params or None)
    _emit_response(response)


@app.command("batch")
def batch(
    batch_id: str = typer.Argument(..., help="Batch identifier."),
) -> None:
    """Fetch batch detail via GET /batches/{batch_id}."""
    response = _api_get(f"/batches/{batch_id}")
    _emit_response(response)


@app.command("escalations")
def escalations() -> None:
    """List escalations via GET /escalations."""
    response = _api_get("/escalations")
    _emit_response(response)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
