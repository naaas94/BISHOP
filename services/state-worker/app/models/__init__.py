"""Pydantic models for state-worker HTTP responses."""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]


class DbHealthResponse(BaseModel):
    status: Literal["ok", "error"]
    detail: str | None = None
