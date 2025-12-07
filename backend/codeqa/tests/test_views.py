from __future__ import annotations

import importlib
import os
import sys
import types
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
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
sys.modules["codeqa.inverted_index"] = types.SimpleNamespace(InvertedIndex=SimpleNamespace)
sys.modules["codeqa.embedding_cache"] = types.SimpleNamespace(
    QueryEmbeddingCache=object,
    build_cache_from_env=lambda: SimpleNamespace(get=lambda _q: None, set=lambda _q, _e: None)
)

from codeqa import rag_index as rag_index_module  # noqa: E402
importlib.reload(rag_index_module)
from codeqa import rag_service as rag_service_module  # noqa: E402
importlib.reload(rag_service_module)
from codeqa.rag_state import get_default_root, load_last_root, save_last_root  # noqa: E402
from codeqa.models import Message, Topic  # noqa: E402
from codeqa.views import (  # noqa: E402
    BuildRagIndexView,
    CodeQAStreamView,
    CodeQAView,
    HealthView,
    SearchView,
    TopicDetailView,
    TopicListView,
)


class CodeQAViewTests(TestCase):
    def setUp(self) -> None:
        self.factory = APIRequestFactory()
        Topic.objects.all().delete()

    def test_post_returns_answer_payload(self) -> None:
        # Arrange
        def fake_answer_question(question: str, top_k: int, system_prompt: str, custom_prompt: str | None = None):
            return "answer text", {"num_contexts": 1, "prompt": system_prompt, "custom": custom_prompt}

        rag_service_module.answer_question = fake_answer_question  # type: ignore[assignment]
        request = self.factory.post(
            "/api/code-qa/",
            {"question": "Hello?", "system_prompt": "code expert"},
            format="json",
        )
        view = CodeQAView.as_view()

        # Act
        response = view(request)

        # Assert
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual("answer text", response.data["answer"])
        self.assertEqual(1, response.data["meta"]["num_contexts"])
        self.assertEqual("code expert", response.data["meta"]["prompt"])
        self.assertIsNone(response.data["meta"]["custom"])

    def test_custom_prompt_is_forwarded(self) -> None:
        # Arrange
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

        # Act
        response = CodeQAView.as_view()(request)

        # Assert
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

    def test_stream_view_emits_sse_events(self) -> None:
        rag_service_module.stream_answer = lambda **kwargs: (
            {"num_contexts": 1},
            ["chunk-one", "chunk-two"],
        )

        request = self.factory.post(
            "/api/code-qa/stream/",
            {"question": "Hello?", "system_prompt": "code expert"},
            format="json",
        )

        response = CodeQAStreamView.as_view()(request)
        body = b"".join(response.streaming_content).decode()

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertIn("meta", body)
        self.assertIn("chunk-two", body)

    def test_records_exchange_when_topic_provided(self) -> None:
        # Arrange
        topic = Topic.objects.create(name="New thread")

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

        # Act
        response = CodeQAView.as_view()(request)

        # Assert
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        messages = list(topic.messages.order_by("created_at"))
        self.assertEqual(2, len(messages))
        self.assertEqual("Hello?", messages[0].content)
        self.assertEqual(Message.ROLE_USER, messages[0].role)
        self.assertEqual("stored answer", messages[1].content)

    def test_returns_404_when_topic_missing(self) -> None:
        # Arrange
        request = self.factory.post(
            "/api/code-qa/",
            {"question": "Hello?", "system_prompt": "code expert", "topic_id": 999},
            format="json",
        )

        # Act
        response = CodeQAView.as_view()(request)

        # Assert
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_post_returns_503_when_index_missing(self) -> None:
        # Arrange
        request = self.factory.post(
            "/api/code-qa/",
            {"question": "Hello?", "system_prompt": "code expert"},
            format="json",
        )
        view = CodeQAView.as_view()

        rag_service_module.answer_question = lambda *_args, **_kwargs: (_ for _ in ()).throw(  # type: ignore[assignment]
            rag_service_module.AnswerNotReadyError("no index")
        )

        # Act
        response = view(request)

        # Assert
        self.assertEqual(status.HTTP_503_SERVICE_UNAVAILABLE, response.status_code)
        self.assertIn("detail", response.data)

    def test_requires_custom_prompt_when_needed(self) -> None:
        # Arrange
        request = self.factory.post(
            "/api/code-qa/",
            {"question": "Hello?", "system_prompt": "custom"},
            format="json",
        )

        # Act
        response = CodeQAView.as_view()(request)

        # Assert
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIn("custom_prompt", response.data)


