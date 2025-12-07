from __future__ import annotations

import importlib
import sys
import types
import os
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from codeqa.models import RagSource


class RagServiceTests(SimpleTestCase):
    def setUp(self) -> None:
        sys.modules["faiss"] = types.SimpleNamespace(
            IndexFlatIP=object,
            write_index=lambda *_, **__: None,
            read_index=lambda *_: object(),
        )
        sys.modules["sentence_transformers"] = types.SimpleNamespace(
            SentenceTransformer=lambda *_, **__: SimpleNamespace(
                encode=lambda texts, **__: [[0.1] * 3 for _ in texts]
            )
        )
        sys.modules["joblib"] = types.SimpleNamespace(dump=lambda *_, **__: None, load=lambda *_: [])

        def fake_chat(model, messages, stream=False, **_kwargs):  # type: ignore[override]
            if stream:
                def _gen():
                    yield SimpleNamespace(message={"content": f"{model}-chunk"})

                return _gen()
            return SimpleNamespace(message=SimpleNamespace(content=f"answer from {model}"))

        sys.modules["ollama"] = types.SimpleNamespace(
            ChatResponse=SimpleNamespace,
            chat=fake_chat,
        )
        sys.modules["codeqa.inverted_index"] = types.SimpleNamespace(InvertedIndex=SimpleNamespace)
        sys.modules["codeqa.embedding_cache"] = types.SimpleNamespace(
            QueryEmbeddingCache=object,
            build_cache_from_env=lambda: SimpleNamespace(get=lambda _q: None, set=lambda _q, _e: None)
        )
        from codeqa import rag_index as rag_index_module
        importlib.reload(rag_index_module)
        from codeqa import rag_service as rag_service_module
        importlib.reload(rag_service_module)
        self.rag_service = rag_service_module
        def fake_gather(question: str, top_k: int, fusion_weight: float, sources):
            hits = self.rag_service._rag_index.search(
                question, k=top_k, fusion_weight=fusion_weight
            )
            if not hits:
                raise self.rag_service.AnswerNotReadyError("RAG index is empty.")
            return [(snippet, score, "source-id", "Source") for snippet, score in hits]

        self.rag_service._gather_contexts = fake_gather

    def test_answer_question_builds_context_and_returns_meta(self) -> None:
        # Arrange
        class FakeIndex:
            def search(self, query: str, k: int, fusion_weight: float = 0.5):
                return [(f"snippet for {query}", 0.42)]

        self.rag_service._rag_index = FakeIndex()

        # Act
        answer, meta = self.rag_service.answer_question(
            "How?", top_k=3, sources=["source-id"]
        )

        # Assert
        self.assertIn("answer", answer)
        self.assertEqual(1, meta["num_contexts"])
        self.assertEqual(0.42, meta["contexts"][0]["score"])
        self.assertEqual(["source-id"], meta["sources"])

    def test_answer_question_raises_when_no_context(self) -> None:
        # Arrange
        class EmptyIndex:
            def search(self, query: str, k: int, fusion_weight: float = 0.5):
                return []

        self.rag_service._rag_index = EmptyIndex()

        # Act & Assert
        with self.assertRaises(self.rag_service.AnswerNotReadyError):
            self.rag_service.answer_question("Missing", sources=["source-id"])

    def test_stream_answer_returns_tokens_and_meta(self) -> None:
        class FakeIndex:
            def search(self, query: str, k: int, fusion_weight: float = 0.5):
                return [(f"snippet for {query}", 0.42)]

        self.rag_service._rag_index = FakeIndex()

        meta, stream = self.rag_service.stream_answer("Hello", sources=["source-id"])
        tokens = list(stream)

        self.assertEqual(1, meta["num_contexts"])
        self.assertTrue(any("llama3.1:8b" in token for token in tokens))

    def test_document_expert_uses_qwen_model(self) -> None:
        # Arrange
        class FakeIndex:
            def search(self, query: str, k: int, fusion_weight: float = 0.5):
                return [(f"snippet for {query}", 0.42)]

        self.rag_service._rag_index = FakeIndex()

        # Act
        answer, _meta = self.rag_service.answer_question(
            "Doc?", system_prompt="document expert", sources=["source-id"]
        )

        # Assert
        self.assertIn("qwen2.5vl:7b", answer)

    def test_document_expert_falls_back_when_primary_fails(self) -> None:
        # Arrange
        class FakeIndex:
            def search(self, query: str, k: int, fusion_weight: float = 0.5):
                return [(f"snippet for {query}", 0.42)]

        self.rag_service._rag_index = FakeIndex()

        os.environ["OLLAMA_DOC_MODEL_NAME"] = "primary-model"
        os.environ["OLLAMA_DOC_MODEL_FALLBACK"] = "fallback-model"

        original_chat = self.rag_service.chat

        def flaky_chat(model, messages, **_kwargs):  # type: ignore[override]
            if model == "primary-model":
                raise RuntimeError("primary failed")
            return SimpleNamespace(message=SimpleNamespace(content=f"answer from {model}"))

        self.rag_service.chat = flaky_chat

        # Act
        try:
            answer, _meta = self.rag_service.answer_question(
                "Doc?", system_prompt="document expert", sources=["source-id"]
            )
        finally:
            self.rag_service.chat = original_chat
            os.environ.pop("OLLAMA_DOC_MODEL_NAME", None)
            os.environ.pop("OLLAMA_DOC_MODEL_FALLBACK", None)

        # Assert
        self.assertIn("fallback-model", answer)


