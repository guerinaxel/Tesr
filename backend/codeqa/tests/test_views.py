from __future__ import annotations

import importlib
import sys
import types
from types import SimpleNamespace
from unittest.mock import patch

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
from codeqa.views import BuildRagIndexView, CodeQAView, HealthView


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


class BuildRagIndexViewTests(SimpleTestCase):
    def setUp(self) -> None:
        self.factory = APIRequestFactory()

    def test_triggers_build_with_custom_root(self) -> None:
        request = self.factory.post(
            "/api/code-qa/build-rag/",
            {"root": "/tmp/project"},
            format="json",
        )

        with patch("codeqa.views.call_command") as mock_call_command:
            response = BuildRagIndexView.as_view()(request)

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        args, kwargs = mock_call_command.call_args
        self.assertEqual("build_rag_index", args[0])
        self.assertEqual("/tmp/project", kwargs["root"])
        self.assertIn("stdout", kwargs)
        self.assertIn("stderr", kwargs)

    def test_defaults_root_when_missing(self) -> None:
        request = self.factory.post("/api/code-qa/build-rag/", {}, format="json")

        with patch("codeqa.views.call_command") as mock_call_command:
            response = BuildRagIndexView.as_view()(request)

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        _args, kwargs = mock_call_command.call_args
        self.assertNotIn("root", kwargs)

    def test_returns_error_on_failure(self) -> None:
        request = self.factory.post("/api/code-qa/build-rag/", {}, format="json")

        with patch("codeqa.views.call_command", side_effect=RuntimeError("boom")):
            response = BuildRagIndexView.as_view()(request)

        self.assertEqual(status.HTTP_500_INTERNAL_SERVER_ERROR, response.status_code)
        self.assertIn("detail", response.data)
