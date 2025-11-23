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
    chat=lambda model, messages, **kwargs: SimpleNamespace(message=SimpleNamespace(content="ai")),
)

from codeqa import rag_index as rag_index_module  # noqa: E402
importlib.reload(rag_index_module)
from codeqa import rag_service as rag_service_module  # noqa: E402
importlib.reload(rag_service_module)
from codeqa.topics import topic_store  # noqa: E402
from codeqa.views import (  # noqa: E402
    BuildRagIndexView,
    CodeQAView,
    HealthView,
    TopicDetailView,
    TopicListView,
)


class CodeQAViewTests(SimpleTestCase):
    def setUp(self) -> None:
        self.factory = APIRequestFactory()
        topic_store.reset()

    def test_post_returns_answer_payload(self) -> None:
        def fake_answer_question(question: str, top_k: int, system_prompt: str, custom_prompt: str | None = None):
            return "answer text", {"num_contexts": 1, "prompt": system_prompt, "custom": custom_prompt}

        rag_service_module.answer_question = fake_answer_question  # type: ignore[assignment]
        request = self.factory.post(
            "/api/code-qa/",
            {"question": "Hello?", "system_prompt": "code expert"},
            format="json",
        )
        view = CodeQAView.as_view()

        response = view(request)

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual("answer text", response.data["answer"])
        self.assertEqual(1, response.data["meta"]["num_contexts"])
        self.assertEqual("code expert", response.data["meta"]["prompt"])
        self.assertIsNone(response.data["meta"]["custom"])

    def test_custom_prompt_is_forwarded(self) -> None:
        captured: dict[str, str | None] = {}

        def fake_answer_question(
            question: str,
            top_k: int,
            system_prompt: str,
            custom_prompt: str | None = None,
        ):
            captured.update(
                {
                    "question": question,
                    "top_k": str(top_k),
                    "system_prompt": system_prompt,
                    "custom_prompt": custom_prompt,
                }
            )
            return "answer text", {"num_contexts": 1}

        rag_service_module.answer_question = fake_answer_question  # type: ignore[assignment]
        request = self.factory.post(
            "/api/code-qa/",
            {"question": "Hi?", "system_prompt": "custom", "custom_prompt": "Act polite"},
            format="json",
        )

        response = CodeQAView.as_view()(request)

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(
            {
                "question": "Hi?",
                "top_k": "5",
                "system_prompt": "custom",
                "custom_prompt": "Act polite",
            },
            captured,
        )

    def test_records_exchange_when_topic_provided(self) -> None:
        topic = topic_store.create_topic("New thread")

        def fake_answer_question(
            question: str,
            top_k: int,
            system_prompt: str,
            custom_prompt: str | None = None,
        ):
            return "stored answer", {"num_contexts": 1}

        rag_service_module.answer_question = fake_answer_question  # type: ignore[assignment]
        request = self.factory.post(
            "/api/code-qa/",
            {"question": "Hello?", "system_prompt": "code expert", "topic_id": topic.id},
            format="json",
        )

        response = CodeQAView.as_view()(request)

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        stored = topic_store.serialize_topic(topic.id)
        assert stored is not None
        self.assertEqual(2, len(stored["messages"]))
        self.assertEqual("Hello?", stored["messages"][0]["content"])
        self.assertEqual("stored answer", stored["messages"][1]["content"])

    def test_returns_404_when_topic_missing(self) -> None:
        request = self.factory.post(
            "/api/code-qa/",
            {"question": "Hello?", "system_prompt": "code expert", "topic_id": 999},
            format="json",
        )

        response = CodeQAView.as_view()(request)

        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_post_returns_503_when_index_missing(self) -> None:
        request = self.factory.post(
            "/api/code-qa/",
            {"question": "Hello?", "system_prompt": "code expert"},
            format="json",
        )
        view = CodeQAView.as_view()

        rag_service_module.answer_question = lambda *_args, **_kwargs: (_ for _ in ()).throw(  # type: ignore[assignment]
            rag_service_module.AnswerNotReadyError("no index")
        )

        response = view(request)

        self.assertEqual(status.HTTP_503_SERVICE_UNAVAILABLE, response.status_code)
        self.assertIn("detail", response.data)

    def test_requires_custom_prompt_when_needed(self) -> None:
        request = self.factory.post(
            "/api/code-qa/",
            {"question": "Hello?", "system_prompt": "custom"},
            format="json",
        )

        response = CodeQAView.as_view()(request)

        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIn("custom_prompt", response.data)


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


class TopicViewsTests(SimpleTestCase):
    def setUp(self) -> None:
        self.factory = APIRequestFactory()
        topic_store.reset()

    def test_creates_topic(self) -> None:
        request = self.factory.post("/api/topics/", {"name": "Release notes"}, format="json")

        response = TopicListView.as_view()(request)

        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertEqual("Release notes", response.data["name"])
        self.assertEqual([], response.data["messages"])

    def test_lists_topics(self) -> None:
        topic_store.create_topic("One")
        topic_store.create_topic("Two")

        request = self.factory.get("/api/topics/")
        response = TopicListView.as_view()(request)

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(2, len(response.data["topics"]))
        self.assertTrue(all("message_count" in topic for topic in response.data["topics"]))

    def test_returns_detail_with_messages(self) -> None:
        topic = topic_store.create_topic("Docs")
        topic_store.add_exchange(topic.id, "Question?", "Answer")

        request = self.factory.get(f"/api/topics/{topic.id}/")
        response = TopicDetailView.as_view()(request, topic_id=topic.id)

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(2, len(response.data["messages"]))
        self.assertEqual("Docs", response.data["name"])

    def test_returns_404_for_missing_topic(self) -> None:
        request = self.factory.get("/api/topics/999/")
        response = TopicDetailView.as_view()(request, topic_id=999)

        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)
