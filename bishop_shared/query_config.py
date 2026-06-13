"""Query path constants (M7 T1 contract surface)."""

from __future__ import annotations

import os

from bishop_shared.enums import DomainEnum

RRF_K = 60
DEFAULT_SEARCH_DOMAIN = DomainEnum.PROFESSIONAL.value


def _int_from_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return int(raw)


BM25_RELOAD_INTERVAL_SEC = _int_from_env("BISHOP_BM25_RELOAD_INTERVAL_SEC", 300)