class HealthViewTests(SimpleTestCase):
    def test_returns_ok_status(self) -> None:
        # Arrange
        view = HealthView.as_view()
        request = APIRequestFactory().get("/api/health/")

        # Act
        response = view(request)

        # Assert
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual({"status": "ok"}, response.data)


class BuildRagIndexViewTests(SimpleTestCase):
    def setUp(self) -> None:
        self.factory = APIRequestFactory()
        self.tmpdir = TemporaryDirectory()
        os.environ["RAG_DATA_DIR"] = self.tmpdir.name
        self.addCleanup(self.tmpdir.cleanup)
        self.addCleanup(os.environ.pop, "RAG_DATA_DIR", None)

    def test_triggers_build_with_custom_root(self) -> None:
        # Arrange
        request = self.factory.post(
            "/api/code-qa/build-rag/",
            {"root": "/tmp/project"},
            format="json",
        )

        with patch("codeqa.views.call_command") as mock_call_command:
            # Act
            response = BuildRagIndexView.as_view()(request)

        # Assert
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        args, kwargs = mock_call_command.call_args
        self.assertEqual("build_rag_index", args[0])
        expected_root = str(Path("/tmp/project").resolve())
        self.assertEqual(expected_root, kwargs["root"])
        self.assertIn("stdout", kwargs)
        self.assertIn("stderr", kwargs)
        self.assertEqual(expected_root, response.data["root"])
        self.assertEqual(expected_root, load_last_root())

    def test_defaults_root_when_missing(self) -> None:
        # Arrange
        request = self.factory.post("/api/code-qa/build-rag/", {}, format="json")

        with patch("codeqa.views.call_command") as mock_call_command:
            # Act
            response = BuildRagIndexView.as_view()(request)

        # Assert
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        _args, kwargs = mock_call_command.call_args
        self.assertNotIn("root", kwargs)
        self.assertEqual(get_default_root(), response.data["root"])
        self.assertEqual(get_default_root(), load_last_root())

    def test_returns_error_on_failure(self) -> None:
        # Arrange
        request = self.factory.post("/api/code-qa/build-rag/", {}, format="json")

        with patch("codeqa.views.call_command", side_effect=RuntimeError("boom")):
            # Act
            response = BuildRagIndexView.as_view()(request)

        # Assert
        self.assertEqual(status.HTTP_500_INTERNAL_SERVER_ERROR, response.status_code)
        self.assertIn("detail", response.data)

    def test_get_returns_last_used_root(self) -> None:
        # Arrange
        stored_root = str(Path(self.tmpdir.name) / "project")
        save_last_root(stored_root)

        request = self.factory.get("/api/code-qa/build-rag/")

        # Act
        response = BuildRagIndexView.as_view()(request)

        # Assert
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(stored_root, response.data["root"])

    def test_get_returns_default_when_state_missing(self) -> None:
        # Arrange
        request = self.factory.get("/api/code-qa/build-rag/")

        # Act
        response = BuildRagIndexView.as_view()(request)

        # Assert
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(get_default_root(), response.data["root"])


