from __future__ import annotations

from io import StringIO
from typing import Any

from django.http import HttpRequest
from django.core.management import call_command
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from . import rag_service
from .serializers import BuildRagRequestSerializer, CodeQuestionSerializer


class CodeQAView(APIView):
    """POST endpoint for code Q&A."""

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> Response:
        serializer = CodeQuestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        question: str = serializer.validated_data["question"]
        top_k: int = serializer.validated_data["top_k"]

        try:
            answer, meta = rag_service.answer_question(question=question, top_k=top_k)
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

        return Response({"answer": answer, "meta": meta}, status=status.HTTP_200_OK)


class HealthView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> Response:
        return Response({"status": "ok"}, status=status.HTTP_200_OK)


class BuildRagIndexView(APIView):
    """Trigger rebuilding the RAG index via the management command."""

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> Response:
        serializer = BuildRagRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        root = serializer.validated_data.get("root") or None
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

        return Response(
            {
                "detail": "RAG index build triggered.",
                "output": stdout.getvalue(),
                "errors": stderr.getvalue(),
            },
            status=status.HTTP_200_OK,
        )
