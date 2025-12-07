from __future__ import annotations

import json
import os
from collections import OrderedDict
from collections import OrderedDict
import json
import os
from dataclasses import dataclass
from typing import Protocol

import numpy as np

try:  # Redis is optional and only used when configured.
    import redis
except Exception:  # pragma: no cover - optional dependency
    redis = None  # type: ignore


class QueryEmbeddingCache(Protocol):
    def get(self, query: str) -> np.ndarray | None:
        ...

    def set(self, query: str, embedding: np.ndarray) -> None:
        ...


@dataclass
class InMemoryEmbeddingCache:
    """Simple LRU cache to avoid recomputing embeddings for repeated queries."""

    max_size: int = 512

    def __post_init__(self) -> None:
        self._entries: OrderedDict[str, np.ndarray] = OrderedDict()

    def get(self, query: str) -> np.ndarray | None:
        key = query.strip()
        if not key:
            return None
        embedding = self._entries.get(key)
        if embedding is not None:
            self._entries.move_to_end(key)
        return embedding

    def set(self, query: str, embedding: np.ndarray) -> None:
        key = query.strip()
        if not key:
            return
        self._entries[key] = embedding
        self._entries.move_to_end(key)
        if len(self._entries) > self.max_size:
            self._entries.popitem(last=False)


class RedisEmbeddingCache:
    """Redis-backed cache; stores embeddings as JSON arrays for portability."""

    def __init__(self, client: "redis.Redis[bytes]", namespace: str = "rag:embeddings") -> None:
        if redis is None:  # pragma: no cover - guard in case redis is missing
            raise ImportError("Redis support requires the 'redis' package to be installed.")
        self._client = client
        self._namespace = namespace

    def _key(self, query: str) -> str:
        return f"{self._namespace}:{query.strip()}"

    def get(self, query: str) -> np.ndarray | None:
        if not query.strip():
            return None
        raw = self._client.get(self._key(query))
        if raw is None:
            return None
        try:
            data = json.loads(raw)
            return np.array(data, dtype=float)
        except Exception:
            return None

    def set(self, query: str, embedding: np.ndarray) -> None:
        if not query.strip():
            return
        payload = json.dumps(embedding.tolist())
        self._client.set(self._key(query), payload)


def build_cache_from_env() -> QueryEmbeddingCache:
    backend = os.getenv("RAG_CACHE_BACKEND", "memory").lower()
    if backend == "redis":
        if redis is None:
            raise ImportError(
                "RAG_CACHE_BACKEND=redis requires the 'redis' package. Install it or switch to 'memory'."
            )
        url = os.getenv("RAG_CACHE_REDIS_URL", "redis://localhost:6379/0")
        client = redis.from_url(url)  # type: ignore[arg-type]
        return RedisEmbeddingCache(client)

    max_size = int(os.getenv("RAG_CACHE_MAX_SIZE", "512"))
    return InMemoryEmbeddingCache(max_size=max_size)

