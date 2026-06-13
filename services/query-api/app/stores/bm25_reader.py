"""Per-domain BM25 read index (main + challenge_hooks) with COW reload (M7 T2)."""

from __future__ import annotations

import asyncio
import logging
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from rank_bm25 import BM25Okapi

from bishop_shared.bm25_tokenize import tokenize_bm25
from bishop_shared.indexing_config import (
    BM25_CHALLENGE_HOOKS_SUBDIR,
    BM25_MAIN_SUBDIR,
    bm25_domain_root,
)
from bishop_shared.query_config import BM25_RELOAD_INTERVAL_SEC

logger = logging.getLogger(__name__)

INDEX_FILENAME = "index.pkl"
Bm25Channel = Literal["main", "challenge_hooks"]


@dataclass(frozen=True)
class _LoadedIndex:
    """Immutable in-memory BM25 snapshot for copy-on-write reload."""

    corpus: tuple[tuple[str, ...], ...]
    source_ids: tuple[str, ...]
    bm25: BM25Okapi | None

    @classmethod
    def empty(cls) -> _LoadedIndex:
        return cls(corpus=(), source_ids=(), bm25=None)


def _payload_to_loaded(payload: dict[str, object]) -> _LoadedIndex:
    raw_corpus = payload.get("corpus", [])
    raw_source_ids = payload.get("source_ids", [])
    corpus = tuple(tuple(tokens) for tokens in raw_corpus)  # type: ignore[arg-type]
    source_ids = tuple(str(source_id) for source_id in raw_source_ids)
    if len(corpus) != len(source_ids):
        raise ValueError("corpus and source_ids length mismatch")
    bm25 = BM25Okapi([list(doc) for doc in corpus]) if corpus else None
    return _LoadedIndex(corpus=corpus, source_ids=source_ids, bm25=bm25)


def _read_index_file(path: Path) -> _LoadedIndex:
    if not path.is_file():
        return _LoadedIndex.empty()
    with path.open("rb") as handle:
        payload = pickle.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("BM25 pickle payload must be a dict")
    if set(payload.keys()) != {"corpus", "source_ids"}:
        raise ValueError("BM25 pickle schema must be corpus + source_ids only")
    return _payload_to_loaded(payload)


class Bm25QueryIndex:
    """Load/search/reload main and challenge_hooks BM25 indices for one domain."""

    def __init__(self, domain: str) -> None:
        self.domain = domain
        domain_root = bm25_domain_root(domain)
        self._main_path = domain_root / BM25_MAIN_SUBDIR / INDEX_FILENAME
        self._hooks_path = domain_root / BM25_CHALLENGE_HOOKS_SUBDIR / INDEX_FILENAME
        self._main = _LoadedIndex.empty()
        self._hooks = _LoadedIndex.empty()
        self._reload_task: asyncio.Task[None] | None = None

    @property
    def main_path(self) -> Path:
        return self._main_path

    @property
    def hooks_path(self) -> Path:
        return self._hooks_path

    def load(self) -> None:
        """Load main and challenge_hooks indices from disk (empty when missing)."""
        self._main = _read_index_file(self._main_path)
        self._hooks = _read_index_file(self._hooks_path)

    def reload_cow(self, log: logging.Logger | None = None) -> None:
        """Reload both indices via copy-on-write; keep prior snapshot on failure."""
        active_logger = log or logger
        try:
            new_main = _read_index_file(self._main_path)
            new_hooks = _read_index_file(self._hooks_path)
        except (EOFError, OSError, pickle.UnpicklingError, ValueError) as exc:
            active_logger.warning(
                "BM25 reload failed; keeping previous in-memory index",
                extra={
                    "event": "bm25_reload_failed",
                    "domain": self.domain,
                    "channel": "bm25_main",
                },
            )
            active_logger.debug("bm25 reload error detail", exc_info=exc)
            return

        self._main = new_main
        self._hooks = new_hooks

    def search(
        self,
        query: str,
        k: int,
        *,
        channel: Bm25Channel = "main",
    ) -> list[tuple[str, float]]:
        """Return top-k (source_id, bm25_score) pairs for the requested channel."""
        loaded = self._main if channel == "main" else self._hooks
        return _search_loaded(loaded, query, k)

    def start_background_reload(
        self,
        log: logging.Logger | None = None,
        *,
        interval_sec: int | None = None,
    ) -> asyncio.Task[None]:
        """Start periodic COW reload loop; idempotent if already running."""
        if self._reload_task is not None and not self._reload_task.done():
            return self._reload_task
        active_logger = log or logger
        period = BM25_RELOAD_INTERVAL_SEC if interval_sec is None else interval_sec
        self._reload_task = asyncio.create_task(
            self._background_reload_loop(active_logger, period),
            name=f"bm25-reload-{self.domain}",
        )
        return self._reload_task

    async def _background_reload_loop(
        self,
        log: logging.Logger,
        interval_sec: int,
    ) -> None:
        while True:
            await asyncio.sleep(interval_sec)
            self.reload_cow(log)

    async def stop_background_reload(self) -> None:
        if self._reload_task is None:
            return
        self._reload_task.cancel()
        try:
            await self._reload_task
        except asyncio.CancelledError:
            pass
        self._reload_task = None


def _search_loaded(
    loaded: _LoadedIndex,
    query: str,
    k: int,
) -> list[tuple[str, float]]:
    if loaded.bm25 is None or not loaded.source_ids or k <= 0:
        return []
    tokens = tokenize_bm25(query)
    if not tokens:
        return []
    scores = loaded.bm25.get_scores(tokens)
    ranked = sorted(
        enumerate(scores),
        key=lambda item: item[1],
        reverse=True,
    )[:k]
    return [(loaded.source_ids[index], float(score)) for index, score in ranked]
