"""Parked inbox proxy routes."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.config import STATE_WORKER_BASE_URL


class PromoteBody(BaseModel):
    source_id: str

router = APIRouter(tags=["parked"])


def _proxy(method: str, path: str, *, body: dict[str, Any] | None = None) -> JSONResponse:
    base = STATE_WORKER_BASE_URL.rstrip("/")
    url = f"{base}{path}"
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            status = response.status
    except urllib.error.HTTPError as exc:
        return JSONResponse(
            status_code=exc.code,
            content={"error": "upstream_error", "status": exc.code},
        )
    except urllib.error.URLError:
        return JSONResponse(
            status_code=502,
            content={"error": "upstream_error", "status": 502},
        )

    payload: dict[str, Any] = json.loads(raw) if raw else {}
    return JSONResponse(status_code=status, content=payload)


@router.get("/parked")
def get_parked() -> JSONResponse:
    return _proxy("GET", "/parked")


@router.post("/parked/promote")
def post_parked_promote(body: PromoteBody) -> JSONResponse:
    return _proxy("POST", "/parked/promote", body={"source_id": body.source_id})
