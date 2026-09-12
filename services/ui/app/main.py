"""BISHOP HTMX UI — query-api client only (M7 T7)."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, Query, Request
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


def _query_api_request(
    method: str,
    path: str,
    *,
    params: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
) -> tuple[int, Any | None]:
    base = QUERY_API_URL.rstrip("/")
    url = f"{base}{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            status = response.status
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            payload = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            payload = None
        return exc.code, payload
    except urllib.error.URLError:
        return 502, None

    if not raw:
        return status, {}
    return status, json.loads(raw)


def _query_api_get(path: str, *, params: dict[str, str] | None = None) -> tuple[int, Any | None]:
    return _query_api_request("GET", path, params=params)


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


READING_STATUS_OPTIONS = ("unread", "reading", "read", "archived")


@app.get("/parked", response_class=HTMLResponse)
def parked_page(request: Request) -> HTMLResponse:
    code, payload = _query_api_get("/parked")
    entries: list[dict[str, Any]] = []
    error: str | None = None
    if code == 200 and isinstance(payload, dict):
        raw = payload.get("entries", [])
        if isinstance(raw, list):
            entries = raw
    else:
        error = f"query-api returned status {code}"
        logger.warning(
            "parked list upstream failure",
            extra={"event": "ui_parked_failed", "status": code},
        )

    return templates.TemplateResponse(
        request,
        "parked.html",
        {"entries": entries, "error": error, "message": None},
    )


@app.post("/parked/{source_id:path}/promote", response_class=HTMLResponse)
def parked_promote(request: Request, source_id: str) -> HTMLResponse:
    code, _payload = _query_api_request(
        "POST",
        "/parked/promote",
        body={"source_id": source_id},
    )
    message: str | None = None
    error: str | None = None
    if code == 200:
        message = f"Promoted {source_id} — scrape and enrichment will run next"
        logger.info(
            "parked promote",
            extra={"event": "manual_parked_promote", "source_id": source_id},
        )
    else:
        error = f"Promote failed (status {code})"

    code_list, payload = _query_api_get("/parked")
    entries: list[dict[str, Any]] = []
    if code_list == 200 and isinstance(payload, dict):
        raw = payload.get("entries", [])
        if isinstance(raw, list):
            entries = raw

    return templates.TemplateResponse(
        request,
        "parked.html",
        {"entries": entries, "error": error, "message": message},
    )


@app.get("/escalations", response_class=HTMLResponse)
def escalations_page(request: Request) -> HTMLResponse:
    code, payload = _query_api_get("/escalations")
    entries: list[dict[str, Any]] = []
    error: str | None = None
    if code == 200 and isinstance(payload, dict):
        raw = payload.get("entries", [])
        if isinstance(raw, list):
            entries = raw
    else:
        error = f"query-api returned status {code}"
        logger.warning(
            "escalations upstream failure",
            extra={"event": "ui_escalations_failed", "status": code},
        )

    return templates.TemplateResponse(
        request,
        "escalations.html",
        {"entries": entries, "error": error, "message": None},
    )


@app.post("/escalations/{source_id:path}/retry", response_class=HTMLResponse)
def escalations_retry(request: Request, source_id: str) -> HTMLResponse:
    quoted = urllib.parse.quote(source_id, safe="")
    code, _payload = _query_api_request("POST", f"/entries/{quoted}/retry")
    message: str | None = None
    error: str | None = None
    if code == 200:
        message = f"Retry queued for {source_id}"
        logger.info(
            "escalation retry",
            extra={"event": "manual_retry", "source_id": source_id},
        )
    else:
        error = f"Retry failed (status {code})"

    code_list, payload = _query_api_get("/escalations")
    entries: list[dict[str, Any]] = []
    if code_list == 200 and isinstance(payload, dict):
        raw = payload.get("entries", [])
        if isinstance(raw, list):
            entries = raw

    return templates.TemplateResponse(
        request,
        "escalations.html",
        {"entries": entries, "error": error, "message": message},
    )


@app.post("/escalations/{source_id:path}/permanent-fail", response_class=HTMLResponse)
def escalations_permanent_fail(request: Request, source_id: str) -> HTMLResponse:
    quoted = urllib.parse.quote(source_id, safe="")
    code, _payload = _query_api_request("POST", f"/entries/{quoted}/permanent-fail")
    message: str | None = None
    error: str | None = None
    if code == 200:
        message = f"Marked {source_id} permanently failed"
        logger.info(
            "escalation permanent-fail",
            extra={"event": "manual_permanent_fail", "source_id": source_id},
        )
    else:
        error = f"Permanent-fail failed (status {code})"

    code_list, payload = _query_api_get("/escalations")
    entries: list[dict[str, Any]] = []
    if code_list == 200 and isinstance(payload, dict):
        raw = payload.get("entries", [])
        if isinstance(raw, list):
            entries = raw

    return templates.TemplateResponse(
        request,
        "escalations.html",
        {"entries": entries, "error": error, "message": message},
    )


@app.get("/explorer", response_class=HTMLResponse)
def explorer(
    request: Request,
    q: str = Query(default=""),
    source: str = Query(default=""),
    type: str = Query(default=""),
    reading_status: str = Query(default=""),
    min_relevance: str = Query(default=""),
    days: str = Query(default=""),
    tags: str = Query(default=""),
) -> HTMLResponse:
    hits: list[dict[str, Any]] = []
    search_meta: dict[str, Any] = {}
    error: str | None = None
    filters = {
        "q": q,
        "source": source,
        "type": type,
        "reading_status": reading_status,
        "min_relevance": min_relevance,
        "days": days,
        "tags": tags,
    }

    if q.strip():
        params: dict[str, str] = {"q": q.strip()}
        if source.strip():
            params["source"] = source.strip()
        if type.strip():
            params["type"] = type.strip()
        if reading_status.strip():
            params["reading_status"] = reading_status.strip()
        if min_relevance.strip():
            params["min_relevance"] = min_relevance.strip()
        if days.strip():
            params["days"] = days.strip()
        if tags.strip():
            params["tags"] = tags.strip()

        code, payload = _query_api_get("/search", params=params)
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
                "explorer search failure",
                extra={"event": "ui_explorer_failed", "status": code},
            )

    return templates.TemplateResponse(
        request,
        "explorer.html",
        {
            "filters": filters,
            "hits": hits,
            "search_meta": search_meta,
            "error": error,
            "reading_status_options": READING_STATUS_OPTIONS,
        },
    )


@app.post("/entries/{source_id:path}/reading-status", response_class=HTMLResponse)
def entry_reading_status_update(
    request: Request,
    source_id: str,
    reading_status: str = Form(...),
) -> HTMLResponse:
    quoted = urllib.parse.quote(source_id, safe="")
    code, _payload = _query_api_request(
        "PATCH",
        f"/entries/{quoted}/reading-status",
        body={"reading_status": reading_status},
    )
    status_message: str | None = None
    error: str | None = None
    if code == 200:
        status_message = f"Reading status updated to {reading_status}"
    else:
        error = f"Update failed (status {code})"

    code_get, payload = _query_api_get(f"/entries/{quoted}")
    entry: dict[str, Any] | None = None
    if code_get == 200 and isinstance(payload, dict):
        entry = payload
    elif code_get == 404:
        error = error or "Entry not found"

    return templates.TemplateResponse(
        request,
        "entry_detail.html",
        {
            "entry": entry,
            "error": error,
            "status_message": status_message,
            "reading_status_options": READING_STATUS_OPTIONS,
        },
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
        {
            "entry": entry,
            "error": error,
            "status_message": None,
            "reading_status_options": READING_STATUS_OPTIONS,
        },
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
