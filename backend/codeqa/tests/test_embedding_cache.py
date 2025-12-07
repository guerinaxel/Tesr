from __future__ import annotations

import os

import numpy as np
from django.test import SimpleTestCase

from codeqa.embedding_cache import (
    InMemoryEmbeddingCache,
    build_cache_from_env,
)


class InMemoryEmbeddingCacheTests(SimpleTestCase):
    def tearDown(self) -> None:
        os.environ.pop("RAG_CACHE_BACKEND", None)
        os.environ.pop("RAG_CACHE_MAX_SIZE", None)

    def test_sets_and_evicts_embeddings(self) -> None:
        # Arrange
        cache = InMemoryEmbeddingCache(max_size=2)
        first = np.array([1, 2, 3])
        second = np.array([4, 5, 6])
        third = np.array([7, 8, 9])

        # Act
        cache.set("one", first)
        cache.set("two", second)
        cache.set("three", third)

        # Assert
        self.assertIsNone(cache.get("one"))
        np.testing.assert_array_equal(cache.get("three"), third)
        np.testing.assert_array_equal(cache.get("two"), second)

    def test_build_cache_from_env_defaults_to_memory(self) -> None:
        # Arrange
        os.environ["RAG_CACHE_BACKEND"] = "memory"
        os.environ["RAG_CACHE_MAX_SIZE"] = "1"

        # Act
        cache = build_cache_from_env()

        # Assert
        self.assertIsInstance(cache, InMemoryEmbeddingCache)
