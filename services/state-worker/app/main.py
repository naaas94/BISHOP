"""state-worker FastAPI application (M0: GET /health only)."""

from fastapi import FastAPI

from app.models import HealthResponse
from bishop_shared.constants import STATE_WORKER_INTERNAL_PORT

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


def run() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=STATE_WORKER_INTERNAL_PORT)


if __name__ == "__main__":
    run()
