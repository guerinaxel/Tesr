from __future__ import annotations

import importlib
import json
import sys
import types
import unittest
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


class FakeKeywordIndex:
    def __init__(self, results: list[tuple[int, float]]) -> None:
        self.results = results
        self.searches: list[tuple[str, int]] = []

    def search(self, query: str, k: int = 5):
        self.searches.append((query, k))
        return self.results[:k]


class FakeInvertedIndex:
    def __init__(self, results: list[tuple[int, float]] | None = None) -> None:
        self.results = results or []
        self.searches: list[tuple[str, int]] = []
        self.built_from: tuple[list[str], Path] | None = None
        self.loaded_from: Path | None = None

    @classmethod
    def build(cls, docs: list[str], root_dir: Path):
        inst = cls()
        inst.built_from = (list(docs), root_dir)
        return inst

    @classmethod
    def from_dir(cls, root_dir: Path):
        inst = cls()
        inst.loaded_from = root_dir
        return inst

    def search(self, query: str, limit: int = 5):
        self.searches.append((query, limit))
        return self.results[:limit]


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
        sys.modules["codeqa.inverted_index"] = types.SimpleNamespace(InvertedIndex=FakeInvertedIndex)
        sys.modules["codeqa.embedding_cache"] = types.SimpleNamespace(
            QueryEmbeddingCache=object,
            build_cache_from_env=lambda: types.SimpleNamespace(
                get=lambda _query: None, set=lambda _query, _embedding: None
            )
        )

        from codeqa import rag_index as rag_index_module

        importlib.reload(rag_index_module)
        self.rag_index_module = rag_index_module
        # Avoid pulling the real Nomic model during tests; use a local placeholder instead.
        rag_index_module.RagConfig.embedding_model_name = "local-test-model"
        rag_index_module.RagConfig.fallback_embedding_model_name = "local-test-model-fallback"
        rag_index_module.InvertedIndex = FakeInvertedIndex

    def test_build_from_texts_persists_embeddings_and_docs(self) -> None:
        from codeqa.rag_index import RagConfig, RagIndex

        # Arrange
        with TemporaryDirectory() as tmp:
            config = RagConfig(
                index_path=Path(tmp) / "idx.faiss",
                docs_path=Path(tmp) / "docs.pkl",
                embedding_model_name="local-model",
                fallback_embedding_model_name="local-fallback",
            )
            rag_index = RagIndex(config)

            # Act
            rag_index.build_from_texts(["alpha", "beta"])

            # Assert
            written_index, saved_path = self.fake_storage["written"]
            self.assertIsInstance(written_index, FakeIndexFlatIP)
            self.assertEqual(str(config.index_path), saved_path)
            self.assertEqual(["alpha", "beta"], self.fake_storage[str(config.docs_path)])
            token_path = str(config.tokenized_docs_path)
            keyword_path = str(config.keyword_index_path)
            embeddings_path = str(config.embeddings_path)
            self.assertIn(token_path, self.fake_storage)
            self.assertIn(keyword_path, self.fake_storage)
            self.assertIn(embeddings_path, self.fake_storage)
            self.assertEqual([["alpha"], ["beta"]], self.fake_storage[token_path])
            self.assertIn("idf", self.fake_storage[keyword_path])
            self.assertEqual((2, 3), self.fake_storage[embeddings_path].shape)
            self.assertEqual(["alpha", "beta"], rag_index._docs)
            self.assertEqual([["alpha"], ["beta"]], rag_index._tokenized_docs)
            self.assertIsInstance(rag_index._index, FakeIndexFlatIP)
            self.assertIsInstance(rag_index._inverted_index, FakeInvertedIndex)
            metadata = json.loads(config.metadata_path.read_text())
            self.assertEqual(config.index_version, metadata["version"])
            self.assertIn("checksum", metadata)
            self.assertIsNotNone(rag_index._doc_embeddings)

    def test_load_reads_index_and_documents(self) -> None:
        from codeqa.rag_index import RagConfig, RagIndex

        # Arrange
        with TemporaryDirectory() as tmp:
            index_path = Path(tmp) / "idx.faiss"
            docs_path = Path(tmp) / "docs.pkl"
            self.fake_storage[str(docs_path)] = ["doc1", "doc2"]
            self.fake_storage[str(docs_path.with_name("docs_tokens.pkl"))] = [
                ["doc1"],
                ["doc2"],
            ]
            self.fake_storage[str(docs_path.with_name("docs_keywords.pkl"))] = {
                "idf": {},
                "doc_lengths": [1, 1],
                "avgdl": 1.0,
            }
            embeddings_path = docs_path.with_name("docs_embeddings.pkl")
            self.fake_storage[str(embeddings_path)] = np.ones((2, 3), dtype=float)

            config = RagConfig(
                index_path=index_path,
                docs_path=docs_path,
                embedding_model_name="local-model",
                fallback_embedding_model_name="local-fallback",
            )
            checksum = RagIndex(config)._compute_checksum(["doc1", "doc2"])  # type: ignore[attr-defined]
            config.metadata_path.write_text(
                json.dumps({"version": config.index_version, "checksum": checksum})
            )
            rag_index = RagIndex(config)

            # Act
            rag_index.load()

            # Assert
            self.assertIsInstance(rag_index._index, FakeIndexFlatIP)
            self.assertEqual(["doc1", "doc2"], rag_index._docs)
            self.assertEqual([["doc1"], ["doc2"]], rag_index._tokenized_docs)
            self.assertIsNotNone(rag_index._keyword_index)
            self.assertIsInstance(rag_index._inverted_index, FakeInvertedIndex)
            self.assertIsNotNone(rag_index._doc_embeddings)

    def test_load_rebuilds_when_version_changes(self) -> None:
        from codeqa.rag_index import RagConfig, RagIndex

        with TemporaryDirectory() as tmp:
            index_path = Path(tmp) / "idx.faiss"
            docs_path = Path(tmp) / "docs.pkl"
            self.fake_storage[str(docs_path)] = ["doc1", "doc2"]
            self.fake_storage[str(docs_path.with_name("docs_tokens.pkl"))] = [
                ["doc1"],
                ["doc2"],
            ]
            self.fake_storage[str(docs_path.with_name("docs_keywords.pkl"))] = {
                "idf": {},
                "doc_lengths": [1, 1],
                "avgdl": 1.0,
            }
            config = RagConfig(
                index_path=index_path,
                docs_path=docs_path,
                embedding_model_name="local-model",
                fallback_embedding_model_name="local-fallback",
            )
            config.metadata_path.write_text(
                json.dumps({"version": "outdated", "checksum": "mismatch"})
            )
            rag_index = RagIndex(config)

            rag_index.load()

            self.assertGreaterEqual(len(rag_index._model.encodes), 1)
            self.assertIn("written", self.fake_storage)

    def test_search_returns_scored_results(self) -> None:
        from codeqa.rag_index import RagConfig, RagIndex

        # Arrange
        rag_index = RagIndex(
            RagConfig(
                index_path=Path("idx"),
                docs_path=Path("docs"),
                embedding_model_name="local-model",
                fallback_embedding_model_name="local-fallback",
            )
        )
        rag_index._index = FakeIndexFlatIP(3)
        rag_index._docs = ["first doc", "second doc"]
        rag_index._tokenized_docs = [["first", "doc"], ["second", "doc"]]
        rag_index._keyword_index = FakeKeywordIndex([(1, 1.0), (0, 0.2)])
        rag_index._inverted_index = FakeInvertedIndex([(0, 0.8)])

        # Act
        results = rag_index.search("What is inside?", k=2, fusion_weight=0.2)

        # Assert
        self.assertEqual(2, len(results))
        self.assertEqual("second doc", results[0][0])
        self.assertGreater(results[0][1], results[1][1])
        self.assertEqual([("What is inside?", 2)], rag_index._keyword_index.searches)
        self.assertEqual([("What is inside?", 2)], rag_index._inverted_index.searches)

    def test_query_embedding_cache_prevents_duplicate_encode(self) -> None:
        from codeqa.rag_index import RagConfig, RagIndex

        rag_index = RagIndex(
            RagConfig(
                index_path=Path("idx"),
                docs_path=Path("docs"),
                embedding_model_name="local-model",
                fallback_embedding_model_name="local-fallback",
            )
        )
        rag_index._index = FakeIndexFlatIP(3)
        rag_index._docs = ["doc"]
        rag_index._tokenized_docs = [["doc"]]
        rag_index._keyword_index = FakeKeywordIndex([(0, 1.0)])
        rag_index._inverted_index = FakeInvertedIndex([(0, 1.0)])

        cache_calls: dict[str, int] = {"set": 0, "encode": 0}

        class CachedModel(FakeModel):
            def encode(self, texts, convert_to_numpy=True, normalize_embeddings=True):  # type: ignore[override]
                cache_calls["encode"] += 1
                return super().encode(
                    texts,
                    convert_to_numpy=convert_to_numpy,
                    normalize_embeddings=normalize_embeddings,
                )

        rag_index._model = CachedModel()
        rag_index._embedding_cache = types.SimpleNamespace(
            get=lambda _query: np.array([0.1, 0.2, 0.3], dtype=float),
            set=lambda _query, _embedding: cache_calls.__setitem__("set", cache_calls["set"] + 1),
        )

        rag_index.search("cached", k=1)
        self.assertEqual(0, cache_calls["encode"])
        self.assertEqual(0, cache_calls["set"])

    def test_falls_back_to_secondary_model_on_load_error(self) -> None:
        from codeqa import rag_index as rag_index_module

        # Arrange
        calls: list[str] = []

        class FlakyModel(FakeModel):
            def __init__(self, name: str, **kwargs: Any) -> None:  # type: ignore[override]
                calls.append(name)
                if len(calls) == 1:
                    raise OSError("primary missing")
                super().__init__(name, **kwargs)

        rag_index_module.SentenceTransformer = FlakyModel  # type: ignore[attr-defined]

        # Act
        rag_index_module.RagIndex(
            rag_index_module.RagConfig(
                index_path=Path("idx"),
                docs_path=Path("docs"),
                embedding_model_name="primary-model",
                fallback_embedding_model_name="fallback-model",
            )
        )

        # Assert
        self.assertEqual(["primary-model", "fallback-model"], calls)

    def test_nomic_model_sets_trust_remote_code_by_default(self) -> None:
        from codeqa import rag_index as rag_index_module

        init_calls: dict[str, Any] = {}

        class CapturingModel(FakeModel):
            def __init__(self, name: str, **kwargs: Any) -> None:  # type: ignore[override]
                init_calls["name"] = name
                init_calls["kwargs"] = kwargs
                super().__init__(name, **kwargs)

        rag_index_module.SentenceTransformer = CapturingModel  # type: ignore[attr-defined]
        rag_index_module.RagIndex._ensure_nomic_dependencies = (  # type: ignore[attr-defined]
            lambda self: None
        )

        rag_index_module.RagIndex(
            rag_index_module.RagConfig(
                index_path=Path("idx"),
                docs_path=Path("docs"),
                embedding_model_name="nomic-ai/nomic-embed-text-v1.5",
            )
        )

        self.assertEqual("nomic-ai/nomic-embed-text-v1.5", init_calls["name"])
        self.assertTrue(init_calls["kwargs"].get("trust_remote_code"))

    def test_nomic_model_respects_provided_trust_remote_code_flag(self) -> None:
        from codeqa import rag_index as rag_index_module

        init_calls: dict[str, Any] = {}

        class CapturingModel(FakeModel):
            def __init__(self, name: str, **kwargs: Any) -> None:  # type: ignore[override]
                init_calls["name"] = name
                init_calls["kwargs"] = kwargs
                super().__init__(name, **kwargs)

        rag_index_module.SentenceTransformer = CapturingModel  # type: ignore[attr-defined]
        rag_index_module.RagIndex._ensure_nomic_dependencies = (  # type: ignore[attr-defined]
            lambda self: None
        )

        rag_index_module.RagIndex(
            rag_index_module.RagConfig(
                index_path=Path("idx"),
                docs_path=Path("docs"),
                embedding_model_name="nomic-ai/nomic-embed-text-v1.5",
                embedding_model_kwargs={"trust_remote_code": False, "device": "cpu"},
            )
        )

        self.assertEqual(
            {"trust_remote_code": False, "device": "cpu"}, init_calls["kwargs"]
        )

    def test_nomic_embedding_requires_sentencepiece(self) -> None:
        from codeqa import rag_index as rag_index_module
        with self.assertRaisesRegex(ImportError, "sentencepiece"):
            with unittest.mock.patch(
                "importlib.import_module", side_effect=ImportError("No module named sentencepiece")
            ):
                rag_index_module.RagIndex(
                    rag_index_module.RagConfig(
                        index_path=Path("idx"),
                        docs_path=Path("docs"),
                        embedding_model_name="nomic-ai/nomic-embed-text-v1.5",
                    )
                )
