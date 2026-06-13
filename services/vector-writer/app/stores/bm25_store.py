"""Per-domain dual BM25 index (main + challenge_hooks) with file lock and atomic persist (M6 T3)."""

from __future__ import annotations

import logging
import pickle
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from filelock import FileLock, Timeout
from rank_bm25 import BM25Okapi

from bishop_shared.atomic_persist import atomic_persist
from bishop_shared.bm25_tokenize import tokenize_bm25
from bishop_shared.indexing_config import (
    BM25_CHALLENGE_HOOKS_SUBDIR,
    BM25_LOCK_NAME,
    BM25_MAIN_SUBDIR,
    bm25_domain_root,
)

logger = logging.getLogger(__name__)

INDEX_FILENAME = "index.pkl"


def _build_main_corpus_text(
    title: str,
    summary: str,
    concepts: Sequence[str] | None,
    tags: Sequence[str] | None,
    challenge_hooks: Sequence[str] | None,
) -> str:
    parts: list[str] = [title, summary]
    if concepts:
        parts.extend(concepts)
    if tags:
        parts.extend(tags)
    if challenge_hooks:
        parts.extend(challenge_hooks)
    return " ".join(p for p in parts if p)


def _build_hooks_corpus_text(challenge_hooks: Sequence[str] | None) -> str:
    return " ".join(challenge_hooks or [])


@dataclass
class _IndexState:
    corpus: list[list[str]] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    bm25: BM25Okapi | None = None

    def has_document(self, source_id: str) -> bool:
        return source_id in self.source_ids

    def add_document(self, source_id: str, tokens: list[str]) -> None:
        if source_id in self.source_ids:
            raise ValueError(f"duplicate source_id: {source_id}")
        self.corpus.append(tokens)
        self.source_ids.append(source_id)
        self.bm25 = BM25Okapi(self.corpus) if self.corpus else None

    def to_payload(self) -> dict[str, object]:
        return {"corpus": self.corpus, "source_ids": self.source_ids}

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> _IndexState:
        corpus = list(payload.get("corpus", []))
        source_ids = list(payload.get("source_ids", []))
        state = cls(corpus=corpus, source_ids=source_ids)
        if state.corpus:
            state.bm25 = BM25Okapi(state.corpus)
        return state


class Bm25DualIndex:
    """In-memory rank-bm25 dual index with per-domain file lock and atomic pickle persist."""

    def __init__(self, domain: str, *, lock_timeout: float = 30.0) -> None:
        self.domain = domain
        self._domain_root = bm25_domain_root(domain)
        self._lock_path = self._domain_root / BM25_LOCK_NAME
        self._main_path = self._domain_root / BM25_MAIN_SUBDIR / INDEX_FILENAME
        self._hooks_path = self._domain_root / BM25_CHALLENGE_HOOKS_SUBDIR / INDEX_FILENAME
        self._lock = FileLock(str(self._lock_path), timeout=lock_timeout)
        self._main = self._load_index(self._main_path)
        self._hooks = self._load_index(self._hooks_path)

    @property
    def lock_path(self) -> Path:
        return self._lock_path

    def _load_index(self, path: Path) -> _IndexState:
        if not path.exists():
            return _IndexState()
        with path.open("rb") as handle:
            payload = pickle.load(handle)
        return _IndexState.from_payload(payload)

    def has_document(self, source_id: str) -> bool:
        return self._main.has_document(source_id)

    def add_main(
        self,
        source_id: str,
        title: str,
        summary: str,
        concepts: Sequence[str] | None,
        tags: Sequence[str] | None,
        challenge_hooks: Sequence[str] | None,
    ) -> None:
        try:
            with self._lock:
                logger.info(
                    "bm25 lock acquired for main add",
                    extra={
                        "event": "bm25_lock_acquired",
                        "source_id": source_id,
                        "domain": self.domain,
                    },
                )
                if self._main.has_document(source_id):
                    raise ValueError(f"duplicate source_id: {source_id}")
                text = _build_main_corpus_text(title, summary, concepts, tags, challenge_hooks)
                self._main.add_document(source_id, tokenize_bm25(text))
        except Timeout as exc:
            logger.error(
                "bm25 lock timeout on main add",
                extra={
                    "event": "bm25_lock_timeout",
                    "source_id": source_id,
                    "domain": self.domain,
                },
            )
            raise Timeout(
                f"BM25 lock timeout for domain {self.domain!r} at {self._lock_path}"
            ) from exc

    def add_challenge_hooks(
        self,
        source_id: str,
        challenge_hooks: Sequence[str] | None,
    ) -> None:
        try:
            with self._lock:
                if self._hooks.has_document(source_id):
                    raise ValueError(f"duplicate source_id: {source_id}")
                text = _build_hooks_corpus_text(challenge_hooks)
                self._hooks.add_document(source_id, tokenize_bm25(text))
        except Timeout as exc:
            logger.error(
                "bm25 lock timeout on challenge_hooks add",
                extra={
                    "event": "bm25_lock_timeout",
                    "source_id": source_id,
                    "domain": self.domain,
                },
            )
            raise Timeout(
                f"BM25 lock timeout for domain {self.domain!r} at {self._lock_path}"
            ) from exc

    def persist(self) -> None:
        try:
            with self._lock:
                logger.info(
                    "bm25 lock acquired for persist",
                    extra={"event": "bm25_lock_acquired", "domain": self.domain},
                )
                self._persist_index(self._main_path, self._main)
                self._persist_index(self._hooks_path, self._hooks)
        except Timeout as exc:
            logger.error(
                "bm25 lock timeout on persist",
                extra={"event": "bm25_lock_timeout", "domain": self.domain},
            )
            raise Timeout(
                f"BM25 lock timeout for domain {self.domain!r} at {self._lock_path}"
            ) from exc

    def _persist_index(self, path: Path, state: _IndexState) -> None:
        payload = state.to_payload()

        def serialize(out: object) -> None:
            pickle.dump(payload, out)  # type: ignore[union-attr]

        atomic_persist(path, serialize)
