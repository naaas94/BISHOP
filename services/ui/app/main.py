"""BISHOP HTMX UI — query-api client only (M7 T7)."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import LOG_LEVEL, QUERY_API_URL
from bishop_shared.constants import QUERY_API_HOST_PORT, STATE_WORKER_INTERNAL_PORT

logger = logging.getLogger(__name__)

UI_CONTAINER_PORT = QUERY_API_HOST_PORT - STATE_WORKER_INTERNAL_PORT

_APP_DIR = Path(__file__).resolve().parent
_STATIC_DIR = _APP_DIR.parent / "static"

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
templates = Jinja2Templates(directory=str(_APP_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


def _query_api_get(path: str, *, params: dict[str, str] | None = None) -> tuple[int, Any | None]:
    base = QUERY_API_URL.rstrip("/")
    url = f"{base}{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
            status = response.status
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except urllib.error.URLError:
        return 502, None

    if not body:
        return status, {}
    return status, json.loads(body)


def _sort_batches_completed_desc(batches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        batches,
        key=lambda item: item.get("completed_at") or "",
        reverse=True,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/batches", status_code=302)


@app.get("/batches", response_class=HTMLResponse)
def batch_list(request: Request) -> HTMLResponse:
    code, payload = _query_api_get("/batches", params={"status": "complete"})
    batches: list[dict[str, Any]] = []
    error: str | None = None
    if code == 200 and isinstance(payload, dict):
        raw = payload.get("batches", [])
        if isinstance(raw, list):
            batches = _sort_batches_completed_desc(raw)
    else:
        error = f"query-api returned status {code}"
        logger.warning(
            "batch list upstream failure",
            extra={"event": "ui_batch_list_failed", "status": code},
        )

    return templates.TemplateResponse(
        request,
        "batches.html",
        {"batches": batches, "error": error},
    )


@app.get("/batches/{batch_id}", response_class=HTMLResponse)
def batch_detail(request: Request, batch_id: str) -> HTMLResponse:
    code, payload = _query_api_get(f"/batches/{urllib.parse.quote(batch_id, safe='')}")
    batch: dict[str, Any] | None = None
    entries: list[dict[str, Any]] = []
    error: str | None = None
    if code == 200 and isinstance(payload, dict):
        batch = payload.get("batch")
        raw_entries = payload.get("entries", [])
        if isinstance(raw_entries, list):
            entries = raw_entries
    else:
        error = f"query-api returned status {code}"
        logger.warning(
            "batch detail upstream failure",
            extra={"event": "ui_batch_detail_failed", "status": code},
        )

    return templates.TemplateResponse(
        request,
        "batch_detail.html",
        {"batch": batch, "entries": entries, "error": error},
    )


@app.get("/entries/{source_id:path}", response_class=HTMLResponse)
def entry_detail(request: Request, source_id: str) -> HTMLResponse:
    code, payload = _query_api_get(f"/entries/{source_id}")
    entry: dict[str, Any] | None = None
    error: str | None = None
    if code == 200 and isinstance(payload, dict):
        entry = payload
    elif code == 404:
        error = "Entry not found"
    else:
        error = f"query-api returned status {code}"
        logger.warning(
            "entry detail upstream failure",
            extra={"event": "ui_entry_detail_failed", "source_id": source_id, "status": code},
        )

    return templates.TemplateResponse(
        request,
        "entry_detail.html",
        {"entry": entry, "error": error},
    )


@app.get("/search", response_class=HTMLResponse)
def search(
    request: Request,
    q: str = Query(default=""),
) -> HTMLResponse:
    hits: list[dict[str, Any]] = []
    search_meta: dict[str, Any] = {}
    error: str | None = None

    if q.strip():
        code, payload = _query_api_get("/search", params={"q": q.strip()})
        if code == 200 and isinstance(payload, dict):
            search_meta = {
                "problem_shaped": payload.get("problem_shaped", False),
                "channels_active": payload.get("channels_active", []),
                "total": payload.get("total", 0),
            }
            raw_hits = payload.get("hits", [])
            if isinstance(raw_hits, list):
                hits = raw_hits
        else:
            error = f"query-api returned status {code}"
            logger.warning(
                "search upstream failure",
                extra={"event": "ui_search_failed", "status": code, "query": q[:200]},
            )

    context = {
        "q": q,
        "hits": hits,
        "search_meta": search_meta,
        "error": error,
    }
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(request, "partials/search_results.html", context)
    return templates.TemplateResponse(request, "search.html", context)


def run() -> None:
    import uvicorn

    logging.basicConfig(level=getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    uvicorn.run(app, host="0.0.0.0", port=UI_CONTAINER_PORT)


if __name__ == "__main__":
    run()
