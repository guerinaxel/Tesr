from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict

import numpy as np
from django.test import SimpleTestCase


class FakeIndexFlatIP:
    def __init__(self, dim: int) -> None:
        self.dim = dim
        self.added = None
        self.search_queries = []
        self.search_result = (
            np.array([[0.9, 0.8]], dtype=float),
            np.array([[0, 1]], dtype=int),
        )

    def add(self, embeddings: np.ndarray) -> None:  # type: ignore[override]
        self.added = embeddings

    def search(self, query_emb: np.ndarray, k: int):  # type: ignore[override]
        self.search_queries.append((query_emb, k))
        return self.search_result


class FakeModel:
    def __init__(self, *_: Any, **__: Any) -> None:
        self.encodes = []

    def encode(self, texts, convert_to_numpy=True, normalize_embeddings=True):  # type: ignore[override]
        self.encodes.append(
            {
                "texts": texts,
                "convert_to_numpy": convert_to_numpy,
                "normalize_embeddings": normalize_embeddings,
            }
        )
        if isinstance(texts, list) and len(texts) and isinstance(texts[0], str):
            count = len(texts)
        else:
            count = 1
        return np.full((count, 3), 0.5, dtype=float)


class FakeJoblib:
    def __init__(self, storage: Dict[str, Any]) -> None:
        self.storage = storage

    def dump(self, obj: Any, path: Path) -> None:
        self.storage[str(path)] = obj

    def load(self, path: Path) -> Any:
        return self.storage[str(path)]


class RagIndexWithFakes(SimpleTestCase):
    def setUp(self) -> None:
        self.fake_storage: Dict[str, Any] = {}
        sys.modules["faiss"] = types.SimpleNamespace(
            IndexFlatIP=FakeIndexFlatIP,
            write_index=lambda index, path: self.fake_storage.__setitem__("written", (index, str(path))),
            read_index=lambda path: FakeIndexFlatIP(3),
        )
        sys.modules["sentence_transformers"] = types.SimpleNamespace(
            SentenceTransformer=FakeModel
        )
        sys.modules["joblib"] = FakeJoblib(self.fake_storage)

        from codeqa import rag_index as rag_index_module

        importlib.reload(rag_index_module)
        self.rag_index_module = rag_index_module

    def test_build_from_texts_persists_embeddings_and_docs(self) -> None:
        from codeqa.rag_index import RagConfig, RagIndex

        with TemporaryDirectory() as tmp:
            config = RagConfig(
                index_path=Path(tmp) / "idx.faiss",
                docs_path=Path(tmp) / "docs.pkl",
            )
            rag_index = RagIndex(config)
            rag_index.build_from_texts(["alpha", "beta"])

            written_index, saved_path = self.fake_storage["written"]
            self.assertIsInstance(written_index, FakeIndexFlatIP)
            self.assertEqual(str(config.index_path), saved_path)
            self.assertEqual(["alpha", "beta"], self.fake_storage[str(config.docs_path)])
            self.assertEqual(["alpha", "beta"], rag_index._docs)
            self.assertIsInstance(rag_index._index, FakeIndexFlatIP)

    def test_load_reads_index_and_documents(self) -> None:
        from codeqa.rag_index import RagConfig, RagIndex

        with TemporaryDirectory() as tmp:
            index_path = Path(tmp) / "idx.faiss"
            docs_path = Path(tmp) / "docs.pkl"
            self.fake_storage[str(docs_path)] = ["doc1", "doc2"]

            config = RagConfig(index_path=index_path, docs_path=docs_path)
            rag_index = RagIndex(config)

            rag_index.load()

            self.assertIsInstance(rag_index._index, FakeIndexFlatIP)
            self.assertEqual(["doc1", "doc2"], rag_index._docs)

    def test_search_returns_scored_results(self) -> None:
        from codeqa.rag_index import RagConfig, RagIndex

        rag_index = RagIndex(
            RagConfig(index_path=Path("idx"), docs_path=Path("docs"))
        )
        rag_index._index = FakeIndexFlatIP(3)
        rag_index._docs = ["first doc", "second doc"]

        results = rag_index.search("What is inside?", k=2)

        self.assertEqual(2, len(results))
        self.assertEqual(("first doc", 0.9), results[0])
        self.assertEqual(("second doc", 0.8), results[1])
