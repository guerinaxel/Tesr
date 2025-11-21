from __future__ import annotations

from typing import Any

from django.http import HttpRequest
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .rag_service import AnswerNotReadyError, answer_question
from .serializers import CodeQuestionSerializer


class CodeQAView(APIView):
    """POST endpoint for code Q&A."""

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> Response:
        serializer = CodeQuestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        question: str = serializer.validated_data["question"]
        top_k: int = serializer.validated_data["top_k"]

        try:
            answer, meta = answer_question(question=question, top_k=top_k)
        except AnswerNotReadyError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception:
            return Response(
                {"detail": "Internal server error."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response({"answer": answer, "meta": meta}, status=status.HTTP_200_OK)


class HealthView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> Response:
        return Response({"status": "ok"}, status=status.HTTP_200_OK)
