from __future__ import annotations

from io import StringIO
import inspect
import os
from pathlib import Path
from typing import Any

from django.http import HttpRequest
from django.core.management import call_command
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from . import rag_service
from .serializers import (
    BuildRagRequestSerializer,
    CodeQuestionSerializer,
    TopicCreateSerializer,
)
from .topics import topic_store


class CodeQAView(APIView):
    """POST endpoint for code Q&A."""

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> Response:
        serializer = CodeQuestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        question: str = serializer.validated_data["question"]
        top_k: int = serializer.validated_data["top_k"]
        fusion_weight: float = serializer.validated_data.get("fusion_weight", 0.5)
        system_prompt: str = serializer.validated_data["system_prompt"]
        custom_prompt: str | None = serializer.validated_data.get("custom_prompt")
        typo_prompt: str | None = serializer.validated_data.get("custom_pront")
        topic_id: int | None = serializer.validated_data.get("topic_id")

        if topic_id is not None and topic_store.get_topic(topic_id) is None:
            return Response(
                {"detail": "Topic not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        answer_kwargs: dict[str, Any] = {
            "question": question,
            "top_k": top_k,
            "system_prompt": system_prompt,
            "custom_prompt": custom_prompt or typo_prompt,
        }

        signature = inspect.signature(rag_service.answer_question)
        if "fusion_weight" in signature.parameters or any(
            param.kind == inspect.Parameter.VAR_KEYWORD
            for param in signature.parameters.values()
        ):
            answer_kwargs["fusion_weight"] = fusion_weight

        try:
            answer, meta = rag_service.answer_question(**answer_kwargs)
        except rag_service.AnswerNotReadyError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            return Response(
                {"detail": "Internal server error.", "errors": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if topic_id is not None:
            try:
                topic_store.add_exchange(topic_id, question=question, answer=answer)
            except KeyError:
                return Response(
                    {"detail": "Topic not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        return Response({"answer": answer, "meta": meta}, status=status.HTTP_200_OK)


class TopicListView(APIView):
    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> Response:
        return Response({"topics": topic_store.list_topics()}, status=status.HTTP_200_OK)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> Response:
        serializer = TopicCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        topic = topic_store.create_topic(serializer.validated_data["name"])
        return Response(topic.to_dict(), status=status.HTTP_201_CREATED)


class TopicDetailView(APIView):
    def get(self, request: HttpRequest, topic_id: int, *args: Any, **kwargs: Any) -> Response:
        topic_data = topic_store.serialize_topic(topic_id)
        if topic_data is None:
            return Response({"detail": "Topic not found."}, status=status.HTTP_404_NOT_FOUND)

        return Response(topic_data, status=status.HTTP_200_OK)


class HealthView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> Response:
        return Response({"status": "ok"}, status=status.HTTP_200_OK)


class BuildRagIndexView(APIView):
    """Trigger rebuilding the RAG index via the management command."""

    _last_root_filename = "last_rag_root.txt"

    @staticmethod
    def _get_last_root_path() -> Path:
        data_dir = Path(
            os.getenv("RAG_DATA_DIR", Path(__file__).resolve().parent / "data")
        )
        return data_dir / BuildRagIndexView._last_root_filename

    @classmethod
    def _load_last_root(cls) -> str | None:
        last_root_path = cls._get_last_root_path()
        try:
            content = last_root_path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return None
        return content or None

    @classmethod
    def _persist_last_root(cls, root: str) -> None:
        last_root_path = cls._get_last_root_path()
        last_root_path.parent.mkdir(parents=True, exist_ok=True)
        last_root_path.write_text(root, encoding="utf-8")

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> Response:
        serializer = BuildRagRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        provided_root = serializer.validated_data.get("root") or None
        root = (provided_root or "").strip() or self._load_last_root()
        stdout, stderr = StringIO(), StringIO()

        try:
            command_kwargs: dict[str, Any] = {"stdout": stdout, "stderr": stderr}
            if root:
                command_kwargs["root"] = root

            call_command("build_rag_index", **command_kwargs)
        except Exception:
            return Response(
                {
                    "detail": "Failed to build RAG index.",
                    "errors": stderr.getvalue(),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if root:
            self._persist_last_root(root)

        return Response(
            {
                "detail": "RAG index build triggered.",
                "output": stdout.getvalue(),
                "errors": stderr.getvalue(),
            },
            status=status.HTTP_200_OK,
        )