class RagServiceMultiSourceTests(TestCase):
    def setUp(self) -> None:
        sys.modules["faiss"] = types.SimpleNamespace(
            IndexFlatIP=object,
            write_index=lambda *_, **__: None,
            read_index=lambda *_: object(),
        )
        sys.modules["sentence_transformers"] = types.SimpleNamespace(
            SentenceTransformer=lambda *_, **__: SimpleNamespace(
                encode=lambda texts, **__: [[0.1] * 3 for _ in texts]
            )
        )
        sys.modules["joblib"] = types.SimpleNamespace(dump=lambda *_, **__: None, load=lambda *_: [])
        sys.modules["ollama"] = types.SimpleNamespace(
            ChatResponse=SimpleNamespace,
            chat=lambda *_, **__: SimpleNamespace(message=SimpleNamespace(content="answer")),
        )
        sys.modules["codeqa.inverted_index"] = types.SimpleNamespace(InvertedIndex=SimpleNamespace)
        sys.modules["codeqa.embedding_cache"] = types.SimpleNamespace(
            QueryEmbeddingCache=object,
            build_cache_from_env=lambda: SimpleNamespace(get=lambda _q: None, set=lambda _q, _e: None),
        )
        from codeqa import rag_service as rag_service_module

        self.rag_service = rag_service_module
        self.rag_service._rag_indexes = {}
        self.rag_service._rag_sources_cache = {}

        self.source_a = RagSource.objects.create(
            name="Source A", description="first", path="/tmp/a", total_files=1, total_chunks=2
        )
        self.source_b = RagSource.objects.create(
            name="Source B", description="second", path="/tmp/b", total_files=1, total_chunks=2
        )

    def test_gather_contexts_normalizes_scores_across_sources(self) -> None:
        # Arrange
        class SourceIndex:
            def __init__(self, scores: list[float]):
                self.scores = scores

            def search(self, _query: str, k: int, fusion_weight: float = 0.5):
                return [(f"snippet-{score}", score) for score in self.scores[:k]]

        def fake_load(source: RagSource):
            return SourceIndex([0.2, 0.4]) if source.id == self.source_a.id else SourceIndex([0.9])

        with patch.object(self.rag_service, "_load_rag_source", fake_load):
            contexts = self.rag_service._gather_contexts(
                "question", top_k=3, fusion_weight=0.5, sources=[self.source_a.id, self.source_b.id]
            )

        # Assert
        self.assertEqual(3, len(contexts))
        scores = [score for _, score, *_ in contexts]
        self.assertTrue(all(0 <= score <= 1 for score in scores))
        source_ids = [uuid for *_snippet, uuid, _name in contexts]
        self.assertEqual([str(self.source_b.id), str(self.source_a.id), str(self.source_a.id)], source_ids)
