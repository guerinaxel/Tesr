from __future__ import annotations

import importlib
import sys
import types
from types import SimpleNamespace

from django.test import SimpleTestCase


class RagServiceTests(SimpleTestCase):
    def setUp(self) -> None:
        sys.modules["faiss"] = types.SimpleNamespace(IndexFlatIP=object, write_index=lambda *_, **__: None, read_index=lambda *_: object())
        sys.modules["sentence_transformers"] = types.SimpleNamespace(SentenceTransformer=lambda *_, **__: SimpleNamespace(encode=lambda texts, **__: [[0.1] * 3 for _ in texts]))
        sys.modules["joblib"] = types.SimpleNamespace(dump=lambda *_, **__: None, load=lambda *_: [])

        sys.modules["ollama"] = types.SimpleNamespace(
            ChatResponse=SimpleNamespace,
            chat=lambda model, messages: SimpleNamespace(message=SimpleNamespace(content=f"answer from {model}")),
        )
        from codeqa import rag_index as rag_index_module
        importlib.reload(rag_index_module)
        from codeqa import rag_service as rag_service_module
        importlib.reload(rag_service_module)
        self.rag_service = rag_service_module

    def test_answer_question_builds_context_and_returns_meta(self) -> None:
        class FakeIndex:
            def search(self, query: str, k: int):
                return [(f"snippet for {query}", 0.42)]

        self.rag_service._rag_index = FakeIndex()

        answer, meta = self.rag_service.answer_question("How?", top_k=3)

        self.assertIn("answer", answer)
        self.assertEqual(1, meta["num_contexts"])
        self.assertEqual(0.42, meta["contexts"][0]["score"])

    def test_answer_question_raises_when_no_context(self) -> None:
        class EmptyIndex:
            def search(self, query: str, k: int):
                return []

        self.rag_service._rag_index = EmptyIndex()

        with self.assertRaises(self.rag_service.AnswerNotReadyError):
            self.rag_service.answer_question("Missing")
