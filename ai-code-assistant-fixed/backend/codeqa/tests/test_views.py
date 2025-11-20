from __future__ import annotations

import importlib
import sys
import types
from types import SimpleNamespace

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

# Provide lightweight substitutes for heavy optional dependencies
sys.modules["faiss"] = types.SimpleNamespace(IndexFlatIP=object, write_index=lambda *_, **__: None, read_index=lambda *_: object())
sys.modules["sentence_transformers"] = types.SimpleNamespace(
    SentenceTransformer=lambda *_, **__: SimpleNamespace(encode=lambda texts, **__: [[0.1] * 3 for _ in texts])
)
sys.modules["joblib"] = types.SimpleNamespace(dump=lambda *_, **__: None, load=lambda *_: [])
sys.modules["ollama"] = types.SimpleNamespace(
    ChatResponse=SimpleNamespace,
    chat=lambda model, messages: SimpleNamespace(message=SimpleNamespace(content="ai")),
)

from codeqa import rag_index as rag_index_module
importlib.reload(rag_index_module)
from codeqa import rag_service as rag_service_module
importlib.reload(rag_service_module)
from codeqa.views import CodeQAView, HealthView


class CodeQAViewTests(SimpleTestCase):
    def setUp(self) -> None:
        self.factory = APIRequestFactory()

    def test_post_returns_answer_payload(self) -> None:
        def fake_answer_question(question: str, top_k: int):
            return "answer text", {"num_contexts": 1}

        rag_service_module.answer_question = fake_answer_question  # type: ignore[assignment]
        request = self.factory.post("/api/code-qa/", {"question": "Hello?"}, format="json")
        view = CodeQAView.as_view()

        response = view(request)

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual("answer text", response.data["answer"])
        self.assertEqual(1, response.data["meta"]["num_contexts"])

    def test_post_returns_503_when_index_missing(self) -> None:
        request = self.factory.post("/api/code-qa/", {"question": "Hello?"}, format="json")
        view = CodeQAView.as_view()

        rag_service_module.answer_question = lambda *_args, **_kwargs: (_ for _ in ()).throw(  # type: ignore[assignment]
            rag_service_module.AnswerNotReadyError("no index")
        )

        response = view(request)

        self.assertEqual(status.HTTP_503_SERVICE_UNAVAILABLE, response.status_code)
        self.assertIn("detail", response.data)


class HealthViewTests(SimpleTestCase):
    def test_returns_ok_status(self) -> None:
        view = HealthView.as_view()
        request = APIRequestFactory().get("/api/health/")
        response = view(request)

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual({"status": "ok"}, response.data)