class TopicViewsTests(TestCase):
    def setUp(self) -> None:
        self.factory = APIRequestFactory()
        Topic.objects.all().delete()

    def test_creates_topic(self) -> None:
        # Arrange
        request = self.factory.post("/api/topics/", {"name": "Release notes"}, format="json")

        # Act
        response = TopicListView.as_view()(request)

        # Assert
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertEqual("Release notes", response.data["name"])
        self.assertEqual([], response.data["messages"])
        self.assertEqual(0, response.data["message_count"])

    def test_lists_topics(self) -> None:
        # Arrange
        Topic.objects.bulk_create([Topic(name="One"), Topic(name="Two"), Topic(name="Three")])

        request = self.factory.get("/api/topics/?limit=2&offset=0")

        # Act
        response = TopicListView.as_view()(request)

        # Assert
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(2, len(response.data["topics"]))
        self.assertEqual(2, response.data["next_offset"])

        second_page = TopicListView.as_view()(self.factory.get("/api/topics/?limit=2&offset=2"))
        self.assertEqual(1, len(second_page.data["topics"]))
        self.assertIsNone(second_page.data["next_offset"])

        self.assertTrue(all("message_count" in topic for topic in response.data["topics"]))

    def test_returns_detail_with_messages(self) -> None:
        # Arrange
        topic = Topic.objects.create(name="Docs")
        Message.objects.create(topic=topic, role=Message.ROLE_USER, content="Question?")
        Message.objects.create(topic=topic, role=Message.ROLE_ASSISTANT, content="Answer")
        Message.objects.create(topic=topic, role=Message.ROLE_ASSISTANT, content="Extra")

        request = self.factory.get(f"/api/topics/{topic.id}/?limit=2&offset=1")

        # Act
        response = TopicDetailView.as_view()(request, topic_id=topic.id)

        # Assert
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(2, len(response.data["messages"]))
        self.assertEqual("Docs", response.data["name"])
        self.assertEqual(3, response.data["message_count"])
        self.assertIsNone(response.data["next_offset"])
        self.assertEqual("Answer", response.data["messages"][0]["content"])

    def test_returns_404_for_missing_topic(self) -> None:
        # Arrange
        request = self.factory.get("/api/topics/999/")

        # Act
        response = TopicDetailView.as_view()(request, topic_id=999)

        # Assert
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)


class SearchViewTests(TestCase):
    def setUp(self) -> None:
        self.factory = APIRequestFactory()
        Topic.objects.all().delete()

    def test_returns_grouped_results(self) -> None:
        # Arrange
        alpha = Topic.objects.create(name="Alpha guide")
        beta = Topic.objects.create(name="Beta release")
        Message.objects.bulk_create(
            [
                Message(topic=alpha, role=Message.ROLE_USER, content="How to deploy?"),
                Message(topic=alpha, role=Message.ROLE_ASSISTANT, content="Use docker-compose"),
                Message(topic=beta, role=Message.ROLE_USER, content="Release checklist"),
                Message(topic=beta, role=Message.ROLE_ASSISTANT, content="Validate migrations"),
            ]
        )

        request = self.factory.get("/api/search/?q=release&limit=5")

        # Act
        response = SearchView.as_view()(request)

        # Assert
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(1, len(response.data["topics"]["items"]))
        self.assertEqual("Beta release", response.data["topics"]["items"][0]["name"])
        self.assertEqual(1, len(response.data["questions"]["items"]))
        self.assertEqual("Release checklist", response.data["questions"]["items"][0]["content"])
        self.assertEqual(1, len(response.data["answers"]["items"]))
        self.assertIn("migrations", response.data["answers"]["items"][0]["content"])

    def test_supports_offsets(self) -> None:
        # Arrange
        topic = Topic.objects.create(name="Changelog")
        Message.objects.bulk_create(
            [
                Message(topic=topic, role=Message.ROLE_USER, content="First question"),
                Message(topic=topic, role=Message.ROLE_USER, content="Second question"),
                Message(topic=topic, role=Message.ROLE_USER, content="Third question"),
            ]
        )

        # Act
        first_page = SearchView.as_view()(self.factory.get("/api/search/?q=question&limit=2"))
        self.assertEqual(2, len(first_page.data["questions"]["items"]))
        self.assertEqual(2, first_page.data["questions"]["next_offset"])

        second_page = SearchView.as_view()(
            self.factory.get("/api/search/?q=question&limit=2&questions_offset=2")
        )

        # Assert
        self.assertEqual(1, len(second_page.data["questions"]["items"]))
        self.assertIsNone(second_page.data["questions"]["next_offset"])
