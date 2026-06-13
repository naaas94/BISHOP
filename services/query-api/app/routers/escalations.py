"""Escalations proxy route (M7 T5)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import STATE_WORKER_BASE_URL

router = APIRouter(tags=["escalations"])


@router.get("/escalations")
def get_escalations() -> JSONResponse:
    base = STATE_WORKER_BASE_URL.rstrip("/")
    url = f"{base}/escalations"
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
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

    payload: dict[str, Any] = json.loads(body) if body else {}
    return JSONResponse(status_code=status, content=payload)
